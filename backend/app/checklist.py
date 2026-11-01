"""Works out each checklist item's state for a system. Nothing here is stored."""
from typing import Any, Optional

from app import config
from app.enums import FINISHED_STATUSES
from app.models import ChecklistAnswer, ChecklistItem, System


def _auto_status(rule: str, system: System) -> Optional[str]:
    if rule == "always_done":
        return "done"
    if rule == "has_source_repo":
        return "done" if any(l.kind == "source_repo" for l in system.links) else "missing"
    if rule == "has_backup_owner":
        return "done" if any(r.role == "backup_owner" for r in system.roles) else "missing"
    return None


def applies_to(item: ChecklistItem, system: System) -> bool:
    return not item.applies_to_types or system.type in item.applies_to_types


def kb_url(item: ChecklistItem) -> Optional[str]:
    if not item.kb_path or not config.KB_BASE_URL:
        return None
    return f"{config.KB_BASE_URL}/{item.kb_path}"


def evaluate(system: System, items: list[ChecklistItem]) -> dict[str, Any]:
    answers: dict[int, ChecklistAnswer] = {a.item_id: a for a in system.answers}
    rows = []
    for item in items:
        if not applies_to(item, system):
            continue
        answer = answers.get(item.id)
        auto = _auto_status(item.auto_rule, system) if item.auto_rule else None
        status = auto or (answer.status if answer else "missing")
        rows.append({
            "code": item.code,
            "category": item.category,
            "title": item.title,
            "from_step": item.from_step,
            "level": item.level,
            "how_to_verify": item.how_to_verify,
            "kb_url": kb_url(item),
            "auto": item.auto_rule is not None,
            "due": item.from_step <= system.step,
            "status": status,
            "evidence": None if auto else (answer.evidence if answer else None),
            "updated_by": answer.updated_by.name if answer and answer.updated_by and not auto else None,
            "updated_at": answer.updated_at.isoformat() if answer and not auto else None,
        })

    due_required = [r for r in rows if r["due"] and r["level"] == "required"]
    finished = [r for r in due_required if r["status"] in FINISHED_STATUSES]
    return {
        "items": rows,
        "summary": {
            "required_due": len(due_required),
            "required_finished": len(finished),
            "open_codes": [r["code"] for r in due_required if r["status"] not in FINISHED_STATUSES],
        },
    }
