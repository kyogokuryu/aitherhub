"""add step_progress column to videos table

Revision ID: 20260221_step_progress
Revises: 20260221_cta_audio
Create Date: 2026-02-21 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260221_step_progress'
down_revision = '20260221_cta_audio'
branch_labels = None
depends_on = None


def upgrade():
    # step_progress: 0-100 integer representing intra-step progress
    # Updated by worker during long-running steps (frame extraction, transcription, etc.)
    # Read by SSE endpoint to provide real-time progress updates within each step
    op.add_column(
        'videos',
        sa.Column('step_progress', sa.Integer(), nullable=True, server_default='0'),
    )


def downgrade():
    op.drop_column('videos', 'step_progress')
