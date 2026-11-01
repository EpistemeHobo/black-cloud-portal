from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.enums import (
    CHECKLIST_LEVELS, CHECKLIST_STATUSES, CHORE_FREQUENCIES, DOC_EXTENSIONS, DOC_MAX_CHARS, GUIDE_KEYS, LINK_KINDS,
    OPEN_ITEM_KINDS, REVIEW_PLACES, ROLES, SYSTEM_TYPES, WATCH_OUT_KINDS,
)


def _email(value: str) -> str:
    value = value.strip().lower()
    local, _, domain = value.partition("@")
    if not local or "." not in domain or " " in value:
        raise ValueError("กรุณากรอกอีเมลให้ถูกต้อง")
    return value


class SignIn(BaseModel):
    email: str
    password: str = Field(max_length=200)

    _check_email = field_validator("email")(lambda cls, v: _email(v))


class SignUp(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str
    password: str = Field(max_length=200)

    _check_email = field_validator("email")(lambda cls, v: _email(v))


class EmailIn(BaseModel):
    email: str

    _check_email = field_validator("email")(lambda cls, v: _email(v))


class TokenIn(BaseModel):
    token: str = Field(max_length=2000)


class PasswordFromLink(BaseModel):
    token: str = Field(max_length=2000)
    password: str = Field(max_length=200)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(max_length=200)


class SystemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str
    description: Optional[str] = Field(default=None, max_length=2000)
    if_down: Optional[str] = Field(default=None, max_length=2000)
    step: int = Field(default=1, ge=1, le=7)
    owning_unit_id: Optional[int] = None

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in SYSTEM_TYPES:
            raise ValueError(f"ประเภทระบบต้องเป็นหนึ่งใน: {', '.join(SYSTEM_TYPES)}")
        return v


class RoleIn(BaseModel):
    person_id: int
    role: str
    reachable_until: Optional[date] = None
    note: Optional[str] = Field(default=None, max_length=300)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError("ไม่รู้จักบทบาทนี้")
        return v


class LinkIn(BaseModel):
    kind: str
    url: str = Field(min_length=1, max_length=1000)
    label: Optional[str] = Field(default=None, max_length=200)

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in LINK_KINDS:
            raise ValueError("ไม่รู้จักประเภทลิงก์นี้")
        return v

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        # Only web links: a javascript: or data: URL would run in the reader's browser.
        if not v.lower().startswith(("https://", "http://")):
            raise ValueError("ลิงก์ต้องขึ้นต้นด้วย https:// หรือ http://")
        return v


class DependencyIn(BaseModel):
    to_system_id: Optional[str] = None
    external_name: Optional[str] = Field(default=None, max_length=200)
    note: Optional[str] = Field(default=None, max_length=300)


class WatchOutIn(BaseModel):
    id: Optional[int] = None
    kind: str
    text: str = Field(min_length=1, max_length=1000)
    how_often: Optional[str] = None
    next_due: Optional[date] = None

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in WATCH_OUT_KINDS:
            raise ValueError("ไม่รู้จักประเภทรายการนี้")
        return v

    @field_validator("how_often")
    @classmethod
    def _often(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CHORE_FREQUENCIES:
            raise ValueError("ไม่รู้จักความถี่นี้")
        return v


class OpenItemIn(BaseModel):
    id: Optional[int] = None
    kind: str
    text: str = Field(min_length=1, max_length=1000)
    promised_to: Optional[str] = Field(default=None, max_length=200)
    due_date: Optional[date] = None
    done: bool = False

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if v not in OPEN_ITEM_KINDS:
            raise ValueError("ไม่รู้จักประเภทรายการนี้")
        return v


class DocIn(BaseModel):
    question: str
    filename: str = Field(min_length=1, max_length=200)
    content: str = Field(max_length=DOC_MAX_CHARS)

    @field_validator("question")
    @classmethod
    def _question(cls, v: str) -> str:
        if v not in GUIDE_KEYS:
            raise ValueError("ไม่รู้จักคำถามนี้")
        return v

    @field_validator("filename")
    @classmethod
    def _filename(cls, v: str) -> str:
        # Keep only the base name: a browser may send a path.
        v = v.replace("\\", "/").rsplit("/", 1)[-1].strip()
        if not v.lower().endswith(DOC_EXTENSIONS):
            raise ValueError("รับเฉพาะไฟล์ Markdown (.md)")
        return v

    @field_validator("content")
    @classmethod
    def _content(cls, v: str) -> str:
        if "\x00" in v:
            raise ValueError("ไฟล์นี้ไม่ใช่ข้อความ")
        return v


class AnswerIn(BaseModel):
    status: str
    evidence: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in CHECKLIST_STATUSES:
            raise ValueError("ไม่รู้จักสถานะนี้")
        return v


class StepIn(BaseModel):
    step: int = Field(ge=1, le=7)


class ReviewIn(BaseModel):
    review_date: date
    place: str
    note: str = Field(min_length=1, max_length=5000)

    @field_validator("place")
    @classmethod
    def _place(cls, v: str) -> str:
        if v not in REVIEW_PLACES:
            raise ValueError("ไม่รู้จักสถานที่ทบทวนนี้")
        return v


class PersonIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str
    unit_id: Optional[int] = None

    _check_email = field_validator("email")(lambda cls, v: _email(v))


class PersonAdminPatch(BaseModel):
    is_admin: Optional[bool] = None
    is_auditor: Optional[bool] = None
    # Approve or reactivate ("active"), or suspend.
    status: Optional[Literal["active", "suspended"]] = None
    unit_id: Optional[int] = None





class UnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class ItemPatch(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    category: Optional[str] = Field(default=None, min_length=1, max_length=100)
    from_step: Optional[int] = Field(default=None, ge=1, le=7)
    level: Optional[str] = None
    applies_to_types: Optional[list[str]] = None
    how_to_verify: Optional[str] = Field(default=None, max_length=2000)
    kb_path: Optional[str] = Field(default=None, max_length=300)

    @field_validator("level")
    @classmethod
    def _level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CHECKLIST_LEVELS:
            raise ValueError("ระดับต้องเป็น จำเป็น หรือ แนะนำ")
        return v

    @field_validator("applies_to_types")
    @classmethod
    def _types(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None and any(t not in SYSTEM_TYPES for t in v):
            raise ValueError("ไม่รู้จักประเภทระบบนี้")
        return v
