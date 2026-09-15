"""
Validation du jeton d'identité émis par Cloudflare Access.

Une fois qu'un utilisateur passe la SSO Entra ID au niveau de Cloudflare
Zero Trust (kaa.zone), Cloudflare transmet à l'origine un JWT signé dans
l'en-tête `Cf-Access-Jwt-Assertion` (et un cookie `CF_Authorization`).
Ce module vérifie la signature de ce jeton via les clés publiques (JWKS)
de l'équipe Cloudflare Access, et en extrait l'email de l'utilisateur.

Variables d'environnement requises :
- CF_ACCESS_TEAM_DOMAIN : ex. "kaazone.cloudflareaccess.com"
- CF_ACCESS_AUD         : le tag AUD (Application Audience) de cette
  application précise dans Cloudflare Zero Trust > Access > Applications
"""
import jwt
from jwt import PyJWKClient
from django.conf import settings

_jwk_client = None


def _get_jwk_client():
    global _jwk_client
    if _jwk_client is None:
        certs_url = f"https://{settings.CF_ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs"
        _jwk_client = PyJWKClient(certs_url)
    return _jwk_client


def get_verified_email(token):
    """Vérifie le JWT Cloudflare Access et renvoie l'email qu'il contient,
    ou None si le jeton est absent, invalide, expiré, ou signé pour une
    autre application (mauvais AUD).
    """
    if not token:
        return None

    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.CF_ACCESS_AUD,
        )
    except jwt.PyJWTError:
        return None

    return payload.get("email")


def extract_token(request):
    """Récupère le JWT Cloudflare Access depuis la requête (en-tête ou cookie)."""
    header_token = request.META.get("HTTP_CF_ACCESS_JWT_ASSERTION")
    if header_token:
        return header_token
    return request.COOKIES.get("CF_Authorization")
