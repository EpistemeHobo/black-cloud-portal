"""The secrets vault: encrypting the values a system's people keep in the portal.

Each value is encrypted with Fernet (AES-128-CBC plus an HMAC-SHA256, from the
`cryptography` package) under a key derived from SECRETS_ENCRYPTION_KEY. The
database only ever holds the ciphertext, so a database dump or backup on its own
doesn't give the secrets away; the key lives elsewhere (SSM or Secrets Manager on
AWS, the Kubernetes secret on-premises).

Who may read a value is decided by can_use() below: only the system's people in
enums.SECRET_ROLES. Admins see the list of names, not the values
(docs/decisions/0009-secrets.md).

Rotating the key: put the new key first in SECRETS_ENCRYPTION_KEY (comma-separated,
old one after it), restart, run `python -m app.vault rotate`, then remove the old key.
"""
import base64
import hashlib
import hmac
import logging
import secrets as _secrets
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app import config
from app.enums import SECRET_ROLES
from app.models import Person, System

logger = logging.getLogger("portal")

KEY_FILE = config.INSTANCE_DIR / "vault.key"


class VaultUnavailable(Exception):
    """No encryption key is set up, so the vault is switched off."""


def _derive(key: str, purpose: bytes) -> bytes:
    # Any 32+ character string works as the setting (Secrets Manager makes one);
    # Fernet wants 32 bytes in url-safe base64. A different purpose gives an
    # unrelated key, so the fingerprint key never equals the encryption key.
    return base64.urlsafe_b64encode(hmac.new(key.encode("utf-8"), purpose, hashlib.sha256).digest())


@lru_cache(maxsize=1)
def _keys() -> tuple[str, ...]:
    if config.SECRETS_ENCRYPTION_KEYS:
        return tuple(config.SECRETS_ENCRYPTION_KEYS)
    if not config.DATABASE_URL.startswith("sqlite"):
        # A key made up on this instance would be lost with it, and every stored
        # value with it. Better no vault than an unreadable one.
        return ()
    # A developer's machine: a key file beside the SQLite database, made once.
    if not KEY_FILE.exists():
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(_secrets.token_urlsafe(48), encoding="utf-8")
        logger.info("Made a new vault key at %s", KEY_FILE)
    return (KEY_FILE.read_text(encoding="utf-8").strip(),)


def configured() -> bool:
    return bool(_keys())


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    keys = _keys()
    if not keys:
        raise VaultUnavailable()
    return MultiFernet([Fernet(_derive(k, b"portal-vault-v1")) for k in keys])


def encrypt(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken:
        # Wrong or missing key: say so in the log, never show the ciphertext.
        logger.error("A vault value could not be decrypted: is the key in SECRETS_ENCRYPTION_KEY?")
        raise


def try_decrypt(ciphertext: str) -> Optional[str]:
    try:
        return decrypt(ciphertext)
    except (InvalidToken, VaultUnavailable):
        return None


def fingerprint_key() -> bytes:
    """Keys the leak scanner's fingerprints, so a stored fingerprint of a short
    password can't be brute-forced from the database alone. The last (oldest)
    key, so rotating the encryption key doesn't change every fingerprint."""
    keys = _keys()
    if not keys:
        return b"portal-leak-fingerprint"
    return _derive(keys[-1], b"portal-leak-fingerprint-v1")


def can_use(person: Person, system: System) -> bool:
    """May read and change the system's vault values and see its leak alerts' details."""
    return any(r.person_id == person.id and r.role in SECRET_ROLES for r in system.roles)


def can_list(person: Person, system: System) -> bool:
    """May see the vault's names and the leak alerts: the people above, and admins."""
    return person.is_admin or can_use(person, system)


def rotate_all(db) -> int:
    """Re-encrypt every value under the first key. Returns how many."""
    from sqlalchemy import select

    from app.models import SystemSecret

    count = 0
    for row in db.scalars(select(SystemSecret)):
        row.ciphertext = _fernet().rotate(row.ciphertext.encode("ascii")).decode("ascii")
        count += 1
    db.commit()
    return count


if __name__ == "__main__":
    import sys

    from app.db import SessionLocal

    if sys.argv[1:] != ["rotate"]:
        raise SystemExit("Usage: python -m app.vault rotate")
    if not configured():
        raise SystemExit("Set SECRETS_ENCRYPTION_KEY first.")
    with SessionLocal() as session:
        print(f"Re-encrypted {rotate_all(session)} secrets with the first key.")
