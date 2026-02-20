"""add compressed_blob_url column to videos

Revision ID: 20260220_compressed_blob
Revises: 20260219_user_rating
Create Date: 2026-02-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260220_compressed_blob"
down_revision = "20260219_user_rating"
branch_labels = None
depends_on = None


def upgrade():
    # Add compressed_blob_url column to store the blob path of the 1080p preview version
    # e.g., "email/video_id/video_id_preview.mp4"
    op.add_column(
        "videos",
        sa.Column("compressed_blob_url", sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_column("videos", "compressed_blob_url")
