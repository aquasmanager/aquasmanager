"""
dosing.py (routes)

Calculateur de dosage : produits (effet d'une dose sur un paramètre), produits
génériques prêts à l'emploi, et application d'un dosage calculé dans
l'interface (tâches jour par jour, stock décompté, note au journal).
"""

from datetime import datetime, timedelta
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from middleware.auth import CARE_ROLES, min_role_required
from middleware.database import get_db
from models.aquarium import Aquarium
from models.dosing import DosingProduct
from models.inventory import InventoryItem, InventoryMovement
from models.maintenance_task import MaintenanceTask, TaskRecurrence
from services import journal

router = APIRouter(prefix="/dosing", tags=["Dosing"], dependencies=[Depends(min_role_required("consult"))])
WRITE = [Depends(min_role_required("user"))]

# Produits génériques (valeurs théoriques calculées à partir des masses molaires) :
# hausse pour 1 g dans 100 L
PRESETS = [
    {"name": "Bicarbonate de sodium (NaHCO₃)", "parameter": "KH", "dose_amount": 1, "dose_unit": "g",
     "raises": 0.33, "per_volume_l": 100, "unit": "°dKH"},
    {"name": "Carbonate de sodium (Na₂CO₃)", "parameter": "KH", "dose_amount": 1, "dose_unit": "g",
     "raises": 0.53, "per_volume_l": 100, "unit": "°dKH"},
    {"name": "Chlorure de calcium dihydraté (CaCl₂·2H₂O)", "parameter": "Ca", "dose_amount": 1, "dose_unit": "g",
     "raises": 2.73, "per_volume_l": 100, "unit": "mg/l"},
    {"name": "Chlorure de magnésium hexahydraté (MgCl₂·6H₂O)", "parameter": "Mg", "dose_amount": 1, "dose_unit": "g",
     "raises": 1.2, "per_volume_l": 100, "unit": "mg/l"},
    {"name": "Nitrate de potassium (KNO₃)", "parameter": "NO3", "dose_amount": 1, "dose_unit": "g",
     "raises": 6.1, "per_volume_l": 100, "unit": "mg/l"},
    {"name": "Phosphate monopotassique (KH₂PO₄)", "parameter": "PO4", "dose_amount": 1, "dose_unit": "g",
     "raises": 6.98, "per_volume_l": 100, "unit": "mg/l"},
]


def _salt(name: str, parameter: str, element_percent: float) -> dict:
    """Sel pur d'oligo-élément : teneur en élément (% en masse) → hausse pour 1 g dans 100 L (mg/l).
    En pratique on en fait une solution mère (ex. 1 g dans 1 L d'eau osmosée)."""
    return {"name": name, "parameter": parameter, "dose_amount": 1, "dose_unit": "g",
            "raises": round(element_percent * 10 / 100, 4), "per_volume_l": 100, "unit": "mg/l",
            "concentration": element_percent, "concentration_unit": "%"}


# Teneur en élément calculée à partir des masses molaires
PRESETS += [
    _salt("Chlorure de manganèse tétrahydraté (MnCl₂·4H₂O)", "Mn", 27.76),
    _salt("Iodure de potassium (KI)", "I", 76.45),
    _salt("Chlorure de strontium hexahydraté (SrCl₂·6H₂O)", "Sr", 32.86),
    _salt("Chlorure de potassium (KCl)", "K", 52.45),
    _salt("Acide borique (H₃BO₃)", "B", 17.48),
    _salt("Sulfate de zinc heptahydraté (ZnSO₄·7H₂O)", "Zn", 22.74),
    _salt("Chlorure de fer(III) hexahydraté (FeCl₃·6H₂O)", "Fe", 20.66),
    _salt("Chlorure de lithium (LiCl)", "Li", 16.37),
    _salt("Molybdate de sodium dihydraté (Na₂MoO₄·2H₂O)", "Mo", 39.66),
]


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    brand: Optional[str] = Field(default=None, max_length=60)
    parameter: str = Field(min_length=1, max_length=30)
    dose_amount: float = Field(gt=0, le=100000)
    dose_unit: str = Field(min_length=1, max_length=20)
    raises: float = Field(gt=0, le=100000)
    per_volume_l: float = Field(gt=0, le=100000)
    inventory_item_id: Optional[int] = Field(default=None, gt=0)
    # Concentration du produit (mg/mL, g/L, mg/L ou %), si c'est ainsi qu'il est décrit
    concentration: Optional[float] = Field(default=None, gt=0, le=1000000)
    concentration_unit: Optional[Literal["mg/mL", "g/L", "mg/L", "%"]] = None

    @field_validator("brand")
    @classmethod
    def _blank_brand(cls, value: Optional[str]) -> Optional[str]:
        return (value or "").strip() or None


