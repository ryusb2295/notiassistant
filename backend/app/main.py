"""공지비서 API."""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from contextlib import asynccontextmanager
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import admin, analyzer, applications, auth, config, crawler, db, parsers, pipeline, schedule
from .auth import ProfileIn
from .db import get_conn
from .matcher import GENERAL, MATCH, match_notice

log = logging.getLogger(__name__)
URGENT_DAYS = 7
NEW_DAYS = 7
STALE_DAYS = 30  # 마감일이 없는 공지를 피드에 남기는 기간
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'self'; base-uri 'self'"
    ),
}
DIST_DIR = Path(__file__).resolve().parents[2] / "frontend" / "dist"


async def _crawl_loop() -> None:
    while True:
        await asyncio.sleep(config.CRAWL_INTERVAL_MIN * 60)
        conn = db.connect()
        try:
            await asyncio.to_thread(pipeline.run, conn)
        except Exception:
            log.exception("주기 수집 실패")
        finally:
            conn.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    task = asyncio.create_task(_crawl_loop()) if config.CRAWL_INTERVAL_MIN > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="공지비서", lifespan=lifespan)
app.include_router(auth.router)
users = APIRouter(prefix="/api/users/{user_id}", dependencies=[Depends(auth.require_owner)])


def today() -> date:
    return date.today()


def load_user(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "사용자를 찾을 수 없습니다")
    return db.row_to_user(row)


def subscribed_ids(conn: sqlite3.Connection, user_id: str) -> list[str]:
    rows = conn.execute("SELECT source_id FROM subscriptions WHERE user_id = ?", (user_id,))
    return [row["source_id"] for row in rows]


def recommended(department: str) -> list[config.Source]:
    """학과가 참여하는 사업단을 앞세운 게시판 목록."""
    info = config.DEPARTMENT_BY_NAME.get(department)
    sources = []
    if info and info.source_id:
        sources.append(config.SOURCE_BY_ID[info.source_id])
    if info and info.sw_group:
        sources.append(config.SOURCE_BY_ID["swedu"])
        sources.append(config.SOURCE_BY_ID["aibootcamp"])
    sources.append(config.SOURCE_BY_ID["rise"])
    return sources


def notice_card(row: sqlite3.Row, user: dict[str, Any], now: date) -> dict[str, Any]:
    analysis = json.loads(row["data"])
    match = match_notice(user, analysis)
    deadline = analysis.get("deadline")
    return {
        "id": row["id"],
        "title": row["title"],
        "source_id": row["source_id"],
        "source": config.SOURCE_BY_ID[row["source_id"]].name,
        "posted_at": row["posted_at"],
        "category": analysis["category"],
        "deadline": deadline,
        "d_day": (date.fromisoformat(deadline) - now).days if deadline else None,
        "match": match.status,
        "reason": match.reason,
        "analyzer": row["analyzer"],
        "found_in": [place.strip("[]") for place in analysis.get("found_in", [])],
    }


def build_feed(conn: sqlite3.Connection, user: dict[str, Any], now: date) -> dict[str, Any]:
    subscribed = [*subscribed_ids(conn, user["id"]), admin.SOURCE_ID]
    marks = ",".join("?" for _ in subscribed)
    rows = conn.execute(
        f"SELECT n.id, n.title, n.source_id, n.posted_at, a.data, a.analyzer "
        f"FROM notices n JOIN analyses a ON a.notice_id = n.id "
        f"WHERE n.source_id IN ({marks}) ORDER BY n.posted_at DESC, n.id DESC",
        subscribed,
    ).fetchall()
    cards = [notice_card(row, user, now) for row in rows]
    stale = (now - timedelta(days=STALE_DAYS)).isoformat()
    active = [
        c for c in cards
        if (c["d_day"] is None and c["posted_at"] >= stale) or (c["d_day"] is not None and c["d_day"] >= 0)
    ]
    urgent = sorted(
        (c for c in active if c["match"] == MATCH and c["d_day"] is not None and c["d_day"] <= URGENT_DAYS),
        key=lambda c: c["d_day"],
    )
    urgent_ids = {c["id"] for c in urgent}
    mine = [c for c in active if c["match"] == MATCH and c["id"] not in urgent_ids]
    others = [c for c in active if c["match"] == GENERAL]
    cutoff = (now - timedelta(days=NEW_DAYS)).isoformat()
    return {
        "new_count": sum(1 for c in cards if c["posted_at"] >= cutoff),
        "match_count": len(urgent) + len(mine),
        "urgent": urgent,
        "mine": mine,
        "others": others,
        "hidden_count": sum(1 for c in active if c["match"] == "no"),
    }


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.update(SECURITY_HEADERS)
    return response


@app.get("/api/health")
def health(conn: sqlite3.Connection = Depends(get_conn)):
    notices = conn.execute("SELECT count(*), max(crawled_at) FROM notices").fetchone()
    return {"status": "ok", "notices": notices[0], "last_crawl": notices[1], "analyzer": analyzer.provider()}


