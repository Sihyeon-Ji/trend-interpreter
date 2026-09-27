"""YouTube Data API v3 로 쇼츠 후보를 모은다.

쿼터: videos.list = 1 unit, search.list = 100 unit, 프로젝트당 하루 10,000 unit.
쇼츠 전용 엔드포인트/필드는 없어서 contentDetails.duration 으로 클라이언트에서 거른다.
2025-07 이후 chart=mostPopular 는 음악·영화·게임 차트 위주라 일반 쇼츠 비율이 낮을 수 있다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from googleapiclient.discovery import build

from ..config import YOUTUBE_API_KEY, require
from ..schemas import ShortsVideo

SHORTS_MAX_SEC = 180  # 2024-10 이후 쇼츠 최대 3분
_DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _seconds(iso: str) -> int:
    m = _DUR.fullmatch(iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def _client():
    key = require("YOUTUBE_API_KEY", YOUTUBE_API_KEY)
    return build("youtube", "v3", developerKey=key, cache_discovery=False)


def _to_video(item: dict, region: str, source: str) -> ShortsVideo:
    sn, st, cd = item["snippet"], item.get("statistics", {}), item["contentDetails"]
    return ShortsVideo(
        video_id=item["id"],
        url=f"https://www.youtube.com/watch?v={item['id']}",
        title=sn["title"],
        channel=sn["channelTitle"],
        published_at=datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00")),
        duration_sec=_seconds(cd.get("duration", "")),
        view_count=int(st.get("viewCount", 0)),
        like_count=int(st.get("likeCount", 0)),
        comment_count=int(st.get("commentCount", 0)),
        region=region,
        category_id=sn.get("categoryId"),
        tags=sn.get("tags", []),
        source=source,
    )


def fetch_most_popular(
    region: str, max_results: int = 50, category_id: str | None = None, shorts_only: bool = True
) -> list[ShortsVideo]:
    """chart=mostPopular. 1 unit."""
    kwargs = dict(
        part="snippet,contentDetails,statistics", chart="mostPopular", regionCode=region, maxResults=min(max_results, 50)
    )
    if category_id:
        kwargs["videoCategoryId"] = category_id
    items = _client().videos().list(**kwargs).execute().get("items", [])
    vids = [_to_video(i, region, "most_popular") for i in items]
    return [v for v in vids if v.duration_sec <= SHORTS_MAX_SEC] if shorts_only else vids


def search_shorts(
    query: str, region: str, hours: int = 48, max_results: int = 50, lang: str | None = None
) -> list[ShortsVideo]:
    """search.list(100 unit) + videos.list(1 unit). 최근 N시간, 조회수순."""
    yt = _client()
    after = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    kwargs = dict(
        part="id", q=query, type="video", videoDuration="short", order="viewCount",
        regionCode=region, publishedAfter=after, maxResults=min(max_results, 50),
    )
    if lang:
        kwargs["relevanceLanguage"] = lang
    ids = [i["id"]["videoId"] for i in yt.search().list(**kwargs).execute().get("items", [])]
    if not ids:
        return []
    items = yt.videos().list(part="snippet,contentDetails,statistics", id=",".join(ids)).execute().get("items", [])
    vids = [_to_video(i, region, f"search:{query}") for i in items]
    return [v for v in vids if v.duration_sec <= SHORTS_MAX_SEC]


def top_comments(video_id: str, max_results: int = 20) -> list[dict]:
    """commentThreads.list — 1 unit. 관련도순 상위 댓글 (커뮤니티 반응 신호)."""
    r = _client().commentThreads().list(part="snippet", videoId=video_id, order="relevance", maxResults=min(max_results, 100), textFormat="plainText").execute()
    out = []
    for it in r.get("items", []):
        sn = it["snippet"]["topLevelComment"]["snippet"]
        out.append({"text": sn.get("textDisplay", ""), "likes": sn.get("likeCount", 0), "author": sn.get("authorDisplayName", ""), "published_at": sn.get("publishedAt", "")})
    return out
