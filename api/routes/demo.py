"""
demo.py (routes)

Instance de démonstration : identifiants du compte de démo, affichés par la
page de connexion. 404 sur une installation normale.
"""

from fastapi import APIRouter, HTTPException

from settings import settings

router = APIRouter(prefix="/public/demo", tags=["public"])


@router.get("/")
def demo_info():
    if not settings.demo:
        raise HTTPException(status_code=404, detail="Pas une instance de démonstration.")
    return {
        "username": settings.demo_username,
        "password": settings.demo_password,
        "reset_hour": settings.demo_reset_hour,
        "timezone": settings.timezone,
    }
