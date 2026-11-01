"""activity log

Account events (sign-ins, sign-ups, approvals, password resets) for the
admins' activity page.

Revision ID: c3e8a1f4d7b6
Revises: b7d41e9a2c55
Create Date: 2026-10-30 17:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e8a1f4d7b6'
down_revision: Union[str, Sequence[str], None] = 'b7d41e9a2c55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('activity_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('actor_email', sa.String(length=320), nullable=True),
    sa.Column('subject_email', sa.String(length=320), nullable=True),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_activity_log_at', 'activity_log', ['at'])
    op.create_index('ix_activity_log_action', 'activity_log', ['action'])


def downgrade() -> None:
    op.drop_index('ix_activity_log_action', table_name='activity_log')
    op.drop_index('ix_activity_log_at', table_name='activity_log')
    op.drop_table('activity_log')
