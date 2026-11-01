"""영남대 게시판 크롤러. robots.txt를 지키고 요청 사이에 간격을 둔다."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from . import config

log = logging.getLogger(__name__)

BLOCK_TAGS = "p, div, li, tr, h1, h2, h3, h4, h5, h6, table, ul, ol, blockquote"


@dataclass
class ListItem:
    article_no: str
    title: str
    url: str
    posted_at: str
    pinned: bool = False


@dataclass
class AttachmentLink:
    name: str
    ext: str
    url: str


@dataclass
class Article:
    title: str
    posted_at: str
    body: str
    attachments: list[AttachmentLink] = field(default_factory=list)
    inline_images: list[str] = field(default_factory=list)


def parse_list(html: str, base_url: str) -> list[ListItem]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for row in soup.select("table.board-table tbody tr"):
        link = row.select_one(".b-title-box a[href*='articleNo=']")
        if link is None:
            continue
        url = urljoin(base_url, link["href"])
        article_no = parse_qs(urlparse(url).query)["articleNo"][0]
        title = link.get_text(" ", strip=True)
        date = row.select_one(".b-date")
        posted = _iso_date(date.get_text(strip=True)) if date else ""
        items.append(ListItem(
            article_no=article_no,
            title=title,
            url=f"{base_url}?mode=view&articleNo={article_no}",
            posted_at=posted,
            pinned="b-top-box" in (row.get("class") or []),
        ))
    return items


def parse_article(html: str, base_url: str) -> Article:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".b-title")
    date = soup.select_one(".b-date-box span:last-child")
    content = soup.select_one(".b-content-box")
    body = ""
    images: list[str] = []
    if content is not None:
        images = [urljoin(base_url, img["src"]) for img in content.select("img[src]")]
        body = _block_text(content)
    attachments: dict[str, AttachmentLink] = {}
    for link in soup.select("a[href*='mode=fileDownload']"):
        url = urljoin(base_url, link["href"])
        name = link.get_text(" ", strip=True)
        if url in attachments or not name:
            continue
        attachments[url] = AttachmentLink(name=name, ext=name.rsplit(".", 1)[-1].lower(), url=url)
    return Article(
        title=title.get_text(strip=True) if title else "",
        posted_at=_iso_date(date.get_text(strip=True)) if date else "",
        body=body,
        attachments=list(attachments.values()),
        inline_images=images,
    )


def _block_text(content) -> str:
    """인라인 태그로 잘린 글자는 잇고, 문단과 표 행만 줄로 나눈다."""
    for tag in content.select("br"):
        tag.replace_with("\n")
    for tag in content.select(BLOCK_TAGS):
        tag.append("\n")
    for cell in content.select("td, th"):
        cell.append(" ")
    lines = (" ".join(line.split()) for line in content.get_text().replace("\xa0", " ").splitlines())
    return "\n".join(line for line in lines if line)


def _iso_date(text: str) -> str:
    match = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", text)
    return f"{match[1]}-{int(match[2]):02d}-{int(match[3]):02d}" if match else ""


class Fetcher:
    """robots.txt 허용 여부를 URL마다 확인하고 요청 간격을 지킨다."""

    def __init__(self, delay: float | None = None, session: requests.Session | None = None):
        self.delay = config.CRAWL_DELAY_SEC if delay is None else delay
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = config.CRAWL_USER_AGENT
        self._robots: dict[str, RobotFileParser] = {}
        self._last_request = 0.0

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots = self._robots.get(origin)
        if robots is None:
            response = self._get(f"{origin}/robots.txt")
            robots = RobotFileParser()
            robots.parse(response.text.splitlines())
            self._robots[origin] = robots
        return robots.can_fetch(config.CRAWL_USER_AGENT, url)

    def get_text(self, url: str) -> str:
        self._require_allowed(url)
        response = self._get(url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding if not response.encoding else response.encoding
        return response.text

    def get_bytes(self, url: str) -> bytes:
        self._require_allowed(url)
        self._wait()
        with self.session.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(64 * 1024):
                data.extend(chunk)
                if len(data) > config.MAX_DOWNLOAD_BYTES:
                    raise ValueError("첨부파일이 너무 큽니다")
        return bytes(data)

    def _require_allowed(self, url: str) -> None:
        if not self.allowed(url):
            raise PermissionError(f"robots.txt 금지 경로: {url}")

    def _get(self, url: str) -> requests.Response:
        self._wait()
        return self.session.get(url, timeout=30)

    def _wait(self) -> None:
        remaining = self.delay - (time.monotonic() - self._last_request)
        if remaining > 0:
            time.sleep(remaining)
        self._last_request = time.monotonic()
