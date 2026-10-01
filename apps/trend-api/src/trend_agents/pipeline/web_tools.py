"""에이전트가 쓰는 웹 도구 (2026-10-01). 콘텐츠 조사 에이전트·사전에 묻기·MCP 서버가 같은 함수를 쓴다.

지키는 것
- 허용한 곳만 연다: 나무위키 /w/, 위키백과 /wiki/, Know Your Meme /memes/, Fandom /wiki/, Trend A Word 게시글. 막은 곳(니코니코·pixiv 등)은 열지 않는다.
- 사이트마다 요청 간격(나무위키 3초는 수집기가 지킨다), 정직한 User-Agent.
- 본문은 저장하지 않는다. 돌려주는 것은 그 자리에서 쓰는 글 조각·제목·절 이름·링크뿐이다(에이전트가 근거로 남기는 것은 문장 하나와 주소).
"""
from __future__ import annotations

import html
import re
import time
import unicodedata
from urllib.parse import quote, unquote, urljoin, urlsplit

import httpx

from ..config import BOT_UA as UA  # noqa: E402
CHUNK = 2500
MAX_LINKS = 40
_last: dict[str, float] = {}
_cache: dict[str, tuple[str, str, list[tuple[str, str]]]] = {}     # 한 실행 안에서만(같은 문서를 다시 받지 않게) — 저장하지 않는다
GAP = {"wikipedia.org": 1.0, "knowyourmeme.com": 2.0, "fandom.com": 1.0, "maily.so": 3.0}


def canon(url: str) -> str:
    """주소를 사람이 읽는 꼴로 맞춘다(퍼센트 인코딩을 푼다) — 모델이 긴 인코딩 주소를 베끼다 틀리는 일이 잦았다."""
    u = urlsplit(url.strip())
    return f"{u.scheme}://{u.netloc}{unquote(u.path)}" + (f"?{u.query}" if u.query else "")


def allowed(url: str) -> bool:
    u = urlsplit(url)
    h, p = (u.hostname or "").lower(), u.path
    return ((h == "namu.wiki" and p.startswith("/w/")) or (h.endswith(".wikipedia.org") and p.startswith("/wiki/"))
            or (h.endswith("knowyourmeme.com") and p.startswith("/memes/")) or (h.endswith(".fandom.com") and "/wiki/" in p)
            or (h == "maily.so" and p.startswith("/trendaword/posts/")))


def _wait(host: str) -> None:
    key = next((k for k in GAP if host.endswith(k)), host)
    gap = GAP.get(key, 1.0) - (time.time() - _last.get(key, 0))
    if gap > 0:
        time.sleep(gap)
    _last[key] = time.time()


def _fetch(url: str) -> str | None:
    if re.search(r"[\x00-\x1f\x7f]", url):                   # 모델이 깨진 글자를 넣은 주소(실측 '\x11')
        return None
    u = urlsplit(url)
    url = f"{u.scheme}://{u.netloc}{quote(u.path, safe="/%:@!$&'()*+,;=-._~")}" + (f"?{u.query}" if u.query else "")
    host = (u.hostname or "").lower()
    if host == "namu.wiki":
        from ..collectors import namuwiki

        r = namuwiki._get(urlsplit(url).path + (("?" + urlsplit(url).query) if urlsplit(url).query else ""))
        return r.text if r is not None and r.status_code == 200 else None
    if host.endswith(".wikipedia.org"):                       # REST 의 HTML(api.php 보다 요청 제한이 덜하다)
        title = unquote(urlsplit(url).path[len("/wiki/"):])
        url = f"https://{host}/api/rest_v1/page/html/{quote(title.replace(' ', '_'), safe='')}"
    for _ in range(3):
        _wait(host)
        try:
            r = httpx.get(url, headers={"User-Agent": UA}, timeout=25, follow_redirects=True)
        except httpx.HTTPError:
            return None
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(int(r.headers.get("Retry-After", "20")) if r.headers.get("Retry-After", "").isdigit() else 20)
            continue
        return r.text if r.status_code == 200 else None
    return None


