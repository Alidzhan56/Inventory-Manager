# inventory/routes/products.py

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from sqlalchemy.orm import joinedload

from inventory.extensions import db
from inventory.models import Product, Warehouse, Stock, TransactionItem
from inventory.utils.translations import _
from inventory.utils.permissions import has_permission

bp = Blueprint("products", __name__)


def _get_owner_id():
    # определям към коя фирма е user-а
    # developer няма owner scope
    if current_user.role == "Developer":
        return None
    if current_user.role == "Admin / Owner":
        return current_user.id
    return current_user.created_by_id


def _get_or_create_stock(product_id: int, warehouse_id: int) -> Stock:
    stock = Stock.query.filter_by(product_id=product_id, warehouse_id=warehouse_id).first()
    if not stock:
        stock = Stock(product_id=product_id, warehouse_id=warehouse_id, quantity=0)
        db.session.add(stock)
        db.session.flush()
    return stock


@bp.route("/products")
@login_required
def products():
    if not has_permission(current_user, "products:view"):
        flash(_("You do not have permission to view products."), "danger")
        return redirect(url_for("main.index"))

    owner_id = _get_owner_id()

    query = (
        Product.query
        .options(joinedload(Product.stocks).joinedload(Stock.warehouse))
        .order_by(Product.name.asc())
    )

    if owner_id is not None:
        query = query.filter(Product.owner_id == owner_id)

    products_list = query.all()

    warehouses_q = Warehouse.query.order_by(Warehouse.name.asc())
    if owner_id is not None:
        warehouses_q = warehouses_q.filter(Warehouse.owner_id == owner_id)
    warehouses = warehouses_q.all()

    return render_template("products.html", products=products_list, warehouses=warehouses)


@bp.route("/add", methods=["POST"])
@login_required
def add_product():
    if not has_permission(current_user, "products:create"):
        flash(_("You do not have permission to add products."), "danger")
        return redirect(url_for("products.products"))

    owner_id = _get_owner_id()

    # не позволявам да се създава продукт без owner
    if owner_id is None:
        flash(_("Developer must add products from an owner context."), "warning")
        return redirect(url_for("products.products"))

    name = (request.form.get("name") or "").strip()
    sku = (request.form.get("sku") or "").strip()
    category = (request.form.get("category") or "").strip() or None
    warehouse_id = request.form.get("warehouse_id")
    image_file = request.files.get("image")

    try:
        quantity = int(request.form.get("quantity", 0))
    except (ValueError, TypeError):
        quantity = 0

    try:
        purchase_price = float(request.form.get("purchase_price", 0) or 0)
    except (ValueError, TypeError):
        purchase_price = 0.0

    try:
        sell_price = float(request.form.get("sell_price", 0) or 0)
    except (ValueError, TypeError):
        sell_price = 0.0

    if not name:
        flash(_("Please provide product name."), "danger")
        return redirect(url_for("products.products"))

    if not sku:
        flash(_("Please provide SKU."), "danger")
        return redirect(url_for("products.products"))

    if not warehouse_id:
        flash(_("Please select a warehouse."), "danger")
        return redirect(url_for("products.products"))

    try:
        warehouse_id = int(warehouse_id)
    except ValueError:
        flash(_("Invalid warehouse selected."), "danger")
        return redirect(url_for("products.products"))

    # проверявам дали warehouse-а е от същата фирма
    warehouse = Warehouse.query.filter_by(id=warehouse_id, owner_id=owner_id).first()
    if not warehouse:
        flash(_("Invalid warehouse selected."), "danger")
        return redirect(url_for("products.products"))

    # качване на снимка ако има
    image_relpath = None
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
        image_file.save(os.path.join(current_app.config["UPLOAD_FOLDER"], filename))
        image_relpath = f"uploads/{filename}"

    # SKU е уникално за даден owner
    existing = Product.query.filter_by(sku=sku, owner_id=owner_id).first()
    if existing:
        # ако продуктът вече съществува добавям само наличност
        stock = _get_or_create_stock(existing.id, warehouse_id)
        stock.quantity = (stock.quantity or 0) + max(quantity, 0)

        existing.default_purchase_price = purchase_price
        existing.default_sell_price = sell_price
        if category:
            existing.category = category
        if image_relpath:
            existing.image = image_relpath

        # временна синхронизация на legacy quantity
        existing.quantity = sum((s.quantity or 0) for s in existing.stocks)

        db.session.commit()
        flash(_("Product already exists. Stock was added to the selected warehouse."), "success")
        return redirect(url_for("products.products"))

    new_product = Product(
        name=name,
        sku=sku,
        category=category,
        default_purchase_price=purchase_price,
        default_sell_price=sell_price,
        image=image_relpath,
        owner_id=owner_id,
        warehouse_id=warehouse_id,  # legacy поле
    )
    db.session.add(new_product)
    db.session.flush()

    stock = _get_or_create_stock(new_product.id, warehouse_id)
    stock.quantity = (stock.quantity or 0) + max(quantity, 0)

    # временна синхронизация
    new_product.quantity = sum((s.quantity or 0) for s in new_product.stocks)

    db.session.commit()
    flash(_("Product '%(name)s' added successfully!") % {"name": name}, "success")
    return redirect(url_for("products.products"))


