"""서버 없이 보는 목업용으로, 데모 계정 기준 API 응답을 frontend/public/mock 에 JSON으로 저장한다.

실행: backend/.venv/Scripts/python.exe backend/scripts/export_mock.py
원본 DB는 건드리지 않고 임시 복사본에 데모 계정을 만들어 뽑는다.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app import config, crawler, db, main  # noqa: E402
from app.files import get_fetcher  # noqa: E402

OUT = BACKEND.parent / "frontend" / "public" / "mock"
DEMO = {
    "username": "demo", "password": "demo-password", "agreed": True,
    "name": "체험용", "department": "정보통신공학전공", "grade": 3,
    "interests": ["장학", "교육·특강", "대외활동", "자격증", "경진대회", "취업·진로"],
}


class OfflineFetcher(crawler.Fetcher):
    """캐시된 첨부만 쓴다. 목업 만들다 학교 서버를 두드리지 않게."""

    def __init__(self):
        pass

    def get_bytes(self, url):
        raise OSError("offline")


def main_() -> None:
    tmp = Path(tempfile.mkdtemp()) / "mock.sqlite3"
    shutil.copy(config.DB_PATH, tmp)
    conn = db.connect(tmp)
    with conn:  # 실제 사용자 데이터는 목업에 섞지 않는다
        for table in ("users", "sessions", "subscriptions", "alerts", "schedule_items",
                      "application_drafts", "ask_log", "feedback", "login_failures"):
            conn.execute(f"DELETE FROM {table}")
    conn.close()

    def override():
        c = db.connect(tmp)
        try:
            yield c
        finally:
            c.close()

    main.app.dependency_overrides[main.get_conn] = override
    main.app.dependency_overrides[get_fetcher] = OfflineFetcher
    client = TestClient(main.app)
    uid = client.post("/api/auth/signup", json=DEMO).json()["id"]

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    saved = 0

    def save(path: str) -> dict | list | None:
        nonlocal saved
        response = client.get(f"/api{path}")
        if response.status_code != 200:
            return None
        body = response.json()
        name = path.replace(uid, "me").strip("/").replace("/", "_").replace("?", "_").replace("=", "-").replace("&", "_")
        (OUT / f"{name}.json").write_text(json.dumps(body, ensure_ascii=False).replace(uid, "me"), encoding="utf-8")
        saved += 1
        return body

    save("/meta")
    save("/auth/me")
    u = f"/users/{uid}"
    for path in ("", "/sources", "/feed", "/summary", "/schedule", "/alerts", "/applications"):
        save(u + path)
    for source in client.get(f"/api{u}/sources").json():
        save(f"{u}/feed?source={source['id']}")

    # 검색은 구독하지 않은 게시판까지 뒤지므로, 프론트가 거를 수 있게 전체 공지 카드를 따로 둔다.
    conn = db.connect(tmp)
    with conn:
        for source in config.SOURCES:
            conn.execute("INSERT OR IGNORE INTO subscriptions VALUES (?, ?)", (uid, source.id))
    ids = [row[0] for row in conn.execute("SELECT id FROM notices")]
    attachment_ids = [row[0] for row in conn.execute("SELECT id FROM attachments")]
    # 검색은 지난 공지도 찾으므로 build_feed의 기간 필터 없이 카드를 만든다.
    rows = conn.execute(
        "SELECT n.id, n.title, n.source_id, n.posted_at, a.data, a.analyzer "
        "FROM notices n JOIN analyses a ON a.notice_id = n.id ORDER BY n.posted_at DESC, n.id DESC"
    ).fetchall()
    user = main.load_user(conn, uid)
    cards = main.merge_duplicates([main.notice_card(row, user, main.today()) for row in rows])
    search_text = {
        row["id"]: " ".join([row["title"], *json.loads(row["data"]).get("summary", []),
                             json.loads(row["data"]).get("audience") or ""])
        for row in rows
    }
    for card in cards:
        card["search_text"] = search_text[card["id"]]
    conn.close()
    (OUT / "all_cards.json").write_text(json.dumps(cards, ensure_ascii=False), encoding="utf-8")

    for notice_id in ids:
        save(f"{u}/notices/{notice_id}")
    # 첨부 원본은 대부분 캐시에 없어서 정보만 저장하고, 목업 화면에선 학교 사이트로 보낸다.
    for attachment_id in attachment_ids:
        save(f"/attachments/{attachment_id}")

    print(f"{saved} files -> {OUT}")


if __name__ == "__main__":
    main_()
