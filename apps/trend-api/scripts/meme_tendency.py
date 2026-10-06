"""밈 성향 분석 (Plan 16). 어떤 성향의 밈이 언제·어디서 많이 생겼나를 **데이터로만** 센다. 모델을 부르지 않고 DB 는 읽기만 한다.

- 시기·종류·나라: wiki_catalog 전체(나무위키·pttpedia·wikidata·trendaword…)의 분류/꼬리표를 `catalog.meta()` 로 읽는다.
  출처마다 '해' 의 뜻이 다르다(나무위키 '20XX년 인터넷 밈', pttpedia '20XX年流行用語', wikidata·trendaword 'year:YYYY',
  trendaword 는 소개된 호의 해). 그래서 해별 표는 출처 열을 따로 둔다.
- 느낌·쓰임·말투: ds.all_fits (확인된 항목만 fit 이 있다).
- 두 시기의 비중 차(규칙)로 '늘어난 것·준 것' 을 뽑는다. 한 시기의 표본이 MIN_N 미만이면 '표본 적음'.
- Trend A Word 는 호 날짜(evidences e_taw_*)의 해·분기별로 느낌·쓰임 비중을 본다.

  uv run scripts/meme_tendency.py     # DATABASE_URL, read-only PostgreSQL
  uv run scripts/meme_tendency.py --sqlite data/trend.db  # read-only legacy snapshot
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.pipeline import catalog  # noqa: E402
from trend_agents.storage import db, dictionary_store as ds  # noqa: E402
from trend_agents.storage.db import Connection  # noqa: E402

OUT = Path("data/work/catalog")
MIN_N = 20                      # 한 칸(시기 × 항목)의 표본이 이보다 적으면 '표본 적음'
PRIORITY = ["namu", "pttpedia", "wikidata", "trendaword"]   # 같은 말이 여러 출처에 있으면 앞의 것을 센다(전체 비교용)
DIMS = [("genres", "종류"), ("regions", "나라"), ("feelings", "느낌"), ("uses", "쓰임"), ("voice", "말투")]
PERIODS = {
    "decade": ("2010년대 vs 2020년대", lambda y: "2010년대" if 2010 <= y < 2020 else "2020년대" if 2020 <= y < 2030 else None),
    "recent": ("2020~2022 vs 2023~2026", lambda y: "2020~2022" if 2020 <= y <= 2022 else "2023~2026" if 2023 <= y <= 2026 else None),
}


def values(row: dict, dim: str) -> list[str]:
    if dim == "voice":
        return [row["fit"].voice] if row.get("fit") else []
    if dim in ("feelings", "uses"):
        return list(getattr(row["fit"], dim)) if row.get("fit") else []
    return row["meta"][dim]


def compare(rows: list[dict], key, a: str, b: str) -> dict:
    """rows 를 key(year) 로 두 시기에 나눠 항목별 비중과 차를 낸다. 분모는 그 항목 값이 있는 표제어 수."""
    out: dict = {}
    for dim, _ in DIMS:
        n = {a: 0, b: 0}
        c = {a: Counter(), b: Counter()}
        for r in rows:
            p = key(r["year"]) if r["year"] else None
            v = values(r, dim)
            if p in n and v:
                n[p] += 1
                c[p].update(set(v))
        cells = []
        for k in set(c[a]) | set(c[b]):
            sa = c[a][k] / n[a] if n[a] else 0
            sb = c[b][k] / n[b] if n[b] else 0
            cells.append({"name": k, a: c[a][k], b: c[b][k], f"share_{a}": round(sa, 3), f"share_{b}": round(sb, 3),
                          "diff": round(sb - sa, 3), "small": min(n[a], n[b]) < MIN_N})
        cells.sort(key=lambda x: (-x["diff"], x["name"]))
        out[dim] = {"n": n, "cells": cells}
    return out


def load(con: Connection | sqlite3.Connection) -> tuple[list[dict], dict]:
    fits = {tid: f for tid, (_, f) in ds.all_fits(con).items()}
    taw = dict(con.execute("SELECT term_id, MIN(observed_at) FROM evidences WHERE evidence_id LIKE 'e_taw_%' GROUP BY term_id"))
    rows = []
    for tid, src, title, cj in con.execute("SELECT term_id, source, title, categories_json FROM wiki_catalog"):
        m = catalog.meta(json.loads(cj or "[]"))
        rows.append({"term_id": tid, "source": src, "title": title, "meta": m, "year": m["year"], "decade": m["decade"],
                     "fit": fits.get(tid), "taw_at": taw.get(tid) if src == "trendaword" else None})
    return rows, {"fit_terms": len(fits), "taw_dated": len(taw)}


def analyze(con: Connection | sqlite3.Connection) -> dict:
    """Build aggregate statistics without mutating the source or calling a model."""
    rows, info = load(con)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    src_count = Counter(r["source"] for r in rows)
    dated = Counter(r["source"] for r in rows if r["year"])
    # 1. 해·연대별 × 출처
    by_year: dict = defaultdict(Counter)
    for r in rows:
        if r["year"]:
            by_year[r["year"]][r["source"]] += 1
    by_decade_only = Counter((r["source"], r["decade"]) for r in rows if r["decade"] and not r["year"])
    # 2. 시기 비교 — 전체(같은 말은 한 번, 출처 우선순위) 와 나무위키만
    best: dict = {}
    for r in sorted(rows, key=lambda r: PRIORITY.index(r["source"]) if r["source"] in PRIORITY else 9):
        if r["term_id"] not in best or (r["year"] and not best[r["term_id"]]["year"]):
            best[r["term_id"]] = r
    groups = {"전체(출처 섞음, 같은 말 1회)": list(best.values()), "나무위키만": [r for r in rows if r["source"] == "namu"],
              "Trend A Word만": [r for r in rows if r["source"] == "trendaword"]}
    cmp_out = {}
    for g, grows in groups.items():
        cmp_out[g] = {"n_rows": len(grows), "by_source": dict(Counter(r["source"] for r in grows if r["year"])),
                      "decade": compare(grows, PERIODS["decade"][1], "2010년대", "2020년대"),
                      "recent": compare(grows, PERIODS["recent"][1], "2020~2022", "2023~2026")}
    # 3. Trend A Word 해·분기 (호 날짜 기준)
    taw_rows = [r for r in rows if r["source"] == "trendaword" and r["taw_at"]]
    per: dict = defaultdict(lambda: {"n": 0, "fit_n": 0, "feelings": Counter(), "uses": Counter()})
    for r in taw_rows:
        d = datetime.fromisoformat(r["taw_at"])
        for k in (str(d.year), f"{d.year}-Q{(d.month - 1) // 3 + 1}"):
            e = per[k]
            e["n"] += 1
            if r["fit"]:
                e["fit_n"] += 1
                e["feelings"].update(set(r["fit"].feelings))
                e["uses"].update(set(r["fit"].uses))
    taw_out = {k: {"issues": e["n"], "fit_n": e["fit_n"], "small": e["fit_n"] < MIN_N,
                   "feelings": {x: round(v / e["fit_n"], 3) for x, v in e["feelings"].most_common()} if e["fit_n"] else {},
                   "uses": {x: round(v / e["fit_n"], 3) for x, v in e["uses"].most_common()} if e["fit_n"] else {}}
               for k, e in sorted(per.items())}
    # 4. 뜬 해 — 위키백과 월별 조회수의 최고 달(출처의 해가 없는 표제어도 시기가 생긴다)
    peaks = []
    has_pageviews = (
        con.execute("SELECT 1 FROM sqlite_master WHERE name='term_pageviews'").fetchone()
        if isinstance(con, sqlite3.Connection)
        else con.execute("SELECT to_regclass('term_pageviews')").fetchone()[0]
    )
    if has_pageviews:
        peaks = [(tid, pm) for tid, pm in con.execute(
            "SELECT term_id, month FROM (SELECT term_id, month, ROW_NUMBER() OVER (PARTITION BY term_id ORDER BY views DESC, month DESC) rn FROM term_pageviews) AS ranked WHERE rn=1")]
    src_year = {r["term_id"] for r in rows if r["year"]}
    peak_years: dict = defaultdict(lambda: {"n": 0, "no_source_year": 0})
    for tid, pm in peaks:
        y = pm[:4]
        peak_years[y]["n"] += 1
        peak_years[y]["no_source_year"] += tid not in src_year
    out = {"generated_at": now, "catalog_rows": dict(src_count), "catalog_dated": dict(dated), "fit_terms": info["fit_terms"],
           "years": {y: dict(by_year[y]) for y in sorted(by_year)},
           "decade_only": {f"{s}:{d}": n for (s, d), n in sorted(by_decade_only.items())},
           "peak_years": {y: peak_years[y] for y in sorted(peak_years)}, "compare": cmp_out, "trendaword": taw_out, "min_n": MIN_N}
    return out


def connect_source(path: str | None) -> Connection | sqlite3.Connection:
    if path:
        snapshot = Path(path).resolve()
        if not snapshot.is_file():
            raise SystemExit(f"DB 사본이 없습니다: {snapshot}")
        return sqlite3.connect(f"{snapshot.as_uri()}?mode=ro", uri=True, timeout=60)
    return db.connect_read_only()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sqlite", help="읽기 전용 SQLite 사본. 생략하면 DATABASE_URL의 PostgreSQL")
    parser.add_argument("--out", type=Path, default=OUT, help="집계 JSON·Markdown 저장 폴더")
    args = parser.parse_args()
    con = connect_source(args.sqlite)
    try:
        # Keep every aggregate in the same snapshot even while collection runs.
        if isinstance(con, sqlite3.Connection):
            con.execute("BEGIN")
        else:
            con.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        out = analyze(con)
    finally:
        con.close()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "tendency.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "tendency.md").write_text(render(out), encoding="utf-8")
    print(render(out))


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def render(o: dict) -> str:
    L = [f"# 밈 성향 분석 (데이터만, 모델 호출 없음)", "",
         f"- 기준 시각: {o['generated_at']} (일괄 등재 진행 중이라 수가 계속 늘어난다)",
         "- 출처별 wiki_catalog 행 수 / 그중 해 있음: " + " · ".join(f"{s} {n}/{o['catalog_dated'].get(s, 0)}" for s, n in sorted(o["catalog_rows"].items())),
         f"- 느낌·쓰임·말투(fit)가 붙은 표제어: {o['fit_terms']}개",
         f"- 한 시기의 표본이 {o['min_n']} 미만이면 '표본 적음'. 해의 뜻: 나무위키·pttpedia 는 분류의 해, wikidata 는 꼬리표, trendaword 는 소개된 호의 해.", ""]
    srcs = sorted(o["catalog_rows"])
    L += ["## 1. 해별 표제어 수 (출처별)", "", "| 해 | " + " | ".join(srcs) + " | 합 |", "|---|" + "---|" * (len(srcs) + 1)]
    for y, d in o["years"].items():
        L.append(f"| {y} | " + " | ".join(str(d.get(s, 0)) for s in srcs) + f" | {sum(d.values())} |")
    if o["decade_only"]:
        L.append("")
        L.append("연대만 알고 해는 모르는 행: " + ", ".join(f"{k} {v}" for k, v in o["decade_only"].items()))
    L += ["", "## 2. 시기 비교 (비중 = 그 항목 값이 있는 표제어 중 비율, 차 = 뒤 시기 − 앞 시기, 규칙)", ""]
    for g, gd in o["compare"].items():
        if g == "Trend A Word만":
            continue
        for pk, (title, _) in PERIODS.items():
            a, b = title.split(" vs ")
            L += [f"### {g} – {title}", "", "표본 수(값 있는 표제어): " + " · ".join(
                f"{lab} {a} {gd[pk][dim]['n'][a]}/{b} {gd[pk][dim]['n'][b]}" for dim, lab in DIMS), ""]
            for dim, lab in DIMS:
                dd = gd[pk][dim]
                if not dd["cells"]:
                    continue
                small = min(dd["n"].values()) < MIN_N
                cells = dd["cells"]
                pick = (cells[:3] + [c for c in cells[::-1][:3] if c["diff"] < 0]) if len(cells) > 3 else cells
                seen, rows = set(), []
                for c in pick:
                    if c["name"] not in seen:
                        seen.add(c["name"])
                        rows.append(c)
                L += [f"**{lab}**" + ("  (표본 적음)" if small else ""), "", f"| {lab} | {a} | {b} | 차 | 비고 |", "|---|---|---|---|---|"]
                for c in rows:
                    L.append(f"| {c['name']} | {pct(c['share_' + a])} ({c[a]}) | {pct(c['share_' + b])} ({c[b]}) | {c['diff'] * 100:+.0f}%p | {'표본 적음' if small else ''} |")
                L.append("")
    L += ["## 3. Trend A Word (한국) 해·분기별 느낌·쓰임", ""]
    tw = o["trendaword"]
    fe = [f for f, _ in Counter({x: v for k in tw.values() for x, v in k["feelings"].items()}).most_common(6)]
    us = [f for f, _ in Counter({x: v for k in tw.values() for x, v in k["uses"].items()}).most_common(6)]
    L += ["| 기간 | 호 수 | fit 붙은 수 | " + " | ".join(fe + us) + " | 비고 |", "|---|---|---|" + "---|" * (len(fe) + len(us) + 1)]
    for k, e in tw.items():
        f = lambda d, x: pct(d.get(x, 0)) if e["fit_n"] else "-"
        L.append(f"| {k} | {e['issues']} | {e['fit_n']} | " + " | ".join(f(e["feelings"], x) for x in fe) + " | " +
                 " | ".join(f(e["uses"], x) for x in us) + f" | {'표본 적음' if e['small'] else ''} |")
    L += ["", "(느낌 열 " + str(len(fe)) + "개 다음이 쓰임 열: " + ", ".join(fe) + " / " + ", ".join(us) + ")", ""]
    if o.get("peak_years"):
        L += ["## 4. 조회 관심 최고 연도 (위키백과 월별 조회수가 가장 높았던 달의 해, 실제 유행 시기와 구분)", "", "| 조회 관심 최고 연도 | 표제어 수 | 그중 출처에 해가 없는 것 |", "|---|---|---|"]
        L += [f"| {y} | {d['n']} | {d['no_source_year']} |" for y, d in o["peak_years"].items()]
        L.append("")
    return "\n".join(L + interpret(o)) + "\n"


def interpret(o: dict) -> list[str]:
    """숫자로 말할 수 있는 것만."""
    ys = o["years"]
    tot = sum(sum(d.values()) for d in ys.values())
    r20 = sum(sum(d.values()) for y, d in ys.items() if int(y) >= 2020)
    ns = o["compare"]["나무위키만"]["recent"]
    ai = next((c for c in ns["genres"]["cells"] if c["name"] == "생성형 인공지능 기반"), None)
    mu = next((c for c in ns["genres"]["cells"] if c["name"] == "음악"), None)
    us = next((c for c in ns["regions"]["cells"] if c["name"] == "US"), None)
    kr = next((c for c in ns["regions"]["cells"] if c["name"] == "KR"), None)
    tw = o["trendaword"]
    fit_taw = sum(e["fit_n"] for k, e in tw.items() if "Q" not in k)
    iss_taw = sum(e["issues"] for k, e in tw.items() if "Q" not in k)
    fn = o["compare"]["전체(출처 섞음, 같은 말 1회)"]["recent"]["feelings"]["n"]
    fa, fb = fn["2020~2022"], fn["2023~2026"]
    L = ["## 해석 (숫자로 말할 수 있는 것만)", ""]
    L.append(f"1. 해가 있는 {tot}행 중 {r20}행({pct(r20 / tot if tot else 0)})이 2020년 이후다. 2010년대 이전은 pttpedia·wikidata 위주라 '옛 밈이 적다' 가 아니라 '옛 밈을 담은 출처가 적다' 에 가깝다(표본 편향).")
    if ai and mu:
        L.append(f"2. 나무위키만 보면 2020~2022 → 2023~2026 에서 '생성형 인공지능 기반' 종류가 {ai['2020~2022']}개({pct(ai['share_2020~2022'])}) → {ai['2023~2026']}개({pct(ai['share_2023~2026'])})로 {ai['diff'] * 100:+.0f}%p 늘었다(표본 {ns['genres']['n']['2020~2022']}/{ns['genres']['n']['2023~2026']}). 음악은 {pct(mu['share_2020~2022'])} → {pct(mu['share_2023~2026'])}로 두 시기 모두 최대 종류다.")
    if us and kr:
        L.append(f"3. 나무위키의 나라 분류는 KR {pct(kr['share_2020~2022'])} → {pct(kr['share_2023~2026'])}({kr['diff'] * 100:+.0f}%p), US {pct(us['share_2020~2022'])} → {pct(us['share_2023~2026'])}({us['diff'] * 100:+.0f}%p). 다만 2020~2022 쪽 나라 표본이 {ns['regions']['n']['2020~2022']}개뿐이다.")
    # 숫자에 맞춰 말한다 — 문장을 고정해 두었더니 표와 어긋났다(10-01: 분기당 10~39개인데 '0~5개' 라고 적혔다)
    if min(fa, fb) < MIN_N:
        L.append(f"4. 느낌·쓰임·말투: fit 이 붙은 표제어 {o['fit_terms']}개, 해가 있는 것은 2020~2022 쪽 {fa}개·2023~2026 쪽 {fb}개다. 앞 시기가 {MIN_N}개 미만이라 시기 비교는 방향을 말할 수 없다.")
    else:
        L.append(f"4. 느낌·쓰임·말투: fit 이 붙은 표제어 {o['fit_terms']}개(2020~2022 쪽 {fa}개·2023~2026 쪽 {fb}개). 비교 표를 읽을 수 있다.")
    qn = [e["fit_n"] for k, e in tw.items() if "Q" in k]
    readable = sum(1 for n in qn if n >= MIN_N)
    L.append(f"5. Trend A Word: 호 {iss_taw}개 중 fit 이 붙은 것 {fit_taw}개, 분기당 fit {min(qn, default=0)}~{max(qn, default=0)}개. "
             f"{MIN_N}개 이상인 분기가 {readable}/{len(qn)}개라 " + ("그 분기끼리는 비교할 수 있다." if readable >= 2 else "분기별 변화는 아직 읽을 수 없다."))
    return L


if __name__ == "__main__":
    main()
