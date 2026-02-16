import os
from flask import Flask, g, request, redirect, url_for, flash
from config import config

from inventory.extensions import db, login_manager, migrate
from inventory.models import User, AppConfig
from inventory.utils.translations import set_language, _


def create_app(config_name="default"):
    """
    App factory
    сглобява Flask приложението
    """
    app = Flask(__name__)

    # конфигурация
    app.config.from_object(config[config_name])

    # upload папка
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    @app.before_request
    def before_request():
        set_language(app)
        g.app_config = None

        from flask_login import current_user
        if not current_user.is_authenticated:
            return

        role = (current_user.role or "").strip()

        # force password change
        if role != "Developer" and current_user.created_by_id is not None and getattr(current_user, "force_password_change", False):
            endpoint = request.endpoint or ""
            allowed = {"settings.change_password", "auth.logout", "static"}
            if endpoint not in allowed:
                flash(_("⚠️ You must change your password to continue."), "warning")
                return redirect(url_for("settings.change_password"))

        if role == "Developer":
            return

        owner_id = current_user.id if role == "Admin / Owner" else current_user.created_by_id
        if not owner_id:
            return

        config_obj = AppConfig.query.filter_by(owner_id=owner_id).first()
        if not config_obj:
            config_obj = AppConfig(
                owner_id=owner_id,
                company_name=_("Inventory Manager"),
                notifications_enabled=True,
                low_stock_threshold=5,
                default_language="en",
                currency="EUR",
            )
            db.session.add(config_obj)
            db.session.commit()

        g.app_config = config_obj

   
    app.jinja_env.globals.update(_=_)

 
    from inventory.routes import (
        auth,
        products,
        warehouses,
        partners,
        transactions,
        users,
        settings,
        main,
        reports,
        legal,     
    )

    app.register_blueprint(auth.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(warehouses.bp)
    app.register_blueprint(partners.bp)
    app.register_blueprint(transactions.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(legal.bp)   

    # DB init + dev user
    with app.app_context():
        db.create_all()

        dev_email = os.environ.get("DEV_EMAIL")
        dev_username = os.environ.get("DEV_USERNAME", "developer")
        dev_password = os.environ.get("DEV_PASSWORD")

        if dev_email and dev_password:
            if not User.query.filter_by(email=dev_email).first():
                from werkzeug.security import generate_password_hash
                db.session.add(User(
                    username=dev_username,
                    email=dev_email,
                    password=generate_password_hash(dev_password),
                    role="Developer",
                    force_password_change=False,
                ))
                db.session.commit()

    return app
