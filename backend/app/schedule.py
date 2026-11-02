"""일정 내보내기와 마감 알림."""
from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode


TITLE_NOISE = re.compile(r"\[[^\]]*\]|\([^)]*\)|[^0-9A-Za-z가-힣]")
TITLE_TAIL = re.compile(r"(안내|공고|알림|공지)+$")


def title_key(title: str) -> str:
    """게시판마다 다른 말머리, 기호, 끝의 "안내" 같은 말을 빼고 같은 공지인지 비교할 열쇠를 만든다."""
    return TITLE_TAIL.sub("", TITLE_NOISE.sub("", title).lower())


def short_title(title: str) -> str:
    return re.sub(r"^((\[[^\]]*\]|\([^)]*\))\s*)+", "", title).strip()[:40]


def notice_events(title: str, analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """분석 일정에 신청 마감이 빠져 있으면 채운다. 마감 알림이 이 일정을 기준으로 동작한다."""
    events = list(analysis.get("events") or [])
    deadline = analysis.get("deadline")
    if deadline and not any(e["kind"] == "deadline" and e["date"] == deadline for e in events):
        events.insert(0, {"title": f"{short_title(title)} 신청 마감", "date": deadline, "end_date": None, "kind": "deadline"})
    return events


def google_calendar_url(item: dict[str, Any], details: str = "") -> str:
    start = date.fromisoformat(item["date"])
    # 구글 캘린더 종일 일정의 종료일은 다음 날로 넘긴다.
    end = date.fromisoformat(item.get("end_date") or item["date"]) + timedelta(days=1)
    query = urlencode({
        "action": "TEMPLATE",
        "text": item["title"],
        "dates": f"{start:%Y%m%d}/{end:%Y%m%d}",
        "details": details,
    })
    return f"https://calendar.google.com/calendar/render?{query}"


def _ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(items: list[dict[str, Any]]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GongjiBiseo//KO",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:공지비서",
    ]
    for item in items:
        start = date.fromisoformat(item["date"])
        end = date.fromisoformat(item.get("end_date") or item["date"]) + timedelta(days=1)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{item['id']}@gongjibiseo",
            f"DTSTAMP:{start:%Y%m%d}T000000Z",
            f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
            f"DTEND;VALUE=DATE:{end:%Y%m%d}",
            f"SUMMARY:{_ics_escape(item['title'])}",
        ]
        if item["kind"] == "deadline":
            lines += [
                "BEGIN:VALARM",
                "TRIGGER:-P1D",
                "ACTION:DISPLAY",
                f"DESCRIPTION:{_ics_escape(item['title'])}",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def generate_deadline_alerts(conn: sqlite3.Connection, user_id: str, today: date) -> None:
    """저장한 마감의 D-1, D-day 알림을 만든다. 같은 알림은 한 번만 생긴다."""
    rows = conn.execute(
        "SELECT id, notice_id, title, date FROM schedule_items WHERE user_id = ? AND kind = 'deadline'",
        (user_id,),
    ).fetchall()
    with conn:
        for row in rows:
            days = (date.fromisoformat(row["date"]) - today).days
            if days not in (0, 1):
                continue
            label = "오늘 마감이에요" if days == 0 else "내일 마감이에요"
            conn.execute(
                "INSERT OR IGNORE INTO alerts (user_id, notice_id, key, title, body) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, row["notice_id"], f"deadline:{row['id']}:{days}", label, row["title"]),
            )


def generate_notice_alerts(
    conn: sqlite3.Connection, user_id: str, feed: dict[str, list[dict[str, Any]]]
) -> None:
    """맞춤 피드에 새로 들어온 공지 알림을 만든다."""
    with conn:
        for item in [*feed["urgent"], *feed["mine"]]:
            conn.execute(
                "INSERT OR IGNORE INTO alerts (user_id, notice_id, key, title, body) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, item["id"], f"notice:{item['id']}", "나에게 해당되는 공지예요", item["title"]),
            )
