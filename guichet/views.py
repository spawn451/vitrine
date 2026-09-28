"""Le guichet : quatre vues qui comptent (inscription, confirmer, statut,
awx_callback), les pages vitrine autour, et /health/.

Aucun processus de fond : le lancement AWX tient dans la requête de
confirmation, l'attente est une page qui interroge /statut/, la fin arrive par
la notification AWX ou par un appel court à son API.
"""
import hmac
import json
import logging
import smtplib

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.db import DatabaseError
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from . import awx, mails, tokens
from .forms import ConnexionForm, InscriptionForm
from .models import Reservation

log = logging.getLogger(__name__)
Statut = Reservation.Statut


# --- Pages vitrine -------------------------------------------------------------


def accueil(request):
    return render(request, "guichet/accueil.html")


def offre(request):
    return render(request, "guichet/offre.html", {"app_version": settings.APP_VERSION})


def conditions(request):
    return render(request, "guichet/conditions.html")


def confidentialite(request):
    return render(request, "guichet/confidentialite.html", {"hours": settings.RESERVATION_HOURS})


@require_GET
def health(request):
    """Route de supervision : 200 seulement si la base répond."""
    try:
        Reservation.objects.exists()
    except DatabaseError as e:
        log.warning("health : base indisponible : %s", e)
        return HttpResponse("db unavailable", status=503, content_type="text/plain")
    return HttpResponse("ok", content_type="text/plain")


# --- Inscription ---------------------------------------------------------------


@require_http_methods(["GET", "POST"])
def inscription(request):
    """Réserve le nom 24 h, hache le mot de passe, envoie le lien de confirmation.
    Rien n'est créé sur les serveurs ici."""
    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        slug = form.cleaned_data["slug"]
        # Une ancienne réservation expirée du même nom libère la place.
        Reservation.objects.filter(slug=slug, statut=Statut.PENDING, expires_at__lte=timezone.now()).delete()
        r = Reservation.objects.create(
            slug=slug,
            nom=form.cleaned_data["nom"],
            email=form.cleaned_data["email"],
            password_hash=make_password(form.cleaned_data["password"]),
            expires_at=Reservation.default_expiry(),
        )
        confirm_url = request.build_absolute_uri(reverse("confirmer", args=[tokens.confirm_token(r.pk)]))
        try:
            mails.confirmation(r, confirm_url)
        except (smtplib.SMTPException, OSError) as e:
            log.error("inscription %s : e-mail de confirmation impossible : %s", slug, e)
            r.delete()
            form.add_error(None, "Impossible d'envoyer l'e-mail de confirmation pour le moment. Réessayez dans un instant.")
        else:
            log.info("inscription %s réservée pour %s", slug, r.email)
            return render(request, "guichet/inscription_envoyee.html", {"r": r})
    return render(request, "guichet/inscription.html", {"form": form, "platform_domain": settings.PLATFORM_DOMAIN})


@require_GET
def confirmer(request, token):
    """Le clic dans l'e-mail : lance le workflow AWX, oublie le hash, envoie sur la page d'attente."""
    rid = tokens.read_confirm_token(token)
    r = Reservation.objects.filter(pk=rid).first() if rid else None
    if r is None:
        return render(request, "guichet/confirmer_invalide.html", {"raison": "lien"}, status=400)
    if r.statut != Statut.PENDING:
        return redirect("attente", slug=r.slug)  # déjà confirmé : on retrouve l'attente ou l'espace
    if r.is_expired:
        return render(request, "guichet/confirmer_invalide.html", {"raison": "expire", "r": r}, status=410)

    try:
        job_id = awx.launch_onboarding(r.slug, r.email, r.password_hash)
    except awx.AwxError:
        # La réservation reste ; le même lien resservira.
        return render(request, "guichet/confirmer_reessayer.html", {"r": r}, status=503)

    now = timezone.now()
    r.workflow_job_id = job_id
    r.statut = Statut.PROVISIONING
    r.confirmed_at = now
    r.awx_checked_at = now
    r.awx_status = "pending"
    r.password_hash = ""
    r.save()
    return redirect("attente", slug=r.slug)


@require_GET
def attente(request, slug):
    """« Votre espace se prépare » : la page interroge /statut/ toutes les 3 s."""
    r = get_object_or_404(Reservation.active(), slug=slug)
    if r.statut == Statut.PENDING:
        return render(request, "guichet/confirmer_invalide.html", {"raison": "non_confirme", "r": r}, status=409)
    return render(request, "guichet/attente.html", {"r": r})


