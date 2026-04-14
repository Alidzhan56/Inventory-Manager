import os

class Config:
    """базови настройки за проекта"""
    SECRET_KEY = os.environ.get("SECRET_KEY") or "supersecretkey"  # в production задължително през env
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///inventory.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # тук качва снимки на продукти и тн
    UPLOAD_FOLDER = "inventory/static/uploads"

    # езиците които поддържа в UI
    LANGUAGES = ["bg", "en"]
    DEFAULT_LANG = "en"

    MAIL_SERVER = "smtp-relay.brevo.com"
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    MAIL_USERNAME = os.getenv("BREVO_SMTP_LOGIN")
    MAIL_PASSWORD = os.getenv("BREVO_SMTP_KEY")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")
    SECURITY_PASSWORD_SALT = "warepulse-email-confirm-2026"

    IP_HASH_SECRET = os.environ.get("IP_HASH_SECRET") or "warepulse-ip-secret-2026"


class DevelopmentConfig(Config):
    """настройки за локална разработка"""
    DEBUG = True


class ProductionConfig(Config):
    """настройки за хостинг"""
    DEBUG = False


# удобна карта за избор на конфигурация
config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}