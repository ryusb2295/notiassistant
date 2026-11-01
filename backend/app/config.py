"""공지비서 설정: 게시판, 학과, 관심사 목록과 환경 변수."""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DB_PATH = Path(os.getenv("NOTI_DB", BACKEND_DIR / "data" / "noti.sqlite3"))
ATTACHMENT_CACHE = BACKEND_DIR / "data" / "attachments"
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "") == "1"  # HTTPS로 배포할 때 1
ADMIN_USERNAMES = {name.strip() for name in os.getenv("ADMIN_USERNAMES", "").split(",") if name.strip()}
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "")  # openai, claude, rules. 비우면 키로 판단
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
CRAWL_INTERVAL_MIN = int(os.getenv("CRAWL_INTERVAL_MIN", "0"))
CRAWL_USER_AGENT = os.getenv(
    "CRAWL_USER_AGENT", "GongjiBiseo/0.1 (YU SW hackathon team 7 prototype)"
)
CRAWL_DELAY_SEC = float(os.getenv("CRAWL_DELAY_SEC", "1.0"))
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
MAX_ATTACHMENTS_PER_NOTICE = 5


def attachment_path(url: str) -> Path:
    return ATTACHMENT_CACHE / hashlib.sha256(url.encode()).hexdigest()


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    description: str
    url: str
    kind: str  # base: 전원 기본, program: 사업단, dept: 학과, direct: 행정실 직접 게시


SOURCES: tuple[Source, ...] = (
    Source("yu-news", "영대소식", "학교 전체 공지 · 장학 · 행사",
           "https://www.yu.ac.kr/main/intro/yu-news.do", "base"),
    Source("swedu", "SW중심대학사업단", "경진대회 · 특강 · 해외 SW 연수",
           "https://www.yu.ac.kr/swedu/notice/notice.do", "program"),
    Source("aibootcamp", "첨단AI산업인재양성부트캠프", "AI 몰입 교육 · 현장실습 · 인턴십",
           "https://www.yu.ac.kr/aibootcamp/board/notice.do", "program"),
    Source("rise", "RISE사업단", "창업밸리 · 지역혁신 LAB · 실무 인재",
           "https://www.yu.ac.kr/rise/board/notice.do", "program"),
    Source("direct", "행정실 공지", "공지비서에 직접 게시한 공지", "", "direct"),
    Source("ice", "정보통신공학과", "학과 공지",
           "https://www.yu.ac.kr/ice/board/notice.do", "dept"),
)
SOURCE_BY_ID = {s.id: s for s in SOURCES}

SW_GROUP = "SW중심대학 참여 학과"


