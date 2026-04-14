import re
from datetime import datetime

import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

from inventory.extensions import db
from inventory.models import User, LoginEvent
from inventory.utils.security import hash_ip
from inventory.utils.translations import _

bp = Blueprint("auth", __name__)


def _client_ip() -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.remote_addr or ""


def _ip_to_country(ip: str) -> str:
    if not ip or ip in ("127.0.0.1", "::1"):
        return "Localhost"

    try:
        r = requests.get(
            f"https://ipapi.co/{ip}/json/",
            headers={"User-Agent": "WarePulse/1.0"},
            timeout=3,
        )

        if r.status_code != 200:
            return "Unknown"

        data = r.json()

        if isinstance(data, dict) and data.get("error"):
            return "Unknown"

        return (data.get("country_name") or "Unknown").strip() or "Unknown"

    except Exception:
        return "Unknown"


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""

        if not identifier or not password:
            flash(_("Please fill in all fields."), "danger")
            return redirect(url_for("auth.login"))

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier.lower())
        ).first()

        if not user:
            flash(_("No account found with that email or username."), "danger")
            return redirect(url_for("auth.login"))

        if not check_password_hash(user.password, password):
            flash(_("Incorrect password."), "danger")
            return redirect(url_for("auth.login"))

        is_company_user = user.created_by_id is not None
        is_developer = (user.role or "").strip() == "Developer"

        login_user(user)

        try:
            ip = _client_ip()
            ip_hash = hash_ip(ip)
            ua = (request.headers.get("User-Agent") or "")[:255]
            country = _ip_to_country(ip)

            user.login_count = (user.login_count or 0) + 1
            user.last_login_at = datetime.utcnow()
            user.last_login_ip = ip_hash
            user.last_login_country = country
            user.last_login_user_agent = ua

            db.session.add(
                LoginEvent(
                    user_id=user.id,
                    logged_in_at=datetime.utcnow(),
                    ip_address=ip_hash,
                    country=country,
                    user_agent=ua,
                    success=True,
                )
            )
            db.session.commit()

        except Exception:
            db.session.rollback()

        if is_company_user and (not is_developer) and getattr(user, "force_password_change", False):
            flash(_("You must change your password before continuing."), "warning")
            return redirect(url_for("settings.change_password"))

        if is_developer:
            return redirect(url_for("users.developer_dashboard"))

        return redirect(url_for("main.index"))

    return render_template("login.html")


@bp.route("/register_admin", methods=["GET", "POST"])
def register_admin():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not email or not username or not password or not confirm_password:
            flash(_("Please fill in all required fields."), "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash(_("Passwords do not match."), "danger")
            return render_template("register.html")

        email_pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
        if not re.match(email_pattern, email):
            flash(_("Please enter a valid email address."), "danger")
            return render_template("register.html")

        if len(password) < 8:
            flash(_("Password must be at least 8 characters."), "danger")
            return render_template("register.html")
        if not re.search(r"[A-Z]", password):
            flash(_("Password must include at least one uppercase letter."), "danger")
            return render_template("register.html")
        if not re.search(r"[a-z]", password):
            flash(_("Password must include at least one lowercase letter."), "danger")
            return render_template("register.html")
        if not re.search(r"\d", password):
            flash(_("Password must include at least one number."), "danger")
            return render_template("register.html")
        if not re.search(r"[^a-zA-Z0-9]", password):
            flash(_("Password must include at least one symbol."), "danger")
            return render_template("register.html")

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash(_("An account with this email or username already exists."), "danger")
            return render_template("register.html")

        hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")

        new_admin = User(
            username=username,
            email=email,
            password=hashed_pw,
            role="Admin / Owner",
            force_password_change=False,
            password_changed_at=datetime.utcnow(),
        )
        db.session.add(new_admin)
        db.session.commit()

        flash(_("Admin account created successfully."), "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash(_("You have been logged out."), "info")
    return redirect(url_for("main.landing"))