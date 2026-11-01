import boto3
import pytest
from moto import mock_aws
from sqlalchemy import select

from app import config, doc_store
from app.db import SessionLocal
from app.models import GuideDoc

BUCKET = "portal-docs-test"


@pytest.fixture
def s3(monkeypatch):
    """A fake S3 bucket, with DOCS_BUCKET pointing at it."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setattr(config, "DOCS_BUCKET", BUCKET)
    monkeypatch.setattr(config, "DOCS_PREFIX", "portal")
    with mock_aws():
        doc_store._s3.cache_clear()
        doc_store._fetch.cache_clear()
        client = boto3.client("s3", region_name=config.AWS_REGION)
        client.create_bucket(Bucket=BUCKET)
        yield client
    doc_store._s3.cache_clear()
    doc_store._fetch.cache_clear()


def keys(client) -> list[str]:
    return sorted(o["Key"] for o in client.list_objects_v2(Bucket=BUCKET).get("Contents", []))


def body(client, key: str) -> str:
    return client.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()


def test_files_go_to_s3_and_the_row_keeps_only_the_key(s3, system, owner):
    sid = system["id"]
    r = owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "คู่มือ.md", "content": "# ขั้นตอน"})
    assert r.status_code == 200, r.text
    key = f"portal/systems/{sid}/how/คู่มือ.md"
    assert keys(s3) == [key] and body(s3, key) == "# ขั้นตอน"
    with SessionLocal() as db:
        row = db.scalar(select(GuideDoc))
        assert (row.content, row.s3_key, row.checksum) == (None, key, doc_store.checksum("# ขั้นตอน"))
    # The API still hands the text to the frontend.
    assert owner.get(f"/api/systems/{sid}").json()["docs"][0]["content"] == "# ขั้นตอน"

    # Replacing overwrites the object and is not served stale from the cache.
    owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "คู่มือ.md", "content": "v2"})
    assert body(s3, key) == "v2"
    assert owner.get(f"/api/systems/{sid}").json()["docs"][0]["content"] == "v2"
    rows = {(h["field"], h["new_value"]) for h in owner.get(f"/api/systems/{sid}/history").json()
            if h["entity"] == "guide_doc"}
    assert rows == {("added", "คู่มือ.md"), ("replaced", "คู่มือ.md")}


def test_removing_a_file_or_its_system_deletes_the_objects(s3, owner):
    sid = owner.post("/api/systems", json={"name": "Docs", "type": "Web app"}).json()["id"]
    for name in ("a.md", "b.md"):
        owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": name, "content": name})
    doc_id = owner.get(f"/api/systems/{sid}").json()["docs"][0]["id"]
    owner.delete(f"/api/systems/{sid}/docs/{doc_id}")
    assert keys(s3) == [f"portal/systems/{sid}/how/b.md"]
    assert owner.delete(f"/api/systems/{sid}").status_code == 204
    assert keys(s3) == []


def test_export_and_import_read_and_write_s3(s3, system, owner):
    sid = system["id"]
    owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "run.md", "content": "# Run"})
    from tests.test_transfer import as_import, unzip
    payload = as_import(unzip(owner.get(f"/api/systems/{sid}/export").content))
    new_id = owner.post("/api/systems/import", json=payload).json()["id"]
    assert body(s3, f"portal/systems/{new_id}/how/run.md") == "# Run"


def test_moving_existing_files_into_s3(system, owner, monkeypatch):
    sid = system["id"]
    owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "old.md", "content": "kept in the db"})
    with mock_aws():
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
        monkeypatch.setattr(config, "DOCS_BUCKET", BUCKET)
        doc_store._s3.cache_clear()
        client = boto3.client("s3", region_name=config.AWS_REGION)
        client.create_bucket(Bucket=BUCKET)
        with SessionLocal() as db:
            assert doc_store.move_to_s3(db) == 1
        assert body(client, f"systems/{sid}/how/old.md") == "kept in the db"
        assert owner.get(f"/api/systems/{sid}").json()["docs"][0]["content"] == "kept in the db"
    doc_store._s3.cache_clear()


def test_database_url_is_built_from_parts(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_HOST", "portal.cluster-abc.us-east-1.rds.amazonaws.com")
    monkeypatch.setenv("DB_USER", "portal")
    monkeypatch.setenv("DB_PASSWORD", "p@ss/word:1")
    monkeypatch.setenv("DB_NAME", "portal")
    assert config._database_url() == (
        "postgresql+psycopg://portal:p%40ss%2Fword%3A1@portal.cluster-abc.us-east-1.rds.amazonaws.com:5432/portal")
