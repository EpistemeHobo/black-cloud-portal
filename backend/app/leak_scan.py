"""Finding secrets that were typed or uploaded into a system's pages.

Developers describe how their systems run, paste config into runbooks and attach
markdown files, so a password or an API key ends up in the portal sooner or later.
Like GitHub secret scanning, GitGuardian and Amazon CodeGuru/Macie, three layers:

1. Push protection: a save that adds a likely secret is refused (422, code
   "secret_detected") with what was found, until the person removes it or saves
   again with `?allow_secrets=true` (the frontend asks them first).
2. Every save is scanned and anything found becomes an alert (table secret_alert)
   for the system's people, who are also emailed.
3. Every system, attached files included, is scanned again on a schedule
   (SECRET_SCAN_INTERVAL_HOURS), so a new rule catches what is already there.
   `python -m app.leak_scan` runs the same scan from a cron job.

Meanwhile, anything that looks like a secret is masked for everyone who isn't one
of the system's people (redactor()), so a leak isn't readable while it waits.

The secret itself is never stored: an alert keeps an HMAC fingerprint, to know it
again, and a masked preview such as "ghp_…Zq". Rules are regular expressions with
known prefixes, plus a few generic ones (password = …) filtered for placeholders.
"""
import asyncio
import hashlib
import hmac
import logging
import math
import re
import secrets as _secrets
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Callable, Iterable, Iterator, Optional, Union

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import config, doc_store, mailer, vault
from app.enums import NOT_SECRET_RESOLUTIONS, SECRET_ROLES
from app.fields import FIELDS, GUIDE_FIELDS
from app.models import GuideDoc, Person, SecretAlert, SecretScanRun, System, utcnow

logger = logging.getLogger("portal")

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2}
# Severities that stop a save until the person confirms.
BLOCKING = {"critical", "high"}
# A line with one of these is never reported: for a documented example value.
IGNORE_MARKERS = ("portal:ignore-secret", "pragma: allowlist secret")
REDACTED = "[ซ่อนรหัสลับ]"


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    severity: str
    pattern: re.Pattern
    # Generic rules match any word after "password =": their value must also look random.
    generic: bool = False


def _r(pattern: str, flags: int = 0) -> re.Pattern:
    return re.compile(pattern, flags)


