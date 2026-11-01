"""AI가 추출한 조건을 학생 프로필과 비교한다. 해당 여부는 코드가 결정한다."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import DEPARTMENT_BY_NAME, SW_GROUP

MATCH = "match"      # 조건이 맞거나 관심사가 일치
GENERAL = "general"  # 제한은 없지만 관심사와 다름
NO = "no"            # 대상이 아님

SEPARATOR = re.compile(r"[\s()\[\],·/]+")
SUFFIX = re.compile(r"(전공|학과|과)$")


@dataclass
class MatchResult:
    status: str
    reason: str


def match_notice(user: dict[str, Any], analysis: dict[str, Any]) -> MatchResult:
    department = DEPARTMENT_BY_NAME.get(user["department"])
    grades = analysis.get("grades") or []
    required = analysis.get("departments") or []

    if grades and user["grade"] not in grades:
        return MatchResult(NO, f"{_join(grades)}학년 대상")

    dept_reason = ""
    if required:
        dept_reason = _department_reason(user["department"], department, required)
        if not dept_reason:
            return MatchResult(NO, f"{', '.join(required)} 대상")

    grade_reason = f"{user['grade']}학년 대상" if grades else ""
    interest = analysis.get("category") in user.get("interests", [])
    if dept_reason or grade_reason:
        reasons = [r for r in (dept_reason, grade_reason) if r]
        if interest:
            reasons.append(f"관심사 {analysis['category']}")
        return MatchResult(MATCH, " · ".join(reasons))
    if interest:
        return MatchResult(MATCH, f"관심사 일치 · {analysis['category']}")
    return MatchResult(GENERAL, "대상 제한 없음")


def _normalize(name: str) -> str:
    """전공·학과 표기 차이만 지운다. 글자 포함 비교는 산업경영학과와 경영학과를 혼동한다."""
    return SUFFIX.sub("", name)


def _department_reason(name: str, department: Any, required: list[str]) -> str:
    if SW_GROUP in required and department is not None and department.sw_group:
        return "SW중심대학 참여 학과 해당"
    terms = {_normalize(t) for t in (department.terms if department is not None else (name,))}
    for item in required:
        if any(_normalize(part) in terms for part in SEPARATOR.split(item) if part):
            return f"{item} 해당"
    return ""


def _join(grades: list[int]) -> str:
    return ",".join(str(g) for g in sorted(grades))
