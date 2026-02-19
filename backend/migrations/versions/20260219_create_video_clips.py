"""create video_clips table for TikTok clip generation

Revision ID: 20260219_video_clips
Revises: 20260219_product_names
Create Date: 2026-02-19 14:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260219_video_clips"
down_revision = "20260219_product_names"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "video_clips",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("video_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("phase_index", sa.Integer(), nullable=False),
        sa.Column("time_start", sa.Float(), nullable=False),
        sa.Column("time_end", sa.Float(), nullable=False),
        # Status: pending, processing, completed, failed
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        # Clip video blob URL (set after processing)
        sa.Column("clip_url", sa.Text(), nullable=True),
        # SAS token for download
        sa.Column("sas_token", sa.Text(), nullable=True),
        sa.Column("sas_expireddate", sa.DateTime(timezone=True), nullable=True),
        # Error message if failed
        sa.Column("error_message", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_index("ix_video_clips_video_id", "video_clips", ["video_id"])
    op.create_index("ix_video_clips_user_id", "video_clips", ["user_id"])
    op.create_index(
        "ix_video_clips_video_phase",
        "video_clips",
        ["video_id", "phase_index"],
    )


def downgrade():
    op.drop_index("ix_video_clips_video_phase", table_name="video_clips")
    op.drop_index("ix_video_clips_user_id", table_name="video_clips")
    op.drop_index("ix_video_clips_video_id", table_name="video_clips")
    op.drop_table("video_clips")
