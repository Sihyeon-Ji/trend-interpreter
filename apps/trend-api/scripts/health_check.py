"""사전·파이프라인 건강 점검. cron 이 하루 한 번 돌리고, 사람은 로그만 본다.

보는 것은 **규칙으로 판정 가능한 것**뿐이다. '좋아 보인다' 는 기준이 못 된다.
지표가 선을 넘으면 경고를 찍는다 — 조용히 나빠지는 것을 막는 게 목적이다
(2026-09-16: 조사 프롬프트가 몇 주 동안 빈 뜻을 만들고 있었는데 아무도 몰랐다).

  uv run scripts/health_check.py            # 사람이 읽는 표
  uv run scripts/health_check.py --json     # 기계가 읽는 한 줄 (추이 비교용)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.config import GEMINI_DAILY_BUDGET  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import sqlite_store as db  # noqa: E402

# 선을 넘으면 경고. 근거는 2026-09-16 전수 검토에서 잡은 실제 사고들.
LIMITS = {
    "stale_hours": 8,          # 파이프라인이 이보다 오래 안 돌면 멈춘 것이다
    "empty_def_ratio": 0.02,   # **화면에 나가는** 표제어 중 뜻이 쓸 수 없는 비율 (게이트가 막아야 한다)
    "untranslated": 0,         # 한국어 화면에 외국어 뜻이 그대로 나가는 표제어 수
    "verified_min": 60,        # 화면에 나갈 검증된 표제어 수
}
_UNUSABLE = re.compile(r"근거 부족|명확한 (사전적 )?(정의|의미)(는|가)? ?없")
_JA = re.compile(r"[ぁ-ゟ゠-ヿ]")
_KO = re.compile(r"[가-힣]")


def collect(con) -> dict:
    now = datetime.now(timezone.utc)
    m: dict = {"at": now.isoformat(timespec="seconds")}

    last = con.execute("SELECT MAX(finished_at) FROM pipeline_runs").fetchone()[0]
    m["last_run"] = last
    m["stale_hours"] = round((now - datetime.fromisoformat(last)).total_seconds() / 3600, 1) if last else 999

    day = now.date().isoformat()
    since = (now - timedelta(hours=24)).isoformat()
    m["stages_24h"] = {s: (c, st) for s, c, st in con.execute(
        "SELECT stage, count, status FROM pipeline_runs WHERE finished_at >= ? "
        "GROUP BY stage HAVING MAX(finished_at)", (since,)).fetchall()}
    m["errors_24h"] = [s for s, (_, st) in m["stages_24h"].items() if st == "error"]

    by_status = dict(con.execute("SELECT status, COUNT(*) FROM terms GROUP BY status").fetchall())
    m["terms"] = by_status
    m["verified"] = by_status.get("verified", 0)
    m["candidates_waiting"] = con.execute("SELECT COUNT(*) FROM candidates WHERE status='new'").fetchone()[0]

    # 화면에 나가는 것(verified)과 대기 중인 것(needs_review)을 갈라 센다.
    # 검수 대기에 쓸 수 없는 뜻이 있는 건 큐가 제 일을 하는 것이고, 화면에 있으면 사고다.
    seen_empty = seen_good = queued_empty = untranslated = 0
    for t in ds.list_terms(con, ("verified", "needs_review")):
        mm = ds.current_meaning(con, t.term_id)
        d = (mm.definition if mm else "").strip()
        bad = len(d) < 8 or bool(_UNUSABLE.search(d))
        if t.status != "verified":
            queued_empty += bad
            continue
        if bad:
            seen_empty += 1
            continue
        seen_good += 1
        ko = ds.get_translation(con, t.term_id, "ko")
        shown = (ko.definition if ko else d) or ""
        if _JA.search(shown) and not _KO.search(shown):
            untranslated += 1
    m["def_good"], m["def_empty"] = seen_good, seen_empty
    m["queued_empty"] = queued_empty
    m["empty_def_ratio"] = round(seen_empty / max(1, seen_good + seen_empty), 3)
    m["untranslated"] = untranslated

    m["media_terms"] = con.execute("SELECT COUNT(DISTINCT term_id) FROM term_media").fetchone()[0]
    m["gemini_used_today"] = (con.execute("SELECT count FROM gemini_calls WHERE day=?", (day,)).fetchone() or [0])[0]
    m["gemini_budget"] = GEMINI_DAILY_BUDGET
    m["open_reviews"] = con.execute("SELECT COUNT(*) FROM review_queue WHERE decision IS NULL").fetchone()[0]
    m["unanswered_questions"] = con.execute("SELECT COUNT(*) FROM lookups").fetchone()[0]

    # 최근 조사 통과율 — 게이트가 갑자기 다 막거나 다 열면 무언가 망가진 것이다
    rows = con.execute("SELECT verification FROM research_log WHERE researched_at >= ? ", (since,)).fetchall()
    passed = sum(1 for (v,) in rows if v == "verified_auto")
    m["research_24h"] = len(rows)
    m["gate_pass_ratio"] = round(passed / len(rows), 3) if rows else None
    return m


def warnings(m: dict) -> list[str]:
    out = []
    if m["stale_hours"] > LIMITS["stale_hours"]:
        out.append(f"파이프라인이 {m['stale_hours']}시간째 안 돌았다 (한계 {LIMITS['stale_hours']})")
    if m["errors_24h"]:
        out.append(f"하루 안에 실패한 단계: {', '.join(m['errors_24h'])}")
    if m["empty_def_ratio"] > LIMITS["empty_def_ratio"]:
        out.append(f"화면에 나가는 표제어 {m['def_empty']}개의 뜻이 쓸 수 없다 ({m['empty_def_ratio']:.0%}) — 게이트가 놓쳤다")
    if m["untranslated"] > LIMITS["untranslated"]:
        out.append(f"한국어 화면에 외국어 뜻이 그대로 나가는 표제어 {m['untranslated']}개")
    if m["verified"] < LIMITS["verified_min"]:
        out.append(f"검증된 표제어 {m['verified']}개 (최소 {LIMITS['verified_min']})")
    if m["gate_pass_ratio"] == 0 and m["research_24h"] >= 10:
        out.append(f"하루 동안 조사 {m['research_24h']}건이 한 건도 통과하지 못했다")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    m = collect(db.connect())
    warn = warnings(m)
    if a.json:
        print(json.dumps({**m, "warnings": warn}, ensure_ascii=False))
        return

    print(f"[{m['at']}] 사전 건강 점검")
    print(f"  마지막 파이프라인   {m['last_run']} ({m['stale_hours']}시간 전)")
    print(f"  표제어              검증 {m['verified']} · 검수대기 {m['terms'].get('needs_review', 0)} · 내린 것 {m['terms'].get('retired', 0)}")
    print(f"  화면에 나가는 뜻    쓸 만함 {m['def_good']} · 쓸 수 없음 {m['def_empty']} ({m['empty_def_ratio']:.0%})")
    print(f"  검수 대기 중 빈 뜻  {m['queued_empty']}개 (큐가 제 일을 하는 중)")
    print(f"  번역 안 된 것       {m['untranslated']}개")
    print(f"  대표 매체           {m['media_terms']}개 표제어")
    print(f"  후보 대기           {m['candidates_waiting']}건")
    print(f"  검수 대기           {m['open_reviews']}건")
    print(f"  못 답한 질문        {m['unanswered_questions']}건")
    print(f"  하루 조사           {m['research_24h']}건 · 통과율 {m['gate_pass_ratio']}")
    print(f"  Gemini              {m['gemini_used_today']}/{m['gemini_budget']}")
    print("  경고                " + ("없음" if not warn else ""))
    for w in warn:
        print(f"    ! {w}")


if __name__ == "__main__":
    main()
