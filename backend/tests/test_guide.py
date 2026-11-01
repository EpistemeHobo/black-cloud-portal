from datetime import date, timedelta

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db import engine
from tests.conftest import BACKEND, login
from tests.test_dashboard import reasons_for


def guide(client, sid):
    return {q["key"]: q for q in client.get(f"/api/systems/{sid}").json()["guide"]["questions"]}


def test_a_new_system_starts_with_only_who_to_ask_answered(system):
    g = system["guide"]
    assert (g["answered"], g["total"]) == (1, 7)
    assert [q["key"] for q in g["questions"] if q["answered"]] == ["who"]


def test_creating_a_system_can_answer_question_one(owner):
    s = owner.post("/api/systems", json={
        "name": "Lab Booking", "type": "Web app",
        "description": "Books lab equipment.", "if_down": "Nobody can book the sequencer.",
    }).json()
    assert {q["key"] for q in s["guide"]["questions"] if q["answered"]} == {"what", "who"}


def test_guide_text_needs_an_editor(system, other, admin):
    sid = system["id"]
    assert other.patch(f"/api/systems/{sid}", json={"deploy_steps": "x"}).status_code == 403
    r = admin.patch(f"/api/systems/{sid}", json={"deploy_steps": "  Merge to main\n`make deploy`  "})
    assert r.json()["guide_fields"]["deploy_steps"] == "Merge to main\n`make deploy`"
    assert guide(admin, sid)["how"]["answered"] is True
    assert guide(admin, sid)["how"]["updated_by"] == "Admin"


def test_auditors_edit_catalog_info_but_not_the_guide(system, admin):
    sid = system["id"]
    auditor = login("audit@example.org", "Audit")
    audit_id = auditor.get("/api/auth/me").json()["person"]["id"]
    assert auditor.patch(f"/api/systems/{sid}", json={"annual_cost": "1 baht"}).status_code == 403
    admin.patch(f"/api/people/{audit_id}", json={"is_auditor": True})
    me = auditor.get("/api/auth/me").json()["person"]
    assert me["is_auditor"] is True
    r = auditor.patch(f"/api/systems/{sid}", json={"annual_cost": "120,000 baht", "server_or_location": "vm-7"})
    assert r.status_code == 200
    assert r.json()["can_edit"] is False and r.json()["can_edit_catalog"] is True
    assert r.json()["fields"]["server_or_location"] == "vm-7"
    assert auditor.patch(f"/api/systems/{sid}", json={"if_down": "x"}).status_code == 403
    assert auditor.put(f"/api/systems/{sid}/watch-outs", json=[]).status_code == 403


def test_watch_outs_keep_their_ids_and_order(system, owner):
    sid = system["id"]
    r = owner.put(f"/api/systems/{sid}/watch-outs", json=[
        {"kind": "trap", "text": "Don't restart during the nightly import"},
        {"kind": "chore", "text": "Renew the TLS certificate", "how_often": "yearly", "next_due": "2027-03-01"},
    ]).json()
    trap, chore = r["watch_outs"]
    assert (chore["how_often"], chore["next_due"]) == ("yearly", "2027-03-01")
    r = owner.put(f"/api/systems/{sid}/watch-outs", json=[
        {**chore, "text": "Renew the TLS cert"}, {"kind": "trap", "text": "New trap", "how_often": "weekly"},
    ]).json()
    assert [w["text"] for w in r["watch_outs"]] == ["Renew the TLS cert", "New trap"]
    assert r["watch_outs"][0]["id"] == chore["id"]
    # Only chores have a frequency.
    assert r["watch_outs"][1]["how_often"] is None
    assert owner.put(f"/api/systems/{sid}/watch-outs", json=[{"kind": "bug", "text": "x"}]).status_code == 422


def test_ticking_an_open_item_records_who_and_when(system, owner):
    sid = system["id"]
    r = owner.put(f"/api/systems/{sid}/open-items", json=[
        {"kind": "promise", "text": "CSV export", "promised_to": "Genomics team", "due_date": "2026-12-15"},
        {"kind": "work", "text": "Move to Postgres", "promised_to": "ignored"},
    ]).json()
    promise, work = r["open_items"]
    assert promise["promised_to"] == "Genomics team" and work["promised_to"] is None
    r = owner.put(f"/api/systems/{sid}/open-items", json=[{**promise, "done": True}, work]).json()
    assert r["open_items"][0]["done"] is True and r["open_items"][0]["done_by"] == "Owner"
    rows = owner.get(f"/api/systems/{sid}/history").json()
    assert any(h["entity"] == "open_item" and h["field"] == "done_at" for h in rows)


