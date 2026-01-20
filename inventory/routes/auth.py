import re
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

from inventory.extensions import db
from inventory.models import User
from inventory.utils.translations import _

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()  # email OR username
        password = request.form.get("password") or ""

        if not identifier or not password:
            flash(_("Please fill in all fields."), "danger")
            return redirect(url_for("auth.login"))

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user:
            flash(_("No account found with that email or username."), "danger")
            return redirect(url_for("auth.login"))

        if not check_password_hash(user.password, password):
            flash(_("Incorrect password."), "danger")
            return redirect(url_for("auth.login"))

        login_user(user)

        # Redirect based on role
        if user.role == "Developer":
            return redirect(url_for("users.users"))  # dev view of all users
        return redirect(url_for("main.index"))

    return render_template("login.html")


@bp.route("/register_admin", methods=["GET", "POST"])
def register_admin():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        if not email or not username or not password or not confirm_password:
            flash(_("Please fill in all required fields."), "danger")
            return render_template("register.html")

        if password != confirm_password:
            flash(_("Passwords do not match."), "danger")
            return render_template("register.html")

        # password strength checks
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

        # unique email/username
        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash(_("An account with this email or username already exists."), "danger")
            return render_template("register.html")

        hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")
        new_admin = User(
            username=username,
            email=email,
            password=hashed_pw,
            role="Admin / Owner",
        )
        db.session.add(new_admin)
        db.session.commit()

        flash(_("Admin account created! Please log in."), "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash(_("You have been logged out."), "info")
    return redirect(url_for("main.landing"))
