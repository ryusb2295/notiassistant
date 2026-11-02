from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import auth, config, db, main
from app.analyzer import NoticeAnalysis, NoticeEvent

TODAY = date(2026, 11, 1)


def seed(conn, article, title, source="yu-news", **fields):
    defaults = dict(summary=["요약"], category="기타", audience="재학생", departments=[], grades=[],
                    deadline=None, events=[], benefit=None, how_to_apply=None, found_in=["본문"])
    data = NoticeAnalysis(**{**defaults, **fields})
    cursor = conn.execute(
        "INSERT INTO notices (source_id, article_no, title, url, posted_at, body) VALUES (?, ?, ?, ?, ?, ?)",
        (source, article, title, f"https://www.yu.ac.kr/{article}", "2026-10-29", "본문"),
    )
    conn.execute(
        "INSERT INTO analyses (notice_id, analyzer, data, deadline) VALUES (?, 'rules', ?, ?)",
        (cursor.lastrowid, data.model_dump_json(), data.deadline),
    )
    conn.commit()
    return cursor.lastrowid


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "test.sqlite3"

    def override():
        conn = db.connect(path)
        try:
            yield conn
        finally:
            conn.close()

    main.app.dependency_overrides[main.get_conn] = override
    main.app.dependency_overrides[main.today] = lambda: TODAY
    api = TestClient(main.app)
    api.conn = db.connect(path)
    yield api
    api.conn.close()
    main.app.dependency_overrides.clear()


def make_user(client, username="seungbeom", **extra):
    body = {
        "username": username, "password": "test-password", "agreed": True,
        "name": "승범", "department": "정보통신공학전공", "grade": 3, "interests": ["취업·진로"], **extra,
    }
    response = client.post("/api/auth/signup", json=body)
    assert response.status_code == 201
    return response.json()["id"]


def test_login_survives_new_client_and_logout_ends_session(client):
    uid = make_user(client)
    assert "password_hash" not in client.get("/api/auth/me").json()
    assert client.put(f"/api/users/{uid}/subscriptions/swedu").status_code == 204

    other = TestClient(main.app)
    assert other.get(f"/api/users/{uid}/feed").status_code == 401
    wrong = other.post("/api/auth/login", json={"username": "seungbeom", "password": "wrong-password"})
    assert wrong.status_code == 401

    login = other.post("/api/auth/login", json={"username": "seungbeom", "password": "test-password"})
    assert login.status_code == 200 and login.json()["id"] == uid
    assert any(s["id"] == "swedu" and s["subscribed"] for s in other.get(f"/api/users/{uid}/sources").json())

    assert other.post("/api/auth/logout").status_code == 204
    assert other.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me").status_code == 200


def test_users_cannot_read_each_other(client):
    first = make_user(client, "first-user")
    second_client = TestClient(main.app)
    second = make_user(second_client, "second-user")
    assert second_client.get(f"/api/users/{second}/feed").status_code == 200
    assert second_client.get(f"/api/users/{first}/feed").status_code == 403
    assert second_client.get(f"/api/users/{first}/calendar.ics").status_code == 403
    assert second_client.put(f"/api/users/{first}/subscriptions/rise").status_code == 403


def test_signup_validation(client):
    make_user(client)
    other = TestClient(main.app)
    base = {"password": "test-password", "name": "a", "department": "경영학과", "grade": 1, "agreed": True}
    assert other.post("/api/auth/signup", json={**base, "username": "seungbeom"}).status_code == 409
    assert other.post("/api/auth/signup", json={**base, "username": "a b"}).status_code == 422
    assert other.post("/api/auth/signup", json={**base, "username": "newuser", "password": "short"}).status_code == 422
    assert other.get("/api/auth/me").status_code == 401


def test_old_department_names_are_renamed(tmp_path):
    path = tmp_path / "old.sqlite3"
    conn = db.connect(path)
    conn.execute("INSERT INTO users (id, name, department, grade) VALUES ('u', 'a', '정보통신공학과', 3)")
    conn.commit()
    conn.close()
    conn = db.connect(path)
    assert conn.execute("SELECT department FROM users").fetchone()[0] == "정보통신공학전공"
    conn.close()


