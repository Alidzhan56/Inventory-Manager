import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from inventory.extensions import db
from inventory.models import Product, Warehouse, Sale
from inventory.utils.decorators import roles_required
from inventory.utils.translations import _

bp = Blueprint('products', __name__)

@bp.route('/products')
@login_required
def products():
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id

    # Get products visible to this user
    if current_user.role in ['Admin / Owner', 'Warehouse Manager']:
        products = Product.query.filter_by(owner_id=owner_id).all()
    else:
        products = Product.query.filter_by(owner_id=owner_id).all()

    warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()

    return render_template('products.html', products=products, warehouses=warehouses)

@bp.route('/add', methods=['POST'])
@login_required
def add_product():
    redirect_page = 'products.products'

    name = request.form.get('name')
    sku = request.form.get('sku')
    category = request.form.get('category')
    warehouse_id = request.form.get('warehouse_id')
    image_file = request.files.get('image')

    # Safe conversions
    try:
        quantity = int(request.form.get('quantity', 0))
    except ValueError:
        quantity = 0
    try:
        price = float(request.form.get('price', 0))
    except ValueError:
        price = 0.0

    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id

    if not warehouse_id:
        flash(_("Please select a warehouse."))
        return redirect(url_for(redirect_page))

    # Ensure warehouse_id is int
    try:
        warehouse_id = int(warehouse_id)
    except ValueError:
        flash(_("Invalid warehouse selected."))
        return redirect(url_for(redirect_page))

    if not sku:
        flash(_("Please provide SKU."))
        return redirect(url_for(redirect_page))

    # Check if SKU exists
    existing = Product.query.filter_by(sku=sku, owner_id=owner_id, warehouse_id=warehouse_id).first()

    if existing:
        warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()
        products = Product.query.filter_by(owner_id=owner_id).all()
        new_product_data = {
            "name": name,
            "quantity": quantity,
            "price": price,
            "sku": sku,
            "category": category,
            "warehouse_id": warehouse_id,
            "image_file": image_file.filename if image_file else None
        }
        return render_template(
            'products.html',
            show_merge_modal=True,
            existing_product=existing,
            new_product_data=new_product_data,
            warehouses=warehouses,
            products=products
        )

    # Handle image
    image_relpath = None
    if image_file and image_file.filename != '':
        filename = secure_filename(image_file.filename)
        image_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        image_relpath = f"uploads/{filename}"

    # Create new
    new_product = Product(
        name=name,
        quantity=quantity,
        price=price,
        sku=sku,
        category=category,
        image=image_relpath,
        owner_id=owner_id,
        warehouse_id=warehouse_id
    )

    db.session.add(new_product)
    db.session.commit()
    flash(_("Product '%(name)s' added successfully!") % {'name': name})
    return redirect(url_for(redirect_page))

@bp.route('/merge_product', methods=['POST'])
@login_required
def merge_product():
    existing_id = request.form.get('existing_id')
    add_qty = request.form.get('add_qty', type=int)

    existing = Product.query.get(existing_id)
    if not existing:
        flash(_("Product not found."), "danger")
        return redirect(url_for('products.products'))

    existing.quantity += add_qty
    db.session.commit()

    flash(_("Quantity successfully merged for %(name)s (new total: %(qty)d).") % 
          {'name': existing.name, 'qty': existing.quantity}, "success")

    return redirect(url_for('products.products'))

@bp.route('/sell/<int:id>', methods=['POST'])
@login_required
def sell_product(id):
    product = Product.query.get_or_404(id)
    try:
        quantity_to_sell = int(request.form.get('quantity', 0))
    except ValueError:
        quantity_to_sell = 0

    if quantity_to_sell <= 0:
        flash(_("Invalid quantity."))
        return redirect(url_for('main.index'))

    if quantity_to_sell > product.quantity:
        flash(_("Not enough stock to sell that quantity."))
        return redirect(url_for('main.index'))

    # Decrease product stock
    product.quantity -= quantity_to_sell

    # Record sale
    total_price = quantity_to_sell * (product.price or 0)
    sale = Sale(
        product_id=product.id,
        quantity=quantity_to_sell,
        total_price=total_price,
        warehouse_id=product.warehouse_id
    )
    db.session.add(sale)
    db.session.commit()

    flash(_("Sold %(qty)s of '%(name)s'. Remaining stock: %(rem)s.") % 
          {'qty': quantity_to_sell, 'name': product.name, 'rem': product.quantity})
    return redirect(url_for('main.index'))

@bp.route('/edit/<int:id>', methods=['POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)

    # Ensure current user can edit this product
    owner_allowed = (
        (current_user.role == 'Admin / Owner' and product.owner_id == current_user.id) or
        (current_user.role != 'Admin / Owner' and product.owner_id == current_user.created_by_id)
    )
    if not owner_allowed:
        abort(403)

    # Get form fields safely
    product.name = request.form.get('name', product.name)
    product.category = request.form.get('category', product.category)
    warehouse_id = request.form.get('warehouse_id')

    try:
        product.quantity = int(request.form.get('quantity', product.quantity))
    except (ValueError, TypeError):
        pass

    try:
        product.price = float(request.form.get('price', product.price))
    except (ValueError, TypeError):
        pass

    new_sku = request.form.get('sku', product.sku)
    if new_sku != product.sku:
        conflict = Product.query.filter_by(
            sku=new_sku,
            owner_id=product.owner_id,
            warehouse_id=warehouse_id
        ).first()
        if conflict and conflict.id != product.id:
            flash(_("Another product with the same SKU exists in this warehouse."), 'warning')
            return redirect(url_for('products.products'))
        product.sku = new_sku

    try:
        product.warehouse_id = int(warehouse_id) if warehouse_id else None
    except (ValueError, TypeError):
        pass

    # Handle image upload
    image_file = request.files.get('image')
    if image_file and image_file.filename:
        filename = secure_filename(image_file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        image_file.save(filepath)
        product.image = f"uploads/{filename}"

    db.session.commit()

    flash(_("Product '%(name)s' updated successfully!") % {'name': product.name}, 'success')
    return redirect(url_for('products.products'))

@bp.route('/delete/<int:id>')
@login_required
@roles_required('Admin / Owner', 'Warehouse Manager')
def delete_product(id):
    product = Product.query.get_or_404(id)

    owner_allowed = (current_user.role == 'Admin / Owner' and product.owner_id == current_user.id) or \
                    (current_user.role != 'Admin / Owner' and product.owner_id == current_user.created_by_id)
    if not owner_allowed:
        abort(403)

    db.session.delete(product)
    db.session.commit()
    flash(_("Product '%(name)s' deleted.") % {'name': product.name})
    return redirect(url_for('main.index'))