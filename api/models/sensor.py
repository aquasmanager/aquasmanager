"""
Capteurs branchés sur un contrôleur (température, niveau, pH...).
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy import Integer, String, ForeignKey, TIMESTAMP, Float, Boolean
from middleware.database import Base



class Sensor(Base):
    """Capteur branché sur un contrôleur (sonde de température, flotteur de niveau)."""

    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(Integer, ForeignKey("aquariums.id"), nullable=False)
    controller_id: Mapped[int] = mapped_column(Integer, ForeignKey("controllers.id", ondelete="CASCADE"), nullable=False)
    pin_id: Mapped[int] = mapped_column(Integer, ForeignKey("controllers_pins.id", ondelete="RESTRICT"), nullable=False)

    # Unique par aquarium (vérifié par l'API) ; le nom technique reste unique partout
    name: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    technical_name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    # Nom technique encore utilisé par le firmware flashé quand technical_name a
    # changé depuis (renommage) ; vidé au flash suivant. NULL = firmware à jour.
    deployed_technical_name: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_inverted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)

    unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    last_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Dernière mesure reçue : sert à repérer une sonde muette (services/sensor_staleness.py)
    last_reading_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    # Adresse ROM 1-Wire (ex: DS18B20, format "0x1c00000ad1a67428") : permet
    # à plusieurs sondes de partager la même broche (bus 1-Wire), chacune
    # identifiée par son adresse plutôt que par la broche seule. Laissé vide,
    # ESPHome retombe sur un adressage par index (voir esphome_generator.py).
    address: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # Intervalle de lecture en secondes (capteurs analogiques/Dallas) ;
    # None = valeur par défaut du générateur ESPHome.
    interval: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # RELATIONS CORRIGÉES AU SINGULIER
    controller: Mapped["Controller"] = relationship(back_populates="sensors")
    aquarium: Mapped["Aquarium"] = relationship(back_populates="sensors")
    pin: Mapped["ControllerPin"] = relationship(back_populates="sensors")
    readings: Mapped[List["SensorReading"]] = relationship(back_populates="sensor", cascade="all, delete-orphan")
    rule_conditions: Mapped[list["RuleCondition"]] = relationship(back_populates="sensor", cascade="all, delete-orphan")

    # Pas de contrainte unique (controller_id, pin_id) au niveau DB : un bus
    # 1-Wire peut porter plusieurs sondes sur la même broche. L'unicité
    # "un seul capteur par broche" (cas non-1-Wire) et "une seule adresse
    # par broche 1-Wire" est validée côté route (routes/sensor.py).

def is_temperature_sensor(sensor) -> bool:
    # create_sensor stocke unit="°C" et type="sensor" : l'ancien test
    # unit == "temperature" ne correspondait jamais aux capteurs réels.
    unit = str(getattr(sensor, "unit", "") or "").lower()
    return unit in ("°c", "temperature") or getattr(sensor, "type", "") == "temperature"
