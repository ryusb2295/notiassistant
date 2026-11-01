"""신청서 초안. 학생 정보가 들어가므로 LLM 없이 프로필과 분석 결과로 채운다."""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from . import auth, db, schedule

router = APIRouter(
    prefix="/api/users/{user_id}/notices/{notice_id}/application",
    dependencies=[Depends(auth.require_owner)],
)

MANUAL_FIELDS = (
    {"key": "student_no", "label": "학번", "multiline": False},
    {"key": "motivation", "label": "신청 동기", "multiline": True},
)


class DraftIn(BaseModel):
    values: dict[str, str] = Field(default_factory=dict)
    status: Literal["draft", "submitted"] = "draft"


def activity_period(title: str, analysis: dict[str, Any]) -> str:
    for event in schedule.notice_events(title, analysis):
        if event["kind"] == "event":
            end = event.get("end_date")
            return f"{event['date']} ~ {end}" if end else event["date"]
    return ""


def auto_fields(user: dict[str, Any], title: str, analysis: dict[str, Any]) -> list[dict[str, Any]]:
    values = (
        ("name", "이름", user["name"]),
        ("department", "소속", user["department"]),
        ("grade", "학년", f"{user['grade']}학년"),
        ("activity", "활동명", schedule.short_title(title)),
        ("period", "활동 기간", activity_period(title, analysis)),
    )
    return [{"key": key, "label": label, "value": value, "multiline": False} for key, label, value in values]


def build_draft(conn: sqlite3.Connection, user_id: str, notice_id: int) -> dict[str, Any]:
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    row = conn.execute(
        "SELECT n.title, n.url, a.data FROM notices n JOIN analyses a ON a.notice_id = n.id WHERE n.id = ?",
        (notice_id,),
    ).fetchone()
    if user is None or row is None:
        raise HTTPException(404, "공지를 찾을 수 없습니다")
    analysis = json.loads(row["data"])
    saved = conn.execute(
        "SELECT data, status FROM application_drafts WHERE user_id = ? AND notice_id = ?",
        (user_id, notice_id),
    ).fetchone()
    values = json.loads(saved["data"]) if saved else {}

    fields = auto_fields(db.row_to_user(user), row["title"], analysis)
    for field in fields:
        field["auto"] = bool(field["value"])
    fields += [{**field, "value": "", "auto": False} for field in MANUAL_FIELDS]
    for field in fields:
        field["value"] = values.get(field["key"], field["value"])
    return {
        "notice_id": notice_id,
        "title": row["title"],
        "url": row["url"],
        "how_to_apply": analysis.get("how_to_apply"),
        "deadline": analysis.get("deadline"),
        "fields": fields,
        "filled": sum(1 for field in fields if field["value"]),
        "total": len(fields),
        "status": saved["status"] if saved else "new",
    }


@router.get("")
def get_draft(user_id: str, notice_id: int, conn: sqlite3.Connection = Depends(db.get_conn)):
    return build_draft(conn, user_id, notice_id)


@router.put("")
def save_draft(user_id: str, notice_id: int, body: DraftIn, conn: sqlite3.Connection = Depends(db.get_conn)):
    allowed = {field["key"] for field in build_draft(conn, user_id, notice_id)["fields"]}
    unknown = set(body.values) - allowed
    if unknown or any(len(value) > 2000 for value in body.values.values()):
        raise HTTPException(422, "저장할 수 없는 항목입니다")
    with conn:
        conn.execute(
            "INSERT INTO application_drafts (user_id, notice_id, data, status) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id, notice_id) DO UPDATE SET data = excluded.data, status = excluded.status, "
            "updated_at = datetime('now')",
            (user_id, notice_id, json.dumps(body.values, ensure_ascii=False), body.status),
        )
    return build_draft(conn, user_id, notice_id)


@router.get(".txt")
def download_draft(user_id: str, notice_id: int, conn: sqlite3.Connection = Depends(db.get_conn)):
    draft = build_draft(conn, user_id, notice_id)
    lines = [draft["title"], ""] + [f"{f['label']}: {f['value']}" for f in draft["fields"]]
    filename = quote(f"신청서 초안 {notice_id}.txt")
    return Response(
        "\n".join(lines),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )
