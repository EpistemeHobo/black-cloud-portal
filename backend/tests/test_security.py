"""The secrets vault, push protection, leak alerts, masking and the scheduled scan.

Fake secrets are put together at run time, so this file itself holds nothing that
looks like a real one to a scanner (ours, GitLab's or GitHub's).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import leak_scan
from app.db import SessionLocal
from app.models import ChangeLog, Person, SecretAlert, SecretScanRun, System, SystemSecret

from conftest import OUTBOX, login

GITHUB = "ghp" + "_" + "Zq8Lr2Xc7Vn4Bm1Kd6Hs9Tf3Gp5Jw0Ya2Ue7"
AWS = "AKIA" + "Q3XWZ7RB2LMN4KDS"
PRIVATE_KEY = ("-----BEGIN RSA " + "PRIVATE KEY-----\n" + "MIIEowIBAAKCAQEAu1SU1LfVLPHCozMxH2Mo4lgOEePzNm0tRgeLezV6ffAt0gun\n"
               "VTLw7onLRnrq0/IzW7yWR7QkrmBL7jTKEn5u+qKhbwKfBstIs+bMY2Zkp18gnTxK\n-----END RSA " + "PRIVATE KEY-----")


def _id(system: dict) -> str:
    return system["id"]


# ---------- The scanner on its own ----------

def test_finds_known_secret_kinds():
    text = f"token: {GITHUB}\naws {AWS}\n{PRIVATE_KEY}\npassword = Tr0ub4dor&3x!"
    rules = [f.rule.id for f in leak_scan.find(text)]
    assert rules == ["github_token", "aws_access_key", "private_key", "password_assignment"]
    assert [f.line for f in leak_scan.find(text)][:2] == [1, 2]


def test_skips_examples_references_and_marked_lines():
    text = "\n".join([
        "AKIAIOSFODNN7EXAMPLE",  # AWS's own documentation key
        "password=${DB_PASSWORD}",
        "password: DB_PASSWORD",
        "password = <your password>",
        "password: required",
        f"token {GITHUB}  # portal:ignore-secret",
    ])
    assert leak_scan.find(text) == []


def test_mask_never_shows_the_secret():
    assert leak_scan.mask(GITHUB) == "ghp_…e7"
    assert GITHUB not in leak_scan.mask(GITHUB)
    assert leak_scan.mask("hunter22!") == "…"
    assert "PRIVATE KEY" in leak_scan.mask(PRIVATE_KEY) and "MIIE" not in leak_scan.mask(PRIVATE_KEY)


def test_thai_password_and_connection_url():
    found = leak_scan.find("รหัสผ่าน: Kx9!pQ2#vz\npostgres://app:N0tS0Secret99@db.internal:5432/app")
    assert [f.rule.id for f in found] == ["password_thai", "url_password"]
    assert found[1].secret == "N0tS0Secret99"


# ---------- Push protection and alerts ----------

def test_save_with_secret_is_refused_until_confirmed(owner, system):
    url = f"/api/systems/{_id(system)}"
    r = owner.patch(url, json={"run_steps": f"export GITHUB_TOKEN={GITHUB}"})
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["code"] == "secret_detected"
    assert detail["findings"][0]["rule"] == "github_token"
    assert GITHUB not in r.text  # the refusal doesn't echo the secret back
    assert owner.get(url).json()["guide_fields"]["run_steps"] is None

    r = owner.patch(url + "?allow_secrets=true", json={"run_steps": f"export GITHUB_TOKEN={GITHUB}"})
    assert r.status_code == 200
    assert r.json()["security"]["open_alerts"] == 1
    alerts = owner.get(f"{url}/secret-alerts").json()
    assert alerts[0]["rule"] == "github_token" and alerts[0]["source"] == "save"
    assert alerts[0]["location_label"].endswith("รันบนเครื่องตัวเอง")

    # The known leak doesn't block the next, unrelated edit.
    assert owner.patch(url, json={"if_down": "Bookings stop."}).status_code == 200


def test_secret_is_masked_for_people_outside_the_system(owner, other, system):
    url = f"/api/systems/{_id(system)}"
    owner.patch(url + "?allow_secrets=true", json={"deploy_steps": f"git clone https://x:{GITHUB}@github.com/a/b"})
    assert GITHUB in owner.get(url).json()["guide_fields"]["deploy_steps"]
    seen = other.get(url).json()
    assert GITHUB not in seen["guide_fields"]["deploy_steps"]
    assert leak_scan.REDACTED in seen["guide_fields"]["deploy_steps"]
    assert seen["security"] == {"can_list": False, "can_use": False}
    # Nor in the list of systems.
    owner.patch(url + "?allow_secrets=true", json={"description": f"Token {GITHUB}"})
    listed = other.get("/api/systems").json()[0]["description"]
    assert GITHUB not in listed and leak_scan.REDACTED in listed
    assert GITHUB in owner.get("/api/systems").json()[0]["description"]
    # Nor in the history.
    history = other.get(f"{url}/history").text
    assert GITHUB not in history and leak_scan.REDACTED in history
    assert other.get(f"{url}/secret-alerts").status_code == 403


def test_false_positive_shows_the_text_again(owner, other, system):
    url = f"/api/systems/{_id(system)}"
    owner.patch(url + "?allow_secrets=true", json={"description": f"Example token {GITHUB}"})
    alert = owner.get(f"{url}/secret-alerts").json()[0]
    r = owner.put(f"{url}/secret-alerts/{alert['id']}", json={"resolution": "false_positive", "note": "doc sample"})
    assert r.json()[0]["status"] == "resolved"
    assert GITHUB in other.get(url).json()["guide_fields"]["description"]
    assert owner.get(url).json()["security"]["open_alerts"] == 0
    # Reopening hides it again.
    owner.put(f"{url}/secret-alerts/{alert['id']}", json={"resolution": None})
    assert GITHUB not in other.get(url).json()["guide_fields"]["description"]


def test_attached_file_with_private_key(owner, system):
    url = f"/api/systems/{_id(system)}/docs"
    body = {"question": "how", "filename": "runbook.md", "content": f"# Deploy\n\n{PRIVATE_KEY}\n"}
    r = owner.post(url, json=body)
    assert r.status_code == 422 and r.json()["detail"]["findings"][0]["location"] == "ไฟล์แนบ runbook.md"
    assert owner.get(f"/api/systems/{_id(system)}").json()["docs"] == []

    assert owner.post(url + "?allow_secrets=true", json=body).status_code == 200
    alert = owner.get(f"/api/systems/{_id(system)}/secret-alerts").json()[0]
    assert alert["location_kind"] == "doc" and alert["severity"] == "critical" and alert["line"] == 3

    # Taking the key out of the file: the alert stays open, marked as gone from the text.
    body["content"] = "# Deploy\n\nThe key is in the vault.\n"
    owner.post(url, json=body)
    alert = owner.get(f"/api/systems/{_id(system)}/secret-alerts").json()[0]
    assert alert["status"] == "open" and alert["still_present"] is False


def test_new_alert_emails_the_other_people_on_the_system(owner, system):
    dev = login("dev@example.org", "Dev")
    with SessionLocal() as db:
        dev_id = db.scalar(select(Person.id).where(Person.email == "dev@example.org"))
        owner_id = db.scalar(select(Person.id).where(Person.email == "owner@example.org"))
    owner.put(f"/api/systems/{_id(system)}/roles", json=[
        {"person_id": owner_id, "role": "technical_owner"}, {"person_id": dev_id, "role": "developer"}])
    OUTBOX.clear()
    owner.patch(f"/api/systems/{_id(system)}?allow_secrets=true", json={"run_steps": f"AWS key {AWS}"})
    assert [m["to"] for m in OUTBOX] == ["dev@example.org"]  # not the person who saved it
    assert AWS not in OUTBOX[0]["text"] and "AKIA…" in OUTBOX[0]["text"]
    assert dev.get(f"/api/systems/{_id(system)}/secret-alerts").json()[0]["rule"] == "aws_access_key"


def test_masked_text_cannot_be_saved_over_the_real_one(owner, system):
    auditor = login("auditor@example.org", "Auditor")
    with SessionLocal() as db:
        db.scalar(select(Person).where(Person.email == "auditor@example.org")).is_auditor = True
        db.commit()
    url = f"/api/systems/{_id(system)}"
    owner.patch(url + "?allow_secrets=true", json={"integrations_apis": f"Slack via {GITHUB}"})
    masked = auditor.get(url).json()["fields"]["integrations_apis"]
    assert leak_scan.REDACTED in masked
    r = auditor.patch(url, json={"integrations_apis": masked + " and email"})
    assert r.status_code == 422
    assert GITHUB in owner.get(url).json()["fields"]["integrations_apis"]


# ---------- The vault ----------

def test_vault_only_for_the_systems_people(owner, other, admin, system):
    url = f"/api/systems/{_id(system)}/secrets"
    r = owner.post(url, json={"name": "DB_PASSWORD", "environment": "Prod", "value": "s3cr3t-Value-1"})
    assert r.status_code == 201, r.text
    item = r.json()["items"][0]
    assert item["name"] == "DB_PASSWORD" and "value" not in item
    assert r.json()["access"][0]["email"] == "owner@example.org"

    with SessionLocal() as db:
        row = db.scalar(select(SystemSecret))
        assert "s3cr3t-Value-1" not in row.ciphertext

    assert owner.post(f"{url}/{item['id']}/reveal").json() == {"value": "s3cr3t-Value-1"}
    assert other.get(url).status_code == 403
    assert other.post(f"{url}/{item['id']}/reveal").status_code == 403
    # Admins oversee the names, not the values.
    assert admin.get(url).json()["items"][0]["name"] == "DB_PASSWORD"
    assert admin.post(f"{url}/{item['id']}/reveal").status_code == 403

    # Every reveal is in the history, which only the system's people and admins read in full.
    rows = owner.get(f"/api/systems/{_id(system)}/history").json()
    assert any(r["entity"] == "secret" and r["field"] == "revealed" and r["entity_id"] == "DB_PASSWORD" for r in rows)
    hidden = [r for r in other.get(f"/api/systems/{_id(system)}/history").json() if r["entity"] == "secret"]
    assert hidden and all(r["hidden"] and r["entity_id"] == "" for r in hidden)


def test_vault_rotate_rename_and_delete(owner, system):
    url = f"/api/systems/{_id(system)}/secrets"
    sid = owner.post(url, json={"name": "API_KEY", "value": "first-value-123"}).json()["items"][0]["id"]
    assert owner.post(url, json={"name": "API_KEY", "value": "x" * 10}).status_code == 409
    r = owner.put(f"{url}/{sid}", json={"name": "PARTNER_API_KEY", "environment": "Staging", "value": "second-value-456"})
    assert r.json()["items"][0]["name"] == "PARTNER_API_KEY"
    assert owner.post(f"{url}/{sid}/reveal").json()["value"] == "second-value-456"
    assert owner.delete(f"{url}/{sid}").json()["items"] == []


def test_vault_value_pasted_in_plain_text_is_caught(owner, system):
    owner.post(f"/api/systems/{_id(system)}/secrets", json={"name": "SMTP", "value": "plain-Mail-Pass-77"})
    r = owner.patch(f"/api/systems/{_id(system)}", json={"run_steps": "login with plain-Mail-Pass-77"})
    assert r.status_code == 422 and r.json()["detail"]["findings"][0]["rule"] == "vault_value"


def test_vault_value_already_in_text_gets_an_alert(owner, system):
    owner.patch(f"/api/systems/{_id(system)}", json={"if_down": "Use the backup login: opensesame-42x"})
    owner.post(f"/api/systems/{_id(system)}/secrets", json={"name": "BACKUP_LOGIN", "value": "opensesame-42x"})
    alerts = owner.get(f"/api/systems/{_id(system)}/secret-alerts").json()
    assert [a["rule"] for a in alerts] == ["vault_value"]


# ---------- The scheduled scan ----------

def test_full_scan_finds_what_got_past_the_save_checks(owner, admin, system):
    # Written straight into the database, as by an old version or a bulk import.
    with SessionLocal() as db:
        db.get(System, _id(system)).backup_frequency_and_location = f"s3 sync with key {AWS}"
        db.commit()
    assert admin.post("/api/admin/secret-scans").status_code == 202
    runs = admin.get("/api/admin/secret-scans").json()["runs"]
    assert runs[0]["trigger"] == "manual" and runs[0]["new_alerts"] == 1 and runs[0]["error"] is None
    alert = owner.get(f"/api/systems/{_id(system)}/secret-alerts").json()[0]
    assert alert["source"] == "manual" and alert["rule"] == "aws_access_key"
    # Scanning again adds nothing new.
    admin.post("/api/admin/secret-scans")
    assert admin.get("/api/admin/secret-scans").json()["runs"][0]["new_alerts"] == 0
    assert owner.get("/api/secret-alerts").json()[0]["system_name"] == "Lab Booking"
    assert owner.get("/api/dashboard").json()["attention"][0]["reasons"][0]["code"] == "secret_leak"


def test_scan_due_follows_the_interval(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "SECRET_SCAN_INTERVAL_HOURS", 24)
    with SessionLocal() as db:
        assert leak_scan.scan_due(db)
        db.add(SecretScanRun(trigger="scheduled", started_at=datetime.now(timezone.utc) - timedelta(hours=2)))
        db.commit()
        assert not leak_scan.scan_due(db)
        assert leak_scan.scan_due(db, datetime.now(timezone.utc) + timedelta(hours=23))
    monkeypatch.setattr(config, "SECRET_SCAN_INTERVAL_HOURS", 0)
    with SessionLocal() as db:
        assert not leak_scan.scan_due(db)


def test_alert_never_stores_the_secret(owner, system):
    owner.patch(f"/api/systems/{_id(system)}?allow_secrets=true", json={"run_steps": GITHUB})
    with SessionLocal() as db:
        for alert in db.scalars(select(SecretAlert)):
            assert GITHUB not in " ".join(str(v) for v in vars(alert).values())
        assert not any(GITHUB in (c.new_value or "") for c in db.scalars(
            select(ChangeLog).where(ChangeLog.entity == "secret")))