# 학과 목록은 영남대 홈페이지 대학·대학원 안내의 대학안내 기준이고, 2027학년도 신설 학부·전공은 뺐다.
# 값이 튜플이면 (학부, 소속 전공 목록)이다.
COLLEGES: dict[str, list[str | tuple[str, list[str]]]] = {
    "인문대학": ["국어국문학과", "일어일문학과", "영어영문학과",
             ("유럽언어문화학부", ["프랑스어문전공", "독일언어문화전공"]),
             "철학과", "역사학과", "문화인류학과"],
    "자연과학대학": ["수학과", "통계학과", "물리학과", "화학과", "생명과학과"],
    "공과대학": ["건설시스템공학과", "환경공학과", "도시공학과",
             ("건축학부", ["건축학전공", "건축공학전공", "건축디자인전공"]),
             ("기계공학부", ["기계공학전공"]),
             ("신소재공학부", ["신소재공학전공"]),
             "전기공학과",
             ("화학공학부", ["고분자·바이오소재전공", "화공시스템전공", "융합화학공학전공", "에너지화공전공"]),
             "파이버시스템공학과"],
    "디지털융합대학": ["전자공학과",
                ("컴퓨터학부", ["컴퓨터공학전공", "정보통신공학전공", "소프트웨어융합전공"]),
                "미래자동차공학과", "로봇공학과", "차세대반도체학과",
                ("소프트웨어응용학부", ["AI데이터사이언스", "응용소프트웨어", "미디어융합"]),
                "자동차소프트웨어학과", "스마트모빌리티학과"],
    "사회과학대학": ["정치외교학과", "행정학과", "심리학과", "사회학과", "미디어커뮤니케이션학과",
               "경찰행정학과", "군사학과"],
    "경영대학": [("경제금융학부", ["경제금융전공"]), "경영학과",
             ("무역학부", ["무역학전공"]), "회계세무학과", "항공운송학과", "산업경영학과"],
    "의과대학": ["의예과", "의학과"],
    "약학대학": [("약학부", ["약학전공", "제약학전공"])],
    "생명응용과학대학": ["식품경제외식학과", "원예생명과학과", "조경학과", "산림자원학과",
                 "식품공학과", "생명공학과", "의생명공학과"],
    "생활과학대학": ["주거환경학과", "식품영양학과", "의류패션학과",
               ("체육학부", ["체육학전공", "무용학전공"]), "휴먼서비스학과"],
    "사범대학": ["교육학과", "국어교육과", "영어교육과", "한문교육과", "수학교육과", "유아교육과", "특수체육교육과"],
    "예술대학": ["회화과", "트랜스아트과", "시각디자인학과", "산업디자인학과", "생활제품디자인학과",
             ("음악학부", ["국악및작곡전공", "성악전공", "피아노전공", "관현악전공"])],
    "글로벌인재대학": ["중국언어문화학과", "국제개발새마을학과",
                ("글로벌교육학부", ["국제한국어교육전공"]), "글로벌비즈니스학과",
                ("글로벌통번역학부", ["영어통번역전공", "응용중국어통번역전공"]),
                "글로벌학부", "글로벌교양학부"],
    "천마학부대학": ["전공자유선택학부", "천마인재학부"],
}

# 2026년도 하반기 SW중심대학사업단 마일리지 신청 공지의 지급 대상 학부(과)다.
SW_DEPARTMENTS = {
    "컴퓨터학부", "소프트웨어응용학부", "자동차소프트웨어학과", "화학공학부",
    "미래자동차공학과", "로봇공학과", "전자공학과", "미디어커뮤니케이션학과",
    "시각디자인학과", "통계학과", "경영학과", "스마트모빌리티학과",
}
ALIASES = {
    "컴퓨터공학전공": ("컴퓨터공학과",),
    "정보통신공학전공": ("정보통신공학과",),
    "소프트웨어응용학부": ("SW응용학부",),
    "자동차소프트웨어학과": ("자동차SW학과",),
}
DEPARTMENT_SOURCES = {"정보통신공학전공": "ice"}


@dataclass(frozen=True)
class Department:
    name: str
    college: str
    parent: str = ""
    sw_group: bool = False
    aliases: tuple[str, ...] = ()
    source_id: str = ""

    @property
    def terms(self) -> tuple[str, ...]:
        return tuple(t for t in (self.name, *self.aliases, self.parent, self.college) if t)


def _department(name: str, college: str, parent: str = "") -> Department:
    return Department(
        name, college, parent,
        sw_group=name in SW_DEPARTMENTS or parent in SW_DEPARTMENTS,
        aliases=ALIASES.get(name, ()),
        source_id=DEPARTMENT_SOURCES.get(name, ""),
    )


def _departments() -> tuple[Department, ...]:
    result = []
    for college, entries in COLLEGES.items():
        for entry in entries:
            name, majors = (entry, []) if isinstance(entry, str) else entry
            result.append(_department(name, college))
            result.extend(_department(major, college, name) for major in majors)
    return tuple(result)


DEPARTMENTS = _departments()
DEPARTMENT_BY_NAME = {d.name: d for d in DEPARTMENTS}

CATEGORIES = ("장학", "취업·진로", "교육·특강", "경진대회", "대외활동", "학사", "행사", "자격증", "기타")
INTERESTS = ("장학", "취업·진로", "교육·특강", "경진대회", "대외활동", "자격증")
