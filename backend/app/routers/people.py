from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app import account_emails, activity
from app.auth import ACTIVE, NO_ACCOUNT, PENDING, SUSPENDED, admin_person, as_utc, current_person, utcnow
from app.db import get_db
from app.models import ActivityLog, Person, Unit
from app.schemas import PersonAdminPatch, PersonIn, UnitIn

router = APIRouter(prefix="/api", tags=["people"])


def _person(p: Person) -> dict:
    return {"id": p.id, "name": p.name, "email": p.email, "active": p.status != SUSPENDED,
            "is_admin": p.is_admin, "is_auditor": p.is_auditor, "unit": p.unit.name if p.unit else None,
            "has_account": p.status != NO_ACCOUNT}


def _account(p: Person) -> dict:
    locked = as_utc(p.locked_until)
    signed_in = as_utc(p.last_sign_in_at)
    # With the timezone, so the browser shows local time, not UTC read as local.
    return {**_person(p), "status": p.status, "email_verified": p.email_verified,
            "created_at": as_utc(p.created_at).isoformat(),
            "last_sign_in_at": signed_in.isoformat() if signed_in else None,
            "locked": bool(locked and locked > utcnow())}


@router.get("/people")
def list_people(db: Session = Depends(get_db), _: Person = Depends(current_person)):
    people = db.scalars(select(Person).options(selectinload(Person.unit)).order_by(Person.name))
    return [_person(p) for p in people]


@router.post("/people", status_code=201)
def add_person(body: PersonIn, db: Session = Depends(get_db), _: Person = Depends(current_person)):
    """Add someone who hasn't signed up yet, so they can be named as an owner.

    Their record becomes their account when they sign up with the same email.
    """
    if db.scalar(select(Person).where(Person.email == body.email)):
        raise HTTPException(status_code=409, detail="มีบุคคลที่ใช้อีเมลนี้อยู่แล้ว")
    if body.unit_id is not None and db.get(Unit, body.unit_id) is None:
        raise HTTPException(status_code=422, detail="ไม่พบหน่วยงานนี้")
    person = Person(name=body.name.strip(), email=body.email, unit_id=body.unit_id)
    db.add(person)
    db.commit()
    return _person(person)


@router.patch("/people/{person_id}")
def admin_update_person(person_id: int, body: PersonAdminPatch, request: Request, db: Session = Depends(get_db),
                        admin: Person = Depends(admin_person)):
    person = _get(db, person_id)
    changes = body.model_dump(exclude_unset=True)
    if person.id == admin.id and (changes.get("is_admin") is False or changes.get("status") == SUSPENDED):
        raise HTTPException(status_code=422, detail="คุณไม่สามารถถอนสิทธิ์หรือระงับบัญชีของตนเองได้")
    if "status" in changes and person.status == NO_ACCOUNT:
        raise HTTPException(status_code=422, detail="บุคคลนี้ยังไม่มีบัญชี ต้องสมัครใช้งานก่อน")
    approving = changes.get("status") == ACTIVE and person.status == PENDING
    if approving and not person.email_verified:
        raise HTTPException(status_code=422, detail="บุคคลนี้ยังไม่ได้ยืนยันอีเมล จึงยังอนุมัติไม่ได้")
    if changes.get("status") == ACTIVE:
        person.locked_until = None
        person.failed_logins = 0
    events = _events(person, changes)
    for key, value in changes.items():
        setattr(person, key, value)
    for action, detail in events:
        activity.record(db, action, actor=admin, subject=person, detail=detail, request=request, commit=False)
    db.commit()
    return _account(person)


