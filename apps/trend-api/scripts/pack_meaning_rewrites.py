"""사람이 ok 로 확정한 '다시 쓴 뜻' 을 승인 배치(ChangeBatch)로 포장한다(Plan 16 10-07). DB·모델을 바꾸지 않는다.

  DATABASE_URL=<다시 쓴 뜻이 든 연구 DB> uv run scripts/pack_meaning_rewrites.py \\
    --review artifacts/meaning-review/rewrite-trial/review-all.csv \\
    --baseline-url postgresql://.../trend_research_stage \\   # 같은 snapshot 의 손대지 않은 사본 – expected_meaning_id·근거의 기준
    --snapshot-id 20261006T224515-8b2a19c --snapshot-sha256 <trend-latest.db 의 SHA-256> \\
    --model-id "local:gemma4:12b@<digest>" --prompt-version research.OFFLINE_PROMPT@<commit> --rule-version audit.rule_overrides@<commit> \\
    --batch-id meaning-rewrite-20261007 --out /private/batch.json

항목마다: term_id, expected_meaning_id(기준 사본의 현재 뜻 판), meaning(다시 쓴 뜻의 MeaningDraft 칸), 다시 쓰기가 새로 찾은 근거(evidences),
그 가운데 인용(citations). 사람이 확인한 뜻·검수 대기·기준이 다른 말은 포장 단계에서 뺀다(게시 도구가 어차피 막는다). 출력 파일은 0600 으로 독점 생성.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.schemas import MeaningDraft  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import publications as pub  # noqa: E402
from trend_agents.storage import db as rawdb  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", required=True)
    ap.add_argument("--baseline-url", required=True)
    ap.add_argument("--snapshot-id", required=True)
    ap.add_argument("--snapshot-sha256", required=True)
    ap.add_argument("--model-id", required=True)
    ap.add_argument("--prompt-version", required=True)
    ap.add_argument("--rule-version", required=True)
    ap.add_argument("--batch-id", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=1000)
    a = ap.parse_args()

    rows = [r for r in csv.DictReader(open(a.review, encoding="utf-8-sig")) if r.get("label(ok/fix)", "").strip().lower() == "ok"][:a.limit]
    src = db.connect()
    base = rawdb.connect(url=a.baseline_url)
    items, skipped = [], {}
    for r in rows:
        tid = r["term_id"]
        new = ds.current_meaning(src, tid)
        old = ds.current_meaning(base, tid)
        t = ds.get_term(base, tid)
        if not new or not old or not t:
            skipped[tid] = "missing"; continue
        if new.meaning_id == old.meaning_id:
            skipped[tid] = "unchanged"; continue
        if old.verification == "verified_human" or ds.under_review(base, tid):
            skipped[tid] = "human_or_review"; continue
        draft = MeaningDraft.model_validate(new.model_dump(include=set(MeaningDraft.model_fields), mode="json"))
        base_urls = {e.url for e in ds.list_evidences(base, tid)}
        new_evs = [e for e in ds.list_evidences(src, tid) if e.url not in base_urls]
        known = base_urls | {e.url for e in new_evs}
        citations = [u for u in new.citations if u in known]
        items.append(pub.ChangeItem(term_id=tid, expected_meaning_id=old.meaning_id, meaning=draft, evidences=new_evs, citations=citations))
    if not items:
        sys.exit("포장할 항목이 없다")
    batch = pub.ChangeBatch(batch_id=a.batch_id, snapshot_id=a.snapshot_id, snapshot_sha256=a.snapshot_sha256, model_id=a.model_id,
                            prompt_version=a.prompt_version, rule_version=a.rule_version, items=items)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(a.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(pub.canonical(batch))
    print(json.dumps({"batch_id": batch.batch_id, "payload_sha256": pub.digest(batch), "items": len(items), "skipped": skipped,
                      "new_evidences": sum(len(i.evidences) for i in items), "citations": sum(len(i.citations) for i in items)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
