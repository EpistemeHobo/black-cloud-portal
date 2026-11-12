"""Loading, checking and shaping systems for the API."""
from datetime import date
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app import doc_store
from app.checklist import evaluate
from app.enums import (
    BUS_FACTOR_ROLES, EDITOR_ROLES, EMPTYABLE_QUESTIONS, GUIDE_QUESTIONS, LIFECYCLE_STATES,
    ROLES, STEPS, SYSTEM_TYPES,
)
from app.fields import FIELDS, GUIDE_FIELDS, RESTRICTED_FIELDS
from app.guide import answered_count, guide_status
from app.models import (
    ChangeLog, ChecklistItem, Dependency, GuideDoc, OpenItem, Person, StandardsVersion, System, SystemRole, Unit,
)

_LOAD = (
    selectinload(System.roles).selectinload(SystemRole.person),
    selectinload(System.links),
    selectinload(System.dependencies).selectinload(Dependency.to_system),
    selectinload(System.answers),
    selectinload(System.owning_unit),
    selectinload(System.watch_outs),
    selectinload(System.open_items).selectinload(OpenItem.done_by),
    selectinload(System.docs).selectinload(GuideDoc.updated_by),
    selectinload(System.tech_debts),
    selectinload(System.secrets),
    selectinload(System.secret_alerts),
)

# Editable by owners, developers and auditors alike.
CORE_KEYS = {"name", "type", "lifecycle_state", "owning_unit_id"}


def get_system(db: Session, system_id: str) -> System:
    system = db.scalar(select(System).where(System.id == system_id).options(*_LOAD))
    if system is None:
        raise HTTPException(status_code=404, detail="ไม่พบระบบนี้")
    return system


def all_systems(db: Session) -> list[System]:
    return list(db.scalars(select(System).options(*_LOAD).order_by(System.name)))


def current_standards(db: Session) -> Optional[StandardsVersion]:
    return db.scalar(select(StandardsVersion).where(StandardsVersion.status == "current"))


def items_for(db: Session, system: System) -> list[ChecklistItem]:
    version_id = system.standards_version_id
    if version_id is None:
        current = current_standards(db)
        version_id = current.id if current else None
    if version_id is None:
        return []
    return list(db.scalars(
        select(ChecklistItem).where(ChecklistItem.standards_version_id == version_id)
        .order_by(ChecklistItem.sort_order)
    ))


def can_edit(person: Person, system: System) -> bool:
    return person.is_admin or any(
        r.person_id == person.id and r.role in EDITOR_ROLES for r in system.roles
    )


def can_edit_catalog(person: Person, system: System) -> bool:
    return person.is_auditor or can_edit(person, system)


def require_editor(person: Person, system: System) -> None:
    if not can_edit(person, system):
        raise HTTPException(status_code=403, detail="เฉพาะเจ้าของ นักพัฒนาของระบบนี้ และผู้ดูแลระบบเท่านั้นที่แก้ไขได้")


def require_patch_rights(person: Person, system: System, keys: set[str]) -> None:
    """Guide fields need an editor; catalog and core fields also accept an auditor."""
    if can_edit(person, system):
        return
    if person.is_auditor and keys <= set(FIELDS) | CORE_KEYS:
        return
    require_editor(person, system)


def can_delete(person: Person, system: System) -> bool:
    """Deleting is for the technical owners (and admins), not every editor."""
    return person.is_admin or any(
        r.person_id == person.id and r.role == "technical_owner" for r in system.roles
    )


def next_system_id(db: Session) -> str:
    # IDs are never reused: a deleted system's ID is still in the change log.
    ids = set(db.scalars(select(System.id).where(System.id.like("APP-%"))))
    ids |= set(db.scalars(
        select(ChangeLog.entity_id).where(ChangeLog.entity == "system", ChangeLog.field == "created")
    ))
    numbers = [int(i[4:]) for i in ids if i.startswith("APP-") and i[4:].isdigit()]
    return f"APP-{(max(numbers) + 1) if numbers else 1:03d}"


def bus_factor(system: System) -> int:
    return len({r.person_id for r in system.roles if r.role in BUS_FACTOR_ROLES})


def _person(p: Optional[Person]) -> Optional[dict]:
    return {"id": p.id, "name": p.name, "email": p.email} if p else None


def _value(value: Any) -> Any:
    return value.isoformat() if isinstance(value, date) else value


