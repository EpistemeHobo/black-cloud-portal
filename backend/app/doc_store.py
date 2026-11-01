"""Where the markdown files attached to the handover guide are kept.

With DOCS_BUCKET set, each file is one S3 object at
`<DOCS_PREFIX>/systems/<system id>/<question>/<file name>` and its guide_doc row
keeps the key and a SHA-256 of the text; the row's content column is empty.
Without it (a developer's machine, the tests) the text stays in the row.

Turn on versioning on the bucket: a replaced or removed file stays recoverable there.

Run `python -m app.doc_store` once after setting DOCS_BUCKET to move files that
are still in the database into S3.
"""
import hashlib
import logging
from functools import lru_cache

from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app import config
from app.models import GuideDoc, System

logger = logging.getLogger("portal")

# Keys of objects whose rows were deleted, removed from S3 once the transaction commits.
_DELETE_KEY = "doc_store_delete"


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=1)
def _s3():
    import boto3
    return boto3.client("s3", region_name=config.AWS_REGION)


def _key(system: System, doc: GuideDoc) -> str:
    key = f"systems/{system.id}/{doc.question}/{doc.filename}"
    return f"{config.DOCS_PREFIX}/{key}" if config.DOCS_PREFIX else key


def save(system: System, doc: GuideDoc, text: str) -> None:
    """Set a file's text: uploads it to S3, or keeps it in the row without a bucket."""
    doc.checksum = checksum(text)
    if not config.DOCS_BUCKET:
        doc.content, doc.s3_key = text, None
        return
    key = _key(system, doc)
    _s3().put_object(Bucket=config.DOCS_BUCKET, Key=key, Body=text.encode("utf-8"),
                     ContentType="text/markdown; charset=utf-8")
    doc.content, doc.s3_key = None, key


def read(doc: GuideDoc) -> str:
    if doc.s3_key is None:
        return doc.content or ""
    return _fetch(doc.s3_key, doc.checksum)


# Keyed by checksum too, so a replaced file is fetched again on every instance.
@lru_cache(maxsize=256)
def _fetch(key: str, _checksum: str) -> str:
    return _s3().get_object(Bucket=config.DOCS_BUCKET, Key=key)["Body"].read().decode("utf-8")


@event.listens_for(Session, "persistent_to_deleted")
def _row_deleted(session: Session, obj) -> None:
    # Also fires for files taken out of system.docs and for a deleted system's files.
    if isinstance(obj, GuideDoc) and obj.s3_key:
        session.info.setdefault(_DELETE_KEY, set()).add(obj.s3_key)


@event.listens_for(Session, "after_commit")
def _delete_objects(session: Session) -> None:
    keys = session.info.pop(_DELETE_KEY, set())
    for key in keys:
        try:
            _s3().delete_object(Bucket=config.DOCS_BUCKET, Key=key)
        except Exception:  # the row is gone either way; an orphaned object only costs storage
            logger.exception("Could not delete s3://%s/%s", config.DOCS_BUCKET, key)


@event.listens_for(Session, "after_rollback")
def _forget(session: Session) -> None:
    session.info.pop(_DELETE_KEY, None)


def move_to_s3(db: Session) -> int:
    """Upload every file still kept in the database. Returns how many moved."""
    docs = db.scalars(select(GuideDoc).where(GuideDoc.s3_key.is_(None))).all()
    for doc in docs:
        save(doc.system, doc, doc.content or "")
    db.commit()
    return len(docs)


if __name__ == "__main__":
    from app.db import SessionLocal

    if not config.DOCS_BUCKET:
        raise SystemExit("Set DOCS_BUCKET first.")
    with SessionLocal() as session:
        print(f"Moved {move_to_s3(session)} files to s3://{config.DOCS_BUCKET}.")
