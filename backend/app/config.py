"""Settings, read once from the environment (and from backend/.env when present)."""
import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

logger = logging.getLogger("portal")


def _bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _list(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()
IS_PRODUCTION = ENVIRONMENT == "production"

INSTANCE_DIR = Path(os.environ.get("INSTANCE_DIR", BACKEND_DIR / "instance"))
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{(INSTANCE_DIR / 'portal.db').as_posix()}"

_secret = os.environ.get("JWT_SECRET_KEY", "")
if not _secret:
    if IS_PRODUCTION:
        raise RuntimeError("JWT_SECRET_KEY must be set when ENVIRONMENT=production.")
    # Development only: a new key per start, so sessions end on every restart.
    _secret = secrets.token_urlsafe(48)
SECRET_KEY = _secret
SESSION_HOURS = int(os.environ.get("SESSION_HOURS", "12"))

COOKIE_SECURE = _bool("COOKIE_SECURE", IS_PRODUCTION)
ALLOWED_HOSTS = _list("ALLOWED_HOSTS") or ["*"]
# Only needed when the Next.js dev server runs on a different port from the API.
ALLOWED_ORIGINS = _list("ALLOWED_ORIGINS")

# The first admin, created at start-up so someone can approve sign-ups.
# SEED_ADMIN_RESET=true re-applies the password to an existing account (for a
# forgotten one); turn it off again afterwards.
SEED_ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "").strip().lower()
SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "")
SEED_ADMIN_NAME = os.environ.get("SEED_ADMIN_NAME", "").strip()
SEED_ADMIN_RESET = _bool("SEED_ADMIN_RESET", False)
if SEED_ADMIN_PASSWORD and len(SEED_ADMIN_PASSWORD) < 12 and IS_PRODUCTION:
    raise RuntimeError("SEED_ADMIN_PASSWORD must be at least 12 characters in production.")

# Email, for verifying addresses and resetting passwords (see mailer.py).
# With Resend: SMTP_HOST=smtp.resend.com, SMTP_USERNAME=resend, SMTP_PASSWORD=<API key>,
# and MAIL_FROM on a domain verified in Resend. Unset: emails go to the log.
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_FROM = os.environ.get("MAIL_FROM", "").strip()
# The portal's own address, for the links in emails.
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
if IS_PRODUCTION and not (SMTP_HOST and MAIL_FROM and os.environ.get("PUBLIC_BASE_URL")):
    raise RuntimeError("SMTP_HOST, MAIL_FROM and PUBLIC_BASE_URL must be set in production: "
                       "sign-up and password reset send emails.")

# Only these email domains may sign up (comma-separated, subdomains included).
# Empty: any domain.
ALLOWED_EMAIL_DOMAINS = [d.lower().lstrip("@") for d in _list("ALLOWED_EMAIL_DOMAINS")]

# PBKDF2 rounds for new password hashes. Lowered only to make tests fast.
PASSWORD_ITERATIONS = int(os.environ.get("PASSWORD_ITERATIONS", "600000"))

# Shown on the sign-in page as the person to contact, by email and on Webex.
# Defaults to the seed admin.
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "").strip() or SEED_ADMIN_EMAIL

# Checklist items link to pages under this address.
KB_BASE_URL = os.environ.get("KB_BASE_URL", "").rstrip("/")

# A relative path is taken from the backend folder, whatever the working directory.
FRONTEND_DIR = BACKEND_DIR / os.environ.get("FRONTEND_DIR", "static_frontend")
