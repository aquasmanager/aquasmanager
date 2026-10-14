from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Provider = Literal["ollama", "openai"]


def _check_url(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    value = value.strip().rstrip("/")
    if not value.lower().startswith(("http://", "https://")):
        raise ValueError("L'adresse doit commencer par http:// ou https://")
    return value


class AssistantStatus(BaseModel):
    enabled: bool
    provider: Optional[Provider] = None
    model: Optional[str] = None
    # Les questions et les données lues partent vers un service externe
    external: bool = False


class AssistantSettingsRead(BaseModel):
    enabled: bool
    provider: Provider
    base_url: str
    model: str
    api_key_set: bool = Field(description="Une clé est enregistrée (jamais renvoyée en clair)")
    timeout_seconds: float
    data_access: bool


class AssistantSettingsUpdate(BaseModel):
    """Champ absent = inchangé ; api_key "" = clé effacée."""

    enabled: Optional[bool] = None
    provider: Optional[Provider] = None
    base_url: Optional[str] = Field(default=None, max_length=300)
    model: Optional[str] = Field(default=None, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=500)
    timeout_seconds: Optional[float] = Field(default=None, ge=5, le=600)
    data_access: Optional[bool] = None

    _url = field_validator("base_url")(classmethod(lambda cls, v: _check_url(v)))


class AssistantProbe(BaseModel):
    """Réglages à essayer (test, liste des modèles) avant de les enregistrer ; absent = valeur enregistrée."""

    provider: Optional[Provider] = None
    base_url: Optional[str] = Field(default=None, max_length=300)
    model: Optional[str] = Field(default=None, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=500)

    _url = field_validator("base_url")(classmethod(lambda cls, v: _check_url(v)))


class AssistantTestResult(BaseModel):
    ok: bool
    message: str
    seconds: Optional[float] = None


class AssistantModels(BaseModel):
    models: list[str]
