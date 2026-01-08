from datetime import datetime

from sqlalchemy import ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm.base import Base, UUIDMixin, TimestampMixin


class PhaseGroup(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "phase_groups"

    phase_group_id: Mapped[int] = mapped_column(nullable=False)
    centroid: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
