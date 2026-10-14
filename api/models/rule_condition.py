"""
Conditions d'une règle (capteur, opérateur, seuil, plage horaire).
"""

from datetime import time
from sqlalchemy import Integer, String, Float, Time, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from middleware.database import Base


class RuleCondition(Base):
    """Condition d'une règle : état d'un capteur, seuil ou plage horaire."""

    __tablename__ = "rule_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    rule_id: Mapped[int] = mapped_column(Integer, ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)

    condition_type: Mapped[str] = mapped_column(String, nullable=False)  # "state", "threshold", "time"

    sensor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=True)

    trigger_state: Mapped[str | None] = mapped_column(String, nullable=True)
    operator: Mapped[str | None] = mapped_column(String, nullable=True)  # ">", "<", "=="
    threshold_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    # Relations
    rule: Mapped["Rule"] = relationship(back_populates="conditions")
    sensor: Mapped["Sensor | None"] = relationship(back_populates="rule_conditions")