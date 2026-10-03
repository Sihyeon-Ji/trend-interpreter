"""밈 여부 평가 표본 — 대시보드 거르기 규칙(dashboard.meme_use)의 정밀도·재현율을 사람이 붙인 정답으로 재기 위한 것.
고른 지역의 대시보드 카드(거른 것 포함)를 묶음별로 뽑는다. 거른 것에서 진짜 밈이 얼마나 빠졌나(정밀도), 남은 것에 밈 아닌 말이
얼마나 남았나(재현율), 화면 첫 쪽이 얼마나 깨끗한가(상위 정밀도)를 한 번에 잰다.

  uv run scripts/export_meme_eval_sample.py                          # 한국, 묶음마다 50개
  uv run scripts/export_meme_eval_sample.py --region JP --per-bucket 40 --seed 7

묶음(bucket):
  top              화면 '지금 쓰이는 밈' 첫 쪽(dashboard.LIST_MAX 개) 전부
  held_audit       감사관이 '밈으로 어떻게 쓰이는지가 없다' 로 남겨 뺀 것
  held_no_evidence 위키 분류에서만 들어와 리스크 점검 뒤에도 쓰인 글이 0건이라 뺀 것
  kept_confirmed   남긴 것 가운데 그 뜻으로 쓰인 글이 확인된 것(top 제외)
  kept_unconfirmed 남긴 것 가운데 아직 확인 전이라 뒤로 보낸 것(top 제외)

결과는 저장소 루트의 artifacts/meme_eval/<지역>-<시각>/ 에 둔다(artifacts/ 는 커밋하지 않는다):
  label.csv  사람이 채울 표. 묶음·규칙 판정을 숨기고 순서를 섞었다 — 판정을 보고 라벨이 기울지 않게. label(·label2)·note 칸을 채운다
  key.csv    같은 no 의 묶음·가중치·규칙 신호. 채점 때 label.csv 와 no 로 맞춘다
  GUIDE.md   라벨 기준
Excel 에서 바로 열리도록 UTF-8(BOM)으로 쓴다. 사용자 입력 표(explain_cache·lookups·reader_prefs)는 읽지 않는다.
커뮤니티·SNS 글은 예시 문장으로 넣지 않는다(ADR 0003) — 기사·쇼츠·위키 문서만.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime
from pathlib import Path

from trend_agents.collectors.community import is_community_post
from trend_agents.pipeline import dashboard
from trend_agents.pipeline.audit import NO_USAGE
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts" / "meme_eval"
BUCKETS = ("top", "held_audit", "held_no_evidence", "kept_confirmed", "kept_unconfirmed")
LABEL_FIELDS = ["no", "term", "lang", "definition", "origin", "doc_url", "example", "example_url", "label", "label2", "note"]
KEY_FIELDS = ["no", "term_id", "term", "bucket", "population", "sampled", "weight", "shown_rank", "held", "hold_reason",
              "use_confirmed", "mentions_mixed", "labels_on", "labels_off", "risk_level", "lifecycle", "diffusion", "mentions_4w",
              "wiki_sources", "wiki_categories", "meaning_verification"]

GUIDE = """# 밈 여부 라벨 기준

`label.csv` 의 `label` 칸에 아래 다섯 가운데 하나를 적는다. 둘째 사람은 `label2` 에 적는다(첫째 사람의 라벨을 보지 않고).
판단이 갈리거나 실제 밈 문구가 따로 있으면 `note` 에 적는다.

| label | 뜻 |
| --- | --- |
| `expr` | 표현·유행어 – 문장 속에서 그 뜻으로 가져다 쓰는 말 (예: 럭키비키, 갑툭튀) |
| `meme_name` | 밈 자체의 이름 – 그 이름을 대화에서 밈으로 부른다 (예: 스키비디 토일렛) |
| `topic` | 밈의 소재가 된 대상 – 인물·작품·노래·사건·브랜드. 그 대상의 대사·장면이 밈이어도 이름 자체는 `topic` |
| `word` | 일반 단어·고유명사 – 밈으로서의 쓰임이 따로 없다 |
| `unsure` | 자료만으로 판단하기 어렵다 |

