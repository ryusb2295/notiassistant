import io

import pytest
from fastapi.testclient import TestClient

from app import analyzer, config, main
from app.analyzer import NoticeEvent

from .test_api import cache, client, deadline_event, make_user, seed  # noqa: F401


def event_on(day):
    return NoticeEvent(title="해커톤 본대회", date=day, end_date="2026-11-21", kind="event")


def test_draft_is_filled_from_profile_and_notice(client):
    uid = make_user(client)
    notice_id = seed(client.conn, "1", "[SW] 창업 해커톤 참가 신청", how_to_apply="통합 시스템 신청",
                     deadline="2026-11-12", events=[deadline_event("2026-11-12"), event_on("2026-11-20")])
    draft = client.get(f"/api/users/{uid}/notices/{notice_id}/application").json()
    values = {f["key"]: f["value"] for f in draft["fields"]}
    assert values["name"] == "승범"
    assert values["department"] == "정보통신공학전공"
    assert values["grade"] == "3학년"
    assert values["activity"] == "창업 해커톤 참가 신청"
    assert values["period"] == "2026-11-20 ~ 2026-11-21"
    assert values["student_no"] == ""
    assert draft["filled"] == 5 and draft["total"] == 7
    assert draft["status"] == "new" and draft["how_to_apply"] == "통합 시스템 신청"


def test_draft_saves_edits_and_status(client):
    uid = make_user(client)
    notice_id = seed(client.conn, "1", "공지")
    url = f"/api/users/{uid}/notices/{notice_id}/application"

    saved = client.put(url, json={"values": {"student_no": "22313584", "motivation": "참여"}}).json()
    assert saved["filled"] == 6 and saved["status"] == "draft"
    done = client.put(url, json={"values": {"student_no": "22313584"}, "status": "submitted"}).json()
    assert done["status"] == "submitted"

    text = client.get(f"{url}.txt")
    assert "학번: 22313584" in text.text
    assert text.headers["content-disposition"].startswith("attachment;")
    assert client.put(url, json={"values": {"unknown": "x"}}).status_code == 422


def test_draft_is_private_to_owner(client):
    uid = make_user(client)
    notice_id = seed(client.conn, "1", "공지")
    other = TestClient(main.app)
    assert other.get(f"/api/users/{uid}/notices/{notice_id}/application").status_code == 401
    second = make_user(other, "second-user")
    assert other.get(f"/api/users/{uid}/notices/{notice_id}/application").status_code == 403
    assert other.get(f"/api/users/{second}/notices/{notice_id}/application").status_code == 200


@pytest.fixture
def office(client, cache, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "ADMIN_USERNAMES", {"office-staff"})
    monkeypatch.setattr(analyzer, "make_llm", lambda: None)
    make_user(client, "office-staff")
    return client


def analysis(**fields):
    base = dict(summary=["요약"], category="장학", audience="재학생", departments=[], grades=[], deadline=None,
                events=[], benefit=None, how_to_apply=None, found_in=["본문"])
    return {**base, **fields}


def upload(api, name="마일리지 안내.txt", data="신청 마감 11월 30일\n대상: 재학생".encode()):
    return api.post("/api/admin/analyze", files={"file": (name, io.BytesIO(data))})


def test_admin_routes_require_admin(client):  # noqa: F811
    make_user(client, "plain-user")
    assert client.get("/api/auth/me").json()["is_admin"] is False
    assert client.get("/api/admin/notices").status_code == 403
    assert upload(client).status_code == 403
    assert TestClient(main.app).get("/api/admin/notices").status_code == 401


def test_upload_validation(office):
    assert office.get("/api/auth/me").json()["is_admin"] is True
    assert upload(office, "위험.exe").status_code == 415
    assert upload(office, "합격자 명단.xlsx").status_code == 422
    assert upload(office, "손상.hwp", b"broken").status_code == 422


def test_publish_reaches_only_target_students(office):
    target = TestClient(main.app)
    target_id = make_user(target, "target-user", department="경영학과")
    other = TestClient(main.app)
    other_id = make_user(other, "other-user", department="철학과")

    result = upload(office)
    assert result.status_code == 200
    draft = result.json()
    assert draft["analysis"]["deadline"] and draft["analyzer"] == "rules"

    body = {
        "title": "하반기 마일리지 신청",
        "analysis": analysis(departments=["SW중심대학 참여 학과"], deadline="2026-11-30"),
        "upload": {"file_id": draft["file_id"], "name": draft["name"]},
    }
    published = office.post("/api/admin/notices", json=body)
    assert published.status_code == 201
    notice_id = published.json()["id"]
    assert published.json()["notified"] == 2  # 작성자(정보통신공학전공)와 경영학과

    target_alerts = target.get(f"/api/users/{target_id}/alerts").json()
    assert [a["body"] for a in target_alerts] == ["하반기 마일리지 신청"]
    assert other.get(f"/api/users/{other_id}/alerts").json() == []
    assert target.get(f"/api/users/{target_id}/feed").json()["mine"][0]["id"] == notice_id

    detail = target.get(f"/api/users/{target_id}/notices/{notice_id}").json()
    assert detail["analyzer"] == "admin" and detail["url"] == ""
    file_id = detail["attachments"][0]["id"]
    assert target.get(f"/api/attachments/{file_id}/file?download=true").content.startswith("신청".encode())

    listed = office.get("/api/admin/notices").json()
    assert listed[0]["id"] == notice_id and listed[0]["notified"] == 2


