from marshmallow import fields, validate

from ..extensions import ma
from .models import Blacklist


class BlacklistCreateSchema(ma.Schema):
    """Valida el cuerpo del POST /blacklists."""

    email = fields.Email(required=True)
    app_uuid = fields.UUID(required=True)
    blocked_reason = fields.String(
        load_default=None, allow_none=True, validate=validate.Length(max=255)
    )


class BlacklistSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Blacklist


blacklist_create_schema = BlacklistCreateSchema()
blacklist_schema = BlacklistSchema()
