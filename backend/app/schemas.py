from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.enums import (
    ALERT_RESOLUTIONS, CHECKLIST_LEVELS, CHECKLIST_STATUSES, CHORE_FREQUENCIES, DEBT_RISKS, DEBT_STATUSES,
    DOC_EXTENSIONS, DOC_MAX_CHARS, GUIDE_KEYS, LINK_KINDS, OPEN_ITEM_KINDS, REVIEW_PLACES, ROLES,
    SYSTEM_TYPES, WATCH_OUT_KINDS,
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


class TechDebtIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=5000)
    reason: Optional[str] = Field(default=None, max_length=5000)
    impact: Optional[str] = Field(default=None, max_length=5000)
    fix_plan: Optional[str] = Field(default=None, max_length=5000)
    risk: str = "Medium"
    effort: Optional[str] = Field(default=None, max_length=50)
    target_date: Optional[date] = None
    issue_url: Optional[str] = Field(default=None, max_length=1000)
    status: str = "open"

    @field_validator("risk")
    @classmethod
    def _risk(cls, v: str) -> str:
        if v not in DEBT_RISKS:
            raise ValueError("ความเสี่ยงต้องเป็น สูง ปานกลาง หรือ ต่ำ")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in DEBT_STATUSES:
            raise ValueError("ไม่รู้จักสถานะนี้")
        return v

    @field_validator("issue_url")
    @classmethod
    def _issue_url(cls, v: Optional[str]) -> Optional[str]:
        v = (v or "").strip()
        if v and not v.lower().startswith(("https://", "http://")):
            raise ValueError("ลิงก์ issue ต้องขึ้นต้นด้วย https:// หรือ http://")
        return v or None


# A box's contents, encrypted: base64 of IV + AES-GCM ciphertext. 400,000 characters
# is about 300 KB, far more than any .env.
CIPHERTEXT_MAX = 400_000


def _box_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("กรุณาตั้งชื่อกล่อง")
    return v


class BoxCreate(BaseModel):
    uid: str = Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    key_id: str = Field(pattern=r"^[0-9a-f]{8,16}$")
    key_check: str = Field(min_length=40, max_length=200)
    ciphertext: str = Field(min_length=40, max_length=CIPHERTEXT_MAX)
    note: Optional[str] = Field(default=None, max_length=300)

    _check_name = field_validator("name")(lambda cls, v: _box_name(v))


class BoxPatch(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)

    _check_name = field_validator("name")(lambda cls, v: _box_name(v))


class BoxVersionIn(BaseModel):
    # The version the browser last saw: a save on top of someone else's is refused (409).
    expected_version: int = Field(ge=1)
    ciphertext: str = Field(min_length=40, max_length=CIPHERTEXT_MAX)
    note: Optional[str] = Field(default=None, max_length=300)


class BoxVersionCipher(BaseModel):
    version: int = Field(ge=1)
    ciphertext: str = Field(min_length=40, max_length=CIPHERTEXT_MAX)


class BoxKeyChange(BaseModel):
    """Every version, re-encrypted in the browser under a new key, replacing the old ones at once."""
    expected_version: int = Field(ge=1)
    key_id: str = Field(pattern=r"^[0-9a-f]{8,16}$")
    key_check: str = Field(min_length=40, max_length=200)
    versions: list[BoxVersionCipher] = Field(min_length=1, max_length=1000)


class AlertResolveIn(BaseModel):
    # None reopens the alert.
    resolution: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("resolution")
    @classmethod
    def _resolution(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALERT_RESOLUTIONS:
            raise ValueError("ไม่รู้จักวิธีปิดการแจ้งเตือนนี้")
        return v
