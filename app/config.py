import os


def _database_uri():
    """DATABASE_URL tiene prioridad; si no, usa las variables RDS_* que
    Beanstalk inyecta cuando la base está asociada al ambiente."""
    url = os.getenv("DATABASE_URL")
    if url:
        # SQLAlchemy 2 no acepta el esquema "postgres://"
        return url.replace("postgres://", "postgresql://", 1)

    if os.getenv("RDS_HOSTNAME"):
        return "postgresql://{user}:{password}@{host}:{port}/{name}".format(
            user=os.environ["RDS_USERNAME"],
            password=os.environ["RDS_PASSWORD"],
            host=os.environ["RDS_HOSTNAME"],
            port=os.getenv("RDS_PORT", "5432"),
            name=os.getenv("RDS_DB_NAME", "postgres"),
        )

    return None


class Config:
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    # Crea las tablas al arrancar
    CREATE_TABLES = True

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
    JWT_ACCESS_TOKEN_EXPIRES = False

    PROPAGATE_EXCEPTIONS = True

    PROXY_COUNT = int(os.getenv("PROXY_COUNT", "2"))


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "postgresql://test:test@localhost:5432/test"
    CREATE_TABLES = False
    JWT_SECRET_KEY = "test-secret-with-at-least-32-bytes!!"
    PROXY_COUNT = 0
