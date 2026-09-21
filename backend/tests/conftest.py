import pytest

from app import create_app
from app.extensions import db as _db
from app.services.geography import seed_countries
from app.services.rbac import seed_roles_and_permissions


@pytest.fixture()
def app():
    application = create_app("testing")
    with application.app_context():
        _db.create_all()
        seed_roles_and_permissions()
        seed_countries()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}
