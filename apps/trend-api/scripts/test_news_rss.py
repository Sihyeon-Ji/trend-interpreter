"""Google News RSS 수집 테스트. 키 불필요."""
from trend_agents.collectors.news_rss import fetch_news
from trend_agents.storage import sqlite_store as db

con = db.connect()
for region in ["KR", "JP", "TH"]:
    items = fetch_news(region, limit=20)
    print(f"[{region}] headlines: {len(items)}")
    for it in items[:3]:
        print(f"   - {it.title[:70]}  ({it.source})")
    db.upsert_news(con, items)

q = fetch_news("KR", query="밈 유행어", limit=10)
print(f"[KR search '밈 유행어'] {len(q)}")
for it in q[:5]:
    print(f"   - {it.title[:70]}")
db.upsert_news(con, q)
print("saved ->", con.execute("SELECT COUNT(*) FROM news").fetchone()[0], "rows")
