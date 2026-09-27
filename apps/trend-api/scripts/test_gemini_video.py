"""Gemini 가 쇼츠 URL 을 직접 보고 해석하는지 테스트. GEMINI_API_KEY 필요.

사용: uv run scripts/test_gemini_video.py [url ...]
URL 을 안 주면 DB 에서 조회수 상위 3개를 쓴다.
"""
import sys
import time

from trend_agents.config import GEMINI_MODEL
from trend_agents.interpreters.gemini_video import interpret_shorts
from trend_agents.storage import sqlite_store as db

con = db.connect()
urls = sys.argv[1:] or db.top_videos(con, n=3)
if not urls:
    raise SystemExit("URL 인자를 주거나 먼저 test_youtube_collect.py 를 실행하세요")

t = time.time()
res = interpret_shorts(urls)
print(f"model={res.model}  {len(urls)} videos  {time.time()-t:.1f}s  tokens in={res.input_tokens:,} out={res.output_tokens:,}")
for it in res.items:
    print(f"\n=== {it.url}  [{it.language}] gen={it.target_generation}")
    print("summary :", it.summary)
    for m in it.memes:
        print(f"  meme   : {m.name} ({m.kind}, conf {m.confidence:.2f}) <- {m.origin_hypothesis}")
    print("viral   :", it.why_viral)
    print("outsider:", it.explain_for_outsider)
    print("risk    :", it.risk_flags)
db.save_interpretations(con, res.items, GEMINI_MODEL)