def test_signup_requires_consent(client):
    body = {"username": "newuser", "password": "test-password", "name": "a", "department": "경영학과", "grade": 1}
    assert client.post("/api/auth/signup", json=body).status_code == 422
    assert client.post("/api/auth/signup", json={**body, "agreed": True}).status_code == 201
    consent = client.conn.execute("SELECT consented_at FROM users").fetchone()[0]
    assert consent


def test_login_locks_after_repeated_failures(client):
    make_user(client)
    other = TestClient(main.app)
    bad = {"username": "seungbeom", "password": "wrong-password"}
    good = {"username": "seungbeom", "password": "test-password"}
    assert [other.post("/api/auth/login", json=bad).status_code for _ in range(5)] == [401] * 5
    assert other.post("/api/auth/login", json=bad).status_code == 429
    assert other.post("/api/auth/login", json=good).status_code == 429

    client.conn.execute("UPDATE login_failures SET locked_until = '2000-01-01'")
    client.conn.commit()
    assert other.post("/api/auth/login", json=good).status_code == 200
    assert client.conn.execute("SELECT count(*) FROM login_failures").fetchone()[0] == 0


def test_password_change_ends_other_sessions(client):
    make_user(client)
    other = TestClient(main.app)
    other.post("/api/auth/login", json={"username": "seungbeom", "password": "test-password"})

    wrong = {"current_password": "bad-password", "new_password": "next-password"}
    assert client.post("/api/auth/password", json=wrong).status_code == 403
    body = {"current_password": "test-password", "new_password": "next-password"}
    assert client.post("/api/auth/password", json=body).status_code == 204

    assert client.get("/api/auth/me").status_code == 200
    assert other.get("/api/auth/me").status_code == 401
    old = other.post("/api/auth/login", json={"username": "seungbeom", "password": "test-password"})
    assert old.status_code == 401
    assert other.post("/api/auth/login", json={"username": "seungbeom", "password": "next-password"}).status_code == 200


def test_delete_account_removes_all_user_data(client):
    uid = make_user(client)
    notice_id = seed(client.conn, "1", "공지", category="취업·진로", deadline="2026-11-13",
                     events=[deadline_event("2026-11-13")])
    client.post(f"/api/users/{uid}/notices/{notice_id}/schedule")
    client.get(f"/api/users/{uid}/alerts")

    assert client.post("/api/auth/delete-account", json={"password": "wrong-password"}).status_code == 403
    assert client.post("/api/auth/delete-account", json={"password": "test-password"}).status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    for table in ("users", "sessions", "subscriptions", "schedule_items", "alerts"):
        assert client.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
    assert client.conn.execute("SELECT count(*) FROM notices").fetchone()[0] == 1


def test_attachments_require_login(client, cache):
    use_fetcher(FakeFetcher())
    attachment = seed_attachment(client, "안내.pdf", "pdf")
    for path in ("", "/file", "/text"):
        assert client.get(f"/api/attachments/{attachment}{path}").status_code == 401


def test_health_and_security_headers(client):
    seed(client.conn, "1", "공지")
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok" and response.json()["notices"] == 1
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors" in response.headers["content-security-policy"]


def department_boards(monkeypatch):
    sources = {
        "ice": config.Source("ice", "정보통신공학과", "학과 공지", "https://x/ice", "dept"),
        "computer": config.Source("computer", "컴퓨터학부", "학과 공지", "https://x/computer", "dept"),
        "math": config.Source("math", "수학과", "학과 공지", "https://x/math", "dept"),
    }
    monkeypatch.setattr(config, "SOURCE_BY_ID", {**config.SOURCE_BY_ID, **sources})
    monkeypatch.setattr(config, "DEPARTMENT_SOURCES", {
        "정보통신공학전공": "ice", "컴퓨터학부": "computer", "수학과": "math",
    })


def test_major_and_parent_boards_are_subscribed_and_count_as_mine(client, monkeypatch):
    department_boards(monkeypatch)
    uid = make_user(client, interests=[])
    sources = client.get(f"/api/users/{uid}/sources").json()
    assert [s["id"] for s in sources[:2]] == ["ice", "computer"]
    assert all(s["subscribed"] for s in sources[:2])

    major = seed(client.conn, "1", "전공 공지", source="ice")
    school = seed(client.conn, "2", "학부 공지", source="computer")
    other = seed(client.conn, "3", "다른 학과 공지", source="math")
    blocked = seed(client.conn, "4", "1학년 전용", source="computer", grades=[1])

    feed = client.get(f"/api/users/{uid}/feed").json()
    mine = {card["id"]: card["reason"] for card in feed["mine"]}
    assert mine == {major: "내 학과 공지", school: "내 학과 공지"}
    assert other not in mine and blocked not in mine
    assert feed["hidden_count"] == 1


