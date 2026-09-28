from pathlib import Path

from django.conf import settings
from django.contrib.staticfiles import finders

_version = None


def static_version(request):
    """Date de modification du CSS, pour versionner son URL et éviter le cache
    (navigateur et Cloudflare) après une mise à jour."""
    global _version
    if _version is None:
        found = finders.find("guichet/style.css")
        path = Path(found) if found else settings.BASE_DIR / "guichet" / "static" / "guichet" / "style.css"
        _version = str(int(path.stat().st_mtime)) if path.exists() else "0"
    return {"static_version": _version}


def plateforme(request):
    return {"PLATFORM_DOMAIN": settings.PLATFORM_DOMAIN}