def summary(db: Session, system: System, items: list[ChecklistItem]) -> dict:
    checklist = evaluate(system, items)["summary"]
    return {
        "id": system.id,
        "name": system.name,
        "type": system.type,
        "step": system.step,
        "lifecycle_state": system.lifecycle_state,
        "unit": system.owning_unit.name if system.owning_unit else None,
        "technical_owners": [r.person.name for r in system.roles if r.role == "technical_owner"],
        "criticality": system.criticality,
        "description": system.description,
        "checklist": checklist,
        "guide": {"answered": answered_count(system), "total": len(GUIDE_QUESTIONS)},
        "updated_at": system.updated_at.isoformat() if system.updated_at else None,
    }


def security_summary(viewer: Person, system: System) -> dict:
    """What the system page shows about its vault and leak alerts, to whoever may see them."""
    from app import vault
    from app.enums import ALERT_SEVERITIES

    if not vault.can_list(viewer, system):
        return {"can_list": False, "can_use": False}
    open_alerts = [a for a in system.secret_alerts if a.status == "open"]
    worst = min((a.severity for a in open_alerts), key=lambda s: list(ALERT_SEVERITIES).index(s), default=None)
    return {"can_list": True, "can_use": vault.can_use(viewer, system), "vault_enabled": vault.configured(),
            "secrets": len(system.secrets), "open_alerts": len(open_alerts), "worst_severity": worst}


def detail(db: Session, system: System, viewer: Person) -> dict:
    from app import leak_scan
    from app.routers.debt import summary as debt_summary

    editable = can_edit(viewer, system)
    restricted_visible = editable or viewer.is_auditor
    # Text that looks like a secret is masked for anyone who isn't one of the system's people.
    show = leak_scan.redactor(viewer, system)
    fields = {}
    for key in FIELDS:
        if key in RESTRICTED_FIELDS and not restricted_visible:
            continue
        value = _value(getattr(system, key))
        fields[key] = show(value) if isinstance(value, str) else value
    used_by = db.scalars(
        select(Dependency).where(Dependency.to_system_id == system.id)
        .options(selectinload(Dependency.from_system))
    ).all()
    items = items_for(db, system)
    return {
        "id": system.id,
        "name": system.name,
        "type": system.type,
        "step": system.step,
        "step_name": STEPS[system.step],
        "lifecycle_state": system.lifecycle_state,
        "owning_unit": {"id": system.owning_unit.id, "name": system.owning_unit.name} if system.owning_unit else None,
        "guide_fields": {key: show(getattr(system, key)) for key in GUIDE_FIELDS},
        "guide": guide_status(db, system),
        "fields": fields,
        "hidden_fields": [] if restricted_visible else sorted(RESTRICTED_FIELDS),
        "roles": [
            {"role": r.role, "role_label": ROLES[r.role], "person": _person(r.person),
             "reachable_until": _value(r.reachable_until), "note": show(r.note),
             "reachable": r.reachable_until is None or r.reachable_until >= date.today()}
            for r in sorted(system.roles, key=lambda r: list(ROLES).index(r.role))
        ],
        "watch_outs": [
            {"id": w.id, "kind": w.kind, "text": show(w.text), "how_often": w.how_often, "next_due": _value(w.next_due)}
            for w in system.watch_outs
        ],
        "docs": [
            {"id": d.id, "question": d.question, "filename": d.filename, "content": show(doc_store.read(d)),
             "updated_at": d.updated_at.isoformat() if d.updated_at else None,
             "updated_by": d.updated_by.name if d.updated_by else None}
            for d in system.docs
        ],
        "open_items": [
            {"id": o.id, "kind": o.kind, "text": show(o.text), "promised_to": show(o.promised_to),
             "due_date": _value(o.due_date), "done": o.done_at is not None,
             "done_at": o.done_at.isoformat() if o.done_at else None,
             "done_by": o.done_by.name if o.done_by else None}
            for o in system.open_items
        ],
        "links": [{"id": l.id, "kind": l.kind, "url": show(l.url), "label": show(l.label)} for l in system.links],
        "depends_on": [
            {"to_system_id": d.to_system_id, "name": d.to_system.name if d.to_system else show(d.external_name),
             "external": d.to_system_id is None, "note": show(d.note)}
            for d in system.dependencies
        ],
        "used_by": [
            {"system_id": d.from_system_id, "name": d.from_system.name, "note": d.note} for d in used_by
        ],
        "bus_factor": bus_factor(system),
        "checklist": evaluate(system, items)["summary"],
        "verified_at": system.verified_at.isoformat() if system.verified_at else None,
        "verified_by": _person(system.verified_by),
        "created_at": system.created_at.isoformat() if system.created_at else None,
        "updated_at": system.updated_at.isoformat() if system.updated_at else None,
        "can_edit": editable,
        "can_edit_catalog": can_edit_catalog(viewer, system),
        "can_delete": can_delete(viewer, system),
        "tech_debt": debt_summary(system),
        "security": security_summary(viewer, system),
    }


