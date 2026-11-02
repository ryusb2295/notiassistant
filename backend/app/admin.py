"""행정실: 공문을 올려 분석 초안을 만들고, 고친 뒤 대상 학생에게 게시한다."""
from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import date
from pathlib import PurePath
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from . import analyzer, auth, config, db, parsers, pipeline
from .analyzer import AttachmentInput, NoticeAnalysis, NoticeInput
from .matcher import MATCH, match_notice

log = logging.getLogger(__name__)
SOURCE_ID = "direct"
ALLOWED = parsers.TEXT_EXTENSIONS | set(parsers.IMAGE_MEDIA_TYPES)


def require_admin(
    user_id: str = Depends(auth.current_user_id), conn: sqlite3.Connection = Depends(db.get_conn)
) -> str:
    row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or config.role_of(row["username"]) == "student":
        raise HTTPException(403, "행정실 계정만 사용할 수 있습니다")
    return user_id


router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


class UploadRef(BaseModel):
    file_id: str
    name: str


class NoticeIn(BaseModel):
    title: str
    body: str = ""
    analysis: NoticeAnalysis
    upload: Optional[UploadRef] = None


def upload_url(file_id: str) -> str:
    return f"upload:{file_id}"


@router.post("/analyze")
def analyze_upload(file: UploadFile = File(...)):
    name = PurePath(file.filename or "").name
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED:
        raise HTTPException(415, "HWP, HWPX, PDF, XLSX, 이미지 파일만 올릴 수 있습니다")
    if pipeline.is_personal_file(name):
        raise HTTPException(422, "명단이나 성적이 담긴 파일은 올릴 수 없습니다")
    data = file.file.read(config.MAX_DOWNLOAD_BYTES + 1)
    if len(data) > config.MAX_DOWNLOAD_BYTES:
        raise HTTPException(413, "20MB 이하 파일만 올릴 수 있습니다")

    item = AttachmentInput(name=name, ext=ext, data=data)
    if ext in parsers.TEXT_EXTENSIONS:
        try:
            item.text = parsers.extract_text(ext, data)
        except Exception as exc:
            log.warning("업로드 파일 읽기 실패 %s: %s", name, exc)
            raise HTTPException(422, "파일 내용을 읽지 못했습니다") from exc

    file_id = hashlib.sha256(data).hexdigest()
    path = config.attachment_path(upload_url(file_id))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    title = name.rsplit(".", 1)[0]
    used, result = analyzer.analyze(
        NoticeInput(title, config.SOURCE_BY_ID[SOURCE_ID].name, date.today().isoformat(), "", [item]),
        analyzer.make_llm(),
    )
    return {"file_id": file_id, "name": name, "title": title, "analyzer": used, "analysis": result.model_dump()}


def notify_targets(conn: sqlite3.Connection, notice_id: int, title: str, analysis: dict[str, Any]) -> int:
    count = 0
    for row in conn.execute("SELECT * FROM users WHERE username IS NOT NULL").fetchall():
        if match_notice(db.row_to_user(row), analysis).status != MATCH:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO alerts (user_id, notice_id, key, title, body) VALUES (?, ?, ?, ?, ?)",
            (row["id"], notice_id, f"notice:{notice_id}", "나에게 해당되는 공지예요", title),
        )
        count += 1
    return count


@router.post("/notices", status_code=201)
def publish(body: NoticeIn, conn: sqlite3.Connection = Depends(db.get_conn)):
    if not body.title.strip():
        raise HTTPException(422, "공지 제목을 입력해 주세요")
    if body.upload and not config.attachment_path(upload_url(body.upload.file_id)).exists():
        raise HTTPException(409, "파일을 다시 올려 주세요")
    analysis = body.analysis.model_dump()
    with conn:
        notice_id = conn.execute(
            "INSERT INTO notices (source_id, article_no, title, url, posted_at, body) VALUES (?, ?, ?, '', ?, ?)",
            (SOURCE_ID, uuid.uuid4().hex, body.title.strip(), date.today().isoformat(), body.body),
        ).lastrowid
        conn.execute(
            "INSERT INTO analyses (notice_id, analyzer, data, deadline) VALUES (?, 'admin', ?, ?)",
            (notice_id, json.dumps(analysis, ensure_ascii=False), analysis["deadline"]),
        )
        if body.upload:
            ext = body.upload.name.rsplit(".", 1)[-1].lower()
            conn.execute(
                "INSERT INTO attachments (notice_id, name, ext, url, status) VALUES (?, ?, ?, ?, 'read')",
                (notice_id, PurePath(body.upload.name).name, ext, upload_url(body.upload.file_id)),
            )
        notified = notify_targets(conn, notice_id, body.title.strip(), analysis)
    return {"id": notice_id, "notified": notified}


@router.get("/notices")
def list_notices(conn: sqlite3.Connection = Depends(db.get_conn)):
    rows = conn.execute(
        "SELECT n.id, n.title, n.posted_at, a.deadline, "
        "(SELECT count(*) FROM alerts WHERE notice_id = n.id) AS notified, "
        "(SELECT count(DISTINCT user_id) FROM schedule_items WHERE notice_id = n.id) AS saved "
        "FROM notices n JOIN analyses a ON a.notice_id = n.id WHERE n.source_id = ? ORDER BY n.id DESC",
        (SOURCE_ID,),
    ).fetchall()
    return [dict(row) for row in rows]


FEEDBACK_LABELS = {"wrong_match": "해당 안 되는데 떴어요", "wrong_hide": "해당되는데 숨겨졌어요", "wrong_info": "요약이 틀렸어요"}


@router.get("/feedback")
def list_feedback(conn: sqlite3.Connection = Depends(db.get_conn)):
    """학생이 신고한 판정 오류. 분석 프롬프트와 판정 규칙을 고칠 때 본다."""
    rows = conn.execute(
        "SELECT f.id, f.kind, f.note, f.created_at, n.id AS notice_id, n.title, u.department "
        "FROM feedback f JOIN notices n ON n.id = f.notice_id LEFT JOIN users u ON u.id = f.user_id "
        "ORDER BY f.id DESC LIMIT 100"
    ).fetchall()
    return [{**dict(row), "label": FEEDBACK_LABELS.get(row["kind"], row["kind"])} for row in rows]
