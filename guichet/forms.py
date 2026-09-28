from django import forms
from django.contrib.auth.password_validation import validate_password

from . import slugs
from .models import Reservation


class InscriptionForm(forms.Form):
    slug = forms.CharField(label="Nom de votre espace", max_length=31)
    email = forms.EmailField(label="Votre e-mail")
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(label="Mot de passe (confirmation)", widget=forms.PasswordInput, strip=False)

    def __init__(self, *args, platform_domain="", **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].help_text = f"Votre adresse sera https://<nom>.{platform_domain}/"

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

    def clean(self):
        data = super().clean()
        if data.get("password") and data.get("password2") and data["password"] != data["password2"]:
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        return data


class ConnexionForm(forms.Form):
    email = forms.EmailField(label="Votre e-mail")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
