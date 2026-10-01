"""Trend A Word (maily.so/trendaword) — 에디터들이 하루 한 단어씩 뜻·유래·용례를 정리하는 신조어 뉴스레터(2026-09-30 기준 629호).

- 새 호는 공식 RSS(`/trendaword/feed`)로 안다. 지난 호는 목록 쪽(`?page=N`, 10편씩)을 넘긴다. robots.txt 는 게시글을 막지 않는다.
- 게시글 본문은 에디터의 글이다. **본문은 저장하지 않고** 뜻을 쓸 때 메모리에서만 보인다. 근거로는 그 단어가 든 한 문장(200자 안)과 링크·호 날짜만 둔다.
- 사용자 요청(2026-09-30)으로 참고 문서로 센다 — maily.so 전체가 아니라 /trendaword/ 경로만(verification.REFERENCE_PATHS).
"""
from __future__ import annotations

import html
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from ..schemas import Evidence

from ..config import BOT_UA as UA  # noqa: E402
BASE = "https://maily.so/trendaword"
MIN_GAP_S = 3.0
_last = 0.0
WORD = re.compile(r"\d{2}\.\d{2}\.\d{2}\s*\([^)]\)\s*['‘’\"“”]([^'‘’\"“”]{1,30})['‘’\"“”]")


def _get(url: str) -> str | None:
    global _last
    wait = MIN_GAP_S - (time.time() - _last)
    if wait > 0:
        time.sleep(wait)
    _last = time.time()
    try:
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
        return r.text if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


def _plain(page: str) -> str:
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))


def feed() -> list[dict]:
    """[{word, url, date, issue}] 최근 20호."""
    x = _get(f"{BASE}/feed") or ""
    out = []
    for it in re.findall(r"<item>(.*?)</item>", x, re.S):
        link = re.search(r"<link>(.*?)</link>", it, re.S)
        desc = html.unescape(re.sub(r"<[^>]+>", " ", html.unescape((re.search(r"<description>(.*?)</description>", it, re.S) or [None, ""])[1] or "")))
        title = html.unescape((re.search(r"<title>(.*?)</title>", it, re.S) or [None, ""])[1] or "")
        date = re.search(r"<pubDate>(.*?)</pubDate>", it)
        w = WORD.search(desc)
        issue = re.search(r"#(\d+)", title)
        if link and w:
            out.append({"word": w.group(1).strip(), "url": link.group(1).strip(), "issue": int(issue.group(1)) if issue else None,
                        "date": parsedate_to_datetime(date.group(1)).astimezone(timezone.utc).isoformat() if date else None})
    return out


def archive(pages: int = 70) -> list[str]:
    """지난 호 게시글 주소들(목록 쪽을 넘긴다)."""
    urls: list[str] = []
    for n in range(1, pages + 1):
        page = _get(f"{BASE}?page={n}")
        if not page:
            break
        got = [f"https://maily.so{p}" for p in dict.fromkeys(re.findall(r"/trendaword/posts/[a-z0-9]+", page))]
        new = [u for u in got if u not in urls]
        if not new:
            break
        urls += new
    return urls


def post(url: str) -> dict | None:
    """{word, url, date, issue, sentences} — sentences 는 본문에서 그 단어가 든 문장·용례(메모리에서만 쓴다)."""
    page = _get(url)
    if not page:
        return None
    t = _plain(page)
    head = WORD.search(t)
    if not head:
        return None
    word = head.group(1).strip()
    d = re.search(r"(\d{4})\.(\d{2})\.(\d{2})\s*\|", t[head.end():head.end() + 40])
    issue = re.search(r"Trend A Word #(\d+)", t)
    i = t.find("from. 트렌드어워드")
    body = t[i + len("from. 트렌드어워드"):] if i >= 0 else t[head.end():]
    body = re.split(r"Trend A Word 오늘 꼭 알아야 하는|구독하기", body)[0]
    body = re.sub(r"이미지\s*=\s*[^()]*\(\s*https?://\S+\s*\)", " ", body)
    sents = [s.strip() for s in re.split(r"(?<=[.!?…다])\s+", body) if 8 < len(s.strip()) < 260]
    keep = [s for s in sents if word in s or "뜻" in s or "유래" in s][:8]
    usage = re.findall(r"\d\.\s*“([^”]{3,120})”", body)[:3]
    return {"word": word, "url": url.split("?")[0], "issue": int(issue.group(1)) if issue else None,
            "date": f"{d.group(1)}-{d.group(2)}-{d.group(3)}" if d else None, "sentences": keep, "usage": usage}


def evidence(p: dict) -> Evidence:
    """그 단어가 든 한 문장과 링크만(본문은 두지 않는다)."""
    line = (next((s for s in p["sentences"] if p["word"] in s and "뜻" in s), None) or next((s for s in p["sentences"] if "뜻" in s), None)
            or next((s for s in p["sentences"] if p["word"] in s), p["word"]))
    when = datetime.fromisoformat(p["date"]).replace(tzinfo=timezone.utc) if p.get("date") else datetime.now(timezone.utc)
    return Evidence(evidence_id=f"e_taw_{p['url'].rsplit('/', 1)[-1]}", kind="web", url=p["url"],
                    title=f"Trend A Word #{p.get('issue') or ''}: {p['word']}"[:200], source_domain="maily.so", observed_at=when, excerpt=line[:200])
