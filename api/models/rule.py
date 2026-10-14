"""
Règles d'automatisation : conditions sur les capteurs -> action sur un
équipement ou un groupe, notification, interlock de sécurité.
"""

from sqlalchemy import Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from middleware.database import Base


class Rule(Base):
    """Règle d'automatisation : conditions et action (allumer, éteindre, notifier) sur un équipement ou un groupe."""

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    # Unique par aquarium de sa cible (services/naming.py)
    name: Mapped[str] = mapped_column(String, index=True, nullable=False)

    # "AND" ou "OR"
    match_type: Mapped[str] = mapped_column(String, default="AND", nullable=False)

    equipment_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equipments.id", ondelete="CASCADE"), nullable=True)

    # Cible : un équipement OU un groupe d'équipements
    group_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("equipment_groups.id", ondelete="CASCADE"), nullable=True)

    action: Mapped[str] = mapped_column(String, nullable=False)  # ex: "ON", "OFF", ou "NOTIFY"

    notification_channel: Mapped[str | None] = mapped_column(String, nullable=True)  # "telegram", "email"
    notification_message: Mapped[str | None] = mapped_column(String, nullable=True)  # "Attention, température trop haute !"

    max_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Interlock de sécurité (ex: niveau haut décante -> coupe osmolateur +
    # écumeur) : ne s'applique qu'aux règles action="OFF". Contrairement aux
    # règles normales, s'applique quel que soit le mode AUTO/MANUAL de
    # l'équipement cible et se relâche automatiquement quand la condition
    # redevient fausse (voir esphome_generator.py).
    is_safety_lock: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Moteur avancé : action inverse (ON <-> OFF) quand la condition redevient fausse
    revert_on_exit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relations
    conditions: Mapped[list["RuleCondition"]] = relationship(back_populates="rule", cascade="all, delete-orphan")
    equipment: Mapped["Equipment | None"] = relationship(back_populates="rules")
    group: Mapped["EquipmentGroup | None"] = relationship(back_populates="rules")