"""Libère les noms réservés jamais confirmés. Lancée par le timer systemd
vitrine-purge.timer (toutes les heures)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from guichet.models import Reservation


class Command(BaseCommand):
    help = "Supprime les réservations en attente de confirmation dont le délai est dépassé."

    def handle(self, *args, **options):
        n, _ = Reservation.objects.filter(statut=Reservation.Statut.PENDING, expires_at__lte=timezone.now()).delete()
        self.stdout.write(f"{n} réservation(s) expirée(s) supprimée(s)")
