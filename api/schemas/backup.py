from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Part = Literal["photos", "icp", "documents", "certificates"]
Location = Literal["local", "external"]


class BackupInfo(BaseModel):
    filename: str
    location: Location = "local"
    size_bytes: int
    created_at: datetime
    label: str = "manual"
    label_text: str = "Manuelle"
    parts: list[str] = []
    # Archive antérieure au manifeste (base + tout le dossier uploads)
    legacy: bool = False
    valid: bool = True


class BackupSettingsBase(BaseModel):
    enabled: bool = False
    frequency: Literal["daily", "weekly"] = "daily"
    hour: int = Field(default=3, ge=0, le=23)
    weekday: int = Field(default=0, ge=0, le=6, description="0 = lundi")
    keep_count: int = Field(default=7, ge=1, le=365)
    include_photos: bool = True
    include_icp: bool = True
    include_documents: bool = True
    include_certificates: bool = True
    destination: Location = "local"
    external_path: Optional[str] = Field(default=None, max_length=300)


class BackupSettingsRead(BackupSettingsBase):
    last_run_at: Optional[datetime] = None
    last_status: Optional[str] = None
    last_message: Optional[str] = None
    next_run_at: Optional[datetime] = None
    # Dossier externe utilisable à l'instant (monté, accessible en écriture)
    external_ok: Optional[bool] = None
    external_error: Optional[str] = None


class BackupCreate(BaseModel):
    """Absent : contenu et destination des réglages."""

    parts: Optional[list[Part]] = None
    location: Optional[Location] = None


class DestinationTest(BaseModel):
    path: str = Field(min_length=1, max_length=300)
