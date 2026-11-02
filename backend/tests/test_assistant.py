from datetime import date, timedelta

from fastapi.testclient import TestClient

from app import assistant, main
from app.assistant import Answer, Plan

from .test_api import FakeFetcher, cache, client, make_user, seed, seed_attachment, use_fetcher  # noqa: F401


class FakeLLM:
    """assistant.complete 대신 불려서 AI에 보낸 내용을 기록하고 정해진 답을 돌려준다."""

    def __init__(self, plan=None, answer=None):
        self.calls = []
        self.plan = plan or Plan(keywords=["해커톤"], deadlines=False)
        self.answer = answer or Answer(answer="11월 20일에 열려요.", used=[1])

    def __call__(self, system, text, schema):
        self.calls.append((schema.__name__, text))
        return self.plan if schema is Plan else self.answer


def install(monkeypatch, **kwargs):
    llm = FakeLLM(**kwargs)
    monkeypatch.setattr(assistant, "complete", llm)
    return llm


def test_notice_question_reads_body_and_attachment_but_not_profile(client, cache, monkeypatch):  # noqa: F811
    llm = install(monkeypatch)
    use_fetcher(FakeFetcher("참가비는 무료이고 노트북을 챙겨 오세요".encode()))
    uid = make_user(client)
    attachment = seed_attachment(client, "안내.txt", "txt")
    notice_id = client.conn.execute("SELECT notice_id FROM attachments WHERE id = ?", (attachment,)).fetchone()[0]

    response = client.post(f"/api/users/{uid}/ask", json={"question": "준비물 뭐야?", "notice_id": notice_id})
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "notice" and data["sources"][0]["id"] == notice_id

    sent = llm.calls[0][1]
    assert "노트북을 챙겨 오세요" in sent and "준비물 뭐야?" in sent
    assert "승범" not in sent and "정보통신공학전공" not in sent


def test_search_question_plans_searches_and_cites(client, monkeypatch):  # noqa: F811
    llm = install(monkeypatch, answer=Answer(answer="해커톤은 11월 20일이에요.", used=[1, 9]))
    uid = make_user(client)
    hackathon = seed(client.conn, "1", "제2회 창업 해커톤 안내", source="swedu")
    seed(client.conn, "2", "기숙사 입사 안내")

    data = client.post(f"/api/users/{uid}/ask", json={"question": "해커톤 언제야?"}).json()
    assert [call[0] for call in llm.calls] == ["Plan", "Answer"]
    assert "제2회 창업 해커톤 안내" in llm.calls[1][1] and "기숙사" not in llm.calls[1][1]
    assert [s["id"] for s in data["sources"]] == [hackathon]  # 없는 번호 9는 버린다
    assert data["keywords"] == ["해커톤"]


def test_same_notice_on_two_boards_is_cited_once(client, monkeypatch):  # noqa: F811
    llm = install(monkeypatch, plan=Plan(keywords=["공모전"], deadlines=False),
                  answer=Answer(answer="수기 공모전이 있어요.", used=[1, 2]))
    uid = make_user(client)
    seed(client.conn, "1", "「2026 글로벌공생HUSS 수기 공모전」안내", source="globalhuss")
    seed(client.conn, "2", "[글로벌공생HUSS] 「2026 글로벌공생HUSS 수기 공모전」 안내")
    data = client.post(f"/api/users/{uid}/ask", json={"question": "공모전 있어?"}).json()
    assert len(data["sources"]) == 1
    assert llm.calls[1][1].count("수기 공모전") == 1


def test_follow_up_question_keeps_previous_notices(client, monkeypatch):  # noqa: F811
    llm = install(monkeypatch, plan=Plan(keywords=[], deadlines=True), answer=Answer(answer="11월 11일이에요.", used=[1]))
    uid = make_user(client)
    contest = seed(client.conn, "1", "수기 공모전 안내", deadline="2099-11-11")
    seed(client.conn, "2", "행정보조 채용", deadline=(date.today() + timedelta(days=2)).isoformat())
    body = {"question": "그중에 마감 제일 빠른 거?", "context_ids": [contest]}
    client.post(f"/api/users/{uid}/ask", json=body)
    listing = llm.calls[1][1]
    assert listing.index("수기 공모전") < listing.index("행정보조 채용")  # 이전 공지가 [1]로 먼저 온다


def test_deadline_question_finds_notices_due_soon(client, monkeypatch):  # noqa: F811
    install(monkeypatch, plan=Plan(keywords=[], deadlines=True), answer=Answer(answer="두 건이에요.", used=[]))
    uid = make_user(client)
    today = date.today()
    soon = seed(client.conn, "1", "곧 마감", deadline=(today + timedelta(days=3)).isoformat())
    seed(client.conn, "2", "한참 남음", deadline=(today + timedelta(days=60)).isoformat())
    seed(client.conn, "3", "이미 지남", deadline=(today - timedelta(days=1)).isoformat())
    data = client.post(f"/api/users/{uid}/ask", json={"question": "이번 주 마감 뭐 있어?"}).json()
    assert [s["id"] for s in data["sources"]] == [soon]


def test_no_results_skips_second_call(client, monkeypatch):  # noqa: F811
    llm = install(monkeypatch, plan=Plan(keywords=["존재하지않는단어"], deadlines=False))
    uid = make_user(client)
    seed(client.conn, "1", "기숙사 입사 안내")
    data = client.post(f"/api/users/{uid}/ask", json={"question": "아무거나"}).json()
    assert data["sources"] == [] and len(llm.calls) == 1


def test_limits_and_errors(client, monkeypatch):  # noqa: F811
    uid = make_user(client)
    url = f"/api/users/{uid}/ask"

    def unavailable(*args):
        raise assistant.LLMUnavailable

    monkeypatch.setattr(assistant, "complete", unavailable)
    assert client.post(url, json={"question": "질문"}).status_code == 503
    assert client.post(url, json={"question": ""}).status_code == 422
    assert client.post(url, json={"question": "x", "notice_id": 99999}).status_code == 404

    monkeypatch.setattr(assistant, "HOURLY_LIMIT", 4)
    statuses = [client.post(url, json={"question": "질문"}).status_code for _ in range(3)]
    assert statuses[-1] == 429


def test_other_users_cannot_ask_as_me(client, monkeypatch):  # noqa: F811
    install(monkeypatch)
    uid = make_user(client)
    other = TestClient(main.app)
    make_user(other, "second-user")
    assert other.post(f"/api/users/{uid}/ask", json={"question": "질문"}).status_code == 403
