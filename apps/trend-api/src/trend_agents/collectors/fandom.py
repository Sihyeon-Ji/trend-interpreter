"""Fandom 위키의 밈 사전 — 공식 MediaWiki API 로만(화면은 이 서버 요청을 403 으로 막는다, API 는 열려 있다. 2026-09-30 실측).

- PTT鄉民百科(대만): 분류 PTT流行用語 487개 + 연도별 流行用語(2012~2018)
- 香港網絡大典(홍콩): 분류 潮語 37개, 2020年代潮語

문서 글은 CC BY-SA 다. 분류 구성원(제목)은 저장하고, 문서 첫머리는 뜻을 쓸 때 **메모리에서만** 쓴다. 근거로는 짧은 발췌·링크만 남긴다.
"""
from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from ..schemas import Evidence

UA = "trend-agents/0.1 (AI Builder Cup 2026 prototype; research)"
MIN_GAP_S = 1.0
_last = 0.0

SITES = {
    "pttpedia": {"api": "https://pttpedia.fandom.com/zh/api.php", "page": "https://pttpedia.fandom.com/zh/wiki/{}", "name": "PTT鄉民百科",
                 "domain": "pttpedia.fandom.com", "region": "TW", "categories": ["PTT流行用語", "PTT基本用語", "流行用語"]},
    "evchk": {"api": "https://evchk.fandom.com/zh/api.php", "page": "https://evchk.fandom.com/zh/wiki/{}", "name": "香港網絡大典",
              "domain": "evchk.fandom.com", "region": "HK", "categories": ["潮語", "2020年代潮語"]},
}


def _api(site: str, params: dict) -> dict | None:
    global _last
    wait = MIN_GAP_S - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    try:
        r = httpx.get(SITES[site]["api"], params={**params, "format": "json"}, headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
        return r.json() if r.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def members(site: str, category: str) -> list[str]:
    """분류 구성원 제목(문서 이름공간만). 하위 분류는 이름을 따로 돌려주지 않는다 — 연도별 분류는 SITES 의 목록과 subcats 로."""
    out, cont = [], {}
    while True:
        j = _api(site, {"action": "query", "list": "categorymembers", "cmtitle": f"Category:{category}", "cmnamespace": 0, "cmlimit": 500, **cont})
        if not j:
            break
        out += [m["title"] for m in j.get("query", {}).get("categorymembers", [])]
        if "continue" not in j:
            break
        cont = j["continue"]
    return out


def subcategories(site: str, category: str) -> list[str]:
    j = _api(site, {"action": "query", "list": "categorymembers", "cmtitle": f"Category:{category}", "cmtype": "subcat", "cmlimit": 500}) or {}
    return [m["title"].split(":", 1)[1] for m in j.get("query", {}).get("categorymembers", [])]


def tree(site: str) -> dict[str, list[str]]:
    """{문서 제목: [걸린 분류]} — SITES 의 분류와 그 바로 아래 분류(연도별 流行用語 등)."""
    out: dict[str, set[str]] = {}
    cats = list(SITES[site]["categories"])
    for c in list(cats):
        cats += [s for s in subcategories(site, c) if s not in cats]
    for c in cats:
        for t in members(site, c):
            out.setdefault(t, set()).add(c)
    return {k: sorted(v) for k, v in out.items()}


def intro(site: str, title: str, limit: int = 900) -> str:
    """문서 첫 절의 평문 — 메모리에서만 쓴다. 닿지 못하면 빈 문자열."""
    j = _api(site, {"action": "parse", "page": title, "prop": "text", "section": 0, "redirects": 1}) or {}
    raw = j.get("parse", {}).get("text", {}).get("*", "")
    raw = re.sub(r"(?is)<(script|style|table|aside)[^>]*>.*?</\1>", " ", raw)
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    text = re.sub(r"\[\d+\]|\[編輯\]|\[编辑\]", "", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def evidence(site: str, title: str, text: str) -> Evidence:
    s = SITES[site]
    return Evidence(evidence_id=f"e_{site}_{abs(hash(title)) % 10**12}", kind="wiki", url=s["page"].format(quote(title.replace(" ", "_"))),
                    title=f"{s['name']}: {title} (CC BY-SA)"[:200], source_domain=s["domain"], observed_at=datetime.now(timezone.utc),
                    excerpt=text[:200])
