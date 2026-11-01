from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import config
from app.auth import MAX_FAILED_LOGINS, seed_admin
from app.db import SessionLocal
from app.main import app
from app.models import Person
from tests.conftest import PASSWORD, login


def sign_up(email="new@example.org", name="New Person", password=PASSWORD):
    return TestClient(app).post("/api/auth/register", json={"name": name, "email": email, "password": password})


def sign_in(email="new@example.org", password=PASSWORD):
    client = TestClient(app)
    return client, client.post("/api/auth/login", json={"email": email, "password": password})


def find(admin, email):
    return next(u for u in admin.get("/api/admin/users").json() if u["email"] == email)


def last_mail(outbox, to):
    return [m for m in outbox if m["to"] == to][-1]


def token_in(mail, name):
    """The token from an emailed link like https://portal/?verify=..."""
    return parse_qs(urlparse(mail["link"]).query)[name][0]


def verify(outbox, email="new@example.org"):
    return TestClient(app).post("/api/auth/verify-email", json={"token": token_in(last_mail(outbox, email), "verify")})


def test_sign_up_then_verify_then_approval(admin, outbox):
    outbox.clear()
    assert sign_up().json() == {"status": "check_email"}
    # Not verified yet: the sign-in page is told so, to offer the link again.
    _, r = sign_in()
    assert r.status_code == 403 and r.json()["detail"]["code"] == "unverified"
    assert admin.get("/api/admin/users/pending-count").json() == {"count": 0}
    user = find(admin, "new@example.org")
    assert admin.patch(f"/api/people/{user['id']}", json={"status": "active"}).status_code == 422

    assert verify(outbox).json() == {"status": "pending"}
    _, r = sign_in()
    assert r.status_code == 403 and "อนุมัติ" in r.json()["detail"]
    assert admin.get("/api/admin/users/pending-count").json() == {"count": 1}

    assert admin.patch(f"/api/people/{user['id']}", json={"status": "active"}).status_code == 200
    # Email is only for confirming the address and resetting passwords.
    assert {m["to"] for m in outbox} == {"new@example.org"}
    client, r = sign_in()
    assert r.status_code == 200
    assert client.get("/api/auth/me").json()["person"]["name"] == "New Person"


def test_sign_up_does_not_reveal_existing_accounts(owner, outbox):
    r = sign_up(email="owner@example.org")
    assert r.status_code == 201 and r.json() == {"status": "check_email"}
    # The real owner is told instead, with a way back in.
    assert "?reset=" in last_mail(outbox, "owner@example.org")["link"]
    # Their password is untouched.
    assert sign_in("owner@example.org")[1].status_code == 200


def test_sign_up_rules(monkeypatch):
    assert sign_up(password="short").status_code == 422
    assert sign_up(email="not-an-email").status_code == 422
    monkeypatch.setattr(config, "ALLOWED_EMAIL_DOMAINS", ["nstda.or.th"])
    assert sign_up(email="x@gmail.com").status_code == 422
    assert sign_up(email="x@ncr.nstda.or.th").status_code == 201
    assert sign_up(email="x@nstda.or.th.evil.com").status_code == 422


def test_resend_verification_is_throttled(outbox):
    sign_up()
    before = len(outbox)
    TestClient(app).post("/api/auth/resend-verification", json={"email": "new@example.org"})
    # Within a minute of the first link, no second email.
    assert len(outbox) == before
    assert TestClient(app).post("/api/auth/resend-verification", json={"email": "nobody@example.org"}).status_code == 200


def test_forgot_password(owner, outbox):
    outbox.clear()
    client = TestClient(app)
    assert client.post("/api/auth/forgot-password", json={"email": "nobody@example.org"}).json() == {"ok": True}
    assert not outbox
    client.post("/api/auth/forgot-password", json={"email": "owner@example.org"})
    token = token_in(last_mail(outbox, "owner@example.org"), "reset")

    assert client.post("/api/auth/reset-password", json={"token": token, "password": "short"}).status_code == 422
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "a-new-password"}).status_code == 200
    assert sign_in("owner@example.org", PASSWORD)[1].status_code == 401
    assert sign_in("owner@example.org", "a-new-password")[1].status_code == 200
    # A reset link works once.
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "another-one!"}).status_code == 400


