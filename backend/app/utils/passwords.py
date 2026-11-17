"""Password hashing and stateless session tokens (stdlib only).

Kept independent of the app config so the hash generator can be used
before the environment is configured.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

PBKDF2_ITERATIONS = 200_000
SALT_BYTES = 16
TOKEN_VERSION = "v1"


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64decode(salt), int(iterations)
        )
        return hmac.compare_digest(_b64encode(digest), expected)
    except (ValueError, TypeError):
        return False


def _sign(secret: str, payload: bytes) -> str:
    return _b64encode(hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest())


def create_token(username: str, secret: str, ttl_seconds: int) -> str:
    payload = json.dumps(
        {"sub": username, "exp": int(time.time()) + ttl_seconds, "v": TOKEN_VERSION},
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{_b64encode(payload)}.{_sign(secret, payload)}"


def verify_token(token: str, secret: str):
    """Return the username for a valid, unexpired token, otherwise None."""
    try:
        payload_b64, signature = token.split(".", 1)
        payload = _b64decode(payload_b64)
        if not hmac.compare_digest(signature, _sign(secret, payload)):
            return None
        data = json.loads(payload)
        if data.get("v") != TOKEN_VERSION:
            return None
        if int(data.get("exp", 0)) <= time.time():
            return None
        return data.get("sub")
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
