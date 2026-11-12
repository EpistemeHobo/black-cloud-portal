"""A system's secret boxes and its leak alerts, and the scheduled scan's runs.

Who sees what (docs/decisions/0009-secrets.md):
- The system's people in enums.SECRET_ROLES (owners, backup owner, developers):
  everything, including the boxes' ciphertext, which they open with the box's key.
- Admins: the boxes' names and history and the leak alerts, never the ciphertext.
- Everyone else: neither; and text that looks like a secret is masked for them.

No one can read a box without its key, which the portal never receives (vault.py).
"""
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import leak_scan, vault
from app import systems_service as svc
from app.auth import admin_person, current_person
from app.db import SessionLocal, get_db
from app.enums import ALERT_RESOLUTIONS, NOT_SECRET_RESOLUTIONS, ROLES, SECRET_ROLES
from app.history import log_secret_event
from app.leak_guard import LeakGuard
from app.models import (
    Person, SecretAlert, SecretBox, SecretBoxVersion, SecretScanRun, System, utcnow,
)
from app.schemas import AlertResolveIn, BoxCreate, BoxKeyChange, BoxPatch, BoxVersionIn

router = APIRouter(prefix="/api", tags=["security"])

NO_ACCESS = "เฉพาะเจ้าของ ผู้ดูแลสำรอง และนักพัฒนาของระบบนี้เท่านั้นที่เปิดกล่องรหัสลับได้"


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _require_list(person: Person, system: System) -> None:
    if not vault.can_list(person, system):
        raise HTTPException(status_code=403, detail=NO_ACCESS)


def _require_use(person: Person, system: System) -> None:
    if not vault.can_use(person, system):
        raise HTTPException(status_code=403, detail=NO_ACCESS)


def _clean(text: Optional[str]) -> Optional[str]:
    return (text or "").strip() or None


def _box_json(db: Session, system: System, b: SecretBox) -> dict:
    return {
        "id": b.id, "uid": b.uid, "name": b.name, "description": b.description,
        "key_id": b.key_id, "key_check": b.key_check, "key_changed_at": _iso(b.key_changed_at),
        "current_version": b.current_version,
        "created_by": b.created_by.name if b.created_by else None, "created_at": _iso(b.created_at),
        "updated_at": _iso(b.updated_at),
        "last_opened_at": _iso(b.last_opened_at),
        "last_opened_by": b.last_opened_by.name if b.last_opened_by else None,
        # Who left the team since the key last changed and may still hold it.
        "left_since_key_change": vault.left_since_key_change(db, system, b),
    }


def _boxes(db: Session, system_id: str, person: Person) -> dict:
    system = svc.get_system(db, system_id)
    _require_list(person, system)
    people: dict[int, dict] = {}
    for r in system.roles:
        if r.role in SECRET_ROLES and r.person.status == "active":
            people.setdefault(r.person.id, {"name": r.person.name, "email": r.person.email, "roles": []})
            people[r.person.id]["roles"].append(ROLES[r.role])
    return {
        "can_use": vault.can_use(person, system),
        "items": [_box_json(db, system, b) for b in system.secret_boxes],
        # Who may download the boxes. Opening one also takes its key.
        "access": list(people.values()),
    }


def _box_for_use(db: Session, system_id: str, box_id: int, person: Person) -> tuple[System, SecretBox]:
    system = svc.get_system(db, system_id)
    _require_use(person, system)
    return system, vault.find_box(system, box_id)


def _version_meta(v: SecretBoxVersion) -> dict:
    return {"version": v.version, "note": v.note, "created_by": v.created_by.name if v.created_by else None,
            "created_at": _iso(v.created_at)}


# ---------- Secret boxes ----------

