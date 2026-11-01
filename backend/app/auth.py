"""Accounts, passwords and the session cookie.

People sign in with their email and a password the portal stores (as a slow,
salted hash). As in THEIA: signing up makes a "pending" account; the person
proves the address by a link sent to it, then an admin approves. A forgotten
password is replaced through an emailed link. A signed session cookie then
holds the person's id.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import activity, config
from app.db import get_db
from app.history import PERSON_KEY
from app.models import Person

logger = logging.getLogger("portal")

ALGORITHM = "HS256"
SESSION_COOKIE = "portal_session"

PASSWORD_MIN_LENGTH = 8
# Ten wrong passwords within an hour lock the account for 20 minutes.
MAX_FAILED_LOGINS = 10
FAILURE_WINDOW = timedelta(hours=1)
LOCKOUT = timedelta(minutes=20)

# Account states. Only "active" can sign in.
NO_ACCOUNT, PENDING, ACTIVE, SUSPENDED = "no_account", "pending", "active", "suspended"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """SQLite hands datetimes back without a timezone; they were stored as UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


# ---------- Passwords ----------

def hash_password(password: str) -> str:
    """PBKDF2-SHA256 with a random salt. The iteration count is stored with the hash."""
    salt = secrets.token_hex(16)
    iterations = config.PASSWORD_ITERATIONS
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(stored: Optional[str], password: str) -> bool:
    try:
        _, iterations, salt, digest = (stored or "").split("$")
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations)).hex()
    except ValueError:
        return False
    return hmac.compare_digest(test, digest)


# Checked against when there is no account, so an unknown email takes as long
# to refuse as a wrong password and doesn't reveal who has an account.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def check_password_length(password: str) -> None:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise HTTPException(status_code=422, detail=f"รหัสผ่านต้องยาวอย่างน้อย {PASSWORD_MIN_LENGTH} ตัวอักษร")


def set_password(person: Person, password: str) -> None:
    check_password_length(password)
    person.password_hash = hash_password(password)
    person.failed_logins = 0
    person.last_failed_at = None
    person.locked_until = None


# ---------- Signing in ----------

def authenticate(db: Session, email: str, password: str, request: Optional[Request] = None) -> Person:
    """The person for a correct email and password, or an HTTP error.

    A wrong password and an unknown email get the same answer. The account's
    state (waiting for approval, suspended) is only told to someone who knows
    the password.
    """
    email = email.strip().lower()
    person = db.scalar(select(Person).where(Person.email == email))
    wrong = HTTPException(status_code=401, detail="อีเมลหรือรหัสผ่านไม่ถูกต้อง")

    def failed(why: str) -> None:
        activity.record(db, "sign_in_failed", subject_email=email, detail=why, request=request)

    if person is None or person.password_hash is None:
        verify_password(_DUMMY_HASH, password)
        failed("ไม่มีบัญชีนี้")
        raise wrong

    now = utcnow()
    locked_until = as_utc(person.locked_until)
    if locked_until and locked_until > now:
        minutes = max(1, round((locked_until - now).total_seconds() / 60))
        failed("บัญชีถูกล็อกอยู่")
        raise HTTPException(status_code=429,
                            detail=f"ใส่รหัสผ่านผิดหลายครั้งเกินไป กรุณาลองใหม่ในอีกประมาณ {minutes} นาที")

    if not verify_password(person.password_hash, password):
        last = as_utc(person.last_failed_at)
        person.failed_logins = (person.failed_logins if last and now - last < FAILURE_WINDOW else 0) + 1
        person.last_failed_at = now
        if person.failed_logins >= MAX_FAILED_LOGINS:
            person.failed_logins = 0
            person.locked_until = now + LOCKOUT
            logger.warning("Account locked after repeated wrong passwords | person=%s", person.id)
            activity.record(db, "locked", subject=person, detail=f"รหัสผ่านผิด {MAX_FAILED_LOGINS} ครั้ง",
                            request=request, commit=False)
        failed("รหัสผ่านไม่ถูกต้อง")
        raise wrong

    if not person.email_verified:
        failed("ยังไม่ได้ยืนยันอีเมล")
        # A code, so the sign-in page can offer to send the link again.
        raise HTTPException(status_code=403, detail={
            "code": "unverified", "message": "กรุณายืนยันอีเมลก่อน โดยกดลิงก์ในอีเมลที่เราส่งไปให้"})
    if person.status == PENDING:
        failed("รอการอนุมัติ")
        raise HTTPException(status_code=403, detail="บัญชีของคุณรอผู้ดูแลระบบอนุมัติ")
    if person.status != ACTIVE:
        failed("บัญชีถูกระงับ")
        raise HTTPException(status_code=403, detail="บัญชีของคุณถูกระงับ กรุณาติดต่อผู้ดูแลระบบ")

    person.failed_logins = 0
    person.last_failed_at = None
    person.locked_until = None
    person.last_sign_in_at = now
    activity.record(db, "sign_in", actor=person, subject=person, request=request)
    return person


