"""Catalog v3 schema update: structured tool cards, taxonomy, and pricing models.

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-10-09 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9c0d1e2f3a4b'
down_revision: str | Sequence[str] | None = '8b9c0d1e2f3a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add new columns to tools table
    op.add_column('tools', sa.Column('domain', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_tools_domain'), 'tools', ['domain'], unique=False)

    op.add_column('tools', sa.Column('pricing_model', sa.String(length=50), nullable=True, server_default='unknown'))
    op.add_column('tools', sa.Column('has_free_tier', sa.Boolean(), nullable=True))
    op.add_column('tools', sa.Column('free_tier_summary', sa.String(length=140), nullable=True))
    op.add_column('tools', sa.Column('free_tier_limits', sa.Text(), nullable=True))
    op.add_column('tools', sa.Column('starting_price_monthly_usd', sa.Float(), nullable=True))
    op.add_column('tools', sa.Column('pricing_notes', sa.Text(), nullable=True))
    op.add_column('tools', sa.Column('credit_card_required', sa.Boolean(), nullable=True))
    op.add_column('tools', sa.Column('watermark_on_free', sa.Boolean(), nullable=True))
    op.add_column('tools', sa.Column('commercial_use_on_free', sa.Boolean(), nullable=True))
    op.add_column('tools', sa.Column('pricing_url', sa.String(length=1024), nullable=True))
    op.add_column('tools', sa.Column('pricing_checked_at', sa.DateTime(timezone=True), nullable=True))

    op.add_column('tools', sa.Column('platforms', sa.JSON(), nullable=True))
    op.add_column('tools', sa.Column('skill_level', sa.String(length=50), nullable=True, server_default='all'))

    op.add_column('tools', sa.Column('tagline', sa.String(length=90), nullable=True))
    op.add_column('tools', sa.Column('summary', sa.Text(), nullable=True))
    op.add_column('tools', sa.Column('how_it_helps', sa.Text(), nullable=True))
    op.add_column('tools', sa.Column('pros', sa.JSON(), nullable=True))
    op.add_column('tools', sa.Column('cons', sa.JSON(), nullable=True))

    op.add_column('tools', sa.Column('logo_url', sa.String(length=1024), nullable=True))
    op.add_column('tools', sa.Column('og_image_url', sa.String(length=1024), nullable=True))

    op.add_column('tools', sa.Column('evidence', sa.JSON(), nullable=True))
    op.add_column('tools', sa.Column('review_flags', sa.JSON(), nullable=True))
    op.add_column('tools', sa.Column('official_domains', sa.JSON(), nullable=True))
    op.add_column('tools', sa.Column('research_provider', sa.String(length=50), nullable=True))
    op.add_column('tools', sa.Column('researched_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tools', sa.Column('verified_by', sa.String(length=255), nullable=True))
    op.add_column('tools', sa.Column('is_pick', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # 2. Existing tools: set status to draft (keep affiliate_url and URLs) so they are re-imported.
    # Safe on both PostgreSQL and SQLite.
    op.execute("UPDATE tools SET status = 'draft' WHERE status != 'draft'")


def downgrade() -> None:
    op.drop_column('tools', 'is_pick')
    op.drop_column('tools', 'verified_by')
    op.drop_column('tools', 'researched_at')
    op.drop_column('tools', 'research_provider')
    op.drop_column('tools', 'official_domains')
    op.drop_column('tools', 'review_flags')
    op.drop_column('tools', 'evidence')

    op.drop_column('tools', 'og_image_url')
    op.drop_column('tools', 'logo_url')

    op.drop_column('tools', 'cons')
    op.drop_column('tools', 'pros')
    op.drop_column('tools', 'how_it_helps')
    op.drop_column('tools', 'summary')
    op.drop_column('tools', 'tagline')

    op.drop_column('tools', 'skill_level')
    op.drop_column('tools', 'platforms')

    op.drop_column('tools', 'pricing_checked_at')
    op.drop_column('tools', 'pricing_url')
    op.drop_column('tools', 'commercial_use_on_free')
    op.drop_column('tools', 'watermark_on_free')
    op.drop_column('tools', 'credit_card_required')
    op.drop_column('tools', 'pricing_notes')
    op.drop_column('tools', 'starting_price_monthly_usd')
    op.drop_column('tools', 'free_tier_limits')
    op.drop_column('tools', 'free_tier_summary')
    op.drop_column('tools', 'has_free_tier')
    op.drop_column('tools', 'pricing_model')

    op.drop_index(op.f('ix_tools_domain'), table_name='tools')
    op.drop_column('tools', 'domain')
