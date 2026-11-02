"""Add step_feedback table for creator usage signals (Slice C7).

Revision ID: a1b2c3d4e5f6
Revises: 9c0d1e2f3a4b
Create Date: 2026-10-09 15:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '9c0d1e2f3a4b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'step_feedback',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('step_id', sa.Integer(), sa.ForeignKey('workflow_steps.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow_id', sa.Integer(), sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('tool_id', sa.Integer(), sa.ForeignKey('tools.id', ondelete='SET NULL'), nullable=True),
        sa.Column('result', sa.String(length=20), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(op.f('ix_step_feedback_step_id'), 'step_feedback', ['step_id'], unique=False)
    op.create_index(op.f('ix_step_feedback_workflow_id'), 'step_feedback', ['workflow_id'], unique=False)
    op.create_index(op.f('ix_step_feedback_user_id'), 'step_feedback', ['user_id'], unique=False)
    op.create_index(op.f('ix_step_feedback_tool_id'), 'step_feedback', ['tool_id'], unique=False)


def downgrade() -> None:
    op.drop_table('step_feedback')
