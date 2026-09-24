"""ALMIGHTY AI — authentication, tokens, RBAC.

- Passwords: PBKDF2-HMAC-SHA256 with per-user salt (never stored in plain text).
- Sessions: stateless HMAC-signed bearer tokens (server secret generated on
  first boot, stored server-side only — never exposed to the browser).
- Roles: owner > admin > user. Admin endpoints are guarded server-side.
"""
import base64
import hashlib
import hmac
import json
import re
import secrets
import time

from fastapi import HTTPException, Request

from . import config, db

_SECRET: bytes | None = None
EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")


def _secret() -> bytes:
    global _SECRET
    if _SECRET is None:
        try:
            _SECRET = config.SECRET_PATH.read_bytes()
        except FileNotFoundError:
            config.ensure_dirs()
            _SECRET = secrets.token_bytes(32)
            config.SECRET_PATH.write_bytes(_SECRET)
            try:
                config.SECRET_PATH.chmod(0o600)
            except Exception:
                pass
    return _SECRET


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 200_000)
    return f"pbkdf2$200000${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, digest = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


# ------------------------------------------------------------------ tokens
def create_token(user_id: int, role: str, hours: int = 24 * 7) -> str:
    payload = {"uid": user_id, "role": role, "exp": int(time.time()) + hours * 3600}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=")
    sig = hmac.new(_secret(), body, hashlib.sha256).hexdigest()
    return body.decode() + "." + sig


def decode_token(token: str) -> dict | None:
    try:
        body, sig = token.split(".")
        expect = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expect):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=="))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except Exception:
        return None


# --------------------------------------------------------------- request auth
def get_current_user(request: Request) -> dict:
    token = ""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = request.query_params.get("token", "")
    payload = decode_token(token) if token else None
    if not payload:
        raise HTTPException(401, "Not authenticated")
    user = db.q1("SELECT * FROM users WHERE id=?", (payload["uid"],))
    if not user or user["banned"]:
        raise HTTPException(401, "Account unavailable")
    return user


def require_admin(user: dict) -> None:
    if user["role"] not in ("admin", "owner"):
        raise HTTPException(403, "Administrator access required")


def public_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "credits": user["credits"],
        "created_at": user["created_at"],
    }
