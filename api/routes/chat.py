"""
Assistant IA (réservé aux licences qui l'incluent).
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from middleware.auth import min_role_required
from sqlalchemy.orm import Session

from schemas.chat import ChatResponse, ChatRequest
from middleware.database import get_db
from services.chat_assistant import AssistantDisabled, ask_assistant
from services.license import require_feature

logger = logging.getLogger(__name__)

# Assistant IA : réservé à une licence qui l'inclut
router = APIRouter(
    prefix="/chat", tags=["chat assistant"], dependencies=[Depends(require_feature("assistant")), Depends(min_role_required("consult"))]
)


@router.post("/", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest, db: Session = Depends(get_db)):
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt required")

    try:
        answer = await ask_assistant(request.prompt, db)
        return ChatResponse(answer=answer)
    except AssistantDisabled:
        raise HTTPException(status_code=409, detail="L'assistant n'est pas activé (Configuration › Assistant IA).")
    except Exception as e:
        logger.exception("Erreur dans l'assistant de chat")
        raise HTTPException(status_code=500, detail=f"Erreur de l'assistant: {str(e)}")