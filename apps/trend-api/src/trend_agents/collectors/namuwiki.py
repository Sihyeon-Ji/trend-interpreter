"""나무위키 — 한국어 유행어·밈의 사실상 표준 문서. 2026-09-28 실측: 우리 한국어 표제어 14개 중 13개에 문서가 있고,
문서마다 기계가 읽는 최근 수정 시각이 있다(절반이 최근 2주 안에 고쳐짐).

쓰는 것은 세 가지뿐이다.
  lookup(term)  그 말이 **유행어 단서와 함께** 나오는 문장 하나 + 문서 제목(넘겨주기 결과) + 최근 수정 시각 → 근거
  ranking()     실시간 검색어 열 개 → 발굴 신호 (한국에서 지금 몰리는 것)
  category()    분류 문서의 항목 이름들 → 후보 씨앗

**본문을 옮겨 저장하지 않는다.** 나무위키는 CC BY-NC-SA 2.0 KR 이다. 짧은 발췌·링크·시각만 근거로 두고,
뜻은 여러 출처를 보고 research 가 새로 쓴다(위키백과를 쓰는 방식과 같다).
robots.txt 는 문서(/w/)를 허용한다. 요청 사이 최소 간격을 지키고, 결과는 하루 캐시한다.
"""
from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, unquote

import httpx

from ..schemas import Evidence
from ..storage import dictionary_store as ds

UA = "trend-agents/0.1 (AI Builder Cup 2026 prototype; research)"
BASE = "https://namu.wiki"
MIN_GAP_S = 2.0
CACHE = Path("data/cache/namuwiki.json")
CACHE_TTL_S = 24 * 3600
# 넘겨받은 문서가 그 유행어를 다루는지 보는 단서. '샤갈' → '마르크 샤갈'(화가) 같은 오인을 막는다.
SLANG_CUE = re.compile(r"유행어|신조어|줄임말|은어|인터넷\s*밈|밈|드립|커뮤니티|숏폼|틱톡|챌린지|유행한|유행하")
# 화면 테두리(메뉴·편집 링크·목차)에 나오는 말. 이런 게 섞인 문장은 본문이 아니다.
CHROME = re.compile(r"(?:[^·]*·){4}|문서를 참고하십시오|나무위키|최근 변경|최근 토론|특수 기능|최근 수정 시각|편집 토론|\[편집\]|둘러보기|분류:|\xa0\s*\xa0")
_last = 0.0


def around(text: str, term: str, width: int = 110) -> str:
    """그 말을 가운데 두고 자른다. 앞에서부터 자르면 정작 그 말이 잘려 나간다."""
    at = text.lower().find(term.lower())
    if at < 0 or len(text) <= width * 2:
        return text[: width * 2]
    a, b = max(0, at - width), min(len(text), at + len(term) + width)
    return ("…" if a else "") + text[a:b] + ("…" if b < len(text) else "")


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


def _text(page: str) -> str:
    page = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", page)))


def lookup(term: str) -> list[Evidence] | None:
    """그 말이 유행어 단서와 함께 나오는 문장이 있으면 근거 한 건. 없다고 확인되면(문서가 없거나 그런 문장이 없음) 빈 목록,
    닿지 못했으면(막힘·429·서버 오류·네트워크) None — '문서 없음' 과 가른다(Plan 12 검토). 닿지 못한 결과는 캐시하지 않는다
    (하루 동안 '문서 없음' 으로 남지 않게)."""
    from ..pipeline.match import mentions

    term = term.strip()
    if not term:
        return []
    cache = _load()
    hit = cache.get(term)
    if not hit or time.time() - hit.get("at", 0) > CACHE_TTL_S:
        r = _get("/w/" + quote(term))
        if r is None or r.status_code not in (200, 404, 410):
            return None
        hit = {"at": time.time(), "ok": False}
        if r.status_code == 200:
            page = r.text
            title = unquote(str(r.url).split("/w/", 1)[-1].split("?")[0])
            mod = re.search(r"(20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d)", page)
            sentence = ""
            body = _text(page)
            cut = body.find("최근 수정 시각")          # 본문은 수정 시각 표시 뒤에서 시작한다
            body = body[cut + 40:] if cut >= 0 else body
            # 문서 제목이 그 말이면 문서 전체가 그 유행어 이야기다. 다른 문서로 넘어갔을 때만 유행어 단서를 요구한다
            # ('샤갈' → '마르크 샤갈' 같은 오인 방지).
            own = title.replace(" ", "") == term.replace(" ", "")
            for s in re.split(r"(?<=[.!?다요])\s+", body):
                if 10 <= len(s) <= 400 and not CHROME.search(s) and mentions(s, term) and (own or SLANG_CUE.search(s)):
                    sentence = s.strip()
                    break
            hit = {"at": time.time(), "ok": bool(sentence), "title": title, "url": str(r.url).split("?")[0],
                   "modified": mod.group(1) if mod else "", "sentence": sentence}
        cache[term] = hit
        _save(cache)
    if not hit.get("ok"):
        return []
    when = datetime.fromisoformat(hit["modified"]).replace(tzinfo=timezone.utc) if hit.get("modified") else datetime.now(timezone.utc)
    return [Evidence(evidence_id=ds.new_id("e", f"{hit['url']}|{term}"), kind="wiki", url=hit["url"],
                     title=f"나무위키: {hit['title']} (CC BY-NC-SA 2.0 KR)"[:200], source_domain="namu.wiki", observed_at=when,
                     excerpt=around(hit["sentence"], term))]


