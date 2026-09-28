"""Réglages poste de développement : SQLite, DEBUG, e-mails dans la console.
Jamais sur un serveur."""
from .base import *  # noqa: F401,F403

DEBUG = True
SECRET_KEY = "dev-only-not-secret"
ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "dev.sqlite3",  # noqa: F405
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Valeurs de test : le lancement AWX échoue proprement tant qu'AWX_URL est vide.
SSO_KEY = SSO_KEY or "dev-sso-key"  # noqa: F405
APP_REPO = APP_REPO or "git@github.com:spawn451/temoin.git"  # noqa: F405
APP_VERSION = APP_VERSION or "v1.0.0"  # noqa: F405
