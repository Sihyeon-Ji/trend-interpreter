"""커뮤니티 신호. 공식 API 가 없는 한국 커뮤니티(더쿠·디시·에펨·인스티즈·루리웹)는 크롤링 대신 **Google 뉴스 RSS 의 site: 검색**으로 구글에 색인된 글만 가져온다
(약관·안정성 문제 회피, 키 없음). Reddit·Bluesky 는 키가 있을 때만. Hacker News 는 키 없음. YouTube 댓글은 공식 API(1 unit).
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from ..config import BLUESKY_APP_PASSWORD, BLUESKY_HANDLE, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
from ..schemas import Evidence
from . import news_rss
from .wikipedia_top import UA

# 지역별 커뮤니티 도메인 (구글 뉴스에 색인되는 것들)
COMMUNITY_SITES = {
    "KR": ["theqoo.net", "fmkorea.com", "dcinside.com", "instiz.net", "ruliweb.com", "clien.net", "ppomppu.co.kr", "reddit.com"],
    "JP": ["togetter.com", "girlschannel.net", "reddit.com"],
    "ID": ["kaskus.co.id", "reddit.com"],
    "TH": ["pantip.com", "reddit.com"],
    "TW": ["ptt.cc", "dcard.tw", "reddit.com"],
    "VN": ["voz.vn", "reddit.com"],
    # 목표 지역(ADR 0001) 나머지. 말레이시아·싱가포르는 본 도메인이 기술 뉴스라 포럼 하위 도메인을 쓴다(09-28 실측)
    "HK": ["lihkg.com", "discuss.com.hk", "reddit.com"],
    "PH": ["reddit.com", "pinoyexchange.com"],
    "MY": ["forum.lowyat.net", "reddit.com"],
    "SG": ["forums.hardwarezone.com.sg", "reddit.com"],
}
DEFAULT_SITES = ["reddit.com"]


def _ev(kind: str, url: str, title: str, domain: str, when: datetime | None, excerpt: str) -> Evidence:
    from ..storage.dictionary_store import new_id

    return Evidence(evidence_id=new_id("e", url), kind=kind, url=url, title=title[:200], source_domain=domain, observed_at=when or datetime.now(timezone.utc), excerpt=excerpt[:240])  # type: ignore[arg-type]


def _site_key(site: str) -> str:
    """출처 이름에서 찾을 사이트 낱말. 'forum.lowyat.net' 은 'forum' 이 아니라 'lowyat' — 앞 낱말은 아무 제목에나 있다."""
    return next((p for p in site.split(".") if p not in ("forum", "forums", "www")), site)


def google_indexed_posts(term: str, region: str, limit: int = 8) -> list[Evidence]:
    """구글에 색인된 커뮤니티 글. 제목에 게시판·사이트 이름이 붙어 온다."""
    sites = COMMUNITY_SITES.get(region, DEFAULT_SITES)
    q = f"{term} " + " OR ".join(f"site:{s}" for s in sites)
    news_region = region if region in news_rss.LOCALES else "US"
    out: list[Evidence] = []
    for n in news_rss.fetch_news(news_region, query=q, limit=limit):
        domain = next((s for s in sites if _site_key(s) in n.title.lower() or _site_key(s) in (n.source or "").lower()), (n.source or "community").lower().replace(" ", ""))
        out.append(_ev("community", n.link, n.title, domain, n.published_at, n.title))
    return out


def hackernews(term: str, limit: int = 5) -> list[Evidence]:
    r = httpx.get("https://hn.algolia.com/api/v1/search_by_date", params={"query": term, "tags": "story", "hitsPerPage": limit}, headers={"User-Agent": UA}, timeout=10)
    r.raise_for_status()
    out = []
    for h in r.json().get("hits", []):
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}"
        out.append(_ev("community", url, h.get("title", ""), "news.ycombinator.com", datetime.fromisoformat(h["created_at"].replace("Z", "+00:00")), f"{h.get('title','')} · {h.get('points',0)} points"))
    return out


def youtube_comments(video_id: str, video_url: str, video_title: str, term: str, limit: int = 20) -> Evidence | None:
    """상위 댓글을 한 근거로. 용어가 들어 있는 댓글을 우선, 없으면 좋아요 상위."""
    from .youtube import top_comments

    key = "".join(term.split()).lower()
    cs = top_comments(video_id, limit)
    if not cs:
        return None
    hit = [c for c in cs if key in "".join(c["text"].split()).lower()] or sorted(cs, key=lambda c: -c["likes"])[:3]
    excerpt = " | ".join(f"({c['likes']}) {c['text'].strip().replace(chr(10), ' ')[:80]}" for c in hit[:3])
    return _ev("community", video_url + "#comments", f"YouTube 댓글 · {video_title}", "youtube.com/comments", None, excerpt)


def reddit_search(term: str, limit: int = 8) -> list[Evidence]:
    """Reddit 공식 API (client_credentials, 읽기 전용). 키 없으면 빈 목록."""
    if not (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        return []
    auth = base64.b64encode(f"{REDDIT_CLIENT_ID}:{REDDIT_CLIENT_SECRET}".encode()).decode()
    tok = httpx.post("https://www.reddit.com/api/v1/access_token", data={"grant_type": "client_credentials"}, headers={"Authorization": f"Basic {auth}", "User-Agent": UA}, timeout=10)
    tok.raise_for_status()
    r = httpx.get("https://oauth.reddit.com/search", params={"q": term, "sort": "new", "limit": limit, "t": "month"},
                  headers={"Authorization": f"Bearer {tok.json()['access_token']}", "User-Agent": UA}, timeout=10)
    r.raise_for_status()
    out = []
    for c in r.json().get("data", {}).get("children", []):
        d = c["data"]
        out.append(_ev("community", "https://www.reddit.com" + d["permalink"], d.get("title", ""), f"reddit.com/r/{d.get('subreddit','')}",
                       datetime.fromtimestamp(d["created_utc"], tz=timezone.utc), f"{d.get('title','')} · r/{d.get('subreddit','')} · {d.get('score',0)}↑ — {(d.get('selftext') or '')[:120]}"))
    return out


# 레딧 대체. Reddit 은 2026-09-16 기준 승인 없이는 API 도 공개 JSON(403)도 막혀 있다.
# Lemmy 는 같은 꼴의 커뮤니티이고 인증 없이 읽힌다. 도메인이 reddit.com 과 다르므로 독립 출처로도 셈이 된다.
LEMMY_HOST = "lemmy.world"


def lemmy_search(term: str, limit: int = 8) -> list[Evidence]:
    """Lemmy 공개 검색 (키 불필요)."""
    r = httpx.get(f"https://{LEMMY_HOST}/api/v3/search",
                  params={"q": term, "type_": "Posts", "sort": "New", "limit": limit},
                  headers={"User-Agent": UA}, timeout=12)
    r.raise_for_status()
    out = []
    for p in r.json().get("posts", [])[:limit]:
        post, cnt = p.get("post", {}), p.get("counts", {})
        body = (post.get("body") or "")[:120]
        try:
            seen = datetime.fromisoformat(post["published"].replace("Z", "+00:00"))
        except Exception:
            seen = datetime.now(timezone.utc)
        out.append(_ev("community", post.get("ap_id") or f"https://{LEMMY_HOST}/post/{post.get('id')}",
                       (post.get("name") or "")[:200], LEMMY_HOST, seen,
                       f"{post.get('name','')} · {cnt.get('score', 0)}↑ — {body}"))
    return out


def bluesky_search(term: str, limit: int = 8) -> list[Evidence]:
    """Bluesky 검색 (앱 비밀번호 필요 — 공개 엔드포인트는 403). 키 없으면 빈 목록."""
    if not (BLUESKY_HANDLE and BLUESKY_APP_PASSWORD):
        return []
    s = httpx.post("https://bsky.social/xrpc/com.atproto.server.createSession", json={"identifier": BLUESKY_HANDLE, "password": BLUESKY_APP_PASSWORD}, timeout=10)
    s.raise_for_status()
    r = httpx.get("https://bsky.social/xrpc/app.bsky.feed.searchPosts", params={"q": term, "limit": limit, "sort": "latest"},
                  headers={"Authorization": f"Bearer {s.json()['accessJwt']}", "User-Agent": UA}, timeout=10)
    r.raise_for_status()
    out = []
    for p in r.json().get("posts", []):
        handle = p["author"]["handle"]
        rkey = p["uri"].rsplit("/", 1)[-1]
        out.append(_ev("community", f"https://bsky.app/profile/{handle}/post/{rkey}", p["record"].get("text", "")[:80], "bsky.app",
                       datetime.fromisoformat(p["record"]["createdAt"].replace("Z", "+00:00")), f"@{handle} · {p.get('likeCount',0)}♥ — {p['record'].get('text','')}"))
    return out


def gather(term: str, region: str, videos: list[tuple[str, str, str]] = (), comment_videos: int = 2) -> tuple[list[Evidence], list[str]]:
    """모든 커뮤니티 소스를 한 번에. (근거 목록, 실패 메모). videos: (video_id, url, title)"""
    evs: list[Evidence] = []
    notes: list[str] = []
    for name, fn in (("community_sites", lambda: google_indexed_posts(term, region)), ("hackernews", lambda: hackernews(term) if region in ("US", "GB", "AU", "IN", "CA") else []),
                     ("reddit", lambda: reddit_search(term)), ("lemmy", lambda: lemmy_search(term)),
                     ("bluesky", lambda: bluesky_search(term))):
        try:
            evs += fn()
        except Exception as e:
            notes.append(f"{name}:{type(e).__name__}")
    # 앵커: 용어(또는 그 조각)가 제목·발췌에 실제로 있는 글만 — site: 검색은 느슨하게 맞는 글도 돌려준다
    key = "".join(term.split()).lower()
    toks = [t.lower() for t in term.split() if len(t) >= 2] or [key]
    evs = [e for e in evs if key in "".join((e.title + e.excerpt).split()).lower() or all(t in (e.title + e.excerpt).lower() for t in toks)]
    for vid, url, title in list(videos)[:comment_videos]:
        try:
            ev = youtube_comments(vid, url, title, term)
            if ev:
                evs.append(ev)
        except Exception as e:
            notes.append(f"comments:{type(e).__name__}")
    return evs, notes
