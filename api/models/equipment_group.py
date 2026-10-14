"""
Groupes d'équipements pilotés ensemble (table d'association incluse).
"""

from typing import List
from sqlalchemy import String, ForeignKey, Table, Column, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from middleware.database import Base

group_equipment_association = Table(
    'group_equipment_association',
    Base.metadata,
    Column('group_id', Integer, ForeignKey('equipment_groups.id', ondelete="CASCADE"), primary_key=True),
    Column('equipment_id', Integer, ForeignKey('equipments.id', ondelete="CASCADE"), primary_key=True),
    extend_existing=True
)

class EquipmentGroup(Base):
    __tablename__ = 'equipment_groups'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    # Unique par aquarium de ses équipements (services/naming.py)
    name: Mapped[str] = mapped_column(String(30), index=True, nullable=False)

    # Relations
    equipments: Mapped[List["Equipment"]] = relationship(
        "Equipment",
        secondary=group_equipment_association,
        back_populates="groups"
    )

    # Règles qui ciblent ce groupe (supprimées avec lui)
    rules: Mapped[List["Rule"]] = relationship("Rule", back_populates="group", cascade="all, delete-orphan")