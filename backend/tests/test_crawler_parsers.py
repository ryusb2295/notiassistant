import io
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook

from app import crawler, parsers

FIXTURES = Path(__file__).parent / "fixtures"
BASE = "https://www.yu.ac.kr/swedu/notice/notice.do"


def test_parse_list_reads_rows():
    items = crawler.parse_list((FIXTURES / "list.html").read_text(encoding="utf-8"), BASE)
    assert len(items) >= 10
    first = items[0]
    assert first.article_no == "232147880"
    assert first.title.startswith("[모집기한 연장] 2026년 SW전공 진로설계 캠프")
    assert first.posted_at == "2026-10-19"
    assert first.pinned
    assert first.url == f"{BASE}?mode=view&articleNo=232147880"


def test_parse_article_reads_body_and_inline_image():
    article = crawler.parse_article((FIXTURES / "view.html").read_text(encoding="utf-8"), BASE)
    assert article.title == "[SW중심대학사업단] 2026년도 AI 활용 역량 인증 프로그램(AICE Associate) 2기 모집"
    assert article.posted_at == "2026-10-29"
    assert "AICE Associate" in article.body
    assert any("/_attach/" in src for src in article.inline_images)


def test_parse_article_keeps_inline_spans_on_one_line():
    html = (
        '<div class="b-content-box"><p>4. 신청 기간 : <span>11.6.</span> ~ <span><b>11.12.</b></span></p>'
        "<table><tr><td>대상</td><td>재학생</td></tr></table></div>"
    )
    assert crawler.parse_article(html, BASE).body == "4. 신청 기간 : 11.6. ~ 11.12.\n대상 재학생"


def test_robots_blocks_attach_path():
    class Response:
        text = "User-agent: *\nDisallow: /_attach\n\nUser-agent: ClaudeBot\nDisallow: /\n"

    fetcher = crawler.Fetcher(delay=0)
    fetcher._get = lambda url: Response()
    assert fetcher.allowed(BASE + "?mode=fileDownload&articleNo=1&attachNo=2")
    assert not fetcher.allowed("https://www.yu.ac.kr/_attach/yu/editor-image/a.png")
    with pytest.raises(PermissionError):
        fetcher.get_bytes("https://www.yu.ac.kr/_attach/yu/editor-image/a.png")


def test_hwpx_text():
    xml = (
        '<sec xmlns:hp="urn:hp"><hp:p><hp:run><hp:t>신청 마감</hp:t></hp:run>'
        '<hp:run><hp:t> 11월 13일</hp:t></hp:run></hp:p>'
        '<hp:p><hp:run><hp:tbl><hp:p><hp:run><hp:t>대상: 재학생</hp:t></hp:run></hp:p></hp:tbl></hp:run></hp:p></sec>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Contents/section0.xml", xml)
    assert parsers.extract_text("hwpx", buffer.getvalue()) == "신청 마감 11월 13일\n대상: 재학생"


def test_xlsx_text():
    book = Workbook()
    book.active.append(["활동", "점수"])
    book.active.append(["해커톤", 10])
    buffer = io.BytesIO()
    book.save(buffer)
    text = parsers.extract_text("xlsx", buffer.getvalue())
    assert "활동 | 점수" in text and "해커톤 | 10" in text


def test_hwp_para_text_skips_controls():
    wide = (11).to_bytes(2, "little") + b"\0" * 14
    chunk = "표".encode("utf-16-le") + wide + "내용".encode("utf-16-le") + (13).to_bytes(2, "little")
    assert parsers._hwp_para_text(chunk) == "표내용"


def test_hwp_records_are_walked():
    text = "마감일".encode("utf-16-le")
    record = (parsers.HWP_PARA_TEXT | (len(text) << 20)).to_bytes(4, "little") + text
    other = (66 | (2 << 20)).to_bytes(4, "little") + b"\0\0"
    assert parsers._hwp_paragraphs(other + record) == ["마감일"]


def test_pdf_text_drops_invalid_characters(monkeypatch):
    class Page:
        def extract_text(self):
            return "마감\ud83d 11월 13일"

    class Reader:
        pages = [Page()]

        def __init__(self, stream):
            pass

    monkeypatch.setattr(parsers, "PdfReader", Reader)
    assert parsers.extract_text("pdf", b"") == "마감 11월 13일"


def test_unsupported_extension():
    with pytest.raises(parsers.UnsupportedAttachment):
        parsers.extract_text("zip", b"")
