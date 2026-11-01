"""수집 → 첨부 분석 → 저장 파이프라인. `python -m app.pipeline --limit 15`로 실행한다."""
from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3

from . import analyzer, config, crawler, db, parsers
from .analyzer import AttachmentInput, ClaudeAnalyzer, NoticeInput, OpenAIAnalyzer
from .parsers import IMAGE_MEDIA_TYPES, UnsupportedAttachment

log = logging.getLogger(__name__)
LLM = ClaudeAnalyzer | OpenAIAnalyzer | None
PERSONAL_FILE = re.compile(r"명단|합격자|선발자|선정자|수상자|당첨자|학번|성적")


def is_personal_file(name: str) -> bool:
    """학생 이름이 담겼을 수 있는 파일은 내려받지 않고 외부 LLM으로도 보내지 않는다."""
    return PERSONAL_FILE.search(name) is not None


def read_attachment(
    fetcher: crawler.Fetcher, link: crawler.AttachmentLink
) -> tuple[AttachmentInput, str]:
    """첨부를 받아 분석 입력으로 바꾼다. 상태는 read, unsupported, failed 중 하나다."""
    item = AttachmentInput(name=link.name, ext=link.ext)
    if link.ext not in IMAGE_MEDIA_TYPES and link.ext not in parsers.TEXT_EXTENSIONS:
        return item, "unsupported"
    try:
        item.data = fetcher.get_bytes(link.url)
        if link.ext not in IMAGE_MEDIA_TYPES:
            item.text = parsers.extract_text(link.ext, item.data)
    except UnsupportedAttachment:
        return item, "unsupported"
    except Exception as exc:  # 첨부 하나의 실패가 공지 전체를 막지 않게 한다
        log.warning("첨부 처리 실패 %s: %s", link.name, exc)
        return item, "failed"
    return item, "read"


def process_article(
    conn: sqlite3.Connection,
    fetcher: crawler.Fetcher,
    source: config.Source,
    item: crawler.ListItem,
    llm: LLM,
) -> None:
    article = crawler.parse_article(fetcher.get_text(item.url), source.url)
    inputs: list[AttachmentInput] = []
    statuses: list[tuple[crawler.AttachmentLink, AttachmentInput, str]] = []
    for link in article.attachments[:config.MAX_ATTACHMENTS_PER_NOTICE]:
        if is_personal_file(link.name):
            statuses.append((link, AttachmentInput(link.name, link.ext), "personal"))
            continue
        data, status = read_attachment(fetcher, link)
        # 이미지는 LLM만 읽을 수 있다.
        if status == "read" and llm is None and link.ext in IMAGE_MEDIA_TYPES:
            status = "needs_ai"
        statuses.append((link, data, status))
        if status == "read":
            inputs.append(data)

    title = article.title or item.title
    posted_at = article.posted_at or item.posted_at
    # 본문 삽입 이미지는 대부분 robots.txt 금지 경로라 읽지 않고 개수만 남긴다.
    skipped = len(article.inline_images)
    used, result = analyzer.analyze(
        NoticeInput(title, source.name, posted_at, article.body, inputs), llm
    )
    with conn:
        existing = conn.execute(
            "SELECT id FROM notices WHERE source_id = ? AND article_no = ?",
            (source.id, item.article_no),
        ).fetchone()
        if existing:
            # 다시 분석할 때는 id를 유지해 저장된 일정과 알림을 지킨다.
            notice_id = existing["id"]
            conn.execute(
                "UPDATE notices SET title = ?, url = ?, posted_at = ?, body = ?, skipped_images = ? "
                "WHERE id = ?",
                (title, item.url, posted_at, article.body, skipped, notice_id),
            )
            conn.execute("DELETE FROM attachments WHERE notice_id = ?", (notice_id,))
            conn.execute("DELETE FROM analyses WHERE notice_id = ?", (notice_id,))
        else:
            notice_id = conn.execute(
                "INSERT INTO notices (source_id, article_no, title, url, posted_at, body, skipped_images) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (source.id, item.article_no, title, item.url, posted_at, article.body, skipped),
            ).lastrowid
        for link, data, status in statuses:
            chars = len(data.text) if status == "read" else 0
            conn.execute(
                "INSERT INTO attachments (notice_id, name, ext, url, status, chars) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (notice_id, link.name, link.ext, link.url, status, chars),
            )
        conn.execute(
            "INSERT INTO analyses (notice_id, analyzer, data, deadline) VALUES (?, ?, ?, ?)",
            (notice_id, used, result.model_dump_json(), result.deadline),
        )


def crawl_source(
    conn: sqlite3.Connection,
    fetcher: crawler.Fetcher,
    source: config.Source,
    limit: int,
    llm: LLM,
) -> int:
    items = crawler.parse_list(fetcher.get_text(source.url), source.url)
    # LLM을 쓸 수 있으면 규칙 분석으로 남은 공지도 다시 처리한다. 호출 한도에 걸린 공지가 여기서 복구된다.
    done_filter = " AND a.analyzer != 'rules'" if llm else ""
    known = {
        row["article_no"]
        for row in conn.execute(
            "SELECT n.article_no FROM notices n JOIN analyses a ON a.notice_id = n.id "
            f"WHERE n.source_id = ?{done_filter}",
            (source.id,),
        )
    }
    added = 0
    for item in items[:limit]:
        if item.article_no in known:
            continue
        try:
            process_article(conn, fetcher, source, item, llm)
            added += 1
            log.info("[%s] %s", source.name, item.title)
        except Exception:
            log.exception("공지 처리 실패: %s", item.url)
    return added


def run(conn: sqlite3.Connection, limit: int = 15, source_ids: list[str] | None = None) -> dict[str, int]:
    llm = analyzer.make_llm()
    if llm is None:
        log.warning("LLM 키가 없어 규칙 분석만 실행합니다.")
    fetcher = crawler.Fetcher()
    # 학과 게시판은 100곳이 넘어 구독자가 있는 곳만 수집해 AI 호출 한도를 아낀다.
    wanted = {row[0] for row in conn.execute("SELECT DISTINCT source_id FROM subscriptions")}
    result = {}
    for source in config.SOURCES:
        if source.kind == "direct" or (source_ids and source.id not in source_ids):
            continue
        if source.kind == "dept" and not source_ids and source.id not in wanted:
            continue
        try:
            result[source.id] = crawl_source(conn, fetcher, source, limit, llm)
        except Exception:
            log.exception("게시판 수집 실패: %s", source.name)
            result[source.id] = 0
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="공지 수집과 분석")
    parser.add_argument("--limit", type=int, default=15, help="게시판별 최대 공지 수")
    parser.add_argument("--source", action="append", help="특정 게시판 id만 수집")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    conn = db.connect()
    print(json.dumps(run(conn, args.limit, args.source), ensure_ascii=False))


if __name__ == "__main__":
    main()
