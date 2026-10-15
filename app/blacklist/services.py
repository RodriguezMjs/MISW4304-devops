"""Lógica de negocio de la lista negra."""

from ..extensions import db
from .models import Blacklist


class EmailAlreadyBlacklisted(Exception):
    def __init__(self, email):
        super().__init__(f"El email {email} ya está en la lista negra global")
        self.email = email


def normalize_email(email):
    return email.strip().lower()


def add_to_blacklist(email, app_uuid, blocked_reason, ip_address):
    """Agrega un email a la lista negra global.

    Lanza EmailAlreadyBlacklisted si el email ya existe.
    """
    email = normalize_email(email)
    if Blacklist.query.filter_by(email=email).first():
        raise EmailAlreadyBlacklisted(email)

    entry = Blacklist(
        email=email,
        app_uuid=str(app_uuid),
        blocked_reason=blocked_reason,
        ip_address=ip_address,
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def find_blacklisted(email):
    """Retorna el registro de la lista negra para el email, o None si no está."""
    return Blacklist.query.filter_by(email=normalize_email(email)).first()
