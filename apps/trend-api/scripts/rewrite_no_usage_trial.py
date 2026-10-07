"""쓰임 없는 뜻 다시 쓰기 시험(Plan 16, 10-07). 수집 서버 코드는 건드리지 않고 저장소의 감사 경로(audit.audit_one → research_one(lean))를
연구 DB 사본에서 돌려, 대상 설명뿐인 뜻(verification.no_usage_meaning)에 쓰임이 붙는지 잰다.

재료: 참고 문서 문장(감사 경로 그대로) + 수집 서버 밈 확인이 문서에서 찾은 인용문(--meme-check <snapshot SQLite>, 있을 때).
인용문은 첫 문서 글 앞에 한 문장으로 덧붙여 감사관과 다시 쓰기가 같이 본다(audit.documents 를 감싼다 – 시험 전용, 서버 코드와 무관).

  USE_LOCAL_GEMMA=1 MODEL_REQUESTS_ENABLED=false DATABASE_URL=postgresql://.../trend_research_xxx \\
    uv run scripts/rewrite_no_usage_trial.py --meme-check ~/trend-research/20261006b/trend-latest.db --in-use --limit 10 --out artifacts/meaning-review/rewrite-trial

결과는 --out 아래 <시각>/results.jsonl·review.csv 에만 남긴다. DB 는 연구 사본이어야 한다(운영·수집 DB 금지 – 스크립트가 이름에 research 가 없으면 멈춘다).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.config import DATABASE_URL  # noqa: E402
from trend_agents.pipeline import audit  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402
from trend_agents.verification import no_usage_meaning  # noqa: E402

ACTIVE = {"emerging", "rising", "peak", "steady"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meme-check", help="수집 서버 snapshot SQLite(meme_check 표) – 인용문을 재료로")
    ap.add_argument("--in-use", action="store_true", help="'쓰이는 중' 생애주기만")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--terms", help="쉼표로 표제어 지정(그 말만)")
    ap.add_argument("--out", default="artifacts/meaning-review/rewrite-trial")
    ap.add_argument("--dry-run", action="store_true", help="대상만 보이고 모델은 부르지 않는다")
    ap.add_argument("--skip-results", action="append", default=[], help="이전 실행의 results.jsonl – 거기 든 말은 건너뛴다")
    a = ap.parse_args()
    if "research" not in DATABASE_URL:
        sys.exit("연구 DB 사본에서만 돌린다(DATABASE_URL 에 research 가 없다)")
    if os.getenv("USE_LOCAL_GEMMA") != "1" and not a.dry_run:
        sys.exit("USE_LOCAL_GEMMA=1 로 로컬 Gemma 를 쓴다(Gemini 는 부르지 않는다)")

    quotes: dict[str, tuple[str, str]] = {}
    if a.meme_check:
        sq = sqlite3.connect(a.meme_check)
        quotes = {t: (v, q or "") for t, v, q in sq.execute("SELECT term_id, verdict, quote FROM meme_check")}

    skip = {json.loads(line)["term_id"] for f in a.skip_results for line in Path(f).read_text(encoding="utf-8").splitlines() if line.strip()}
    con = db.connect()
    cat = {t for (t,) in con.execute("SELECT DISTINCT term_id FROM wiki_catalog").fetchall()}
    picks = []
    want = {x.strip() for x in a.terms.split(",")} if a.terms else None
    for t in ds.list_terms(con, ("verified",)):
        if want and t.canonical not in want or t.term_id in skip:
            continue
        if a.in_use and t.lifecycle not in ACTIVE:
            continue
        m = ds.current_meaning(con, t.term_id)
        if not m or m.verification == "verified_human":
            continue
        if t.term_id in cat and no_usage_meaning(m.definition):
            picks.append((t, m))
        if len(picks) >= a.limit:
            break
    print(f"대상 {len(picks)}개 (쓰임 없는 자동 확인 뜻, 위키 분류{' · 쓰이는 중' if a.in_use else ''})", flush=True)
    if a.dry_run:
        for t, m in picks:
            q = quotes.get(t.term_id, ("", ""))
            print(f"  {t.canonical:14} [{q[0] or '-'}] {(m.definition or '')[:50]!r} | 인용문: {q[1][:50]!r}")
        return

    out = Path(a.out) / datetime.now().strftime("%Y%m%d_%H%M")
    out.mkdir(parents=True, exist_ok=True)
    real_documents = audit.documents

    current_quote = {"text": ""}

    def documents_with_quote(term, evidences):
        docs = real_documents(term, evidences)
        q = current_quote["text"]
        if q and docs:
            e, text = docs[0]
            docs[0] = (e, f"(이 문서에서 밈 쓰임을 말한 문장) {q}. {text}")
        return docs

    audit.documents = documents_with_quote
    rows = []
    with (out / "results.jsonl").open("w", encoding="utf-8") as f:
        for i, (t, m) in enumerate(picks, 1):
            verdict, quote = quotes.get(t.term_id, ("", ""))
            current_quote["text"] = quote if verdict == "meme" else ""
            t0 = time.time()
            try:
                result = audit.audit_one(con, ds.get_term(con, t.term_id))
            except Exception as e:
                result = f"error:{type(e).__name__}"
            after = ds.current_meaning(con, t.term_id)
            changed = bool(after and after.meaning_id != m.meaning_id)
            usage_now = bool(after and not no_usage_meaning(after.definition))
            row = {"term_id": t.term_id, "term": t.canonical, "lang": t.lang, "lifecycle": t.lifecycle, "result": result,
                   "quote_used": bool(current_quote["text"]), "meme_check": verdict, "changed": changed, "usage_after": usage_now,
                   "before": m.definition, "after": after.definition if after else None, "after_verification": after.verification if after else None,
                   "seconds": round(time.time() - t0, 1)}
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i}/{len(picks)}] {t.canonical} → {result} {'(바뀜' + (', 쓰임 있음)' if usage_now else ', 쓰임 없음)') if changed else ''} {row['seconds']}s", flush=True)
    audit.documents = real_documents

    with (out / "review.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["term_id", "term", "result", "quote_used", "before", "after", "usage_after", "label(ok/fix)", "note"])
        for r in rows:
            w.writerow([r["term_id"], r["term"], r["result"], "Y" if r["quote_used"] else "", r["before"], r["after"] or "", "Y" if r["usage_after"] else "", "", ""])
    n = len(rows)
    print(f"\n끝 – {n}개: 바뀜 {sum(r['changed'] for r in rows)}, 바뀐 뒤 쓰임 있음 {sum(r['usage_after'] and r['changed'] for r in rows)}, "
          f"인용문 씀 {sum(r['quote_used'] for r in rows)}, 결과 {dict((k, sum(1 for r in rows if r['result'] == k)) for k in {r['result'] for r in rows})}")
    print("저장:", out)


if __name__ == "__main__":
    main()
