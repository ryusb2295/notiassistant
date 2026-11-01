import json

import anthropic
import httpx2
import openai
import pytest

from app import analyzer, config
from app.analyzer import AttachmentInput, ClaudeAnalyzer, NoticeInput, OpenAIAnalyzer
from app.matcher import GENERAL, MATCH, NO, match_notice

USER = {"department": "정보통신공학전공", "grade": 3, "interests": ["취업·진로"]}


def notice(body="", title="공지", posted="2026-10-27", attachments=None):
    return NoticeInput(title, "SW중심대학사업단", posted, body, attachments or [])


def base(**extra):
    return {"category": "기타", "departments": [], "grades": [], **extra}


def test_rule_deadline_from_text():
    result = analyzer.rule_analyze(notice("신청 기간: 11월 2일 ~ 11월 13일(금)까지"))
    assert result.deadline == "2026-11-13"
    assert result.events[0].kind == "deadline"


def test_rule_full_date_and_grades():
    body = "모집 대상: 2~3학년 재학생\n접수 마감: 2026. 11. 6.(금) 18:00"
    result = analyzer.rule_analyze(notice(body, title="[SW] 캠프 참가자 모집"))
    assert result.deadline == "2026-11-06"
    assert result.grades == [2, 3]
    assert result.category == "교육·특강"


def test_rule_ignores_time_and_past_dates():
    assert analyzer.rule_analyze(notice("행사는 10월 1일에 종료되었습니다. 신청 10월 2일")).deadline is None


def test_rule_year_rolls_over():
    result = analyzer.rule_analyze(notice("신청 마감 1월 15일", posted="2026-12-20"))
    assert result.deadline == "2027-01-15"


def test_rule_reads_attachment_text():
    extra = [AttachmentInput("안내.hwp", "hwp", text="신청 마감: 11월 20일\n대상: SW중심대학 참여 학과 재학생")]
    result = analyzer.rule_analyze(notice("첨부를 확인하세요", attachments=extra))
    assert result.deadline == "2026-11-20"
    assert result.departments == ["SW중심대학 참여 학과"]


def test_rule_deadline_from_title_marker():
    assert analyzer.rule_analyze(notice("본문", title="(~11/2 오후 12시) 신입사원 공개채용")).deadline == "2026-11-02"


def test_rule_ignores_grades_outside_audience():
    form = [AttachmentInput("신청서.hwp", "hwp", text="학년\n3학년\n성명")]
    body = "일괄 적립: 2026 SW전공 진로설계 캠프(2~3학년)\n지급 대상: 재학생"
    assert analyzer.rule_analyze(notice(body, attachments=form)).grades == []


def test_rule_grade_from_title():
    assert analyzer.rule_analyze(notice("본문", title="캠프 모집(2~3학년 대상)")).grades == [2, 3]


def test_match_group_department():
    result = match_notice(USER, base(departments=["SW중심대학 참여 학과"]))
    assert result.status == MATCH and "SW중심대학" in result.reason


def test_match_parent_department():
    assert match_notice(USER, base(departments=["컴퓨터학부"])).status == MATCH


def test_match_ignores_major_and_department_suffix():
    assert match_notice(USER, base(departments=["정보통신공학과"])).status == MATCH
    assert match_notice(USER, base(departments=["컴퓨터학부(컴퓨터공학과)"])).status == MATCH
    assert match_notice(USER, base(departments=["디지털융합대학"])).status == MATCH


def test_similar_department_names_do_not_match():
    user = {"department": "산업경영학과", "grade": 3, "interests": []}
    assert match_notice(user, base(departments=["경영학과"])).status == NO
    economics = {"department": "경영학과", "grade": 3, "interests": []}
    assert match_notice(economics, base(departments=["산업경영학과"])).status == NO


def test_official_department_list():
    names = config.DEPARTMENT_BY_NAME
    assert len(names) == len(config.DEPARTMENTS) >= 100
    assert names["정보통신공학전공"].parent == "컴퓨터학부"
    assert names["정보통신공학전공"].college == "디지털융합대학"
    assert names["에너지화공전공"].sw_group
    assert names["자동차소프트웨어학과"].sw_group
    assert not names["철학과"].sw_group


def test_no_match_other_department():
    assert match_notice(USER, base(departments=["간호학과"])).status == NO


def test_no_match_grade():
    assert match_notice(USER, base(grades=[1, 2])).status == NO


def test_interest_match_and_general():
    assert match_notice(USER, base(category="취업·진로")).status == MATCH
    assert match_notice(USER, base(category="장학")).status == GENERAL


