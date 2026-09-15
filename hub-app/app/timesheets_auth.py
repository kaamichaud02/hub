"""
Validation du jeton d'identité émis par Cloudflare Access.

Port de suivi_temps/timesheets/cf_access.py + auth_backends.py + middleware.py
vers des dépendances FastAPI. Une fois qu'un utilisateur passe la SSO Entra ID
au niveau de Cloudflare Zero Trust (kaa.zone), Cloudflare transmet à l'origine
un JWT signé dans l'en-tête `Cf-Access-Jwt-Assertion` (et un cookie
`CF_Authorization`). Ce module vérifie la signature de ce jeton via les clés
publiques (JWKS) de l'équipe Cloudflare Access, et résout l'email vérifié vers
un compte `auth_user` existant.

Variables d'environnement requises :
- CF_ACCESS_TEAM_DOMAIN : ex. "kaazone.cloudflareaccess.com"
- CF_ACCESS_AUD         : AUD tag de l'application Cloudflare Access qui
  protège le hub (Zero Trust > Access > Applications)
"""
import os
import jwt
from jwt import PyJWKClient
from fastapi import Request, Depends, HTTPException
from sqlmodel import Session, select, func

from .timesheets_db import get_session_st
from .timesheets_models import AuthUser
from .timesheets_schemas import CurrentUser

CF_ACCESS_TEAM_DOMAIN = os.getenv("CF_ACCESS_TEAM_DOMAIN", "")
CF_ACCESS_AUD = os.getenv("CF_ACCESS_AUD", "")

_jwk_client = None


def _get_jwk_client() -> PyJWKClient:
    global _jwk_client
    if _jwk_client is None:
        certs_url = f"https://{CF_ACCESS_TEAM_DOMAIN}/cdn-cgi/access/certs"
        _jwk_client = PyJWKClient(certs_url)
    return _jwk_client


def get_verified_email(token: str | None) -> str | None:
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
            audience=CF_ACCESS_AUD,
        )
    except jwt.PyJWTError:
        return None

    return payload.get("email")


def extract_token(request: Request) -> str | None:
    """Récupère le JWT Cloudflare Access depuis la requête (en-tête ou cookie)."""
    header_token = request.headers.get("Cf-Access-Jwt-Assertion")
    if header_token:
        return header_token
    return request.cookies.get("CF_Authorization")


def get_current_user(
    request: Request,
    session_st: Session = Depends(get_session_st),
) -> CurrentUser:
    """Dépendance FastAPI : résout l'utilisateur courant à partir du JWT
    Cloudflare Access. Pas de token/JWT invalide -> 401. Email vérifié mais
    absent de auth_user -> 403 (jamais de création automatique de compte,
    un admin doit l'ajouter via la section Administration)."""
    email = get_verified_email(extract_token(request))
    if not email:
        raise HTTPException(status_code=401, detail="Identité Cloudflare manquante ou invalide")

    user = session_st.exec(
        select(AuthUser).where(func.lower(AuthUser.email) == email.lower())
    ).first()
    if not user:
        raise HTTPException(status_code=403, detail="Compte non trouvé")

    return CurrentUser(
        id=user.id,
        email=user.email,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_superuser=user.is_superuser,
    )


def require_superuser(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    return user