def test_a_list_can_be_marked_as_having_nothing(system, owner):
    sid = system["id"]
    assert owner.patch(f"/api/systems/{sid}", json={"guide_nothing": ["where"]}).status_code == 422
    owner.patch(f"/api/systems/{sid}", json={"guide_nothing": ["progress", "deps"]})
    g = guide(owner, sid)
    assert g["progress"]["answered"] and g["progress"]["nothing"] and g["deps"]["answered"]
    assert g["progress"]["updated_by"] == "Owner"
    # Adding an item clears the mark.
    r = owner.put(f"/api/systems/{sid}/open-items", json=[{"kind": "work", "text": "Finish import"}]).json()
    progress = next(q for q in r["guide"]["questions"] if q["key"] == "progress")
    assert progress["answered"] and not progress["nothing"]
    assert owner.get(f"/api/systems/{sid}").json()["guide"]["answered"] == 3


def test_previous_owner_is_reachable_until_a_date(system, owner):
    sid = system["id"]
    me = owner.get("/api/auth/me").json()["person"]["id"]
    old = owner.post("/api/people", json={"name": "Senior", "email": "senior@example.org"}).json()["id"]
    gone = owner.post("/api/people", json={"name": "Gone", "email": "gone@example.org"}).json()["id"]
    soon = (date.today() + timedelta(days=30)).isoformat()
    past = (date.today() - timedelta(days=1)).isoformat()
    r = owner.put(f"/api/systems/{sid}/roles", json=[
        {"person_id": me, "role": "technical_owner"},
        {"person_id": old, "role": "previous_owner", "reachable_until": soon, "note": "Ask about billing"},
        {"person_id": gone, "role": "previous_owner", "reachable_until": past},
    ]).json()
    roles = {x["person"]["name"]: x for x in r["roles"]}
    assert (roles["Senior"]["reachable_until"], roles["Senior"]["note"], roles["Senior"]["reachable"]) == \
        (soon, "Ask about billing", True)
    assert roles["Gone"]["reachable"] is False
    # A previous owner can't edit, and doesn't count towards the bus factor.
    assert r["bus_factor"] == 1
    assert login("senior@example.org", "Senior").get(f"/api/systems/{sid}").json()["can_edit"] is False


def test_dashboard_nudges_for_the_guide(owner):
    sid = owner.post("/api/systems", json={"name": "Live", "type": "Web app", "step": 6}).json()["id"]
    codes = reasons_for(owner, sid)
    assert "guide_incomplete" in codes and "no_runbook" in codes
    owner.patch(f"/api/systems/{sid}", json={"deploy_steps": "Merge to main"})
    assert "no_runbook" not in reasons_for(owner, sid)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    owner.put(f"/api/systems/{sid}/watch-outs", json=[
        {"kind": "chore", "text": "Renew cert", "how_often": "yearly", "next_due": yesterday},
    ])
    assert "overdue_chore" in reasons_for(owner, sid)


def test_migration_moves_old_fields_into_the_guide():
    cfg = Config(str(BACKEND / "alembic.ini"))
    command.downgrade(cfg, "26254c4c2215")
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO system (id, name, type, step, lifecycle_state, business_purpose, known_issues, "
            "roadmap_notes, created_at, updated_at) VALUES ('APP-001', 'Old', 'Web app', 6, 'Active', "
            "'Booking stops', 'Slow on Mondays', 'Move to Postgres', '2026-01-01', '2026-01-01')"
        ))
        conn.execute(text("INSERT INTO link (system_id, kind, url) VALUES ('APP-001', 'other', 'https://x.org')"))
    command.upgrade(cfg, "head")
    with engine.begin() as conn:
        assert conn.execute(text("SELECT if_down FROM system")).scalar() == "Booking stops"
        assert conn.execute(text("SELECT kind, text FROM watch_out")).one() == ("trap", "Slow on Mondays")
        assert conn.execute(text("SELECT kind, text FROM open_item")).one() == ("work", "Move to Postgres")
        # Rebuilding the system table must not cascade-delete what points at it.
        assert conn.execute(text("SELECT count(*) FROM link")).scalar() == 1


