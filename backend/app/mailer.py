"""Sending email through SMTP (for example Resend: smtp.resend.com, user "resend",
the API key as password).

Without SMTP settings the email is written to the log instead, so sign-up and
password reset still work on a developer's machine: the link is in the log.
"""
import logging
import smtplib
import ssl
import time
from email.message import EmailMessage
from html import escape

from app import config

logger = logging.getLogger("portal")

# The same kind of email to the same address at most once a minute, so the
# sign-up and reset forms can't be used to flood someone's inbox.
COOLDOWN_SECONDS = 60
_last_sent: dict[tuple[str, str], float] = {}


def configured() -> bool:
    # A username without its password (an API key not pasted in yet) counts as not set up.
    return bool(config.SMTP_HOST and config.MAIL_FROM and (config.SMTP_PASSWORD or not config.SMTP_USERNAME))


def too_soon(kind: str, to: str) -> bool:
    """True if this kind of email went to this address within the cooldown; otherwise records it."""
    key, now = (kind, to.lower()), time.monotonic()
    if now - _last_sent.get(key, -COOLDOWN_SECONDS) < COOLDOWN_SECONDS:
        return True
    _last_sent[key] = now
    return False


def link(path: str) -> str:
    return f"{config.PUBLIC_BASE_URL}{path}"


def send(to: str, subject: str, lines: list[str], button: tuple[str, str] | None = None) -> None:
    """One short email: a few lines of text and, optionally, one button (label, url).

    Meant to run as a background task: failures are logged, never raised, so the
    person's request doesn't depend on the mail server.
    """
    text = "\n\n".join(lines + ([f"{button[0]}: {button[1]}"] if button else []))
    if not configured():
        logger.info("[MAIL not configured] to=%s subject=%s\n%s", to, subject, text)
        return

    html = "".join(f"<p>{escape(line)}</p>" for line in lines)
    if button:
        html += (f'<p><a href="{escape(button[1])}" style="display:inline-block;padding:10px 18px;'
                 f'background:#0f172a;color:#fff;border-radius:6px;text-decoration:none">{escape(button[0])}</a></p>'
                 f'<p style="color:#64748b;font-size:12px">หรือคัดลอกลิงก์นี้: {escape(button[1])}</p>')
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = config.MAIL_FROM
    msg["To"] = to
    msg.set_content(text)
    msg.add_alternative(f'<div style="font-family:sans-serif;font-size:15px;color:#0f172a">{html}</div>', subtype="html")

    try:
        context = ssl.create_default_context()
        if config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20, context=context)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
            server.starttls(context=context)
        with server:
            if config.SMTP_USERNAME:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Email sent | to=%s subject=%s", to, subject)
    except (OSError, smtplib.SMTPException):
        logger.exception("Email could not be sent | to=%s subject=%s", to, subject)
