"""L'annuaire de la vitrine : une ligne par nom d'espace demandé.

La vitrine ne garde durablement que l'e-mail, le nom d'espace, le statut et
l'id du workflow. Le mot de passe haché n'y vit que jusqu'à la confirmation
de l'adresse ; il part ensuite dans le vault (chiffré) puis dans la base du
client, et la colonne est vidée.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Reservation(models.Model):
    class Statut(models.TextChoices):
        PENDING = "pending", "En attente de confirmation"
        PROVISIONING = "provisioning", "Mise en service"
        READY = "ready", "Prêt"
        FAILED = "failed", "Échec"

    slug = models.SlugField("nom d'espace", max_length=31, unique=True)
    nom = models.CharField("nom du demandeur", max_length=80, blank=True)
    email = models.EmailField("e-mail")
    # make_password() du mot de passe choisi ; vidé à la confirmation.
    password_hash = models.CharField(max_length=128, blank=True)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField("expiration de la réservation")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)

    # Suivi AWX : id du workflow_job, dernier statut connu, dernière fois qu'on l'a appris.
    workflow_job_id = models.IntegerField(null=True, blank=True)
    awx_status = models.CharField(max_length=20, blank=True)
    awx_checked_at = models.DateTimeField(null=True, blank=True)
    message = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "réservation"

    def __str__(self):
        return f"{self.slug} ({self.statut})"

    @staticmethod
    def default_expiry():
        return timezone.now() + timedelta(hours=settings.RESERVATION_HOURS)

    @property
    def domain(self):
        return f"{self.slug}.{settings.PLATFORM_DOMAIN}"

    @property
    def url(self):
        return f"https://{self.domain}/"

    @property
    def is_expired(self):
        return self.statut == self.Statut.PENDING and self.expires_at <= timezone.now()

    @classmethod
    def active(cls):
        """Réservations qui tiennent un nom : tout sauf les pending expirées."""
        now = timezone.now()
        return cls.objects.exclude(statut=cls.Statut.PENDING, expires_at__lte=now)