def test_changing_department_replaces_department_boards(client, monkeypatch):
    department_boards(monkeypatch)
    uid = make_user(client)
    assert client.put(f"/api/users/{uid}/subscriptions/swedu").status_code == 204
    body = {"name": "승범", "department": "수학과", "grade": 3, "interests": []}
    assert client.patch(f"/api/users/{uid}", json=body).status_code == 200
    subscribed = {s["id"] for s in client.get(f"/api/users/{uid}/sources").json() if s["subscribed"]}
    assert subscribed == {"yu-news", "swedu", "math"}


def test_passwords_are_hashed():
    stored = auth.hash_password("test-password")
    assert "test-password" not in stored
    assert auth.verify_password("test-password", stored)
    assert not auth.verify_password("wrong-password", stored)
    assert not auth.verify_password("test-password", None)


def deadline_event(day):
    return NoticeEvent(title="신청 마감", date=day, end_date=None, kind="deadline")


def test_feed_sorts_into_sections(client):
    uid = make_user(client)
    urgent = seed(client.conn, "1", "임박", departments=["SW중심대학 참여 학과"], deadline="2026-11-06")
    mine = seed(client.conn, "2", "내 공지", category="취업·진로", deadline="2026-11-13")
    other = seed(client.conn, "3", "일반", category="장학")
    seed(client.conn, "4", "다른 학과", departments=["간호학과"])
    seed(client.conn, "5", "지난 공지", category="취업·진로", deadline="2026-10-20")
    seed(client.conn, "6", "미구독", source="rise", category="취업·진로")

    data = client.get(f"/api/users/{uid}/feed").json()
    assert [c["id"] for c in data["urgent"]] == [urgent]
    assert data["urgent"][0]["d_day"] == 5
    assert [c["id"] for c in data["mine"]] == [mine]
    assert [c["id"] for c in data["others"]] == [other]
    assert data["match_count"] == 2
    assert data["hidden_count"] == 1


def test_feed_drops_old_notices_without_deadline(client):
    uid = make_user(client)
    notice_id = seed(client.conn, "1", "오래된 공지", category="취업·진로")
    assert client.get(f"/api/users/{uid}/feed").json()["match_count"] == 1
    client.conn.execute("UPDATE notices SET posted_at = '2026-09-01' WHERE id = ?", (notice_id,))
    client.conn.commit()
    assert client.get(f"/api/users/{uid}/feed").json()["match_count"] == 0


def test_subscribe_adds_source_and_recommends(client):
    uid = make_user(client)
    sources = client.get(f"/api/users/{uid}/sources").json()
    assert [s["id"] for s in sources if s["recommended"]] == ["ice", "computer", "swedu", "aibootcamp", "rise"]
    assert next(s for s in sources if s["id"] == "yu-news")["subscribed"]
    assert {"anchor", "globalhuss", "volunteer", "intl"} <= {s["id"] for s in sources}

    notice_id = seed(client.conn, "1", "사업단 공지", source="swedu", category="취업·진로")
    assert client.get(f"/api/users/{uid}/feed").json()["match_count"] == 0
    assert client.put(f"/api/users/{uid}/subscriptions/swedu").status_code == 204
    assert client.get(f"/api/users/{uid}/feed").json()["mine"][0]["id"] == notice_id
    assert client.delete(f"/api/users/{uid}/subscriptions/yu-news").status_code == 409