@bp.route("/edit/<int:id>", methods=["POST"])
@login_required
def edit_product(id):
    if not has_permission(current_user, "products:edit"):
        flash(_("You do not have permission to edit products."), "danger")
        return redirect(url_for("products.products"))

    owner_id = _get_owner_id()

    if owner_id is None:
        flash(_("Developer must edit products from an owner context."), "warning")
        return redirect(url_for("products.products"))

    product = Product.query.filter_by(id=id, owner_id=owner_id).first_or_404()

    product.name = (request.form.get("name") or product.name).strip()
    product.sku = (request.form.get("sku") or product.sku).strip()
    product.category = (request.form.get("category") or "").strip() or None

    try:
        product.default_purchase_price = float(
            request.form.get("purchase_price", product.default_purchase_price) or 0
        )
    except (ValueError, TypeError):
        pass

    try:
        product.default_sell_price = float(
            request.form.get("sell_price", product.default_sell_price) or 0
        )
    except (ValueError, TypeError):
        pass

    # проверка за конфликтен SKU
    conflict = Product.query.filter(
        Product.owner_id == owner_id,
        Product.sku == product.sku,
        Product.id != product.id,
    ).first()
    if conflict:
        flash(_("Another product with the same SKU already exists."), "warning")
        return redirect(url_for("products.products"))

    warehouse_id = request.form.get("warehouse_id")
    stock_qty = request.form.get("stock_qty")

    if warehouse_id:
        try:
            warehouse_id = int(warehouse_id)
        except ValueError:
            warehouse_id = None

    if warehouse_id:
        wh = Warehouse.query.filter_by(id=warehouse_id, owner_id=owner_id).first()
        if not wh:
            flash(_("Invalid warehouse selected."), "danger")
            return redirect(url_for("products.products"))

        if stock_qty is not None and stock_qty != "":
            try:
                stock_qty = int(stock_qty)
            except (ValueError, TypeError):
                stock_qty = None

            if stock_qty is not None and stock_qty >= 0:
                stock = _get_or_create_stock(product.id, warehouse_id)
                stock.quantity = stock_qty
                product.warehouse_id = warehouse_id  # legacy поле

    image_file = request.files.get("image")
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        os.makedirs(current_app.config["UPLOAD_FOLDER"], exist_ok=True)
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        image_file.save(filepath)
        product.image = f"uploads/{filename}"

    # временна синхронизация
    product.quantity = sum((s.quantity or 0) for s in product.stocks)

    db.session.commit()
    flash(_("Product '%(name)s' updated successfully!") % {"name": product.name}, "success")
    return redirect(url_for("products.products"))


@bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_product(id):
    if not has_permission(current_user, "products:delete"):
        flash(_("You do not have permission to delete products."), "danger")
        return redirect(url_for("products.products"))

    owner_id = _get_owner_id()

    if owner_id is None:
        flash(_("Developer must delete products from an owner context."), "warning")
        return redirect(url_for("products.products"))

    product = Product.query.filter_by(id=id, owner_id=owner_id).first_or_404()

    # не трия ако има наличност
    has_stock = any((s.quantity or 0) > 0 for s in product.stocks)
    if has_stock:
        flash(_("Cannot delete this product because it still has stock."), "warning")
        return redirect(url_for("products.products"))

    # не трия ако е използван в транзакции
    used_in_txn = TransactionItem.query.filter_by(product_id=product.id).first() is not None
    if used_in_txn:
        flash(_("Cannot delete this product because it is used in transactions."), "warning")
        return redirect(url_for("products.products"))

    db.session.delete(product)
    db.session.commit()

    flash(_("Product '%(name)s' deleted.") % {"name": product.name}, "success")
    return redirect(url_for("products.products"))
