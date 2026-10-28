"""Pruebas de la lógica de negocio. La sesión y las consultas de SQLAlchemy se mockean."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.blacklist.models import Blacklist
from app.blacklist.services import (
    EmailAlreadyBlacklisted,
    add_to_blacklist,
    find_blacklisted,
)


@pytest.fixture
def query(app_context):
    """Reemplaza Blacklist.query; query.filter_by(...).first() retorna None por defecto."""
    mock = MagicMock()
    mock.filter_by.return_value.first.return_value = None
    with patch.object(Blacklist, "query", mock):
        yield mock


@pytest.fixture
def session():
    with patch("app.blacklist.services.db") as db_mock:
        yield db_mock.session


def test_add_normaliza_el_email_y_guarda(query, session):
    app_uuid = uuid.uuid4()
    entry = add_to_blacklist("  Spam@Example.COM ", app_uuid, "Spam", "1.1.1.1")

    query.filter_by.assert_called_once_with(email="spam@example.com")
    assert entry.email == "spam@example.com"
    assert entry.app_uuid == str(app_uuid)
    assert entry.blocked_reason == "Spam"
    assert entry.ip_address == "1.1.1.1"
    session.add.assert_called_once_with(entry)
    session.commit.assert_called_once()


def test_add_duplicado_lanza_excepcion_y_no_guarda(query, session):
    query.filter_by.return_value.first.return_value = Blacklist(email="spam@example.com")

    with pytest.raises(EmailAlreadyBlacklisted):
        add_to_blacklist("SPAM@example.com", uuid.uuid4(), None, "2.2.2.2")

    session.add.assert_not_called()
    session.commit.assert_not_called()


def test_find_blacklisted_normaliza_el_email(query):
    existing = Blacklist(email="spam@example.com", blocked_reason="Spam")
    query.filter_by.return_value.first.return_value = existing

    assert find_blacklisted(" Spam@Example.com") is existing
    query.filter_by.assert_called_once_with(email="spam@example.com")


def test_find_blacklisted_retorna_none_si_no_existe(query):
    assert find_blacklisted("otro@example.com") is None