def test_schedule_ics_and_alerts(client):
    uid = make_user(client)
    tomorrow = "2026-11-02"
    notice_id = seed(client.conn, "1", "내일 마감", category="취업·진로", deadline=tomorrow,
                     events=[deadline_event(tomorrow)])

    detail = client.get(f"/api/users/{uid}/notices/{notice_id}").json()
    assert detail["saved"] is False
    assert "calendar.google.com" in detail["events"][0]["google_url"]
    assert "20261102%2F20261103" in detail["events"][0]["google_url"]

    assert client.post(f"/api/users/{uid}/notices/{notice_id}/schedule").status_code == 201
    assert client.post(f"/api/users/{uid}/notices/{notice_id}/schedule").status_code == 201
    items = client.get(f"/api/users/{uid}/schedule").json()
    assert len(items) == 1 and items[0]["d_day"] == 1

    ics = client.get(f"/api/users/{uid}/calendar.ics")
    assert "DTSTART;VALUE=DATE:20261102" in ics.text and "TRIGGER:-P1D" in ics.text

    alerts = client.get(f"/api/users/{uid}/alerts").json()
    assert {a["title"] for a in alerts} == {"내일 마감이에요", "나에게 해당되는 공지예요"}
    assert len(client.get(f"/api/users/{uid}/alerts").json()) == 2

    client.post(f"/api/users/{uid}/alerts/read")
    assert all(a["read"] for a in client.get(f"/api/users/{uid}/alerts").json())

    assert client.delete(f"/api/users/{uid}/notices/{notice_id}/schedule").status_code == 204
    assert client.get(f"/api/users/{uid}/schedule").json() == []


def test_deadline_is_added_when_analysis_lists_only_the_event(client):
    uid = make_user(client)
    event = NoticeEvent(title="취업 컨설팅", date="2026-11-25", end_date=None, kind="event")
    notice_id = seed(client.conn, "1", "(~11.13.) 컨설팅 모집", deadline="2026-11-13", events=[event])

    detail = client.get(f"/api/users/{uid}/notices/{notice_id}").json()
    assert [(e["date"], e["kind"]) for e in detail["events"]] == [("2026-11-13", "deadline"), ("2026-11-25", "event")]
    assert detail["events"][0]["title"] == "컨설팅 모집 신청 마감"

    assert client.post(f"/api/users/{uid}/notices/{notice_id}/schedule").status_code == 201
    assert [i["kind"] for i in client.get(f"/api/users/{uid}/schedule").json()] == ["deadline", "event"]


def test_schedule_without_events_conflicts(client):
    uid = make_user(client)
    notice_id = seed(client.conn, "1", "일정 없음")
    assert client.post(f"/api/users/{uid}/notices/{notice_id}/schedule").status_code == 409


class FakeFetcher:
    def __init__(self, data=b"%PDF", error=None):
        self.data, self.error, self.calls = data, error, 0

    def get_bytes(self, url):
        self.calls += 1
        if self.error:
            raise self.error
        return self.data


def seed_attachment(client, name, ext):
    notice_id = seed(client.conn, name, "첨부 공지")
    cursor = client.conn.execute(
        "INSERT INTO attachments (notice_id, name, ext, url, status) VALUES (?, ?, ?, ?, 'read')",
        (notice_id, name, ext, f"https://www.yu.ac.kr/file/{name}"),
    )
    client.conn.commit()
    return cursor.lastrowid


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ATTACHMENT_CACHE", tmp_path / "attachments")


def use_fetcher(fetcher):
    main.app.dependency_overrides[main.get_fetcher] = lambda: fetcher


def test_attachment_inline_download_and_cache(client, cache):
    make_user(client)
    fetcher = FakeFetcher()
    use_fetcher(fetcher)
    attachment = seed_attachment(client, "안내 문서.pdf", "pdf")

    info = client.get(f"/api/attachments/{attachment}").json()
    assert info["preview"] == "pdf"

    inline = client.get(f"/api/attachments/{attachment}/file")
    assert inline.content == b"%PDF"
    assert inline.headers["content-type"] == "application/pdf"
    assert inline.headers["content-disposition"].startswith("inline;")

    saved = client.get(f"/api/attachments/{attachment}/file?download=true")
    assert saved.headers["content-disposition"].startswith("attachment;")
    assert "filename*=UTF-8''%EC%95%88%EB%82%B4" in saved.headers["content-disposition"]
    assert fetcher.calls == 1


def test_personal_attachment_is_never_fetched(client, cache):
    make_user(client)
    fetcher = FakeFetcher()
    use_fetcher(fetcher)
    attachment = seed_attachment(client, "합격자 명단.xlsx", "xlsx")
    client.conn.execute("UPDATE attachments SET status = 'personal' WHERE id = ?", (attachment,))
    client.conn.commit()
    info = client.get(f"/api/attachments/{attachment}").json()
    assert info["personal"] is True and info["preview"] == "none"
    assert client.get(f"/api/attachments/{attachment}/file").status_code == 403
    assert client.get(f"/api/attachments/{attachment}/text").status_code == 403
    assert fetcher.calls == 0