# Group 1 is the secret when the pattern has a group; otherwise the whole match.
RULES: list[Rule] = [
    Rule("portal_box_key", "กุญแจกล่องรหัสลับของพอร์ทัล", "critical", _r(r"\b(pvk1_[A-Za-z0-9_\-]{43})(?![A-Za-z0-9_\-])")),
    Rule("private_key", "กุญแจส่วนตัว (private key)", "critical", _r(
        r"-----BEGIN[A-Z ]{0,30} PRIVATE KEY(?: BLOCK)?-----[\s\S]{0,200}?[A-Za-z0-9+/]{40,}"
        r"[\s\S]*?(?:-----END[A-Z ]{0,30} PRIVATE KEY(?: BLOCK)?-----|$)")),
    Rule("aws_access_key", "AWS access key ID", "critical", _r(r"\b((?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16})\b")),
    Rule("aws_secret_key", "AWS secret access key", "critical", _r(
        r"(?i)aws.{0,10}secret.{0,10}key[\"'\s]*[:=]\s*[\"']?([A-Za-z0-9/+]{40})(?![A-Za-z0-9/+])")),
    Rule("gcp_service_account", "กุญแจ Google Cloud service account", "critical", _r(
        r"\"private_key_id\"\s*:\s*\"([a-f0-9]{40})\"")),
    Rule("azure_storage_key", "Azure storage account key", "critical", _r(r"AccountKey=([A-Za-z0-9+/=]{86,88})")),
    Rule("github_token", "GitHub token", "high", _r(
        r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,255}|github_pat_[A-Za-z0-9_]{22,255})\b")),
    Rule("gitlab_token", "GitLab token", "high", _r(r"\b((?:glpat|gldt|glrt|glptt|glsoat)-[A-Za-z0-9_\-]{20,})")),
    Rule("slack_token", "Slack token", "high", _r(r"\b(xox[abposr]-[A-Za-z0-9-]{10,})")),
    Rule("slack_webhook", "Slack webhook URL", "high", _r(
        r"(https://hooks\.slack\.com/(?:services|workflows)/[A-Za-z0-9/_\-]{20,})")),
    Rule("google_api_key", "Google API key", "high", _r(r"\b(AIza[0-9A-Za-z_\-]{35})(?![0-9A-Za-z_\-])")),
    Rule("google_oauth_secret", "Google OAuth client secret", "high", _r(r"\b(GOCSPX-[A-Za-z0-9_\-]{28})")),
    Rule("stripe_key", "Stripe live key", "high", _r(r"\b((?:sk|rk)_live_[0-9a-zA-Z]{24,})")),
    Rule("openai_key", "OpenAI API key", "high", _r(
        r"\b(sk-(?:proj|svcacct|admin)-[A-Za-z0-9_\-]{40,}|sk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20})")),
    Rule("anthropic_key", "Anthropic API key", "high", _r(r"\b(sk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{80,})")),
    Rule("huggingface_token", "Hugging Face token", "high", _r(r"\b(hf_[A-Za-z0-9]{34,})")),
    Rule("sendgrid_key", "SendGrid API key", "high", _r(r"\b(SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43})")),
    Rule("resend_key", "Resend API key", "high", _r(r"\b(re_[A-Za-z0-9]{8,}_[A-Za-z0-9]{16,})")),
    Rule("npm_token", "npm token", "high", _r(r"\b(npm_[A-Za-z0-9]{36})\b")),
    Rule("telegram_bot_token", "Telegram bot token", "high", _r(r"\b(\d{8,10}:AA[A-Za-z0-9_\-]{33})\b")),
    Rule("url_password", "รหัสผ่านในที่อยู่การเชื่อมต่อ (user:password@host)", "high", _r(
        r"\b[a-zA-Z][a-zA-Z0-9+.\-]{1,20}://[^\s:/@'\"<>]{1,100}:([^\s/@'\"<>]{3,200})@[^\s/'\"<>]+")),
    Rule("bearer_token", "Bearer token ในคำสั่งหรือ header", "high", _r(
        r"(?i)authorization[\"']?\s*[:=]\s*[\"']?bearer\s+([A-Za-z0-9\-._~+/]{20,}=*)")),
    Rule("jwt", "JSON Web Token", "medium", _r(
        r"\b(eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})")),
    Rule("password_assignment", "รหัสผ่านหรือคีย์ที่เขียนไว้ตรง ๆ", "medium", _r(
        r"(?i)\b(?:password|passwd|pwd|pass|secret|client[_\-]?secret|api[_\-]?key|access[_\-]?key|"
        r"auth[_\-]?token|private[_\-]?key|token)\b[\"']?\s*[:=]\s*[\"'`]?([^\s\"'`,;]{8,200})"), generic=True),
    Rule("password_thai", "รหัสผ่านที่เขียนไว้ตรง ๆ", "medium", _r(
        r"(?:รหัสผ่าน|รหัส)\s*(?:คือ|:|：|=)\s*[\"'`]?([^\s\"'`,;]{6,200})"), generic=True),
]
RULES_BY_ID = {r.id: r for r in RULES}

# Values that are examples or references, not secrets.
_PLACEHOLDER_WORDS = (
    "example", "sample", "changeme", "change_me", "your", "xxxx", "****", "....", "…", "<", ">",
    "${", "{{", "%(", "placeholder", "dummy", "redacted", "ซ่อน", "fake", "test1234", "replace",
)
_PLACEHOLDER_EXACT = {"password", "pass", "secret", "token", "none", "null", "true", "false", "required",
                      "optional", "undefined", "string", "env", "masked"}


def _entropy(s: str) -> float:
    counts = Counter(s)
    return -sum(c / len(s) * math.log2(c / len(s)) for c in counts.values())


