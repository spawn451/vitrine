"""Réglages communs. Rien de secret ici : tout vient de l'environnement.

Les réglages propres au guichet (AWX, plateforme, SSO) sont lus ici avec des
valeurs vides ; production.py exige ceux qui ne peuvent pas manquer.
"""
import os
from pathlib import Path

# /var/www/vitrine/src sur le serveur
BASE_DIR = Path(__file__).resolve().parent.parent.parent

INSTALLED_APPS = [
    "django.contrib.auth",  # pas de compte sur la vitrine : sert aux validateurs de mot de passe (messages en français)
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "guichet",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
X_FRAME_OPTIONS = "DENY"

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "guichet.context_processors.plateforme",
                "guichet.context_processors.static_version",
            ]
        },
    },
]

LANGUAGE_CODE = "fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

# Nginx sert /static/ depuis /var/www/vitrine/static/ (collectstatic y écrit).
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR.parent / "static"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Le mot de passe choisi à l'inscription devient celui du premier compte de l'espace.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

# --- Guichet -----------------------------------------------------------------

# Domaine de la plateforme : un espace « client1 » vit à https://client1.<PLATFORM_DOMAIN>/
PLATFORM_DOMAIN = os.environ.get("PLATFORM_DOMAIN", "lovelyhome.io")

# Code reçu par tout nouvel inscrit : un dépôt, un tag, fixés ici (jamais « le dernier tag »).
APP_REPO = os.environ.get("APP_REPO", "")
APP_VERSION = os.environ.get("APP_VERSION", "")
APP_WORKERS = int(os.environ.get("APP_WORKERS", "2"))

# AWX : le jeton n'a que le droit d'exécuter le workflow onboard-client.
AWX_URL = os.environ.get("AWX_URL", "").rstrip("/")
AWX_TOKEN = os.environ.get("AWX_TOKEN", "")
AWX_ONBOARD_WORKFLOW_ID = os.environ.get("AWX_ONBOARD_WORKFLOW_ID", "")
AWX_VERIFY_SSL = os.environ.get("AWX_VERIFY_SSL", "true").lower() != "false"
# En-tête X-Vitrine-Secret attendu sur la notification webhook d'AWX.
AWX_CALLBACK_SECRET = os.environ.get("AWX_CALLBACK_SECRET", "")
# Sans notification depuis ce délai, /statut/ sonde l'API AWX en secours.
AWX_POLL_AFTER_SECONDS = int(os.environ.get("AWX_POLL_AFTER_SECONDS", "60"))

# Clé de signature du jeton de première connexion, commune à la vitrine et aux espaces.
SSO_KEY = os.environ.get("SSO_KEY", "")
SSO_MAX_AGE_SECONDS = 120

# Une réservation non confirmée est libérée après ce délai.
RESERVATION_HOURS = int(os.environ.get("RESERVATION_HOURS", "24"))

# Reçoit un e-mail quand un workflow échoue.
OPERATOR_EMAIL = os.environ.get("OPERATOR_EMAIL", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "GemLogic <no-reply@" + PLATFORM_DOMAIN + ">")
