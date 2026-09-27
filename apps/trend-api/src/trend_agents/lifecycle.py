"""트렌드 생애주기 판정. 결정론 규칙만. LLM 은 이 결과를 서술만 한다.

입력은 주간 언급 수(쇼츠 등장 + 뉴스 등장 + 데이터랩 지수 등을 합산한 것), 오래된 → 최근 순.
"""
from __future__ import annotations

from .schemas import Lifecycle

DORMANT_WEEKS = 4
EMERGING_MAX_WEEKS = 2
RISE_RATIO = 1.5
PEAK_RATIO = 0.8
DECLINE_RATIO = 0.6


def stage(weekly_counts: list[int], weeks_since_first_seen: int) -> Lifecycle:
    if not weekly_counts or sum(weekly_counts) == 0:
        return "dormant" if weeks_since_first_seen > DORMANT_WEEKS and weekly_counts else "unknown"
    tail = weekly_counts[-DORMANT_WEEKS:]
    if len(weekly_counts) > DORMANT_WEEKS and sum(tail) == 0:
        return "dormant"
    recent = weekly_counts[-1]
    prior = weekly_counts[-2] if len(weekly_counts) > 1 else 0
    peak = max(weekly_counts)
    if weeks_since_first_seen <= EMERGING_MAX_WEEKS and recent > 0:
        return "emerging"
    if prior > 0 and recent >= prior * RISE_RATIO:
        return "rising"
    if recent >= peak * PEAK_RATIO and peak >= 2 * max(1, min(weekly_counts)):
        return "peak"  # 실제로 '올라간' 이력이 있어야 peak. 평평한 곡선은 steady
    if recent <= peak * DECLINE_RATIO and recent <= prior:
        return "declining"
    return "steady"


def recheck_interval_days(lc: Lifecycle) -> int:
    """빨리 변하는 것은 자주 다시 본다. 리서치 에이전트의 재검증 주기."""
    return {"emerging": 2, "rising": 3, "peak": 7, "steady": 14, "declining": 14, "dormant": 60, "unknown": 7}[lc]
