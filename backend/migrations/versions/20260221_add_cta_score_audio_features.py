"""add cta_score and audio_features to video_phases

Revision ID: 20260221_cta_audio
Revises: 20260218_upload_type
Create Date: 2026-02-21 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260221_cta_audio'
down_revision = '20260218_upload_type'
branch_labels = None
depends_on = None


def upgrade():
    # CTA score: 1-5 integer, extracted from GPT phase description
    # 1 = no CTA, 5 = strongest CTA (direct purchase instruction)
    op.add_column(
        'video_phases',
        sa.Column('cta_score', sa.Integer(), nullable=True)
    )

    # Audio features: JSON blob containing paralinguistic features
    # {
    #   "energy_mean": 0.0123,
    #   "energy_max": 0.0456,
    #   "pitch_mean": 210.5,
    #   "pitch_std": 45.2,
    #   "speech_rate": 5.3,
    #   "silence_ratio": 0.12,
    #   "energy_trend": "rising"
    # }
    # NULL for phases that were not analyzed (below CTA/importance threshold)
    op.add_column(
        'video_phases',
        sa.Column('audio_features', sa.Text(), nullable=True)
    )


def downgrade():
    op.drop_column('video_phases', 'audio_features')
    op.drop_column('video_phases', 'cta_score')
