"""YouTube Data API 쇼츠 수집 테스트. YOUTUBE_API_KEY 필요. 쿼터 사용량을 출력한다."""
from trend_agents.collectors.youtube import fetch_most_popular, search_shorts
from trend_agents.storage import store as db

con = db.connect()
units = 0
for region in ["KR", "JP", "TH"]:
    allv = fetch_most_popular(region, shorts_only=False)
    shorts = [v for v in allv if v.duration_sec <= 180]
    units += 1
    print(f"[{region}] mostPopular: {len(allv)} videos, {len(shorts)} are shorts(<=180s)")
    for v in shorts[:3]:
        print(f"   - {v.duration_sec:3d}s  {v.view_count:>10,}  {v.title[:50]}")
    db.upsert_videos(con, shorts)

s = search_shorts("#shorts", "KR", hours=48)
units += 101
print(f"[KR search #shorts 48h] {len(s)} shorts")
for v in s[:5]:
    print(f"   - {v.duration_sec:3d}s  {v.view_count:>10,}  {v.title[:50]}")
db.upsert_videos(con, s)
print(f"quota used ≈ {units} / 10,000 units. saved -> {con.execute('SELECT COUNT(*) FROM videos').fetchone()[0]} videos")