def _parse(url: str, page: str) -> tuple[str, str, list[tuple[str, str]]]:
    """(제목, 평문, [(링크 글, 주소)]) — 허용한 곳의 링크만."""
    t = re.search(r"<title>([^<]+)</title>", page)
    title = html.unescape(t.group(1)).split(" - ")[0].strip() if t else unquote(urlsplit(url).path.rsplit("/", 1)[-1])
    links: list[tuple[str, str]] = []
    for m in re.finditer(r"""<a\s[^>]*?href=(["'])([^"'#]+)\1[^>]*>(.*?)</a>""", page, re.S):     # 나무위키 본문 링크는 작은따옴표다
        raw = html.unescape(m.group(2))
        href = urljoin(url, raw)
        if "wikipedia.org" in url and raw.startswith("./"):
            href = f"https://{urlsplit(url).hostname}/wiki/{raw[2:]}"
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(3)))).strip()
        if text and allowed(href) and href.split("#")[0] != url and not re.search(r"/w/(분류|틀|파일|나무위키|사용자):", unquote(href)):
            href = canon(href)
            if (text, href) not in links:
                links.append((text[:60], href))
    body = re.sub(r"(?is)<(script|style|noscript|table)[^>]*>.*?</\1>", " ", page)
    # 위키백과 절 제목을 나무위키처럼 '§ 제목' 줄로 남긴다(절 찾기·목록에 쓴다)
    if "namu.wiki" not in url:
        body = re.sub(r"(?is)<h([23])[^>]*>(.*?)</h\1>", lambda m: "\n§ " + re.sub(r"<[^>]+>", "", m.group(2)).strip() + "\n", body)
    body = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h[1-6])>", "\n", body)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r"[ \t\xa0]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()
    if "namu.wiki" in url:                                   # 나무위키 머리말·목차를 건너뛴다
        i = text.find("1. 개요")
        text = text[i:] if i >= 0 else text
    return title, text, links


def open_page(url: str, section: str = "", offset: int = 0) -> dict:
    """문서 한 쪽을 연다. section 을 주면 그 절(제목에 그 글이 든 첫 절)부터, offset 은 이어 읽기.
    돌려주는 것: {url, title, headings(절 이름들), text(최대 2,500자), next_offset, links[(글, 주소)] 최대 40} 또는 {error}."""
    url = canon(url)
    if not url.startswith("http"):
        return {"error": "주소는 http(s) 로 시작해야 한다"}
    if not allowed(url):
        return {"error": "허용하지 않은 곳이다(나무위키·위키백과·Know Your Meme·Fandom·Trend A Word 만)"}
    if url not in _cache:
        page = _fetch(url)
        if page is None:
            return {"error": "문서에 닿지 못했거나 없다"}
        _cache[url] = _parse(url, page)
    title, text, links = _cache[url]
    headings = (re.findall(r"(?m)^\s*(\d+(?:\.\d+)*\.\s[^\n\[]{1,40})\s*\[편집\]", text) if "namu.wiki" in url
                else re.findall(r"(?m)^§ ([^\n]{1,60})$", text))[:40]
    start = 0
    if section:                                              # 절 제목에서 먼저 찾는다 — 본문 첫 '밈' 은 개요에 있다
        m = _heading(text, section)
        i = m.start() if m else text.find(section)
        if i < 0:
            return {"error": f"'{section}' 절이 없다 — 절 목록: " + ", ".join(headings[:30])}
        start = i
    start += max(0, offset)
    chunk = text[start:start + CHUNK]
    nxt = start + CHUNK if start + CHUNK < len(text) else None
    return {"url": url, "title": title, "headings": headings, "text": chunk, "next_offset": (nxt - (start - offset)) if nxt else None,
            # 지금 읽는 조각 안에 나온 링크만 — 문서 머리의 안내 틀(등장인물 목록 등)이 40칸을 채웠다
            "links": [{"text": a, "url": b} for a, b in links if a in chunk][:MAX_LINKS],
            # 나무위키 하위 문서(‘오징어 게임/흥행 및 파급력’ 등) — 본문은 하위 문서에 있는 일이 많다
            "subpages": list({b: {"text": a, "url": b} for a, b in links if "namu.wiki" in url and b.startswith(url + "/")}.values())[:20]}


_HEAD = re.compile(r"(?m)^(?:\s*(\d+(?:\.\d+)*)\.\s[^\n]*\[편집\]|§ [^\n]*)[^\n]*$")


def _heading(text: str, section: str):
    """절 제목 줄 가운데 section 이 든 첫 줄(띄어쓰기 무시 — 나무위키 제목은 '밈 화' 처럼 링크 자리에서 끊긴다)."""
    want = re.sub(r"\s+", "", section)
    return next((m for m in _HEAD.finditer(text) if want and want in re.sub(r"\s+", "", m.group(0))), None)


