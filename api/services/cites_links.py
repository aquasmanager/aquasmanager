"""
Lien automatique entre documents d'achat et coraux par numéro CITES.

Un document peut porter plusieurs numéros CITES. Quand un numéro est ajouté à un
document, les coraux portant ce numéro y sont liés ; quand un corail reçoit un
numéro CITES, il est lié aux documents qui le portent. Seuls les numéros
nouveaux déclenchent un lien : un lien retiré à la main ne revient pas.
Comparaison sans tenir compte de la casse, des espaces ni des tirets.

À l'inverse, un corail rattaché à un document en reçoit ce qui lui manque :
- le numéro CITES : le seul du document, sinon celui dont l'espèce a le même nom
  scientifique que le corail ;
- la provenance (« acquis auprès de ») : le fournisseur / cédant du document.
Ce qui est déjà saisi sur le corail n'est jamais remplacé.
"""

import re
from typing import Iterable

from sqlalchemy.orm import Session

from models.coral import Coral
from models.purchase_document import PurchaseDocument, PurchaseDocumentLink

MAX_NUMBERS = 50


def normalize(number: str) -> str:
    return re.sub(r"[\s\-_/.]", "", number or "").upper()


def split_numbers(raw: str | None) -> list[str]:
    """« A, B ; C » ou une ligne par numéro → [A, B, C], sans doublon."""
    seen, numbers = set(), []
    for part in re.split(r"[\n,;]+", raw or ""):
        part = part.strip()
        if part and normalize(part) not in seen:
            seen.add(normalize(part))
            numbers.append(part)
    return numbers


def join_numbers(numbers: Iterable[str]) -> str:
    return "\n".join(split_numbers("\n".join(numbers)))


def link_corals_to_document(db: Session, document: PurchaseDocument, numbers: Iterable[str]) -> int:
    keys = {normalize(n) for n in numbers if normalize(n)}
    if not keys:
        return 0
    linked = {link.entity_id for link in document.links if link.entity_type == "corals"}
    added = 0
    for coral in db.query(Coral).filter(Coral.cites != ""):
        if normalize(coral.cites) in keys and coral.id not in linked:
            document.links.append(PurchaseDocumentLink(entity_type="corals", entity_id=coral.id))
            linked.add(coral.id)
            added += 1
    return added


def link_documents_to_coral(db: Session, coral: Coral) -> int:
    key = normalize(coral.cites)
    if not key or coral.id is None:
        return 0
    added = 0
    for document in db.query(PurchaseDocument).filter(PurchaseDocument.cites_number != ""):
        if key in {normalize(n) for n in split_numbers(document.cites_number)} and not any(
            link.entity_type == "corals" and link.entity_id == coral.id for link in document.links
        ):
            document.links.append(PurchaseDocumentLink(entity_type="corals", entity_id=coral.id))
            added += 1
    return added


def _coral_cites_column_length() -> int:
    return Coral.__table__.c.cites.type.length or 30


def fill_corals_from_document(db: Session, document: PurchaseDocument, species_names: dict[str, str]) -> int:
    """Numéro CITES et provenance du document recopiés sur les coraux liés qui n'en ont pas.

    species_names : numéro normalisé → nom scientifique de l'espèce associée au numéro.
    """
    numbers = split_numbers(document.cites_number)
    supplier = (document.supplier or "").strip()
    coral_ids = [link.entity_id for link in document.links if link.entity_type == "corals"]
    if not coral_ids or not (numbers or supplier):
        return 0
    max_length = _coral_cites_column_length()
    filled = 0
    for coral in db.query(Coral).filter(Coral.id.in_(coral_ids)):
        if supplier and not (coral.acquired_from or "").strip():
            coral.acquired_from = supplier[:120]
            filled += 1
        if not numbers or (coral.cites or "").strip():
            continue
        if len(numbers) == 1:
            candidates = numbers
        else:
            name = (coral.scientific_name or "").strip().lower()
            candidates = [n for n in numbers if name and species_names.get(normalize(n), "").strip().lower() == name]
        if len(candidates) == 1 and len(candidates[0]) <= max_length:
            coral.cites = candidates[0]
            filled += 1
    return filled

