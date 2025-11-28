from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from inventory.extensions import db
from inventory.models import Partner
from inventory.utils.translations import _

bp = Blueprint('partners', __name__)

@bp.route('/partners', methods=['GET', 'POST'])
@login_required
def partners():
    if current_user.role != 'Admin / Owner':
        flash(_("You do not have permission to access Partners."))
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        name = request.form.get('name')
        ptype = request.form.get('type')
        if not name or not ptype:
            flash(_('Please provide partner name and type.'))
            return redirect(url_for('partners.partners'))
        
        new_p = Partner(name=name, type=ptype, owner_id=current_user.id)
        db.session.add(new_p)
        db.session.commit()
        flash(_('%(ptype)s "%(name)s" added.') % {'ptype': ptype, 'name': name})
        return redirect(url_for('partners.partners'))
    
    partners = Partner.query.filter_by(owner_id=current_user.id).all()
    return render_template('partners.html', partners=partners)