def _is_placeholder(value: str, generic: bool) -> bool:
    low = value.lower()
    if any(w in low for w in _PLACEHOLDER_WORDS) or low in _PLACEHOLDER_EXACT or len(set(value)) <= 2:
        return True
    if not generic:
        return False
    # password=$DB_PASSWORD, password: DB_PASSWORD, os.environ[...]: references to a secret.
    if value.startswith(("$", "%", "@", "process.env", "os.environ", "env.", "secrets.", "vars.")):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9_]+", value) or re.fullmatch(r"[a-z]+", value):
        return True
    return _entropy(value) < 2.5


@dataclass
class Finding:
    rule: Rule
    start: int
    end: int
    secret: str
    line: int

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.secret)


FINGERPRINT_KEY_FILE = config.INSTANCE_DIR / "leak-fingerprint.key"


@lru_cache(maxsize=1)
def _fingerprint_key() -> bytes:
    """Keys the fingerprints, so a stored fingerprint of a short password can't be
    brute-forced from the database alone. From the session key when it is set (it is
    in production); otherwise from a key file made once beside the database. Changing
    JWT_SECRET_KEY changes every fingerprint: known leaks are then reported once more."""
    if config.JWT_SECRET_FROM_SETTINGS:
        return hmac.new(config.SECRET_KEY.encode("utf-8"), b"portal-leak-fingerprint-v1", hashlib.sha256).digest()
    if not FINGERPRINT_KEY_FILE.exists():
        FINGERPRINT_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        FINGERPRINT_KEY_FILE.write_text(_secrets.token_urlsafe(48), encoding="utf-8")
    return FINGERPRINT_KEY_FILE.read_text(encoding="utf-8").strip().encode("utf-8")


def fingerprint(secret: str) -> str:
    return hmac.new(_fingerprint_key(), secret.encode("utf-8"), hashlib.sha256).hexdigest()


def mask(secret: str) -> str:
    """Enough to recognise which secret it was, not enough to use it."""
    s = secret.strip()
    if s.startswith("-----BEGIN"):
        return s.split("-----")[1][:50]
    if len(s) >= 20:
        return f"{s[:4]}…{s[-2:]}"
    if len(s) >= 10:
        return f"{s[:2]}…"
    return "…"


def find(text: Optional[str]) -> list[Finding]:
    """Every likely secret in the text, without overlaps, in order."""
    if not text:
        return []
    found: list[Finding] = []
    for rule in RULES:
        for m in rule.pattern.finditer(text):
            group = 1 if m.re.groups else 0
            secret = m.group(group)
            if not secret or _is_placeholder(secret, rule.generic):
                continue
            found.append(Finding(rule, m.start(group), m.end(group), secret, 0))
    # Most serious first at each place, then drop anything overlapping what's kept.
    found.sort(key=lambda f: (f.start, SEVERITY_RANK[f.rule.severity], -(f.end - f.start)))
    kept: list[Finding] = []
    for f in found:
        if kept and f.start < kept[-1].end:
            continue
        line_start = text.rfind("\n", 0, f.start) + 1
        line_end = text.find("\n", f.end)
        line = text[line_start: len(text) if line_end == -1 else line_end]
        if any(marker in line for marker in IGNORE_MARKERS):
            continue
        f.line = text.count("\n", 0, f.start) + 1
        kept.append(f)
    return kept


def redact(text: Optional[str], allowed: set[str] = frozenset()) -> Optional[str]:
    """The text with each likely secret replaced, except those owners said aren't secrets."""
    if not text:
        return text
    findings = [f for f in find(text) if f.fingerprint not in allowed]
    for f in reversed(findings):
        text = text[: f.start] + REDACTED + text[f.end:]
    return text


# ---------- Where a system keeps text ----------

@dataclass
class Place:
    kind: str
    key: str
    label: str
    text: Optional[str]


