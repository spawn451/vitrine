"""Les deux appels AWX de la vitrine : lancer le workflow onboard-client, lire l'état d'un workflow_job.

Le jeton n'a que le droit d'exécuter ce workflow ; tout autre appel serait refusé par AWX.
"""
import logging
import secrets

import requests
from django.conf import settings

log = logging.getLogger(__name__)

# Statuts AWX qui terminent un workflow.
FINAL_OK = {"successful"}
FINAL_KO = {"failed", "error", "canceled"}


class AwxError(Exception):
    pass


def _headers():
    return {"Authorization": f"Bearer {settings.AWX_TOKEN}", "Content-Type": "application/json"}


def launch_onboarding(slug: str, email: str, password_hash: str) -> int:
    """POST launch du workflow. Les secrets du client sont générés ici et ne
    sont gardés nulle part sur la vitrine : AWX les chiffre dans vault.yml."""
    new_client = {
        "name": slug,
        "domain": f"{slug}.{settings.PLATFORM_DOMAIN}",
        "repo": settings.APP_REPO,
        "version": settings.APP_VERSION,
        "workers": settings.APP_WORKERS,
        "db_password": secrets.token_urlsafe(24),
        "django_secret_key": secrets.token_urlsafe(48),
        "admin_email": email,
        "admin_password_hash": password_hash,
    }
    url = f"{settings.AWX_URL}/api/v2/workflow_job_templates/{settings.AWX_ONBOARD_WORKFLOW_ID}/launch/"
    try:
        r = requests.post(url, headers=_headers(), json={"extra_vars": {"new_client": new_client}}, timeout=30, verify=settings.AWX_VERIFY_SSL)
        r.raise_for_status()
        job_id = int(r.json()["id"])
    except (requests.RequestException, KeyError, ValueError) as e:
        log.error("AWX launch %s : %s", slug, e)
        raise AwxError(str(e)) from e
    log.info("AWX launch %s : workflow_job %s", slug, job_id)
    return job_id


def workflow_status(job_id: int) -> str:
    """Statut du workflow_job : pending, waiting, running, successful, failed, error, canceled."""
    url = f"{settings.AWX_URL}/api/v2/workflow_jobs/{job_id}/"
    try:
        r = requests.get(url, headers=_headers(), timeout=10, verify=settings.AWX_VERIFY_SSL)
        r.raise_for_status()
        return str(r.json()["status"])
    except (requests.RequestException, KeyError, ValueError) as e:
        log.warning("AWX status %s : %s", job_id, e)
        raise AwxError(str(e)) from e


def espace_repond(domain: str) -> bool:
    """L'espace répond-il déjà ? Tant que le vhost n'existe pas, Nginx ferme la
    connexion (444) et Cloudflare renvoie une erreur 52x ; dès qu'il est là,
    la page d'accueil (ou sa redirection vers /login/) répond en 2xx/3xx."""
    try:
        r = requests.get(f"https://{domain}/", timeout=5, allow_redirects=True)
        return r.status_code < 400
    except requests.RequestException:
        return False
