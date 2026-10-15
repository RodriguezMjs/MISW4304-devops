import click
from flask import Flask
from flask_jwt_extended import create_access_token
from flask_restful import Api
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .blacklist.resources import BlacklistListResource, BlacklistResource
from .extensions import db, jwt, ma
from .health.resources import HealthResource


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    if not app.config["SQLALCHEMY_DATABASE_URI"]:
        raise RuntimeError(
            "No hay base de datos configurada"
        )

    # ProxyFix toma la IP real del cliente desde X-Forwarded-For.
    if app.config["PROXY_COUNT"] > 0:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["PROXY_COUNT"])

    db.init_app(app)
    ma.init_app(app)
    jwt.init_app(app)

    api = Api(app)
    api.add_resource(HealthResource, "/ping")
    api.add_resource(BlacklistListResource, "/blacklists")
    api.add_resource(BlacklistResource, "/blacklists/<string:email>")

    @app.cli.command("generate-token")
    def generate_token():
        click.echo(create_access_token(identity="blacklist-client"))

    if app.config["CREATE_TABLES"]:
        with app.app_context():
            db.create_all()

    return app
