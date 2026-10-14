"""
services/llm_provider.py

Connexion au modèle de langage choisi par l'utilisateur pour l'assistant :
- « ollama » : API native d'Ollama (/api/chat, /api/tags), en local ;
- « openai » : toute API compatible OpenAI (/chat/completions, /models) :
  OpenAI, Mistral, OpenRouter, LM Studio, llama.cpp server, vLLM...

AquasManager n'embarque aucun modèle. La clé d'API est chiffrée en base
(Fernet, clé dérivée de AQUAS_SECRET_KEY) et n'est jamais renvoyée au front.
"""

import base64
import hashlib
import ipaddress
import logging
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from models.assistant import AssistantSettings
from settings import settings

logger = logging.getLogger(__name__)

LOCAL_SUFFIXES = (".local", ".lan", ".home", ".internal", ".localdomain", ".cluster.local")


def _fernet() -> Fernet:
    digest = hashlib.sha256(f"aquas-assistant:{settings.secret_key}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_key(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_key(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        # Clé secrète de l'installation changée : la clé d'API est à ressaisir
        logger.warning("Clé d'API de l'assistant illisible (clé secrète changée ?)")
        return None


def get_assistant_settings(db: Session) -> AssistantSettings:
    conf = db.get(AssistantSettings, 1)
    if conf is None:
        conf = AssistantSettings(id=1)
        db.add(conf)
        db.commit()
        db.refresh(conf)
    return conf


def is_external(base_url: str) -> bool:
    """Service hors du réseau local : les questions et les données lues y sont envoyées."""
    try:
        host = (httpx.URL(base_url).host or "").strip("[]").lower()
    except httpx.InvalidURL:
        return True
    try:
        ip = ipaddress.ip_address(host)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        # Nom sans point (nom de service Docker, « localhost ») ou suffixe de réseau local
        return "." in host and not host.endswith(LOCAL_SUFFIXES)


@dataclass
class Connection:
    provider: str
    base_url: str
    model: str
    api_key: Optional[str]
    timeout: float

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}


def connection_from(conf: AssistantSettings, **override: Any) -> Connection:
    api_key = override.get("api_key")
    return Connection(
        provider=override.get("provider") or conf.provider,
        base_url=(override.get("base_url") or conf.base_url).rstrip("/"),
        model=override.get("model") if override.get("model") is not None else conf.model,
        api_key=api_key if api_key else decrypt_key(conf.api_key_encrypted),
        timeout=conf.timeout_seconds,
    )


class LLMError(Exception):
    """Erreur lisible par l'utilisateur (service injoignable, clé refusée...)."""


def _explain(exc: Exception) -> LLMError:
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return LLMError("Clé d'API refusée par le service.")
        if code == 404:
            return LLMError("Adresse ou modèle introuvable sur le service (vérifie l'adresse et le nom du modèle).")
        if code == 429:
            return LLMError("Le service limite les requêtes (quota ou crédit épuisé).")
        detail = exc.response.text[:200]
        return LLMError(f"Le service a répondu {code} : {detail}")
    if isinstance(exc, httpx.TimeoutException):
        return LLMError("Le service n'a pas répondu à temps.")
    if isinstance(exc, httpx.RequestError):
        return LLMError("Service injoignable : vérifie l'adresse et que le serveur est démarré.")
    return LLMError("Réponse inattendue du service.")


async def list_models(conn: Connection) -> list[str]:
    path = "/api/tags" if conn.provider == "ollama" else "/models"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{conn.base_url}{path}", headers=conn.headers)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise _explain(exc) from exc
    if conn.provider == "ollama":
        names = [m.get("name") or m.get("model") for m in data.get("models", [])]
    else:
        names = [m.get("id") for m in data.get("data", [])]
    return sorted(n for n in names if n)


async def chat(conn: Connection, messages: list[dict], tools: Optional[list[dict]]) -> dict:
    """Un tour de conversation ; renvoie le message de l'assistant au format OpenAI
    ({"role": "assistant", "content": ..., "tool_calls": [{"id", "function": {"name", "arguments"}}]})."""
    if not conn.model:
        raise LLMError("Aucun modèle choisi dans les réglages de l'assistant.")
    try:
        async with httpx.AsyncClient(timeout=conn.timeout) as client:
            if conn.provider == "ollama":
                body: dict[str, Any] = {"model": conn.model, "messages": messages, "stream": False}
                if tools:
                    body["tools"] = tools
                response = await client.post(f"{conn.base_url}/api/chat", json=body, headers=conn.headers)
                response.raise_for_status()
                message = response.json().get("message") or {}
            else:
                body = {"model": conn.model, "messages": messages}
                if tools:
                    body["tools"] = tools
                response = await client.post(f"{conn.base_url}/chat/completions", json=body, headers=conn.headers)
                response.raise_for_status()
                message = ((response.json().get("choices") or [{}])[0]).get("message") or {}
    except (httpx.HTTPError, ValueError) as exc:
        raise _explain(exc) from exc
    return message
