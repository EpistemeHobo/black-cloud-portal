"""handover guide

Adds the handover guide (docs/decisions/0003-handover-first.md) and moves the
inventory fields that overlap it: business purpose becomes "if it's down",
known issues become traps, roadmap notes become unfinished work.

Revision ID: 5a1c0e7d9b42
Revises: 26254c4c2215
Create Date: 2026-10-29 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5a1c0e7d9b42'
down_revision: Union[str, Sequence[str], None] = '26254c4c2215'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('system') as batch:
        for name in ('if_down', 'run_steps', 'deploy_steps', 'rollback_steps'):
            batch.add_column(sa.Column(name, sa.Text(), nullable=True))
        batch.add_column(sa.Column('guide_nothing', sa.JSON(), nullable=True))
    with op.batch_alter_table('person') as batch:
        batch.add_column(sa.Column('is_auditor', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('system_role') as batch:
        batch.add_column(sa.Column('reachable_until', sa.Date(), nullable=True))
        batch.add_column(sa.Column('note', sa.String(length=300), nullable=True))

    op.create_table('watch_out',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('system_id', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('how_often', sa.String(length=20), nullable=True),
    sa.Column('next_due', sa.Date(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['system_id'], ['system.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('open_item',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('system_id', sa.String(length=20), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('promised_to', sa.String(length=200), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('done_by_id', sa.Integer(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['done_by_id'], ['person.id'], ),
    sa.ForeignKeyConstraint(['system_id'], ['system.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )

    op.execute("UPDATE system SET if_down = business_purpose WHERE business_purpose IS NOT NULL")
    op.execute(
        "INSERT INTO watch_out (system_id, kind, text, sort_order) "
        "SELECT id, 'trap', known_issues, 0 FROM system WHERE known_issues IS NOT NULL AND known_issues != ''"
    )
    op.execute(
        "INSERT INTO open_item (system_id, kind, text, sort_order) "
        "SELECT id, 'work', roadmap_notes, 0 FROM system WHERE roadmap_notes IS NOT NULL AND roadmap_notes != ''"
    )

    with op.batch_alter_table('system') as batch:
        batch.drop_column('business_purpose')
        batch.drop_column('known_issues')
        batch.drop_column('roadmap_notes')


def downgrade() -> None:
    with op.batch_alter_table('system') as batch:
        batch.add_column(sa.Column('business_purpose', sa.Text(), nullable=True))
        batch.add_column(sa.Column('known_issues', sa.Text(), nullable=True))
        batch.add_column(sa.Column('roadmap_notes', sa.Text(), nullable=True))
    op.execute("UPDATE system SET business_purpose = if_down")
    op.drop_table('open_item')
    op.drop_table('watch_out')
    with op.batch_alter_table('system_role') as batch:
        batch.drop_column('note')
        batch.drop_column('reachable_until')
    with op.batch_alter_table('person') as batch:
        batch.drop_column('is_auditor')
    with op.batch_alter_table('system') as batch:
        for name in ('guide_nothing', 'rollback_steps', 'deploy_steps', 'run_steps', 'if_down'):
            batch.drop_column(name)
