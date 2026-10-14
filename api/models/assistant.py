"""
assistant.py

Réglages de l'assistant conversationnel (une seule ligne) : désactivé par
défaut ; l'utilisateur branche s'il le souhaite un LLM local (Ollama) ou un
service compatible OpenAI (OpenAI, Mistral, OpenRouter, LM Studio...).
La clé d'API est chiffrée avec la clé secrète de l'installation.
"""

from typing import Optional

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from middleware.database import Base


class AssistantSettings(Base):
    __tablename__ = "assistant_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # "ollama" : API native d'Ollama ; "openai" : toute API compatible /chat/completions
    provider: Mapped[str] = mapped_column(String(10), nullable=False, default="ollama")
    base_url: Mapped[str] = mapped_column(String(300), nullable=False, default="http://localhost:11434")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timeout_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=120.0)
    # Autorise l'assistant à lire les données de l'appli (aquariums, relevés, équipements)
    data_access: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
