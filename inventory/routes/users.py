# inventory/routes/users.py

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from inventory.extensions import db
from inventory.models import User
from inventory.utils.translations import _
from inventory.utils.permissions import has_permission

bp = Blueprint("users", __name__)


def _get_owner_id():
    """
    Owner scoping logic used in your app:
    - Admin/Owner owns the org
    - other roles belong to owner via created_by_id
    - Developer is special (no owner scope)
    """
    if current_user.role == "Developer":
        return None
    if current_user.role == "Admin / Owner":
        return current_user.id
    return current_user.created_by_id


def _is_org_admin(user: User) -> bool:
    return (user.role or "").strip() == "Admin / Owner"


def _is_in_same_org(target: User, owner_id: int) -> bool:
    # Org members are: owner (id == owner_id) + any user created_by_id == owner_id
    return (target.id == owner_id) or (target.created_by_id == owner_id)


@bp.route("/users")
@login_required
def users():
    if not has_permission(current_user, "users:view"):
        flash(_("You do not have permission to manage users."), "danger")
        return redirect(url_for("main.index"))

    q = (request.args.get("q") or "").strip()
    r = (request.args.get("role") or "").strip()

    # Developer sees everything
    if current_user.role == "Developer":
        query = User.query
        if q:
            query = query.filter((User.username.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")))
        if r:
            query = query.filter(User.role == r)

        users_list = query.order_by(User.id.desc()).all()
        return render_template("users.html", users=users_list, q=q, f_role=r)

    # Non-developer: only allow Admin/Owner org view (by permission mapping)
    owner_id = _get_owner_id()
    if owner_id is None:
        flash(_("Invalid organization context."), "danger")
        return redirect(url_for("main.index"))

    query = User.query.filter((User.id == owner_id) | (User.created_by_id == owner_id))

    if q:
        query = query.filter((User.username.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%")))
    if r:
        query = query.filter(User.role == r)

    users_list = query.order_by(User.id.asc()).all()
    return render_template("users.html", users=users_list, q=q, f_role=r)


@bp.route("/users/add", methods=["POST"])
@login_required
def add_user():
    if not has_permission(current_user, "users:create"):
        abort(403)

    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "").strip()

    if role not in ["Admin / Owner", "Warehouse Manager", "Sales Agent"]:
        flash(_("Invalid role."), "danger")
        return redirect(url_for("users.users"))

    if not email or not username or not password:
        flash(_("Email, username, and password are required."), "danger")
        return redirect(url_for("users.users"))

    if len(password) < 8:
        flash(_("Password must be at least 8 characters long."), "danger")
        return redirect(url_for("users.users"))

    # Figure out org owner id
    # - Admin creates users in their org
    # - Developer creating users without org context is risky -> block
    if current_user.role == "Developer":
        flash(_("Developer must create users from an owner context."), "warning")
        return redirect(url_for("users.users"))

    owner_id = _get_owner_id()
    if not owner_id:
        flash(_("Invalid organization context."), "danger")
        return redirect(url_for("users.users"))

    existing = User.query.filter((User.username == username) | (User.email == email)).first()
    if existing:
        flash(_("Username or Email already exists."), "danger")
        return redirect(url_for("users.users"))

    hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")

    new_user = User(
        username=username,
        email=email,
        password=hashed_pw,
        role=role,
        created_by_id=owner_id,
    )

    db.session.add(new_user)
    db.session.commit()

    flash(_("User added successfully!"), "success")
    return redirect(url_for("users.users"))


@bp.route("/users/update_role/<int:id>", methods=["POST"])
@login_required
def update_role(id):
    if not has_permission(current_user, "users:update_role"):
        abort(403)

    target = User.query.get_or_404(id)

    # Never allow changing a Developer from non-Developer
    if target.role == "Developer" and current_user.role != "Developer":
        flash(_("You cannot change a Developer account."), "warning")
        return redirect(url_for("users.users"))

    # Developer can change roles except other Developers
    if current_user.role == "Developer":
        if target.role == "Developer":
            flash(_("You cannot change another Developer account."), "warning")
            return redirect(url_for("users.users"))

        new_role = (request.form.get("role") or "").strip()
        if new_role not in ["Admin / Owner", "Warehouse Manager", "Sales Agent"]:
            flash(_("Invalid role."), "danger")
            return redirect(url_for("users.users"))

        target.role = new_role
        db.session.commit()
        flash(_("Role updated."), "success")
        return redirect(url_for("users.users"))

    # Admin/Owner: org only + safety rules
    owner_id = _get_owner_id()
    if not owner_id:
        flash(_("Invalid organization context."), "danger")
        return redirect(url_for("users.users"))

    if not _is_in_same_org(target, owner_id):
        flash(_("You can only manage users in your organization."), "danger")
        return redirect(url_for("users.users"))

    new_role = (request.form.get("role") or "").strip()
    if new_role not in ["Admin / Owner", "Warehouse Manager", "Sales Agent"]:
        flash(_("Invalid role."), "danger")
        return redirect(url_for("users.users"))

    # Don't let admin downgrade themselves
    if target.id == current_user.id and new_role != "Admin / Owner":
        flash(_("You cannot change your own role."), "warning")
        return redirect(url_for("users.users"))

    # Prevent removing last org admin
    if _is_org_admin(target) and new_role != "Admin / Owner":
        admins_count = User.query.filter(
            ((User.id == owner_id) | (User.created_by_id == owner_id)) &
            (User.role == "Admin / Owner")
        ).count()

        if admins_count <= 1:
            flash(_("You cannot remove the last Admin/Owner for this organization."), "warning")
            return redirect(url_for("users.users"))

    target.role = new_role
    db.session.commit()

    flash(_("Role updated."), "success")
    return redirect(url_for("users.users"))


@bp.route("/users/delete/<int:id>", methods=["POST"])
@login_required
def delete_user(id):
    if not has_permission(current_user, "users:delete"):
        abort(403)

    target = User.query.get_or_404(id)

    # Never allow deleting yourself
    if target.id == current_user.id:
        flash(_("You cannot delete your own account."), "warning")
        return redirect(url_for("users.users"))

    # Developer rules
    if current_user.role == "Developer":
        if target.role == "Developer":
            flash(_("Developer accounts cannot delete each other."), "warning")
            return redirect(url_for("users.users"))

        db.session.delete(target)
        db.session.commit()
        flash(_("User deleted."), "success")
        return redirect(url_for("users.users"))

    # Admin/Owner rules (org only)
    owner_id = _get_owner_id()
    if not owner_id:
        flash(_("Invalid organization context."), "danger")
        return redirect(url_for("users.users"))

    if not _is_in_same_org(target, owner_id):
        flash(_("You can only delete users in your organization."), "danger")
        return redirect(url_for("users.users"))

    # Prevent deleting last org admin
    if _is_org_admin(target):
        admins_count = User.query.filter(
            ((User.id == owner_id) | (User.created_by_id == owner_id)) &
            (User.role == "Admin / Owner")
        ).count()

        if admins_count <= 1:
            flash(_("You cannot delete the last Admin/Owner for this organization."), "warning")
            return redirect(url_for("users.users"))

    db.session.delete(target)
    db.session.commit()
    flash(_("User deleted."), "success")
    return redirect(url_for("users.users"))
