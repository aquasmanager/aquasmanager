"""
species.py (routes)

Catalogue d'espèces : /species/{fishes|corals|plants|invertebrates}. Avec
?aquarium_id=, chaque espèce porte des avertissements calculés pour cet
aquarium (type d'eau, volume, compatibilité récif...).
"""

from dataclasses import dataclass
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from middleware.auth import min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium, AquariumWaterType
from models.catalog_sync import CatalogSyncState
from models.species import CoralSpecies, FishSpecies, InvertebrateSpecies, PlantSpecies
from services.catalog_sync import sync_catalog, sync_enabled
from schemas.species import (
    CoralSpeciesBase,
    CoralSpeciesRead,
    CoralSpeciesUpdate,
    FishSpeciesBase,
    FishSpeciesRead,
    FishSpeciesUpdate,
    InvertebrateSpeciesBase,
    InvertebrateSpeciesRead,
    InvertebrateSpeciesUpdate,
    PlantSpeciesBase,
    PlantSpeciesRead,
    PlantSpeciesUpdate,
)

router = APIRouter(prefix="/species", tags=["species"], dependencies=[Depends(min_role_required("consult"))])

AGGRESSIVE_CORAL_LEVEL = 7


def _water_warning(species_water: AquariumWaterType, aquarium: Aquarium) -> list[str]:
    if species_water == aquarium.water_type:
        return []
    if species_water == AquariumWaterType.sea:
        return ["Espèce marine : aquarium d'eau douce."]
    return ["Espèce d'eau douce : aquarium d'eau de mer."]


def _volume_warning(min_volume: int, aquarium: Aquarium) -> list[str]:
    if aquarium.volume >= min_volume:
        return []
    return [f"Volume minimal conseillé {min_volume} L (bac : {aquarium.volume} L)."]


def fish_warnings(species: FishSpecies, aquarium: Aquarium) -> list[str]:
    warnings = _water_warning(species.water_type, aquarium) + _volume_warning(species.min_volume, aquarium)
    if species.water_type == AquariumWaterType.sea and not species.reef_safe:
        warnings.append("Pas compatible récif : risque pour les coraux ou les invertébrés.")
    return warnings


def coral_warnings(species: CoralSpecies, aquarium: Aquarium) -> list[str]:
    warnings = _water_warning(AquariumWaterType.sea, aquarium)
    if species.aggressiveness_level >= AGGRESSIVE_CORAL_LEVEL:
        warnings.append("Corail agressif : prévoir de l'espace autour.")
    return warnings


def plant_warnings(species: PlantSpecies, aquarium: Aquarium) -> list[str]:
    return _water_warning(AquariumWaterType.pure, aquarium)


def invertebrate_warnings(species: InvertebrateSpecies, aquarium: Aquarium) -> list[str]:
    warnings = _water_warning(species.water_type, aquarium) + _volume_warning(species.min_volume, aquarium)
    if species.water_type == AquariumWaterType.sea and not species.reef_safe:
        warnings.append("Pas compatible récif : risque pour les coraux.")
    return warnings


@dataclass(frozen=True)
class Catalog:
    model: type
    create_schema: type[BaseModel]
    update_schema: type[BaseModel]
    read_schema: type[BaseModel]
    warnings: Callable
    range_pairs: tuple[tuple[str, str], ...] = ()
    # Type d'eau des espèces : colonne water_type, sinon valeur fixe (coraux : mer, plantes : douce)
    fixed_water_type: Optional[AquariumWaterType] = None


CATALOGS = {
    "fishes": Catalog(FishSpecies, FishSpeciesBase, FishSpeciesUpdate, FishSpeciesRead, fish_warnings),
    "corals": Catalog(
        CoralSpecies, CoralSpeciesBase, CoralSpeciesUpdate, CoralSpeciesRead, coral_warnings,
        (("light_min", "light_max"), ("brewing_min", "brewing_max")), AquariumWaterType.sea,
    ),
    "plants": Catalog(
        PlantSpecies, PlantSpeciesBase, PlantSpeciesUpdate, PlantSpeciesRead, plant_warnings,
        (("light_min", "light_max"), ("temperature_min", "temperature_max")), AquariumWaterType.pure,
    ),
    "invertebrates": Catalog(
        InvertebrateSpecies, InvertebrateSpeciesBase, InvertebrateSpeciesUpdate, InvertebrateSpeciesRead,
        invertebrate_warnings,
    ),
}


def _aquarium(db: Session, aquarium_id: Optional[int]) -> Optional[Aquarium]:
    if aquarium_id is None:
        return None
    aquarium = db.query(Aquarium).filter(Aquarium.id == aquarium_id).first()
    if not aquarium:
        raise HTTPException(status_code=404, detail="Aquarium introuvable")
    return aquarium


def _get_or_404(db: Session, model, species_id: int):
    species = db.query(model).filter(model.id == species_id, model.hidden.is_(False)).first()
    if not species:
        raise HTTPException(status_code=404, detail="Espèce introuvable")
    return species


