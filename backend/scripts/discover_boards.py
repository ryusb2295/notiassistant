"""학교 학과 안내에서 학과별 공지 게시판을 찾아 app/department_boards.json에 저장한다.

`python scripts/discover_boards.py`로 실행한다. 학기마다 주소가 바뀌었는지 확인할 때 다시 돌린다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, crawler  # noqa: E402

GUIDE_URL = "https://www.yu.ac.kr/main/academics/university.do"
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "department_boards.json"
# 학과 사이트가 쓰는 게시판 경로. 메뉴에서 못 찾을 때 순서대로 시험한다.
COMMON_PATHS = ("board/notice.do", "notice/notice.do", "community/notice.do", "major/notice.do")
NAME_ALIASES = {"건축학전공(5년제)": "건축학전공", "산업경영학과": "산업경영학과"}
SECONDARY_BOARD = re.compile(r"grad|master|abeek|bk21|koica|certificate|employment")


def department_homes(html: str) -> dict[str, str]:
    """안내 페이지를 문서 순서로 읽어 학과 이름 바로 뒤의 홈페이지 링크를 짝짓는다."""
    soup = BeautifulSoup(html, "html.parser")
    names = {*config.DEPARTMENT_BY_NAME, *NAME_ALIASES}
    homes: dict[str, str] = {}
    current = None
    for node in soup.descendants:
        if isinstance(node, NavigableString):
            text = node.strip()
            if text in names:
                current = NAME_ALIASES.get(text, text)
            elif text in config.COLLEGES:
                current = None
        elif isinstance(node, Tag) and node.name == "a" and current and "홈페이지" in node.get_text():
            href = node.get("href", "")
            if href.startswith("http") or href.startswith("/"):
                homes.setdefault(current, urljoin(GUIDE_URL, href))
                current = None
    return homes


def notice_candidates(html: str, home: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found = []
    for link in soup.find_all("a", href=True):
        label = link.get_text(" ", strip=True)
        href = link["href"]
        if "공지" in label and "articleNo" not in href and not href.startswith(("#", "javascript")):
            found.append(urljoin(home, href).split("?")[0])
    for link in soup.find_all("a", href=re.compile(r"[/-]notice\.do")):
        if "articleNo" not in link["href"]:
            found.append(urljoin(home, link["href"]).split("?")[0])
    root = re.match(r"(https?://[^/]+/[^/]+/)", home)
    if root:
        found += [root[1] + path for path in COMMON_PATHS]
    unique = dict.fromkeys(url for url in found if url.endswith(".do"))
    # 대학원·인증 게시판은 학부생 공지가 아니므로 뒤로 미룬다.
    return sorted(unique, key=lambda url: bool(SECONDARY_BOARD.search(url)))


def board_slug(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.strip("/").split("/")
    return re.sub(r"[^a-z0-9-]", "-", (path[0] if path else parsed.netloc).lower())


def main() -> None:
    fetcher = crawler.Fetcher()
    homes = department_homes(fetcher.get_text(GUIDE_URL))
    print(f"홈페이지 {len(homes)}곳")
    only = set(sys.argv[1:])  # 학과 이름을 주면 그 학과만 다시 조사한다
    boards = json.loads(OUTPUT.read_text(encoding="utf-8")) if only and OUTPUT.exists() else {}
    for name, home in homes.items():
        if only and name not in only:
            continue
        try:
            response = fetcher.session.get(home, timeout=20, allow_redirects=True)
            response.encoding = "utf-8"
            final = response.url
            candidates = notice_candidates(response.text, final)
        except Exception as exc:
            print(f"실패 {name}: {type(exc).__name__}")
            continue
        for url in candidates:
            try:
                items = crawler.parse_list(fetcher.get_text(url), url)
            except Exception:
                continue
            if items:
                boards[name] = {"id": board_slug(url), "url": url}
                print(f"{name}: {url} ({len(items)}건)")
                break
        else:
            print(f"게시판 없음 {name}: {final}")
    OUTPUT.write_text(json.dumps(boards, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(f"저장 {len(boards)}곳")


if __name__ == "__main__":
    main()
