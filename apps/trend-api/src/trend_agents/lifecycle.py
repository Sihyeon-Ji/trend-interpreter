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

    태동  커뮤니티 근거만 있고, 참고 문서(ADR 0003 — 나무위키·위키백과·Know Your Meme·pixiv 백과사전·萌娘百科)가 아직 없다
    확산  쇼츠 근거가 있고 언급이 막 뜨거나 오르는 중이다
    주류  뉴스 근거가 3건 이상이고 정점이거나 꾸준하다
    식상  뉴스 근거가 있고 지는 중이거나 잠잠하다
    어느 것도 아니면 None(판단 보류).
    """
    community, short, news = kinds.get("community", 0), kinds.get("short", 0), kinds.get("news", 0)
    documented = kinds.get("documented", 0)
    if news and lc in ("declining", "dormant"):
        return "fading"
    if news >= MAINSTREAM_NEWS and lc in ("peak", "steady"):
        return "mainstream"
    if short and lc in ("emerging", "rising"):
        return "spreading"
    # 문서가 있는 말은 이미 자리 잡은 밈이다 — 'The cake is a lie'(2007) 같은 것이 '태동'으로 나왔다(09-28: 태동 53개 중 50개가 문서 있음)
    if community and not short and not news and not documented:
        return "underground"
    return None


# ── 관심도로 정하기 (2026-10-06) ──────────────────────────────────────
# 위키 밈 분류로 들어온 말은 뉴스·쇼츠·검색어 원본에 거의 나오지 않아 대부분 '판단 보류' 였다(verified 의 91.7%).
# 원본에 언급이 없고 조사 근거로도 정하지 못했을 때만, 그 말의 검색 관심도(한국어: 네이버 데이터랩 주별)나 위키 문서 조회수(월별)로 정한다.
# 모양은 그 말 자신의 최고점에 대한 비율로만 본다(데이터랩 값은 같이 부른 말끼리 상대값이라 크기는 쓰지 않는다).
INTEREST_MIN_POINTS = 8        # 이보다 짧은 시계열은 보류
INTEREST_RECENT = {"week": 4, "month": 3}      # 최근 창(주 4개 · 달 3개)
INTEREST_FLOOR = {"week": 0.0, "month": 30.0}  # 월 조회수가 이보다 적으면(최고점조차) 신호가 아니다


def interest_stage(series: list[float], unit: str = "week") -> Lifecycle:
    """오래된 → 최근 순의 관심도(주별 비율 또는 월별 조회수). 마지막 칸(아직 덜 찬 주·달)은 부르는 쪽이 뺀다.

    꾸준함: 최근 평균이 최고점의 35% 이상 · 지는 중: 10% 이상 · 잠잠함: 그 아래. 신호가 없으면 보류.
    모양(정점·오르는 중)은 말하지 않는다 — 검색 관심도는 그 낱말 자체의 관심이라 밈과 상관없는 검색에도 뛴다
    ('소갈비찜 레시피'·'산미증식계획' 이 '오르는 중', '시바스 리갈' 이 '정점' 이 됐다, 10-06). recency_stage 와 같은 세 단계만."""
    pts = [max(0.0, float(x)) for x in series]
    if len(pts) < INTEREST_MIN_POINTS or max(pts, default=0) <= INTEREST_FLOOR[unit]:
        return "unknown"
    w = INTEREST_RECENT[unit]
    top = max(pts)
    recent = sum(pts[-w:]) / w
    ratio = recent / top
    if ratio >= 0.35:
        return "steady"
    if ratio >= 0.10:
        return "declining"
    return "dormant"
