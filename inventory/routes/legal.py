from flask import Blueprint, render_template

bp = Blueprint("legal", __name__, url_prefix="/legal")

@bp.route("/terms")
def terms():
    return render_template("legal/terms.html")

@bp.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")

@bp.route("/cookies")
def cookies():
    return render_template("legal/cookies.html")

@bp.route("/contact")
def contact():
    return render_template("legal/contact.html")
