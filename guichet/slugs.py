"""Règles sur le nom d'espace. Les mêmes que l'assert de onboard-client.yml :
si on les change ici, les changer là aussi (et inversement)."""
import re

SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,30}$")

# Copie de reserved_names dans playbooks/onboard-client.yml (plateforme).
RESERVED = frozenset(
    ["www", "lb", "health", "mail", "preview", "admin", "root", "postgres", "temoin", "gemlogic", "demo", "api", "status", "docs", "blog"]
)


def normalize(value: str) -> str:
    return (value or "").strip().lower()


def problem(slug: str) -> str | None:
    """Renvoie le message d'erreur, ou None si le nom est acceptable (hors disponibilité)."""
    if not SLUG_RE.match(slug):
        return "2 à 31 caractères, lettres minuscules, chiffres et tirets, en commençant par une lettre."
    if slug.endswith("-") or "--" in slug:
        return "Le nom ne peut pas finir par un tiret ni en contenir deux à la suite."
    if slug in RESERVED:
        return "Ce nom est réservé."
    return None
