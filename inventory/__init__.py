import os
from flask import Flask, g
from config import config

from inventory.extensions import db, login_manager
from inventory.models import User, AppConfig
from inventory.utils.translations import set_language, _


def create_app(config_name="default"):
    """Application factory"""
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config[config_name])

    # Create upload folder
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Before request: language + org config
    @app.before_request
    def before_request():
        set_language(app)

        # default: nothing loaded
        g.app_config = None

        from flask_login import current_user
        if not current_user.is_authenticated:
            return

        # Developer should not load org config / regular site context
        if (current_user.role or "").strip() == "Developer":
            return

        # find the organization owner
        owner_id = current_user.id if current_user.role == "Admin / Owner" else current_user.created_by_id
        if not owner_id:
            return

        # load config for that owner, or create it if missing
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

    # Make translation function available in templates
    app.jinja_env.globals.update(_=_)

    # Register blueprints
    from inventory.routes import auth, products, warehouses, partners, transactions, users, settings, main, reports

    app.register_blueprint(auth.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(warehouses.bp)
    app.register_blueprint(partners.bp)
    app.register_blueprint(transactions.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(reports.bp)

    # Create database tables + optional dev user
    with app.app_context():
        db.create_all()

        # Optional: auto-create Developer user from env
        dev_email = os.environ.get("DEV_EMAIL")
        dev_username = os.environ.get("DEV_USERNAME", "developer")
        dev_password = os.environ.get("DEV_PASSWORD")

        if dev_email and dev_password:
            existing = User.query.filter_by(email=dev_email).first()
            if not existing:
                from werkzeug.security import generate_password_hash
                dev_user = User(
                    username=dev_username,
                    email=dev_email,
                    password=generate_password_hash(dev_password, method="pbkdf2:sha256"),
                    role="Developer",
                )
                db.session.add(dev_user)
                db.session.commit()

    return app
