"""guide docs

Markdown files developers attach to handover guide questions.

Revision ID: 8c2e4b6f1a03
Revises: 5a1c0e7d9b42
Create Date: 2026-10-29 15:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8c2e4b6f1a03'
down_revision: Union[str, Sequence[str], None] = '5a1c0e7d9b42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('guide_doc',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('system_id', sa.String(length=20), nullable=False),
    sa.Column('question', sa.String(length=20), nullable=False),
    sa.Column('filename', sa.String(length=200), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('updated_by_id', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['system_id'], ['system.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['updated_by_id'], ['person.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('system_id', 'question', 'filename')
    )


def downgrade() -> None:
    op.drop_table('guide_doc')
