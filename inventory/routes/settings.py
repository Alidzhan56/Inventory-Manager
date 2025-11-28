import os
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from inventory.extensions import db
from inventory.models import AppConfig
from inventory.utils.decorators import roles_required
from inventory.utils.translations import _

bp = Blueprint('settings', __name__)

@bp.route('/settings', methods=['GET', 'POST'])
@login_required
@roles_required('Admin / Owner')
def settings():
    config = AppConfig.query.first()
    if not config:
        config = AppConfig(company_name=_("My Company"))
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        config.company_name = request.form.get('company_name')
        config.notifications_enabled = bool(request.form.get('notifications_enabled'))

        logo = request.files.get('logo')
        if logo and logo.filename:
            filename = f"company_logo_{config.id}.png"
            logo_path = f"static/uploads/{filename}"
            os.makedirs(os.path.dirname(logo_path), exist_ok=True)
            logo.save(logo_path)
            config.logo_path = logo_path

        db.session.commit()
        flash(_("Settings updated successfully!"), "success")
        return redirect(url_for('settings.settings'))

    return render_template('settings.html', config=config)