def section_text(url: str, section: str, limit: int = 10000) -> str:
    """절 하나를 끝까지(다음 같은 깊이 절 제목 전까지, 최대 limit 자). 없으면 ''."""
    url = canon(url)
    if url not in _cache:
        open_page(url)
    text = _cache.get(url, ("", "", []))[1]
    m = _heading(text, section)
    if not m:
        return ""
    rest = text[m.end():]
    if m.group(1):                                           # 나무위키 2.4. → 다음 '2.5.'·'3.' 같은 깊이 이하 제목에서 끊는다
        depth = m.group(1).count(".")
        end = re.search(r"(?m)^\s*\d+(?:\.\d+){0,%d}\.\s[^\n]*\[편집\]" % depth, rest)
    else:
        end = re.search(r"(?m)^§ ", rest)
    return (text[m.start():m.end()] + rest[: end.start() if end else len(rest)])[:limit]


def page_links(url: str) -> list[tuple[str, str]]:
    """이 실행에서 연 문서의 허용된 링크 전부 [(글, 주소)]."""
    url = canon(url)
    if url not in _cache:
        open_page(url)
    return _cache.get(url, ("", "", []))[2]


def page_text(url: str) -> str:
    """검증용 — 이 실행에서 연 문서의 평문(없으면 연다)."""
    url = canon(url)
    if url not in _cache:
        open_page(url)
    return _cache.get(url, ("", "", []))[1]


def search(site: str, query: str, lang: str = "ko") -> dict:
    """site: 'wikipedia'(lang 판) 또는 'namu'. 돌려주는 것: {results:[{title, url}]} 최대 10."""
    q = query.strip()
    if not q:
        return {"error": "검색어가 비었다"}
    site = "namu" if "namu" in site.lower() else "wikipedia"      # 모델이 'namu.wiki'·'wikipedia.org' 로 적는다
    lang = (lang or "ko").lower()[:2]
    if site == "namu":
        page = _fetch(f"https://namu.wiki/w/{quote(q)}")       # 나무위키 검색 결과 쪽은 스크립트로 그려져 읽을 수 없다 — 같은 이름 문서를 바로 연다
        if page is None:
            return {"results": []}
        return {"results": [{"title": q, "url": f"https://namu.wiki/w/{quote(q)}"}]}
    host = f"{lang}.wikipedia.org"
    _wait(host)
    try:
        r = httpx.get(f"https://{host}/w/api.php", params={"action": "query", "list": "search", "srsearch": q, "srlimit": 10, "format": "json"},
                      headers={"User-Agent": UA}, timeout=20)
        hits = r.json().get("query", {}).get("search", []) if r.status_code == 200 and r.text.startswith("{") else []
    except (httpx.HTTPError, ValueError):
        hits = []
    if not hits:                                             # 검색 API 가 막히면(429 잦음) 같은 이름 문서를 REST 로 바로 열어 본다
        u = f"https://{host}/wiki/{q.replace(' ', '_')}"
        return {"results": [{"title": q, "url": u}] if "error" not in open_page(u) else []}
    return {"results": [{"title": h["title"], "url": canon(f"https://{host}/wiki/{h['title'].replace(' ', '_')}")} for h in hits]}


def kym_children(slug: str) -> dict:
    """Know Your Meme 의 한 갈래(subcultures/<slug>) 아래 항목들의 제목·주소. 제목·주소만 쓴다(약관, Plan 12)."""
    slug = slug.strip().strip("/").split("/")[-1]
    out: list[dict] = []
    for page in range(1, 4):
        url = f"https://knowyourmeme.com/memes/subcultures/{slug}/children" + (f"/page/{page}" if page > 1 else "")
        x = _fetch(url)
        if not x:
            break
        before = len(out)
        for m in re.finditer(r'<a class="item"[^>]*>', x):        # 하위 항목 칸만 — 옆의 '인기 검색'·'뉴스' 칸은 다른 밈이다
            s = re.search(r'data-comments-link="(/memes/[^"#]+)', m.group(0))
            t = re.search(r'alt="([^"]*)"', m.group(0))
            u = "https://knowyourmeme.com" + s.group(1) if s else ""
            if u and all(o["url"] != u for o in out):
                out.append({"title": html.unescape(t.group(1)).strip() if t else s.group(1).rsplit("/", 1)[-1], "url": u})
        if len(out) == before:
            break
    return {"results": out[:80]}


def page_title(url: str) -> str:
    if canon(url) not in _cache:
        open_page(url)
    return _cache.get(canon(url), ("", "", []))[0]


def in_series(url: str, name: str) -> bool:
    """Know Your Meme 항목이 그 갈래에 든 것인가 — 'Part of a series on <name>'."""
    m = re.search(r"Part of a series on\s+([^\n]{1,80})", page_text(url))
    # 'Spy × Family' 와 'SPY x FAMILY' 처럼 기호·대소문자가 다르다 — 글자만 맞춘다
    key = lambda x: re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", x).replace("×", "x").lower())
    return bool(m) and bool(key(name)) and key(m.group(1)) == key(name)
