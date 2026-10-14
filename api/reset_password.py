"""
reset_password.py

Réinitialise le mot de passe d'un compte en cas d'oubli (ex. le seul admin).
À lancer dans le conteneur de l'API, qui a accès à la base :

    python reset_password.py admin            # mot de passe temporaire généré
    python reset_password.py admin -p 'xxx'   # mot de passe imposé

Le compte devra choisir un nouveau mot de passe à la connexion suivante, et
ses sessions ouvertes sont fermées.
"""

import argparse
import secrets
import sys

import bcrypt
from sqlalchemy.orm import Session

from middleware.database import SessionLocal
from models.refresh_token import RefreshToken
from models.user import User


def reset_password(db: Session, username: str, password: str | None = None) -> str:
    """Remplace le mot de passe de `username` et renvoie le mot de passe (généré ou fourni)."""
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise LookupError(f"Aucun compte « {username} »")
    password = password or secrets.token_urlsafe(12)
    user.password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    user.must_change_password = True
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id).delete()
    db.commit()
    return password


def main() -> int:
    parser = argparse.ArgumentParser(description="Réinitialise le mot de passe d'un compte AquasManager.")
    parser.add_argument("username", help="identifiant du compte (ex. admin)")
    parser.add_argument("-p", "--password", help="mot de passe à imposer (sinon généré)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        password = reset_password(db, args.username, args.password)
    except LookupError as exc:
        usernames = ", ".join(u for (u,) in db.query(User.username).order_by(User.username))
        print(f"{exc}. Comptes existants : {usernames or 'aucun'}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print(f"Mot de passe de « {args.username} » réinitialisé.")
    if not args.password:
        print(f"Mot de passe temporaire : {password}")
    print("Un nouveau mot de passe sera demandé à la connexion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