@router.get("/systems/{system_id}/boxes")
def list_boxes(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    return _boxes(db, system_id, person)


@router.post("/systems/{system_id}/boxes", status_code=201)
def create_box(system_id: str, body: BoxCreate, guard: LeakGuard = Depends(),
               db: Session = Depends(get_db), person: Person = Depends(current_person)):
    """A new box: its first version, already encrypted in the browser with a key it made."""
    system = svc.get_system(db, system_id)
    _require_use(person, system)
    vault.check_ciphertext(body.ciphertext)
    vault.check_ciphertext(body.key_check, "ค่าตรวจกุญแจ")
    if any(b.name == body.name for b in system.secret_boxes):
        raise HTTPException(status_code=409, detail="ระบบนี้มีกล่องชื่อนี้อยู่แล้ว")
    if db.scalar(select(SecretBox.id).where(SecretBox.uid == body.uid)) is not None:
        raise HTTPException(status_code=409, detail="รหัสกล่องซ้ำ ลองสร้างใหม่อีกครั้ง")
    now = utcnow()
    box = SecretBox(uid=body.uid, name=body.name, description=_clean(body.description), key_id=body.key_id,
                    key_check=body.key_check, key_changed_at=now, current_version=1, created_by_id=person.id)
    box.versions.append(SecretBoxVersion(version=1, ciphertext=body.ciphertext, note=_clean(body.note),
                                         created_by_id=person.id))
    system.secret_boxes.append(box)
    guard.check(system)  # the name, description and note are in clear
    log_secret_event(db, system_id, body.name, "box_created", f"กุญแจ {body.key_id}")
    db.commit()
    guard.after(system_id)
    return _boxes(db, system_id, person)


@router.patch("/systems/{system_id}/boxes/{box_id}")
def rename_box(system_id: str, box_id: int, body: BoxPatch, guard: LeakGuard = Depends(),
               db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system, box = _box_for_use(db, system_id, box_id, person)
    if body.name != box.name and any(b.name == body.name for b in system.secret_boxes):
        raise HTTPException(status_code=409, detail="ระบบนี้มีกล่องชื่อนี้อยู่แล้ว")
    if body.name != box.name:
        log_secret_event(db, system_id, body.name, "box_renamed", f"{box.name} → {body.name}")
    box.name, box.description = body.name, _clean(body.description)
    guard.check(system)
    db.commit()
    guard.after(system_id)
    return _boxes(db, system_id, person)


@router.get("/systems/{system_id}/boxes/{box_id}/versions")
def box_versions(system_id: str, box_id: int, db: Session = Depends(get_db),
                 person: Person = Depends(current_person)):
    """Every version's number, author, time and note: no ciphertext, so admins may see it too."""
    system = svc.get_system(db, system_id)
    _require_list(person, system)
    box = vault.find_box(system, box_id)
    return [_version_meta(v) for v in reversed(box.versions)]


@router.get("/systems/{system_id}/boxes/{box_id}/versions/{version}")
def box_version(system_id: str, box_id: int, version: int, db: Session = Depends(get_db),
                person: Person = Depends(current_person)):
    _, box = _box_for_use(db, system_id, box_id, person)
    v = next((v for v in box.versions if v.version == version), None)
    if v is None:
        raise HTTPException(status_code=404, detail="ไม่พบเวอร์ชันนี้")
    return {**_version_meta(v), "ciphertext": v.ciphertext}


@router.get("/systems/{system_id}/boxes/{box_id}/ciphertexts")
def box_ciphertexts(system_id: str, box_id: int, db: Session = Depends(get_db),
                    person: Person = Depends(current_person)):
    """Every version's ciphertext, for re-encrypting the whole box under a new key."""
    _, box = _box_for_use(db, system_id, box_id, person)
    return {"current_version": box.current_version,
            "versions": [{"version": v.version, "ciphertext": v.ciphertext} for v in box.versions]}


@router.post("/systems/{system_id}/boxes/{box_id}/versions", status_code=201)
def save_version(system_id: str, box_id: int, body: BoxVersionIn, guard: LeakGuard = Depends(),
                 db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system, box = _box_for_use(db, system_id, box_id, person)
    if body.expected_version != box.current_version:
        raise HTTPException(status_code=409, detail=(
            f"มีคนบันทึกกล่องนี้เป็นเวอร์ชัน {box.current_version} ไปแล้ว เปิดกล่องใหม่เพื่อดูค่าล่าสุดก่อนบันทึก"))
    vault.check_ciphertext(body.ciphertext)
    box.current_version += 1
    box.versions.append(SecretBoxVersion(version=box.current_version, ciphertext=body.ciphertext,
                                         note=_clean(body.note), created_by_id=person.id))
    box.updated_at = utcnow()
    guard.check(system)
    log_secret_event(db, system_id, box.name, "box_version_added", f"เวอร์ชัน {box.current_version}")
    db.commit()
    guard.after(system_id)
    return _boxes(db, system_id, person)


@router.put("/systems/{system_id}/boxes/{box_id}/key")
def change_key(system_id: str, box_id: int, body: BoxKeyChange, db: Session = Depends(get_db),
               person: Person = Depends(current_person)):
    """Replace the key: every version comes back re-encrypted under the new one, all at once."""
    system, box = _box_for_use(db, system_id, box_id, person)
    if body.expected_version != box.current_version:
        raise HTTPException(status_code=409, detail="มีคนบันทึกกล่องนี้ระหว่างเปลี่ยนกุญแจ ลองใหม่อีกครั้ง")
    given = {v.version: v.ciphertext for v in body.versions}
    if len(given) != len(body.versions) or set(given) != {v.version for v in box.versions}:
        raise HTTPException(status_code=422, detail="ต้องส่งทุกเวอร์ชันของกล่องที่เข้ารหัสด้วยกุญแจใหม่")
    vault.check_ciphertext(body.key_check, "ค่าตรวจกุญแจ")
    for v in box.versions:
        v.ciphertext = vault.check_ciphertext(given[v.version])
    old_key = box.key_id
    box.key_id, box.key_check, box.key_changed_at = body.key_id, body.key_check, utcnow()
    log_secret_event(db, system_id, box.name, "box_key_changed", f"กุญแจ {old_key} → {body.key_id}")
    db.commit()
    return _boxes(db, system_id, person)


@router.post("/systems/{system_id}/boxes/{box_id}/opened", status_code=204)
def box_opened(system_id: str, box_id: int, db: Session = Depends(get_db),
               person: Person = Depends(current_person)):
    """The browser reports it opened the box with the right key: for 'last opened' and the history."""
    _, box = _box_for_use(db, system_id, box_id, person)
    box.last_opened_at, box.last_opened_by_id = utcnow(), person.id
    log_secret_event(db, system_id, box.name, "box_opened")
    db.commit()


@router.delete("/systems/{system_id}/boxes/{box_id}")
def delete_box(system_id: str, box_id: int, guard: LeakGuard = Depends(),
               db: Session = Depends(get_db), person: Person = Depends(current_person)):
    """Delete a box and every version of it, for good."""
    system, box = _box_for_use(db, system_id, box_id, person)
    system.secret_boxes.remove(box)
    log_secret_event(db, system_id, box.name, "box_deleted", f"{box.current_version} เวอร์ชัน")
    db.commit()
    guard.after(system_id)
    return _boxes(db, system_id, person)


def alert_json(a: SecretAlert) -> dict:
    rule = leak_scan.RULES_BY_ID.get(a.rule)
    return {
        "id": a.id, "system_id": a.system_id, "rule": a.rule, "rule_label": rule.label if rule else a.rule,
        "severity": a.severity, "location_kind": a.location_kind, "location_key": a.location_key,
        "location_label": a.location_label, "line": a.line, "preview": a.preview, "status": a.status,
        "resolution": a.resolution, "resolution_note": a.resolution_note, "resolved_at": _iso(a.resolved_at),
        "resolved_by": a.resolved_by.name if a.resolved_by else None, "still_present": a.still_present,
        "source": a.source, "first_seen_at": _iso(a.first_seen_at), "last_seen_at": _iso(a.last_seen_at),
    }


def _alert_order(a: SecretAlert):
    return (a.status != "open", leak_scan.SEVERITY_RANK.get(a.severity, 9), -a.id)


# ---------- Leak alerts ----------

@router.get("/systems/{system_id}/secret-alerts")
def system_alerts(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    _require_list(person, system)
    return [alert_json(a) for a in sorted(system.secret_alerts, key=_alert_order)]


@router.put("/systems/{system_id}/secret-alerts/{alert_id}")
def resolve_alert(system_id: str, alert_id: int, body: AlertResolveIn,
                  db: Session = Depends(get_db), person: Person = Depends(current_person)):
    """Close an alert with a resolution, or reopen it (resolution null)."""
    system = svc.get_system(db, system_id)
    _require_list(person, system)
    alert = next((a for a in system.secret_alerts if a.id == alert_id), None)
    if alert is None:
        raise HTTPException(status_code=404, detail="ไม่พบการแจ้งเตือนนี้")
    # "Not a secret" is about the text, so it applies wherever the same text was found.
    same = [a for a in system.secret_alerts if a.fingerprint == alert.fingerprint] \
        if body.resolution in NOT_SECRET_RESOLUTIONS or alert.resolution in NOT_SECRET_RESOLUTIONS else [alert]
    now = utcnow()
    note = (body.note or "").strip() or None
    for a in same:
        if body.resolution is None:
            a.status, a.resolution, a.resolution_note, a.resolved_at, a.resolved_by_id = "open", None, None, None, None
        else:
            a.status, a.resolution, a.resolution_note = "resolved", body.resolution, note
            a.resolved_at, a.resolved_by_id = now, person.id
    action = "alert_reopened" if body.resolution is None else "alert_resolved"
    detail = None if body.resolution is None else ALERT_RESOLUTIONS[body.resolution]
    log_secret_event(db, system_id, f"{alert.rule} {alert.preview}", action, detail)
    db.commit()
    return system_alerts(system_id, db, person)


@router.get("/secret-alerts")
def my_alerts(status: str = "open", db: Session = Depends(get_db), person: Person = Depends(current_person)):
    """Alerts on every system this person may see: their own systems', or every one for an admin."""
    query = select(System).options(
        selectinload(System.roles), selectinload(System.secret_alerts).selectinload(SecretAlert.resolved_by))
    result = []
    for system in db.scalars(query):
        if not vault.can_list(person, system):
            continue
        for a in system.secret_alerts:
            if status == "all" or a.status == status:
                result.append({**alert_json(a), "system_name": system.name})
    result.sort(key=lambda a: (a["status"] != "open", leak_scan.SEVERITY_RANK.get(a["severity"], 9),
                               a["first_seen_at"] or ""), reverse=False)
    return result


@router.get("/secret-scan/rules")
def rules(_: Person = Depends(current_person)):
    """What the scanner looks for, for the help on the security page."""
    return [{"id": r.id, "label": r.label, "severity": r.severity, "blocks_save": r.severity in leak_scan.BLOCKING}
            for r in leak_scan.RULES]


# ---------- Scheduled scans (admins) ----------

def _run_json(r: SecretScanRun) -> dict:
    return {"id": r.id, "trigger": r.trigger, "started_at": _iso(r.started_at), "finished_at": _iso(r.finished_at),
            "systems_scanned": r.systems_scanned, "texts_scanned": r.texts_scanned, "findings": r.findings,
            "new_alerts": r.new_alerts, "error": r.error, "started_by": r.started_by_email}


@router.get("/admin/secret-scans")
def scan_runs(db: Session = Depends(get_db), _: Person = Depends(admin_person)):
    from app import config

    runs = db.scalars(select(SecretScanRun).order_by(SecretScanRun.started_at.desc()).limit(50)).all()
    return {"interval_hours": config.SECRET_SCAN_INTERVAL_HOURS, "runs": [_run_json(r) for r in runs]}


def _scan_in_background(person_id: int) -> None:
    with SessionLocal() as db:
        leak_scan.run_full_scan(db, "manual", db.get(Person, person_id))


@router.post("/admin/secret-scans", status_code=202)
def start_scan(background: BackgroundTasks, person: Person = Depends(admin_person)):
    background.add_task(_scan_in_background, person.id)
    return {"started": True}
