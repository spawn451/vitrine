from django.urls import path

from . import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("offre/", views.offre, name="offre"),
    path("conditions/", views.conditions, name="conditions"),
    path("confidentialite/", views.confidentialite, name="confidentialite"),
    path("health/", views.health, name="health"),
    path("inscription/", views.inscription, name="inscription"),
    path("confirmer/<str:token>/", views.confirmer, name="confirmer"),
    path("attente/<slug:slug>/", views.attente, name="attente"),
    path("statut/<slug:slug>/", views.statut, name="statut"),
    path("awx/callback/", views.awx_callback, name="awx_callback"),
    path("connexion/", views.connexion, name="connexion"),
]
