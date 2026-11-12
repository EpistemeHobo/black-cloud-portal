"""Secret boxes: who may hold a system's encrypted secrets, and checks on what is stored.

Each system can have several boxes (one per environment, say), and each box keeps
every version it was saved as. The browser does all the cryptography
(frontend/src/lib/boxCrypto.ts):

- When a box is made, the browser generates a random 256-bit key (`pvk1_…`) and
  shows it once. Its creator keeps it (a password manager, next to their .env)
  and passes it to whoever takes over. The portal never receives it.
- Contents are encrypted with AES-256-GCM under that key, bound to the box and the
  version number, and only the ciphertext is uploaded.
- A key check (a known text encrypted the same way) lets the browser tell a wrong
  key from a damaged box, and a short key id lets people tell keys apart.

So a database dump, a backup or an admin can't read a box, and a lost key can't be
recovered: the portal is a second copy, never the only place a secret lives
(docs/decisions/0009-secrets.md).

The server still limits who may download ciphertext to the system's people:
encryption is the lock, this is the door.
"""
import base64
import binascii
import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import SECRET_ROLES
from app.models import ChangeLog, Person, SecretBox, System

# IV (12 bytes) + GCM tag (16 bytes): nothing shorter can be a real ciphertext.
MIN_CIPHERTEXT_BYTES = 28
UID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
KEY_ID_PATTERN = re.compile(r"[0-9a-f]{8,16}")


def can_use(person: Person, system: System) -> bool:
    """May download the boxes' ciphertext, add versions and see the leak alerts' details."""
    return any(r.person_id == person.id and r.role in SECRET_ROLES for r in system.roles)


def can_list(person: Person, system: System) -> bool:
    """May see the boxes' names and history and the leak alerts: the people above, and admins."""
    return person.is_admin or can_use(person, system)


def check_ciphertext(value: str, label: str = "ข้อมูลที่เข้ารหัส") -> str:
    """Refuse anything that isn't base64 of at least an IV and a tag: plain text sent by mistake."""
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(status_code=422, detail=f"{label} ไม่ใช่ข้อมูลที่เข้ารหัสแล้ว")
    if len(raw) < MIN_CIPHERTEXT_BYTES:
        raise HTTPException(status_code=422, detail=f"{label} สั้นเกินกว่าจะเป็นข้อมูลที่เข้ารหัส")
    return value


def left_since_key_change(db: Session, system: System, box: SecretBox) -> list[str]:
    """People taken off the system (from a role that could open boxes) since the box's key changed.

    They may still have the old key, so the box's key should be changed and the
    new one given to the people who stay.
    """
    rows = db.scalars(
        select(ChangeLog).where(ChangeLog.system_id == system.id, ChangeLog.entity == "role",
                                ChangeLog.field == "removed", ChangeLog.changed_at > box.key_changed_at)
    ).all()
    current = {f"{r.role}: {r.person.name}" for r in system.roles}
    names: list[str] = []
    for row in rows:
        role, _, name = (row.old_value or "").partition(": ")
        if role in SECRET_ROLES and row.old_value not in current and name not in names:
            names.append(name)
    return names


def find_box(system: System, box_id: int) -> SecretBox:
    box: Optional[SecretBox] = next((b for b in system.secret_boxes if b.id == box_id), None)
    if box is None:
        raise HTTPException(status_code=404, detail="ไม่พบกล่องรหัสลับนี้")
    return box