def test_link_tokens_are_not_sessions_or_each_other(outbox):
    sign_up()
    token = token_in(last_mail(outbox, "new@example.org"), "verify")
    client = TestClient(app)
    client.cookies.set("portal_session", token)
    assert client.get("/api/auth/me").json() == {"person": None}
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "a-new-password"}).status_code == 400
    assert client.post("/api/auth/verify-email", json={"token": "garbage"}).status_code == 400


def test_wrong_password_and_unknown_email_look_the_same(owner):
    _, wrong = sign_in("owner@example.org", "nope-nope-nope")
    _, unknown = sign_in("nobody@example.org", "nope-nope-nope")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_too_many_wrong_passwords_lock_the_account(owner):
    for _ in range(MAX_FAILED_LOGINS):
        assert sign_in("owner@example.org", "wrong-password")[1].status_code == 401
    # Even the right password is refused while locked.
    assert sign_in("owner@example.org", PASSWORD)[1].status_code == 429


def test_suspending_ends_the_session_at_once(admin, owner):
    me = owner.get("/api/auth/me").json()["person"]["id"]
    admin.patch(f"/api/people/{me}", json={"status": "suspended"})
    assert owner.get("/api/systems").status_code == 401
    _, r = sign_in("owner@example.org")
    assert r.status_code == 403 and "ระงับ" in r.json()["detail"]
    admin.patch(f"/api/people/{me}", json={"status": "active"})
    assert sign_in("owner@example.org")[1].status_code == 200


def test_admins_cannot_lock_themselves_out(admin):
    me = admin.get("/api/auth/me").json()["person"]["id"]
    assert admin.patch(f"/api/people/{me}", json={"is_admin": False}).status_code == 422
    assert admin.patch(f"/api/people/{me}", json={"status": "suspended"}).status_code == 422


def test_only_admins_manage_accounts(owner):
    assert owner.get("/api/admin/users").status_code == 403
    assert owner.post("/api/admin/users/1/send-reset").status_code == 403


def test_change_own_password(owner):
    r = owner.put("/api/auth/password", json={"current_password": "wrong-password", "new_password": "brand-new-pass"})
    assert r.status_code == 422
    r = owner.put("/api/auth/password", json={"current_password": PASSWORD, "new_password": "brand-new-pass"})
    assert r.status_code == 200
    assert sign_in("owner@example.org", PASSWORD)[1].status_code == 401
    assert sign_in("owner@example.org", "brand-new-pass")[1].status_code == 200


def test_admin_sends_a_reset_link(admin, owner, outbox):
    me = owner.get("/api/auth/me").json()["person"]["id"]
    assert admin.post(f"/api/admin/users/{me}/send-reset").status_code == 202
    reset = token_in(last_mail(outbox, "owner@example.org"), "reset")
    TestClient(app).post("/api/auth/reset-password", json={"token": reset, "password": "second-password"})
    assert sign_in("owner@example.org", "second-password")[1].status_code == 200


def test_owner_added_earlier_signs_up_into_the_same_record(owner, admin):
    added = owner.post("/api/people", json={"name": "Tong", "email": "tong@example.org"}).json()
    assert added["has_account"] is False
    sign_up("tong@example.org", "Tong Real")
    user = find(admin, "tong@example.org")
    assert user["id"] == added["id"] and user["status"] == "pending" and user["email_verified"] is False


