from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from inventory.models import Product, Partner, Warehouse, Transaction
from inventory.transactions.validators import validate_transaction_form
from inventory.transactions.services import TransactionService

bp = Blueprint('transactions', __name__)


@bp.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id

    products = Product.query.filter_by(owner_id=owner_id).all()
    partners = Partner.query.filter_by(owner_id=owner_id).all()
    warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()

    # Handle filters
    filters = {}
    type_filter = request.args.get("type")
    product_filter = request.args.get("product_id")
    partner_filter = request.args.get("partner_id")
    if type_filter:
        filters["type"] = type_filter
    if product_filter:
        filters["product_id"] = product_filter
    if partner_filter:
        filters["partner_id"] = partner_filter

    txns_query = Transaction.query.join(Product).filter(Product.owner_id == owner_id)
    for key, value in filters.items():
        txns_query = txns_query.filter(getattr(Transaction, key) == value)
    txns = txns_query.order_by(Transaction.date.desc()).all()

    if request.method == 'POST':
        ttype = request.form.get("type")
        warehouse_id = request.form.get("warehouse_id")
        partner_id = request.form.get("partner_id")

        product_ids = request.form.getlist("product_id[]")
        quantities = request.form.getlist("quantity[]")

        errors = []
        for pid, qty in zip(product_ids, quantities):
            form_data = {
                "type": ttype,
                "product_id": pid,
                "partner_id": partner_id,
                "warehouse_id": warehouse_id,
                "quantity": qty
            }
            err = validate_transaction_form(form_data)
            if err:
                errors.extend(err)

        if errors:
            for e in errors:
                flash(e, "danger")
            return redirect(url_for("transactions.transactions"))

        # Create multiple transactions
        for pid, qty in zip(product_ids, quantities):
            result = TransactionService.create_transaction(
                ttype=ttype,
                product_id=pid,
                partner_id=partner_id,
                warehouse_id=warehouse_id,
                quantity=int(qty),
                user_id=current_user.id
            )
            if "error" in result:
                flash(result["error"], "danger")

        flash(f"{ttype} recorded successfully.", "success")
        return redirect(url_for("transactions.transactions"))

    return render_template(
        "transactions.html",
        txns=txns,
        products=products,
        partners=partners,
        warehouses=warehouses
    )
