"""
maintenance_task.py

Tâches d'entretien de l'aquarium (remplacer une cartouche osmoseur, la
résine déionisante, un test à réaliser...), ponctuelles ou récurrentes.
Chaque réalisation est journalisée (MaintenanceTaskCompletion) pour pouvoir
retrouver la dernière fois qu'une tâche a été faite.
"""

import enum
from typing import TYPE_CHECKING, Optional, List
from datetime import date, datetime

from sqlalchemy import Column, Date, Integer, String, Text, ForeignKey, TIMESTAMP, Enum, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from middleware.database import Base

if TYPE_CHECKING:
    from models.aquarium import Aquarium



class TaskRecurrence(enum.Enum):
    none = "none"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    custom_days = "custom_days"

    def __str__(self):
        return self.value


# Aquariums concernés par une tâche partagée (portée « multiple »)
maintenance_task_aquariums = Table(
    "maintenance_task_aquariums",
    Base.metadata,
    Column("task_id", Integer, ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), primary_key=True),
    Column("aquarium_id", Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), primary_key=True),
)


class MaintenanceTask(Base):
    """Tâche d'entretien, ponctuelle ou récurrente, d'un ou plusieurs aquariums."""

    __tablename__ = "maintenance_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    aquarium_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("aquariums.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Portée : « single », « multiple » (linked_aquariums) ou « all » (voir InventoryItem)
    scope: Mapped[str] = mapped_column(String(10), nullable=False, default="single")
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    recurrence: Mapped[TaskRecurrence] = mapped_column(
        Enum(TaskRecurrence, validate_strings=True), nullable=False, default=TaskRecurrence.none
    )
    # Utilisé seulement quand recurrence == custom_days.
    recurrence_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    last_completed_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    # Prochaine échéance : saisie manuellement à la création (utile pour une
    # tâche ponctuelle avec une date cible), puis recalculée automatiquement
    # à chaque complétion pour une tâche récurrente.
    next_due_at: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    # Jour (local) où le rappel « tâche du jour » a été envoyé : un seul par jour
    reminder_sent_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)

    completions: Mapped[List["MaintenanceTaskCompletion"]] = relationship(
        back_populates="task", cascade="all, delete-orphan", order_by="MaintenanceTaskCompletion.completed_at"
    )
    linked_aquariums: Mapped[List["Aquarium"]] = relationship(secondary=maintenance_task_aquariums)

    @property
    def aquarium_ids(self) -> list[int]:
        """Aquariums concernés ([] = tous)."""
        if self.scope == "all":
            return []
        if self.scope == "multiple":
            return sorted(a.id for a in self.linked_aquariums)
        return [self.aquarium_id]


class MaintenanceTaskCompletion(Base):
    """Réalisation d'une tâche d'entretien (date, note)."""

    __tablename__ = "maintenance_task_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    task_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("maintenance_tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    completed_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False, default=datetime.now)
    note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    task: Mapped["MaintenanceTask"] = relationship(back_populates="completions")