@require_GET
def statut(request, slug):
    """Statut JSON de la réservation ; sonde AWX en secours si la notification tarde."""
    r = get_object_or_404(Reservation.active(), slug=slug)
    if r.statut == Statut.PROVISIONING:
        _refresh(r)
    data = {"statut": r.statut, "message": r.message, "url": r.url}
    if r.statut == Statut.READY:
        data["sso_url"] = f"{r.url}sso/?token={tokens.sso_token(r.slug, r.email)}"
    return JsonResponse(data)


def _refresh(r):
    """Fait avancer une réservation en mise en service : interroge AWX si besoin,
    puis vérifie que l'espace répond avant de le déclarer prêt."""
    now = timezone.now()
    if r.awx_status not in awx.FINAL_OK | awx.FINAL_KO:
        stale = r.awx_checked_at is None or (now - r.awx_checked_at).total_seconds() >= settings.AWX_POLL_AFTER_SECONDS
        if stale and r.workflow_job_id:
            try:
                r.awx_status = awx.workflow_status(r.workflow_job_id)
            except awx.AwxError:
                pass
            r.awx_checked_at = now
    _apply_awx_status(r)
    r.save()


def _apply_awx_status(r):
    """Traduit le statut AWX en statut de réservation. Ne sauvegarde pas."""
    if r.statut != Statut.PROVISIONING:
        return
    if r.awx_status in awx.FINAL_KO:
        r.statut = Statut.FAILED
        r.message = "La mise en service a échoué. Nous avons été prévenus et revenons vers vous par e-mail."
        mails.alerte_exploitant(r, f"workflow_job {r.workflow_job_id} : {r.awx_status}")
    elif r.awx_status in awx.FINAL_OK:
        if awx.espace_repond(r.domain):
            r.statut = Statut.READY
            r.ready_at = timezone.now()
            r.message = ""
            try:
                mails.bienvenue(r)
            except (smtplib.SMTPException, OSError) as e:
                log.warning("bienvenue %s : %s", r.slug, e)
        else:
            r.message = "Les serveurs finissent la mise en service."
    else:
        r.message = {"pending": "En file d'attente.", "waiting": "En file d'attente."}.get(r.awx_status, "Mise en service en cours.")


@csrf_exempt
@require_POST
def awx_callback(request):
    """Notification webhook d'AWX (succès et échec du workflow). Le corps est le
    JSON du workflow_job : on lit id et status. Toute requête authentique
    (bon secret) reçoit 204, même sans id exploitable : le bouton « Test »
    d'AWX envoie un message générique, et un 204 lui suffit pour afficher
    « succès », ce qui prouve connectivité et secret."""
    secret = settings.AWX_CALLBACK_SECRET
    given = request.headers.get("X-Vitrine-Secret", "")
    if not secret or not hmac.compare_digest(given, secret):
        return HttpResponseForbidden()
    try:
        body = json.loads(request.body or b"{}")
        job_id = int(body["id"])
        status = str(body.get("status", ""))
    except (ValueError, KeyError, TypeError):
        log.info("callback AWX sans id de workflow (test ?) : %.200s", request.body)
        return HttpResponse(status=204)
    r = Reservation.objects.filter(workflow_job_id=job_id).first()
    if r is None:
        log.info("callback AWX pour un workflow inconnu : %s", job_id)
        return HttpResponse(status=204)
    r.awx_status = status
    r.awx_checked_at = timezone.now()
    _apply_awx_status(r)
    r.save()
    return HttpResponse(status=204)


# --- Connexion (retrouver son espace) ------------------------------------------


@require_http_methods(["GET", "POST"])
def connexion(request):
    """Ne vérifie aucun mot de passe : retrouve l'espace d'après l'e-mail et y envoie."""
    form = ConnexionForm(request.POST or None)
    espaces = None
    if request.method == "POST" and form.is_valid():
        espaces = list(Reservation.objects.filter(email=form.cleaned_data["email"], statut=Statut.READY).order_by("slug"))
        if len(espaces) == 1:
            return redirect(f"{espaces[0].url}login/")
    return render(request, "guichet/connexion.html", {"form": form, "espaces": espaces})
