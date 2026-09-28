"""Réglages serveur. Variables lues dans /var/www/vitrine/.env (voir .env.example).

Obligatoires : SECRET_KEY, ALLOWED_HOST, DATABASE_NAME, DATABASE_USER,
DATABASE_PASSWORD, AWX_URL, AWX_TOKEN, AWX_ONBOARD_WORKFLOW_ID,
AWX_CALLBACK_SECRET, APP_REPO, APP_VERSION, SSO_KEY, EMAIL_HOST.
"""
import os

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = [os.environ["ALLOWED_HOST"]]

# PostgreSQL local : la vitrine n'est pas redondée, sa base non plus (D3 : rien
# des clients n'y vit durablement). CONN_MAX_AGE=60 + contrôle de santé, valeur
# de référence de la plateforme.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["DATABASE_NAME"],
        "USER": os.environ["DATABASE_USER"],
        "PASSWORD": os.environ["DATABASE_PASSWORD"],
        "HOST": os.environ.get("DATABASE_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DATABASE_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": 3},
    }
}

# Derrière Nginx et Cloudflare : le schéma d'origine arrive dans X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = False
CSRF_TRUSTED_ORIGINS = ["https://" + os.environ["ALLOWED_HOST"]]
CSRF_COOKIE_SECURE = True

# E-mails : confirmation d'adresse, bienvenue, alerte exploitant.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ["EMAIL_HOST"]
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() != "false"
EMAIL_TIMEOUT = 10

# Ce qui ne peut pas manquer pour que le guichet fonctionne.
for _name in ("AWX_URL", "AWX_TOKEN", "AWX_ONBOARD_WORKFLOW_ID", "AWX_CALLBACK_SECRET", "APP_REPO", "APP_VERSION", "SSO_KEY"):
    if not globals()[_name]:
        raise RuntimeError(f"Variable d'environnement manquante : {_name}")