@app.get("/api/meta")
def meta():
    return {
        "departments": [
            {"name": d.name, "college": d.college, "parent": d.parent, "aliases": d.aliases}
            for d in config.DEPARTMENTS
        ],
        "interests": config.INTERESTS,
        "analyzer": analyzer.provider(),
        "model": analyzer.active_model(),
    }


@users.get("")
def get_user(user_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return load_user(conn, user_id)


@users.patch("")
def update_user(user_id: str, body: ProfileIn, conn: sqlite3.Connection = Depends(get_conn)):
    load_user(conn, user_id)
    if body.department not in config.DEPARTMENT_BY_NAME:
        raise HTTPException(422, "목록에 없는 학과입니다")
    with conn:
        conn.execute(
            "UPDATE users SET name = ?, department = ?, grade = ?, interests = ? WHERE id = ?",
            (body.name, body.department, body.grade, json.dumps(body.interests, ensure_ascii=False), user_id),
        )
    return load_user(conn, user_id)


@users.get("/sources")
def list_sources(user_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    user = load_user(conn, user_id)
    subscribed = set(subscribed_ids(conn, user_id))
    picks = recommended(user["department"])
    pick_ids = {s.id for s in picks}
    ordered = picks + [s for s in config.SOURCES if s.id not in pick_ids and s.kind in ("base", "program")]
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "kind": s.kind,
            "recommended": s.id in pick_ids,
            "subscribed": s.id in subscribed,
        }
        for s in ordered
    ]


