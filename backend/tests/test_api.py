from fastapi.testclient import TestClient

from app.fields import FIELDS
from app.main import app
from app.models import System
from tests.conftest import login


def test_every_field_is_a_system_column():
    columns = set(System.__table__.columns.keys())
    assert set(FIELDS) <= columns


def test_api_needs_sign_in():
    client = TestClient(app)
    assert client.get("/api/systems").status_code == 401
    assert client.get("/api/auth/me").json() == {"person": None}


def test_creator_becomes_technical_owner(system):
    assert system["id"] == "APP-001"
    assert system["step"] == 1
    assert [(r["role"], r["person"]["name"]) for r in system["roles"]] == [("technical_owner", "Owner")]
    assert system["can_edit"] is True


def test_only_editors_can_change_a_system(system, other):
    sid = system["id"]
    assert other.get(f"/api/systems/{sid}").json()["can_edit"] is False
    assert other.patch(f"/api/systems/{sid}", json={"description": "x"}).status_code == 403
    assert other.put(f"/api/systems/{sid}/step", json={"step": 3}).status_code == 403


def test_admin_can_change_any_system(system, admin):
    r = admin.patch(f"/api/systems/{system['id']}", json={"description": "Changed by admin"})
    assert r.status_code == 200
    assert r.json()["guide_fields"]["description"] == "Changed by admin"


def test_restricted_fields_are_hidden_from_other_people(system, owner, other):
    sid = system["id"]
    owner.patch(f"/api/systems/{sid}", json={"server_or_location": "vm-prod-07"})
    assert owner.get(f"/api/systems/{sid}").json()["fields"]["server_or_location"] == "vm-prod-07"
    seen = other.get(f"/api/systems/{sid}").json()
    assert "server_or_location" not in seen["fields"]
    assert "server_or_location" in seen["hidden_fields"]
    history = other.get(f"/api/systems/{sid}/history").json()
    row = next(h for h in history if h["field"] == "server_or_location")
    assert row["new_value"] is None and row["hidden"] is True


def test_patch_validates_values(system, owner):
    sid = system["id"]
    assert owner.patch(f"/api/systems/{sid}", json={"criticality": "Very high"}).status_code == 422
    assert owner.patch(f"/api/systems/{sid}", json={"hosting": ["Mars"]}).status_code == 422
    assert owner.patch(f"/api/systems/{sid}", json={"go_live_date": "soon"}).status_code == 422
    assert owner.patch(f"/api/systems/{sid}", json={"id": "APP-999"}).status_code == 422
    r = owner.patch(f"/api/systems/{sid}", json={
        "criticality": "High", "hosting": ["HPC", "HPC"], "go_live_date": "2026-12-01", "aliases": "  ",
    })
    fields = r.json()["fields"]
    assert (fields["criticality"], fields["hosting"], fields["go_live_date"], fields["aliases"]) == \
        ("High", ["HPC"], "2026-12-01", None)


def test_checklist_shows_items_due_at_the_current_step(system, owner):
    data = owner.get(f"/api/systems/{system['id']}/checklist").json()
    due = {i["code"] for i in data["items"] if i["due"]}
    assert due == {"A1", "A2"}
    assert data["summary"] == {"required_due": 2, "required_finished": 0, "open_codes": ["A1", "A2"]}
    a1 = next(i for i in data["items"] if i["code"] == "A1")
    assert a1["kb_url"] == "https://kb.example.org/development-basics/#project-brief"


def test_auto_items_follow_the_system(system, owner):
    sid = system["id"]
    owner.put(f"/api/systems/{sid}/links", json=[{"kind": "source_repo", "url": "https://gitlab.example.org/x"}])
    items = {i["code"]: i for i in owner.get(f"/api/systems/{sid}/checklist").json()["items"]}
    assert items["A2"]["status"] == "done" and items["A2"]["auto"] is True
    assert owner.put(f"/api/systems/{sid}/checklist/A2", json={"status": "missing"}).status_code == 422