def _clean_value(key: str, value: Any) -> Any:
    spec = FIELDS[key]
    if value is None or value == "" or value == []:
        return None
    kind = spec["type"]
    if kind in ("text", "paragraph"):
        if not isinstance(value, str):
            raise HTTPException(status_code=422, detail=f"{spec['label']} ต้องเป็นข้อความ")
        value = value.strip()
        if len(value) > 5000:
            raise HTTPException(status_code=422, detail=f"{spec['label']} ยาวเกินไป")
        return value or None
    if kind == "choice":
        if value not in spec["choices"]:
            raise HTTPException(status_code=422, detail=f"{spec['label']}: '{value}' ไม่ใช่ตัวเลือกที่กำหนด")
        return value
    if kind == "multi":
        if not isinstance(value, list) or any(v not in spec["choices"] for v in value):
            raise HTTPException(status_code=422, detail=f"{spec['label']}: กรุณาเลือกจากตัวเลือกที่กำหนด")
        return list(dict.fromkeys(value))
    if kind == "date":
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            raise HTTPException(status_code=422, detail=f"{spec['label']} ต้องเป็นวันที่ (ปปปป-ดด-วว)")
    if kind == "number":
        try:
            return int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=422, detail=f"{spec['label']} ต้องเป็นจำนวนเต็ม")
    return value


def apply_patch(db: Session, system: System, data: dict) -> None:
    from app.leak_guard import keep_hidden_text

    for key, value in data.items():
        if key == "name":
            if not isinstance(value, str) or not value.strip():
                raise HTTPException(status_code=422, detail="ชื่อต้องไม่ว่าง")
            system.name = value.strip()[:200]
        elif key == "type":
            if value not in SYSTEM_TYPES:
                raise HTTPException(status_code=422, detail="ไม่รู้จักประเภทระบบนี้")
            system.type = value
        elif key == "lifecycle_state":
            if value not in LIFECYCLE_STATES:
                raise HTTPException(status_code=422, detail="ไม่รู้จักสถานะวงจรชีวิตนี้")
            system.lifecycle_state = value
        elif key == "owning_unit_id":
            if value is not None and db.get(Unit, value) is None:
                raise HTTPException(status_code=422, detail="ไม่พบหน่วยงานนี้")
            system.owning_unit_id = value
        elif key in GUIDE_FIELDS:
            spec = GUIDE_FIELDS[key]
            if value is not None and not isinstance(value, str):
                raise HTTPException(status_code=422, detail=f"{spec['label']} ต้องเป็นข้อความ")
            value = (value or "").strip()
            keep_hidden_text(getattr(system, key), value, spec["label"])
            if len(value) > spec["max"]:
                raise HTTPException(status_code=422, detail=f"{spec['label']} ยาวเกินไป")
            setattr(system, key, value or None)
        elif key == "guide_nothing":
            if not isinstance(value, list) or any(k not in EMPTYABLE_QUESTIONS for k in value):
                raise HTTPException(status_code=422, detail="ทำเครื่องหมาย 'ไม่มีรายการ' ได้เฉพาะบางคำถาม")
            system.guide_nothing = sorted(set(value)) or None
        elif key in FIELDS:
            cleaned = _clean_value(key, value)
            if isinstance(cleaned, str):
                keep_hidden_text(getattr(system, key), cleaned, FIELDS[key]["label"])
            setattr(system, key, cleaned)
        else:
            raise HTTPException(status_code=422, detail=f"'{key}' แก้ไขที่นี่ไม่ได้")


def clear_nothing(system: System, key: str) -> None:
    """A list that now has items is no longer marked as having nothing."""
    if system.guide_nothing and key in system.guide_nothing:
        system.guide_nothing = [k for k in system.guide_nothing if k != key] or None


def count_systems(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(System)) or 0
