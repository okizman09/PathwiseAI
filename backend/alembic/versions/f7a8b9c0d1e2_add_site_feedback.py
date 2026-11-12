"""Add site_feedback table for landing-page UX feedback.

Revision ID: f7a8b9c0d1e2
Revises: a7b8c9d0e1f2
Create Date: 2026-11-12 14:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f7a8b9c0d1e2'
down_revision: str | Sequence[str] | None = 'a7b8c9d0e1f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'site_feedback',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('page', sa.String(length=500), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('contact', sa.String(length=320), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_site_feedback_user_id'), 'site_feedback', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_table('site_feedback')
