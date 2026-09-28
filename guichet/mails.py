"""Les trois e-mails de la vitrine, envoyés dans la requête qui les provoque."""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

log = logging.getLogger(__name__)


def _send(subject, template, ctx, to):
    body = render_to_string(template, ctx)
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to])


def confirmation(reservation, confirm_url: str):
    _send(
        f"Confirmez votre adresse pour ouvrir {reservation.domain}",
        "guichet/mail_confirmation.txt",
        {"r": reservation, "confirm_url": confirm_url, "hours": settings.RESERVATION_HOURS},
        reservation.email,
    )


def bienvenue(reservation):
    _send(
        f"Votre espace {reservation.domain} est prêt",
        "guichet/mail_bienvenue.txt",
        {"r": reservation},
        reservation.email,
    )


def alerte_exploitant(reservation, detail: str):
    """Un workflow a échoué : l'exploitant reprend à la main (guide-ajout-client §4)."""
    if not settings.OPERATOR_EMAIL:
        log.error("workflow %s en échec pour %s : %s", reservation.workflow_job_id, reservation.slug, detail)
        return
    _send(
        f"[vitrine] Échec de l'inscription {reservation.slug}",
        "guichet/mail_alerte.txt",
        {"r": reservation, "detail": detail, "awx_url": settings.AWX_URL},
        settings.OPERATOR_EMAIL,
    )