def test_attachment_unknown_type_is_never_inline(client, cache):
    make_user(client)
    use_fetcher(FakeFetcher(b"<script>"))
    attachment = seed_attachment(client, "압축.html", "html")
    response = client.get(f"/api/attachments/{attachment}/file")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["content-type"] == "application/octet-stream"
    assert client.get(f"/api/attachments/{attachment}").json()["preview"] == "none"
    assert client.get(f"/api/attachments/{attachment}/text").status_code == 415


def test_attachment_text_and_failures(client, cache):
    make_user(client)
    use_fetcher(FakeFetcher("신청 마감".encode()))
    text = seed_attachment(client, "메모.txt", "txt")
    assert client.get(f"/api/attachments/{text}/text").json() == {"text": "신청 마감"}

    use_fetcher(FakeFetcher(b"broken"))
    broken = seed_attachment(client, "손상.hwp", "hwp")
    assert client.get(f"/api/attachments/{broken}/text").status_code == 422

    use_fetcher(FakeFetcher(error=OSError("down")))
    missing = seed_attachment(client, "실패.pdf", "pdf")
    assert client.get(f"/api/attachments/{missing}/file").status_code == 502
    assert client.get("/api/attachments/999999").status_code == 404


def test_unknown_inputs(client):
    body = {"username": "someone", "password": "test-password", "name": "a", "department": "없는과", "grade": 1, "agreed": True}
    assert client.post("/api/auth/signup", json=body).status_code == 422
    assert client.get("/api/users/none/feed").status_code == 401


def test_duplicate_notices_are_merged_and_keep_best_match(client, monkeypatch):
    department_boards(monkeypatch)
    uid = make_user(client, interests=[])
    seed(client.conn, "1", "[컴퓨터학부] 2026 하반기 마일리지 신청", source="computer")
    seed(client.conn, "2", "「2026 하반기 마일리지 신청」 안내", source="ice")
    seed(client.conn, "3", "2026 하반기 장학금 신청 안내", source="ice")

    cards = [*client.get(f"/api/users/{uid}/feed").json()["mine"]]
    assert len(cards) == 2 and "2026 하반기 장학금 신청 안내" in [card["title"] for card in cards]
    merged = next(card for card in cards if "마일리지" in card["title"])
    assert merged["also"] == [next(s for s in ("컴퓨터학부", "정보통신공학과") if s != merged["source"])]


def test_feed_can_show_one_board(client, monkeypatch):
    department_boards(monkeypatch)
    uid = make_user(client, interests=[])
    seed(client.conn, "1", "학부 공지", source="computer")
    seed(client.conn, "2", "전공 공지", source="ice")
    seed(client.conn, "3", "학교 공지", source="yu-news", category="장학")

    only = client.get(f"/api/users/{uid}/feed", params={"source": "ice"}).json()
    assert [c["title"] for c in [*only["mine"], *only["others"]]] == ["전공 공지"]
    assert client.get(f"/api/users/{uid}/feed", params={"source": "math"}).json()["match_count"] == 0


PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 32


