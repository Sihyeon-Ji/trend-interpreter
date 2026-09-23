"""네이버 검색 API (뉴스·카페·블로그·지식iN) — NAVER API HUB.

약관(2026-09-07 개정): 검색 API 결과는 '앱에서 네이버 검색 결과를 보여 주는 용도'로만. → 이 근거들은 **화면에 링크로 보여 주기만** 하고,
모델 프롬프트에 넣지 않으며 검증 게이트의 독립 출처로도 세지 않는다. source_domain 이 "naver:" 로 시작하면 그 규칙이 적용된다.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from ..config import NAVER_API_HUB, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
from ..schemas import Evidence

HUB = "https://naverapihub.apigw.ntruss.com/search/v1"
LEGACY = "https://openapi.naver.com/v1/search"
KIND = {"news": "news", "cafearticle": "community", "blog": "web", "kin": "community"}
DISPLAY_ONLY_PREFIX = "naver:"


def available() -> bool:
    return bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET)


def _strip(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s or ""))


def search(api: str, query: str, display: int = 10, sort: str = "date") -> list[Evidence]:
    """api: news | cafearticle | blog | kin"""
    if not available():
        return []
    from ..storage.dictionary_store import new_id

    if NAVER_API_HUB:
        url, headers = f"{HUB}/{api}", {"X-NCP-APIGW-API-KEY-ID": NAVER_CLIENT_ID, "X-NCP-APIGW-API-KEY": NAVER_CLIENT_SECRET}
    else:
        url, headers = f"{LEGACY}/{api}.json", {"X-Naver-Client-Id": NAVER_CLIENT_ID, "X-Naver-Client-Secret": NAVER_CLIENT_SECRET}
    r = httpx.get(url, params={"query": query, "display": display, "sort": sort}, headers=headers, timeout=15)
    r.raise_for_status()
    out: list[Evidence] = []
    for it in r.json().get("items", []):
        title = _strip(it.get("title", ""))
        desc = _strip(it.get("description", ""))
        link = it.get("originallink") or it.get("link", "")
        when = None
        for key in ("pubDate", "postdate"):
            v = it.get(key)
            if v:
                try:
                    when = parsedate_to_datetime(v) if key == "pubDate" else datetime.strptime(v, "%Y%m%d").replace(tzinfo=timezone.utc)
                except Exception:
                    when = None
        label = {"news": "뉴스", "cafearticle": "카페", "blog": "블로그", "kin": "지식iN"}[api]
        out.append(Evidence(evidence_id=new_id("e", link), kind=KIND[api], url=link, title=f"네이버 {label} · {title}"[:200],  # type: ignore[arg-type]
                            source_domain=f"{DISPLAY_ONLY_PREFIX}{api}", observed_at=when or datetime.now(timezone.utc), excerpt=(desc or title)[:240]))
    return out


def gather(term: str, per_api: int = 5) -> tuple[list[Evidence], list[str]]:
    evs: list[Evidence] = []
    notes: list[str] = []
    for api in ("news", "cafearticle", "kin", "blog"):
        try:
            evs += search(api, term, display=per_api)
        except Exception as e:
            notes.append(f"naver_{api}:{type(e).__name__}")
    return evs, notes


def for_model(evs: list[Evidence]) -> list[Evidence]:
    """모델 프롬프트·게이트에 넣을 수 있는 근거만 (네이버 검색 결과는 표시 전용)."""
    return [e for e in evs if not e.source_domain.startswith(DISPLAY_ONLY_PREFIX)]
