from django import forms
from django.contrib.auth.password_validation import validate_password

from . import slugs
from .models import Reservation


class InscriptionForm(forms.Form):
    nom = forms.CharField(label="Nom", max_length=80, widget=forms.TextInput(attrs={"autocomplete": "name", "autofocus": True, "required": True}))
    email = forms.EmailField(label="E-mail", widget=forms.EmailInput(attrs={"autocomplete": "email", "required": True}))
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput(attrs={"autocomplete": "new-password", "required": True}), strip=False)
    slug = forms.CharField(label="Nom de l'espace de travail", max_length=31, widget=forms.TextInput(attrs={"autocomplete": "off", "spellcheck": "false", "required": True}))

    def clean_nom(self):
        return " ".join(self.cleaned_data["nom"].split())

    def clean_slug(self):
        slug = slugs.normalize(self.cleaned_data["slug"])
        msg = slugs.problem(slug)
        if msg:
            raise forms.ValidationError(msg)
        if Reservation.active().filter(slug=slug).exists():
            raise forms.ValidationError("Ce nom est déjà pris.")
        return slug

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_password(self):
        pwd = self.cleaned_data["password"]
        validate_password(pwd)
        return pwd


class ConnexionForm(forms.Form):
    email = forms.EmailField(label="Votre e-mail")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
