"""add step job metadata

Revision ID: 7a8b9c0d1e2f
Revises: 9f1ff3a9373e
Create Date: 2026-10-06 15:10:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7a8b9c0d1e2f'
down_revision: str | Sequence[str] | None = '9f1ff3a9373e'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('workflow_steps', sa.Column('job_tags', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('workflow_steps', sa.Column('input_types', sa.JSON(), nullable=True, server_default='[]'))
    op.add_column('workflow_steps', sa.Column('output_types', sa.JSON(), nullable=True, server_default='[]'))


def downgrade() -> None:
    op.drop_column('workflow_steps', 'output_types')
    op.drop_column('workflow_steps', 'input_types')
    op.drop_column('workflow_steps', 'job_tags')
