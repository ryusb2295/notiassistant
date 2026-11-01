from pathlib import Path

from app import config, crawler, db, pipeline
from app.analyzer import NoticeAnalysis

FIXTURES = Path(__file__).parent / "fixtures"
SOURCE = config.SOURCE_BY_ID["swedu"]


class FakeFetcher:
    def __init__(self):
        self.pages = 0

    def get_text(self, url):
        if "mode=view" in url:
            self.pages += 1
            return (FIXTURES / "view.html").read_text(encoding="utf-8")
        return (FIXTURES / "list.html").read_text(encoding="utf-8")

    def get_bytes(self, url):
        raise OSError("첨부 없음")


class FakeLLM:
    name = "openai"

    def analyze(self, notice):
        return NoticeAnalysis(
            summary=["AI 요약"], category="자격증", audience="재학생", departments=[], grades=[],
            deadline=None, events=[], benefit=None, how_to_apply=None, found_in=["본문"],
        )


def analyzers(conn):
    return [row[0] for row in conn.execute("SELECT analyzer FROM analyses")]


def test_rule_notices_are_upgraded_and_keep_user_schedule(tmp_path):
    conn = db.connect(tmp_path / "t.sqlite3")
    fetcher = FakeFetcher()

    assert pipeline.crawl_source(conn, fetcher, SOURCE, 2, None) == 2
    assert analyzers(conn) == ["rules", "rules"]
    assert pipeline.crawl_source(conn, fetcher, SOURCE, 2, None) == 0

    notice_id = conn.execute("SELECT id FROM notices ORDER BY id LIMIT 1").fetchone()[0]
    conn.execute("INSERT INTO users (id, name, department, grade) VALUES ('u', 'a', '철학과', 1)")
    conn.execute(
        "INSERT INTO schedule_items (user_id, notice_id, title, date, kind) "
        "VALUES ('u', ?, '마감', '2026-11-13', 'deadline')",
        (notice_id,),
    )
    conn.commit()

    assert pipeline.crawl_source(conn, fetcher, SOURCE, 2, FakeLLM()) == 2
    assert analyzers(conn) == ["openai", "openai"]
    assert conn.execute("SELECT count(*) FROM notices").fetchone()[0] == 2
    assert conn.execute("SELECT count(*) FROM schedule_items").fetchone()[0] == 1

    pages = fetcher.pages
    assert pipeline.crawl_source(conn, fetcher, SOURCE, 2, FakeLLM()) == 0
    assert fetcher.pages == pages


def test_personal_files_are_detected():
    assert pipeline.is_personal_file("서류전형 합격자(면접 대상자) 명단.xlsx")
    assert not pipeline.is_personal_file("참가 신청서 양식_학생.hwp")


def test_personal_attachment_is_not_downloaded_or_sent(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "t.sqlite3")
    link = crawler.AttachmentLink("합격자 명단.xlsx", "xlsx", "https://www.yu.ac.kr/f")
    article = crawler.Article("제목", "2026-10-28", "본문", [link])
    monkeypatch.setattr(crawler, "parse_article", lambda html, url: article)
    seen = {}

    class Spy(FakeLLM):
        def analyze(self, notice):
            seen["attachments"] = notice.attachments
            return super().analyze(notice)

    item = crawler.ListItem("1", "제목", "https://www.yu.ac.kr/a?mode=view", "2026-10-28")
    pipeline.process_article(conn, FakeFetcher(), SOURCE, item, Spy())
    assert seen["attachments"] == []
    assert conn.execute("SELECT status FROM attachments").fetchone()[0] == "personal"


def test_list_items_are_limited(tmp_path):
    conn = db.connect(tmp_path / "t.sqlite3")
    assert pipeline.crawl_source(conn, FakeFetcher(), SOURCE, 1, None) == 1
    assert isinstance(crawler.parse_list((FIXTURES / "list.html").read_text(encoding="utf-8"), SOURCE.url)[0], crawler.ListItem)
