"""guide docs in s3

A guide file's text can live in S3 (doc_store.py): the row keeps the object key
and a SHA-256 of the text, and content becomes optional.

Revision ID: d4f2a7c9e1b3
Revises: c3e8a1f4d7b6
Create Date: 2026-11-01 10:00:00

"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f2a7c9e1b3'
down_revision: Union[str, Sequence[str], None] = 'c3e8a1f4d7b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

guide_doc = sa.table('guide_doc', sa.column('id', sa.Integer), sa.column('content', sa.Text),
                     sa.column('checksum', sa.String))


def upgrade() -> None:
    with op.batch_alter_table('guide_doc') as batch:
        batch.add_column(sa.Column('s3_key', sa.String(length=500), nullable=True))
        batch.add_column(sa.Column('checksum', sa.String(length=64), nullable=True))
        batch.alter_column('content', existing_type=sa.Text(), nullable=True)
    conn = op.get_bind()
    for doc_id, content in conn.execute(sa.select(guide_doc.c.id, guide_doc.c.content)).all():
        conn.execute(guide_doc.update().where(guide_doc.c.id == doc_id)
                     .values(checksum=hashlib.sha256((content or "").encode("utf-8")).hexdigest()))
    with op.batch_alter_table('guide_doc') as batch:
        batch.alter_column('checksum', existing_type=sa.String(length=64), nullable=False)


def downgrade() -> None:
    # Files kept in S3 come back empty here; their text is still in the bucket.
    op.execute("UPDATE guide_doc SET content = '' WHERE content IS NULL")
    with op.batch_alter_table('guide_doc') as batch:
        batch.alter_column('content', existing_type=sa.Text(), nullable=False)
        batch.drop_column('checksum')
        batch.drop_column('s3_key')
