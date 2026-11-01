"""Export a system as a folder (zipped), and import such a folder as a new system.

The folder holds `system.json` (everything that goes into the database) and the
attached markdown files under `docs/<number>-<question>/`. See
docs/system-export-format.md.
"""
import io
import json
import re
import zipfile
from datetime import date, datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import doc_store
from app import systems_service as svc
from app.enums import GUIDE_QUESTIONS, ROLES
from app.fields import FIELDS, GUIDE_FIELDS
from app.models import (
    ChecklistAnswer, Dependency, GuideDoc, Link, OpenItem, Person, System, SystemRole, Unit, WatchOut,
)
from app.schemas import DocIn, LinkIn, OpenItemIn, WatchOutIn, _email

FORMAT = "cloud-dev-portal/system"
VERSION = 1
# Folder per guide question, numbered in reading order: docs/3-how/runbook.md
QUESTION_DIRS = {q["key"]: f"{i}-{q['key']}" for i, q in enumerate(GUIDE_QUESTIONS, start=1)}
MAX_DOCS = 100


def _value(value: Any) -> Any:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def folder_name(system: System) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", system.name).strip("-").lower()[:40]
    return f"{system.id}-{slug}" if slug else system.id


def export_data(system: System) -> dict:
    """Everything about the system that a new copy needs, without database IDs."""
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "exported_from": {"id": system.id},
        "system": {"name": system.name, "type": system.type, "lifecycle_state": system.lifecycle_state,
                   "step": system.step},
        "owning_unit": system.owning_unit.name if system.owning_unit else None,
        "guide": {**{k: getattr(system, k) for k in GUIDE_FIELDS}, "nothing": system.guide_nothing or []},
        "catalog": {k: _value(getattr(system, k)) for k in FIELDS},
        "people": [
            {"name": r.person.name, "email": r.person.email, "role": r.role,
             "reachable_until": _value(r.reachable_until), "note": r.note}
            for r in system.roles
        ],
        "links": [{"kind": l.kind, "url": l.url, "label": l.label} for l in system.links],
        "dependencies": [
            {"system_id": d.to_system_id, "name": d.to_system.name if d.to_system else d.external_name,
             "external": d.to_system_id is None, "note": d.note}
            for d in system.dependencies
        ],
        "watch_outs": [
            {"kind": w.kind, "text": w.text, "how_often": w.how_often, "next_due": _value(w.next_due)}
            for w in system.watch_outs
        ],
        "open_items": [
            {"kind": o.kind, "text": o.text, "promised_to": o.promised_to, "due_date": _value(o.due_date),
             "done": o.done_at is not None}
            for o in system.open_items
        ],
        "checklist": [
            {"code": a.item.code, "status": a.status, "evidence": a.evidence}
            for a in system.answers if a.item is not None
        ],
    }


README = """# {name} ({id})

Exported from the Cloud Developer Portal on {date}.

- `system.json`: the system's data (handover guide, catalog info, people, links,
  dependencies, watch-outs, open items, checklist answers).
- `docs/`: markdown files attached to the handover guide, one folder per question:
{dirs}

To bring it back, open the portal, go to "ลงทะเบียนระบบ" (Register a system) and
choose "นำเข้า" (Import). You can import this folder as it is or zipped. It is
registered as a new system, and you become its technical owner.

You can edit the files before importing, for example to add a .md file to a
question folder. Keep `system.json` valid JSON.
"""


def export_zip(system: System) -> tuple[str, bytes]:
    root = folder_name(system)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{root}/system.json", json.dumps(export_data(system), ensure_ascii=False, indent=2))
        dirs = "\n".join(f"  - `docs/{d}/`: {q['title']}" for q, d in zip(GUIDE_QUESTIONS, QUESTION_DIRS.values()))
        z.writestr(f"{root}/README.md", README.format(
            name=system.name, id=system.id, date=date.today().isoformat(), dirs=dirs))
        for doc in system.docs:
            z.writestr(f"{root}/docs/{QUESTION_DIRS[doc.question]}/{doc.filename}", doc_store.read(doc))
    return f"{root}.zip", buffer.getvalue()


# ---------- import ----------

class ImportPerson(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str
    role: str
    reachable_until: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=300)

    _check_email = field_validator("email")(lambda cls, v: _email(v))

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError(f"ไม่รู้จักบทบาท '{v}'")
        return v


class ImportDependency(BaseModel):
    system_id: Optional[str] = None
    name: str = Field(min_length=1, max_length=200)
    external: bool = False
    note: Optional[str] = Field(default=None, max_length=300)


class ImportAnswer(BaseModel):
    code: str
    status: str
    evidence: Optional[str] = Field(default=None, max_length=2000)


