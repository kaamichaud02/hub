"""Gestion minimale des comptes (remplace l'admin Django /admin/, qui
disparaît avec Django — c'était le seul moyen de créer un compte employé).
Réservé aux superusers (colonne auth_user.is_superuser, reprise telle quelle)."""
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select, func

from .timesheets_db import get_session_st
from .timesheets_models import AuthUser
from .timesheets_schemas import AdminUserCreate, CurrentUser
from .timesheets_auth import require_superuser, unique_username

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _serialize_user(user: AuthUser) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
    }


@router.get("/users")
def list_users(
    _: CurrentUser = Depends(require_superuser),
    session_st: Session = Depends(get_session_st),
):
    users = session_st.exec(select(AuthUser).order_by(AuthUser.email)).all()
    return [_serialize_user(u) for u in users]


@router.post("/users")
def create_user(
    payload: AdminUserCreate,
    _: CurrentUser = Depends(require_superuser),
    session_st: Session = Depends(get_session_st),
):
    existing = session_st.exec(
        select(AuthUser).where(func.lower(AuthUser.email) == payload.email.lower())
    ).first()
    if existing:
        raise HTTPException(409, "Un compte existe déjà avec cet email")

    base_username = payload.username or payload.email.split("@")[0]
    username = unique_username(session_st, base_username)

    user = AuthUser(
        password="!" + secrets.token_hex(20),  # convention Django "mot de passe inutilisable" — jamais vérifié, auth 100% déléguée au JWT Cloudflare
        last_login=None,
        is_superuser=payload.is_superuser,
        username=username,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        is_staff=False,
        is_active=True,
        date_joined=datetime.utcnow(),
    )
    session_st.add(user)
    try:
        session_st.commit()
    except IntegrityError:
        session_st.rollback()
        raise HTTPException(409, "Un compte existe déjà avec cet email ou ce nom d'utilisateur")
    session_st.refresh(user)
    return _serialize_user(user)