@users.put("/subscriptions/{source_id}", status_code=204)
def subscribe(user_id: str, source_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    load_user(conn, user_id)
    if source_id not in config.SOURCE_BY_ID or config.SOURCE_BY_ID[source_id].kind == "direct":
        raise HTTPException(404, "게시판을 찾을 수 없습니다")
    with conn:
        conn.execute("INSERT OR IGNORE INTO subscriptions VALUES (?, ?)", (user_id, source_id))


@users.delete("/subscriptions/{source_id}", status_code=204)
def unsubscribe(user_id: str, source_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    load_user(conn, user_id)
    if config.SOURCE_BY_ID.get(source_id) and config.SOURCE_BY_ID[source_id].kind == "base":
        raise HTTPException(409, "기본 게시판은 해제할 수 없습니다")
    with conn:
        conn.execute("DELETE FROM subscriptions WHERE user_id = ? AND source_id = ?", (user_id, source_id))


@users.get("/feed")
def feed(user_id: str, conn: sqlite3.Connection = Depends(get_conn), now: date = Depends(today)):
    user = load_user(conn, user_id)
    return build_feed(conn, user, now)


@users.get("/notices/{notice_id}")
def notice_detail(
    user_id: str, notice_id: int,
    conn: sqlite3.Connection = Depends(get_conn), now: date = Depends(today),
):
    user = load_user(conn, user_id)
    row = conn.execute(
        "SELECT n.*, a.data, a.analyzer FROM notices n JOIN analyses a ON a.notice_id = n.id WHERE n.id = ?",
        (notice_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "공지를 찾을 수 없습니다")
    attachments = conn.execute(
        "SELECT id, name, ext, status FROM attachments WHERE notice_id = ?", (notice_id,)
    ).fetchall()
    saved = conn.execute(
        "SELECT 1 FROM schedule_items WHERE user_id = ? AND notice_id = ? LIMIT 1", (user_id, notice_id)
    ).fetchone()
    analysis = json.loads(row["data"])
    return {
        **notice_card(row, user, now),
        "url": row["url"],
        "summary": analysis["summary"],
        "audience": analysis["audience"],
        "benefit": analysis.get("benefit"),
        "how_to_apply": analysis.get("how_to_apply"),
        "events": [
            {**event, "google_url": schedule.google_calendar_url(event, row["url"])}
            for event in schedule.notice_events(row["title"], analysis)
        ],
        "attachments": [dict(a) for a in attachments],
        "skipped_images": row["skipped_images"],
        "saved": saved is not None,
    }


@users.post("/notices/{notice_id}/schedule", status_code=201)
def save_schedule(user_id: str, notice_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    load_user(conn, user_id)
    row = conn.execute(
        "SELECT n.title, a.data FROM analyses a JOIN notices n ON n.id = a.notice_id WHERE n.id = ?",
        (notice_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, "공지를 찾을 수 없습니다")
    events = schedule.notice_events(row["title"], json.loads(row["data"]))
    if not events:
        raise HTTPException(409, "이 공지에는 확정된 일정이 없습니다")
    with conn:
        for event in events:
            conn.execute(
                "INSERT OR IGNORE INTO schedule_items (user_id, notice_id, title, date, end_date, kind) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, notice_id, event["title"], event["date"], event.get("end_date"), event["kind"]),
            )
    return {"added": len(events)}


@users.delete("/notices/{notice_id}/schedule", status_code=204)
def remove_schedule(user_id: str, notice_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    load_user(conn, user_id)
    with conn:
        conn.execute("DELETE FROM schedule_items WHERE user_id = ? AND notice_id = ?", (user_id, notice_id))


def schedule_rows(conn: sqlite3.Connection, user_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM schedule_items WHERE user_id = ? ORDER BY date", (user_id,)
    ).fetchall()
    return [dict(row) for row in rows]


@users.get("/schedule")
def get_schedule(user_id: str, conn: sqlite3.Connection = Depends(get_conn), now: date = Depends(today)):
    load_user(conn, user_id)
    return [
        {
            **item,
            "d_day": (date.fromisoformat(item["date"]) - now).days,
            "google_url": schedule.google_calendar_url(item),
        }
        for item in schedule_rows(conn, user_id)
    ]


@users.get("/calendar.ics")
def calendar_ics(user_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    load_user(conn, user_id)
    return Response(
        schedule.build_ics(schedule_rows(conn, user_id)),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gongjibiseo.ics"'},
    )


@users.get("/alerts")
def get_alerts(user_id: str, conn: sqlite3.Connection = Depends(get_conn), now: date = Depends(today)):
    user = load_user(conn, user_id)
    schedule.generate_deadline_alerts(conn, user_id, now)
    schedule.generate_notice_alerts(conn, user_id, build_feed(conn, user, now))
    rows = conn.execute(
        "SELECT id, notice_id, title, body, read, created_at FROM alerts "
        "WHERE user_id = ? ORDER BY read, id DESC LIMIT 50",
        (user_id,),
    ).fetchall()
    return [dict(row) for row in rows]


@users.post("/alerts/read", status_code=204)
def read_alerts(user_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    load_user(conn, user_id)
    with conn:
        conn.execute("UPDATE alerts SET read = 1 WHERE user_id = ?", (user_id,))


def preview_kind(ext: str) -> str:
    if ext == "pdf":
        return "pdf"
    if ext in parsers.IMAGE_MEDIA_TYPES:
        return "image"
    return "text" if ext in parsers.TEXT_EXTENSIONS else "none"


@lru_cache
def get_fetcher() -> crawler.Fetcher:
    return crawler.Fetcher()


def load_attachment(conn: sqlite3.Connection, attachment_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM attachments WHERE id = ?", (attachment_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "첨부파일을 찾을 수 없습니다")
    return row


def attachment_bytes(row: sqlite3.Row, fetcher: crawler.Fetcher) -> bytes:
    """학교 서버 부담을 줄이고 현장 네트워크에 대비해 받은 파일을 캐시한다."""
    if row["status"] == "personal":
        raise HTTPException(403, "개인정보가 있을 수 있어 학교 사이트에서만 볼 수 있습니다")
    path = config.attachment_path(row["url"])
    if path.exists():
        return path.read_bytes()
    try:
        data = fetcher.get_bytes(row["url"])
    except (OSError, ValueError, PermissionError) as exc:
        log.warning("첨부 다운로드 실패 %s: %s", row["name"], exc)
        raise HTTPException(502, "학교 서버에서 파일을 받지 못했습니다") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


@app.get("/api/attachments/{attachment_id}", dependencies=[Depends(auth.current_user_id)])
def attachment_info(attachment_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    row = load_attachment(conn, attachment_id)
    return {
        "id": row["id"],
        "notice_id": row["notice_id"],
        "name": row["name"],
        "ext": row["ext"],
        "url": row["url"],
        "preview": "none" if row["status"] == "personal" else preview_kind(row["ext"]),
        "personal": row["status"] == "personal",
    }


@app.get("/api/attachments/{attachment_id}/file", dependencies=[Depends(auth.current_user_id)])
def attachment_file(
    attachment_id: int,
    download: bool = False,
    conn: sqlite3.Connection = Depends(get_conn),
    fetcher: crawler.Fetcher = Depends(get_fetcher),
):
    row = load_attachment(conn, attachment_id)
    kind = preview_kind(row["ext"])
    inline = not download and kind in ("pdf", "image")
    media_type = (
        "application/pdf" if kind == "pdf"
        else parsers.IMAGE_MEDIA_TYPES.get(row["ext"], "application/octet-stream")
    )
    disposition = "inline" if inline else "attachment"
    return Response(
        attachment_bytes(row, fetcher),
        media_type=media_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{quote(row['name'])}",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/api/attachments/{attachment_id}/text", dependencies=[Depends(auth.current_user_id)])
def attachment_text(
    attachment_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
    fetcher: crawler.Fetcher = Depends(get_fetcher),
):
    row = load_attachment(conn, attachment_id)
    if row["ext"] not in parsers.TEXT_EXTENSIONS:
        raise HTTPException(415, "텍스트로 볼 수 없는 형식입니다")
    data = attachment_bytes(row, fetcher)
    try:
        return {"text": parsers.extract_text(row["ext"], data)}
    except Exception as exc:  # 손상된 문서여도 다운로드는 할 수 있게 둔다
        log.warning("첨부 텍스트 추출 실패 %s: %s", row["name"], exc)
        raise HTTPException(422, "이 파일의 내용을 읽지 못했습니다") from exc


app.include_router(users)
app.include_router(applications.router)
app.include_router(admin.router)

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "없는 경로입니다")
        # 파일명에 해시가 붙는 assets와 달리 index.html은 항상 새로 받아 예전 화면이 남지 않게 한다.
        return FileResponse(DIST_DIR / "index.html", headers={"Cache-Control": "no-cache"})
