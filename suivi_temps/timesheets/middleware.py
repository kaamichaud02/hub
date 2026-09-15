"""
Remplace le login/signup Django par une authentification automatique
basée sur l'identité déjà vérifiée par Cloudflare Access.

À chaque requête :
1. Lit et valide le JWT Cloudflare Access (cf_access.get_verified_email)
2. Retrouve le compte Django correspondant à cet email
3. Connecte automatiquement l'utilisateur (aucun formulaire de login)

Si l'email ne correspond à aucun compte existant, affiche une page
invitant à demander la création d'un compte à un administrateur, plutôt
que de créer un compte automatiquement.
"""
from django.contrib.auth import authenticate, login
from django.shortcuts import render

from .cf_access import extract_token, get_verified_email

# Chemins qui ne doivent jamais être bloqués par ce middleware (santé, statique...)
EXEMPT_PREFIXES = ("/static/",)


class CloudflareAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(EXEMPT_PREFIXES):
            return self.get_response(request)

        token = extract_token(request)
        email = get_verified_email(token)

        if not email:
            return render(request, "timesheets/no_identity.html", status=401)

        if not request.user.is_authenticated or request.user.email.lower() != email.lower():
            user = authenticate(request, cf_email=email)
            if user is None:
                return render(
                    request,
                    "timesheets/account_not_found.html",
                    {"email": email},
                    status=403,
                )
            login(request, user, backend="timesheets.auth_backends.CloudflareAccessBackend")

        return self.get_response(request)
