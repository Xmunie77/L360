"""Password hashing + signed session cookies for per-user auth.

No third-party crypto dependency: PBKDF2-HMAC-SHA256 (stdlib hashlib) for
passwords, HMAC-SHA256 for the session cookie — mirrors kitchentable's
signed-cookie approach but carries a user id + role instead of a shared
family passcode.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time

from l360.config import SESSION_SECRET, SESSION_TTL_SECONDS

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return hmac.compare_digest(actual, expected)


def _sign(payload: bytes) -> str:
    return hmac.new(SESSION_SECRET.encode(), payload, hashlib.sha256).hexdigest()


def issue_session_cookie(user_id: int, role: str) -> str:
    payload = {
        "uid": user_id,
        "role": role,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
        "nonce": secrets.token_hex(8),
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    return body.hex() + "." + _sign(body)


def read_session_cookie(cookie_value: str | None) -> dict | None:
    if not cookie_value or "." not in cookie_value:
        return None
    body_hex, mac = cookie_value.split(".", 1)
    try:
        body = bytes.fromhex(body_hex)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(body), mac):
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return None
    if payload.get("exp", 0) < int(time.time()):
        return None
    return payload
