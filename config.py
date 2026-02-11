import os

class Config:
    """базови настройки за проекта"""
    SECRET_KEY = os.environ.get("SECRET_KEY") or "supersecretkey"  # в production задължително през env
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "sqlite:///inventory.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # тук качваш снимки на продукти и тн
    UPLOAD_FOLDER = "inventory/static/uploads"

    # езиците които поддържаш в UI
    LANGUAGES = ["bg", "en"]
    DEFAULT_LANG = "en"


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
