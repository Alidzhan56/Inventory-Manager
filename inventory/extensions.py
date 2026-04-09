from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()


login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
