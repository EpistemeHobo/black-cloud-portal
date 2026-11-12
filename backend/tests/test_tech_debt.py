from datetime import date, timedelta

DEBT = {
    "title": "No automated tests for billing",
    "description": "Billing has no tests.",
    "reason": "Launch date.",
    "impact": "A change can break invoices unnoticed.",
    "fix_plan": "Add tests for the invoice run.",
    "risk": "High",
    "effort": "3 days",
    "target_date": (date.today() - timedelta(days=3)).isoformat(),
    "issue_url": "https://gitlab.example.org/a/b/-/issues/1",
}


def test_owner_records_debt_everyone_reads_it(owner, other, system):
    url = f"/api/systems/{system['id']}/tech-debt"
    r = owner.post(url, json=DEBT)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["items"][0]["title"] == DEBT["title"] and body["items"][0]["overdue"] is True
    assert body["summary"] == {"open": 1, "high_open": 1, "overdue": 1}

    seen = other.get(url).json()
    assert seen["items"][0]["impact"] == DEBT["impact"] and seen["can_edit"] is False
    assert other.post(url, json=DEBT).status_code == 403

    detail = owner.get(f"/api/systems/{system['id']}").json()
    assert detail["tech_debt"]["open"] == 1
    reasons = [r["code"] for r in owner.get("/api/dashboard").json()["attention"][0]["reasons"]]
    assert "debt_overdue" in reasons
    assert owner.get("/api/dashboard").json()["overview"]["debt_high_open"] == 1


def test_paying_off_debt(owner, system):
    url = f"/api/systems/{system['id']}/tech-debt"
    debt_id = owner.post(url, json=DEBT).json()["items"][0]["id"]
    r = owner.put(f"{url}/{debt_id}", json={**DEBT, "status": "paid_off"})
    item = r.json()["items"][0]
    assert item["status"] == "paid_off" and item["closed_at"] and item["overdue"] is False
    assert r.json()["summary"]["open"] == 0

    history = owner.get(f"/api/systems/{system['id']}/history").json()
    assert any(h["entity"] == "tech_debt" and h["field"] == "added" for h in history)
    assert any(h["entity"] == "tech_debt" and h["field"] == "status" and h["new_value"] == "paid_off" for h in history)

    assert owner.delete(f"{url}/{debt_id}").json()["items"] == []


def test_all_debt_across_systems(owner, other, system):
    owner.post(f"/api/systems/{system['id']}/tech-debt", json={**DEBT, "risk": "Low", "title": "Old CSS"})
    owner.post(f"/api/systems/{system['id']}/tech-debt", json=DEBT)
    items = other.get("/api/tech-debt").json()
    assert [i["title"] for i in items] == [DEBT["title"], "Old CSS"]  # riskiest first
    assert items[0]["system"]["name"] == "Lab Booking"


def test_bad_values_are_refused(owner, system):
    url = f"/api/systems/{system['id']}/tech-debt"
    assert owner.post(url, json={**DEBT, "risk": "Huge"}).status_code == 422
    assert owner.post(url, json={**DEBT, "issue_url": "javascript:alert(1)"}).status_code == 422