def test_rejecting_a_sign_up(admin, owner, system):
    sign_up("stranger@example.org")
    stranger = find(admin, "stranger@example.org")
    assert admin.delete(f"/api/admin/users/{stranger['id']}").status_code == 204
    assert all(u["email"] != "stranger@example.org" for u in admin.get("/api/admin/users").json())

    # Someone already named as an owner keeps their record, without the account.
    me = owner.get("/api/auth/me").json()["person"]["id"]
    tong = owner.post("/api/people", json={"name": "Tong", "email": "tong@example.org"}).json()["id"]
    owner.put(f"/api/systems/{system['id']}/roles", json=[
        {"person_id": me, "role": "technical_owner"}, {"person_id": tong, "role": "backup_owner"},
    ])
    sign_up("tong@example.org")
    assert admin.delete(f"/api/admin/users/{tong}").status_code == 204
    assert find(admin, "tong@example.org")["status"] == "no_account"
    # Only pending sign-ups can be rejected.
    assert admin.delete(f"/api/admin/users/{me}").status_code == 422


def test_seed_admin(monkeypatch):
    monkeypatch.setattr(config, "SEED_ADMIN_EMAIL", "boss@example.org")
    monkeypatch.setattr(config, "SEED_ADMIN_PASSWORD", "seed-password-1")
    with SessionLocal() as db:
        seed_admin(db)
    client, r = sign_in("boss@example.org", "seed-password-1")
    assert r.status_code == 200 and r.json()["person"]["is_admin"] is True

    # Starting again leaves a changed password alone, unless reset is on.
    client.put("/api/auth/password", json={"current_password": "seed-password-1", "new_password": "changed-pass"})
    with SessionLocal() as db:
        seed_admin(db)
    assert sign_in("boss@example.org", "changed-pass")[1].status_code == 200
    monkeypatch.setattr(config, "SEED_ADMIN_RESET", True)
    with SessionLocal() as db:
        seed_admin(db)
        assert db.scalar(select(Person).where(Person.email == "boss@example.org")).status == "active"
    assert sign_in("boss@example.org", "seed-password-1")[1].status_code == 200


def test_login_helper_users_have_working_accounts():
    client = login("helper@example.org", "Helper")
    assert client.get("/api/auth/me").json()["person"]["email"] == "helper@example.org"


def test_demo_systems_belong_to_the_seed_admin(monkeypatch):
    from app.seed import give_demo_systems_to, seed_demo, seed_standards
    monkeypatch.setattr(config, "SEED_ADMIN_EMAIL", "boss@example.org")
    monkeypatch.setattr(config, "SEED_ADMIN_PASSWORD", "seed-password-1")
    with SessionLocal() as db:
        seed_demo(db, seed_standards(db))
    client, _ = sign_in("boss@example.org", "seed-password-1")
    me = client.get("/api/auth/me").json()["person"]["id"]
    for sid in ("APP-001", "APP-002", "APP-003", "APP-004"):
        roles = client.get(f"/api/systems/{sid}").json()["roles"]
        owners = [r["person"]["id"] for r in roles if r["role"] == "technical_owner"]
        assert owners == [me], sid
        # The demo developers stay on as backups, each once.
        pairs = [(r["person"]["id"], r["role"]) for r in roles]
        assert len(pairs) == len(set(pairs)), sid
    # Running it again changes nothing.
    with SessionLocal() as db:
        give_demo_systems_to(db, db.get(Person, me))
    assert client.get("/api/systems/APP-002").json()["can_edit"] is True


def test_activity_log_records_account_events(admin, outbox):
    sign_up()
    verify(outbox)
    sign_in("new@example.org", "wrong-password")
    user = find(admin, "new@example.org")
    admin.patch(f"/api/people/{user['id']}", json={"status": "active", "is_auditor": True})
    sign_in()
    log = admin.get("/api/admin/activity").json()
    actions = [e["action"] for e in log["events"] if e["subject_email"] == "new@example.org"]
    # Newest first.
    assert actions == ["sign_in", "role_changed", "approved", "sign_in_failed", "email_verified", "sign_up"]
    approved = next(e for e in log["events"] if e["action"] == "approved")
    assert approved["actor_email"] == "admin@example.org"
    assert log["actions"]["approved"] == "อนุมัติบัญชี"


def test_only_admins_see_activity(owner):
    assert owner.get("/api/admin/activity").status_code == 403