class ImportCore(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str
    lifecycle_state: str = "Active"
    step: int = Field(default=1, ge=1, le=7)


class SystemFile(BaseModel):
    """The contents of system.json."""
    format: str
    version: int
    system: ImportCore
    owning_unit: Optional[str] = Field(default=None, max_length=200)
    guide: dict = {}
    catalog: dict = {}
    people: list[ImportPerson] = []
    links: list[LinkIn] = []
    dependencies: list[ImportDependency] = []
    watch_outs: list[WatchOutIn] = []
    open_items: list[OpenItemIn] = []
    checklist: list[ImportAnswer] = []

    @field_validator("format")
    @classmethod
    def _format(cls, v: str) -> str:
        if v != FORMAT:
            raise ValueError("system.json นี้ไม่ได้มาจาก Cloud Developer Portal")
        return v

    @field_validator("version")
    @classmethod
    def _version(cls, v: int) -> int:
        if v > VERSION:
            raise ValueError("ไฟล์นี้มาจากพอร์ทัลรุ่นที่ใหม่กว่า กรุณาอัปเดตพอร์ทัลก่อน")
        return v


class ImportIn(BaseModel):
    data: SystemFile
    docs: list[DocIn] = Field(default=[], max_length=MAX_DOCS)


def _person_for(db: Session, p: ImportPerson) -> Person:
    person = db.scalar(select(Person).where(Person.email == p.email))
    if person is None:
        person = Person(name=p.name.strip(), email=p.email)
        db.add(person)
        db.flush()
    return person


def _unit_for(db: Session, name: Optional[str]) -> Optional[int]:
    name = (name or "").strip()
    if not name:
        return None
    unit = db.scalar(select(Unit).where(Unit.name == name))
    if unit is None:
        unit = Unit(name=name)
        db.add(unit)
        db.flush()
    return unit.id


def _dependency_target(db: Session, d: ImportDependency) -> tuple[Optional[str], Optional[str]]:
    """(to_system_id, external_name): a system in this portal when one matches, else an external name."""
    if not d.external:
        same_id = db.get(System, d.system_id) if d.system_id else None
        if same_id is not None and same_id.name == d.name:
            return same_id.id, None
        by_name = db.scalars(select(System).where(func.lower(System.name) == d.name.strip().lower())).all()
        if len(by_name) == 1:
            return by_name[0].id, None
    return None, d.name.strip()


def import_system(db: Session, body: ImportIn, importer: Person) -> System:
    data = body.data
    standards = svc.current_standards(db)
    system = System(id=svc.next_system_id(db), name=data.system.name.strip(), type="Script", step=data.system.step,
                    standards_version_id=standards.id if standards else None)
    db.add(system)

    # Core, guide text and catalog go through the same checks as an edit.
    patch: dict[str, Any] = {"type": data.system.type, "lifecycle_state": data.system.lifecycle_state,
                             "owning_unit_id": _unit_for(db, data.owning_unit)}
    patch.update({k: v for k, v in data.guide.items() if k in GUIDE_FIELDS})
    nothing = [k for k in data.guide.get("nothing") or [] if isinstance(k, str)]
    patch.update({k: v for k, v in data.catalog.items() if k in FIELDS})
    svc.apply_patch(db, system, patch)
    if nothing:
        svc.apply_patch(db, system, {"guide_nothing": nothing})

    roles = {}
    for p in data.people:
        person = _person_for(db, p)
        roles[(person.id, p.role)] = SystemRole(person_id=person.id, role=p.role,
                                                reachable_until=p.reachable_until, note=p.note)
    # The person importing it looks after it from now on.
    roles.setdefault((importer.id, "technical_owner"), SystemRole(person_id=importer.id, role="technical_owner"))
    system.roles.extend(roles.values())

    for l in data.links:
        system.links.append(Link(kind=l.kind, url=l.url, label=(l.label or "").strip() or None))
    seen = set()
    for d in data.dependencies:
        to_id, external = _dependency_target(db, d)
        key = (to_id, external, (d.note or "").strip() or None)
        if key not in seen:
            seen.add(key)
            system.dependencies.append(Dependency(to_system_id=to_id, external_name=external, note=key[2]))
    for i, w in enumerate(data.watch_outs):
        chore = w.kind == "chore"
        system.watch_outs.append(WatchOut(kind=w.kind, text=w.text.strip(), sort_order=i,
                                          how_often=w.how_often if chore else None,
                                          next_due=w.next_due if chore else None))
    for i, o in enumerate(data.open_items):
        system.open_items.append(OpenItem(
            kind=o.kind, text=o.text.strip(), sort_order=i, due_date=o.due_date,
            promised_to=((o.promised_to or "").strip() or None) if o.kind == "promise" else None,
            done_at=datetime.now(timezone.utc) if o.done else None,
        ))

    items = {i.code: i for i in svc.items_for(db, system)}
    for a in data.checklist:
        item = items.get(a.code)
        if item is not None and not item.auto_rule and a.status in ("done", "partly", "missing", "not_applicable"):
            system.answers.append(ChecklistAnswer(item_id=item.id, status=a.status,
                                                  evidence=(a.evidence or "").strip() or None,
                                                  updated_by_id=importer.id))

    names = set()
    for doc in body.docs:
        key = (doc.question, doc.filename)
        if key in names:
            raise HTTPException(status_code=422, detail=f"มีไฟล์ {doc.filename} ซ้ำในคำถามเดียวกัน")
        names.add(key)
        row = GuideDoc(question=doc.question, filename=doc.filename, updated_by_id=importer.id)
        system.docs.append(row)
        doc_store.save(system, row, doc.content)
    db.commit()
    return system
