"""Tests du guichet. AWX et les espaces sont simulés : aucun réseau.

    python manage.py test
"""
import json
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import awx, slugs, tokens
from .models import Reservation

SETTINGS = dict(
    AWX_URL="https://awx.test",
    AWX_TOKEN="t",
    AWX_ONBOARD_WORKFLOW_ID="7",
    AWX_CALLBACK_SECRET="callback-secret",
    APP_REPO="git@github.com:spawn451/temoin.git",
    APP_VERSION="v1.0.0",
    SSO_KEY="sso-key-de-test",
    PLATFORM_DOMAIN="lovelyhome.io",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    OPERATOR_EMAIL="exploitant@example.test",
)

FORM = {"slug": "client1", "email": "Alice@Example.test", "password": "un-bon-mot-de-passe", "password2": "un-bon-mot-de-passe"}


def _reponse(payload, status=200):
    r = mock.Mock(status_code=status)
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


class SlugTests(TestCase):
    def test_regles(self):
        self.assertIsNone(slugs.problem("client1"))
        self.assertIsNone(slugs.problem("mon-espace-2"))
        for mauvais in ["1client", "Client", "a", "a" * 32, "client_1", "client-", "cli--ent", ""]:
            self.assertIsNotNone(slugs.problem(mauvais), mauvais)

    def test_reserves_identiques_au_playbook(self):
        for nom in ["www", "lb", "health", "mail", "preview", "admin", "root", "postgres", "temoin", "gemlogic", "demo", "api", "status", "docs", "blog"]:
            self.assertEqual(slugs.problem(nom), "Ce nom est réservé.")


@override_settings(**SETTINGS)
class InscriptionTests(TestCase):
    def test_reservation_et_email(self):
        r = self.client.post(reverse("inscription"), FORM)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Un e-mail vient de partir")
        res = Reservation.objects.get(slug="client1")
        self.assertEqual(res.email, "alice@example.test")
        self.assertEqual(res.statut, "pending")
        self.assertTrue(res.password_hash.startswith("pbkdf2_") or res.password_hash.startswith("argon2"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/confirmer/", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, ["alice@example.test"])

    def test_nom_pris(self):
        Reservation.objects.create(slug="client1", email="x@y.test", expires_at=Reservation.default_expiry())
        r = self.client.post(reverse("inscription"), FORM)
        self.assertContains(r, "déjà pris")
        self.assertEqual(Reservation.objects.count(), 1)

    def test_nom_reserve_et_mot_de_passe_faible(self):
        r = self.client.post(reverse("inscription"), {**FORM, "slug": "gemlogic", "password": "court", "password2": "court"})
        self.assertContains(r, "réservé")
        self.assertContains(r, "trop court")
        self.assertEqual(Reservation.objects.count(), 0)

    def test_reservation_expiree_liberee(self):
        Reservation.objects.create(slug="client1", email="x@y.test", expires_at=timezone.now() - timedelta(minutes=1))
        r = self.client.post(reverse("inscription"), FORM)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Reservation.objects.get(slug="client1").email, "alice@example.test")

    def test_email_impossible_annule(self):
        with mock.patch("guichet.mails.send_mail", side_effect=OSError("smtp down")):
            r = self.client.post(reverse("inscription"), FORM)
        self.assertContains(r, "Réessayez dans un instant")
        self.assertEqual(Reservation.objects.count(), 0)


@override_settings(**SETTINGS)
class ConfirmationTests(TestCase):
    def setUp(self):
        self.client.post(reverse("inscription"), FORM)
        self.res = Reservation.objects.get(slug="client1")
        self.url = reverse("confirmer", args=[tokens.confirm_token(self.res.pk)])

    @mock.patch("guichet.awx.requests.post")
    def test_lance_le_workflow(self, post):
        post.return_value = _reponse({"id": 42})
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse("attente", args=["client1"]), fetch_redirect_response=False)
        self.res.refresh_from_db()
        self.assertEqual(self.res.statut, "provisioning")
        self.assertEqual(self.res.workflow_job_id, 42)
        self.assertEqual(self.res.password_hash, "", "le hash ne survit pas à la confirmation")

        kwargs = post.call_args.kwargs
        self.assertEqual(post.call_args.args[0], "https://awx.test/api/v2/workflow_job_templates/7/launch/")
        nc = kwargs["json"]["extra_vars"]["new_client"]
        self.assertEqual(nc["name"], "client1")
        self.assertEqual(nc["domain"], "client1.lovelyhome.io")
        self.assertEqual(nc["repo"], "git@github.com:spawn451/temoin.git")
        self.assertEqual(nc["version"], "v1.0.0")
        self.assertEqual(nc["admin_email"], "alice@example.test")
        self.assertTrue(nc["admin_password_hash"].startswith("pbkdf2_") or nc["admin_password_hash"].startswith("argon2"))
        self.assertGreaterEqual(len(nc["db_password"]), 16)
        self.assertGreaterEqual(len(nc["django_secret_key"]), 32)

    @mock.patch("guichet.awx.requests.post", side_effect=awx.requests.ConnectionError("awx down"))
    def test_awx_indisponible_garde_la_reservation(self, post):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 503)
        self.assertContains(r, "rouvrez le même lien", status_code=503)
        self.res.refresh_from_db()
        self.assertEqual(self.res.statut, "pending")
        self.assertNotEqual(self.res.password_hash, "")

    def test_lien_falsifie(self):
        r = self.client.get(reverse("confirmer", args=["n-importe-quoi"]))
        self.assertEqual(r.status_code, 400)

    def test_lien_expire(self):
        Reservation.objects.filter(pk=self.res.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 410)

    @mock.patch("guichet.awx.requests.post")
    def test_second_clic_renvoie_vers_attente(self, post):
        post.return_value = _reponse({"id": 42})
        self.client.get(self.url)
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse("attente", args=["client1"]), fetch_redirect_response=False)
        self.assertEqual(post.call_count, 1)