def places(system: System, docs: Union[bool, list[GuideDoc]] = True) -> Iterator[Place]:
    """Every piece of free text on a system. `docs`: all attached files, none, or these."""
    yield Place("field", "name", "ชื่อระบบ", system.name)
    for key, spec in GUIDE_FIELDS.items():
        yield Place("field", key, f"คู่มือรับช่วงต่อ: {spec['label']}", getattr(system, key))
    for key, spec in FIELDS.items():
        if spec["type"] in ("text", "paragraph"):
            yield Place("field", key, f"ข้อมูลแค็ตตาล็อก: {spec['label']}", getattr(system, key))
    for w in system.watch_outs:
        yield Place("watch_out", str(w.id), "ข้อควรระวังและงานประจำ", w.text)
    for o in system.open_items:
        yield Place("open_item", str(o.id), "งานค้าง", "\n".join(filter(None, [o.text, o.promised_to])))
    for link in system.links:
        yield Place("link", str(link.id), "ลิงก์", "\n".join(filter(None, [link.url, link.label])))
    for d in system.dependencies:
        yield Place("dependency", str(d.id), "ระบบที่พึ่งพา", "\n".join(filter(None, [d.external_name, d.note])))
    for r in system.roles:
        yield Place("role", str(r.id), "หมายเหตุของบทบาท", r.note)
    for n in system.reviews:
        yield Place("review", str(n.id), "บันทึกการทบทวน", n.note)
    for a in system.answers:
        code = a.item.code if a.item else str(a.item_id)
        yield Place("checklist", code, f"หลักฐานรายการตรวจสอบ {code}", a.evidence)
    for t in system.tech_debts:
        yield Place("tech_debt", str(t.id), f"หนี้ทางเทคนิค: {t.title[:100]}",
                    "\n".join(filter(None, [t.title, t.description, t.reason, t.impact, t.fix_plan, t.issue_url])))
    for b in system.secret_boxes:
        # Contents are encrypted; the name, description and version notes are not.
        yield Place("box", str(b.id), f"กล่องรหัสลับ {b.name[:100]}",
                    "\n".join(filter(None, [b.name, b.description, *(v.note for v in b.versions)])))
    wanted = system.docs if docs is True else (docs or [])
    for doc in wanted:
        try:
            text = doc_store.read(doc)
        except Exception:  # S3 unreachable: the next scan tries again
            logger.exception("Could not read %s for the leak scan", doc.filename)
            continue
        yield Place("doc", str(doc.id), f"ไฟล์แนบ {doc.filename}", text)


def allowed_fingerprints(system: System) -> set[str]:
    """Fingerprints the system's people said aren't secrets (false positive, test value)."""
    return {a.fingerprint for a in system.secret_alerts
            if a.status == "resolved" and a.resolution in NOT_SECRET_RESOLUTIONS}


def redactor(viewer: Person, system: System) -> Callable[[Optional[str]], Optional[str]]:
    """What to show this viewer: the text as it is to the system's people (and admins, who
    can edit everything and mustn't save a masked copy over it), masked to everyone else."""
    if viewer.is_admin or vault.can_use(viewer, system):
        return lambda text: text
    allowed = allowed_fingerprints(system)
    return lambda text: redact(text, allowed)


# ---------- Push protection ----------

def _finding_json(place: Place, f: Finding) -> dict:
    return {"rule": f.rule.id, "label": f.rule.label, "severity": f.rule.severity,
            "location": place.label, "line": f.line, "preview": mask(f.secret)}


def check_before_save(system: System, extra: Iterable[Place] = (), allow: bool = False) -> None:
    """Refuse a save that adds a serious secret nobody has seen yet.

    Run after the change is applied to the objects and before the commit. Attached
    files aren't re-read here; a file being uploaded comes in through `extra`.
    Secrets already known (an alert exists for them, in any state) don't block,
    so an old leak doesn't stop every later edit.
    """
    if allow:
        return
    known = {a.fingerprint for a in system.secret_alerts}
    new = []
    for place in [*places(system, docs=False), *extra]:
        for f in find(place.text):
            if f.rule.severity in BLOCKING and f.fingerprint not in known:
                new.append(_finding_json(place, f))
    if new:
        raise HTTPException(status_code=422, detail={
            "code": "secret_detected",
            "message": "ข้อความนี้ดูเหมือนมีรหัสลับ ลบออกแล้วเก็บไว้ในกล่องรหัสลับของระบบแทน",
            "findings": new[:20],
        })


