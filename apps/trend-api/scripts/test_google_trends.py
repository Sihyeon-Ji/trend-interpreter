"""Google Trends 두 경로 실측. RSS 는 키 없음, BigQuery 는 ADC + GOOGLE_CLOUD_PROJECT.

사용: uv run scripts/test_google_trends.py [KR JP ID ...]
"""
import sys

from trend_agents.collectors import google_trends as gt
from trend_agents.config import GOOGLE_CLOUD_PROJECT

regions = sys.argv[1:] or ["KR", "JP", "ID"]

print("== Trending now RSS (키 없음) ==")
for r in regions:
    items = gt.trending_now(r)
    print(f"[{r}] {len(items)}건: " + " · ".join(f"{q.term}({q.approx_traffic})" for q in items[:6]))

if not GOOGLE_CLOUD_PROJECT:
    raise SystemExit("GOOGLE_CLOUD_PROJECT 가 비어 있습니다. .env 를 채우고 `gcloud auth login --update-adc` 를 실행하세요.")
try:
    d = gt.latest_refresh_date()
except Exception as e:  # ADC 없음, API 미사용 등
    raise SystemExit(f"BigQuery 접근 실패: {type(e).__name__}: {str(e)[:160]}\n→ gcloud auth login --update-adc 후 다시 실행")

cc = gt.countries(d)
print(f"\n== BigQuery 공개 데이터셋 (refresh_date={d}) — {len(cc)}개국 ==")
print(" ".join(cc))
for r in regions:
    if r not in cc:
        print(f"[{r}] 데이터셋에 없음 → RSS 만 사용"); continue
    rising = gt.rising_terms(r, d)
    top = gt.top_terms(r, d)
    print(f"\n[{r}] 급상승 {len(rising)}: " + " · ".join(f"{q.rank}.{q.term}(+{q.percent_gain}%)" for q in rising[:8]))
    print(f"[{r}] 상위   {len(top)}: " + " · ".join(f"{q.rank}.{q.term}({q.score})" for q in top[:8]))
