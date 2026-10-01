"""나무위키 출신 확인 항목에 문서 속 원본 유튜브 영상을 붙인다(2026-10-01). 그림·영상이 없는 것만, 파이프라인 창에는 쉰다."""
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_import import busy  # noqa: E402
from trend_agents.pipeline.research import media_from_namu  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

con = db.connect()
rows = con.execute("SELECT DISTINCT term_id, title FROM wiki_catalog WHERE source='namu'").fetchall()
added = seen = 0
for tid, title in rows:
    t = ds.get_term(con, tid)
    if not t or t.status != "verified" or ds.has_media(con, tid):
        continue
    while busy():
        time.sleep(300)
    seen += 1
    got = media_from_namu(con, t, title)
    added += got
    if seen % 50 == 0:
        print(f"[{datetime.now():%H:%M}] 본 것 {seen} 붙은 것 {added}", flush=True)
print("끝", seen, added, flush=True)
