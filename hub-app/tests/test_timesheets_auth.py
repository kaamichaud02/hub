"""Scénarios pour la dépendance FastAPI get_current_user : email connu -> OK,
email inconnu mais vérifié par Cloudflare Access -> compte auto-créé (la
policy Cloudflare Access est la seule barrière d'authentification), pas de
jeton -> 401.
"""
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException

from app import timesheets_auth
from app.timesheets_models import AuthUser


def _fake_request():
    req = MagicMock()
    req.headers.get.return_value = None
    req.cookies.get.return_value = "some-jwt"
    return req


def _fake_session(first_result):
    session = MagicMock()
    session.exec.return_value.first.return_value = first_result
    return session


def test_known_email_resolves_user(monkeypatch):
    monkeypatch.setattr(timesheets_auth, "get_verified_email", lambda token: "kaamichaud02@outlook.com")
    user_row = AuthUser(
        id=1, password="!x", is_superuser=True, username="kaamichaud02",
        first_name="Jean-François", last_name="Chaudron", email="kaamichaud02@outlook.com",
        is_staff=False, is_active=True, date_joined=None,
    )
    session = _fake_session(user_row)

    result = timesheets_auth.get_current_user(_fake_request(), session)

    assert result.email == "kaamichaud02@outlook.com"
    assert result.is_superuser is True


def test_unknown_email_auto_creates_user(monkeypatch):
    # Aucun compte existant (ni pour l'email, ni collision de username) —
    # simule ce qu'une vraie session ferait : refresh() peuple l'id après commit.
    monkeypatch.setattr(timesheets_auth, "get_verified_email", lambda token: "nouveau@example.com")
    session = _fake_session(None)
    session.refresh = MagicMock(side_effect=lambda obj: setattr(obj, "id", 42))

    result = timesheets_auth.get_current_user(_fake_request(), session)

    assert result.email == "nouveau@example.com"
    assert result.is_superuser is False  # jamais admin à la création automatique
    assert result.first_name == ""
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_no_token_returns_401(monkeypatch):
    monkeypatch.setattr(timesheets_auth, "get_verified_email", lambda token: None)
    session = _fake_session(None)

    with pytest.raises(HTTPException) as exc_info:
        timesheets_auth.get_current_user(_fake_request(), session)

    assert exc_info.value.status_code == 401
