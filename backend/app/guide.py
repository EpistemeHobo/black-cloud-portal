"""Works out the handover guide's progress and freshness. Nothing here is stored.

A question counts as answered when its main box or list has something in it, or
when the writer marked it as having nothing to list (docs/handover-guide.md).
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.enums import GUIDE_QUESTIONS
from app.models import ChangeLog, System

# Change-log rows that update each question: (entity, field or None for any field).
_SOURCES = {
    "what": [("system", "description"), ("system", "if_down")],
    "where": [("link", None)],
    "how": [("system", "run_steps"), ("system", "deploy_steps"), ("system", "rollback_steps")],
    "watch": [("watch_out", None)],
    "deps": [("dependency", None)],
    "who": [("role", None)],
    "progress": [("open_item", None)],
}


def _filled(value: Optional[str]) -> bool:
    return bool(value and value.strip())


def _has_content(system: System, key: str) -> bool:
    # An attached markdown file answers the question too, e.g. an existing runbook.md.
    return any(d.question == key for d in system.docs) or _written(system, key)


def _written(system: System, key: str) -> bool:
    """Answered in the guide's own boxes and lists, not only by an attached file."""
    if key == "what":
        return _filled(system.description) and _filled(system.if_down)
    if key == "where":
        return bool(system.links)
    if key == "how":
        return _filled(system.run_steps) or _filled(system.deploy_steps)
    if key == "watch":
        return bool(system.watch_outs)
    if key == "deps":
        return bool(system.dependencies)
    if key == "who":
        return any(r.role == "technical_owner" for r in system.roles)
    if key == "progress":
        return bool(system.open_items)
    return False


def answered_count(system: System) -> int:
    nothing = set(system.guide_nothing or [])
    return sum(1 for q in GUIDE_QUESTIONS if _has_content(system, q["key"]) or q["key"] in nothing)


def _touches(row: ChangeLog, key: str) -> bool:
    if row.entity == "guide_doc":
        return row.entity_id == key
    if row.entity == "system" and row.field == "guide_nothing":
        return f'"{key}"' in (row.old_value or "") + (row.new_value or "")
    return any(row.entity == entity and (field is None or row.field == field) for entity, field in _SOURCES[key])


def guide_status(db: Session, system: System) -> dict:
    rows = db.scalars(
        select(ChangeLog).where(ChangeLog.system_id == system.id)
        .where(ChangeLog.entity.in_({"system", "link", "watch_out", "dependency", "role", "open_item", "guide_doc"}))
        .options(selectinload(ChangeLog.changed_by))
        .order_by(ChangeLog.changed_at.desc(), ChangeLog.id.desc())
    ).all()
    nothing = set(system.guide_nothing or [])
    questions = []
    for q in GUIDE_QUESTIONS:
        key = q["key"]
        latest = next((r for r in rows if _touches(r, key)), None)
        has_content = _has_content(system, key)
        questions.append({
            "key": key,
            "title": q["title"],
            "can_be_empty": q["can_be_empty"],
            "answered": has_content or key in nothing,
            "written": _written(system, key),
            "nothing": key in nothing and not has_content,
            "updated_at": latest.changed_at.isoformat() if latest else None,
            "updated_by": latest.changed_by.name if latest and latest.changed_by else None,
        })
    return {
        "questions": questions,
        "answered": sum(1 for q in questions if q["answered"]),
        "total": len(questions),
    }
