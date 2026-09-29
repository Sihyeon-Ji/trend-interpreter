"""Know Your Meme — 영어권·일본 밈의 참고 문서(ADR 0003, Plan 12). 2026-09-29 실측: 문서(/memes/<slug>)는 이 서버에서 200 으로 열리고,
'About' 절이 그 밈이 무엇인지 적는다. 없는 문서는 404 'Page Not Found'.

**기본은 꺼져 있다(config.KNOWYOURMEME_ENABLED).** 이용 약관(운영사 Cheezburger)은 자동 접근을 사람 수준의 요청 속도로만 허락하고,
내용은 개인적 정보 이용만 되며 사전 서면 동의 없이 내려받기·복제·배포·게시할 수 없고, 서면 허락 없는 상업적 이용을 금한다.
제품에 쓸지는 사용자가 정한다. 꺼져 있으면 lookup 은 요청을 하나도 보내지 않는다.

켜도 흔적을 최소로 둔다.
  lookup(term, aliases)  표제어·로마자 별칭으로 만든 문서 주소를 최대 세 번 열어, 제목과 'About' 절에 그 말이 있으면
                         **문서 주소와 제목만** 근거(wiki)로 돌려준다. 받은 글은 그 자리에서 mentions() 확인에만 쓰고 저장하지 않는다.
- 문서 주소만 연다. robots.txt 가 /search 를 막으므로 검색하지 않는다.
- 요청 사이 2초 넘게 쉬고, 정직한 User-Agent 를 쓴다. 하루 캐시에는 찾았나·못 찾았나(주소·제목)만 둔다 — 본문은 두지 않는다.
"""
from __future__ import annotations

import html
import json
import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .. import config
from ..schemas import Evidence
from ..storage import dictionary_store as ds

UA = "trend-agents/0.1 (AI Builder Cup 2026 prototype; research)"
BASE = "https://knowyourmeme.com"
MIN_GAP_S = 2.0
MAX_FETCHES = 3
CACHE = Path("data/cache/knowyourmeme.json")
CACHE_TTL_S = 24 * 3600
_last = 0.0


def enabled() -> bool:
    """켜져 있나(KNOWYOURMEME_ENABLED). 부를 때마다 읽는다 — 부르는 쪽(조사·문서 대조·스크립트)이 먼저 확인한다."""
    return config.KNOWYOURMEME_ENABLED


def _fold(name: str) -> str:
    """악센트를 떼고 소문자로 (Pokémon → pokemon)."""
    return "".join(ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch)).lower()


def latin(name: str) -> bool:
    """로마자로 쓴 이름인가 — 글자가 모두 라틴 문자이고 글자·숫자가 하나 이상. 한글·가나·한자 표기로는 문서 주소를 만들 수 없다."""
    s = _fold(name or "")
    return bool(re.search(r"[a-z0-9]", s)) and all(ch.isascii() for ch in s if ch.isalpha())


def slug(name: str) -> str:
    """문서 주소의 끝 — 소문자, 띄어쓰기·기호는 '-'. 따옴표는 뺀다(Know Your Meme 주소 관례: Ain't → aint). 로마자가 아니면 빈 문자열."""
    if not latin(name):
        return ""
    s = re.sub(r"['’]", "", _fold(name))
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _get(path: str, timeout: float = 15.0) -> httpx.Response | None:
    global _last
    wait = MIN_GAP_S - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    try:
        return httpx.get(BASE + path, headers={"User-Agent": UA}, timeout=timeout, follow_redirects=True)
    except httpx.HTTPError:
        return None


def _load() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(c: dict) -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")


