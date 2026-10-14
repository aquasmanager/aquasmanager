from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

# Réutilise l'enum du modèle plutôt que d'en dupliquer un second : les deux
# avaient fini par diverger (ex: "other_alive" ici vs "other_alives" côté
# modèle), cassant la sérialisation des photos pour ces entités.
from models.photo import PhotoType as Type

__all__ = ["Type", "PhotoBase", "PhotoCreate", "PhotoRead", "PhotoUpdate"]


class PhotoBase(BaseModel):
    entity_type: Type = Field(description="Entité", examples=["aquariums | corals | plants | fishes | invertebrates"])
    entity_id: int = Field(gt=0, description="ID de l'entitée")
    filename: str = Field(min_length=4, description="Nom du fichier", examples=["photo.jpg"])
    is_main: bool = Field(default=False, description="Si c'est vrai, il s'agit de la photo principale")


class PhotoCreate(PhotoBase):
    pass


class PhotoRead(PhotoBase):
    id: int = Field(gt=0, description="ID de la photo (auto généré)")
    created_at: datetime = Field(None, description="Date et heure de la photo")

    model_config = ConfigDict(from_attributes=True)


class PhotoUpdate(PhotoBase):
    entity_type: Type = Field(None, description="Entité")
    entity_id: int = Field(None, gt=0, description="ID de l'entitée")
    filename: str = Field(None, min_length=4, description="Nom du fichier", examples=["photo.jpg"])
    is_main: bool = Field(None, description="Si c'est vrai, il s'agit de la photo principale")
