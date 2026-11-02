"""Sign-in through Cognito, with Cognito's token endpoint and keys faked."""
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import cognito, config
from app.auth import seed_admin
from app.db import SessionLocal
from app.main import app
from app.models import Person

POOL = "us-east-1_TESTPOOL"
CLIENT = "test-client"
ISSUER = f"https://cognito-idp.us-east-1.amazonaws.com/{POOL}"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def cognito_on(monkeypatch):
    monkeypatch.setattr(config, "USE_COGNITO", True)
    monkeypatch.setattr(config, "COGNITO_USER_POOL_ID", POOL)
    monkeypatch.setattr(config, "COGNITO_CLIENT_ID", CLIENT)
    monkeypatch.setattr(config, "COGNITO_DOMAIN", "https://pool.example.org")
    monkeypatch.setattr(config, "PUBLIC_BASE_URL", "https://portal.example.org")
    monkeypatch.setattr(cognito, "_signing_key", lambda token: KEY.public_key())


def browser() -> TestClient:
    return TestClient(app, follow_redirects=False)


def sign_in(monkeypatch, client=None, key=KEY, nonce=None, sub="sub-1", email="new@example.org", **claims):
    """Goes to Cognito and back, as a browser would. Returns the client and the final redirect."""
    client = client or browser()
    start = client.get("/api/auth/start")
    assert start.status_code == 302
    sent = parse_qs(urlparse(start.headers["location"]).query)
    body = {"sub": sub, "email": email, "email_verified": True, "name": "New Person", "token_use": "id",
            "aud": CLIENT, "iss": ISSUER, "nonce": sent["nonce"][0] if nonce is None else nonce,
            "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(hours=1), **claims}
    token = jwt.encode(body, key, algorithm="RS256")
    seen = {}

    def fake_post(url, data, timeout):
        seen.update(data)
        return httpx.Response(200, json={"id_token": token, "access_token": "unused"})

    monkeypatch.setattr(cognito.httpx, "post", fake_post)
    back = client.get("/api/auth/callback", params={"code": "the-code", "state": sent["state"][0]})
    assert back.status_code == 302
    return client, back, seen


@pytest.fixture
def admin(monkeypatch) -> TestClient:
    """Replaces conftest's: that one signs up with a password, which is switched off here."""
    with SessionLocal() as db:
        db.add(Person(email="admin@example.org", name="Admin", status="active", is_admin=True, email_verified=True))
        db.commit()
    client, back, _ = sign_in(monkeypatch, sub="admin-sub", email="admin@example.org")
    assert back.headers["location"] == "/"
    return client


def person(email="new@example.org") -> Person:
    with SessionLocal() as db:
        return db.scalar(select(Person).where(Person.email == email))


def signed_in(client) -> bool:
    return client.get("/api/auth/me").json()["person"] is not None


def test_start_sends_the_browser_to_cognito_with_pkce():
    client = browser()
    r = client.get("/api/auth/start")
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert url.netloc == "pool.example.org" and url.path == "/oauth2/authorize"
    assert q["client_id"] == [CLIENT] and q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["https://portal.example.org/api/auth/callback"]
    assert q["code_challenge_method"] == ["S256"] and q["code_challenge"] and q["state"] and q["nonce"]
    assert "HttpOnly" in r.headers["set-cookie"] and "samesite=lax" in r.headers["set-cookie"].lower()
    assert urlparse(client.get("/api/auth/start?page=signup").headers["location"]).path == "/signup"


def test_a_new_person_waits_for_approval_then_gets_in(monkeypatch, admin):
    client, back, seen = sign_in(monkeypatch)
    assert back.headers["location"] == "/?signin=pending"
    assert not signed_in(client)
    assert seen["code"] == "the-code" and seen["code_verifier"]
    p = person()
    assert (p.status, p.email_verified, p.cognito_sub, p.password_hash) == ("pending", True, "sub-1", None)

    assert admin.patch(f"/api/people/{p.id}", json={"status": "active"}).status_code == 200
    _, back, _ = sign_in(monkeypatch, client)
    assert back.headers["location"] == "/"
    assert signed_in(client)


def test_the_seed_admin_gets_in_once_cognito_has_verified_the_address(monkeypatch):
    monkeypatch.setattr(config, "SEED_ADMIN_EMAIL", "boss@example.org")
    with SessionLocal() as db:
        seed_admin(db)
    client, back, _ = sign_in(monkeypatch, email="boss@example.org")
    assert back.headers["location"] == "/"
    assert client.get("/api/auth/me").json()["person"]["is_admin"] is True


def test_seeding_again_does_not_undo_a_suspension(monkeypatch, admin):
    monkeypatch.setattr(config, "SEED_ADMIN_EMAIL", "boss@example.org")
    with SessionLocal() as db:
        seed_admin(db)
    assert admin.patch(f"/api/people/{person('boss@example.org').id}", json={"status": "suspended"}).status_code == 200
    with SessionLocal() as db:
        seed_admin(db)
    assert person("boss@example.org").status == "suspended"


def test_someone_added_as_an_owner_takes_over_that_record(monkeypatch, admin):
    added = admin.post("/api/people", json={"name": "Added", "email": "new@example.org"}).json()
    sign_in(monkeypatch)
    p = person()
    assert p.id == added["id"] and p.status == "pending" and p.name == "New Person"


@pytest.mark.parametrize("change", [
    {"aud": "another-client"},
    {"iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_OTHER"},
    {"token_use": "access"},
    {"exp": datetime.now(timezone.utc) - timedelta(minutes=5)},
    {"email_verified": False},
    {"email_verified": "false"},
    {"nonce": "someone-elses"},
    {"key": OTHER_KEY},
])
def test_an_untrustworthy_token_is_refused(monkeypatch, change):
    client, back, _ = sign_in(monkeypatch, **change)
    assert back.headers["location"] == "/?signin=failed"
    assert not signed_in(client)
    assert person() is None


def test_a_callback_this_browser_did_not_start_is_refused(monkeypatch):
    _, _, _ = sign_in(monkeypatch)
    fresh = browser()
    assert fresh.get("/api/auth/callback", params={"code": "c", "state": "s"}).headers["location"] == "/?signin=failed"
    client = browser()
    client.get("/api/auth/start")
    assert client.get("/api/auth/callback", params={"code": "c", "state": "wrong"}).headers["location"] == "/?signin=failed"


def test_the_token_endpoint_refusing_is_a_failed_sign_in(monkeypatch):
    client = browser()
    q = parse_qs(urlparse(client.get("/api/auth/start").headers["location"]).query)
    monkeypatch.setattr(cognito.httpx, "post", lambda url, data, timeout: httpx.Response(400, json={"error": "invalid_grant"}))
    assert client.get("/api/auth/callback", params={"code": "c", "state": q["state"][0]}).headers["location"] == "/?signin=failed"


def test_the_permanent_id_decides_not_the_address(monkeypatch, admin):
    _, _, _ = sign_in(monkeypatch)
    first = person()
    # Same person, new address at Cognito: still their own record, and no new one.
    client, back, _ = sign_in(monkeypatch, email="changed@example.org")
    assert back.headers["location"] == "/?signin=pending" and person("changed@example.org") is None
    # A different Cognito user with an address that's already linked: refused.
    client, back, _ = sign_in(monkeypatch, sub="sub-2")
    assert back.headers["location"] == "/?signin=refused" and person().cognito_sub == "sub-1" and person().id == first.id


def test_suspended_people_stay_out(monkeypatch, admin):
    sign_in(monkeypatch)
    p = person()
    admin.patch(f"/api/people/{p.id}", json={"status": "active"})
    admin.patch(f"/api/people/{p.id}", json={"status": "suspended"})
    client, back, _ = sign_in(monkeypatch)
    assert back.headers["location"] == "/?signin=suspended" and not signed_in(client)


def test_a_turned_down_sign_up_can_ask_again(monkeypatch, admin):
    sign_in(monkeypatch)
    assert admin.delete(f"/api/admin/users/{person().id}").status_code == 204
    _, back, _ = sign_in(monkeypatch)
    assert back.headers["location"] == "/?signin=pending"


def test_email_domain_rule_applies_to_new_people(monkeypatch):
    monkeypatch.setattr(config, "ALLOWED_EMAIL_DOMAINS", ["example.org"])
    _, back, _ = sign_in(monkeypatch, email="someone@elsewhere.net")
    assert back.headers["location"] == "/?signin=refused" and person("someone@elsewhere.net") is None


@pytest.mark.parametrize("method, path", [
    ("post", "/api/auth/login"), ("post", "/api/auth/register"), ("post", "/api/auth/verify-email"),
    ("post", "/api/auth/resend-verification"), ("post", "/api/auth/forgot-password"),
    ("post", "/api/auth/reset-password"), ("put", "/api/auth/password"),
])
def test_the_portals_own_password_routes_are_gone(method, path):
    assert getattr(browser(), method)(path, json={}).status_code == 404


def test_the_admin_reset_email_is_gone(monkeypatch, admin):
    sign_in(monkeypatch)
    assert admin.post(f"/api/admin/users/{person().id}/send-reset").status_code == 404


def test_config_and_sign_out_tell_the_page_about_cognito(monkeypatch):
    client = browser()
    settings = client.get("/api/auth/config").json()
    assert settings["cognito"] is True
    assert settings["cognito_logout_url"] == client.post("/api/auth/logout").json()["logout_url"]
    url = urlparse(client.post("/api/auth/logout").json()["logout_url"])
    q = parse_qs(url.query)
    assert url.path == "/logout" and q["client_id"] == [CLIENT] and q["logout_uri"] == ["https://portal.example.org/"]


def test_without_cognito_the_new_routes_do_not_exist(monkeypatch):
    monkeypatch.setattr(config, "USE_COGNITO", False)
    client = browser()
    assert client.get("/api/auth/start").status_code == 404
    assert client.get("/api/auth/callback").status_code == 404
    assert client.post("/api/auth/logout").json()["logout_url"] is None
