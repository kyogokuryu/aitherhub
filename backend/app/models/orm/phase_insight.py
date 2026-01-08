from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm.base import Base, UUIDMixin, TimestampMixin


class PhaseInsight(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "phase_insights"

    video_id: Mapped[str] = mapped_column(
        ForeignKey("videos.id"),
        nullable=False,
    )
    phase_id: Mapped[str] = mapped_column(
        ForeignKey("phases.id"),
        nullable=False,
    )
    phase_index: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_group_id: Mapped[str] = mapped_column(
        ForeignKey("phase_groups.id"),
        nullable=False,
    )
    insight: Mapped[str | None] = mapped_column(Text, nullable=True)
    need_update: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
