from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from inventory.extensions import db
from inventory.models import Warehouse, Product
from inventory.utils.translations import _

bp = Blueprint('warehouses', __name__)

@bp.route('/warehouses')
@login_required
def warehouses():
    if current_user.role in ['Admin / Owner', 'Warehouse Manager']:
        warehouses = Warehouse.query.all()
        return render_template('warehouses.html', warehouses=warehouses)
    
    flash(_("You do not have permission to access Warehouses."))
    return redirect(url_for('main.index'))

@bp.route('/add_warehouse', methods=['POST'])
@login_required
def add_warehouse():
    if current_user.role not in ['Admin / Owner', 'Warehouse Manager']:
        flash(_("You do not have permission to add warehouses."))
        return redirect(url_for('main.index'))

    name = request.form.get('name')
    location = request.form.get('location')

    if not name:
        flash(_("Warehouse name is required."))
        return redirect(url_for('warehouses.warehouses'))

    owner_id = current_user.id if current_user.role == 'Admin / Owner' else None

    new_w = Warehouse(name=name, location=location, owner_id=owner_id)
    db.session.add(new_w)
    db.session.commit()
    flash(_("Warehouse added successfully."))
    return redirect(url_for('warehouses.warehouses'))

@bp.route('/delete_warehouse/<int:id>')
@login_required
def delete_warehouse(id):
    if current_user.role != 'Admin / Owner':
        flash(_("Only Admins can delete warehouses."))
        return redirect(url_for('warehouses.warehouses'))

    w = Warehouse.query.get_or_404(id)
    linked = Product.query.filter_by(warehouse_id=w.id).first()

    if linked:
        flash(_("Cannot delete a warehouse that contains products. Move or delete products first."))
        return redirect(url_for('warehouses.warehouses'))

    db.session.delete(w)
    db.session.commit()
    flash(_("Warehouse deleted successfully."))
    return redirect(url_for('warehouses.warehouses'))