def _plain(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<sup[^>]*>.*?</sup>", "", fragment, flags=re.S | re.I)      # 각주 번호 [1]
    fragment = re.sub(r"</?(?:a|b|i|em|strong|span|abbr|small)\b[^>]*>", "", fragment, flags=re.I)   # 글줄 안의 태그는 붙여서 ('"aura"')
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def title_of(page: str) -> str:
    """문서 제목. 본문 머리(h1.entry-title)가 먼저, 없으면 og:title·<title> 에서 사이트 이름을 뗀다."""
    m = (re.search(r"<h1[^>]*class=['\"][^'\"]*entry-title[^'\"]*['\"][^>]*>(.*?)</h1>", page, re.S | re.I)
         or re.search(r"<meta\s+property=['\"]og:title['\"]\s+content=['\"]([^'\"]*)['\"]", page, re.I)
         or re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I))
    return re.sub(r"\s*[|-]\s*Know Your Meme\s*$", "", _plain(m.group(1)) if m else "").strip()


def about_of(page: str) -> str:
    """'About' 절의 평문 — 다음 소제목(Origin 등) 앞까지. 그 자리에서 확인에만 쓰고 저장하지 않는다."""
    m = re.search(r"<h2[^>]*id=['\"]about['\"][^>]*>.*?</h2>(.*?)(?=<h2\b|</section>)", page, re.S | re.I)
    return _plain(m.group(1)) if m else ""


def not_found(page: str) -> bool:
    return "page not found" in title_of(page).lower()


def covers(page: str, term: str, aliases: list[str] | tuple[str, ...] = ()) -> bool:
    """그 문서가 이 말을 다루나 — 제목과 'About' 절 둘 다에 표제어(또는 별칭)가 있어야 한다(match.mentions).
    저장하는 것은 제목뿐이라 제목에 그 말이 있어야 근거가 앵커되고, 'About' 에도 있어야 제목만 같은 딴 문서가 아니다."""
    from ..pipeline.match import mentions

    return mentions(title_of(page), term, aliases) and mentions(about_of(page), term, aliases)


def lookup(term: str, aliases: list[str] | tuple[str, ...] = ()) -> list[Evidence]:
    """꺼져 있으면 요청 없이 빈 목록. 켜져 있으면 표제어·로마자 별칭으로 만든 문서 주소를 차례로(최대 세 번) 열어,
    그 말을 다루는 문서가 있으면 **주소와 제목만** 근거 한 건으로(발췌 없음). 네트워크 실패는 캐시하지 않는다(하루 동안 '없음' 으로 남지 않게)."""
    if not enabled():
        return []
    term = (term or "").strip()
    names = [n.strip() for n in dict.fromkeys([term, *aliases]) if n and n.strip()]
    slugs = list(dict.fromkeys(s for s in (slug(n) for n in names) if s))[:MAX_FETCHES]
    if not term or not slugs:
        return []
    rest = [n for n in names if n != term]
    key = "|".join([term, *sorted(rest)])
    cache = _load()
    hit = cache.get(key)
    if not hit or time.time() - hit.get("at", 0) > CACHE_TTL_S:
        hit, definite = {"at": time.time(), "ok": False}, True
        for s in slugs:
            r = _get(f"/memes/{s}")
            if r is None or r.status_code not in (200, 404, 410):
                definite = False                     # 막혔거나 서버 오류 — 다음에 다시 본다
                continue
            final = str(r.url).split("#")[0].split("?")[0]
            u = urlsplit(final)
            if r.status_code != 200 or not ((u.hostname or "").endswith("knowyourmeme.com") and u.path.startswith("/memes/")) or not_found(r.text):
                continue
            if covers(r.text, term, rest):
                hit = {"at": time.time(), "ok": True, "url": final, "title": title_of(r.text)}
                break
        if hit["ok"] or definite:
            cache[key] = hit
            _save(cache)
    if not hit.get("ok"):
        return []
    return [Evidence(evidence_id=ds.new_id("e", f"{hit['url']}|{term}"), kind="wiki", url=hit["url"],
                     title=f"Know Your Meme: {hit['title']}"[:200], source_domain="knowyourmeme.com",
                     observed_at=datetime.fromtimestamp(hit["at"], timezone.utc))]
