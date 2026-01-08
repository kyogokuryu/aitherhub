from datetime import datetime

from sqlalchemy import ForeignKey, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.orm.base import Base, UUIDMixin


class Report(Base, UUIDMixin):
    __tablename__ = "reports"

    video_id: Mapped[str] = mapped_column(
        ForeignKey("videos.id"),
        nullable=False,
    )
    report_content: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
