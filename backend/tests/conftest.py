import os
import tempfile
from pathlib import Path

# Settings are read at import time, so set them before anything imports app.
_TMP = Path(tempfile.mkdtemp(prefix="portal-test-"))
os.environ["INSTANCE_DIR"] = str(_TMP)
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["ENVIRONMENT"] = "test"
os.environ["PASSWORD_ITERATIONS"] = "1000"  # fast hashing for tests
os.environ["KB_BASE_URL"] = "https://kb.example.org"
os.environ["FRONTEND_DIR"] = str(_TMP / "no-frontend")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from sqlalchemy import select  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Person  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_standards  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def fresh_db():
    """Every test starts from an empty, fully migrated database with the standards loaded."""
    Base.metadata.drop_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    with SessionLocal() as db:
        seed_standards(db)
    yield


PASSWORD = "test-password-1"

# Emails "sent" during a test: dicts with to, subject, text and link.
OUTBOX: list[dict] = []


@pytest.fixture(autouse=True)
def outbox(monkeypatch):
    """Capture emails instead of sending them, and forget the resend cooldowns."""
    from app import mailer
    OUTBOX.clear()
    mailer._last_sent.clear()
    monkeypatch.setattr(mailer, "send", lambda to, subject, lines, button=None: OUTBOX.append(
        {"to": to, "subject": subject, "text": " ".join(lines), "link": button[1] if button else None}))
    return OUTBOX


def login(email: str, name: str = "", admin: bool = False) -> TestClient:
    """A client signed in as this person: signs up, gets approved, signs in."""
    client = TestClient(app)
    client.post("/api/auth/register", json={"name": name or email.split("@")[0], "email": email, "password": PASSWORD})
    with SessionLocal() as db:
        person = db.scalar(select(Person).where(Person.email == email.lower()))
        person.status = "active"
        person.email_verified = True
        person.is_admin = person.is_admin or admin
        db.commit()
    r = client.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return client


@pytest.fixture
def owner() -> TestClient:
    return login("owner@example.org", "Owner")


@pytest.fixture
def other() -> TestClient:
    return login("other@example.org", "Other")


@pytest.fixture
def admin() -> TestClient:
    return login("admin@example.org", "Admin", admin=True)


@pytest.fixture
def system(owner) -> dict:
    r = owner.post("/api/systems", json={"name": "Lab Booking", "type": "Web app"})
    assert r.status_code == 201, r.text
    return r.json()