def page_text(title: str) -> str | None:
    """문서 한 쪽의 본문 평문 — 전수조사가 준 발췌가 그 문서에 실제로 있는지 볼 때만 그 자리에서 쓴다. **저장하지도 캐시하지도 않는다.**
    문서가 없으면 빈 문자열, 닿지 못했으면 None."""
    r = _get("/w/" + quote(title.strip()))
    if r is None or r.status_code not in (200, 404, 410):
        return None
    if r.status_code != 200:
        return ""
    body = _text(r.text)
    cut = body.find("최근 수정 시각")
    return body[cut + 40:] if cut >= 0 else body


def category_page(name: str, pages: int = 20) -> tuple[list[str], list[str]]:
    """분류 문서 하나의 (문서 이름들, 하위 분류 이름들). 분류 이름은 '분류:' 를 뗀다. 제목만 읽고 본문은 두지 않는다."""
    docs: set[str] = set()
    subs: set[str] = set()
    path = "/w/" + quote(f"분류:{name}")
    seen: set[str] = set()
    for _ in range(max(1, pages)):
        r = _get(path)
        if r is None or r.status_code != 200:
            break
        for x in re.findall(r'href="/w/([^"#?]+)"', r.text):
            n = unquote(x)
            if n.startswith("분류:"):
                subs.add(n[3:])
            elif not n.startswith(("나무위키:", "틀:", "파일:", "사용자:", "휴지통:")):
                docs.add(n)
        nxt = re.search(r'href="(/w/[^"]*\?[^"]*namespace=%EB%AC%B8%EC%84%9C[^"]*cfrom=[^"]+)"', r.text)
        if not nxt or html.unescape(nxt.group(1)) in seen:
            break
        path = html.unescape(nxt.group(1))
        seen.add(path)
    subs.discard(name)
    return sorted(docs), sorted(subs)


def category_tree(roots: tuple[str, ...], follow, depth: int = 3) -> dict[str, list[str]]:
    """분류 나무를 따라가며 {문서 이름: [걸린 분류들]}. follow(분류 이름) 가 참인 하위 분류만 내려간다(위 분류·옆 분류로 새지 않게)."""
    out: dict[str, set[str]] = {}
    todo = [(r, 0) for r in roots]
    done: set[str] = set()
    while todo:
        cat, d = todo.pop(0)
        if cat in done:
            continue
        done.add(cat)
        docs, subs = category_page(cat)
        for doc in docs:
            out.setdefault(doc, set()).add(cat)
        if d < depth:
            todo += [(s, d + 1) for s in subs if s not in done and follow(s)]
    return {k: sorted(v) for k, v in out.items()}


def ranking() -> list[str]:
    """실시간 검색어. 공식 문서화된 API 는 아니라 실패하면 빈 목록."""
    try:
        r = httpx.get("https://search.namu.wiki/api/ranking", headers={"User-Agent": UA}, timeout=10)
        data = r.json() if r.status_code == 200 else []
        return [str(x) for x in data if isinstance(x, str)][:20]
    except Exception:
        return []


def category(name: str = "유행어", pages: int = 1) -> list[str]:
    """분류 문서에 걸린 항목 이름들. 분류 쪽은 100개씩 끊겨 '다음' 링크(cfrom)로 이어진다 — pages 만큼 따라간다
    (09-30 실측: 첫 쪽만 읽어 분류:유행어 700여 개 가운데 97개만 들어왔다)."""
    names: set[str] = set()
    path = "/w/" + quote(f"분류:{name}")
    seen: set[str] = set()
    for _ in range(max(1, pages)):
        r = _get(path)
        if r is None or r.status_code != 200:
            break
        names |= {unquote(x) for x in re.findall(r'href="/w/([^"#?]+)"', r.text)}
        nxt = re.search(r'href="(/w/[^"]*\?[^"]*namespace=%EB%AC%B8%EC%84%9C[^"]*cfrom=[^"]+)"', r.text)
        if not nxt:
            break
        path = html.unescape(nxt.group(1))
        if path in seen:
            break
        seen.add(path)
    return sorted(n for n in names if not n.startswith(("분류:", "나무위키:", "틀:", "파일:")))
