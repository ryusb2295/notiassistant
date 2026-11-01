"""아이디·비밀번호 로그인과 세션 쿠키."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from . import config, db

COOKIE_NAME = "gongjibiseo_session"
SESSION_DAYS = 30
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
USERNAME = re.compile(r"^[A-Za-z0-9_.\-]{4,30}$")

router = APIRouter(prefix="/api/auth")


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    department: str
    grade: int = Field(ge=1, le=5)
    interests: list[str] = []


class SignupIn(ProfileIn):
    username: str
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    username: str
    password: str


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **SCRYPT)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    salt, digest = stored.split("$")
    actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), **SCRYPT)
    return secrets.compare_digest(actual.hex(), digest)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _start_session(conn: sqlite3.Connection, response: Response, user_id: str) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    with conn:
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
            (_token_hash(token), user_id, expires.isoformat()),
        )
    response.set_cookie(
        COOKIE_NAME, token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=config.COOKIE_SECURE,
    )


def current_user_id(
    conn: sqlite3.Connection = Depends(db.get_conn),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> str:
    if token:
        row = conn.execute(
            "SELECT user_id FROM sessions WHERE token_hash = ? AND expires_at > ?",
            (_token_hash(token), datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        if row:
            return row["user_id"]
    raise HTTPException(401, "로그인이 필요합니다")


def require_owner(user_id: str, session_user: str = Depends(current_user_id)) -> None:
    """다른 사용자의 데이터에 접근하지 못하게 한다."""
    if user_id != session_user:
        raise HTTPException(403, "내 계정의 정보만 볼 수 있습니다")


def _load(conn: sqlite3.Connection, user_id: str) -> dict:
    return db.row_to_user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


@router.post("/signup", status_code=201)
def signup(body: SignupIn, response: Response, conn: sqlite3.Connection = Depends(db.get_conn)):
    if not USERNAME.match(body.username):
        raise HTTPException(422, "아이디는 영문, 숫자, _ . - 로 4자 이상 입력해 주세요")
    if body.department not in config.DEPARTMENT_BY_NAME:
        raise HTTPException(422, "목록에 없는 학과입니다")
    user_id = uuid.uuid4().hex
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (id, name, department, grade, interests, username, password_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, body.name, body.department, body.grade,
                 json.dumps(body.interests, ensure_ascii=False), body.username, hash_password(body.password)),
            )
            conn.execute("INSERT INTO subscriptions VALUES (?, 'yu-news')", (user_id,))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "이미 사용 중인 아이디입니다") from exc
    _start_session(conn, response, user_id)
    return _load(conn, user_id)


@router.post("/login")
def login(body: LoginIn, response: Response, conn: sqlite3.Connection = Depends(db.get_conn)):
    row = conn.execute(
        "SELECT id, password_hash FROM users WHERE username = ?", (body.username,)
    ).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(401, "아이디 또는 비밀번호가 맞지 않습니다")
    _start_session(conn, response, row["id"])
    return _load(conn, row["id"])


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    conn: sqlite3.Connection = Depends(db.get_conn),
    token: str | None = Cookie(default=None, alias=COOKIE_NAME),
):
    if token:
        with conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
    response.delete_cookie(COOKIE_NAME)


@router.get("/me")
def me(user_id: str = Depends(current_user_id), conn: sqlite3.Connection = Depends(db.get_conn)):
    return _load(conn, user_id)