def _find_by_common_name(db: Session, model, common_name: str, exclude_id: Optional[int] = None):
    """Le catalogue est identifié par le nom commun (sans tenir compte de la casse) :
    plusieurs variétés peuvent partager un nom scientifique."""
    query = db.query(model).filter(func.lower(model.common_name) == common_name.strip().lower())
    if exclude_id is not None:
        query = query.filter(model.id != exclude_id)
    return query.first()


def _read(catalog: Catalog, species, aquarium: Optional[Aquarium]) -> dict:
    data = catalog.read_schema.model_validate(species).model_dump()
    data["warnings"] = catalog.warnings(species, aquarium) if aquarium else []
    return data


def _register(kind: str, catalog: Catalog) -> None:
    model = catalog.model

    @router.get(f"/{kind}", response_model=list[catalog.read_schema], name=f"list_{kind}_species")
    def list_species(
        q: Optional[str] = Query(None, description="Recherche sur le nom courant ou scientifique"),
        aquarium_id: Optional[int] = Query(None, description="Calcule les avertissements pour cet aquarium"),
        compatible_only: bool = Query(False, description="Avec aquarium_id : seulement les espèces du même type d'eau"),
        db: Session = Depends(get_db),
    ):
        aquarium = _aquarium(db, aquarium_id)
        query = db.query(model).filter(model.hidden.is_(False))
        if compatible_only and aquarium is not None:
            if catalog.fixed_water_type is None:
                query = query.filter(model.water_type == aquarium.water_type)
            elif catalog.fixed_water_type != aquarium.water_type:
                return []
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            query = query.filter(or_(model.common_name.ilike(pattern), model.scientific_name.ilike(pattern)))
        return [_read(catalog, s, aquarium) for s in query.order_by(model.common_name).all()]

    @router.post(
        f"/{kind}",
        response_model=catalog.read_schema,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(min_role_required("user"))],
        name=f"create_{kind}_species",
    )
    def create_species(species_in: catalog.create_schema, db: Session = Depends(get_db)):
        data = species_in.model_dump()
        species = _find_by_common_name(db, model, data["common_name"])
        if species is not None and not species.hidden:
            raise HTTPException(status_code=409, detail="Cette espèce existe déjà dans le catalogue.")
        if species is None:
            species = model(**data, builtin=False)
            db.add(species)
        else:
            # Recréer une espèce supprimée (masquée) la réactive avec les nouvelles valeurs.
            for field, value in data.items():
                setattr(species, field, value)
            species.hidden = False
        db.commit()
        db.refresh(species)
        return _read(catalog, species, None)

    @router.patch(
        f"/{kind}/{{species_id}}",
        response_model=catalog.read_schema,
        dependencies=[Depends(min_role_required("user"))],
        name=f"update_{kind}_species",
    )
    def update_species(species_id: int, update: catalog.update_schema, db: Session = Depends(get_db)):
        species = _get_or_404(db, model, species_id)
        data = update.model_dump(exclude_unset=True)
        if "common_name" in data and _find_by_common_name(db, model, data["common_name"], species_id):
            raise HTTPException(status_code=409, detail="Ce nom est déjà utilisé dans le catalogue.")
        changed = False
        for field, value in data.items():
            if getattr(species, field) != value:
                setattr(species, field, value)
                changed = True
        # Fiche du catalogue commun modifiée ici : la synchronisation ne l'écrasera plus
        if changed and species.builtin:
            species.customized = True
        if any(getattr(species, low) > getattr(species, high) for low, high in catalog.range_pairs):
            db.rollback()
            raise HTTPException(status_code=422, detail="Le minimum doit être inférieur ou égal au maximum.")
        db.commit()
        db.refresh(species)
        return _read(catalog, species, None)

    @router.delete(
        f"/{kind}/{{species_id}}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(min_role_required("manager"))],
        name=f"delete_{kind}_species",
    )
    def delete_species(species_id: int, db: Session = Depends(get_db)):
        species = _get_or_404(db, model, species_id)
        # Une espèce du jeu de départ est masquée : sinon elle serait réinsérée au démarrage.
        if species.builtin:
            species.hidden = True
        else:
            db.delete(species)
        db.commit()



@router.get("/catalog/status", name="species_catalog_status")
def catalog_status(db: Session = Depends(get_db)):
    """Synchronisation du catalogue commun : activée ou non, dernier passage, résultat."""
    state = db.get(CatalogSyncState, 1)
    return {
        "enabled": sync_enabled(),
        "checked_at": state.checked_at if state else None,
        "applied_at": state.applied_at if state else None,
        "result": state.result if state else None,
        "error": state.error if state else None,
    }


@router.post(
    "/catalog/sync",
    dependencies=[Depends(min_role_required("manager"))],
    name="species_catalog_sync",
)
def catalog_sync_now(db: Session = Depends(get_db)):
    """Synchronise tout de suite le catalogue commun (sans attendre le passage automatique)."""
    if not sync_enabled():
        raise HTTPException(status_code=409, detail="Synchronisation du catalogue commun désactivée.")
    sync_catalog(db, force=True)
    return catalog_status(db)

for _kind, _catalog in CATALOGS.items():
    _register(_kind, _catalog)
