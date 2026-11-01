from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import System
from tests.conftest import login


def reasons_for(client, system_id):
    entry = next((a for a in client.get("/api/dashboard").json()["attention"] if a["id"] == system_id), None)
    return [] if entry is None else [r["code"] for r in entry["reasons"]]


def make_old(system_id, days=60):
    with SessionLocal() as db:
        db.get(System, system_id).created_at = datetime.now(timezone.utc) - timedelta(days=days)
        db.commit()


def test_dashboard_needs_sign_in():
    from fastapi.testclient import TestClient
    from app.main import app
    assert TestClient(app).get("/api/dashboard").status_code == 401


def test_important_system_with_one_fixer_is_flagged(owner):
    sid = owner.post("/api/systems", json={"name": "LIMS", "type": "Web app"}).json()["id"]
    owner.patch(f"/api/systems/{sid}", json={"criticality": "Critical"})
    assert "single_point" in reasons_for(owner, sid)
    assert "no_backup_owner" in reasons_for(owner, sid)

    me = owner.get("/api/auth/me").json()["person"]["id"]
    backup = owner.post("/api/people", json={"name": "Backup", "email": "backup@example.org"}).json()["id"]
    owner.put(f"/api/systems/{sid}/roles", json=[
        {"person_id": me, "role": "technical_owner"}, {"person_id": backup, "role": "backup_owner"},
    ])
    codes = reasons_for(owner, sid)
    assert "single_point" not in codes and "no_backup_owner" not in codes


def test_low_criticality_with_one_fixer_is_not_a_single_point(owner):
    sid = owner.post("/api/systems", json={"name": "Script", "type": "Script"}).json()["id"]
    owner.patch(f"/api/systems/{sid}", json={"criticality": "Low"})
    assert "single_point" not in reasons_for(owner, sid)


def test_live_system_needs_a_runbook_and_backups(owner):
    sid = owner.post("/api/systems", json={"name": "Live app", "type": "Web app", "step": 6}).json()["id"]
    codes = reasons_for(owner, sid)
    assert "no_runbook" in codes and "no_backups" in codes

    owner.put(f"/api/systems/{sid}/links", json=[{"kind": "runbook", "url": "https://drive.example.org/runbook"}])
    owner.patch(f"/api/systems/{sid}", json={"backup": "Yes"})
    codes = reasons_for(owner, sid)
    assert "no_runbook" not in codes and "no_backups" not in codes


def test_runbook_and_backup_rules_wait_until_live(owner):
    sid = owner.post("/api/systems", json={"name": "New app", "type": "Web app", "step": 3}).json()["id"]
    codes = reasons_for(owner, sid)
    assert "no_runbook" not in codes and "no_backups" not in codes


def test_confirming_the_page_clears_the_flag(owner):
    sid = owner.post("/api/systems", json={"name": "App", "type": "Web app"}).json()["id"]
    assert "never_confirmed" in reasons_for(owner, sid)
    owner.post(f"/api/systems/{sid}/verify")
    assert "never_confirmed" not in reasons_for(owner, sid)


def test_reviews_are_expected_once_a_system_is_a_month_old(owner, other):
    sid = owner.post("/api/systems", json={"name": "App", "type": "Web app"}).json()["id"]
    assert "never_reviewed" not in reasons_for(owner, sid)
    make_old(sid)
    assert "never_reviewed" in reasons_for(owner, sid)
    other.post(f"/api/systems/{sid}/reviews", json={
        "review_date": datetime.now(timezone.utc).date().isoformat(), "place": "Team meeting", "note": "Fine.",
    })
    assert "never_reviewed" not in reasons_for(owner, sid)

    old = (datetime.now(timezone.utc).date() - timedelta(days=200)).isoformat()
    sid2 = owner.post("/api/systems", json={"name": "App 2", "type": "Web app"}).json()["id"]
    other.post(f"/api/systems/{sid2}/reviews", json={"review_date": old, "place": "Team meeting", "note": "Old."})
    assert "stale_review" in reasons_for(owner, sid2)


def test_most_serious_systems_come_first(owner):
    minor = owner.post("/api/systems", json={"name": "Minor", "type": "Script"}).json()["id"]
    major = owner.post("/api/systems", json={"name": "Major", "type": "Web app", "step": 6}).json()["id"]
    ids = [a["id"] for a in owner.get("/api/dashboard").json()["attention"]]
    assert ids.index(major) < ids.index(minor)


def test_retired_systems_are_left_out(owner):
    sid = owner.post("/api/systems", json={"name": "Old", "type": "Web app", "step": 6}).json()["id"]
    owner.patch(f"/api/systems/{sid}", json={"lifecycle_state": "Retired"})
    data = owner.get("/api/dashboard").json()
    assert sid not in [a["id"] for a in data["attention"]]
    assert data["overview"]["total"] == 0


def test_overview_counts(owner):
    unit = owner.post("/api/units", json={"name": "Genomics"}).json()["id"]
    for name, type_, step in (("A", "Web app", 1), ("B", "Web app", 6), ("C", "Script", 6)):
        owner.post("/api/systems", json={"name": name, "type": type_, "step": step, "owning_unit_id": unit})
    o = owner.get("/api/dashboard").json()["overview"]
    assert (o["total"], o["live"], o["in_development"]) == (3, 2, 1)
    assert {s["step"]: s["count"] for s in o["by_step"]} == {1: 1, 2: 0, 3: 0, 4: 0, 5: 0, 6: 2, 7: 0}
    assert o["by_type"][0] == {"label": "Web app", "count": 2}
    assert o["by_unit"] == [{"label": "Genomics", "count": 3}]
    assert o["required_due"] > 0 and 0 <= o["required_finished"] <= o["required_due"]
