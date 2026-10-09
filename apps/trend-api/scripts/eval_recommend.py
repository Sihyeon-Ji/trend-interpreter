"""추천·만들기 품질 평가 (Plan 09). 시장 3곳 × 제품 4종 = 12개 사례를 실제 모델로 한 번 돌린다.

재는 것 — 규칙으로 잴 수 있는 것만 여기서 채운다. 사람이 볼 것(추천 적합도·바로 쓸 수 있는가·뜻 정확성·리스크 누락)은 빈칸으로 내보낸다.
  응답 시간(추천·만들기 각각 p50·최대), 모델 호출 수, 추천 수, 규칙 검사로 뺀 안(코드별), 추천의 리스크·생애주기 분포,
  현지 쓰임(국가별 해석)이 붙은 추천 비율, 후보가 없는 지역

  uv run scripts/eval_recommend.py                 # 설정된 대로(요청 때는 Gemini — 요청 장부 REQUEST_GEMINI_DAILY 안에서)
  uv run scripts/eval_recommend.py --local         # 로컬 Gemma 로만(개발 PC. Gemini 를 부르지 않는다)
  uv run scripts/eval_recommend.py --only KR       # 한 지역만
  uv run scripts/eval_recommend.py --briefs artifacts/eval/recommend-….json   # 그 실행의 제품 이해를 다시 쓴다(규칙만 견줄 때)

결과는 저장소 루트의 artifacts/eval/ 에 JSON 과 사람이 채울 CSV 로 남긴다(artifacts/ 는 커밋하지 않는다). 요약 수치만 Plan 09 에 옮긴다.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

from trend_agents.pipeline import generate, recommend
from trend_agents.schemas import ProductBrief
from trend_agents.storage import store as db

OUT = Path(__file__).resolve().parents[3] / "artifacts" / "eval"
# 만들기 화면의 시장과 같게(Plan 20: 한국·일본·영어권). TW·TH·ID 는 고를 수 없는 지역이라 후보가 2~9개뿐이었다(10-09)
REGIONS = ["KR", "JP", "GLOBAL"]
# 제품 4종 (Plan 09: 식품·화장품·패션·앱). 사진 대신 그 나라 마케터가 넣을 만한 문구로 돌린다.
PRODUCTS = {
    "food": "여름 한정 아이스 흑당 라떼. 더운 오후 한 잔으로 기분 전환",
    "cosmetics": "촉촉한 수분 쿠션 신제품. 하루 종일 무너지지 않는 피부 표현",
    "fashion": "가볍고 편한 러닝화. 출근길에도 운동할 때도",
    "app": "친구와 함께 모으는 가계부 앱. 이번 달 목표 달성하면 보상",
}
TONE = "friendly"


def run_case(con, region: str, kind: str, text: str, given: ProductBrief | None = None) -> dict:
    row: dict = {"region": region, "product": kind, "text": text}
    row["candidates"] = recommend.ready(con, [region])
    if not row["candidates"]:
        row["status"] = "후보 없음"
        return row
    t0 = time.time()
    try:
        # 제품 이해는 실행마다 느낌 태그가 달라진다(10-09: 러닝화가 '편안함·공감' → '편안함·멋짐' 이 되자 '인정' 이 빠졌다) — 규칙을 견줄 때는 고정한다
        brief, source = (given, "given") if given else recommend.understand(con, text, None, "ko")
        res = recommend.recommend(con, brief, source, [region], TONE)
    except Exception as e:
        row["status"] = f"추천 실패: {type(e).__name__}"
        return row
    row["recommend_s"] = round(time.time() - t0, 1)
    row["brief"], row["brief_source"] = brief.model_dump(), source
    row["items"] = [{"canonical": i.canonical, "score": i.score, "risk": i.risk_level, "lifecycle": i.lifecycle, "diffusion": i.diffusion,
                     "local_note": i.local_note.ko if i.local_note else None, "write_regions": i.write_regions,
                     "evidences": [e.url for e in i.evidences]} for i in res.items]
    picks = [i.term_id for i in res.items if region in i.write_regions][:2]
    if not picks:
        row["status"] = "추천 0" if not res.items else "그 지역 말로 쓸 밈 없음"
        return row
    t0 = time.time()
    try:
        gen = generate.run(con, picks, brief, region, TONE, "ko")
    except Exception as e:
        row["status"] = f"만들기 실패: {type(e).__name__}: {str(e)[:60]}"
        return row
    row["generate_s"] = round(time.time() - t0, 1)
    row["model_calls"] = gen.model_calls
    row["generation"] = {"source": gen.source, "language": gen.language, "memes": gen.memes, "copies": [c.model_dump() for c in gen.copies],
                         "script": gen.script.model_dump() if gen.script else None, "thumbnail": gen.thumbnail.model_dump() if gen.thumbnail else None,
                         "dropped": [d.model_dump() for d in gen.dropped]}
    row["status"] = "ok"
    return row


def summary(rows: list[dict]) -> str:
    ok = [r for r in rows if r.get("status") == "ok"]
    rec = [r["recommend_s"] for r in rows if "recommend_s" in r]
    gen = [r["generate_s"] for r in ok]
    items = [i for r in rows for i in r.get("items", [])]
    out = [f"사례 {len(rows)} · 끝까지 된 것 {len(ok)} · 후보 없는 사례 {sum(1 for r in rows if r.get('status') == '후보 없음')}"]
    if rec:
        out.append(f"추천 시간 p50 {statistics.median(rec):.1f}초 · 최대 {max(rec):.1f}초")
    if gen:
        out.append(f"만들기 시간 p50 {statistics.median(gen):.1f}초 · 최대 {max(gen):.1f}초 · 모델 호출 평균 {statistics.mean(r['model_calls'] for r in ok):.1f}회")
    if items:
        out.append(f"추천 {len(items)}개 · 리스크 {dict(Counter(i['risk'] for i in items))} · 생애주기 {dict(Counter(i['lifecycle'] for i in items))}")
        out.append(f"현지 쓰임이 붙은 추천 {sum(1 for i in items if i['local_note'])}/{len(items)}")
    drops = [d["code"] for r in ok for d in r["generation"]["dropped"]]
    if ok:
        out.append(f"만들기에서 뺀 안 {len(drops)}건 / 사례 {len(ok)}개 · 코드 {dict(Counter(drops))}")
    for region in REGIONS:
        rs = [r for r in rows if r["region"] == region]
        if rs:
            out.append(f"  {region}: " + ", ".join(f"{r['product']}={r.get('status')}({len(r.get('items', []))})" for r in rs))
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="로컬 Gemma 로만 (Gemini 를 부르지 않는다)")
    ap.add_argument("--only", help="한 지역만")
    ap.add_argument("--briefs", help="이전 결과 JSON — 그 실행의 제품 이해(brief)를 제품마다 다시 쓴다")
    a = ap.parse_args()
    briefs = {r["product"]: ProductBrief.model_validate(r["brief"]) for r in json.loads(Path(a.briefs).read_text(encoding="utf-8"))
              if r.get("brief")} if a.briefs else {}
    if a.local:
        from trend_agents.pipeline import gemini

        generate.configured = recommend.configured = gemini.configured = lambda: False
    con = db.connect()
    rows = []
    for region in ([a.only] if a.only else REGIONS):
        for kind, text in PRODUCTS.items():
            r = run_case(con, region, kind, text, briefs.get(kind))
            print(f"{region} {kind:9s} {r.get('status')} 추천 {len(r.get('items', []))} {r.get('recommend_s', '-')}s 만들기 {r.get('generate_s', '-')}s", flush=True)
            rows.append(r)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"recommend-{stamp}.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    with open(OUT / f"recommend-{stamp}-judge.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["지역", "제품", "추천(상위 5)", "어울리는 수(0~5, 사람)", "위험한데 없음으로 나온 수(사람)", "뜻대로 썼나(카피, 사람)", "카피 바로 쓸 수 있나(1~3, 사람)", "메모"])
        for r in rows:
            w.writerow([r["region"], r["product"], " / ".join(i["canonical"] for i in r.get("items", [])), "", "", "", "", r.get("status")])
    print("\n" + summary(rows))
    print(f"\n결과 {OUT}/recommend-{stamp}.json · 사람이 채울 표 {OUT}/recommend-{stamp}-judge.csv")


if __name__ == "__main__":
    main()
