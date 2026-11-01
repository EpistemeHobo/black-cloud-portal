import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import config
from app.auth import admin_person, current_person
from app.checklist import kb_url
from app.db import get_db
from app.enums import (
    CHECKLIST_STATUSES, CHOICE_LABELS, CHORE_FREQUENCIES, LIFECYCLE_STATES, LINK_KINDS, OPEN_ITEM_KINDS,
    REVIEW_PLACES, ROLES, STEPS, SYSTEM_TYPES, WATCH_OUT_KINDS,
)
from app.fields import SECTIONS
from app.models import ChecklistItem, Person
from app.schemas import ItemPatch
from app.systems_service import current_standards

router = APIRouter(prefix="/api", tags=["meta"])

# When someone last used the portal (main.py's track_activity); start-up counts.
last_activity = time.monotonic()


@router.get("/health")
def health():
    # idle_seconds lets the sleep job put an unused portal to sleep (docs/aws-learner-lab.md).
    return {"status": "ok", "idle_seconds": int(time.monotonic() - last_activity)}


@router.get("/meta")
def meta(_: Person = Depends(current_person)):
    """Everything the frontend needs to draw forms and labels."""
    return {
        "steps": [{"number": n, "name": name} for n, name in STEPS.items()],
        "system_types": SYSTEM_TYPES,
        "lifecycle_states": LIFECYCLE_STATES,
        "roles": [{"key": k, "label": v} for k, v in ROLES.items()],
        "link_kinds": [{"key": k, "label": v} for k, v in LINK_KINDS.items()],
        "checklist_statuses": [{"key": k, "label": v} for k, v in CHECKLIST_STATUSES.items()],
        "review_places": REVIEW_PLACES,
        "watch_out_kinds": [{"key": k, "label": v} for k, v in WATCH_OUT_KINDS.items()],
        "chore_frequencies": [{"key": k, "label": v} for k, v in CHORE_FREQUENCIES.items()],
        "open_item_kinds": [{"key": k, "label": v} for k, v in OPEN_ITEM_KINDS.items()],
        "sections": SECTIONS,
        "kb_base_url": config.KB_BASE_URL or None,
        # Thai labels for stored English values (types, states, places, choices).
        "choice_labels": CHOICE_LABELS,
    }


def _item(i: ChecklistItem) -> dict:
    return {"code": i.code, "category": i.category, "title": i.title, "from_step": i.from_step,
            "level": i.level, "applies_to_types": i.applies_to_types or [],
            "how_to_verify": i.how_to_verify, "kb_path": i.kb_path, "kb_url": kb_url(i),
            "auto_rule": i.auto_rule}


@router.get("/standards")
def standards(db: Session = Depends(get_db), _: Person = Depends(current_person)):
    version = current_standards(db)
    if version is None:
        return {"version": None, "items": []}
    return {"version": version.version, "items": [_item(i) for i in version.items]}


@router.patch("/standards/items/{code}")
def update_item(code: str, body: ItemPatch, db: Session = Depends(get_db),
                _: Person = Depends(admin_person)):
    version = current_standards(db)
    item = next((i for i in version.items if i.code == code), None) if version else None
    if item is None:
        raise HTTPException(status_code=404, detail="ไม่พบรายการตรวจสอบนี้")
    for key, value in body.model_dump(exclude_unset=True).items():
        if key == "kb_path":
            value = (value or "").strip().lstrip("/") or None
        setattr(item, key, value)
    db.commit()
    return _item(item)
