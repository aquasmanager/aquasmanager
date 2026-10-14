"""
Synchronisation du catalogue commun d'espèces.

Le catalogue commun vit dans le dépôt public de l'éditeur (catalogue.json),
servi par son hub (GET /v1/catalogue). Chaque installation le récupère
régulièrement et l'applique :

- espèce absente (par nom commun, sans tenir compte de la casse) : ajoutée ;
- fiche du catalogue commun (builtin) jamais modifiée ici : mise à jour ;
- fiche modifiée ici (customized) ou créée par l'utilisateur : jamais touchée ;
- fiche masquée (supprimée par l'utilisateur) : reste masquée ;
- espèce renommée : retrouvée par ses anciens noms (« previous_names ») ;
- une espèce retirée du catalogue reste dans les installations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from models.catalog_sync import CatalogSyncState
from models.species import CoralSpecies, FishSpecies, InvertebrateSpecies, PlantSpecies
from schemas.species import CoralSpeciesBase, FishSpeciesBase, InvertebrateSpeciesBase, PlantSpeciesBase
from services.species_catalog import _species_rows
from settings import settings

logger = logging.getLogger(__name__)

KINDS: dict[str, tuple[type, type[BaseModel]]] = {
    "fishes": (FishSpecies, FishSpeciesBase),
    "corals": (CoralSpecies, CoralSpeciesBase),
    "plants": (PlantSpecies, PlantSpeciesBase),
    "invertebrates": (InvertebrateSpecies, InvertebrateSpeciesBase),
}
SUPPORTED_FORMAT = 1


def _key(name: str) -> str:
    return " ".join(name.split()).lower()


def _plain(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


@dataclass
class SyncResult:
    added: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)
    invalid: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"{len(self.added)} ajoutée(s)", f"{len(self.updated)} mise(s) à jour"]
        if self.invalid:
            parts.append(f"{len(self.invalid)} ignorée(s) (fiche invalide)")
        return ", ".join(parts)


def apply_catalog(db: Session, catalog: dict) -> SyncResult:
    """Applique le catalogue reçu (voir le docstring du module). Valide chaque fiche
    avec le schéma de création de l'API : une fiche invalide est ignorée."""
    if catalog.get("format") != SUPPORTED_FORMAT:
        raise ValueError(f"Format de catalogue non pris en charge : {catalog.get('format')!r}")
    result = SyncResult()
    for kind, (model, schema) in KINDS.items():
        rows = db.query(model).all()
        by_name = {_key(row.common_name): row for row in rows}
        for entry in catalog.get(kind) or []:
            if not isinstance(entry, dict):
                continue
            previous = [n for n in entry.get("previous_names") or [] if isinstance(n, str)]
            data = {k: v for k, v in entry.items() if k != "previous_names"}
            try:
                values = schema(**data).model_dump()
            except ValidationError:
                result.invalid.append(f"{kind}:{data.get('common_name')}")
                continue
            row = by_name.get(_key(values["common_name"]))
            if row is None:
                # Renommée dans le catalogue commun : fiche retrouvée par un ancien nom
                row = next(
                    (r for n in previous if (r := by_name.get(_key(n))) is not None and r.builtin and not r.customized),
                    None,
                )
            if row is None:
                row = model(**values, builtin=True)
                db.add(row)
                by_name[_key(values["common_name"])] = row
                result.added.append(values["common_name"])
                continue
            if not row.builtin or row.customized:
                continue
            changed = False
            for name, value in values.items():
                if _plain(getattr(row, name)) != _plain(value):
                    setattr(row, name, value)
                    changed = True
            if changed:
                by_name[_key(values["common_name"])] = row
                result.updated.append(values["common_name"])
    db.commit()
    return result


def _state(db: Session) -> CatalogSyncState:
    state = db.get(CatalogSyncState, 1)
    if state is None:
        state = CatalogSyncState(id=1)
        db.add(state)
        db.flush()
    return state


def sync_enabled() -> bool:
    return bool(settings.hub_url) and settings.hub_url.lower() != "none"


def sync_catalog(db: Session, force: bool = False, client: Optional[httpx.Client] = None) -> CatalogSyncState:
    """Récupère le catalogue auprès du hub (sauf s'il n'a pas changé) et l'applique."""
    state = _state(db)
    state.checked_at = datetime.now()
    headers = {} if force or not state.etag else {"If-None-Match": state.etag}
    url = f"{settings.hub_url.rstrip('/')}/v1/catalogue"
    try:
        http = client or httpx.Client(timeout=20)
        try:
            response = http.get(url, headers=headers)
        finally:
            if client is None:
                http.close()
        if response.status_code == 304:
            state.error = None
            db.commit()
            return state
        response.raise_for_status()
        result = apply_catalog(db, response.json())
        state = _state(db)
        state.etag = response.headers.get("ETag")
        state.applied_at = datetime.now()
        state.result = result.summary()
        state.error = None
        if result.added or result.updated:
            logger.info("Catalogue commun : %s", state.result)
        if result.invalid:
            logger.warning("Catalogue commun : fiches ignorées %s", ", ".join(result.invalid))
    except Exception as exc:  # réseau, hub, format : on réessaiera au prochain passage
        db.rollback()
        state = _state(db)
        state.checked_at = datetime.now()
        state.error = f"{exc.__class__.__name__}: {exc}"[:500]
        logger.warning("Catalogue commun non synchronisé : %s", state.error)
    db.commit()
    return state


def mark_customized_builtins(db: Session) -> int:
    """Une seule fois, avant la première synchronisation : les fiches du jeu de
    départ déjà modifiées par l'utilisateur sont marquées pour ne pas être écrasées."""
    bundled = {(model, _key(row["common_name"])): row for model, row in _species_rows()}
    marked = 0
    for model, _schema in KINDS.values():
        for species in db.query(model).filter(model.builtin.is_(True), model.customized.is_(False)):
            reference = bundled.get((model, _key(species.common_name)))
            if reference is None or any(
                _plain(getattr(species, name)) != _plain(value) for name, value in reference.items()
            ):
                species.customized = True
                marked += 1
    db.commit()
    return marked
