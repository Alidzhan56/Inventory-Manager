# inventory/routes/settings.py

import re
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash

from inventory.extensions import db
from inventory.models import AppConfig
from inventory.utils.translations import _
from inventory.utils.permissions import has_permission

bp = Blueprint("settings", __name__, url_prefix="/settings")


def _get_owner_id():
    if current_user.role == "Developer":
        return None
    if current_user.role == "Admin / Owner":
        return current_user.id
    return current_user.created_by_id


def _get_or_create_config(owner_id: int) -> AppConfig:
    config = AppConfig.query.filter_by(owner_id=owner_id).first()
    if not config:
        config = AppConfig(owner_id=owner_id, company_name="My Company")
        db.session.add(config)
        db.session.commit()
    return config


@bp.route("/", methods=["GET", "POST"])
@login_required
def settings():
    # This page is for org/company settings (admin/owner typically)
    if not has_permission(current_user, "settings:manage"):
        flash(_("Access denied"), "danger")
        return redirect(url_for("main.index"))

    owner_id = _get_owner_id()

    # Developer safety: settings belong to an org owner
    if owner_id is None:
        flash(_("Owner context required."), "warning")
        return redirect(url_for("main.index"))

    config = _get_or_create_config(owner_id)

    if request.method == "POST":
        company_name = (request.form.get("company_name") or "").strip()
        currency = (request.form.get("currency") or "BGN").strip().upper()
        default_language = (request.form.get("default_language") or "en").strip().lower()
        notifications_enabled = request.form.get("notifications_enabled") == "on"

        # Safe int parse
        try:
            low_stock_threshold = int(request.form.get("low_stock_threshold", 5))
        except (ValueError, TypeError):
            low_stock_threshold = 5

        if not company_name:
            flash(_("Company name is required"), "danger")
            return redirect(url_for("settings.settings"))

        allowed_currencies = {"BGN", "EUR", "USD"}
        if currency not in allowed_currencies:
            currency = "BGN"

        if default_language not in {"bg", "en"}:
            default_language = "en"

        if low_stock_threshold < 0:
            low_stock_threshold = 0

        config.company_name = company_name
        config.currency = currency
        config.default_language = default_language
        config.low_stock_threshold = low_stock_threshold
        config.notifications_enabled = notifications_enabled

        db.session.commit()

        flash(_("Company settings updated"), "success")
        return redirect(url_for("settings.settings"))

    return render_template("settings.html", config=config)


@bp.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    # This page is for EVERY user (including Developer)
    if request.method == "POST":
        current_pw = request.form.get("current_password") or ""
        new_pw = request.form.get("new_password") or ""
        confirm_pw = request.form.get("confirm_password") or ""

        # verify current password
        if not check_password_hash(current_user.password, current_pw):
            flash(_("Current password is incorrect."), "danger")
            return redirect(url_for("settings.change_password"))

        # validate new password (reuse your register rules)
        if new_pw != confirm_pw:
            flash(_("New password and confirmation do not match."), "danger")
            return redirect(url_for("settings.change_password"))

        if len(new_pw) < 8:
            flash(_("Password must be at least 8 characters."), "danger")
            return redirect(url_for("settings.change_password"))
        if not re.search(r"[A-Z]", new_pw):
            flash(_("Password must include at least one uppercase letter."), "danger")
            return redirect(url_for("settings.change_password"))
        if not re.search(r"[a-z]", new_pw):
            flash(_("Password must include at least one lowercase letter."), "danger")
            return redirect(url_for("settings.change_password"))
        if not re.search(r"\d", new_pw):
            flash(_("Password must include at least one number."), "danger")
            return redirect(url_for("settings.change_password"))
        if not re.search(r"[^a-zA-Z0-9]", new_pw):
            flash(_("Password must include at least one symbol."), "danger")
            return redirect(url_for("settings.change_password"))

        # update password + clear force flag
        current_user.password = generate_password_hash(new_pw, method="pbkdf2:sha256")
        current_user.password_changed_at = datetime.utcnow()
        current_user.force_password_change = False
        db.session.commit()

        flash(_("Password changed successfully."), "success")

        # If your settings page is admin-only, redirect safely:
        # - Admin/Owner can go to /settings
        # - Others can go to main dashboard
        if has_permission(current_user, "settings:manage") and current_user.role != "Developer":
            return redirect(url_for("settings.settings"))
        return redirect(url_for("main.index"))

    return render_template("change_password.html")
