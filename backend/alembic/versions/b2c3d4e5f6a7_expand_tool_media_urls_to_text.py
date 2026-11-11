"""Expand tool logo_url and og_image_url to Text.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-09 17:38:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Expand logo_url and og_image_url to TEXT to support data URIs and long asset URLs
    # batch_alter_table keeps this working on SQLite (local dev) as well as Postgres.
    with op.batch_alter_table('tools') as batch_op:
        batch_op.alter_column(
            'logo_url',
            existing_type=sa.String(length=1024),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'og_image_url',
            existing_type=sa.String(length=1024),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table('tools') as batch_op:
        batch_op.alter_column(
            'og_image_url',
            existing_type=sa.Text(),
            type_=sa.String(length=1024),
            existing_nullable=True,
        )
        batch_op.alter_column(
            'logo_url',
            existing_type=sa.Text(),
            type_=sa.String(length=1024),
            existing_nullable=True,
        )