def seed_admin(db: Session) -> None:
    """Create the first admin from SEED_ADMIN_* settings, so someone can approve sign-ups.

    An existing account keeps its password unless SEED_ADMIN_RESET is on, which
    is how a forgotten admin password is replaced.
    """
    email, password = config.SEED_ADMIN_EMAIL, config.SEED_ADMIN_PASSWORD
    if not email or not password:
        if not db.scalar(select(Person.id).where(Person.is_admin, Person.status == ACTIVE)):
            logger.warning("No active admin and SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD are not set: "
                           "nobody can approve sign-ups.")
        return
    person = db.scalar(select(Person).where(Person.email == email))
    if person is None:
        person = Person(email=email, name=config.SEED_ADMIN_NAME or email)
        db.add(person)
    elif person.password_hash and not config.SEED_ADMIN_RESET:
        return
    set_password(person, password)
    person.status = ACTIVE
    person.is_admin = True
    person.email_verified = True
    db.commit()
    logger.info("Seed admin %s is ready.", email)


# ---------- Links sent by email ----------

VERIFY, RESET = "verify", "reset"
LINK_LIFETIME = {VERIFY: timedelta(days=2), RESET: timedelta(hours=1)}


def _password_stamp(person: Person) -> str:
    """Changes whenever the password does, so a reset link works only once."""
    return hashlib.sha256((person.password_hash or "none").encode()).hexdigest()[:16]


def make_link_token(person: Person, purpose: str) -> str:
    claims = {"sub": str(person.id), "purpose": purpose, "exp": utcnow() + LINK_LIFETIME[purpose]}
    if purpose == RESET:
        claims["pw"] = _password_stamp(person)
    return jwt.encode(claims, config.SECRET_KEY, algorithm=ALGORITHM)


def read_link_token(db: Session, token: str, purpose: str) -> Person:
    expired = HTTPException(status_code=400, detail="ลิงก์นี้หมดอายุหรือใช้ไปแล้ว กรุณาขอลิงก์ใหม่")
    try:
        claims = jwt.decode(token, config.SECRET_KEY, algorithms=[ALGORITHM])
        person = db.get(Person, int(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        raise expired
    if person is None or claims.get("purpose") != purpose:
        raise expired
    if "pw" in claims and claims["pw"] != _password_stamp(person):
        raise expired
    return person


# ---------- Session cookie ----------

def set_session(response: Response, person: Person) -> None:
    token = jwt.encode(
        {"sub": str(person.id), "purpose": "session",
         "exp": utcnow() + timedelta(hours=config.SESSION_HOURS)},
        config.SECRET_KEY, algorithm=ALGORITHM,
    )
    response.set_cookie(
        SESSION_COOKIE, token, max_age=config.SESSION_HOURS * 3600,
        httponly=True, secure=config.COOKIE_SECURE, samesite="lax", path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def optional_person(request: Request, db: Session = Depends(get_db)) -> Optional[Person]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        claims = jwt.decode(token, config.SECRET_KEY, algorithms=[ALGORITHM])
        person = db.get(Person, int(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
    # An emailed link's token is signed with the same key; it isn't a session.
    if claims.get("purpose") != "session":
        return None
    # Checked on every request, so suspending someone ends their session at once.
    if person is None or person.status != ACTIVE:
        return None
    db.info[PERSON_KEY] = person.id
    return person


def current_person(person: Optional[Person] = Depends(optional_person)) -> Person:
    if person is None:
        raise HTTPException(status_code=401, detail="กรุณาเข้าสู่ระบบ")
    return person


def admin_person(person: Person = Depends(current_person)) -> Person:
    if not person.is_admin:
        raise HTTPException(status_code=403, detail="เฉพาะผู้ดูแลระบบเท่านั้นที่ทำรายการนี้ได้")
    return person
