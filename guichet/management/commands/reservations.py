"""Liste l'annuaire de la vitrine (pas d'interface d'administration : une commande suffit)."""
from django.core.management.base import BaseCommand

from guichet.models import Reservation


class Command(BaseCommand):
    help = "Affiche les réservations : nom, statut, e-mail, workflow AWX, dates."

    def add_arguments(self, parser):
        parser.add_argument("--statut", choices=[s.value for s in Reservation.Statut], help="ne montrer qu'un statut")

    def handle(self, *args, **options):
        qs = Reservation.objects.all()
        if options["statut"]:
            qs = qs.filter(statut=options["statut"])
        self.stdout.write(f"{'nom':<32}{'statut':<14}{'e-mail':<36}{'awx':>6}  créé le             message")
        for r in qs:
            job = r.workflow_job_id or ""
            self.stdout.write(f"{r.slug:<32}{r.statut:<14}{r.email:<36}{job:>6}  {r.created_at:%Y-%m-%d %H:%M}    {r.message}")
        self.stdout.write(f"{qs.count()} réservation(s)")
