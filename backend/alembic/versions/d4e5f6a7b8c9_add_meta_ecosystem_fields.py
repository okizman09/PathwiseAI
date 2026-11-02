"""Add Meta ecosystem fields to tools (hackathon T4).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-02 16:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tools', sa.Column('ecosystem', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_tools_ecosystem'), 'tools', ['ecosystem'], unique=False)
    op.add_column('tools', sa.Column('kind', sa.String(length=30), nullable=True))
    op.add_column('tools', sa.Column('model_id', sa.String(length=100), nullable=True))
    op.add_column('tools', sa.Column('api_snippet', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_index(op.f('ix_tools_ecosystem'), table_name='tools')
    op.drop_column('tools', 'api_snippet')
    op.drop_column('tools', 'model_id')
    op.drop_column('tools', 'kind')
    op.drop_column('tools', 'ecosystem')