def _events(person: Person, changes: dict) -> list[tuple[str, str | None]]:
    """The activity-log entries for an admin's change, worked out before it is applied."""
    events: list[tuple[str, str | None]] = []
    status = changes.get("status")
    if status and status != person.status:
        events.append(({ACTIVE: "approved" if person.status == PENDING else "reactivated",
                        SUSPENDED: "suspended"}[status], None))
    for flag, name in (("is_admin", "ผู้ดูแลระบบ"), ("is_auditor", "ผู้ตรวจสอบ")):
        if flag in changes and changes[flag] != getattr(person, flag):
            events.append(("role_changed", f"{'ให้สิทธิ์' if changes[flag] else 'ถอนสิทธิ์'}{name}"))
    return events


# ---------- Accounts (admins only) ----------

@router.get("/admin/users")
def list_accounts(db: Session = Depends(get_db), _: Person = Depends(admin_person)):
    people = db.scalars(select(Person).options(selectinload(Person.unit)).order_by(Person.name))
    return [_account(p) for p in people]


@router.get("/admin/users/pending-count")
def pending_count(db: Session = Depends(get_db), _: Person = Depends(admin_person)):
    """Sign-ups an admin can act on: pending, with the address already verified."""
    return {"count": db.scalar(select(func.count()).select_from(Person)
                               .where(Person.status == PENDING, Person.email_verified))}


@router.post("/admin/users/{person_id}/send-reset", status_code=202)
def send_reset(person_id: int, request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db),
               admin: Person = Depends(admin_person)):
    """Email someone the same link as "forgot password", for when they ask an admin."""
    person = _get(db, person_id)
    if person.status == NO_ACCOUNT:
        raise HTTPException(status_code=422, detail="บุคคลนี้ยังไม่มีบัญชี")
    account_emails.reset_password(tasks, person)
    activity.record(db, "reset_link_sent", actor=admin, subject=person, request=request)
    return {"ok": True}


@router.delete("/admin/users/{person_id}", status_code=204)
def reject_sign_up(person_id: int, request: Request, db: Session = Depends(get_db),
                   admin: Person = Depends(admin_person)):
    """Turn down a pending sign-up.

    The record is deleted, unless it is already named somewhere (say as a
    system's owner); then it goes back to having no account.
    """
    person = _get(db, person_id)
    if person.status != PENDING:
        raise HTTPException(status_code=422, detail="ปฏิเสธได้เฉพาะคำขอที่รออนุมัติ ถ้าต้องการปิดบัญชี ให้ระงับแทน")
    email = person.email
    db.delete(person)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        person = _get(db, person_id)
        person.status = NO_ACCOUNT
        person.password_hash = None
        db.commit()
    activity.record(db, "rejected", actor=admin, subject_email=email, request=request)


@router.get("/admin/activity")
def list_activity(limit: int = 500, db: Session = Depends(get_db), _: Person = Depends(admin_person)):
    """The latest account events, newest first."""
    rows = db.scalars(select(ActivityLog).order_by(ActivityLog.at.desc(), ActivityLog.id.desc())
                      .limit(min(max(limit, 1), 2000)))
    return {
        "actions": activity.ACTIONS,
        "events": [{"id": r.id, "at": as_utc(r.at).isoformat(), "action": r.action, "actor_email": r.actor_email,
                    "subject_email": r.subject_email, "detail": r.detail, "ip": r.ip} for r in rows],
    }


def _get(db: Session, person_id: int) -> Person:
    person = db.get(Person, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="ไม่พบบุคคลนี้")
    return person


@router.get("/units")
def list_units(db: Session = Depends(get_db), _: Person = Depends(current_person)):
    return [{"id": u.id, "name": u.name} for u in db.scalars(select(Unit).order_by(Unit.name))]


@router.post("/units", status_code=201)
def add_unit(body: UnitIn, db: Session = Depends(get_db), _: Person = Depends(current_person)):
    name = body.name.strip()
    if db.scalar(select(Unit).where(Unit.name == name)):
        raise HTTPException(status_code=409, detail="มีหน่วยงานนี้อยู่แล้ว")
    unit = Unit(name=name)
    db.add(unit)
    db.commit()
    return {"id": unit.id, "name": unit.name}
