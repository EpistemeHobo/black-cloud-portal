"""The dashboard: what needs attention across all systems, and an overview."""
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import systems_service as svc
from app.auth import current_person
from app.checklist import evaluate
from app.db import get_db
from app.enums import FINISHED_STATUSES, GUIDE_QUESTIONS, STEPS
from app.guide import answered_count
from app.models import Person, ReviewNote, System

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# How long before a page or a review counts as stale, and how long a new system
# is left alone before it is expected to have had a review.
CONFIRM_STALE_DAYS = 90
REVIEW_STALE_DAYS = 180
NEW_SYSTEM_GRACE_DAYS = 30
LIVE_STEP = 6
IMPORTANT = {"Critical", "High"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    # SQLite gives back naive datetimes; they are stored in UTC.
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _reasons(system: System, checklist: dict, last_review: Optional[date], today: date) -> list[dict]:
    status = {row["code"]: row["status"] for row in checklist["items"]}
    finished = lambda code: status.get(code) in FINISHED_STATUSES  # noqa: E731
    reasons = []

    bus = svc.bus_factor(system)
    if system.criticality in IMPORTANT and bus <= 1:
        reasons.append({"code": "single_point", "severity": "high",
                        "label": "ไม่มีใครแก้ไขระบบได้" if bus == 0 else "มีเพียงคนเดียวที่แก้ไขระบบได้"})

    live = system.step >= LIVE_STEP
    has_steps = bool((system.run_steps or "").strip() or (system.deploy_steps or "").strip())
    if live and not has_steps and not any(l.kind == "runbook" for l in system.links) and not finished("F2"):
        reasons.append({"code": "no_runbook", "severity": "high", "label": "ใช้งานจริงแต่ไม่มีขั้นตอนรันและติดตั้ง"})

    overdue = [w for w in system.watch_outs if w.kind == "chore" and w.next_due and w.next_due < today]
    if overdue:
        reasons.append({"code": "overdue_chore", "severity": "medium",
                        "label": f"งานประจำเลยกำหนด: {overdue[0].text[:60]}"})

    answered = answered_count(system)
    if answered < len(GUIDE_QUESTIONS):
        reasons.append({"code": "guide_incomplete", "severity": "medium" if live else "low",
                        "label": f"คู่มือรับช่วงต่อตอบแล้ว {answered} จาก {len(GUIDE_QUESTIONS)} ข้อ"})
    if live and system.backup not in ("Yes", "Partial") and not finished("G2"):
        reasons.append({"code": "no_backups", "severity": "high", "label": "ใช้งานจริงแต่ไม่มีบันทึกการสำรองข้อมูล"})

    if not any(r.role == "backup_owner" for r in system.roles):
        reasons.append({"code": "no_backup_owner", "severity": "medium", "label": "ไม่มีผู้ดูแลสำรอง"})

    verified = _aware(system.verified_at)
    if verified is None:
        reasons.append({"code": "never_confirmed", "severity": "low", "label": "ยังไม่เคยยืนยันว่าข้อมูลเป็นปัจจุบัน"})
    elif (today - verified.date()).days > CONFIRM_STALE_DAYS:
        reasons.append({"code": "stale_confirm", "severity": "low",
                        "label": f"ไม่ได้ยืนยันข้อมูลเกิน {CONFIRM_STALE_DAYS} วัน"})

    created = _aware(system.created_at)
    old_enough = created is None or (today - created.date()).days > NEW_SYSTEM_GRACE_DAYS
    if last_review is None and old_enough:
        reasons.append({"code": "never_reviewed", "severity": "low", "label": "ยังไม่เคยได้รับการทบทวน"})
    elif last_review is not None and (today - last_review).days > REVIEW_STALE_DAYS:
        reasons.append({"code": "stale_review", "severity": "low",
                        "label": f"ไม่ได้ทบทวนเกิน {REVIEW_STALE_DAYS} วัน"})

    return sorted(reasons, key=lambda r: SEVERITY_ORDER[r["severity"]])


@router.get("")
def dashboard(db: Session = Depends(get_db), _: Person = Depends(current_person)):
    today = datetime.now(timezone.utc).date()
    systems = [s for s in svc.all_systems(db) if s.lifecycle_state != "Retired"]
    last_reviews = dict(db.execute(
        select(ReviewNote.system_id, func.max(ReviewNote.review_date)).group_by(ReviewNote.system_id)
    ).all())

    items_cache: dict = {}
    attention = []
    required_due = required_finished = guide_answered = 0
    for system in systems:
        key = system.standards_version_id
        if key not in items_cache:
            items_cache[key] = svc.items_for(db, system)
        checklist = evaluate(system, items_cache[key])
        required_due += checklist["summary"]["required_due"]
        required_finished += checklist["summary"]["required_finished"]
        guide_answered += answered_count(system)
        reasons = _reasons(system, checklist, last_reviews.get(system.id), today)
        if reasons:
            attention.append({
                "id": system.id, "name": system.name, "type": system.type, "step": system.step,
                "criticality": system.criticality,
                "unit": system.owning_unit.name if system.owning_unit else None,
                "reasons": reasons,
            })

    # Most serious first: by worst reason, then by how many reasons.
    attention.sort(key=lambda a: (SEVERITY_ORDER[a["reasons"][0]["severity"]], -len(a["reasons"]), a["name"]))

    by_step = Counter(s.step for s in systems)
    return {
        "attention": attention,
        "overview": {
            "total": len(systems),
            "live": sum(1 for s in systems if s.step >= LIVE_STEP),
            "in_development": sum(1 for s in systems if s.step < LIVE_STEP),
            "required_due": required_due,
            "required_finished": required_finished,
            "guide_answered": guide_answered,
            "guide_total": len(GUIDE_QUESTIONS) * len(systems),
            "by_step": [{"step": n, "name": name, "count": by_step.get(n, 0)} for n, name in STEPS.items()],
            "by_type": [{"label": k, "count": v} for k, v in Counter(s.type for s in systems).most_common()],
            "by_unit": [{"label": k, "count": v} for k, v in Counter(
                (s.owning_unit.name if s.owning_unit else "ไม่มีหน่วยงาน") for s in systems).most_common()],
        },
        "thresholds": {"confirm_days": CONFIRM_STALE_DAYS, "review_days": REVIEW_STALE_DAYS},
    }
