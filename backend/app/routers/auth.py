import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import account_emails, activity, cognito, config
from app.auth import (
    ACTIVE, NO_ACCOUNT, PENDING, RESET, VERIFY, authenticate, check_password_length, clear_session,
    current_person, local_passwords, optional_person, read_link_token, set_password, set_session, utcnow,
    verify_password,
)
from app.db import get_db
from app.models import Person
from app.schemas import EmailIn, PasswordChange, PasswordFromLink, SignIn, SignUp, TokenIn

logger = logging.getLogger("portal")

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _me(person: Person) -> dict:
    return {"id": person.id, "name": person.name, "email": person.email, "is_admin": person.is_admin,
            "is_auditor": person.is_auditor}


@router.get("/config")
def auth_config():
    return {"support_email": config.SUPPORT_EMAIL, "allowed_email_domains": config.ALLOWED_EMAIL_DOMAINS,
            "cognito": config.USE_COGNITO, "cognito_logout_url": cognito.logout_url() if config.USE_COGNITO else None}


@router.get("/me")
def me(person: Optional[Person] = Depends(optional_person)):
    return {"person": _me(person) if person else None}


@router.get("/start")
def cognito_start(page: str = "login"):
    """Off to Cognito's sign-in or sign-up page."""
    if not config.USE_COGNITO:
        raise HTTPException(status_code=404, detail="Not Found")
    url, cookie = cognito.begin(page)
    response = RedirectResponse(url, status_code=302)
    # Lax, not Strict: the browser must send it when Cognito redirects back.
    response.set_cookie(cognito.SIGNIN_COOKIE, cookie, max_age=int(cognito.SIGNIN_LIFETIME.total_seconds()),
                        httponly=True, secure=config.COOKIE_SECURE, samesite="lax", path="/api/auth")
    return response


def _person_for_cognito_user(db: Session, claims: dict, request: Request) -> Optional[Person]:
    """The person for a verified Cognito user, signing up someone new as "pending".

    After the first sign-in the permanent id decides, so a later change of address
    at Cognito can't take over someone else's record. None: this can't be let in.
    """
    person = db.scalar(select(Person).where(Person.cognito_sub == claims["sub"]))
    if person is not None:
        return person
    email = claims["email"].strip().lower()
    person = db.scalar(select(Person).where(Person.email == email))
    if person is not None and person.cognito_sub:
        activity.record(db, "sign_in_failed", subject=person, detail="อีเมลนี้ผูกกับผู้ใช้ Cognito คนอื่นแล้ว", request=request)
        return None
    if person is None or person.status == NO_ACCOUNT:
        if not _domain_allowed(email):
            activity.record(db, "sign_in_failed", subject_email=email, detail="โดเมนอีเมลไม่ได้รับอนุญาต", request=request)
            return None
        name = (claims.get("name") or email.split("@")[0]).strip()[:200]
        if person is None:
            person = Person(email=email, name=name)
            db.add(person)
        else:
            person.name = name
        person.status = PENDING
        person.cognito_sub = claims["sub"]
        person.email_verified = True
        activity.record(db, "sign_up", actor=person, subject=person, detail=name, request=request)
        return person
    person.cognito_sub = claims["sub"]
    person.email_verified = True
    return person


@router.get("/callback")
def cognito_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    """Where Cognito sends the browser back. The answer is always a redirect to the portal."""
    if not config.USE_COGNITO:
        raise HTTPException(status_code=404, detail="Not Found")

    def back(outcome: Optional[str] = None) -> RedirectResponse:
        response = RedirectResponse(f"/?signin={outcome}" if outcome else "/", status_code=302)
        response.delete_cookie(cognito.SIGNIN_COOKIE, path="/api/auth")
        return response

    try:
        claims = cognito.finish(code, state, request.cookies.get(cognito.SIGNIN_COOKIE))
    except cognito.SignInFailed as e:
        logger.warning("Cognito sign-in refused: %s", e)
        activity.record(db, "sign_in_failed", detail="Cognito", request=request)
        return back("failed")
    person = _person_for_cognito_user(db, claims, request)
    if person is None:
        return back("refused")
    if person.status == PENDING:
        db.commit()
        return back("pending")
    if person.status != ACTIVE:
        activity.record(db, "sign_in_failed", subject=person, detail="บัญชีถูกระงับ", request=request)
        return back("suspended")
    person.last_sign_in_at = utcnow()
    activity.record(db, "sign_in", actor=person, subject=person, request=request)
    response = back()
    set_session(response, person)
    return response


@router.post("/login", dependencies=[Depends(local_passwords)])
def login(body: SignIn, request: Request, response: Response, db: Session = Depends(get_db)):
    person = authenticate(db, body.email, body.password, request)
    set_session(response, person)
    return {"person": _me(person)}


def _domain_allowed(email: str) -> bool:
    domain = email.rpartition("@")[2]
    return not config.ALLOWED_EMAIL_DOMAINS or any(
        domain == d or domain.endswith("." + d) for d in config.ALLOWED_EMAIL_DOMAINS)


@router.post("/register", status_code=201, dependencies=[Depends(local_passwords)])
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


@router.post("/verify-email", dependencies=[Depends(local_passwords)])
def verify_email(body: TokenIn, request: Request, db: Session = Depends(get_db)):
    person = read_link_token(db, body.token, VERIFY)
    if not person.email_verified:
        person.email_verified = True
        activity.record(db, "email_verified", actor=person, subject=person, request=request)
    return {"status": person.status}


@router.post("/resend-verification", dependencies=[Depends(local_passwords)])
def resend_verification(body: EmailIn, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    person = db.scalar(select(Person).where(Person.email == body.email))
    if person is not None and person.password_hash and not person.email_verified:
        account_emails.verify_address(tasks, person)
    return {"ok": True}


@router.post("/forgot-password", dependencies=[Depends(local_passwords)])
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


@router.post("/reset-password", dependencies=[Depends(local_passwords)])
def reset_password(body: PasswordFromLink, request: Request, db: Session = Depends(get_db)):
    """Set a new password from an emailed link."""
    person = read_link_token(db, body.token, RESET)
    set_password(person, body.password)
    # Opening the link proved the address.
    person.email_verified = True
    activity.record(db, "password_reset", actor=person, subject=person, request=request)
    return {"status": person.status}


@router.put("/password", dependencies=[Depends(local_passwords)])
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
    return {"ok": True, "logout_url": cognito.logout_url() if config.USE_COGNITO else None}
