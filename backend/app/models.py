"""Database tables. See docs/data-model.md."""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Unit(Base):
    __tablename__ = "unit"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("unit.id"))


class Person(Base):
    __tablename__ = "person"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("unit.id"))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    # Auditors fill in catalog info on any system.
    is_auditor: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # The portal's own sign-in account (see auth.py). "no_account" is someone
    # added as an owner who has never signed up; "pending" waits for an admin.
    status: Mapped[str] = mapped_column(String(20), default="no_account")
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    # Cognito's permanent id for this person, set at their first sign-in through it.
    cognito_sub: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    # Set by the link emailed at sign-up (or any emailed link the person opened).
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sign_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    # Failed-password lockout.
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    last_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    unit: Mapped[Optional[Unit]] = relationship()


class StandardsVersion(Base):
    __tablename__ = "standards_version"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="current")
    published_at: Mapped[Optional[date]] = mapped_column(Date)

    items: Mapped[list["ChecklistItem"]] = relationship(
        back_populates="standards_version", order_by="ChecklistItem.sort_order"
    )


class ChecklistItem(Base):
    __tablename__ = "checklist_item"
    __table_args__ = (UniqueConstraint("standards_version_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    standards_version_id: Mapped[int] = mapped_column(ForeignKey("standards_version.id"))
    code: Mapped[str] = mapped_column(String(10))
    category: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    from_step: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(20), default="required")
    # Empty or null means the item applies to every system type.
    applies_to_types: Mapped[Optional[list]] = mapped_column(JSON)
    how_to_verify: Mapped[str] = mapped_column(Text, default="")
    kb_path: Mapped[Optional[str]] = mapped_column(String(300))
    auto_rule: Mapped[Optional[str]] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    standards_version: Mapped[StandardsVersion] = relationship(back_populates="items")


class System(Base):
    __tablename__ = "system"
    __table_args__ = (CheckConstraint("step BETWEEN 1 AND 7", name="step_range"),)

    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(50))
    step: Mapped[int] = mapped_column(Integer, default=1)
    lifecycle_state: Mapped[str] = mapped_column(String(30), default="Active")
    owning_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("unit.id"))
    standards_version_id: Mapped[Optional[int]] = mapped_column(ForeignKey("standards_version.id"))

    # Handover guide (docs/handover-guide.md). Step fields hold one step per line.
    description: Mapped[Optional[str]] = mapped_column(Text)
    if_down: Mapped[Optional[str]] = mapped_column(Text)
    run_steps: Mapped[Optional[str]] = mapped_column(Text)
    deploy_steps: Mapped[Optional[str]] = mapped_column(Text)
    rollback_steps: Mapped[Optional[str]] = mapped_column(Text)
    # Guide questions the writer marked as having nothing to list.
    guide_nothing: Mapped[Optional[list]] = mapped_column(JSON)

    # Catalog info, filled in by auditors (fields.py)
    aliases: Mapped[Optional[str]] = mapped_column(String(300))
    developed_by: Mapped[Optional[str]] = mapped_column(String(50))
    go_live_date: Mapped[Optional[date]] = mapped_column(Date)
    planned_retirement_date: Mapped[Optional[date]] = mapped_column(Date)
    # Users and criticality
    user_groups: Mapped[Optional[str]] = mapped_column(String(300))
    user_count_estimate: Mapped[Optional[str]] = mapped_column(String(20))
    internal_or_external: Mapped[Optional[str]] = mapped_column(String(30))
    criticality: Mapped[Optional[str]] = mapped_column(String(20))
    max_tolerable_downtime: Mapped[Optional[str]] = mapped_column(String(100))
    # How it is built and run
    tech_stack: Mapped[Optional[str]] = mapped_column(Text)
    hosting: Mapped[Optional[list]] = mapped_column(JSON)
    server_or_location: Mapped[Optional[str]] = mapped_column(String(300))
    environments: Mapped[Optional[list]] = mapped_column(JSON)
    ci_cd: Mapped[Optional[str]] = mapped_column(String(20))
    deployment_method: Mapped[Optional[str]] = mapped_column(String(30))
    database: Mapped[Optional[str]] = mapped_column(String(300))
    integrations_apis: Mapped[Optional[str]] = mapped_column(Text)
    # Data and security
    data_types: Mapped[Optional[list]] = mapped_column(JSON)
    data_classification: Mapped[Optional[str]] = mapped_column(String(30))
    authentication: Mapped[Optional[list]] = mapped_column(JSON)
    access_control: Mapped[Optional[str]] = mapped_column(Text)
    data_storage_location: Mapped[Optional[str]] = mapped_column(String(300))
    data_leaves_org: Mapped[Optional[str]] = mapped_column(String(300))
    backup: Mapped[Optional[str]] = mapped_column(String(20))
    backup_frequency_and_location: Mapped[Optional[str]] = mapped_column(String(300))
    last_restore_test: Mapped[Optional[date]] = mapped_column(Date)
    last_security_review: Mapped[Optional[date]] = mapped_column(Date)
    known_vulnerabilities_or_risks: Mapped[Optional[str]] = mapped_column(Text)
    compliance_requirements: Mapped[Optional[str]] = mapped_column(String(300))
    # Cost and contracts
    license_type: Mapped[Optional[str]] = mapped_column(String(50))
    annual_cost: Mapped[Optional[str]] = mapped_column(String(100))
    contract_renewal_date: Mapped[Optional[date]] = mapped_column(Date)
    funding_source: Mapped[Optional[str]] = mapped_column(String(200))
    # Current state
    version: Mapped[Optional[str]] = mapped_column(String(50))
    last_major_update: Mapped[Optional[date]] = mapped_column(Date)

    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owning_unit: Mapped[Optional[Unit]] = relationship()
    standards_version: Mapped[Optional[StandardsVersion]] = relationship()
    verified_by: Mapped[Optional[Person]] = relationship()
    roles: Mapped[list["SystemRole"]] = relationship(back_populates="system", cascade="all, delete-orphan")
    links: Mapped[list["Link"]] = relationship(back_populates="system", cascade="all, delete-orphan")
    dependencies: Mapped[list["Dependency"]] = relationship(
        back_populates="from_system", cascade="all, delete-orphan",
        foreign_keys="Dependency.from_system_id",
    )
    answers: Mapped[list["ChecklistAnswer"]] = relationship(back_populates="system", cascade="all, delete-orphan")
    reviews: Mapped[list["ReviewNote"]] = relationship(
        back_populates="system", cascade="all, delete-orphan", order_by="ReviewNote.review_date.desc()"
    )
    watch_outs: Mapped[list["WatchOut"]] = relationship(
        back_populates="system", cascade="all, delete-orphan", order_by="WatchOut.sort_order"
    )
    open_items: Mapped[list["OpenItem"]] = relationship(
        back_populates="system", cascade="all, delete-orphan", order_by="OpenItem.sort_order"
    )
    docs: Mapped[list["GuideDoc"]] = relationship(
        back_populates="system", cascade="all, delete-orphan", order_by="GuideDoc.filename"
    )
    tech_debts: Mapped[list["TechDebt"]] = relationship(
        back_populates="system", cascade="all, delete-orphan", order_by="TechDebt.id"
    )
    secrets: Mapped[list["SystemSecret"]] = relationship(
        back_populates="system", cascade="all, delete-orphan", order_by="SystemSecret.name"
    )
    secret_alerts: Mapped[list["SecretAlert"]] = relationship(
        back_populates="system", cascade="all, delete-orphan", order_by="SecretAlert.id"
    )


