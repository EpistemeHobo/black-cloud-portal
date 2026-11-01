import io
import json
import zipfile

from tests.conftest import login


def unzip(content: bytes) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        return {n: z.read(n).decode("utf-8") for n in z.namelist()}


def as_import(files: dict[str, str]) -> dict:
    """What the frontend sends after reading the folder."""
    root = next(n for n in files if n.endswith("system.json")).rsplit("/", 1)[0]
    dirs = {"1-what": "what", "2-where": "where", "3-how": "how", "4-watch": "watch",
            "5-deps": "deps", "6-who": "who", "7-progress": "progress"}
    docs = []
    for name, content in files.items():
        parts = name[len(root) + 1:].split("/")
        if len(parts) == 3 and parts[0] == "docs" and parts[2].endswith(".md"):
            docs.append({"question": dirs[parts[1]], "filename": parts[2], "content": content})
    return {"data": json.loads(files[f"{root}/system.json"]), "docs": docs}


def make_full_system(owner) -> str:
    me = owner.get("/api/auth/me").json()["person"]["id"]
    senior = owner.post("/api/people", json={"name": "Senior", "email": "senior@example.org"}).json()["id"]
    minio = owner.post("/api/systems", json={"name": "MinIO", "type": "Infrastructure"}).json()["id"]
    sid = owner.post("/api/systems", json={
        "name": "Cohort Builder", "type": "Web app", "description": "Builds cohorts.", "if_down": "Research stops.",
    }).json()["id"]
    owner.patch(f"/api/systems/{sid}", json={
        "deploy_steps": "Merge\n`make deploy`", "criticality": "High", "hosting": ["HPC"],
        "server_or_location": "vm-7", "guide_nothing": ["progress"],
    })
    owner.put(f"/api/systems/{sid}/roles", json=[
        {"person_id": me, "role": "technical_owner"},
        {"person_id": senior, "role": "previous_owner", "reachable_until": "2027-01-31", "note": "Billing"},
    ])
    owner.put(f"/api/systems/{sid}/links", json=[{"kind": "source_repo", "url": "https://gitlab.example.org/c"}])
    owner.put(f"/api/systems/{sid}/dependencies", json=[
        {"to_system_id": minio, "note": "files"}, {"external_name": "Google Maps"},
    ])
    owner.put(f"/api/systems/{sid}/watch-outs", json=[
        {"kind": "chore", "text": "Renew cert", "how_often": "yearly", "next_due": "2027-03-01"},
    ])
    owner.put(f"/api/systems/{sid}/checklist/A1", json={"status": "done", "evidence": "docs/brief.md"})
    owner.post(f"/api/systems/{sid}/docs", json={"question": "how", "filename": "runbook.md", "content": "# Runbook\n"})
    return sid


def test_export_is_a_folder_with_json_and_markdown(owner):
    sid = make_full_system(owner)
    r = owner.get(f"/api/systems/{sid}/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert f'filename="{sid}-cohort-builder.zip"' in r.headers["content-disposition"]
    files = unzip(r.content)
    root = f"{sid}-cohort-builder"
    assert set(files) == {f"{root}/system.json", f"{root}/README.md", f"{root}/docs/3-how/runbook.md"}
    data = json.loads(files[f"{root}/system.json"])
    assert data["format"] == "cloud-dev-portal/system" and data["system"]["name"] == "Cohort Builder"
    assert data["catalog"]["server_or_location"] == "vm-7"
    assert "content" not in json.dumps(data["guide"])  # file contents stay in the .md files


def test_only_editors_export(owner, other):
    sid = make_full_system(owner)
    assert other.get(f"/api/systems/{sid}/export").status_code == 403


def test_import_registers_a_new_system_with_everything(owner):
    sid = make_full_system(owner)
    payload = as_import(unzip(owner.get(f"/api/systems/{sid}/export").content))

    newcomer = login("newcomer@example.org", "Newcomer")
    r = newcomer.post("/api/systems/import", json=payload)
    assert r.status_code == 201, r.text
    new = r.json()
    assert new["id"] not in (sid, "APP-001") and new["name"] == "Cohort Builder"
    assert new["guide_fields"]["deploy_steps"] == "Merge\n`make deploy`"
    assert new["guide"]["answered"] == new["guide"]["total"] == 7
    assert new["fields"]["criticality"] == "High" and new["fields"]["hosting"] == ["HPC"]
    roles = {(x["person"]["email"], x["role"]) for x in new["roles"]}
    assert ("newcomer@example.org", "technical_owner") in roles
    assert ("owner@example.org", "technical_owner") in roles
    prev = next(x for x in new["roles"] if x["role"] == "previous_owner")
    assert (prev["reachable_until"], prev["note"]) == ("2027-01-31", "Billing")
    deps = {(d["name"], d["external"]) for d in new["depends_on"]}
    assert deps == {("MinIO", False), ("Google Maps", True)}
    assert new["watch_outs"][0]["next_due"] == "2027-03-01"
    assert [(d["question"], d["filename"]) for d in new["docs"]] == [("how", "runbook.md")]
    checklist = {i["code"]: i["status"] for i in newcomer.get(f"/api/systems/{new['id']}/checklist").json()["items"]}
    assert checklist["A1"] == "done"


def test_import_rejects_other_files(owner):
    assert owner.post("/api/systems/import", json={"data": {"format": "something", "version": 1,
                      "system": {"name": "X", "type": "Script"}}}).status_code == 422
    bad_type = {"format": "cloud-dev-portal/system", "version": 1, "system": {"name": "X", "type": "Robot"}}
    assert owner.post("/api/systems/import", json={"data": bad_type}).status_code == 422
    newer = {"format": "cloud-dev-portal/system", "version": 99, "system": {"name": "X", "type": "Script"}}
    assert owner.post("/api/systems/import", json={"data": newer}).status_code == 422
    assert owner.get("/api/systems").json() == []
