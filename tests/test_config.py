"""Configuración de conexión sin abrir conexiones a PostgreSQL."""

import pytest
from sqlalchemy import create_engine

from app.config import _database_uri


@pytest.fixture(autouse=True)
def database_env(monkeypatch):
    for name in (
        "DATABASE_URL", "RDS_HOSTNAME", "RDS_USERNAME", "RDS_PASSWORD",
        "RDS_PORT", "RDS_DB_NAME",
    ):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_database_url_usa_driver_instalado(monkeypatch, scheme):
    suffix = "user:password@localhost:5432/db?application_name=postgres://client"
    monkeypatch.setenv("DATABASE_URL", f"{scheme}://{suffix}")

    uri = _database_uri()

    assert uri == f"postgresql+psycopg2://{suffix}"
    # Crear el engine carga el driver, pero no abre conexiones.
    engine = create_engine(uri)
    try:
        assert engine.dialect.driver == "psycopg2"
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "uri",
    [
        "postgresql+psycopg2://user:password@localhost/db",
        "postgresql+psycopg://user:password@localhost/db",
        "sqlite:///:memory:",
    ],
)
def test_database_url_conserva_driver_explicito(monkeypatch, uri):
    monkeypatch.setenv("DATABASE_URL", uri)
    assert _database_uri() == uri


def test_database_url_tiene_prioridad_sobre_rds(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:password@localhost/local")
    monkeypatch.setenv("RDS_HOSTNAME", "rds.example.com")

    assert _database_uri() == "postgresql+psycopg2://user:password@localhost/local"


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({}, "postgresql+psycopg2://user:password@rds.example.com:5432/postgres"),
        (
            {"RDS_PORT": "5433", "RDS_DB_NAME": "blacklist"},
            "postgresql+psycopg2://user:password@rds.example.com:5433/blacklist",
        ),
    ],
    ids=["valores-predeterminados", "puerto-y-base-personalizados"],
)
def test_rds_usa_driver_instalado(monkeypatch, overrides, expected):
    for name, value in {
        "RDS_HOSTNAME": "rds.example.com",
        "RDS_USERNAME": "user",
        "RDS_PASSWORD": "password",
        **overrides,
    }.items():
        monkeypatch.setenv(name, value)

    assert _database_uri() == expected


def test_sin_configuracion_no_hay_uri():
    assert _database_uri() is None
