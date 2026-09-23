"""한국 세대 신호. 네이버 데이터랩 검색어 트렌드를 세대별(10대~50대+)로 나눠 불러 '어느 세대에서 먼저 튀었나·지금 얼마나 남았나'를
Segment 사용(usage)과 datalab 근거로 저장한다. 한국어 용어(lang=ko)만. 용어당 5회, 실행당 8개 용어."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone

from ..collectors import naver_datalab as nd
from ..collectors.naver_search import available
from ..schemas import Evidence
from ..storage import dictionary_store as ds
from .runs import stage

TERMS_PER_RUN = 12
DAYS = 180


def run(con: sqlite3.Connection) -> dict:
    with stage(con, "naver") as r:
        if not available():
            r.status, r.note = "skipped", "NAVER_CLIENT_ID 없음"
        else:
            end = date.today()
            start = end - timedelta(days=DAYS)
            terms = [t for t in ds.list_terms(con, ("verified", "needs_review", "researching")) if t.lang == "ko"]
            # 최근에 본 것부터, 아직 datalab 근거가 없는 용어 우선
            terms.sort(key=lambda t: (any(e.kind == "datalab" and e.source_domain == "datalab.naver.com" for e in ds.list_evidences(con, t.term_id)), -(t.last_seen or datetime.min.replace(tzinfo=timezone.utc)).timestamp()))
            for t in terms[:TERMS_PER_RUN]:
                gens = nd.spike_by_generation(t.canonical, start.isoformat(), end.isoformat())
                recent = {g: (sum(p["ratio"] for p in v["points"][-14:]) / max(1, len(v["points"][-14:]))) for g, v in gens.items()}
                total = sum(recent.values()) or 1
                rows = []
                for g, v in gens.items():
                    first = v["peak_date"] or start.isoformat()
                    rows.append((g, "KR", datetime.fromisoformat(first).replace(tzinfo=timezone.utc).isoformat(), round(recent[g] / total, 3)))
                ds.set_usage(con, t.term_id, rows)
                for g, v in gens.items():
                    ds.set_gen_curve(con, t.term_id, g, v["points"])
                peaks = ", ".join(f"{g} {v['peak_date']}" for g, v in gens.items() if v["peak_date"])
                ds.add_evidences(con, t.term_id, [Evidence(evidence_id=ds.new_id("e", f"datalab|{t.term_id}|{end}"), kind="datalab", url="https://datalab.naver.com/keyword/trendSearch.naver",
                                                          title=f"네이버 데이터랩 세대별 검색 추이: {t.canonical}", source_domain="datalab.naver.com", observed_at=datetime.now(timezone.utc),
                                                          excerpt=f"{t.canonical} 최근 {DAYS}일 세대별 피크 — {peaks}")])
                r.detail[t.canonical] = peaks[:80]
                r.count += 1
            # 쇼핑인사이트: 분야별(전체 + 연령별) 주간 클릭 추세 12주 — 보드의 패션·뷰티·음식·제품 축
            try:
                s0 = (end - timedelta(weeks=12)).isoformat()
                for name, code in nd.SHOPPING_CATEGORIES.items():
                    res = nd.shopping_categories({name: code}, s0, end.isoformat(), time_unit="week")
                    ds.upsert_shopping(con, name, "all", res["results"][0]["data"] if res.get("results") else [])
                    for age in ("10", "20", "30", "40", "50", "60"):
                        res = nd.shopping_categories({name: code}, s0, end.isoformat(), time_unit="week", ages=[age])
                        ds.upsert_shopping(con, name, age, res["results"][0]["data"] if res.get("results") else [])
                r.detail["shopping"] = f"{len(nd.SHOPPING_CATEGORIES)} categories x 7"
            except Exception as e:
                r.note += f" shopping:{type(e).__name__}"
    return {"naver": r}
