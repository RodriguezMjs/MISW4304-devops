"""Fixtures compartidas para pruebas aisladas, sin conexión a una base de datos."""

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.config import TestConfig


@pytest.fixture
def app():
    """Crea una aplicación independiente en modo test, sin crear tablas."""
    return create_app(TestConfig)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def token(app):
    """Genera un JWT con el secreto exclusivo de pruebas."""
    with app.app_context():
        return create_access_token(identity="test")


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app_context(app):
    """Proporciona el contexto que requieren las consultas de Flask-SQLAlchemy."""
    with app.app_context():
        yield
