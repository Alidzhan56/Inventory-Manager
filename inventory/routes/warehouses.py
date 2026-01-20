# inventory/routes/warehouses.py

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import func

from inventory.extensions import db
from inventory.models import Warehouse, Stock, Transaction
from inventory.utils.translations import _
from inventory.utils.permissions import has_permission

bp = Blueprint("warehouses", __name__)


def _get_owner_id():
    """
    Everyone works inside an organization:
    - Admin/Owner owns the org
    - other roles belong to the owner via created_by_id
    - Developer is special (can see everything), but we still try to keep things safe
    """
    if current_user.role == "Developer":
        return None
    if current_user.role == "Admin / Owner":
        return current_user.id
    return current_user.created_by_id


@bp.route("/warehouses")
@login_required
def warehouses():
    if not has_permission(current_user, "warehouses:view"):
        flash(_("You do not have permission to view warehouses."), "danger")
        return redirect(url_for("main.index"))

    owner_id = _get_owner_id()

    q = Warehouse.query
    if owner_id is not None:
        q = q.filter(Warehouse.owner_id == owner_id)

    warehouses_list = q.order_by(Warehouse.name.asc()).all()

    # total units per warehouse (quick summary)
    stock_totals_q = (
        db.session.query(Stock.warehouse_id, func.coalesce(func.sum(Stock.quantity), 0))
        .join(Warehouse, Stock.warehouse_id == Warehouse.id)
    )
    if owner_id is not None:
        stock_totals_q = stock_totals_q.filter(Warehouse.owner_id == owner_id)

    stock_totals = dict(stock_totals_q.group_by(Stock.warehouse_id).all())

    # number of different products per warehouse (count stock rows with qty > 0)
    product_counts_q = (
        db.session.query(Stock.warehouse_id, func.count(Stock.id))
        .join(Warehouse, Stock.warehouse_id == Warehouse.id)
        .filter(Stock.quantity > 0)
    )
    if owner_id is not None:
        product_counts_q = product_counts_q.filter(Warehouse.owner_id == owner_id)

    product_counts = dict(product_counts_q.group_by(Stock.warehouse_id).all())

    return render_template(
        "warehouses.html",
        warehouses=warehouses_list,
        stock_totals=stock_totals,
        product_counts=product_counts,
    )


@bp.route("/warehouses/add", methods=["POST"])
@login_required
def add_warehouse():
    if not has_permission(current_user, "warehouses:create"):
        flash(_("You do not have permission to create warehouses."), "danger")
        return redirect(url_for("warehouses.warehouses"))

    owner_id = _get_owner_id()

    # Avoid creating "ownerless" warehouses (important for Developer context)
    if owner_id is None:
        flash(_("Developer must create warehouses from an owner context."), "warning")
        return redirect(url_for("warehouses.warehouses"))

    name = (request.form.get("name") or "").strip()
    location = (request.form.get("location") or "").strip() or None

    if not name:
        flash(_("Warehouse name is required."), "danger")
        return redirect(url_for("warehouses.warehouses"))

    # Avoid duplicates inside the same org
    existing = Warehouse.query.filter_by(owner_id=owner_id, name=name).first()
    if existing:
        flash(_("A warehouse with this name already exists."), "warning")
        return redirect(url_for("warehouses.warehouses"))

    new_w = Warehouse(name=name, location=location, owner_id=owner_id)
    db.session.add(new_w)
    db.session.commit()

    flash(_("Warehouse added successfully."), "success")
    return redirect(url_for("warehouses.warehouses"))


@bp.route("/warehouses/delete/<int:id>", methods=["POST"])
@login_required
def delete_warehouse(id):
    if not has_permission(current_user, "warehouses:delete"):
        flash(_("You do not have permission to delete warehouses."), "danger")
        return redirect(url_for("warehouses.warehouses"))

    owner_id = _get_owner_id()

    # Owner scope is important: we never delete warehouses outside the org
    q = Warehouse.query.filter(Warehouse.id == id)
    if owner_id is not None:
        q = q.filter(Warehouse.owner_id == owner_id)

    w = q.first_or_404()

    # If there is stock, deleting would be a disaster.
    has_stock = (
        Stock.query
        .filter(Stock.warehouse_id == w.id)
        .filter(Stock.quantity > 0)
        .first()
        is not None
    )
    if has_stock:
        flash(_("Cannot delete a warehouse that has stock. Move or sell the items first."), "warning")
        return redirect(url_for("warehouses.warehouses"))

    # If there are transactions, deleting breaks history and reports.
    has_txn = Transaction.query.filter_by(warehouse_id=w.id).first() is not None
    if has_txn:
        flash(_("Cannot delete a warehouse that has transactions. Keep it for history."), "warning")
        return redirect(url_for("warehouses.warehouses"))

    db.session.delete(w)
    db.session.commit()

    flash(_("Warehouse deleted successfully."), "success")
    return redirect(url_for("warehouses.warehouses"))