class SystemRole(Base):
    __tablename__ = "system_role"
    __table_args__ = (UniqueConstraint("system_id", "person_id", "role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    person_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    role: Mapped[str] = mapped_column(String(30))
    # Mostly for a previous owner: until when they can be asked, and about what.
    reachable_until: Mapped[Optional[date]] = mapped_column(Date)
    note: Mapped[Optional[str]] = mapped_column(String(300))

    system: Mapped[System] = relationship(back_populates="roles")
    person: Mapped[Person] = relationship()


class Link(Base):
    __tablename__ = "link"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    url: Mapped[str] = mapped_column(String(1000))
    label: Mapped[Optional[str]] = mapped_column(String(200))

    system: Mapped[System] = relationship(back_populates="links")


class Dependency(Base):
    __tablename__ = "dependency"
    __table_args__ = (
        CheckConstraint(
            "(to_system_id IS NULL) != (external_name IS NULL)", name="one_target"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    to_system_id: Mapped[Optional[str]] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    external_name: Mapped[Optional[str]] = mapped_column(String(200))
    note: Mapped[Optional[str]] = mapped_column(String(300))

    from_system: Mapped[System] = relationship(back_populates="dependencies", foreign_keys=[from_system_id])
    to_system: Mapped[Optional[System]] = relationship(foreign_keys=[to_system_id])


class WatchOut(Base):
    """Guide question 4: a trap to avoid, or a chore someone must remember to do."""
    __tablename__ = "watch_out"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    how_often: Mapped[Optional[str]] = mapped_column(String(20))
    next_due: Mapped[Optional[date]] = mapped_column(Date)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    system: Mapped[System] = relationship(back_populates="watch_outs")


class OpenItem(Base):
    """Guide question 7: unfinished work, a promise or an open decision."""
    __tablename__ = "open_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    promised_to: Mapped[Optional[str]] = mapped_column(String(200))
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    done_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    system: Mapped[System] = relationship(back_populates="open_items")
    done_by: Mapped[Optional[Person]] = relationship()


class GuideDoc(Base):
    """A markdown file a developer attached to one handover question, such as a runbook."""
    __tablename__ = "guide_doc"
    __table_args__ = (UniqueConstraint("system_id", "question", "filename"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    question: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(200))
    # The text, unless it is in S3 under s3_key (doc_store.py); read it with doc_store.read().
    content: Mapped[Optional[str]] = mapped_column(Text)
    s3_key: Mapped[Optional[str]] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64))  # SHA-256 of the text
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    system: Mapped[System] = relationship(back_populates="docs")
    updated_by: Mapped[Optional[Person]] = relationship()


class ChecklistAnswer(Base):
    __tablename__ = "checklist_answer"
    __table_args__ = (UniqueConstraint("system_id", "item_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    item_id: Mapped[int] = mapped_column(ForeignKey("checklist_item.id"))
    status: Mapped[str] = mapped_column(String(20))
    evidence: Mapped[Optional[str]] = mapped_column(Text)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    system: Mapped[System] = relationship(back_populates="answers")
    item: Mapped[ChecklistItem] = relationship()
    updated_by: Mapped[Optional[Person]] = relationship()


class ReviewNote(Base):
    __tablename__ = "review_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("person.id"))
    review_date: Mapped[date] = mapped_column(Date)
    place: Mapped[str] = mapped_column(String(30))
    step: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    system: Mapped[System] = relationship(back_populates="reviews")
    reviewer: Mapped[Person] = relationship()


class ChangeLog(Base):
    __tablename__ = "change_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(50))
    field: Mapped[str] = mapped_column(String(100))
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    changed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    changed_by: Mapped[Optional[Person]] = relationship()


class ActivityLog(Base):
    """Account events for admins: sign-ins, sign-ups, approvals, password resets.

    Emails are copied in rather than linked, so the record outlives a deleted
    (rejected) person and says who it was.
    """
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    # Who did it (None for someone not signed in) and whose account it was about.
    actor_email: Mapped[Optional[str]] = mapped_column(String(320))
    subject_email: Mapped[Optional[str]] = mapped_column(String(320))
    detail: Mapped[Optional[str]] = mapped_column(Text)
    ip: Mapped[Optional[str]] = mapped_column(String(64))


class TechDebt(Base):
    """A shortcut taken on purpose, with the plan to fix it (docs/technical_debt.md's fields)."""
    __tablename__ = "tech_debt"

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    # What it is, why we took it on, what happens if we leave it, how to fix it.
    description: Mapped[Optional[str]] = mapped_column(Text)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    impact: Mapped[Optional[str]] = mapped_column(Text)
    fix_plan: Mapped[Optional[str]] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String(10), default="Medium")
    effort: Mapped[Optional[str]] = mapped_column(String(50))
    target_date: Mapped[Optional[date]] = mapped_column(Date)
    issue_url: Mapped[Optional[str]] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    system: Mapped[System] = relationship(back_populates="tech_debts")
    created_by: Mapped[Optional[Person]] = relationship()


class SystemSecret(Base):
    """One value in a system's secrets vault, encrypted (vault.py).

    Only the system's people in enums.SECRET_ROLES can read the value. Nothing
    about the value (not even its length) is kept in clear.
    """
    __tablename__ = "system_secret"
    __table_args__ = (UniqueConstraint("system_id", "name", "environment"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    environment: Mapped[str] = mapped_column(String(20), default="All")
    description: Mapped[Optional[str]] = mapped_column(String(500))
    ciphertext: Mapped[str] = mapped_column(Text)
    created_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    # When the value itself last changed: a secret nobody has rotated in a year shows it.
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_revealed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_revealed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))

    system: Mapped[System] = relationship(back_populates="secrets")
    created_by: Mapped[Optional[Person]] = relationship(foreign_keys=[created_by_id])
    updated_by: Mapped[Optional[Person]] = relationship(foreign_keys=[updated_by_id])
    last_revealed_by: Mapped[Optional[Person]] = relationship(foreign_keys=[last_revealed_by_id])


class SecretAlert(Base):
    """Something that looks like a secret, found in a system's text (leak_scan.py).

    The secret itself is never stored: only a keyed fingerprint, to recognise it
    again, and a masked preview. One row per secret and place it was found.
    """
    __tablename__ = "secret_alert"
    __table_args__ = (UniqueConstraint("system_id", "location_kind", "location_key", "fingerprint"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    system_id: Mapped[str] = mapped_column(ForeignKey("system.id", ondelete="CASCADE"), index=True)
    rule: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    # Where: a kind (field, doc, watch_out...), its key (field name, row id), a label to show.
    location_kind: Mapped[str] = mapped_column(String(20))
    location_key: Mapped[str] = mapped_column(String(100))
    location_label: Mapped[str] = mapped_column(String(300))
    line: Mapped[Optional[int]] = mapped_column(Integer)
    preview: Mapped[str] = mapped_column(String(60))
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    # "open" until an owner closes it ("resolved") with one of enums.ALERT_RESOLUTIONS.
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolution: Mapped[Optional[str]] = mapped_column(String(20))
    resolution_note: Mapped[Optional[str]] = mapped_column(String(500))
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("person.id"))
    # False once a scan no longer finds it there (edited out). It stays exposed in
    # the change history and in anyone's copy, so the alert stays open until closed.
    still_present: Mapped[bool] = mapped_column(Boolean, default=True)
    # How it was first found: "save" (a change as it was saved), "scheduled", "manual" or "cli".
    source: Mapped[str] = mapped_column(String(20))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    system: Mapped[System] = relationship(back_populates="secret_alerts")
    resolved_by: Mapped[Optional[Person]] = relationship()


class SecretScanRun(Base):
    """One scan of every system for leaked secrets: scheduled, started by an admin, or the CLI."""
    __tablename__ = "secret_scan_run"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    systems_scanned: Mapped[int] = mapped_column(Integer, default=0)
    texts_scanned: Mapped[int] = mapped_column(Integer, default=0)
    findings: Mapped[int] = mapped_column(Integer, default=0)
    new_alerts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text)
    started_by_email: Mapped[Optional[str]] = mapped_column(String(320))
