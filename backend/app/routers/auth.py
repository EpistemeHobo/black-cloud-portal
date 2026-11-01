from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import account_emails, activity, config
from app.auth import (
    NO_ACCOUNT, PENDING, RESET, VERIFY, authenticate, check_password_length, clear_session,
    current_person, optional_person, read_link_token, set_password, set_session, verify_password,
)
from app.db import get_db
from app.models import Person
from app.schemas import EmailIn, PasswordChange, PasswordFromLink, SignIn, SignUp, TokenIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _me(person: Person) -> dict:
    return {"id": person.id, "name": person.name, "email": person.email, "is_admin": person.is_admin,
            "is_auditor": person.is_auditor}


@router.get("/config")
def auth_config():
    return {"support_email": config.SUPPORT_EMAIL, "allowed_email_domains": config.ALLOWED_EMAIL_DOMAINS}


@router.get("/me")
def me(person: Optional[Person] = Depends(optional_person)):
    return {"person": _me(person) if person else None}


@router.post("/login")
def login(body: SignIn, request: Request, response: Response, db: Session = Depends(get_db)):
    person = authenticate(db, body.email, body.password, request)
    set_session(response, person)
    return {"person": _me(person)}


def _domain_allowed(email: str) -> bool:
    domain = email.rpartition("@")[2]
    return not config.ALLOWED_EMAIL_DOMAINS or any(
        domain == d or domain.endswith("." + d) for d in config.ALLOWED_EMAIL_DOMAINS)


@router.post("/register", status_code=201)
def register(body: SignUp, request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Ask for an account: a link goes to the address, then an admin approves.

    The answer is the same whether or not the email already has an account (its
    owner is told by email instead), so this form can't be used to find out who
    has one. Someone already added as an owner takes over that record.
    """
    check_password_length(body.password)
    if not _domain_allowed(body.email):
        raise HTTPException(status_code=422, detail="กรุณาใช้อีเมลขององค์กร: " + ", ".join(config.ALLOWED_EMAIL_DOMAINS))
    person = db.scalar(select(Person).where(Person.email == body.email))
    if person is not None and person.status != NO_ACCOUNT:
        account_emails.account_exists(tasks, person)
        activity.record(db, "sign_up", subject=person, detail="อีเมลนี้มีบัญชีอยู่แล้ว ส่งลิงก์ตั้งรหัสผ่านให้เจ้าของแทน",
                        request=request)
        return {"status": "check_email"}
    if person is None:
        person = Person(email=body.email, name=body.name.strip())
        db.add(person)
    else:
        person.name = body.name.strip()
    set_password(person, body.password)
    person.status = PENDING
    person.email_verified = False
    activity.record(db, "sign_up", actor=person, subject=person, detail=person.name, request=request)
    account_emails.verify_address(tasks, person)
    return {"status": "check_email"}


@router.post("/verify-email")
def verify_email(body: TokenIn, request: Request, db: Session = Depends(get_db)):
    person = read_link_token(db, body.token, VERIFY)
    if not person.email_verified:
        person.email_verified = True
        activity.record(db, "email_verified", actor=person, subject=person, request=request)
    return {"status": person.status}


@router.post("/resend-verification")
def resend_verification(body: EmailIn, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    person = db.scalar(select(Person).where(Person.email == body.email))
    if person is not None and person.password_hash and not person.email_verified:
        account_emails.verify_address(tasks, person)
    return {"ok": True}


@router.post("/forgot-password")
def forgot_password(body: EmailIn, request: Request, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Always the same answer; the link only goes to an address that has an account."""
    person = db.scalar(select(Person).where(Person.email == body.email))
    if person is not None and person.status != NO_ACCOUNT:
        account_emails.reset_password(tasks, person)
        activity.record(db, "reset_requested", subject=person, request=request)
    else:
        activity.record(db, "reset_requested", subject_email=body.email, detail="ไม่มีบัญชีนี้ ไม่ได้ส่งอีเมล",
                        request=request)
    return {"ok": True}


@router.post("/reset-password")
def reset_password(body: PasswordFromLink, request: Request, db: Session = Depends(get_db)):
    """Set a new password from an emailed link."""
    person = read_link_token(db, body.token, RESET)
    set_password(person, body.password)
    # Opening the link proved the address.
    person.email_verified = True
    activity.record(db, "password_reset", actor=person, subject=person, request=request)
    return {"status": person.status}


@router.put("/password")
def change_password(body: PasswordChange, request: Request, db: Session = Depends(get_db),
                    person: Person = Depends(current_person)):
    if not verify_password(person.password_hash, body.current_password):
        raise HTTPException(status_code=422, detail="รหัสผ่านปัจจุบันไม่ถูกต้อง")
    set_password(person, body.new_password)
    activity.record(db, "password_changed", actor=person, subject=person, request=request)
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db),
           person: Optional[Person] = Depends(optional_person)):
    if person is not None:
        activity.record(db, "sign_out", actor=person, subject=person, request=request)
    clear_session(response)
    return {"ok": True}
