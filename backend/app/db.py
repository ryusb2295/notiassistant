"""SQLite 저장소."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    grade INTEGER NOT NULL,
    interests TEXT NOT NULL DEFAULT '[]',
    username TEXT,
    password_hash TEXT,
    consented_at TEXT,
    avatar_type TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS application_drafts (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, notice_id)
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS login_failures (
    username TEXT PRIMARY KEY,
    failures INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    PRIMARY KEY (user_id, source_id)
);
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    article_no TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    skipped_images INTEGER NOT NULL DEFAULT 0,
    crawled_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (source_id, article_no)
);
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY,
    notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    ext TEXT NOT NULL,
    url TEXT NOT NULL,
    status TEXT NOT NULL,
    chars INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS analyses (
    notice_id INTEGER PRIMARY KEY REFERENCES notices(id) ON DELETE CASCADE,
    analyzer TEXT NOT NULL,
    data TEXT NOT NULL,
    deadline TEXT,
    analyzed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS schedule_items (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    end_date TEXT,
    kind TEXT NOT NULL,
    UNIQUE (user_id, notice_id, title, date)
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notice_id INTEGER NOT NULL REFERENCES notices(id) ON DELETE CASCADE,
    key TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0,
    deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, key)
);
"""


# 공식 학과 목록을 쓰기 전에 저장된 이름
RENAMED_DEPARTMENTS = {
    "정보통신공학과": "정보통신공학전공",
    "컴퓨터공학과": "컴퓨터공학전공",
    "SW응용학부": "소프트웨어응용학부",
    "자동차SW학과": "자동차소프트웨어학과",
}


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(path or config.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """로그인 도입 전에 만든 DB에 계정 컬럼을 더한다."""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    for column in ("username", "password_hash", "consented_at", "avatar_type"):
        if column not in columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
    if "deleted" not in {row["name"] for row in conn.execute("PRAGMA table_info(alerts)")}:
        conn.execute("ALTER TABLE alerts ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username ON users(username)")
    for old, new in RENAMED_DEPARTMENTS.items():
        conn.execute("UPDATE users SET department = ? WHERE department = ?", (new, old))
    conn.commit()


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def row_to_user(row: sqlite3.Row) -> dict[str, Any]:
    user = dict(row)
    user.pop("password_hash", None)
    user["interests"] = json.loads(user["interests"])
    return user