@override_settings(**SETTINGS)
class SuiviTests(TestCase):
    def setUp(self):
        self.res = Reservation.objects.create(
            slug="client1", email="alice@example.test", statut="provisioning", workflow_job_id=42,
            awx_status="running", awx_checked_at=timezone.now(), expires_at=Reservation.default_expiry(),
        )
        self.statut = reverse("statut", args=["client1"])
        self.callback = reverse("awx_callback")

    def _callback(self, status, secret="callback-secret", job_id=42):
        return self.client.post(self.callback, data=json.dumps({"id": job_id, "status": status}), content_type="application/json", headers={"X-Vitrine-Secret": secret})

    def test_statut_sans_sondage_si_recent(self):
        with mock.patch("guichet.awx.requests.get") as get:
            d = self.client.get(self.statut).json()
        get.assert_not_called()
        self.assertEqual(d["statut"], "provisioning")

    @mock.patch("guichet.awx.espace_repond", return_value=True)
    @mock.patch("guichet.awx.requests.get")
    def test_sondage_de_secours_puis_pret(self, get, repond):
        Reservation.objects.filter(pk=self.res.pk).update(awx_checked_at=timezone.now() - timedelta(minutes=2))
        get.return_value = _reponse({"status": "successful"})
        d = self.client.get(self.statut).json()
        self.assertEqual(get.call_args.args[0], "https://awx.test/api/v2/workflow_jobs/42/")
        self.assertEqual(d["statut"], "ready")
        self.assertTrue(d["sso_url"].startswith("https://client1.lovelyhome.io/sso/?token="))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("prêt", mail.outbox[0].subject)

    @mock.patch("guichet.awx.espace_repond", return_value=False)
    def test_callback_succes_attend_que_l_espace_reponde(self, repond):
        self.assertEqual(self._callback("successful").status_code, 204)
        self.res.refresh_from_db()
        self.assertEqual(self.res.statut, "provisioning")
        self.assertEqual(self.res.awx_status, "successful")
        with mock.patch("guichet.awx.requests.get") as get:
            d = self.client.get(self.statut).json()
        get.assert_not_called()  # le statut AWX est final : plus de sondage
        self.assertEqual(d["statut"], "provisioning")
        repond.return_value = True
        d = self.client.get(self.statut).json()
        self.assertEqual(d["statut"], "ready")

    def test_callback_echec(self):
        self.assertEqual(self._callback("failed").status_code, 204)
        self.res.refresh_from_db()
        self.assertEqual(self.res.statut, "failed")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["exploitant@example.test"])
        self.assertIn("client1", mail.outbox[0].subject)

    def test_callback_secret_manquant_ou_faux(self):
        self.assertEqual(self._callback("failed", secret="").status_code, 403)
        self.assertEqual(self._callback("failed", secret="faux").status_code, 403)
        self.res.refresh_from_db()
        self.assertEqual(self.res.statut, "provisioning")

    def test_callback_workflow_inconnu(self):
        self.assertEqual(self._callback("successful", job_id=999).status_code, 204)

    def test_callback_test_awx_sans_id(self):
        """Le bouton Test d'AWX envoie un message générique : 204 si le secret est bon."""
        r = self.client.post(self.callback, data=json.dumps({"body": "Ansible Tower Test Notification"}), content_type="application/json", headers={"X-Vitrine-Secret": "callback-secret"})
        self.assertEqual(r.status_code, 204)
        self.res.refresh_from_db()
        self.assertEqual(self.res.statut, "provisioning")

    def test_attente_page(self):
        r = self.client.get(reverse("attente", args=["client1"]))
        self.assertContains(r, "client1.lovelyhome.io")
        self.assertContains(r, self.statut)

    def test_pret_regenere_un_jeton(self):
        Reservation.objects.filter(pk=self.res.pk).update(statut="ready")
        d = self.client.get(self.statut).json()
        token = d["sso_url"].split("token=")[1]
        self.assertEqual(tokens.read_sso_token(token), {"slug": "client1", "email": "alice@example.test"})


