"""Add step content fields for setup steps (dynamic steps vs prompts).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-02 18:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('workflow_steps',
                  sa.Column('content_type', sa.String(length=10), nullable=True,
                            server_default='prompt'))
    op.add_column('workflow_steps', sa.Column('action_steps', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('workflow_steps', 'action_steps')
    op.drop_column('workflow_steps', 'content_type')