def test_avatar_upload_replace_and_delete(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AVATAR_DIR", tmp_path / "avatars")
    uid = make_user(client)
    url = f"/api/users/{uid}/avatar"
    assert client.get("/api/auth/me").json()["has_avatar"] is False
    assert client.get(url).status_code == 404

    assert client.put(url, files={"file": ("me.png", PNG)}).status_code == 204
    assert client.get("/api/auth/me").json()["has_avatar"] is True
    shown = client.get(url)
    assert shown.content == PNG and shown.headers["content-type"] == "image/png"

    webp = b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 16
    assert client.put(url, files={"file": ("me.webp", webp)}).status_code == 204
    assert client.get(url).headers["content-type"] == "image/webp"

    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404 and not (tmp_path / "avatars" / uid).exists()


def test_avatar_rejects_fake_and_large_files_and_others(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AVATAR_DIR", tmp_path / "avatars")
    uid = make_user(client)
    url = f"/api/users/{uid}/avatar"
    assert client.put(url, files={"file": ("me.png", b"<svg onload=alert(1)>")}).status_code == 415
    assert client.put(url, files={"file": ("me.png", PNG + b"\0" * (3 * 1024 * 1024))}).status_code == 413
    other = TestClient(main.app)
    make_user(other, "second-user")
    assert other.put(url, files={"file": ("me.png", PNG)}).status_code == 403
    assert other.get(url).status_code == 403


def test_account_deletion_removes_avatar(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AVATAR_DIR", tmp_path / "avatars")
    uid = make_user(client)
    client.put(f"/api/users/{uid}/avatar", files={"file": ("me.png", PNG)})
    client.post("/api/auth/delete-account", json={"password": "test-password"})
    assert not (tmp_path / "avatars" / uid).exists()


def test_search_finds_title_and_summary_ignoring_spaces(client):
    uid = make_user(client, interests=[])
    seed(client.conn, "1", "2026 해커톤 참가자 모집", category="경진대회")
    seed(client.conn, "2", "장학금 안내", summary=["SW 마일리지 장학금 신청 안내"], category="장학")
    seed(client.conn, "3", "기숙사 안내")

    def titles(q):
        data = client.get(f"/api/users/{uid}/feed", params={"q": q}).json()
        return sorted(c["title"] for c in [*data["urgent"], *data["mine"], *data["others"]])

    assert titles("해커 톤") == ["2026 해커톤 참가자 모집"]
    assert titles("마일리지") == ["장학금 안내"]
    assert titles("장학 신청") == ["장학금 안내"]
    assert titles("없는단어") == []
    assert len(titles("")) == 3


def test_hidden_notices_and_last_crawl_are_returned(client):
    uid = make_user(client)
    hidden = seed(client.conn, "1", "간호학과 전용", departments=["간호학과"])
    data = client.get(f"/api/users/{uid}/feed").json()
    assert [c["id"] for c in data["hidden"]] == [hidden] and data["hidden_count"] == 1
    assert data["last_crawl"]


def test_feedback_is_stored_and_visible_to_office(client, monkeypatch):
    monkeypatch.setattr(config, "ADMIN_USERNAMES", {"office-staff"})
    uid = make_user(client)
    notice_id = seed(client.conn, "1", "간호학과 전용", departments=["간호학과"])
    url = f"/api/users/{uid}/notices/{notice_id}/feedback"
    assert client.post(url, json={"kind": "wrong_hide", "note": "저도 대상이에요"}).status_code == 204
    assert client.post(url, json={"kind": "nonsense"}).status_code == 422
    assert client.post(f"/api/users/{uid}/notices/99999/feedback", json={"kind": "wrong_info"}).status_code == 404
    assert client.get("/api/admin/feedback").status_code == 403

    office = TestClient(main.app)
    make_user(office, "office-staff")
    listed = office.get("/api/admin/feedback").json()
    assert listed[0]["label"] == "해당되는데 숨겨졌어요" and listed[0]["note"] == "저도 대상이에요"
    assert listed[0]["department"] == "정보통신공학전공"


def test_search_covers_unsubscribed_boards_but_feed_does_not(client):
    uid = make_user(client, interests=[])
    seed(client.conn, "1", "2026 해커톤 참가자 모집", source="swedu", category="경진대회")
    feed = client.get(f"/api/users/{uid}/feed").json()
    assert all("해커톤" not in c["title"] for c in [*feed["mine"], *feed["others"]])
    found = client.get(f"/api/users/{uid}/feed", params={"q": "해커톤"}).json()
    assert [c["source"] for c in [*found["mine"], *found["others"]]] == ["SW중심대학사업단"]


def test_summary_counts_new_matches_before_inbox_is_opened(client):
    uid = make_user(client)
    seed(client.conn, "1", "취업 공지", category="취업·진로")
    assert client.get(f"/api/users/{uid}/summary").json()["unread_alerts"] == 1


def test_search_includes_expired_notices(client):
    uid = make_user(client, interests=["경진대회"])
    seed(client.conn, "1", "지난 해커톤", category="경진대회", deadline="2026-10-20")
    assert client.get(f"/api/users/{uid}/feed").json()["match_count"] == 0
    found = client.get(f"/api/users/{uid}/feed", params={"q": "해커톤"}).json()
    cards = [*found["urgent"], *found["mine"]]
    assert [c["title"] for c in cards] == ["지난 해커톤"] and cards[0]["d_day"] < 0
    assert found["urgent"] == []
