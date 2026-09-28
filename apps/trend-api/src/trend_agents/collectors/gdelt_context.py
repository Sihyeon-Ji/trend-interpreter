"""GDELT Context 2.0 — 뉴스에서 그 말이 **실제로 쓰인 문장**을 돌려준다. 근거 발췌로 바로 쓸 수 있다.

2026-09-28 실측으로 정한 쓰임새:
  - DOC 2.0 은 이 서버에서 계속 429 (70초를 쉬어도). GEO 2.0 은 404(내려감). 쓰지 않는다.
  - Context 2.0 은 15초 이상 간격 · 최근 72시간이면 된다. "delulu" 로 e!online·boredpanda 등 5건.
  - GDELT 는 밈을 **찾는** 데는 약하다(3시간 2만 건 뉴스 제목에 우리 표제어가 0번). 이미 아는 말의
    '언론까지 번졌나' 를 보는 데 쓴다. 발굴은 커뮤니티 위키가 맡는다.

MCTI(lib/gdelt.ts) 방식을 따른다: 파일 캐시 + 오래된 캐시 폴백, 상류가 막혀도 조용히 빈 결과.
요청 간격은 프로세스를 넘어 지키도록 파일에 마지막 시각을 남긴다(cron 과 API 가 같이 부를 수 있다).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from ..schemas import Evidence
from ..storage import dictionary_store as ds
from .namuwiki import around

URL = "https://api.gdeltproject.org/api/v2/context/context"
MIN_GAP_S = 16.0
CACHE = Path("data/cache/gdelt_context.json")
STAMP = Path("data/cache/gdelt_context.last")
CACHE_TTL_S = 12 * 3600


def _pace() -> None:
    """프로세스를 넘어 간격을 지킨다. 잠금 없이 읽고 쓰면 cron 과 API 가 동시에 불렀을 때 간격이 깨진다."""
    import fcntl

    STAMP.parent.mkdir(parents=True, exist_ok=True)
    with open(STAMP, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)          # 다른 프로세스는 여기서 기다린다
        f.seek(0)
        try:
            last = float(f.read().strip() or 0)
        except ValueError:
            last = 0.0
        wait = MIN_GAP_S - (time.time() - last)
        if wait > 0:
            time.sleep(wait)
        f.seek(0)
        f.truncate()
        f.write(str(time.time()))


def sentences(term: str, limit: int = 6) -> list[Evidence]:
    """최근 72시간 뉴스에서 그 말이 들어간 문장들. 용어가 실제로 있는 문장만 남긴다."""
    from ..pipeline.match import mentions

    term = term.strip()
    if len(term) < 3:
        return []
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    hit = cache.get(term)
    if not hit or time.time() - hit.get("at", 0) > CACHE_TTL_S:
        _pace()
        q = f'"{term}"' if " " in term else term
        try:
            r = httpx.get(URL, params={"query": q, "mode": "artlist", "maxrecords": 20, "timespan": "72h", "format": "json"},
                          timeout=40)
            arts = r.json().get("articles", []) if r.status_code == 200 and r.text.strip().startswith("{") else None
        except Exception:
            arts = None
        if arts is None:                     # 막혔다 — 오래된 캐시가 있으면 그걸 쓴다
            arts = (hit or {}).get("arts", [])
        hit = {"at": time.time(), "arts": arts}
        cache[term] = hit
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    out, seen = [], set()
    for a in hit.get("arts", []):
        ctx, dom = (a.get("context") or "").strip(), a.get("domain") or ""
        if not ctx or dom in seen or not mentions(ctx, term):
            continue
        seen.add(dom)
        try:
            when = datetime.strptime(a.get("seendate", "")[:15], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except ValueError:
            when = datetime.now(timezone.utc)
        out.append(Evidence(evidence_id=ds.new_id("e", f"{a.get('url')}|{term}"), kind="news", url=a.get("url", ""),
                            title=(a.get("title") or dom)[:200], source_domain=dom, observed_at=when, excerpt=around(ctx, term)))
        if len(out) >= limit:
            break
    return out
