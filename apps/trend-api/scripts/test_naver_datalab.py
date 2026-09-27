"""네이버 데이터랩 세대별 검색 곡선 테스트. NAVER_CLIENT_ID/SECRET 필요.

사용: uv run scripts/test_naver_datalab.py [키워드]
"""
import sys
from datetime import date, timedelta

from trend_agents.collectors.naver_datalab import spike_by_generation

kw = sys.argv[1] if len(sys.argv) > 1 else "럭키비키"
end = date.today()
start = end - timedelta(days=180)
res = spike_by_generation(kw, start.isoformat(), end.isoformat())
print(f"'{kw}' 세대별 피크 시점 (최근 180일, 값은 요청 내 상대지수)")
for gen, r in res.items():
    pts = r["points"]
    recent = sum(p["ratio"] for p in pts[-14:]) / max(1, len(pts[-14:]))
    print(f"  {gen:4s} peak={r['peak_date']}  last14d_avg={recent:5.1f}")
