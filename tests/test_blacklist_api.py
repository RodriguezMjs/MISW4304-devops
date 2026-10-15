"""Pruebas de la capa HTTP. La capa de servicio se mockea: no se toca la base."""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from app.blacklist.models import Blacklist
from app.blacklist.services import EmailAlreadyBlacklisted
from app.config import TestConfig

SERVICES = "app.blacklist.resources"


@pytest.fixture
def app():
    return create_app(TestConfig)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth(app):
    with app.app_context():
        token = create_access_token(identity="test")
    return {"Authorization": f"Bearer {token}"}


def _payload(**overrides):
    body = {
        "email": "cliente@example.com",
        "app_uuid": str(uuid.uuid4()),
        "blocked_reason": "Spam",
    }
    body.update(overrides)
    return body


def _entry(**overrides):
    fields = {
        "id": 1,
        "email": "cliente@example.com",
        "app_uuid": str(uuid.uuid4()),
        "blocked_reason": "Spam",
        "ip_address": "10.1.2.3",
        "created_at": datetime(2026, 10, 14, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return Blacklist(**fields)


def test_ping_no_requiere_token(client):
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


@patch(f"{SERVICES}.add_to_blacklist")
def test_post_agrega_email_con_ip_de_origen(add_mock, client, auth):
    body = _payload()
    add_mock.return_value = _entry(app_uuid=body["app_uuid"])

    resp = client.post(
        "/blacklists",
        json=body,
        headers=auth,
        environ_base={"REMOTE_ADDR": "10.1.2.3"},
    )

    assert resp.status_code == 201
    assert resp.get_json()["blacklist"]["email"] == "cliente@example.com"
    add_mock.assert_called_once_with(
        email="cliente@example.com",
        app_uuid=uuid.UUID(body["app_uuid"]),
        blocked_reason="Spam",
        ip_address="10.1.2.3",
    )


@patch(f"{SERVICES}.add_to_blacklist")
def test_post_sin_motivo_es_valido(add_mock, client, auth):
    add_mock.return_value = _entry(blocked_reason=None)
    body = _payload()
    del body["blocked_reason"]

    assert client.post("/blacklists", json=body, headers=auth).status_code == 201
    assert add_mock.call_args.kwargs["blocked_reason"] is None


@patch(f"{SERVICES}.add_to_blacklist")
def test_post_duplicado_retorna_409(add_mock, client, auth):
    add_mock.side_effect = EmailAlreadyBlacklisted("cliente@example.com")
    resp = client.post("/blacklists", json=_payload(), headers=auth)
    assert resp.status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        _payload(email="no-es-un-email"),
        _payload(app_uuid="no-es-uuid"),
        _payload(blocked_reason="x" * 256),
        {"email": "a@b.com"},
        {},
    ],
)
@patch(f"{SERVICES}.add_to_blacklist")
def test_post_datos_invalidos_retorna_400(add_mock, client, auth, body):
    resp = client.post("/blacklists", json=body, headers=auth)
    assert resp.status_code == 400
    assert "errors" in resp.get_json()
    add_mock.assert_not_called()


@patch(f"{SERVICES}.find_blacklisted")
def test_get_email_en_lista_negra(find_mock, client, auth):
    find_mock.return_value = _entry()
    resp = client.get("/blacklists/CLIENTE@example.com", headers=auth)

    assert resp.status_code == 200
    data = resp.get_json()
    assert data["is_blacklisted"] is True
    assert data["blocked_reason"] == "Spam"
    find_mock.assert_called_once_with("CLIENTE@example.com")


@patch(f"{SERVICES}.find_blacklisted", return_value=None)
def test_get_email_no_en_lista_negra(find_mock, client, auth):
    resp = client.get("/blacklists/otro@example.com", headers=auth)
    assert resp.status_code == 200
    assert resp.get_json()["is_blacklisted"] is False
    assert resp.get_json()["blocked_reason"] is None


@pytest.mark.parametrize(
    "method,url",
    [("post", "/blacklists"), ("get", "/blacklists/cliente@example.com")],
)
def test_endpoints_requieren_token(client, method, url):
    resp = getattr(client, method)(url, json=_payload())
    assert resp.status_code == 401


def test_token_invalido_es_rechazado(client):
    resp = client.get(
        "/blacklists/cliente@example.com",
        headers={"Authorization": "Bearer token-falso"},
    )
    assert resp.status_code in (401, 422)
