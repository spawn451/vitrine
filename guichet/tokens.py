"""Les deux jetons signés de la vitrine.

- Lien de confirmation d'e-mail : signé avec SECRET_KEY de la vitrine, valable
  RESERVATION_HOURS, porte l'id de la réservation.
- Jeton SSO de première connexion : signé avec SSO_KEY (commune aux espaces),
  valable 120 s, porte le slug et l'e-mail. L'espace ne l'accepte que pour un
  compte qui ne s'est jamais connecté.
"""
from django.conf import settings
from django.core import signing

CONFIRM_SALT = "signup-confirm"
SSO_SALT = "signup-sso"


def confirm_token(reservation_id: int) -> str:
    return signing.TimestampSigner(salt=CONFIRM_SALT).sign_object({"id": reservation_id})


def read_confirm_token(token: str) -> int | None:
    try:
        data = signing.TimestampSigner(salt=CONFIRM_SALT).unsign_object(token, max_age=settings.RESERVATION_HOURS * 3600)
        return int(data["id"])
    except (signing.BadSignature, KeyError, ValueError, TypeError):
        return None


def sso_token(slug: str, email: str) -> str:
    return signing.TimestampSigner(key=settings.SSO_KEY, salt=SSO_SALT).sign_object({"slug": slug, "email": email})


def read_sso_token(token: str, key: str | None = None) -> dict | None:
    """Ce que fait la vue /sso/ de l'espace client (ici pour les tests et la documentation)."""
    try:
        return signing.TimestampSigner(key=key or settings.SSO_KEY, salt=SSO_SALT).unsign_object(token, max_age=settings.SSO_MAX_AGE_SECONDS)
    except signing.BadSignature:
        return None
