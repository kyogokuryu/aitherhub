from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Float, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm.base import Base, UUIDMixin, TimestampMixin


class PhaseGroupBestPhase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "phase_group_best_phases"

    phase_group_id: Mapped[str] = mapped_column(
        ForeignKey("phase_groups.id"),
        nullable=False,
    )
    phase_id: Mapped[str] = mapped_column(
        ForeignKey("phases.id"),
        nullable=False,
    )
    video_id: Mapped[str] = mapped_column(
        ForeignKey("videos.id"),
        nullable=False,
    )
    phase_index: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    view_velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    like_velocity: Mapped[float | None] = mapped_column(Float, nullable=True)
    like_per_viewer: Mapped[float | None] = mapped_column(Float, nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
