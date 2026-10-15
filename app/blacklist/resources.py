from flask import request
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from marshmallow import ValidationError

from .schemas import blacklist_create_schema, blacklist_schema
from .services import EmailAlreadyBlacklisted, add_to_blacklist, find_blacklisted


class BlacklistListResource(Resource):
    @jwt_required()
    def post(self):
        try:
            data = blacklist_create_schema.load(request.get_json(silent=True) or {})
        except ValidationError as err:
            return {"msg": "Datos inválidos", "errors": err.messages}, 400

        try:
            entry = add_to_blacklist(
                email=data["email"],
                app_uuid=data["app_uuid"],
                blocked_reason=data["blocked_reason"],
                ip_address=request.remote_addr or "unknown",
            )
        except EmailAlreadyBlacklisted as err:
            return {"msg": str(err)}, 409

        return {
            "msg": f"El email {entry.email} fue agregado a la lista negra global",
            "blacklist": blacklist_schema.dump(entry),
        }, 201


class BlacklistResource(Resource):
    @jwt_required()
    def get(self, email):
        entry = find_blacklisted(email)
        return {
            "email": email,
            "is_blacklisted": entry is not None,
            "blocked_reason": entry.blocked_reason if entry else None,
        }, 200
