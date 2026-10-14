from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from models.notification_settings import NotificationProvider


class NotificationSettingsRead(BaseModel):
    provider: NotificationProvider
    telegram_chat_id: Optional[str] = None
    telegram_bot_token_set: bool = Field(description="Un jeton de bot est enregistré (jamais renvoyé en clair)")
    ntfy_url: str
    ntfy_topic: Optional[str] = None
    ntfy_token_set: bool


class NotificationSettingsUpdate(BaseModel):
    """Champ absent = inchangé ; jeton "" = effacé."""

    provider: Optional[NotificationProvider] = None
    telegram_bot_token: Optional[str] = Field(default=None, max_length=200)
    telegram_chat_id: Optional[str] = Field(default=None, max_length=100)
    ntfy_url: Optional[str] = Field(default=None, max_length=300)
    ntfy_topic: Optional[str] = Field(default=None, max_length=100)
    ntfy_token: Optional[str] = Field(default=None, max_length=200)

    @field_validator("ntfy_url")
    @classmethod
    def check_url(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value.strip().lower().startswith(("http://", "https://")):
            raise ValueError("L'adresse du serveur ntfy doit commencer par http:// ou https://")
        return value.strip() if value else value

    @field_validator("ntfy_topic")
    @classmethod
    def check_topic(cls, value: Optional[str]) -> Optional[str]:
        if value and not all(c.isalnum() or c in "-_" for c in value):
            raise ValueError("Le topic ntfy ne peut contenir que lettres, chiffres, - et _")
        return value


class NotificationTestRequest(BaseModel):
    channel: Optional[Literal["telegram", "ntfy"]] = Field(
        default=None, description="Canal à tester ; par défaut, le ou les canaux actifs"
    )


class NotificationTestResult(BaseModel):
    results: dict[str, Optional[str]] = Field(description="Canal -> null si envoyé, sinon l'erreur")
