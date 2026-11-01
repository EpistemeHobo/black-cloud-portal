"""own accounts

The portal signs people in with its own email + password accounts instead of
Keycloak SSO, verifying addresses by email. Person gains an account status, a
password hash, email_verified and the failed-login lockout; `active` and
`sso_subject` go.

Nobody has a password yet, so everyone who could sign in before becomes an
active account without one, and sets a password through "forgot password".

Revision ID: b7d41e9a2c55
Revises: 8c2e4b6f1a03
Create Date: 2026-10-30 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d41e9a2c55'
down_revision: Union[str, Sequence[str], None] = '8c2e4b6f1a03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('person') as batch:
        batch.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='no_account'))
        batch.add_column(sa.Column('password_hash', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('last_sign_in_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('failed_logins', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('last_failed_at', sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE person SET status = 'suspended' WHERE active = false AND sso_subject IS NOT NULL")
    op.execute("UPDATE person SET status = 'active' WHERE active = true AND sso_subject IS NOT NULL")
    # SSO already proved these addresses.
    op.execute("UPDATE person SET email_verified = true WHERE sso_subject IS NOT NULL")
    with op.batch_alter_table('person') as batch:
        batch.drop_column('sso_subject')
        batch.drop_column('active')


def downgrade() -> None:
    with op.batch_alter_table('person') as batch:
        batch.add_column(sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column('sso_subject', sa.String(length=255), nullable=True))
    op.execute("UPDATE person SET active = false WHERE status = 'suspended'")
    with op.batch_alter_table('person') as batch:
        batch.create_unique_constraint('uq_person_sso_subject', ['sso_subject'])
        batch.drop_column('locked_until')
        batch.drop_column('last_failed_at')
        batch.drop_column('failed_logins')
        batch.drop_column('last_sign_in_at')
        batch.drop_column('email_verified')
        batch.drop_column('password_hash')
        batch.drop_column('status')
