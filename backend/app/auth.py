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
MAX_LOGIN_FAILURES = 5
LOCK_MINUTES = 15
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}
USERNAME = re.compile(r"^[A-Za-z0-9_.\-]{4,30}$")

router = APIRouter(prefix="/api/auth")


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    department: str
    grade: int = Field(ge=1, le=config.MAX_YEARS)
    interests: list[str] = []


class SignupIn(ProfileIn):
    username: str
    password: str = Field(min_length=8, max_length=128)
    agreed: bool = False


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


class AccountDeleteIn(BaseModel):
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


def check_grade(department: str, grade: int) -> None:
    years = config.DEPARTMENT_BY_NAME[department].years
    if grade > years:
        raise HTTPException(422, f"{department}는 {years}학년까지 있어요")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_not_locked(conn: sqlite3.Connection, username: str) -> None:
    row = conn.execute("SELECT locked_until FROM login_failures WHERE username = ?", (username,)).fetchone()
    if row and row["locked_until"] and row["locked_until"] > _now():
        raise HTTPException(429, f"로그인 시도가 많습니다. {LOCK_MINUTES}분 뒤 다시 시도해 주세요")


def _record_failure(conn: sqlite3.Connection, username: str) -> None:
    """없는 아이디도 똑같이 세어 계정 존재 여부가 드러나지 않게 한다."""
    with conn:
        conn.execute(
            "INSERT INTO login_failures (username, failures) VALUES (?, 1) "
            "ON CONFLICT(username) DO UPDATE SET failures = failures + 1, locked_until = NULL",
            (username,),
        )
        locked = datetime.now(timezone.utc) + timedelta(minutes=LOCK_MINUTES)
        conn.execute(
            "UPDATE login_failures SET failures = 0, locked_until = ? WHERE username = ? AND failures >= ?",
            (locked.isoformat(), username, MAX_LOGIN_FAILURES),
        )


def sync_department_boards(conn: sqlite3.Connection, user_id: str, department: str) -> None:
    """학과 게시판 구독을 내 전공과 소속 학부로 맞춘다."""
    current = {r["source_id"] for r in conn.execute("SELECT source_id FROM subscriptions WHERE user_id = ?", (user_id,))}
    for source_id in current:
        if config.SOURCE_BY_ID.get(source_id) and config.SOURCE_BY_ID[source_id].kind == "dept":
            conn.execute("DELETE FROM subscriptions WHERE user_id = ? AND source_id = ?", (user_id, source_id))
    for source_id in config.department_source_ids(department):
        conn.execute("INSERT OR IGNORE INTO subscriptions VALUES (?, ?)", (user_id, source_id))


def _load(conn: sqlite3.Connection, user_id: str) -> dict:
    user = db.row_to_user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
    role = config.role_of(user["username"])
    return {**user, "role": role, "is_admin": role != "student", "has_avatar": bool(user.get("avatar_type"))}


@router.post("/signup", status_code=201)
def signup(body: SignupIn, response: Response, conn: sqlite3.Connection = Depends(db.get_conn)):
    if not body.agreed:
        raise HTTPException(422, "개인정보 수집·이용에 동의해 주세요")
    if not USERNAME.match(body.username):
        raise HTTPException(422, "아이디는 영문, 숫자, _ . - 로 4자 이상 입력해 주세요")
    if body.department not in config.DEPARTMENT_BY_NAME:
        raise HTTPException(422, "목록에 없는 학과입니다")
    check_grade(body.department, body.grade)
    user_id = uuid.uuid4().hex
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (id, name, department, grade, interests, username, password_hash, consented_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, body.name, body.department, body.grade,
                 json.dumps(body.interests, ensure_ascii=False), body.username,
                 hash_password(body.password), _now()),
            )
            conn.execute("INSERT INTO subscriptions VALUES (?, 'yu-news')", (user_id,))
            sync_department_boards(conn, user_id, body.department)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "이미 사용 중인 아이디입니다") from exc
    _start_session(conn, response, user_id)
    return _load(conn, user_id)


@router.post("/login")
def login(body: LoginIn, response: Response, conn: sqlite3.Connection = Depends(db.get_conn)):
    username = body.username[:30]
    _require_not_locked(conn, username)
    row = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        _record_failure(conn, username)
        raise HTTPException(401, "아이디 또는 비밀번호가 맞지 않습니다")
    with conn:
        conn.execute("DELETE FROM login_failures WHERE username = ?", (username,))
    _start_session(conn, response, row["id"])
    return _load(conn, row["id"])


def _check_password(conn: sqlite3.Connection, user_id: str, password: str) -> None:
    row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if not verify_password(password, row["password_hash"]):
        raise HTTPException(403, "비밀번호가 맞지 않습니다")


@router.post("/password", status_code=204)
def change_password(
    body: PasswordChangeIn, response: Response,
    user_id: str = Depends(current_user_id), conn: sqlite3.Connection = Depends(db.get_conn),
):
    _check_password(conn, user_id, body.current_password)
    with conn:
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(body.new_password), user_id))
        # 비밀번호가 유출됐을 때를 대비해 다른 기기의 로그인을 모두 끊는다.
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    _start_session(conn, response, user_id)


@router.post("/delete-account", status_code=204)
def delete_account(
    body: AccountDeleteIn, response: Response,
    user_id: str = Depends(current_user_id), conn: sqlite3.Connection = Depends(db.get_conn),
):
    _check_password(conn, user_id, body.password)
    with conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    (config.AVATAR_DIR / user_id).unlink(missing_ok=True)
    response.delete_cookie(COOKIE_NAME)


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
