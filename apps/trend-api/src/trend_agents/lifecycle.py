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


RECENT_DAYS = 14
FADING_DAYS = 60


def recency_stage(newest_usage, now=None) -> Lifecycle:
    """꾸준한 원본 수집에 언급이 없을 때, 조사가 찾은 가장 최근 쓰임만으로 정한다. 모양은 말하지 않는다
    — 오르는지 내리는지는 한 번의 검색 표본으로 알 수 없어서 '꾸준함·지는 중·잠잠함' 만 쓴다."""
    from datetime import datetime, timezone

    if newest_usage is None:
        return "unknown"
    days = ((now or datetime.now(timezone.utc)) - newest_usage).days
    if days <= RECENT_DAYS:
        return "steady"
    if days <= FADING_DAYS:
        return "declining"
    return "dormant"


def recheck_interval_days(lc: Lifecycle) -> int:
    """빨리 변하는 것은 자주 다시 본다. 리서치 에이전트의 재검증 주기."""
    return {"emerging": 2, "rising": 3, "peak": 7, "steady": 14, "declining": 14, "dormant": 60, "unknown": 7}[lc]


MAINSTREAM_NEWS = 3


def diffusion(kinds: dict[str, int], lc: Lifecycle):
    """어디까지 퍼졌나(Plan 02). 이미 수집하는 근거의 출처 종류만 본다 — X·인스타·틱톡은 모으지 않아 쓰지 않는다.

    태동  커뮤니티 근거만 있다
    확산  쇼츠 근거가 있고 언급이 막 뜨거나 오르는 중이다
    주류  뉴스 근거가 3건 이상이고 정점이거나 꾸준하다
    식상  뉴스 근거가 있고 지는 중이거나 잠잠하다
    어느 것도 아니면 None(판단 보류).
    """
    community, short, news = kinds.get("community", 0), kinds.get("short", 0), kinds.get("news", 0)
    if news and lc in ("declining", "dormant"):
        return "fading"
    if news >= MAINSTREAM_NEWS and lc in ("peak", "steady"):
        return "mainstream"
    if short and lc in ("emerging", "rising"):
        return "spreading"
    if community and not short and not news:
        return "underground"
    return None
