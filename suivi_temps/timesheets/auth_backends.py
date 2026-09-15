"""
Backend d'authentification qui ne vérifie aucun mot de passe : l'identité
a déjà été prouvée par Cloudflare Access (Entra ID) avant que la requête
n'arrive ici. On se contente de retrouver le compte Django existant dont
l'email correspond exactement à celui du jeton Cloudflare.

Aucun compte n'est créé automatiquement : si l'email ne correspond à
aucun `User` existant, authenticate() renvoie None et l'utilisateur voit
la page "compte introuvable" (voir middleware.py) — un administrateur
doit créer le compte manuellement via /admin/.
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class CloudflareAccessBackend(ModelBackend):
    def authenticate(self, request, cf_email=None, **kwargs):
        if not cf_email:
            return None
        try:
            user = User.objects.get(email__iexact=cf_email)
        except User.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None
