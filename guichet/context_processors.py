from django.conf import settings


def plateforme(request):
    return {"PLATFORM_DOMAIN": settings.PLATFORM_DOMAIN}
