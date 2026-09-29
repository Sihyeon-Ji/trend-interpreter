"""커뮤니티 신호. 공식 API 가 없는 한국 커뮤니티(더쿠·디시·에펨·인스티즈·루리웹)는 크롤링 대신 **Google 뉴스 RSS 의 site: 검색**으로 구글에 색인된 글만 가져온다
(약관·안정성 문제 회피, 키 없음). Reddit·Bluesky 는 키가 있을 때만. YouTube 댓글은 공식 API(1 unit).

커뮤니티·SNS 글은 **쓰임을 재는 지표로만** 쓴다(ADR 0003) — 생애주기·순위·리스크 판정에는 세지만, 제목·인용·링크·사이트 이름으로
이용자에게 내지 않는다. Lemmy·Hacker News 는 목표 지역 밖이라 2026-09-29 에 수집을 멈췄다.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from urllib.parse import urlsplit

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

# 커뮤니티·SNS 글이 'community' 가 아닌 길로 들어올 때 알아보는 곳 — 구글 뉴스 검색이 커뮤니티 글을 기사로 돌려주고(한국 커뮤니티는
# 한국어 이름으로), 조사 모델이 든 웹 링크가 커뮤니티·SNS 글이기도 하다. 예전에 모은 Lemmy·Hacker News 글도 남아 있다.
POST_HOSTS = ({s for sites in COMMUNITY_SITES.values() for s in sites}
              | {"bsky.app", "lemmy.world", "news.ycombinator.com", "5ch.net", "x.com", "twitter.com", "threads.net", "threads.com", "instagram.com", "facebook.com"})
POST_NAMES = {"디시인사이드", "갤러리", "클리앙", "에펨코리아", "더쿠", "루리웹", "인스티즈", "뽐뿌"}


def is_community_post(e) -> bool:
    """커뮤니티·SNS 글인가(Evidence·EvidenceBrief). 이런 글은 이용자에게 제목·인용·링크·사이트 이름으로 내지 않는다(ADR 0003).
    'community' 로 모은 글, 그리고 기사·웹 문서로 들어온 커뮤니티·SNS 사이트의 글. 사이트는 그 도메인이거나 하위 도메인일 때만 —
    글자가 들어 있다고 보지 않는다."""
    if e.kind == "community":
        return True
    if e.kind not in ("news", "web"):
        return False
    domain = (e.source_domain or "").lower()
    hosts = {domain.split("/")[0], (urlsplit(e.url or "").hostname or "").lower()}
    return domain in POST_NAMES or any(h == s or h.endswith("." + s) for h in hosts if h for s in POST_HOSTS)


def for_prompt(evs: list) -> tuple[list, str]:
    """모델에게 보일 근거와 한 줄 알림. 커뮤니티·SNS 글은 뜻의 근거가 아니라 쓰였다는 신호라(ADR 0003) 내용은 넣지 않고 몇 건인지만 알린다 —
    사용자 결정(09-29): 'AI 가 얼마나 쓰는지만 지표로 보게'. 리스크 판정(pipeline/risk.py)은 백엔드 판단이라 따로 원문을 본다."""
    posts = sum(1 for e in evs if is_community_post(e))
    note = f"- (커뮤니티·SNS 글 {posts}건 — 쓰였다는 신호일 뿐 뜻의 근거가 아니어서 내용은 넣지 않았다)" if posts else ""
    return [e for e in evs if not is_community_post(e)], note


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
    for name, fn in (("community_sites", lambda: google_indexed_posts(term, region)), ("reddit", lambda: reddit_search(term)),
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