class ProductRead(ProductIn):
    id: int

    model_config = ConfigDict(from_attributes=True)


class DosingApply(BaseModel):
    aquarium_id: int = Field(gt=0)
    product_id: int = Field(gt=0)
    # Quantité totale (unité du produit), répartie sur `days` jours
    total: float = Field(gt=0, le=100000)
    days: int = Field(default=1, ge=1, le=14)
    # Pour la note du journal : valeur mesurée et objectif
    current: Optional[float] = None
    target: Optional[float] = None
    create_tasks: bool = True
    consume_stock: bool = False
    add_journal: bool = True


def _fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _quantity(value: float, unit: str) -> str:
    """Quantité lisible : 1 250 mL -> 1,25 L ; 2 500 g -> 2,5 kg."""
    bigger = {"ml": "L", "g": "kg"}.get(unit.strip().lower())
    if bigger and value >= 1000:
        return f"{_fmt(value / 1000)} {bigger}"
    return f"{_fmt(value)} {unit}"


def _label(product: DosingProduct) -> str:
    return f"{product.name} ({product.brand})" if product.brand else product.name


@router.get("/presets")
def presets():
    return PRESETS


@router.get("/products", response_model=List[ProductRead])
def list_products(db: Session = Depends(get_db)):
    return db.query(DosingProduct).order_by(DosingProduct.parameter, DosingProduct.name).all()


def _check_item(db: Session, item_id: Optional[int]) -> None:
    if item_id and db.get(InventoryItem, item_id) is None:
        raise HTTPException(status_code=404, detail="Article du stock introuvable.")


@router.post("/products", response_model=ProductRead, status_code=status.HTTP_201_CREATED, dependencies=WRITE)
def create_product(payload: ProductIn, db: Session = Depends(get_db)):
    _check_item(db, payload.inventory_item_id)
    product = DosingProduct(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.put("/products/{product_id}", response_model=ProductRead, dependencies=WRITE)
def update_product(product_id: int, payload: ProductIn, db: Session = Depends(get_db)):
    product = db.get(DosingProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Produit introuvable.")
    _check_item(db, payload.inventory_item_id)
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=WRITE)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.get(DosingProduct, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Produit introuvable.")
    db.delete(product)
    db.commit()


@router.post("/apply", dependencies=[Depends(min_role_required("user", also=CARE_ROLES))])
def apply_dosing(payload: DosingApply, db: Session = Depends(get_db)):
    """Dosage calculé : une tâche par jour, stock décompté, note au journal."""
    aquarium = db.get(Aquarium, payload.aquarium_id)
    product = db.get(DosingProduct, payload.product_id)
    if aquarium is None or product is None:
        raise HTTPException(status_code=404, detail="Aquarium ou produit introuvable.")
    per_day = payload.total / payload.days
    amount = f"{_quantity(per_day, product.dose_unit)} de {_label(product)}"
    tasks = []
    if payload.create_tasks:
        start = datetime.now().replace(minute=0, second=0, microsecond=0)
        for day in range(payload.days):
            suffix = f" ({day + 1}/{payload.days})" if payload.days > 1 else ""
            task = MaintenanceTask(
                aquarium_id=aquarium.id,
                title=f"Doser {amount}{suffix}"[:100],
                description=f"Dosage {product.parameter} calculé le {start.strftime('%d/%m/%Y')}",
                recurrence=TaskRecurrence.none,
                next_due_at=start + timedelta(days=day),
            )
            db.add(task)
            tasks.append(task)
    stock_left = None
    if payload.consume_stock and product.inventory_item_id:
        item = db.get(InventoryItem, product.inventory_item_id)
        if item:
            db.add(InventoryMovement(item_id=item.id, delta=-payload.total,
                                     note=f"Dosage {product.parameter} ({aquarium.name})"))
            item.quantity = round(item.quantity - payload.total, 6)
            stock_left = item.quantity
    if payload.add_journal:
        change = ""
        if payload.current is not None and payload.target is not None:
            change = f" ({product.parameter} {_fmt(payload.current)} → {_fmt(payload.target)})"
        spread = f" par jour pendant {payload.days} jours" if payload.days > 1 else ""
        journal.add(db, aquarium.id, "dosing", f"Dosage : {amount}{spread}{change}")
    db.commit()
    return {"tasks": len(tasks), "per_day": per_day, "stock_left": stock_left}