# ---------- Scanning and alerts ----------

def scan_system(db: Session, system: System, source: str,
                docs: Union[bool, list[GuideDoc]] = True) -> tuple[list[SecretAlert], int, int]:
    """Scan one system and bring its alerts up to date. Doesn't commit.

    `docs=True` reads every attached file (the scheduled scan); a list scans only
    those files, as after a save, and leaves the other files' alerts as they are.
    Returns (alerts that are new and open, texts scanned, findings).
    """
    now = utcnow()
    existing = {(a.location_kind, a.location_key, a.fingerprint): a for a in system.secret_alerts}
    not_secret = {a.fingerprint: a for a in system.secret_alerts
                  if a.status == "resolved" and a.resolution in NOT_SECRET_RESOLUTIONS}
    seen: set[tuple[str, str, str]] = set()
    new: list[SecretAlert] = []
    texts = findings = 0

    scanned = list(places(system, docs))
    for place in scanned:
        texts += 1
        for f in find(place.text):
            findings += 1
            key = (place.kind, place.key, f.fingerprint)
            if key in seen:
                continue
            seen.add(key)
            alert = existing.get(key)
            if alert is not None:
                alert.last_seen_at, alert.still_present = now, True
                alert.line, alert.location_label = f.line, place.label[:300]
                continue
            alert = SecretAlert(
                rule=f.rule.id, severity=f.rule.severity, location_kind=place.kind, location_key=place.key[:100],
                location_label=place.label[:300], line=f.line, preview=mask(f.secret)[:60],
                fingerprint=f.fingerprint, source=source, first_seen_at=now, last_seen_at=now,
            )
            earlier = not_secret.get(f.fingerprint)
            if earlier is not None:
                # The same text was already judged not a secret elsewhere on this system.
                alert.status, alert.resolution = "resolved", earlier.resolution
                alert.resolution_note, alert.resolved_at = "ตามที่ตัดสินไว้ในที่อื่นของระบบนี้", now
            else:
                new.append(alert)
            system.secret_alerts.append(alert)

    # What a scan in this scope no longer finds has been edited out.
    if docs is True:
        in_scope = lambda a: True  # noqa: E731
    else:
        scanned_docs = {str(d.id) for d in docs or []}
        current_docs = {str(d.id) for d in system.docs}
        in_scope = lambda a: a.location_kind != "doc" or a.location_key in scanned_docs or a.location_key not in current_docs  # noqa: E731
    for key, alert in existing.items():
        if key not in seen and alert.still_present and in_scope(alert):
            alert.still_present = False
    return new, texts, findings


def recipients(system: System, exclude: Optional[Person] = None) -> list[Person]:
    people = {r.person.id: r.person for r in system.roles if r.role in SECRET_ROLES}
    return [p for p in people.values()
            if p.status == "active" and (exclude is None or p.id != exclude.id)]


