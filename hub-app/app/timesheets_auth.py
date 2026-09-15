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
import secrets
from datetime import datetime
import jwt
from jwt import PyJWKClient
from fastapi import Request, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
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


def unique_username(session_st: Session, base: str) -> str:
    """Dérive un username unique à partir d'une base (email ou nom souhaité) —
    partagé entre la création auto (get_current_user) et la création manuelle
    (admin_routes.py) pour ne pas dupliquer la logique."""
    candidate = base
    suffix = 1
    while session_st.exec(select(AuthUser).where(AuthUser.username == candidate)).first():
        suffix += 1
        candidate = f"{base}{suffix}"
    return candidate


def get_or_create_user(session_st: Session, email: str) -> AuthUser:
    """Résout un email déjà vérifié par le JWT Cloudflare Access vers un
    compte auth_user, en le créant s'il n'existe pas encore. La sécurité
    (qui peut se connecter du tout) est déjà assurée par la policy
    Cloudflare Access — un email qui atteint ce point a déjà passé ce
    filtre, donc plus besoin de provisioning manuel côté hub. Toujours créé
    sans droits admin (is_superuser=False) ; nom vide au départ, la personne
    le configure elle-même via l'engrenage (PATCH /api/whoami) — rester
    admin reste un acte manuel (page Administration).

    Appelé à la fois par get_current_user (routes /api/timesheets,
    /api/recipes, /api/admin) et par GET /api/whoami dans main.py, pour que
    le compte existe dès la première visite plutôt que seulement après avoir
    touché une section qui l'exige."""
    user = session_st.exec(
        select(AuthUser).where(func.lower(AuthUser.email) == email.lower())
    ).first()
    if user:
        return user

    username = unique_username(session_st, email.split("@")[0])
    user = AuthUser(
        password="!" + secrets.token_hex(20),  # convention Django "mot de passe inutilisable" — jamais vérifié, auth 100% déléguée au JWT Cloudflare
        last_login=None,
        is_superuser=False,
        username=username,
        first_name="",
        last_name="",
        email=email,
        is_staff=False,
        is_active=True,
        date_joined=datetime.utcnow(),
    )
    session_st.add(user)
    try:
        session_st.commit()
    except IntegrityError:
        # Course entre deux requêtes simultanées de la même personne au tout
        # premier login — l'une des deux a gagné, on relit ce qu'elle a créé.
        session_st.rollback()
        user = session_st.exec(
            select(AuthUser).where(func.lower(AuthUser.email) == email.lower())
        ).first()
        if not user:
            raise
    else:
        session_st.refresh(user)
    return user


def get_current_user(
    request: Request,
    session_st: Session = Depends(get_session_st),
) -> CurrentUser:
    """Dépendance FastAPI : résout l'utilisateur courant à partir du JWT
    Cloudflare Access. Pas de token/JWT invalide -> 401 (Cloudflare Access
    est la seule barrière d'authentification — un email qui arrive ici a
    déjà été autorisé par sa policy, donc le compte auth_user est
    auto-créé s'il n'existe pas encore, plutôt que rejeté)."""
    email = get_verified_email(extract_token(request))
    if not email:
        raise HTTPException(status_code=401, detail="Identité Cloudflare manquante ou invalide")

    user = get_or_create_user(session_st, email)

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
