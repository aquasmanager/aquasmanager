"""
assistant.py (routes)

Réglages de l'assistant IA : désactivé par défaut, l'administrateur branche
s'il le souhaite un LLM local (Ollama) ou un service compatible OpenAI.
La clé d'API n'est jamais renvoyée.
"""

import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.assistant import AssistantSettings
from schemas.assistant import (
    AssistantModels,
    AssistantProbe,
    AssistantSettingsRead,
    AssistantSettingsUpdate,
    AssistantStatus,
    AssistantTestResult,
)
from services.llm_provider import (
    LLMError,
    chat,
    connection_from,
    encrypt_key,
    get_assistant_settings,
    is_external,
    list_models,
)
from services.license import has_feature, require_feature

router = APIRouter(prefix="/assistant", tags=["chat assistant"], dependencies=[Depends(min_role_required("consult"))])
# Réglages et essais : licence « assistant » requise
ADMIN = [Depends(require_feature("assistant")), Depends(min_role_required("admin"))]


def _read(conf: AssistantSettings) -> dict:
    return {
        "enabled": conf.enabled,
        "provider": conf.provider,
        "base_url": conf.base_url,
        "model": conf.model,
        "api_key_set": bool(conf.api_key_encrypted),
        "timeout_seconds": conf.timeout_seconds,
        "data_access": conf.data_access,
    }


@router.get("/status", response_model=AssistantStatus)
def status(db: Session = Depends(get_db)):
    """Pour l'interface : afficher ou non le bouton de l'assistant."""
    conf = get_assistant_settings(db)
    # Sans licence « assistant » : bouton masqué, même si des réglages existent
    if not conf.enabled or not has_feature("assistant"):
        return {"enabled": False}
    return {"enabled": True, "provider": conf.provider, "model": conf.model, "external": is_external(conf.base_url)}


@router.get("/settings", response_model=AssistantSettingsRead, dependencies=ADMIN)
def read_settings(db: Session = Depends(get_db)):
    return _read(get_assistant_settings(db))


@router.put("/settings", response_model=AssistantSettingsRead, dependencies=ADMIN)
def update_settings(update: AssistantSettingsUpdate, db: Session = Depends(get_db)):
    conf = get_assistant_settings(db)
    for field, value in update.model_dump(exclude_unset=True).items():
        if field == "api_key":
            # "" efface la clé ; absent = inchangée
            conf.api_key_encrypted = encrypt_key(value.strip()) if value and value.strip() else None
        elif value is not None:
            setattr(conf, field, value.strip() if isinstance(value, str) else value)
    if conf.enabled and not conf.model:
        raise HTTPException(status_code=400, detail="Choisis un modèle avant d'activer l'assistant.")
    db.commit()
    db.refresh(conf)
    return _read(conf)


@router.post("/models", response_model=AssistantModels, dependencies=ADMIN)
async def available_models(probe: AssistantProbe, db: Session = Depends(get_db)):
    """Modèles proposés par le service (réglages du formulaire, pas encore enregistrés)."""
    conn = connection_from(get_assistant_settings(db), **probe.model_dump())
    try:
        return {"models": await list_models(conn)}
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/test", response_model=AssistantTestResult, dependencies=ADMIN)
async def test_connection(probe: AssistantProbe, db: Session = Depends(get_db)):
    conn = connection_from(get_assistant_settings(db), **probe.model_dump())
    started = time.monotonic()
    try:
        message = await chat(conn, [{"role": "user", "content": "Réponds seulement : OK"}], None)
    except LLMError as exc:
        return {"ok": False, "message": str(exc)}
    reply = (message.get("content") or "").strip()
    return {
        "ok": True,
        "message": f"Le modèle répond : « {reply[:120]} »" if reply else "Le modèle répond (réponse vide).",
        "seconds": round(time.monotonic() - started, 1),
    }