@override_settings(**SETTINGS)
class SsoTokenTests(TestCase):
    def test_signature_et_delai(self):
        t = tokens.sso_token("client1", "a@b.test")
        self.assertEqual(tokens.read_sso_token(t), {"slug": "client1", "email": "a@b.test"})
        self.assertIsNone(tokens.read_sso_token(t, key="autre-cle"))
        self.assertIsNone(tokens.read_sso_token(t + "x"))
        with mock.patch("django.core.signing.time.time", return_value=__import__("time").time() + 121):
            self.assertIsNone(tokens.read_sso_token(t))


@override_settings(**SETTINGS)
class ConnexionTests(TestCase):
    def test_redirige_vers_l_espace(self):
        Reservation.objects.create(slug="client1", email="a@b.test", statut="ready", expires_at=Reservation.default_expiry())
        r = self.client.post(reverse("connexion"), {"email": "A@b.test"})
        self.assertRedirects(r, "https://client1.lovelyhome.io/login/", fetch_redirect_response=False)

    def test_inconnu_ou_plusieurs(self):
        r = self.client.post(reverse("connexion"), {"email": "x@y.test"})
        self.assertContains(r, "Aucun espace")
        for s in ["c1", "c2"]:
            Reservation.objects.create(slug=s, email="a@b.test", statut="ready", expires_at=Reservation.default_expiry())
        r = self.client.post(reverse("connexion"), {"email": "a@b.test"})
        self.assertContains(r, "c1.lovelyhome.io")
        self.assertContains(r, "c2.lovelyhome.io")


class ProductionSettingsTests(TestCase):
    """production.py se charge avec un environnement complet, en mode smtp et en mode fichier."""

    ENV = dict(
        SECRET_KEY="s", ALLOWED_HOST="gemlogic.lovelyhome.io", DATABASE_NAME="v", DATABASE_USER="v", DATABASE_PASSWORD="p",
        AWX_URL="https://awx.test", AWX_TOKEN="t", AWX_ONBOARD_WORKFLOW_ID="7", AWX_CALLBACK_SECRET="c",
        APP_REPO="git@github.com:spawn451/temoin.git", APP_VERSION="v1.0.0", SSO_KEY="k",
    )

    def _load(self, **extra):
        import importlib
        import sys

        with mock.patch.dict("os.environ", {**self.ENV, **extra}, clear=False):
            # base.py lit l'environnement à l'import : on le recharge aussi.
            for name in ("config.settings.production", "config.settings.base"):
                sys.modules.pop(name, None)
            return importlib.import_module("config.settings.production")

    def test_mode_fichier_sans_smtp(self):
        m = self._load(EMAIL_MODE="fichier")
        self.assertEqual(m.EMAIL_BACKEND, "django.core.mail.backends.filebased.EmailBackend")
        self.assertTrue(m.EMAIL_FILE_PATH.endswith("mails"))

    def test_mode_smtp_exige_email_host(self):
        with self.assertRaises(KeyError):
            self._load()
        m = self._load(EMAIL_HOST="smtp.test")
        self.assertEqual(m.EMAIL_BACKEND, "django.core.mail.backends.smtp.EmailBackend")

    def test_variable_manquante_refusee(self):
        with self.assertRaisesRegex(RuntimeError, "SSO_KEY"):
            self._load(EMAIL_MODE="fichier", SSO_KEY="")


@override_settings(**SETTINGS)
class PurgeTests(TestCase):
    def test_purge(self):
        from django.core.management import call_command

        Reservation.objects.create(slug="vieux", email="a@b.test", expires_at=timezone.now() - timedelta(hours=1))
        Reservation.objects.create(slug="recent", email="a@b.test", expires_at=Reservation.default_expiry())
        Reservation.objects.create(slug="encours", email="a@b.test", statut="provisioning", expires_at=timezone.now() - timedelta(hours=1))
        call_command("purge_reservations", verbosity=0)
        self.assertEqual(sorted(Reservation.objects.values_list("slug", flat=True)), ["encours", "recent"])

    def test_health(self):
        self.assertEqual(self.client.get(reverse("health")).content, b"ok")
