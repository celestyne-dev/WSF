import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    ENV = "production"
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me-please-32-bytes-min")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_ERROR_MESSAGE_KEY = "message"

    # Media is stored on the Hostinger VPS filesystem, outside the app's
    # source tree, and served in production by Nginx directly from
    # MEDIA_ROOT at the MEDIA_URL path — Flask only handles the
    # upload/validate/process/authorize side (see app/services/media.py).
    MEDIA_ROOT = os.environ.get(
        "MEDIA_ROOT", os.path.join(basedir, "instance", "media")
    )
    MEDIA_URL = os.environ.get("MEDIA_URL", "/media/")
    MAX_UPLOAD_SIZE = int(os.environ.get("MAX_UPLOAD_SIZE", 10 * 1024 * 1024))  # 10MB
    ALLOWED_IMAGE_EXTENSIONS = set(
        os.environ.get("ALLOWED_IMAGE_EXTENSIONS", "jpg,jpeg,png,webp").split(",")
    )
    MAX_CONTENT_LENGTH = MAX_UPLOAD_SIZE
    # (max_width, max_height) per generated responsive WebP variant.
    MEDIA_VARIANTS = {
        "thumbnail": (200, 200),
        "card": (600, 400),
        "medium": (1000, 667),
        "large": (1600, 1067),
        "hero": (2400, 1350),
    }

    MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY")
    MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET")
    MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE")
    MPESA_PASSKEY = os.environ.get("MPESA_PASSKEY")

    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    API_URL = os.environ.get("API_URL", "http://localhost:5000/api/v1")

    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100


class DevelopmentConfig(Config):
    ENV = "development"
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://wsf:wsf_dev_pw@localhost:5432/wsf_dev"
    )


class TestingConfig(Config):
    ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://wsf:wsf_dev_pw@localhost:5432/wsf_test"
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)


class ProductionConfig(Config):
    ENV = "production"
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
