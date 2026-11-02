"""add rate limit buckets

Revision ID: 8b9c0d1e2f3a
Revises: 7a8b9c0d1e2f
Create Date: 2026-10-07 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '8b9c0d1e2f3a'
down_revision: str | Sequence[str] | None = '7a8b9c0d1e2f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'rate_limit_buckets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=128), nullable=False),
        sa.Column('window_type', sa.String(length=10), nullable=False),
        sa.Column('window_start', sa.Integer(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key', 'window_type', 'window_start', name='uq_rate_limit_key_window'),
    )
    op.create_index(op.f('ix_rate_limit_buckets_key'), 'rate_limit_buckets', ['key'], unique=False)
    op.create_index(op.f('ix_rate_limit_buckets_window_start'), 'rate_limit_buckets', ['window_start'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_rate_limit_buckets_window_start'), table_name='rate_limit_buckets')
    op.drop_index(op.f('ix_rate_limit_buckets_key'), table_name='rate_limit_buckets')
    op.drop_table('rate_limit_buckets')
