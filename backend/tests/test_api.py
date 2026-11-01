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
        "username": username, "password": "test-password",
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
    base = {"password": "test-password", "name": "a", "department": "경영학과", "grade": 1}
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
    assert [s["id"] for s in sources if s["recommended"]] == ["ice", "swedu", "aibootcamp", "rise"]
    assert next(s for s in sources if s["id"] == "yu-news")["subscribed"]

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
    use_fetcher(FakeFetcher(b"<script>"))
    attachment = seed_attachment(client, "압축.html", "html")
    response = client.get(f"/api/attachments/{attachment}/file")
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.headers["content-type"] == "application/octet-stream"
    assert client.get(f"/api/attachments/{attachment}").json()["preview"] == "none"
    assert client.get(f"/api/attachments/{attachment}/text").status_code == 415


def test_attachment_text_and_failures(client, cache):
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
    body = {"username": "someone", "password": "test-password", "name": "a", "department": "없는과", "grade": 1}
    assert client.post("/api/auth/signup", json=body).status_code == 422
    assert client.get("/api/users/none/feed").status_code == 401