def test_answering_an_item_updates_progress(system, owner):
    sid = system["id"]
    r = owner.put(f"/api/systems/{sid}/checklist/A1", json={"status": "done", "evidence": "docs/brief.md"})
    assert r.status_code == 200
    a1 = next(i for i in r.json()["items"] if i["code"] == "A1")
    assert (a1["status"], a1["evidence"], a1["updated_by"]) == ("done", "docs/brief.md", "Owner")
    assert r.json()["summary"]["required_finished"] == 1


def test_items_that_dont_fit_the_type_are_left_out(owner):
    saas = owner.post("/api/systems", json={"name": "Vendor LIMS", "type": "SaaS", "step": 3}).json()
    codes = {i["code"] for i in owner.get(f"/api/systems/{saas['id']}/checklist").json()["items"]}
    assert "A2" not in codes and "D1" not in codes
    assert {"A1", "C1", "F2"} <= codes


def test_any_step_is_allowed(system, owner):
    # Guide, don't block: moving on with open items is fine.
    r = owner.put(f"/api/systems/{system['id']}/step", json={"step": 6})
    assert r.status_code == 200
    assert r.json()["step"] == 6
    assert r.json()["checklist"]["required_finished"] < r.json()["checklist"]["required_due"]


def test_anyone_can_add_a_review_note_but_only_its_author_removes_it(system, other, owner):
    sid = system["id"]
    notes = other.post(f"/api/systems/{sid}/reviews", json={
        "review_date": "2026-11-05", "place": "Team meeting", "note": "Check MinIO before coding.",
    }).json()
    assert notes[0]["reviewer"]["name"] == "Other" and notes[0]["step"] == 1
    assert owner.delete(f"/api/systems/{sid}/reviews/{notes[0]['id']}").status_code == 403
    assert other.delete(f"/api/systems/{sid}/reviews/{notes[0]['id']}").json() == []


def test_dependencies_show_on_both_systems(system, owner):
    minio = owner.post("/api/systems", json={"name": "MinIO", "type": "Infrastructure"}).json()
    r = owner.put(f"/api/systems/{system['id']}/dependencies", json=[
        {"to_system_id": minio["id"], "note": "File storage"}, {"external_name": "Google Maps API"},
    ])
    assert {d["name"] for d in r.json()["depends_on"]} == {"MinIO", "Google Maps API"}
    used_by = owner.get(f"/api/systems/{minio['id']}").json()["used_by"]
    assert used_by == [{"system_id": system["id"], "name": "Lab Booking", "note": "File storage"}]
    bad = owner.put(f"/api/systems/{system['id']}/dependencies", json=[{"to_system_id": system["id"]}])
    assert bad.status_code == 422


def test_a_system_keeps_a_technical_owner(system, owner):
    me = owner.get("/api/auth/me").json()["person"]["id"]
    r = owner.put(f"/api/systems/{system['id']}/roles", json=[{"person_id": me, "role": "backup_owner"}])
    assert r.status_code == 422


def test_owners_can_name_people_who_havent_signed_in(system, owner):
    me = owner.get("/api/auth/me").json()["person"]["id"]
    new = owner.post("/api/people", json={"name": "Tong", "email": "Tong@Example.org"}).json()
    r = owner.put(f"/api/systems/{system['id']}/roles", json=[
        {"person_id": me, "role": "technical_owner"}, {"person_id": new["id"], "role": "backup_owner"},
    ])
    assert r.json()["bus_factor"] == 2
    # When Tong signs up, the existing record is used, not a duplicate.
    tong = login("tong@example.org", "Tong")
    assert tong.get(f"/api/systems/{system['id']}").json()["can_edit"] is True


def test_links_must_be_web_addresses(system, owner):
    r = owner.put(f"/api/systems/{system['id']}/links", json=[{"kind": "other", "url": "javascript:alert(1)"}])
    assert r.status_code == 422


