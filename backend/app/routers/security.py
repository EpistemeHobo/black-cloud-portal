"""A system's secrets vault and its leak alerts, and the scheduled scan's runs.

Who sees what (docs/decisions/0009-secrets.md):
- The system's people in enums.SECRET_ROLES (owners, backup owner, developers):
  everything, including the vault's values.
- Admins: the vault's names and the leak alerts, never the values. An admin who
  needs a value adds themself to the system's people, which its history records.
- Everyone else: neither; and text that looks like a secret is masked for them.
"""
from typing import Optional

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import leak_scan, vault
from app import systems_service as svc
from app.auth import admin_person, current_person
from app.db import SessionLocal, get_db
from app.enums import ALERT_RESOLUTIONS, NOT_SECRET_RESOLUTIONS, ROLES, SECRET_ROLES
from app.history import log_secret_event
from app.models import Person, SecretAlert, SecretScanRun, System, SystemRole, SystemSecret, utcnow
from app.schemas import AlertResolveIn, SecretIn

router = APIRouter(prefix="/api", tags=["security"])

NO_ACCESS = "เฉพาะเจ้าของ ผู้ดูแลสำรอง และนักพัฒนาของระบบนี้เท่านั้นที่ใช้ตู้เซฟรหัสลับได้"


def _iso(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _require_list(person: Person, system: System) -> None:
    if not vault.can_list(person, system):
        raise HTTPException(status_code=403, detail=NO_ACCESS)


def _require_use(person: Person, system: System) -> None:
    if not vault.can_use(person, system):
        raise HTTPException(status_code=403, detail=NO_ACCESS)


def _require_vault() -> None:
    if not vault.configured():
        raise HTTPException(status_code=503, detail=(
            "ตู้เซฟรหัสลับยังไม่เปิดใช้: ผู้ดูแลพอร์ทัลต้องตั้งค่า SECRETS_ENCRYPTION_KEY ก่อน"))


def _secret_json(s: SystemSecret) -> dict:
    return {
        "id": s.id, "name": s.name, "environment": s.environment, "description": s.description,
        "created_by": s.created_by.name if s.created_by else None, "created_at": _iso(s.created_at),
        "updated_by": s.updated_by.name if s.updated_by else None, "updated_at": _iso(s.updated_at),
        "rotated_at": _iso(s.rotated_at),
        "last_revealed_at": _iso(s.last_revealed_at),
        "last_revealed_by": s.last_revealed_by.name if s.last_revealed_by else None,
    }


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


def _vault(db: Session, system_id: str, person: Person) -> dict:
    system = svc.get_system(db, system_id)
    _require_list(person, system)
    people = {}
    for r in system.roles:
        if r.role in SECRET_ROLES and r.person.status == "active":
            people.setdefault(r.person.id, {"name": r.person.name, "email": r.person.email, "roles": []})
            people[r.person.id]["roles"].append(ROLES[r.role])
    return {
        "enabled": vault.configured(),
        "can_use": vault.can_use(person, system),
        "items": [_secret_json(s) for s in system.secrets],
        # Who can read the values: the review an owner should do when someone leaves.
        "access": list(people.values()),
    }


# ---------- The vault ----------

@router.get("/systems/{system_id}/secrets")
def list_secrets(system_id: str, db: Session = Depends(get_db), person: Person = Depends(current_person)):
    return _vault(db, system_id, person)


@router.post("/systems/{system_id}/secrets", status_code=201)
def add_secret(system_id: str, body: SecretIn, background: BackgroundTasks,
               db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    _require_use(person, system)
    _require_vault()
    if not body.value:
        raise HTTPException(status_code=422, detail="กรุณาใส่ค่าของรหัสลับ")
    system.secrets.append(SystemSecret(
        name=body.name, environment=body.environment, description=(body.description or "").strip() or None,
        ciphertext=vault.encrypt(body.value), created_by_id=person.id, updated_by_id=person.id,
    ))
    log_secret_event(db, system_id, body.name, "added", body.environment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="มีรหัสลับชื่อนี้ในสภาพแวดล้อมนี้อยู่แล้ว")
    _rescan(db, system_id, person, background)
    return _vault(db, system_id, person)


def _rescan(db: Session, system_id: str, person: Person, background: BackgroundTasks) -> None:
    # A value just put in the vault may already be written in plain text somewhere.
    system = svc.get_system(db, system_id)
    new, _, _ = leak_scan.scan_system(db, system, "save", docs=True)
    db.commit()
    if new:
        background.add_task(leak_scan.notify, system_id, [a.id for a in new], None)


def _get_secret(system: System, secret_id: int) -> SystemSecret:
    secret = next((s for s in system.secrets if s.id == secret_id), None)
    if secret is None:
        raise HTTPException(status_code=404, detail="ไม่พบรหัสลับนี้")
    return secret


@router.put("/systems/{system_id}/secrets/{secret_id}")
def update_secret(system_id: str, secret_id: int, body: SecretIn, background: BackgroundTasks,
                  db: Session = Depends(get_db), person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    _require_use(person, system)
    _require_vault()
    secret = _get_secret(system, secret_id)
    old_name = secret.name
    secret.name, secret.environment = body.name, body.environment
    secret.description = (body.description or "").strip() or None
    secret.updated_by_id = person.id
    if body.value:
        secret.ciphertext = vault.encrypt(body.value)
        secret.rotated_at = utcnow()
        log_secret_event(db, system_id, body.name, "rotated")
    if old_name != body.name:
        log_secret_event(db, system_id, body.name, "renamed", f"{old_name} → {body.name}")
    secret.updated_at = utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="มีรหัสลับชื่อนี้ในสภาพแวดล้อมนี้อยู่แล้ว")
    if body.value:
        _rescan(db, system_id, person, background)
    return _vault(db, system_id, person)


@router.post("/systems/{system_id}/secrets/{secret_id}/reveal")
def reveal_secret(system_id: str, secret_id: int, db: Session = Depends(get_db),
                  person: Person = Depends(current_person)):
    """The value, for one of the system's people. Every reveal is in the system's history."""
    system = svc.get_system(db, system_id)
    _require_use(person, system)
    _require_vault()
    secret = _get_secret(system, secret_id)
    try:
        value = vault.decrypt(secret.ciphertext)
    except InvalidToken:
        raise HTTPException(status_code=500, detail="ถอดรหัสค่านี้ไม่ได้: กุญแจของตู้เซฟอาจถูกเปลี่ยน แจ้งผู้ดูแลพอร์ทัล")
    secret.last_revealed_at, secret.last_revealed_by_id = utcnow(), person.id
    log_secret_event(db, system_id, secret.name, "revealed")
    db.commit()
    return {"value": value}


@router.delete("/systems/{system_id}/secrets/{secret_id}")
def delete_secret(system_id: str, secret_id: int, db: Session = Depends(get_db),
                  person: Person = Depends(current_person)):
    system = svc.get_system(db, system_id)
    _require_use(person, system)
    secret = _get_secret(system, secret_id)
    system.secrets.remove(secret)
    log_secret_event(db, system_id, secret.name, "removed", secret.environment)
    db.commit()
    return _vault(db, system_id, person)


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
            for r in [*leak_scan.RULES, leak_scan.VAULT_RULE]]


# ---------- Scheduled scans (admins) ----------

def _run_json(r: SecretScanRun) -> dict:
    return {"id": r.id, "trigger": r.trigger, "started_at": _iso(r.started_at), "finished_at": _iso(r.finished_at),
            "systems_scanned": r.systems_scanned, "texts_scanned": r.texts_scanned, "findings": r.findings,
            "new_alerts": r.new_alerts, "error": r.error, "started_by": r.started_by_email}


@router.get("/admin/secret-scans")
def scan_runs(db: Session = Depends(get_db), _: Person = Depends(admin_person)):
    from app import config

    runs = db.scalars(select(SecretScanRun).order_by(SecretScanRun.started_at.desc()).limit(50)).all()
    return {"interval_hours": config.SECRET_SCAN_INTERVAL_HOURS, "vault_enabled": vault.configured(),
            "runs": [_run_json(r) for r in runs]}


def _scan_in_background(person_id: int) -> None:
    with SessionLocal() as db:
        leak_scan.run_full_scan(db, "manual", db.get(Person, person_id))


@router.post("/admin/secret-scans", status_code=202)
def start_scan(background: BackgroundTasks, person: Person = Depends(admin_person)):
    background.add_task(_scan_in_background, person.id)
    return {"started": True}
