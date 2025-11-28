import os
from flask import Flask, g
from config import config

from inventory.extensions import db, login_manager
from inventory.models import User, AppConfig
from inventory.utils.translations import set_language, _

def create_app(config_name='default'):
    """Application factory"""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config[config_name])
    
    # Create upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    
    # User loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Before request: set language and load company settings
    @app.before_request
    def before_request():
        set_language(app)
        
        config_obj = AppConfig.query.first()
        if not config_obj:
            config_obj = AppConfig(company_name=_("Inventory Manager"), notifications_enabled=True)
            db.session.add(config_obj)
            db.session.commit()
        g.app_config = config_obj
    
    # Make translation function available in templates
    app.jinja_env.globals.update(_=_)
    
    # Register blueprints
    from inventory.routes import auth, products, warehouses, partners, transactions, users, settings, main
    
    app.register_blueprint(auth.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(warehouses.bp)
    app.register_blueprint(partners.bp)
    app.register_blueprint(transactions.bp)
    app.register_blueprint(users.bp)
    app.register_blueprint(settings.bp)
    app.register_blueprint(main.bp)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app