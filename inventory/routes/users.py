from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from inventory.extensions import db
from inventory.models import User
from inventory.utils.translations import _

bp = Blueprint('users', __name__)

@bp.route('/users')
@login_required
def users():
    # Developer: can see all users
    if current_user.role == "Developer":
        users_list = User.query.all()
        return render_template('users.html', users=users_list)

    # Admin/Owner: can see only users they created
    if current_user.role == "Admin / Owner":
        users_list = User.query.filter_by(created_by_id=current_user.id).all()
        return render_template('users.html', users=users_list)

@bp.route('/add_user', methods=['POST'])
@login_required
def add_user():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    role = request.form.get('role')

    # Validate fields
    if not email or not username or not password:
        flash("Email, username, and password are required.", "danger")
        return redirect(url_for('users.users'))

    # Validate password length
    if len(password) < 8:
        flash("Password must be at least 8 characters long.", "danger")
        return redirect(url_for('users.users'))

    # Check if username or email already exists
    existing_user = User.query.filter(
        (User.username == username) | (User.email == email)
    ).first()

    if existing_user:
        flash("Username or Email already exists.", "danger")
        return redirect(url_for('users.users'))

    # Secure password hashing
    hashed_pw = generate_password_hash(password, method='pbkdf2:sha256')

    new_user = User(
        username=username,
        email=email,
        password=hashed_pw,
        role=role,
        created_by_id=current_user.id
    )

    db.session.add(new_user)
    db.session.commit()

    flash("User added successfully!", "success")
    return redirect(url_for('users.users'))

@bp.route('/delete_user/<int:id>', methods=['POST'])
@login_required
def delete_user(id):
    user = User.query.get_or_404(id)

    # Developer can delete anyone EXCEPT other developers
    if current_user.role == "Developer":
        if user.role == "Developer":
            flash("Developer accounts cannot delete each other.")
            return redirect(request.referrer)
        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.username} deleted.")
        return redirect(request.referrer)

    # Admin can delete only users they created
    if current_user.role == "Admin / Owner":
        if user.created_by_id != current_user.id:
            flash("You can only delete users you created.")
            return redirect(url_for('users.users'))

        if user.id == current_user.id:
            flash("You cannot delete your own account.")
            return redirect(url_for('users.users'))

        db.session.delete(user)
        db.session.commit()
        flash(f"User {user.username} deleted.")
        return redirect(url_for('users.users'))

    abort(403)

# Developer Dashboard
@bp.route('/developer')
@login_required
def developer_dashboard():
    if current_user.role != "Developer":
        abort(403)

    users_list = User.query.all()
    return render_template('developer_dashboard.html', users=users_list)

@bp.route('/delete_user_dev/<int:id>', methods=['POST'])
@login_required
def delete_user_dev(id):
    if current_user.role != "Developer":
        abort(403)

    user = User.query.get_or_404(id)
    if user.id == current_user.id:
        flash(_("You cannot delete your own account!"))
        return redirect(url_for('users.developer_dashboard'))

    db.session.delete(user)
    db.session.commit()
    flash(_('User %(username)s deleted.') % {'username': user.username})
    return redirect(url_for('users.developer_dashboard'))

# Developer specific routes
@bp.route('/developer/user/create', methods=['GET', 'POST'])
@login_required
def create_user_dev():
    if request.method == 'POST':
        flash('User created successfully!', 'success')
        return redirect(url_for('users.developer_dashboard'))
    return render_template('create_user_form.html')

@bp.route('/developer/logs')
@login_required
def view_logs_dev():
    logs = ["Log line 1", "Log line 2", "Log line 3"]
    return render_template('system_logs.html', logs=logs)

@bp.route('/developer/settings')
@login_required
def app_settings_dev():
    settings = {'app_name': 'Inventory Manager', 'debug_mode': False}
    return render_template('app_settings.html', settings=settings)