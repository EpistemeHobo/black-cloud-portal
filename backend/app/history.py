"""Writes a change_log row for every change to a system and its related records.

Runs inside each flush, so nothing has to remember to call it. The person making
the change is put on the database session by the auth dependency (session.info),
because FastAPI may run the dependency and the endpoint in different threads.
"""
import json
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models import (
    ChangeLog, ChecklistAnswer, ChecklistItem, Dependency, GuideDoc, Link, OpenItem, Person, ReviewNote,
    System, SystemRole, WatchOut,
)

# Records that belong to one system and are logged as added, removed or changed.
_CHILDREN = (SystemRole, Link, Dependency, ReviewNote, WatchOut, OpenItem)

PERSON_KEY = "person_id"

# Not worth recording: they change on every save, or are recorded by another row.
_SKIP = {"id", "created_at", "updated_at", "system_id", "updated_by_id", "item_id"}


def _fmt(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _system_id(obj: Any) -> Optional[str]:
    # A record added through a relationship (system.links.append(...)) has no
    # system_id until the flush, so fall back to the related system object.
    if isinstance(obj, Dependency):
        return obj.from_system_id or (obj.from_system.id if obj.from_system else None)
    return obj.system_id or (obj.system.id if obj.system else None)


def _describe(session: Session, obj: Any) -> tuple[Optional[str], str, str]:
    """(system_id, entity name, a readable one-line summary) for a child record."""
    system_id = _system_id(obj)
    if isinstance(obj, SystemRole):
        person = session.get(Person, obj.person_id)
        return system_id, "role", f"{obj.role}: {person.name if person else obj.person_id}"
    if isinstance(obj, Link):
        return system_id, "link", f"{obj.kind}: {obj.url}"
    if isinstance(obj, Dependency):
        return system_id, "dependency", obj.to_system_id or obj.external_name or ""
    if isinstance(obj, ReviewNote):
        return system_id, "review", obj.note[:200]
    if isinstance(obj, WatchOut):
        return system_id, "watch_out", f"{obj.kind}: {obj.text[:200]}"
    if isinstance(obj, OpenItem):
        return system_id, "open_item", f"{obj.kind}: {obj.text[:200]}"
    item = session.get(ChecklistItem, obj.item_id)
    return system_id, "checklist", item.code if item else str(obj.item_id)


# A system's lists. A row taken out of one (system.links.remove(...)) is only
# deleted later, during the flush, so it isn't in session.deleted yet.
_COLLECTIONS = ("roles", "links", "dependencies", "reviews", "watch_outs", "open_items", "docs")


def _removed(session: Session) -> list:
    """Rows deleted outright plus rows taken out of a system's lists, each once."""
    removed = {id(o): o for o in session.deleted}
    for obj in session.dirty:
        if isinstance(obj, System):
            state = inspect(obj)
            for name in _COLLECTIONS:
                for child in state.attrs[name].history.deleted:
                    if inspect(child).persistent:
                        removed.setdefault(id(child), child)
    return list(removed.values())


def _log(session: Session, **kwargs) -> None:
    session.add(ChangeLog(changed_by_id=session.info.get(PERSON_KEY), **kwargs))


@event.listens_for(Session, "before_flush")
def _record_changes(session: Session, _flush_context, _instances) -> None:
    for obj in list(session.new):
        if isinstance(obj, System):
            _log(session, system_id=obj.id, entity="system", entity_id=obj.id,
                 field="created", new_value=obj.name)
        elif isinstance(obj, _CHILDREN):
            system_id, entity, summary = _describe(session, obj)
            _log(session, system_id=system_id, entity=entity, entity_id="",
                 field="added", new_value=summary)

    # A deleted system gets one "deleted" row; its own records going with it aren't listed.
    deleted_systems = {o.id for o in session.deleted if isinstance(o, System)}
    for system_id in deleted_systems:
        obj = next(o for o in session.deleted if isinstance(o, System) and o.id == system_id)
        _log(session, system_id=system_id, entity="system", entity_id=system_id,
             field="deleted", old_value=obj.name)
    # Only a system's own records; a deleted person (a turned-down sign-up) isn't logged.
    removed = [o for o in _removed(session)
               if isinstance(o, (*_CHILDREN, GuideDoc)) and _system_id(o) not in deleted_systems]
    for obj in removed:
        if isinstance(obj, _CHILDREN):
            system_id, entity, summary = _describe(session, obj)
            _log(session, system_id=system_id, entity=entity, entity_id=str(obj.id),
                 field="removed", old_value=summary)

    # Attached files: log the file name, not the content, keyed by question.
    for obj, action in ([(o, "added") for o in session.new] + [(o, "removed") for o in removed]
                        + [(o, "replaced") for o in session.dirty]):
        if not isinstance(obj, GuideDoc):
            continue
        if action == "replaced" and not inspect(obj).attrs.content.history.has_changes():
            continue
        _log(session, system_id=_system_id(obj), entity="guide_doc", entity_id=obj.question, field=action,
             old_value=obj.filename if action == "removed" else None,
             new_value=None if action == "removed" else obj.filename)

    for obj in list(session.dirty):
        if not isinstance(obj, (System, ChecklistAnswer, ChecklistItem, SystemRole, WatchOut, OpenItem)):
            continue
        state = inspect(obj)
        for attr in state.mapper.column_attrs:
            if attr.key in _SKIP:
                continue
            hist = state.attrs[attr.key].history
            if not hist.has_changes():
                continue
            old = _fmt(hist.deleted[0]) if hist.deleted else None
            new = _fmt(hist.added[0]) if hist.added else None
            if old == new:
                continue
            if isinstance(obj, System):
                _log(session, system_id=obj.id, entity="system", entity_id=obj.id,
                     field=attr.key, old_value=old, new_value=new)
            elif isinstance(obj, (SystemRole, WatchOut, OpenItem)):
                if attr.key in ("sort_order", "done_by_id"):
                    continue
                system_id, entity, summary = _describe(session, obj)
                _log(session, system_id=system_id, entity=entity, entity_id=str(obj.id),
                     field=attr.key, old_value=old, new_value=new)
            elif isinstance(obj, ChecklistAnswer):
                system_id, _, code = _describe(session, obj)
                _log(session, system_id=system_id, entity="checklist", entity_id=code,
                     field=attr.key, old_value=old, new_value=new)
            else:
                _log(session, system_id=None, entity="checklist_item", entity_id=obj.code,
                     field=attr.key, old_value=old, new_value=new)

    # A first answer to a checklist item is new, not dirty.
    for obj in list(session.new):
        if isinstance(obj, ChecklistAnswer):
            system_id, _, code = _describe(session, obj)
            _log(session, system_id=system_id, entity="checklist", entity_id=code,
                 field="status", new_value=obj.status)
            if obj.evidence:
                _log(session, system_id=system_id, entity="checklist", entity_id=code,
                     field="evidence", new_value=obj.evidence)