def test_history_records_who_changed_what(system, owner):
    sid = system["id"]
    owner.patch(f"/api/systems/{sid}", json={"criticality": "Low"})
    owner.patch(f"/api/systems/{sid}", json={"criticality": "High"})
    rows = [h for h in owner.get(f"/api/systems/{sid}/history").json() if h["field"] == "criticality"]
    assert [(r["old_value"], r["new_value"], r["changed_by"]) for r in rows] == \
        [("Low", "High", "Owner"), (None, "Low", "Owner")]


def test_only_admins_edit_checklist_items(owner, admin):
    assert owner.patch("/api/standards/items/A1", json={"from_step": 2}).status_code == 403
    r = admin.patch("/api/standards/items/A1", json={"from_step": 2, "kb_path": "/new/page/"})
    assert (r.json()["from_step"], r.json()["kb_path"]) == (2, "new/page/")


def test_new_systems_get_increasing_ids(owner):
    ids = [owner.post("/api/systems", json={"name": f"S{i}", "type": "Script"}).json()["id"] for i in range(3)]
    assert ids == ["APP-001", "APP-002", "APP-003"]


def test_history_includes_added_records(system, owner, other):
    sid = system["id"]
    owner.put(f"/api/systems/{sid}/links", json=[{"kind": "brief", "url": "https://drive.example.org/brief"}])
    owner.put(f"/api/systems/{sid}/checklist/A1", json={"status": "done", "evidence": "docs/brief.md"})
    other.post(f"/api/systems/{sid}/reviews", json={"review_date": "2026-11-05", "place": "Team meeting", "note": "OK to start."})
    rows = {(h["entity"], h["field"], h["new_value"], h["changed_by"]) for h in owner.get(f"/api/systems/{sid}/history").json()}
    assert ("link", "added", "brief: https://drive.example.org/brief", "Owner") in rows
    assert ("checklist", "status", "done", "Owner") in rows
    assert ("checklist", "evidence", "docs/brief.md", "Owner") in rows
    assert ("review", "added", "OK to start.", "Other") in rows
    assert ("role", "added", "technical_owner: Owner", "Owner") in rows


def test_nextjs_prefetch_files_are_found(tmp_path):
    from fastapi import FastAPI
    from app.main import FrontendFiles
    (tmp_path / "system" / "__next.system").mkdir(parents=True)
    (tmp_path / "system" / "__next.system" / "__PAGE__.txt").write_text("page")
    (tmp_path / "404.html").write_text("not found")
    from fastapi import FastAPI
    site = FastAPI()
    site.mount("/", FrontendFiles(directory=tmp_path, html=True))
    client = TestClient(site)
    assert client.get("/system/__next.system.__PAGE__.txt").text == "page"
    assert client.get("/system/missing.txt").status_code == 404


def test_health_reports_idle_time_but_does_not_count_itself(monkeypatch):
    from app.routers import meta
    client = TestClient(app)
    monkeypatch.setattr(meta, "last_activity", meta.time.monotonic() - 3600)
    assert client.get("/api/health").json() == {"status": "ok", "idle_seconds": 3600}
    client.get("/api/meta")  # any other request is someone using the portal
    assert client.get("/api/health").json()["idle_seconds"] == 0


def test_redirects_stay_relative_behind_a_proxy(tmp_path):
    from fastapi import FastAPI
    from app.main import FrontendFiles
    (tmp_path / "system").mkdir()
    (tmp_path / "system" / "index.html").write_text("page")
    site = FastAPI()
    site.mount("/", FrontendFiles(directory=tmp_path, html=True))
    client = TestClient(site, base_url="http://app-behind-proxy.internal")
    r = client.get("/system?id=APP-001", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/system/?id=APP-001"


def test_only_the_proxy_gets_in_when_a_secret_is_set(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "ORIGIN_VERIFY_SECRET", "s3cret")
    client = TestClient(app)
    assert client.get("/api/meta").status_code == 403
    assert client.get("/api/meta", headers={"X-Origin-Verify": "wrong"}).status_code == 403
    assert client.get("/api/meta", headers={"X-Origin-Verify": "s3cret"}).status_code == 401  # through, not signed in
    assert client.get("/api/health").status_code == 200  # Beanstalk and the sleep job call it directly
