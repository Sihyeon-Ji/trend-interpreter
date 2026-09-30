"""밈 성향 분석 (Plan 16). 어떤 종류·느낌의 밈이 언제·어디서 많이 생겼나를 **데이터로만** 센다.

- 종류·연대·나라: 나무위키 분류(wiki_catalog 또는 data/work/catalog/namu.json). 모델 추정 없음.
- 느낌·쓰임·말투: 사전에 오른 말의 fit 낱말(닫힌 낱말, fit 단계가 뜻에 붙인 것) — 연대별로 비율을 비교한다.
- 연대가 둘 이상일 때 비중이 가장 크게 늘거나 준 종류를 '오르는 성향'·'내리는 성향' 으로 뽑는다(비율 차, 규칙).

  uv run scripts/meme_tendency.py                    # 표를 찍고 data/work/catalog/tendency.json 에 남긴다
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.pipeline import catalog  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

MIN_PER_DECADE = 20      # 한 연대에 이만큼은 있어야 비율을 비교한다


def shares(counter: Counter, total: int) -> dict[str, float]:
    return {k: round(v / total, 3) for k, v in counter.most_common()} if total else {}


def shift(by_decade: dict[int, Counter], totals: dict[int, int], a: int, b: int, top: int = 5) -> dict:
    keys = set(by_decade[a]) | set(by_decade[b])
    d = {k: round(by_decade[b][k] / totals[b] - by_decade[a][k] / totals[a], 3) for k in keys}
    ranked = sorted(d.items(), key=lambda x: -x[1])
    return {"rising": [x for x in ranked[:top] if x[1] > 0], "falling": [x for x in ranked[::-1][:top] if x[1] < 0]}


def main() -> None:
    src = Path("data/work/catalog/namu.json")
    entries = json.loads(src.read_text(encoding="utf-8"))
    con = db.connect()
    fits = {tid: f for tid, (_, f) in ds.all_fits(con).items()}
    rows = [(t, catalog.meta(c)) for t, c in entries.items()]
    dated = [(t, m) for t, m in rows if m["decade"]]
    genre = defaultdict(Counter)
    country = defaultdict(Counter)
    totals = Counter()
    for _, m in dated:
        totals[m["decade"]] += 1
        genre[m["decade"]].update(m["genres"] or ["(종류 분류 없음)"])
        country[m["decade"]].update(m["countries"] or ["(나라 분류 없음)"])
    # 사전에 오른 말의 느낌·쓰임·말투 (fit) — 제목으로 표제어를 찾는다
    feel, use, voice, ftot = defaultdict(Counter), defaultdict(Counter), defaultdict(Counter), Counter()
    for title, m in dated:
        name = catalog.title_to_term(title)
        t = ds.find_term(con, name) if name else None
        f = fits.get(t.term_id) if t and t.status == "verified" else None
        if f:
            ftot[m["decade"]] += 1
            feel[m["decade"]].update(f.feelings)
            use[m["decade"]].update(f.uses)
            voice[m["decade"]][f.voice] += 1
    decades = sorted(d for d in totals if totals[d] >= MIN_PER_DECADE)
    out = {"documents": len(rows), "dated": len(dated), "decades": {d: totals[d] for d in sorted(totals)},
           "genre_share": {d: shares(genre[d], totals[d]) for d in decades},
           "country_share": {d: shares(country[d], totals[d]) for d in decades},
           "fit_counted": dict(ftot),
           "feeling_share": {d: shares(feel[d], ftot[d]) for d in decades if ftot[d]},
           "use_share": {d: shares(use[d], ftot[d]) for d in decades if ftot[d]},
           "voice_share": {d: shares(voice[d], ftot[d]) for d in decades if ftot[d]}}
    if len(decades) >= 2:
        a, b = decades[-2], decades[-1]
        out["genre_shift"] = {"from": a, "to": b, **shift(genre, totals, a, b)}
        out["country_shift"] = {"from": a, "to": b, **shift(country, totals, a, b)}
        if ftot[a] >= MIN_PER_DECADE and ftot[b] >= MIN_PER_DECADE:
            out["feeling_shift"] = {"from": a, "to": b, **shift(feel, ftot, a, b)}
    Path("data/work/catalog/tendency.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"문서 {out['documents']} · 연대 있음 {out['dated']} · 연대별 {out['decades']}")
    for d in decades:
        print(f"\n{d}년대 ({totals[d]}개) 종류 상위: {list(out['genre_share'][d].items())[:6]}")
        print(f"  나라: {list(out['country_share'][d].items())[:5]}")
        if d in out["feeling_share"]:
            print(f"  느낌(사전에 오른 {ftot[d]}개): {list(out['feeling_share'][d].items())[:5]}")
    for k in ("genre_shift", "country_shift", "feeling_shift"):
        if k in out:
            s = out[k]
            print(f"\n{k} {s['from']}→{s['to']}: 오름 {s['rising']} / 내림 {s['falling']}")


if __name__ == "__main__":
    main()
