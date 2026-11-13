"""Leak checks around every save of a system's text (leak_scan.py's layers 1 and 2).

An endpoint that saves free text takes `guard: LeakGuard = Depends()`, then:

    ...apply the change...
    guard.check(system)          # before the commit: refuses a new serious secret
    db.commit()
    guard.after(system.id)       # after it: scans, records alerts, emails the owners
"""
from typing import Iterable, Optional, Union

from fastapi import BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import leak_scan
from app import systems_service as svc
from app.auth import current_person
from app.db import get_db
from app.models import GuideDoc, Person, System


class LeakGuard:
    def __init__(self, background: BackgroundTasks,
                 allow_secrets: bool = Query(False, description="Save even though a secret was found"),
                 db: Session = Depends(get_db), person: Person = Depends(current_person)):
        self.background, self.allow, self.db, self.person = background, allow_secrets, db, person

    def check(self, system: System, extra: Iterable[leak_scan.Place] = ()) -> None:
        leak_scan.check_before_save(system, extra, self.allow)

    def after(self, system_id: str, docs: Union[bool, list[GuideDoc]] = ()) -> None:
        system = svc.get_system(self.db, system_id)
        new, _, _ = leak_scan.scan_system(self.db, system, "save", docs=list(docs) if docs is not True else True)
        self.db.commit()
        if new:
            self.background.add_task(leak_scan.notify, system_id, [a.id for a in new], self.person.id)


def keep_hidden_text(old: Optional[str], new: Optional[str], label: str) -> None:
    """Refuse to save the mask over the real text.

    Someone who sees a field masked (not one of the system's people) and saves it
    unchanged around the mask would otherwise replace the secret-bearing text with
    the mask, and with it whatever else they didn't mean to change.
    """
    if new and leak_scan.REDACTED in new and leak_scan.REDACTED not in (old or ""):
        raise HTTPException(status_code=422, detail=(
            f"{label} มีข้อความที่ถูกซ่อนไว้เพราะดูเหมือนรหัสลับ จึงบันทึกทับไม่ได้ "
            "ให้เจ้าของหรือนักพัฒนาของระบบแก้ข้อความนี้"))
