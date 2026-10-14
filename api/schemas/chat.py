from pydantic import BaseModel
from typing import Optional

# Ce que le front (Quasar) envoie
class ChatRequest(BaseModel):
    prompt: str
    context: Optional[dict] = None # Peut envoyer les données des capteurs

# Ce que l'API renvoie
class ChatResponse(BaseModel):
    answer: str
    status: str = "success"