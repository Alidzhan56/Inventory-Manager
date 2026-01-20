# inventory/routes/transactions.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from inventory.extensions import db
from inventory.models import Product, Partner, Warehouse, Transaction, TransactionItem, Stock
from inventory.transactions.services import TransactionService
from inventory.transactions.validators import validate_transaction_form_data
from inventory.utils.translations import _
from inventory.utils.permissions import has_permission

bp = Blueprint("transactions", __name__)


def _get_owner_id():
    # org owner logic (Developer is special)
    if current_user.role == "Developer":
        return None
    if current_user.role == "Admin / Owner":
        return current_user.id
    return current_user.created_by_id


@bp.route("/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    # View permission
    if not has_permission(current_user, "transactions:view"):
        flash(_("You do not have permission to view transactions."), "danger")
        return redirect(url_for("main.index"))

    owner_id = _get_owner_id()

    # Dropdown data (owner scoped)
    products_q = Product.query.order_by(Product.name.asc())
    partners_q = Partner.query.order_by(Partner.name.asc())
    warehouses_q = Warehouse.query.order_by(Warehouse.name.asc())

    if owner_id is not None:
        products_q = products_q.filter_by(owner_id=owner_id)
        partners_q = partners_q.filter_by(owner_id=owner_id)
        warehouses_q = warehouses_q.filter_by(owner_id=owner_id)

    products = products_q.all()
    partners = partners_q.all()
    warehouses = warehouses_q.all()

    # -------------------- CREATE TRANSACTION -------------------- #
    if request.method == "POST":
        ttype = (request.form.get("type") or "").strip()
        partner_id = request.form.get("partner_id")
        warehouse_id = request.form.get("warehouse_id")

        # Permission rules per transaction type
        if ttype == "Sale":
            if not has_permission(current_user, "transactions:create_sale"):
                flash(_("You do not have permission to record sales."), "danger")
                return redirect(url_for("transactions.transactions"))
        elif ttype == "Purchase":
            if not has_permission(current_user, "transactions:create_purchase"):
                flash(_("You do not have permission to record purchases."), "danger")
                return redirect(url_for("transactions.transactions"))
        else:
            flash(_("Invalid transaction type."), "danger")
            return redirect(url_for("transactions.transactions"))

        product_ids = request.form.getlist("product_id[]")
        quantities = request.form.getlist("qty[]")
        prices = request.form.getlist("unit_price[]")

        # Build rows, skip empty product rows
        items = []
        for pid, q, p in zip(product_ids, quantities, prices):
            pid = (pid or "").strip()
            if not pid:
                continue
            items.append({"product_id": pid, "quantity": q, "unit_price": p})

        errors = validate_transaction_form_data(ttype, partner_id, warehouse_id, items)
        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("transactions.transactions"))

        # Developer safety: avoid creating mixed org data accidentally
        if owner_id is None:
            flash(_("Developer must create transactions from an owner context."), "warning")
            return redirect(url_for("transactions.transactions"))

        # Security: make sure chosen warehouse/partner belong to this owner
        wh_ok = Warehouse.query.filter_by(id=warehouse_id, owner_id=owner_id).first()
        if not wh_ok:
            flash(_("Invalid warehouse."), "danger")
            return redirect(url_for("transactions.transactions"))

        pr_ok = Partner.query.filter_by(id=partner_id, owner_id=owner_id).first()
        if not pr_ok:
            flash(_("Invalid partner."), "danger")
            return redirect(url_for("transactions.transactions"))

        # Validate products ownership
        requested_ids = []
        for row in items:
            try:
                requested_ids.append(int(row["product_id"]))
            except Exception:
                flash(_("Invalid product."), "danger")
                return redirect(url_for("transactions.transactions"))

        owned_products = (
            Product.query
            .filter(Product.owner_id == owner_id, Product.id.in_(requested_ids))
            .with_entities(Product.id)
            .all()
        )
        owned_ids = {pid for (pid,) in owned_products}

        for pid in requested_ids:
            if pid not in owned_ids:
                flash(_("Invalid product."), "danger")
                return redirect(url_for("transactions.transactions"))

        result = TransactionService.create_transaction(
            ttype=ttype,
            partner_id=partner_id,
            warehouse_id=warehouse_id,
            user_id=current_user.id,
            items=items,
        )

        if result.get("error"):
            flash(result["error"], "danger")
            return redirect(url_for("transactions.transactions"))

        flash(_("Transaction recorded successfully."), "success")
        return redirect(url_for("transactions.transactions"))

    # -------------------- LIST + FILTERS -------------------- #
    q_type = (request.args.get("type") or "").strip()
    q_partner_id = (request.args.get("partner_id") or "").strip()
    q_product_id = (request.args.get("product_id") or "").strip()

    tx_query = (
        Transaction.query
        .join(Warehouse, Transaction.warehouse_id == Warehouse.id)
        .options(
            db.joinedload(Transaction.items).joinedload(TransactionItem.product),
            db.joinedload(Transaction.partner),
            db.joinedload(Transaction.warehouse),
            db.joinedload(Transaction.user),
        )
        .order_by(Transaction.date.desc())
    )

    if owner_id is not None:
        tx_query = tx_query.filter(Warehouse.owner_id == owner_id)

    if q_type in {"Purchase", "Sale"}:
        tx_query = tx_query.filter(Transaction.type == q_type)

    if q_partner_id.isdigit():
        tx_query = tx_query.filter(Transaction.partner_id == int(q_partner_id))

    # Filter by product: txns that have at least one line with that product
    if q_product_id.isdigit():
        tx_query = (
            tx_query
            .join(TransactionItem, TransactionItem.transaction_id == Transaction.id)
            .filter(TransactionItem.product_id == int(q_product_id))
            .distinct()
        )

    txns = tx_query.all()

    return render_template(
        "transactions.html",
        products=products,
        partners=partners,
        warehouses=warehouses,
        txns=txns,
    )


@bp.route("/api/stock")
@login_required
def api_stock():
    """
    Returns available stock for a product in a warehouse:
    GET /api/stock?warehouse_id=1&product_id=2
    """
    if not has_permission(current_user, "transactions:view"):
        return jsonify({"ok": False, "error": "Forbidden."}), 403

    owner_id = _get_owner_id()

    warehouse_id = request.args.get("warehouse_id", type=int)
    product_id = request.args.get("product_id", type=int)

    if not warehouse_id or not product_id:
        return jsonify({"ok": False, "error": "Missing parameters."}), 400

    # Developer safety: avoid returning mixed org data accidentally
    if owner_id is None:
        return jsonify({"ok": False, "error": "Owner context required."}), 403

    # Make sure warehouse & product belong to this org
    wh_ok = Warehouse.query.filter_by(id=warehouse_id, owner_id=owner_id).first()
    if not wh_ok:
        return jsonify({"ok": False, "error": "Invalid warehouse."}), 403

    pr_ok = Product.query.filter_by(id=product_id, owner_id=owner_id).first()
    if not pr_ok:
        return jsonify({"ok": False, "error": "Invalid product."}), 403

    stock = Stock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
    qty = int(stock.quantity) if stock and stock.quantity is not None else 0

    return jsonify({"ok": True, "quantity": qty})
