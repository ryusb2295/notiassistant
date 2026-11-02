"""첨부파일 다운로드와 캐시. 첨부 보기 화면과 AI 비서가 함께 쓴다."""
from __future__ import annotations

import logging
import sqlite3
from functools import lru_cache

from fastapi import HTTPException

from . import config, crawler

log = logging.getLogger(__name__)


@lru_cache
def get_fetcher() -> crawler.Fetcher:
    return crawler.Fetcher()


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
