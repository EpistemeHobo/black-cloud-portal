"""Signing in through an Amazon Cognito user pool.

Cognito's own pages handle passwords, verifying the address and forgotten
passwords. It sends the browser back with a one-time code, which is swapped here
for an ID token saying who the person is. The tokens are read once and never
kept: from then on the portal's own session cookie applies, as with passwords.

The authorization code flow with PKCE, and no client secret: a stolen code is
useless without the verifier held in this browser's cookie.
"""
import base64
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta
from typing import Optional
from urllib.parse import urlencode

import httpx
import jwt
from jwt import PyJWKClient

from app import config
from app.auth import ALGORITHM, utcnow

logger = logging.getLogger("portal")

SIGNIN_COOKIE = "portal_signin"
# Long enough to sign up on Cognito's pages, including waiting for the emailed code.
SIGNIN_LIFETIME = timedelta(hours=1)

_jwks: Optional[PyJWKClient] = None


class SignInFailed(Exception):
    """Cognito's answer couldn't be trusted. The reason goes to the log, never to the browser."""


def callback_url() -> str:
    return f"{config.PUBLIC_BASE_URL}/api/auth/callback"


def logout_url() -> str:
    """Ends the session at Cognito too; otherwise the next sign-in would happen silently."""
    query = urlencode({"client_id": config.COGNITO_CLIENT_ID, "logout_uri": f"{config.PUBLIC_BASE_URL}/"})
    return f"{config.COGNITO_DOMAIN}/logout?{query}"


def _issuer() -> str:
    region = config.COGNITO_USER_POOL_ID.split("_")[0]
    return f"https://cognito-idp.{region}.amazonaws.com/{config.COGNITO_USER_POOL_ID}"


def begin(page: str) -> tuple[str, str]:
    """Where to send the browser ("login" or "signup" page), and the cookie that proves it's the same browser later."""
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({
        "client_id": config.COGNITO_CLIENT_ID, "response_type": "code", "scope": "openid email profile",
        "redirect_uri": callback_url(), "state": state, "nonce": nonce,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })
    cookie = jwt.encode({"purpose": "cognito", "state": state, "nonce": nonce, "verifier": verifier,
                         "exp": utcnow() + SIGNIN_LIFETIME}, config.SECRET_KEY, algorithm=ALGORITHM)
    path = "signup" if page == "signup" else "oauth2/authorize"
    return f"{config.COGNITO_DOMAIN}/{path}?{query}", cookie


def _signing_key(id_token: str):
    global _jwks
    if _jwks is None:
        _jwks = PyJWKClient(f"{_issuer()}/.well-known/jwks.json", timeout=10)
    return _jwks.get_signing_key_from_jwt(id_token).key


def _exchange(code: str, verifier: str) -> str:
    response = httpx.post(f"{config.COGNITO_DOMAIN}/oauth2/token", timeout=10, data={
        "grant_type": "authorization_code", "client_id": config.COGNITO_CLIENT_ID, "code": code,
        "redirect_uri": callback_url(), "code_verifier": verifier,
    })
    if response.status_code != 200:
        raise SignInFailed(f"token endpoint answered {response.status_code}")
    return response.json()["id_token"]


def finish(code: str, state: str, cookie: Optional[str]) -> dict:
    """The verified claims of the person Cognito sent back, or SignInFailed."""
    try:
        saved = jwt.decode(cookie or "", config.SECRET_KEY, algorithms=[ALGORITHM])
        if saved.get("purpose") != "cognito" or not hmac.compare_digest(saved["state"], state):
            raise SignInFailed("state doesn't match this browser's sign-in")
        id_token = _exchange(code, saved["verifier"])
        claims = jwt.decode(id_token, _signing_key(id_token), algorithms=["RS256"],
                            audience=config.COGNITO_CLIENT_ID, issuer=_issuer(),
                            options={"require": ["exp", "iat", "sub", "aud", "iss"]})
    except (jwt.PyJWTError, httpx.HTTPError, KeyError, ValueError) as e:
        raise SignInFailed(type(e).__name__) from e
    if claims.get("token_use") != "id":
        raise SignInFailed("not an ID token")
    if not hmac.compare_digest(str(claims.get("nonce", "")), saved["nonce"]):
        raise SignInFailed("nonce doesn't match")
    # Cognito may send this as a string. An unverified address could be anyone's.
    if not claims.get("email") or str(claims.get("email_verified")).lower() != "true":
        raise SignInFailed("email not verified")
    return claims
