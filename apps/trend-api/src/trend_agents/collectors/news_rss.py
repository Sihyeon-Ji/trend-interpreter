"""Google News RSS. API 키 불필요. 국가/언어별 헤드라인과 키워드 검색.

feedparser 에 URL 을 그대로 주면 내부 urllib 이 소켓 기본 타임아웃(None)을 써서 응답이 없으면 무한 대기한다.
2026-09-16 실측: collect.news 가 news.google.com 소켓에 붙어 파이프라인 전체가 멈췄다. 그래서 httpx 로 받아서
feedparser 에는 본문만 넘긴다 — collectors/google_trends.trending_now 과 같은 방식."""
from __future__ import annotations

from email.utils import parsedate_to_datetime
from urllib.parse import quote

import feedparser
import httpx

from ..schemas import NewsItem

TIMEOUT = 15.0  # 로케일 27개를 순회하므로 한 곳이 느리면 전체가 밀린다
UA = "Mozilla/5.0 (compatible; trend-agents/0.1)"
BREAKER_TRIP = 5  # 상류가 죽었을 때(09-16 실측: 전 로케일 503) 한 번의 실행에서 이만큼 연달아 실패하면 나머지는 시도하지 않는다
_fails = 0


class Unavailable(RuntimeError):
    """상류(news.google.com)가 연달아 실패해 이번 실행에서는 더 묻지 않는다. 단계는 이 예외를 note 에 남기고 넘어간다."""


def reset_breaker() -> None:
    global _fails
    _fails = 0

# region -> (hl, gl, ceid)
LOCALES = {
    "KR": ("ko", "KR", "KR:ko"),
    "JP": ("ja", "JP", "JP:ja"),
    "TW": ("zh-TW", "TW", "TW:zh-Hant"),
    "TH": ("th", "TH", "TH:th"),
    "VN": ("vi", "VN", "VN:vi"),
    "ID": ("id", "ID", "ID:id"),
    "SG": ("en-SG", "SG", "SG:en"),
    "HK": ("zh-HK", "HK", "HK:zh-Hant"),
    "PH": ("en-PH", "PH", "PH:en"),
    "MY": ("en-MY", "MY", "MY:en"),
    "IN": ("en-IN", "IN", "IN:en"),
    "AU": ("en-AU", "AU", "AU:en"),
    "US": ("en-US", "US", "US:en"),
    "CA": ("en-CA", "CA", "CA:en"),
    "GB": ("en-GB", "GB", "GB:en"),
    "DE": ("de", "DE", "DE:de"),
    "FR": ("fr", "FR", "FR:fr"),
    "ES": ("es", "ES", "ES:es"),
    "IT": ("it", "IT", "IT:it"),
    "BR": ("pt-BR", "BR", "BR:pt-419"),
    "MX": ("es-419", "MX", "MX:es-419"),
    "AR": ("es-419", "AR", "AR:es-419"),
    "TR": ("tr", "TR", "TR:tr"),
    "SA": ("ar", "SA", "SA:ar"),
    "EG": ("ar", "EG", "EG:ar"),
    "NG": ("en-NG", "NG", "NG:en"),
    "ZA": ("en-ZA", "ZA", "ZA:en"),
}


def _url(region: str, query: str | None) -> str:
    hl, gl, ceid = LOCALES[region]
    base = "https://news.google.com/rss"
    if query:
        return f"{base}/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    return f"{base}?hl={hl}&gl={gl}&ceid={ceid}"


def fetch_news(region: str, query: str | None = None, limit: int = 30, timeout: float = TIMEOUT) -> list[NewsItem]:
    global _fails
    if _fails >= BREAKER_TRIP:
        raise Unavailable(f"news.google.com 연속 실패 {_fails}회 — 이번 실행에서는 건너뜀")
    url = _url(region, query)  # 지역 코드 오류(KeyError)는 상류 실패가 아니다 — try 밖에서 터뜨린다
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=timeout, follow_redirects=True)
        r.raise_for_status()
    except Exception:
        _fails += 1
        raise
    _fails = 0
    feed = feedparser.parse(r.content)
    out: list[NewsItem] = []
    for e in feed.entries[:limit]:
        try:
            pub = parsedate_to_datetime(e.published) if getattr(e, "published", None) else None
        except Exception:
            pub = None
        src = e.source.get("title", "") if hasattr(e, "source") else ""
        out.append(NewsItem(title=e.title, link=e.link, published_at=pub, source=src, region=region, query=query))
    return out
