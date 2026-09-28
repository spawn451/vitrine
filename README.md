# Vitrine GemLogic

Site vitrine et guichet d'inscription de la plateforme. Un visiteur choisit un
nom d'espace, confirme son e-mail, et une minute plus tard il est connecté sur
`<nom>.lovelyhome.io`, mis en service par AWX. L'architecture est décrite dans
`Architecture/evolution-onboarding-signup.md` du vault de documentation ; ce
dépôt en est l'étape 2 (le guichet) et fournit les fichiers de l'étape 3
(l'hébergement).

Ce que la vitrine **fait** : réserver un nom, faire confirmer l'adresse,
générer les secrets du client, lancer le workflow AWX `onboard-client`,
afficher l'attente, rediriger vers l'espace avec un jeton de première
connexion, retrouver l'espace d'un e-mail au bouton « Se connecter ».

Ce qu'elle **n'a pas** : SSH vers les serveurs, accès Git, mot de passe du
vault, comptes utilisateurs, mots de passe en clair, Celery, Redis. Si elle
tombe, personne n'est empêché de se connecter à son espace.

## Routes

| Route | Rôle |
|---|---|
| `/`, `/offre/` | Pages vitrine (contenu à remplacer) |
| `/inscription/` | Formulaire : nom, e-mail, mot de passe. Réserve le nom 24 h, hache le mot de passe, envoie le lien de confirmation |
| `/confirmer/<token>/` | Le clic dans l'e-mail : lance le workflow AWX, efface le hash, redirige vers l'attente |
| `/attente/<slug>/` | « Votre espace se prépare » ; interroge `/statut/` toutes les 3 s |
| `/statut/<slug>/` | JSON : `pending`, `provisioning`, `ready` (+ `sso_url`), `failed`. Sonde l'API AWX si la notification tarde |
| `/awx/callback/` | Notification webhook d'AWX, en-tête `X-Vitrine-Secret` |
| `/connexion/` | E-mail → redirection vers `https://<slug>.lovelyhome.io/login/` |
| `/health/` | `ok` si la base répond, sinon 503 |

Règles sur le nom (`guichet/slugs.py`) : mêmes regex et noms réservés que
`reserved_names` dans `playbooks/onboard-client.yml`. **Si l'un change,
changer l'autre.**

## Poste de développement

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
python manage.py migrate
python manage.py test
python manage.py runserver
```

Sans réglage, `manage.py` utilise `config.settings.dev` : SQLite, `DEBUG`,
e-mails dans la console. Sans `AWX_URL`, le clic de confirmation affiche
« réessayez dans un instant » et garde la réservation.

## Installation sur le serveur (Ubuntu 24.04, une seule machine)

Utilisateur `vitrine`, code dans `/var/www/vitrine/src`, venv dans
`/var/www/vitrine/venv`, réglages dans `/var/www/vitrine/.env`, PostgreSQL
local. Tout est fait à la main ici ; un playbook `vitrine.yml` dans
`plateforme` pourra le reprendre. La procédure pas à pas, avec les
vérifications, le tunnel Cloudflare et la configuration AWX, est dans le
vault : `Guide/guide-installation-vitrine.md`. Ci-dessous, le condensé.

```bash
sudo apt install -y python3-venv postgresql nginx git
sudo useradd --system --home /var/www/vitrine --shell /usr/sbin/nologin vitrine
sudo mkdir -p /var/www/vitrine && sudo chown vitrine:www-data /var/www/vitrine

sudo -u postgres psql -c "CREATE ROLE vitrine LOGIN PASSWORD '<mot de passe>';"
sudo -u postgres psql -c "CREATE DATABASE vitrine OWNER vitrine;"

sudo -u vitrine git clone git@github.com:spawn451/vitrine.git /var/www/vitrine/src   # deploy key en lecture si privé
sudo -u vitrine python3 -m venv /var/www/vitrine/venv
sudo -u vitrine /var/www/vitrine/venv/bin/pip install -r /var/www/vitrine/src/requirements.txt

sudo cp /var/www/vitrine/src/.env.example /var/www/vitrine/.env   # puis renseigner chaque valeur
sudo chown vitrine:www-data /var/www/vitrine/.env && sudo chmod 640 /var/www/vitrine/.env

cd /var/www/vitrine/src
sudo -u vitrine env $(grep -v '^#' ../.env | xargs) ../venv/bin/python manage.py migrate
sudo -u vitrine env $(grep -v '^#' ../.env | xargs) ../venv/bin/python manage.py collectstatic --noinput

sudo cp deploy/vitrine.service deploy/vitrine-purge.service deploy/vitrine-purge.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now vitrine.service vitrine-purge.timer

sudo cp deploy/nginx-vitrine.conf /etc/nginx/sites-available/vitrine
sudo ln -sf /etc/nginx/sites-available/vitrine /etc/nginx/sites-enabled/vitrine
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
curl -H 'Host: gemlogic.lovelyhome.io' http://127.0.0.1/health/     # ok
```

**Exposition.** Un tunnel Cloudflare propre à ce serveur (`cloudflared`),
route publique `gemlogic.lovelyhome.io` → `http://localhost:80`. Dans la
zone DNS, l'enregistrement `gemlogic` (CNAME vers le tunnel, proxied) prime
sur le wildcard `*.lovelyhome.io` qui pointe vers S1/S2. Rien à changer sur
les tunnels de la plateforme ni sur le load balancer.

**Mise à jour.** `git pull` (ou checkout d'un tag), `pip install -r
requirements.txt` si les dépendances ont changé, `migrate`, `collectstatic`,
puis `systemctl reload vitrine` : Gunicorn recharge sans coupure.

## Côté AWX

| Quoi | Comment |
|---|---|
| Utilisateur `vitrine` | Utilisateur AWX normal, sans rôle d'organisation. Sur le modèle de workflow `onboard-client` : Accès → Ajouter → rôle **Exécuter**. Il ne peut rien lancer d'autre |
| Jeton | Connecté en `vitrine` : Utilisateurs → vitrine → Jetons → Ajouter, portée **Écriture**, sans application. La valeur n'est affichée qu'une fois : `AWX_TOKEN` |
| Id du workflow | Dans l'URL du modèle de workflow : `/#/templates/workflow_job_template/<id>/` → `AWX_ONBOARD_WORKFLOW_ID` |
| Enquête | Pas pour l'instant : une enquête ne masque (`$encrypted$`) que des variables de premier niveau, et l'entrée est le dictionnaire `new_client`. L'onglet Variables du job montre donc `db_password`, `django_secret_key` et `admin_password_hash` en clair aux utilisateurs AWX qui voient les jobs. Aplatir l'entrée (vitrine + playbook) dans une seconde version |
| Notification | Notifications → Ajouter : type **Webhook**, URL `https://gemlogic.lovelyhome.io/awx/callback/`, en-têtes HTTP `{"X-Vitrine-Secret": "<AWX_CALLBACK_SECRET>"}`, méthode POST. Puis sur le modèle de workflow `onboard-client`, onglet Notifications : activer **Succès** et **Échec**. Le corps par défaut contient `id` et `status`, c'est ce que lit la vitrine |
| Sans notification | La vitrine s'en passe : passé `AWX_POLL_AFTER_SECONDS` (60 s), `/statut/` interroge `GET /api/v2/workflow_jobs/<id>/` avec le jeton. La notification rend juste la fin visible plus tôt |

Ce que la vitrine envoie au workflow (`guichet/awx.py`) :

```yaml
new_client:
  name: client1
  domain: client1.lovelyhome.io
  repo: <APP_REPO>
  version: <APP_VERSION>
  workers: <APP_WORKERS>
  db_password: <généré>
  django_secret_key: <généré>
  admin_email: <saisi>
  admin_password_hash: <make_password() du mot de passe saisi>
```

`onboard-client.yml` chiffre `admin_email` et `admin_password_hash` dans le
vault avec les autres secrets ; `env.j2` les pose dans le `.env` de l'espace
(`BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD_HASH`) avec `SSO_KEY`
(`vault_sso_key`) ; le rôle `deploy` lance `manage.py bootstrap` après
`migrate` si l'application a la commande. Tant qu'elle ne l'a pas, l'espace
est créé sans premier compte, le jeton SSO est refusé et le visiteur atterrit
sur `/login/`.

## Ce que l'application cliente doit fournir

Deux ajouts, décrits dans `evolution-onboarding-signup.md`, sans dépendance
vers la vitrine :

- une commande `manage.py bootstrap`, idempotente, qui crée le premier compte
  depuis `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD_HASH` si la table
  des utilisateurs est vide, l'organisation, et les données de référence ;
- une vue `/sso/?token=…` qui vérifie le jeton avec la même `SSO_KEY`
  (`TimestampSigner(key=SSO_KEY, salt="signup-sso")`, âge < 120 s, `slug`
  égal au sien, utilisateur trouvé par e-mail, `last_login` vide), fait
  `login()` et redirige vers le tableau de bord ; sinon redirige vers
  `/login/`. `guichet/tokens.py::read_sso_token` en est la référence.

## Exploitation

```bash
cd /var/www/vitrine/src && sudo -u vitrine env $(grep -v '^#' ../.env | xargs) ../venv/bin/python manage.py reservations
```

Liste l'annuaire (nom, statut, e-mail, id du workflow, message). Un échec de
workflow envoie un e-mail à `OPERATOR_EMAIL` avec le lien du job ; le client
est peut-être déjà dans `clients.yml` (le push a pu réussir avant
`client-provision`) : reprendre avec `guide-ajout-client` §4. Une ligne
`failed` garde le nom pris ; la supprimer à la main (`psql`) une fois la
situation réglée si le nom doit redevenir libre.

Les réservations jamais confirmées disparaissent au bout de 24 h
(`vitrine-purge.timer`). Le mot de passe haché ne vit dans la base que jusqu'à
la confirmation.
