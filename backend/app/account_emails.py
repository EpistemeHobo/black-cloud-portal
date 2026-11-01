"""The only emails the portal sends: confirming an address at sign-up, and
setting a new password. Each returns quickly; sending happens in a FastAPI
background task, after the response."""
from fastapi import BackgroundTasks

from app import mailer
from app.auth import RESET, VERIFY, make_link_token
from app.models import Person

PORTAL = "Cloud Developer Portal"


def _send(tasks: BackgroundTasks, kind: str, to: str, subject: str, lines: list[str],
          button: tuple[str, str] | None = None) -> None:
    if not mailer.too_soon(kind, to):
        tasks.add_task(mailer.send, to, subject, lines, button)


def verify_address(tasks: BackgroundTasks, person: Person) -> None:
    _send(tasks, "verify", person.email, f"ยืนยันอีเมลของคุณ · {PORTAL}", [
        f"สวัสดี {person.name}",
        f"กดปุ่มด้านล่างเพื่อยืนยันอีเมลนี้สำหรับ {PORTAL} ลิงก์ใช้ได้ 2 วัน",
        "หลังจากยืนยันแล้ว ผู้ดูแลระบบจะตรวจสอบและอนุมัติบัญชีของคุณ",
        "ถ้าคุณไม่ได้สมัครใช้งาน ไม่ต้องทำอะไร",
    ], ("ยืนยันอีเมล", mailer.link(f"/?verify={make_link_token(person, VERIFY)}")))


def account_exists(tasks: BackgroundTasks, person: Person) -> None:
    """Sent instead of a sign-up confirmation, so sign-up never shows who has an account."""
    _send(tasks, "exists", person.email, f"มีบัญชีนี้อยู่แล้ว · {PORTAL}", [
        f"มีคนพยายามสมัครใช้งาน {PORTAL} ด้วยอีเมลนี้ แต่อีเมลนี้มีบัญชีอยู่แล้ว",
        "ถ้าเป็นคุณและลืมรหัสผ่าน กดปุ่มด้านล่างเพื่อตั้งรหัสผ่านใหม่ ลิงก์ใช้ได้ 1 ชั่วโมง",
        "ถ้าไม่ใช่คุณ ไม่ต้องทำอะไร",
    ], ("ตั้งรหัสผ่านใหม่", mailer.link(f"/?reset={make_link_token(person, RESET)}")))


def reset_password(tasks: BackgroundTasks, person: Person) -> None:
    _send(tasks, "reset", person.email, f"ตั้งรหัสผ่านใหม่ · {PORTAL}", [
        f"สวัสดี {person.name}",
        "กดปุ่มด้านล่างเพื่อตั้งรหัสผ่านใหม่ ลิงก์ใช้ได้ 1 ชั่วโมง และใช้ได้ครั้งเดียว",
        "ถ้าคุณไม่ได้ขอ ไม่ต้องทำอะไร รหัสผ่านเดิมยังใช้ได้",
    ], ("ตั้งรหัสผ่านใหม่", mailer.link(f"/?reset={make_link_token(person, RESET)}")))
