"""Enable Row-Level Security on all public tables (Supabase linter fix).

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-03 00:00:00.000000

All data access flows through the backend's postgres connection (which
bypasses RLS) and the frontend uses Supabase only for auth, so enabling
RLS with no policies locks out anonymous PostgREST access without
affecting the app. No-op on non-Postgres databases.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = (
    'alembic_version',
    'events',
    'profiles',
    'rate_limit_buckets',
    'step_feedback',
    'step_runs',
    'tool_gaps',
    'tools',
    'usage_daily',
    'workflow_steps',
    'workflows',
)


def upgrade() -> None:
    if op.get_bind().dialect.name != 'postgresql':
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name != 'postgresql':
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')
