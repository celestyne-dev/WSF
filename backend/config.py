import os
from datetime import timedelta

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "postgresql://localhost/wsf_dev"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-jwt-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=30)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

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

    MPESA_CONSUMER_KEY = os.environ.get("MPESA_CONSUMER_KEY")
    MPESA_CONSUMER_SECRET = os.environ.get("MPESA_CONSUMER_SECRET")
    MPESA_SHORTCODE = os.environ.get("MPESA_SHORTCODE")
    MPESA_PASSKEY = os.environ.get("MPESA_PASSKEY")

    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    API_URL = os.environ.get("API_URL", "http://localhost:5000/api/v1")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_by_name = {"development": DevelopmentConfig, "production": ProductionConfig}