기준이 되는 물음: **브랜드가 카피·SNS 에서 이 표제어를 그대로 밈으로 가져다 쓸 수 있나.** `expr`·`meme_name` 이면 밈, `topic`·`word` 면 밈이 아니다.

- **표제어 그대로 판정한다.** 밈 문구의 재료일 뿐인 말은 밈이 아니다 – 나무위키 '토마토' 문서는 '인터넷 밈/음식/호불호' 분류에 있지만
  밈은 '토맛토마토 vs 토마토맛토' 이고 '토마토' 는 `word`. 이럴 때 `note` 에 실제 밈 문구를 적는다(새 표제어 후보가 된다).
- **뜻풀이(`definition`)가 아니라 말 자체를 본다.** 뜻풀이가 사전식(식물 설명·인물 약력)이어도 실제로 밈으로 쓰이는 말이면 밈이다.
- `topic` 과 `meme_name` 이 헷갈리면: 그 이름만으로 농담·반응이 되나(“완전 스키비디네”) → `meme_name`, 대사·장면을 인용해야 밈이 되나 → `topic`.
- 위의 예는 기준을 설명하려는 것이고 정답 목록이 아니다. 표본에 같은 말이 나오면 자료를 보고 다시 판단한다.

`doc_url`(참고 위키)과 `example`(기사·쇼츠 제목)을 보고, 모르면 검색해도 된다. 한 사람이 한 번에 끝까지 붙이고,
둘째 사람이 `unsure` 와 무작위 20개 이상을 `label2` 에 따로 붙인다. 채점은 `score_meme_eval.py` 가 한다(두 사람 일치율·카파 포함).
"""


def _wiki(con, term_id: str) -> tuple[list[str], list[str]]:
    rows = con.execute("SELECT source, categories_json FROM wiki_catalog WHERE term_id=?", (term_id,)).fetchall()
    sources = sorted({s for s, _ in rows})
    cats = sorted({c for _, cj in rows for c in json.loads(cj or "[]") if not c.startswith("region:")})
    return sources, cats


def _audit_flagged(con, term_id: str, meaning_id: str | None) -> bool:
    if not meaning_id:
        return False
    row = con.execute("SELECT action, reasons_json FROM audit_log WHERE term_id=? AND meaning_id=?", (term_id, meaning_id)).fetchone()
    return bool(row) and row[0] == "flagged" and NO_USAGE in json.loads(row[1] or "[]")


def _examples(con, t) -> tuple[str, str, str]:
    """(참고 위키 주소, 예시 제목, 예시 주소) — 위키 문서와, 표제어가 든 기사·쇼츠 가운데 가장 최근 것. 커뮤니티 글은 쓰지 않는다."""
    from trend_agents.pipeline.match import mentions

    evs = [e for e in ds.list_evidences(con, t.term_id) if not is_community_post(e) and not e.source_domain.startswith("naver")]
    doc = next((e.url for e in evs if e.kind == "wiki" and dashboard._has_path(e.url)), "")
    used = sorted((e for e in evs if e.kind in ("news", "short") and mentions(f"{e.title or ''} {e.excerpt or ''}", t.canonical, t.aliases)),
                  key=lambda e: e.observed_at, reverse=True)
    return doc, ((used[0].title or used[0].excerpt or "")[:160] if used else ""), (used[0].url if used else "")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="KR")
    ap.add_argument("--per-bucket", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261003)
    a = ap.parse_args()
    region = a.region.upper()
    con = db.connect()

    loaded = dashboard._load(con)
    if not loaded:
        raise SystemExit("대시보드 캐시가 없습니다. 먼저 run_pipeline.py --stages dashboard 를 돌리세요.")
    stored = [s for s in dashboard._live(con, loaded[0]) if dashboard._browsable(s.card) and region in s.card.regions]
    cards = {s.card.term_id: (s, dashboard.view(s, [region])) for s in stored}
    rising, _, _ = dashboard.split([c for s, c in cards.values() if not s.held], loaded[1])
    rank = {c.term_id: i for i, c in enumerate(rising, 1)}
    top = {c.term_id for c in rising[:dashboard.LIST_MAX]}

    groups: dict[str, list[str]] = {b: [] for b in BUCKETS}
    info: dict[str, dict] = {}
    for tid, (s, c) in cards.items():
        t = ds.get_term(con, tid)
        m = ds.current_meaning(con, tid)
        audit = _audit_flagged(con, tid, m.meaning_id if m else None)
        labels = ds.evidence_labels(con, tid)
        on = sum(1 for p, _ in labels.values() if p != "offtopic")
        if s.held:
            bucket, reason = ("held_audit", "audit") if audit else ("held_no_evidence", "no_evidence")
        else:
            bucket, reason = ("top" if tid in top else "kept_confirmed" if c.use_confirmed else "kept_unconfirmed"), ""
        groups[bucket].append(tid)
        info[tid] = {"t": t, "m": m, "c": c, "held": int(s.held), "reason": reason, "on": on, "off": len(labels) - on}

    rnd = random.Random(a.seed)
    picked: list[tuple[str, str]] = []
    sizes = {}
    for b in BUCKETS:
        ids = sorted(groups[b])
        take = ids if b == "top" else rnd.sample(ids, min(a.per_bucket, len(ids)))
        sizes[b] = (len(ids), len(take))
        picked += [(b, tid) for tid in take]
    rnd.shuffle(picked)

    out = OUT / f"{region}-{datetime.now().strftime('%Y%m%d-%H%M')}"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "label.csv", "w", newline="", encoding="utf-8-sig") as lf, open(out / "key.csv", "w", newline="", encoding="utf-8-sig") as kf:
        lw, kw = csv.DictWriter(lf, LABEL_FIELDS), csv.DictWriter(kf, KEY_FIELDS)
        lw.writeheader()
        kw.writeheader()
        for no, (b, tid) in enumerate(picked, 1):
            x = info[tid]
            t, m, c = x["t"], x["m"], x["c"]
            doc, ex, ex_url = _examples(con, t)
            sources, cats = _wiki(con, tid)
            pop, n = sizes[b]
            lw.writerow({"no": no, "term": t.canonical, "lang": t.lang, "definition": c.gloss_ko[:300], "origin": (m.origin if m else "")[:200],
                         "doc_url": doc, "example": ex, "example_url": ex_url, "label": "", "label2": "", "note": ""})
            kw.writerow({"no": no, "term_id": tid, "term": t.canonical, "bucket": b, "population": pop, "sampled": n,
                         "weight": round(pop / n, 3) if n else 0, "shown_rank": rank.get(tid, ""), "held": x["held"], "hold_reason": x["reason"],
                         "use_confirmed": int(c.use_confirmed), "mentions_mixed": int(c.mentions_mixed), "labels_on": x["on"],
                         "labels_off": x["off"], "risk_level": c.risk_level or "", "lifecycle": c.lifecycle, "diffusion": c.diffusion or "",
                         "mentions_4w": c.mentions_4w, "wiki_sources": "|".join(sources), "wiki_categories": "|".join(cats)[:300],
                         "meaning_verification": m.verification if m else ""})
    (out / "GUIDE.md").write_text(GUIDE, encoding="utf-8")
    print(f"{region} 카드 {len(cards)}개 (캐시 {loaded[1].isoformat(timespec='minutes')}) → 표본 {len(picked)}개")
    for b in BUCKETS:
        print(f"  {b:18} 모집단 {sizes[b][0]:5}  표본 {sizes[b][1]:3}")
    print(f"→ {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
