from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from inventory.extensions import db
from inventory.models import Transaction, Product, Partner, Warehouse
from inventory.utils.translations import _

bp = Blueprint('transactions', __name__)

@bp.route('/transactions', methods=['GET', 'POST'])
@login_required
def transactions():
    owner_id = current_user.id if current_user.role == 'Admin / Owner' else current_user.created_by_id
    products = Product.query.filter_by(owner_id=owner_id).all()
    partners = Partner.query.filter_by(owner_id=owner_id).all()
    warehouses = Warehouse.query.filter_by(owner_id=owner_id).all()

    if request.method == 'POST':
        ttype = request.form.get('type')
        product_id = request.form.get('product_id')
        partner_id = request.form.get('partner_id')
        warehouse_id = request.form.get('warehouse_id')
        quantity = int(request.form.get('quantity', 0))

        product = Product.query.get(product_id)
        if not product:
            flash(_('Product not found.'), 'danger')
            return redirect(url_for('transactions.transactions'))

        if ttype == 'Sale':
            if quantity > product.quantity:
                flash(_('Not enough stock for sale.'), 'danger')
                return redirect(url_for('transactions.transactions'))
            product.quantity -= quantity
        elif ttype == 'Purchase':
            product.quantity += quantity

        total_price = (product.price or 0) * quantity

        txn = Transaction(
            type=ttype,
            product_id=product.id,
            partner_id=partner_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            total_price=total_price,
            user_id=current_user.id
        )
        db.session.add(txn)
        db.session.commit()
        flash(_('%(ttype)s recorded successfully.') % {'ttype': ttype}, 'success')
        return redirect(url_for('transactions.transactions'))

    # For GET: show transactions
    txns = (
        Transaction.query
        .join(Product)
        .filter(Product.owner_id == owner_id)
        .order_by(Transaction.date.desc())
        .all()
    )

    return render_template('transactions.html', txns=txns, products=products, partners=partners, warehouses=warehouses)