def test_markdown_files_attach_to_a_question(system, owner, other):
    sid = system["id"]
    r = owner.post(f"/api/systems/{sid}/docs", json={
        "question": "how", "filename": r"C:\fakepath\runbook.md", "content": "# Runbook\n\n- step",
    })
    assert r.status_code == 200, r.text
    doc = r.json()["docs"][0]
    assert (doc["question"], doc["filename"], doc["updated_by"]) == ("how", "runbook.md", "Owner")
    # A file answers its question.
    how = next(q for q in r.json()["guide"]["questions"] if q["key"] == "how")
    assert how["answered"] and how["updated_by"] == "Owner"
    # Same name, same question: replaced, not duplicated.
    r = owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "runbook.md", "content": "v2"})
    assert [(d["filename"], d["content"]) for d in r.json()["docs"]] == [("runbook.md", "v2")]
    rows = {(h["entity"], h["field"], h["new_value"]) for h in owner.get(f"/api/systems/{sid}/history").json()}
    assert ("guide_doc", "added", "runbook.md") in rows and ("guide_doc", "replaced", "runbook.md") in rows

    assert other.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "x.md", "content": ""}).status_code == 403
    assert owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "x.pdf", "content": ""}).status_code == 422
    assert owner.post(f"/api/systems/{sid}/docs", json={"question": "nope", "filename": "x.md", "content": ""}).status_code == 422
    assert owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "x.md", "content": "a\x00b"}).status_code == 422

    r = owner.delete(f"/api/systems/{sid}/docs/{doc['id']}").json()
    assert r["docs"] == [] and not next(q for q in r["guide"]["questions"] if q["key"] == "how")["answered"]
    rows = {(h["entity"], h["field"], h["old_value"]) for h in owner.get(f"/api/systems/{sid}/history").json()}
    assert ("guide_doc", "removed", "runbook.md") in rows


def test_only_a_technical_owner_or_admin_deletes_a_system(system, owner, other, admin):
    sid = system["id"]
    me = owner.get("/api/auth/me").json()["person"]["id"]
    dev = login("dev@example.org", "Dev")
    dev_id = dev.get("/api/auth/me").json()["person"]["id"]
    owner.put(f"/api/systems/{sid}/roles", json=[
        {"person_id": me, "role": "technical_owner"}, {"person_id": dev_id, "role": "developer"},
    ])
    assert owner.get(f"/api/systems/{sid}").json()["can_delete"] is True
    assert dev.get(f"/api/systems/{sid}").json()["can_delete"] is False
    assert dev.delete(f"/api/systems/{sid}").status_code == 403
    assert other.delete(f"/api/systems/{sid}").status_code == 403

    other_sys = admin.post("/api/systems", json={"name": "Admin's", "type": "Script"}).json()["id"]
    assert admin.delete(f"/api/systems/{other_sys}").status_code == 204


def test_deleting_a_system(system, owner):
    sid = system["id"]
    user = owner.post("/api/systems", json={"name": "Uses it", "type": "Web app"}).json()["id"]
    owner.put(f"/api/systems/{user}/dependencies", json=[{"to_system_id": sid, "note": "login"}])
    owner.put(f"/api/systems/{sid}/watch-outs", json=[{"kind": "trap", "text": "x"}])
    owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "a.md", "content": "# A"})

    assert owner.delete(f"/api/systems/{sid}").status_code == 204
    assert owner.get(f"/api/systems/{sid}").status_code == 404
    assert sid not in [s["id"] for s in owner.get("/api/systems").json()]
    # The system that used it loses the dependency, and its history says so.
    assert owner.get(f"/api/systems/{user}").json()["depends_on"] == []
    assert any(h["entity"] == "dependency" and h["field"] == "removed"
               for h in owner.get(f"/api/systems/{user}/history").json())
    # One "deleted" row is kept for the deleted system.
    from app.db import SessionLocal
    from app.models import ChangeLog
    with SessionLocal() as db:
        rows = db.query(ChangeLog).filter(ChangeLog.system_id == sid).all()
        assert [(r.field, r.old_value) for r in rows if r.field in ("deleted", "removed")] == [("deleted", "Lab Booking")]
    # Its ID is never given to a new system.
    assert owner.post("/api/systems", json={"name": "New", "type": "Script"}).json()["id"] == "APP-003"


def test_removing_from_a_list_is_recorded(system, owner):
    sid = system["id"]
    owner.put(f"/api/systems/{sid}/links", json=[{"kind": "other", "url": "https://a.example.org"}])
    owner.put(f"/api/systems/{sid}/watch-outs", json=[{"kind": "trap", "text": "Fragile import"}])
    owner.put(f"/api/systems/{sid}/links", json=[])
    owner.put(f"/api/systems/{sid}/watch-outs", json=[])
    rows = [(h["entity"], h["field"]) for h in owner.get(f"/api/systems/{sid}/history").json()]
    assert rows.count(("link", "removed")) == 1 and rows.count(("watch_out", "removed")) == 1
