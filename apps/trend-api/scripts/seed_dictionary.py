"""조사해서 만든 사전(apps/trend-web/lib/sample → data/seed/dictionary.json)을 실DB 에 '팀이 확인한 항목(verified_human, created_by=team)' 으로 심는다.

가정치였던 주간 수치·비중은 심지 않는다 — track(언급 실측)·naver(세대 실측) 단계가 채운다. 이미 있는 용어는 건너뛴다.
사용: pnpm -C ../trend-web dlx tsx scripts/export-sample.ts && uv run scripts/seed_dictionary.py
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from trend_agents.schemas import Evidence, MeaningDraft, MeaningText, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import sqlite_store as db

ROOT = Path(__file__).resolve().parents[1]
CATEGORY = {"slang": "slang", "meme": "meme", "song": "song", "other": "other"}


def dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def main() -> None:
    data = json.loads((ROOT / "data" / "seed" / "dictionary.json").read_text())
    con = db.connect()
    added = skipped = 0
    for rec in data["records"]:
        t = rec["term"]
        if ds.find_term(con, t["canonical"]):
            skipped += 1
            continue
        status = t.get("status", "verified")
        term = Term(term_id=t["term_id"], canonical=t["canonical"], lang=t.get("lang", "ko"), aliases=t.get("aliases", []), category=CATEGORY.get(rec.get("category", "slang"), "other"),
                    status=status, lifecycle=t.get("lifecycle", "unknown"), first_seen=dt(t.get("first_seen")), last_seen=dt(t.get("last_seen")))
        ds.upsert_term(con, term)
        for m in sorted(rec["meanings"], key=lambda x: x["version"]):
            draft = MeaningDraft(definition=m["definition"], expansion=m.get("expansion"), origin=m.get("origin", "unknown"), nuance=m.get("nuance", ""),
                                 generations=m.get("generations", ["all"]), regions=m.get("regions", ["KR"]), self_confidence=m.get("confidence", 0.8))
            verification = "verified_human" if status == "verified" else "unverified"
            ds.add_meaning(con, term.term_id, draft, verification, m.get("citations", []), created_by="team")
        evs = []
        for e in rec.get("evidences", []):
            evs.append(Evidence(evidence_id=e["evidence_id"], kind=e["kind"], url=e["url"], title=e.get("title", ""), source_domain=e["source_domain"],
                                observed_at=dt(e.get("observed_at")) or datetime.now(timezone.utc), excerpt=e.get("excerpt", "")))
        ds.add_evidences(con, term.term_id, evs)
        # 세대×국가 사용: 조사로 본 조합만, 비중은 균등(실측 전)
        segs = [(u["segment"]["generation"], u["segment"]["region"], u.get("first_seen", "")[:10] or datetime.now(timezone.utc).date().isoformat()) for u in rec.get("usage", [])]
        if segs:
            ds.set_usage(con, term.term_id, [(g, r, f, round(1 / len(segs), 3)) for g, r, f in segs])
        cur = ds.current_meaning(con, term.term_id)
        if cur:
            ds.set_translation(con, term.term_id, "ko", MeaningText(definition=cur.definition, expansion=cur.expansion, origin=cur.origin, nuance=cur.nuance, plain=rec.get("plain") or None), "team")
            if rec.get("en"):
                ds.set_translation(con, term.term_id, "en", MeaningText(**rec["en"]), "team")
        if status == "needs_review":
            q = next((x for x in data.get("queue", []) if x["term_id"] == term.term_id), None)
            if cur:
                ds.queue_review(con, term.term_id, MeaningDraft(**{k: getattr(cur, k) for k in MeaningDraft.model_fields}), (q or {}).get("reasons", rec.get("gate_reasons") or ["팀 검수 대기"]), len(evs))
        added += 1
    print(f"seeded {added}, skipped {skipped} (already present); terms now {len(ds.list_terms(con))}")


if __name__ == "__main__":
    main()
