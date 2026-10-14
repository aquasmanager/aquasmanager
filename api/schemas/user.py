from enum import Enum
from typing import Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class Role(str, Enum):
    consult = "consult"
    seller = "seller"
    caretaker = "caretaker"
    user = "user"
    manager = "manager"
    admin = "admin"


class UserCreate(BaseModel):
    username: str = Field(min_length=4, description="Nom de l'utilisateur'", examples=["Robert"])
    password: str = Field(min_length=8, description="Mot de passe de l'utilisateur'", examples=["P@ssw0rd"])
    role: Role = Field(
        pattern="^(consult|seller|caretaker|user|manager|admin)$",
        description="Rôle de l'utilisateur",
        examples=["consult | user | manager | admin"],
    )
    must_change_password: bool = Field(True, description="Imposer un changement de mot de passe à la première connexion")


class UserRead(BaseModel):
    id: int = Field(gt=0, description="ID de l'utilisateur (auto généré)")
    username: str = Field(min_length=4, description="Nom de l'utilisateur'", examples=["Robert"])
    role: Role = Field(
        pattern="^(consult|seller|caretaker|user|manager|admin)$",
        description="Rôle de l'utilisateur",
        examples=["consult | user | manager | admin"],
    )
    must_change_password: bool = Field(description="L'utilisateur doit changer son mot de passe à la prochaine connexion")
    model_config = ConfigDict(from_attributes=True)


class LanguageChange(BaseModel):
    language: Literal["fr", "en"] = Field(description="Langue de l'interface")


class PasswordChange(BaseModel):
    current_password: str = Field(description="Mot de passe actuel", examples=["ChangeMe123!"])
    new_password: str = Field(min_length=8, description="Nouveau mot de passe", examples=["P@ssw0rd"])


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=4, description="Nouveau nom d'utilisateur")
    role: Optional[Role] = Field(None, description="Nouveau rôle")


class UserPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, description="Nouveau mot de passe", examples=["P@ssw0rd"])
    must_change_password: bool = Field(True, description="Imposer un changement de mot de passe à la prochaine connexion")
