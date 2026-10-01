"""위키백과(태국어·인도네시아어…) 분류 나무 — 공식 MediaWiki API 로만. 제목과 걸린 분류만 받는다(본문은 저장하지 않는다).

요청 사이 1초 이상, 429·5xx 는 Retry-After(없으면 30초)만큼 기다렸다 최대 5번 다시. 첫머리는 뜻을 쓸 때 메모리에서만 쓴다(CC BY-SA).
"""
from __future__ import annotations

import time

import httpx

from ..config import BOT_UA as UA  # noqa: E402
MIN_GAP_S = 1.0
RETRIES = 5
_last = 0.0

# 출처별 위키 언어·뿌리 분류·지역. 태국어는 인터넷 속어 분류도(2026-10-01 API 확인), 인도네시아어는 연도별 하위 분류가 밈 분류 아래에 있다.
SOURCES = {
    "wiki-th": {"lang": "th", "roots": ["หมวดหมู่:อินเทอร์เน็ตมีม", "หมวดหมู่:สแลงอินเทอร์เน็ต"], "region": "TH", "name": "Wikipedia (th)"},
    "wiki-id": {"lang": "id", "roots": ["Kategori:Meme internet"], "region": "ID", "name": "Wikipedia (id)"},
    # 과거 밈을 쌓는다(10-01 사용자 요청) — 연도 분류('Internet memes introduced in 20XX' 등)가 뜬 해를 준다. 지역을 한 나라로 정할 수 없는 판은 region 을 비운다.
    "wiki-en": {"lang": "en", "roots": ["Category:Internet memes", "Category:Internet slang"], "region": "", "name": "Wikipedia (en)"},
    "wiki-ja": {"lang": "ja", "roots": ["Category:インターネット・ミーム", "Category:インターネットスラング"], "region": "JP", "name": "Wikipedia (ja)"},
    "wiki-zh": {"lang": "zh", "roots": ["Category:网络迷因", "Category:网络流行语"], "region": "", "name": "Wikipedia (zh)"},
    "wiki-ko": {"lang": "ko", "roots": ["분류:인터넷 밈", "분류:인터넷 속어"], "region": "KR", "name": "Wikipedia (ko)"},
    "wiki-vi": {"lang": "vi", "roots": ["Thể loại:Meme Internet", "Thể loại:Hiện tượng Internet"], "region": "VN", "name": "Wikipedia (vi)"},
}


def _api(lang: str, params: dict) -> dict | None:
    global _last
    for _ in range(RETRIES):
        wait = MIN_GAP_S - (time.time() - _last)
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            r = httpx.get(f"https://{lang}.wikipedia.org/w/api.php", params={**params, "format": "json"},
                          headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
        except httpx.HTTPError:
            time.sleep(5)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            ra = r.headers.get("Retry-After", "")
            time.sleep(int(ra) if ra.isdigit() else 30)
            continue
        try:
            return r.json() if r.status_code == 200 else None
        except ValueError:
            return None
    return None


def _members(lang: str, category: str) -> tuple[list[str], list[str]]:
    """(문서 제목들, 하위 분류 제목들). continue 를 끝까지 따라간다."""
    docs, subs, cont = [], [], {}
    while True:
        j = _api(lang, {"action": "query", "list": "categorymembers", "cmtitle": category, "cmnamespace": "0|14", "cmlimit": 500, **cont})
        if not j:
            break
        for m in j.get("query", {}).get("categorymembers", []):
            (subs if m["ns"] == 14 else docs).append(m["title"])
        if "continue" not in j:
            break
        cont = j["continue"]
    return docs, subs


def tree(lang: str, root: str, depth: int = 2, skip=lambda name: False) -> dict[str, list[str]]:
    """{문서 제목: [걸린 분류들]} — root 와 그 아래 depth 단계 하위 분류. 분류 이름은 접두어('หมวดหมู่:')를 뗀다.
    skip(분류 이름) 이 참이면 그 아래로는 내려가지 않는다(그 분류의 문서는 기록한다)."""
    out: dict[str, set[str]] = {}
    seen: set[str] = set()
    level = [root]
    for d in range(depth + 1):
        nxt = []
        for cat in level:
            if cat in seen:
                continue
            seen.add(cat)
            docs, subs = _members(lang, cat)
            name = cat.split(":", 1)[-1]
            for t in docs:
                out.setdefault(t, set()).add(name)
            if d < depth and not skip(name):
                nxt += subs
        level = nxt
    return {k: sorted(v) for k, v in out.items()}


def intro(lang: str, title: str) -> str:
    """문서 첫머리 1200자 — 메모리에서만 쓴다."""
    from .wikipedia_search import article_text
    return article_text(lang, title)[:1200]


def evidence(source: str, title: str, text: str):
    from datetime import datetime, timezone
    from urllib.parse import quote

    from ..schemas import Evidence
    lang = SOURCES[source]["lang"]
    return Evidence(evidence_id=f"e_{source}_{abs(hash(title)) % 10**12}", kind="wiki",
                    url=f"https://{lang}.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                    title=f"{SOURCES[source]['name']}: {title} (CC BY-SA)"[:200], source_domain=f"{lang}.wikipedia.org",
                    observed_at=datetime.now(timezone.utc), excerpt=text[:200])
