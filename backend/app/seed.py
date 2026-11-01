"""Load the standards checklist, and optionally sample systems for local development.

    python -m app.seed           # standards only; safe to run on every deploy
    python -m app.seed --demo    # also sample systems (only when there are none), owned by the seed admin
"""
import json
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, history  # noqa: F401
from app.auth import seed_admin
from app.db import SessionLocal
from app.models import (
    ChecklistItem, Dependency, Link, OpenItem, Person, StandardsVersion, System, SystemRole, Unit, WatchOut,
)
from app.systems_service import count_systems

STANDARDS_FILE = Path(__file__).with_name("standards_v1.json")


def seed_standards(db: Session) -> StandardsVersion:
    """Add the standards version and any missing items. Never overwrites admin edits."""
    data = json.loads(STANDARDS_FILE.read_text(encoding="utf-8"))
    version = db.scalar(select(StandardsVersion).where(StandardsVersion.version == data["version"]))
    if version is None:
        version = StandardsVersion(version=data["version"], status="current", published_at=date.today())
        db.add(version)
        db.flush()
    existing = {i.code for i in version.items}
    for order, raw in enumerate(data["items"]):
        if raw["code"] in existing:
            continue
        db.add(ChecklistItem(
            standards_version_id=version.id, code=raw["code"], category=raw["category"],
            title=raw["title"], from_step=raw["from_step"], level=raw["level"],
            applies_to_types=raw.get("applies_to_types"), how_to_verify=raw.get("how_to_verify", ""),
            kb_path=raw.get("kb_path"), auto_rule=raw.get("auto_rule"), sort_order=order,
        ))
    db.commit()
    db.refresh(version)
    return version


# Demo systems are the ones whose name ends like this.
DEMO_SUFFIX = "(demo)"


def demo_owner(db: Session) -> Person:
    """The seed admin, who owns every demo system, so whoever runs the demo can edit it all."""
    if not config.SEED_ADMIN_EMAIL:
        sys.exit("SEED_ADMIN_EMAIL is not set: demo systems belong to the seed admin. Set it in backend/.env.")
    seed_admin(db)
    person = db.scalar(select(Person).where(Person.email == config.SEED_ADMIN_EMAIL))
    if person is None:
        # No password set yet: the record waits, and becomes the admin's account once one is.
        person = Person(email=config.SEED_ADMIN_EMAIL, name=config.SEED_ADMIN_NAME or config.SEED_ADMIN_EMAIL)
        db.add(person)
        db.flush()
    return person


def give_demo_systems_to(db: Session, owner: Person) -> int:
    """Make the owner the technical owner of every demo system; earlier owners become backups."""
    systems = db.scalars(select(System).where(System.name.endswith(DEMO_SUFFIX))).all()
    for s in systems:
        # The roles the system should end up with, as (person, role) pairs.
        wanted = {(owner.id, "technical_owner")}
        for r in s.roles:
            if r.person_id != owner.id:
                wanted.add((r.person_id, "backup_owner" if r.role == "technical_owner" else r.role))
        have = {(r.person_id, r.role) for r in s.roles}
        for r in list(s.roles):
            if (r.person_id, r.role) not in wanted:
                s.roles.remove(r)
        for person_id, role in wanted - have:
            s.roles.append(SystemRole(person_id=person_id, role=role))
    db.commit()
    return len(systems)