def test_staff_role_can_use_office_tools(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(config, "STAFF_USERNAMES", {"staff-user"})
    make_user(client, "staff-user")
    me = client.get("/api/auth/me").json()
    assert me["role"] == "staff" and me["is_admin"] is True
    assert client.get("/api/admin/notices").status_code == 200


def test_role_labels(monkeypatch):
    monkeypatch.setattr(config, "ADMIN_USERNAMES", {"a"})
    monkeypatch.setattr(config, "STAFF_USERNAMES", {"a", "b"})
    assert [config.role_of(n) for n in ("a", "b", "c", None)] == ["admin", "staff", "student", "student"]


def test_summary_counts_and_application_list(client):  # noqa: F811
    uid = make_user(client)
    assert client.get("/api/auth/me").json()["role"] == "student"
    notice_id = seed(client.conn, "1", "공지", category="취업·진로", deadline="2099-11-13",
                     events=[deadline_event("2099-11-13")])
    client.post(f"/api/users/{uid}/notices/{notice_id}/schedule")
    client.put(f"/api/users/{uid}/notices/{notice_id}/application", json={"values": {"student_no": "1"}})
    client.get(f"/api/users/{uid}/alerts")

    data = client.get(f"/api/users/{uid}/summary").json()
    assert data == {"subscriptions": 3, "upcoming": 1, "applications": 1, "unread_alerts": 1}
    listed = client.get(f"/api/users/{uid}/applications").json()
    assert listed[0]["notice_id"] == notice_id and listed[0]["status"] == "draft"
    assert TestClient(main.app).get(f"/api/users/{uid}/summary").status_code == 401


def test_alert_inbox_read_and_delete(client):  # noqa: F811
    uid = make_user(client)
    first = seed(client.conn, "1", "첫 공지", category="취업·진로")
    seed(client.conn, "2", "둘째 공지", category="취업·진로")
    url = f"/api/users/{uid}/alerts"

    alerts = client.get(url).json()
    assert len(alerts) == 2 and alerts[0]["sender"] == "영대소식" and not alerts[0]["read"]
    target = next(a for a in alerts if a["notice_id"] == first)

    assert client.post(f"{url}/read", json={"ids": [target["id"]]}).status_code == 204
    states = {a["notice_id"]: a["read"] for a in client.get(url).json()}
    assert states[first] == 1 and sum(states.values()) == 1

    assert client.post(f"{url}/delete", json={"ids": [target["id"]]}).status_code == 204
    remaining = client.get(url).json()  # 다시 조회해도 지운 알림이 되살아나지 않는다
    assert [a["notice_id"] for a in remaining] == [n for n in [first + 1]]
    assert client.get(f"/api/users/{uid}/summary").json()["unread_alerts"] == 1

    assert client.post(f"{url}/read").status_code == 204
    assert client.get(f"/api/users/{uid}/summary").json()["unread_alerts"] == 0


def test_alerts_of_others_are_not_touched(client):  # noqa: F811
    uid = make_user(client)
    seed(client.conn, "1", "공지", category="취업·진로")
    alert_id = client.get(f"/api/users/{uid}/alerts").json()[0]["id"]
    other = TestClient(main.app)
    second = make_user(other, "second-user")
    assert other.post(f"/api/users/{second}/alerts/delete", json={"ids": [alert_id]}).status_code == 204
    assert len(client.get(f"/api/users/{uid}/alerts").json()) == 1
    assert other.post(f"/api/users/{uid}/alerts/delete", json={"ids": [alert_id]}).status_code == 403


def test_publish_requires_title_and_known_file(office):
    assert office.post("/api/admin/notices", json={"title": " ", "analysis": analysis()}).status_code == 422
    body = {"title": "공지", "analysis": analysis(), "upload": {"file_id": "missing", "name": "a.pdf"}}
    assert office.post("/api/admin/notices", json=body).status_code == 409


def test_direct_source_cannot_be_subscribed(client):  # noqa: F811
    uid = make_user(client)
    assert client.put(f"/api/users/{uid}/subscriptions/direct").status_code == 404
    assert all(s["id"] != "direct" for s in client.get(f"/api/users/{uid}/sources").json())
