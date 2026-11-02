"""person cognito sub

Links a person to their Cognito user, for portals signing in through a user pool.

Revision ID: e5a9c3b7d2f1
Revises: d4f2a7c9e1b3
Create Date: 2026-11-02 18:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a9c3b7d2f1'
down_revision: Union[str, Sequence[str], None] = 'd4f2a7c9e1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('person') as batch:
        batch.add_column(sa.Column('cognito_sub', sa.String(length=64), nullable=True))
        batch.create_unique_constraint('uq_person_cognito_sub', ['cognito_sub'])


def downgrade() -> None:
    with op.batch_alter_table('person') as batch:
        batch.drop_constraint('uq_person_cognito_sub', type_='unique')
        batch.drop_column('cognito_sub')
