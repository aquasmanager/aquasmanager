"""Réinitialisation du mot de passe en ligne de commande (reset_password.py)."""

import pytest

from middleware.database import SessionLocal
from reset_password import reset_password


def test_reset_password_forces_change_and_closes_sessions(client, api, uid):
    username = f"oubli{uid}"
    api.post("/register", {"username": username, "password": "Ancien-mdp-123", "role": "user"}, code=201)
    assert client.post("/login", data={"username": username, "password": "Ancien-mdp-123"}).status_code == 200
    assert client.cookies  # jeton de rafraîchissement posé

    db = SessionLocal()
    try:
        password = reset_password(db, username)
    finally:
        db.close()

    assert client.post("/login", data={"username": username, "password": "Ancien-mdp-123"}).status_code == 400
    login = client.post("/login", data={"username": username, "password": password})
    assert login.status_code == 200, login.text
    assert login.json()["must_change_password"] is True


def test_reset_password_unknown_user():
    db = SessionLocal()
    try:
        with pytest.raises(LookupError):
            reset_password(db, "personne-de-ce-nom")
    finally:
        db.close()