def notify(system_id: str, alert_ids: list[int], exclude_person_id: Optional[int] = None) -> None:
    """Email the system's people about new alerts. Its own session: runs after the request."""
    if not alert_ids:
        return
    from app.db import SessionLocal

    with SessionLocal() as db:
        system = db.get(System, system_id)
        if system is None:
            return
        alerts = [a for a in system.secret_alerts if a.id in alert_ids]
        exclude = db.get(Person, exclude_person_id) if exclude_person_id else None
        lines = [
            f"พอร์ทัลพบข้อความที่ดูเหมือนรหัสลับ {len(alerts)} รายการในระบบ {system.name} ({system.id}):",
            *[f"• {RULES_BY_ID[a.rule].label if a.rule in RULES_BY_ID else a.rule} ({a.preview}) "
              f"ที่ {a.location_label}" + (f" บรรทัด {a.line}" if a.line else "") for a in alerts[:10]],
            "ถ้าเป็นรหัสจริง ให้เปลี่ยนหรือยกเลิกรหัสนั้นที่ต้นทางก่อน แล้วลบออกจากข้อความ "
            "และเก็บค่าใหม่ไว้ในกล่องรหัสลับของระบบ คนที่ไม่ได้อยู่ในทีมของระบบจะเห็นข้อความนั้นเป็น "
            f"\"{REDACTED}\" ระหว่างนี้",
        ]
        for person in recipients(system, exclude):
            mailer.send(person.email, f"พบรหัสลับรั่วไหลในระบบ {system.name}", lines,
                        button=("เปิดหน้าความปลอดภัยของระบบ", mailer.link(f"/system/?id={system.id}&tab=security")))
        now = utcnow()
        for a in alerts:
            a.notified_at = now
        db.commit()


def run_full_scan(db: Session, trigger: str, started_by: Optional[Person] = None) -> SecretScanRun:
    """Scan every system, attached files included, and email about new alerts."""
    run = SecretScanRun(trigger=trigger, started_by_email=started_by.email if started_by else None)
    db.add(run)
    db.commit()
    to_notify: list[tuple[str, list[int]]] = []
    try:
        for system in db.scalars(select(System).order_by(System.id)):
            new, texts, findings = scan_system(db, system, trigger, docs=True)
            db.commit()
            run.systems_scanned += 1
            run.texts_scanned += texts
            run.findings += findings
            run.new_alerts += len(new)
            if new:
                to_notify.append((system.id, [a.id for a in new]))
    except Exception as exc:  # recorded on the run; the next run tries again
        db.rollback()
        logger.exception("Leak scan failed")
        run.error = f"{type(exc).__name__}: {exc}"[:2000]
    run.finished_at = utcnow()
    db.commit()
    for system_id, ids in to_notify:
        notify(system_id, ids)
    logger.info("Leak scan (%s): %d systems, %d texts, %d findings, %d new alerts",
                trigger, run.systems_scanned, run.texts_scanned, run.findings, run.new_alerts)
    return run


# ---------- The schedule ----------

# How often the loop checks whether a scan is due, and the wait after start-up,
# so a waking portal (hibernate mode) answers its first visitor first.
CHECK_SECONDS = 15 * 60
STARTUP_DELAY_SECONDS = 120


def scan_due(db: Session, now: Optional[datetime] = None) -> bool:
    if config.SECRET_SCAN_INTERVAL_HOURS <= 0:
        return False
    last = db.scalar(select(SecretScanRun.started_at).order_by(SecretScanRun.started_at.desc()).limit(1))
    if last is None:
        return True
    if last.tzinfo is None:  # SQLite gives back naive UTC
        last = last.replace(tzinfo=timezone.utc)
    return (now or datetime.now(timezone.utc)) - last >= timedelta(hours=config.SECRET_SCAN_INTERVAL_HOURS)


def _scheduled_once() -> None:
    from app.db import SessionLocal

    with SessionLocal() as db:
        if scan_due(db):
            run_full_scan(db, "scheduled")


async def scheduler() -> None:
    """Runs inside the app (main.py's lifespan). Several instances may both scan; it's harmless."""
    if config.SECRET_SCAN_INTERVAL_HOURS <= 0:
        return
    await asyncio.sleep(STARTUP_DELAY_SECONDS)
    while True:
        try:
            await asyncio.to_thread(_scheduled_once)
        except Exception:
            logger.exception("Scheduled leak scan failed")
        await asyncio.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    from app.db import SessionLocal

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    with SessionLocal() as session:
        result = run_full_scan(session, "cli")
    print(f"Scanned {result.systems_scanned} systems ({result.texts_scanned} texts): "
          f"{result.findings} findings, {result.new_alerts} new alerts.")
    raise SystemExit(1 if result.error else 0)