def seed_demo(db: Session, version: StandardsVersion) -> None:
    """Sample data so the pages have something to show. Not real records."""
    owner = demo_owner(db)
    if count_systems(db):
        n = give_demo_systems_to(db, owner)
        print(f"Systems already exist; demo data not added. {n} demo systems now owned by {owner.email}.")
        return
    unit = Unit(name="ฝ่ายไอที T2Gen (ตัวอย่าง)")
    db.add(unit)
    people = [
        Person(email="dev.one@example.org", name="Demo Developer One", unit=unit),
        Person(email="dev.two@example.org", name="Demo Developer Two", unit=unit),
        Person(email="lead@example.org", name="Demo Team Leader", unit=unit),
    ]
    db.add_all(people)
    db.flush()
    one, two, lead = people

    def system(id_, name, type_, step, **fields):
        s = System(id=id_, name=name, type=type_, step=step, owning_unit=unit,
                   standards_version_id=version.id, **fields)
        db.add(s)
        return s

    sso = system("APP-001", "Keycloak SSO (demo)", "Platform", 6,
                 description="ระบบเข้าสู่ระบบครั้งเดียว (SSO) สำหรับเว็บแอปของ T2Gen",
                 if_down="ไม่มีใครเข้าเว็บแอปภายในได้เลย ทุกทีมรู้ภายในไม่กี่นาที", criticality="Critical")
    minio = system("APP-002", "MinIO object storage (demo)", "Infrastructure", 6,
                   description="ที่เก็บไฟล์และชุดข้อมูลแบบ S3", criticality="High")
    cohort = system("APP-003", "Cohort Builder (demo)", "Web app", 6,
                    description="สร้างและตรวจสอบกลุ่มตัวอย่างงานวิจัย (cohort)",
                    if_down="นักวิจัยสร้างคำขอเข้าถึงข้อมูลไม่ได้ ส่วนใหญ่รู้ภายในหนึ่งวันทำการ",
                    run_steps="`pip install -r backend/requirements.txt`\n`uvicorn app.main:app --app-dir backend`",
                    deploy_steps="Merge เข้า main\nรอ GitLab CI สร้าง image และ deploy เสร็จ\nเปิดหน้าเว็บตรวจว่าเข้าสู่ระบบได้",
                    rollback_steps="เปิด GitLab > Pipelines\nกด Retry ที่ job deploy ของ pipeline ก่อนหน้า",
                    tech_stack="Python (FastAPI), Next.js, SQLite", hosting=["On-prem Kubernetes"],
                    criticality="High", data_types=["Genomic", "Health or patient"])
    portal = system("APP-004", "Internal Developer Portal (demo)", "Web app", 3,
                    description="รวบรวมทุกระบบของ T2Gen และแนะนำนักพัฒนาในแต่ละขั้นตอน",
                    if_down="ไม่มีงานใดหยุด แต่คนที่รับช่วงระบบต่อจะหาคู่มือไม่เจอ",
                    tech_stack="Python (FastAPI), Next.js, SQLite")
    db.flush()

    for s, dev, backup in ((sso, two, None), (minio, two, one), (cohort, one, two), (portal, one, None)):
        s.roles.append(SystemRole(person_id=dev.id, role="technical_owner"))
        if backup:
            s.roles.append(SystemRole(person_id=backup.id, role="backup_owner"))
    cohort.roles.append(SystemRole(person_id=lead.id, role="business_owner"))
    cohort.links.append(Link(kind="production_url", url="https://cohort.example.org/"))
    cohort.links.append(Link(kind="source_repo", url="https://gitlab.example.org/t2gen/cohort-builder"))
    portal.links.append(Link(kind="source_repo", url="https://gitlab.example.org/t2gen/developer-portal"))
    for s in (cohort, portal):
        s.dependencies.append(Dependency(to_system_id=sso.id, note="เข้าสู่ระบบ"))
    cohort.dependencies.append(Dependency(to_system_id=minio.id, note="ชุดข้อมูลที่อัปโหลด"))
    cohort.watch_outs.append(WatchOut(kind="trap", text="อย่า restart pod ระหว่างนำเข้าข้อมูลตอนกลางคืน (01:00–03:00)", sort_order=0))
    cohort.watch_outs.append(WatchOut(kind="chore", text="ต่ออายุใบรับรอง TLS", how_often="yearly",
                                      next_due=date(2027, 3, 1), sort_order=1))
    cohort.open_items.append(OpenItem(kind="promise", text="เพิ่มปุ่มส่งออก CSV", promised_to="ทีมวิจัยจีโนม",
                                      due_date=date(2026, 12, 15), sort_order=0))
    cohort.links.append(Link(kind="logs", url="https://grafana.example.org/explore?app=cohort"))
    db.commit()
    give_demo_systems_to(db, owner)
    print(f"Demo data added: 4 systems, 3 people, all owned by {owner.email}.")


def main(argv: list[str]) -> None:
    with SessionLocal() as db:
        version = seed_standards(db)
        print(f"Standards {version.version}: {len(version.items)} checklist items.")
        if "--demo" in argv:
            seed_demo(db, version)


if __name__ == "__main__":
    main(sys.argv[1:])
