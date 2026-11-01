"""Recording account events for the admins' activity page (ประวัติการใช้งาน)."""
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import ActivityLog, Person

# What each action means, in Thai, for the page.
ACTIONS = {
    "sign_in": "เข้าสู่ระบบ",
    "sign_in_failed": "เข้าสู่ระบบไม่สำเร็จ",
    "locked": "บัญชีถูกล็อกชั่วคราว",
    "sign_out": "ออกจากระบบ",
    "sign_up": "สมัครใช้งาน",
    "email_verified": "ยืนยันอีเมล",
    "reset_requested": "ขอลิงก์ตั้งรหัสผ่านใหม่",
    "password_reset": "ตั้งรหัสผ่านใหม่จากลิงก์",
    "password_changed": "เปลี่ยนรหัสผ่าน",
    "approved": "อนุมัติบัญชี",
    "rejected": "ปฏิเสธคำขอ",
    "suspended": "ระงับบัญชี",
    "reactivated": "เปิดใช้บัญชีอีกครั้ง",
    "role_changed": "เปลี่ยนสิทธิ์",
    "reset_link_sent": "ส่งลิงก์ตั้งรหัสผ่านให้",
}


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None or request.client is None:
        return None
    return request.client.host


def record(db: Session, action: str, *, actor: Optional[Person] = None, subject: Optional[Person] = None,
           subject_email: Optional[str] = None, detail: Optional[str] = None,
           request: Optional[Request] = None, commit: bool = True) -> None:
    db.add(ActivityLog(
        action=action,
        actor_email=actor.email if actor else None,
        subject_email=subject.email if subject else subject_email,
        detail=detail, ip=client_ip(request),
    ))
    if commit:
        db.commit()