def test_non_sw_department_excluded_from_group():
    user = {"department": "철학과", "grade": 3, "interests": []}
    assert match_notice(user, base(departments=["SW중심대학 참여 학과"])).status == NO


ANALYSIS = {
    "summary": ["취업 컨설팅 참가자 모집"], "category": "취업·진로", "audience": "재학생",
    "departments": [], "grades": [], "deadline": "2026-11-13",
    "events": [{"title": "신청 마감", "date": "2026-11-13", "end_date": None, "kind": "deadline"}],
    "benefit": None, "how_to_apply": "QR 접수", "found_in": ["카드뉴스.jpg"],
}


def claude_with(handler):
    client = anthropic.Anthropic(
        api_key="test-key",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return ClaudeAnalyzer(client=client, model="claude-opus-5-5")


def reply(stop_reason="end_turn"):
    return httpx2.Response(200, json={
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": json.dumps(ANALYSIS, ensure_ascii=False)}],
        "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    })


def test_claude_request_carries_attachments_and_schema():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["beta"] = request.headers.get("anthropic-beta", "")
        return reply()

    attachments = [
        AttachmentInput("안내.pdf", "pdf", data=b"%PDF"),
        AttachmentInput("카드뉴스.jpg", "jpg", data=b"\xff\xd8"),
        AttachmentInput("세부.hwp", "hwp", data=b"x", text="HWP 내용"),
    ]
    used, result = analyzer.analyze(notice("본문", attachments=attachments), claude_with(handler))
    assert used == "claude"
    assert result.deadline == "2026-11-13"
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in seen["beta"]
    assert body["output_config"]["effort"] == "medium"
    assert body["output_config"]["format"]["type"] == "json_schema"
    types = [block["type"] for block in body["messages"][0]["content"]]
    assert types == ["document", "image", "text"]
    assert "HWP 내용" in body["messages"][0]["content"][-1]["text"]


def gpt_with(handler):
    client = openai.OpenAI(
        api_key="test-key",
        max_retries=0,
        http_client=openai.DefaultHttpxClient(transport=httpx2.MockTransport(handler)),
    )
    return OpenAIAnalyzer(client=client, model="gpt-test")


def gpt_reply(content=None, refusal=None):
    return httpx2.Response(200, json={
        "id": "c1", "object": "chat.completion", "created": 1, "model": "gpt-test",
        "choices": [{
            "index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": content, "refusal": refusal},
        }],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })


def test_gpt_request_carries_attachments_and_schema():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return gpt_reply(json.dumps(ANALYSIS, ensure_ascii=False))

    attachments = [
        AttachmentInput("안내.pdf", "pdf", data=b"%PDF", text="PDF 내용"),
        AttachmentInput("카드뉴스.jpg", "jpg", data=b"\xff\xd8"),
    ]
    used, result = analyzer.analyze(notice("본문", attachments=attachments), gpt_with(handler))
    assert used == "openai"
    assert result.deadline == "2026-11-13"
    body = seen["body"]
    assert body["model"] == "gpt-test"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    content = body["messages"][1]["content"]
    assert [block["type"] for block in content] == ["text", "image_url"]
    assert "PDF 내용" in content[0]["text"]
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_gpt_refusal_falls_back_to_rules():
    used, _ = analyzer.analyze(notice("본문"), gpt_with(lambda r: gpt_reply(refusal="거부")))
    assert used == "rules"


@pytest.mark.parametrize("status", [401, 429, 500])
def test_gpt_errors_fall_back_to_rules(status):
    def handler(request):
        return httpx2.Response(status, json={"error": {"message": "x", "type": "x"}})

    used, _ = analyzer.analyze(notice("본문"), gpt_with(handler))
    assert used == "rules"


def test_provider_prefers_configured_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(config, "LLM_PROVIDER", "")
    assert analyzer.provider() == "rules"
    assert analyzer.make_llm() is None
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    assert analyzer.provider() == "openai"
    assert isinstance(analyzer.make_llm(), OpenAIAnalyzer)


def test_refusal_falls_back_to_rules():
    used, result = analyzer.analyze(notice("신청 마감 11월 13일"), claude_with(lambda r: reply("refusal")))
    assert used == "rules"
    assert result.deadline == "2026-11-13"


@pytest.mark.parametrize("status", [429, 500])
def test_api_errors_fall_back_to_rules(status):
    def handler(request):
        return httpx2.Response(status, json={"type": "error", "error": {"type": "x", "message": "x"}})

    used, _ = analyzer.analyze(notice("본문"), claude_with(handler))
    assert used == "rules"
