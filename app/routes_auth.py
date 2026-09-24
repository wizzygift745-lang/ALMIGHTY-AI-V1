"""Auth API: register, login, session, password change. Admin is seeded at
boot — never created from the frontend, never hard-coded in the frontend."""
import datetime
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from . import db
from .security import (EMAIL_RE, create_token, get_current_user, hash_password,
                       public_user, verify_password)

router = APIRouter()


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=200)


class LoginIn(BaseModel):
    email: str
    password: str


class PasswordIn(BaseModel):
    current: str
    new: str = Field(min_length=8, max_length=200)


def _ensure_daily_credits(user: dict) -> dict:
    """Refresh free credits once per local day for standard users."""
    if user["role"] in ("admin", "owner") or user["credits"] == -1:
        return user
    today = datetime.date.today().isoformat()
    if user.get("last_grant") != today:
        daily = int(db.setting("daily_free_credits", "30"))
        db.execute("UPDATE users SET credits=?, last_grant=? WHERE id=?",
                   (daily, today, user["id"]))
        user = db.q1("SELECT * FROM users WHERE id=?", (user["id"],))
    return user


@router.post("/register")
def register(body: RegisterIn):
    email = body.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Invalid email address")
    if db.q1("SELECT id FROM users WHERE email=?", (email,)):
        raise HTTPException(409, "An account with this email already exists")
    daily = int(db.setting("daily_free_credits", "30"))
    uid = db.execute(
        "INSERT INTO users (email,name,password_hash,role,credits,last_grant,created_at)"
        " VALUES (?,?,?,?,?,?,?)",
        (email, body.name.strip(), hash_password(body.password), "user",
         daily, datetime.date.today().isoformat(), db.now()))
    db.log("info", "user-registered", email, f"user id {uid}")
    token = create_token(uid, "user")
    return {"token": token, "user": public_user(db.q1("SELECT * FROM users WHERE id=?", (uid,)))}


@router.post("/login")
def login(body: LoginIn):
    user = db.q1("SELECT * FROM users WHERE email=?", (body.email.strip().lower(),))
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    if user["banned"]:
        raise HTTPException(403, "This account has been suspended")
    user = _ensure_daily_credits(user)
    db.log("info", "login", user["email"], "")
    return {"token": create_token(user["id"], user["role"]), "user": public_user(user)}


@router.get("/me")
def me(request: Request):
    user = _ensure_daily_credits(get_current_user(request))
    return public_user(user)


@router.post("/logout")
def logout(request: Request):
    # Stateless tokens: client discards the token. Endpoint kept for audits.
    user = get_current_user(request)
    db.log("info", "logout", user["email"], "")
    return {"ok": True}


@router.post("/me/password")
def change_password(body: PasswordIn, request: Request):
    user = get_current_user(request)
    if not verify_password(body.current, user["password_hash"]):
        raise HTTPException(401, "Current password is incorrect")
    db.execute("UPDATE users SET password_hash=? WHERE id=?",
               (hash_password(body.new), user["id"]))
    db.log("info", "password-changed", user["email"], "")
    return {"ok": True}
