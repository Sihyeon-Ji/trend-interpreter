"""사전 전수 대조(Plan 12) — 확인된 항목을 참고 위키(나무위키·위키백과·Know Your Meme)와 맞춰 본다. 한 번 쓰고, 필요할 때 다시 돌린다.

  uv run scripts/crosscheck_dictionary.py                                     # collect: 확인된 말마다 찾은 참고 문서를 보고만
  uv run scripts/crosscheck_dictionary.py collect --store                     # 찾은 문서(짧은 발췌·링크)를 wiki 근거로 더한다
  uv run scripts/crosscheck_dictionary.py collect --terms "럭키비키|aura farming" --limit 20
  uv run scripts/crosscheck_dictionary.py import --from audit.json            # 밖에서 만든 판정: 판정별 건수와 검수 큐에 올릴 것만 보고
  uv run scripts/crosscheck_dictionary.py import --from audit.json --queue    # 고칠 것·위키끼리 다름·밈이 아님 → 검수 큐 (+ 대조 기록)
  uv run scripts/crosscheck_dictionary.py import --from audit.json --store-evidence   # 발췌를 wiki 근거로 (참고 문서이고 표제어가 든 것만)
  uv run scripts/crosscheck_dictionary.py judge                               # 같은 판정을 로컬 Gemma 로 — 보고만
  uv run scripts/crosscheck_dictionary.py judge --queue [--store]             # 제안을 검수 큐에 (+ 대조 기록, 찾은 문서를 근거로)

import 파일은 판정 목록(JSON 배열)이다. 한 줄:
  {"term_id": "t_…", "verdict": "keep" | "fix" | "conflict" | "no_doc" | "not_a_meme",
   "problems": ["사전과 문서가 다른 점", …], "sources": ["https://…", …],
   "proposal": {"definition": "…", "origin": "…", "nuance": "…"} | null,            # fix — 빈 칸은 지금 뜻 그대로
   "alternatives": [{"wiki": "…", "url": "https://…", "summary": "…", "proposal": {…}?}, …],   # conflict
   "excerpt": {"url": "https://…", "title": "…", "text": "…"} | null}              # --store-evidence

Know Your Meme 은 KNOWYOURMEME_ENABLED=true 일 때만 찾고(이용 약관 검토 전까지 기본 꺼짐), 켜도 문서 주소와 제목만 근거로 둔다 —
가져온 판정의 Know Your Meme 발췌도 같다(꺼져 있으면 받지 않는다).
어느 모드도 확인 상태·뜻을 바꾸지 않는다. 모든 제안은 검수 큐로 가고 사람이 승인해야 새 판이 생기거나 빠진다.
참고 문서 주소는 참고 문서 도메인의 문서 주소만 남기고(나머지는 보고), 한 꼴로 고친다(퍼센트 인코딩). 고칠 것·위키끼리 다름·밈이 아님은
참고 문서 주소가 하나는 있어야 한다. --store-evidence 의 발췌는 나무위키·위키백과 문서를 그 자리에서 읽어 그 문장이 실제로 있을 때만 받는다.
'문서 없음' 은 아무것도 바꾸지 않고 목록만 보인다 — 사용자가 확인한 이름만 scripts/audit_dictionary.py --downgrade "이름|이름" 으로
검수 대기로 돌린다(--apply 는 쓰지 않는다). 참고 위키에 닿지 못한 말은 '문서 없음' 이 아니라 '닿지 못함' 으로 따로 보인다.
다시 돌려도 근거·대기 제안이 겹치지 않는다. 이미 검수 대기 중인 제안이 있는 말은 건너뛰고 보고한다.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.pipeline import crosscheck as cc  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402
from trend_agents.storage.db import Connection  # noqa: E402


def _terms(con: Connection, names: str, limit: int | None):
    terms = ds.list_terms(con, ("verified",))
    if names:
        want = [x.strip() for x in names.split("|") if x.strip()]
        keys = {ds.norm(x) for x in want}
        terms = [t for t in terms if t.term_id in want or ds.norm(t.canonical) in keys or any(ds.norm(a) in keys for a in t.aliases)]
    return terms[:limit] if limit else terms


def _kym_note() -> None:
    from trend_agents.collectors import knowyourmeme

    if not knowyourmeme.enabled():
        print("Know Your Meme 은 꺼져 있어 찾지 않는다(KNOWYOURMEME_ENABLED — 이용 약관 검토 전까지 기본 꺼짐, Plan 12).\n")


def collect(con: Connection, a: argparse.Namespace) -> None:
    _kym_note()
    terms = _terms(con, a.terms, a.limit)
    missing, unreached, added = [], [], 0
    for t in terms:
        found, unreachable = cc.gather(t)
        docs = cc.documents(t, ds.list_evidences(con, t.term_id) + found)
        if a.store:
            added += ds.add_evidences(con, t.term_id, [e for e in found if e in docs])
        if docs:
            print(f"  {t.canonical} ({t.lang}) — " + " · ".join(f"{cc.wiki_name(e.url)} {e.url}" for e in docs))
        elif unreachable:
            unreached.append((t.canonical, unreachable))
        else:
            missing.append(t)
    print(f"\n확인된 항목 {len(terms)}개 중 참고 문서가 있는 것 {len(terms) - len(missing) - len(unreached)}개, 없는 것 {len(missing)}개,"
          f" 닿지 못한 것 {len(unreached)}개" + (f" · 근거로 더한 문서 {added}건" if a.store else ""))
    _print_unreachable(unreached)
    _print_no_doc([t.canonical for t in missing])


def _print_unreachable(rows: list[tuple[str, list[str]]]) -> None:
    if rows:
        print("\n닿지 못함 — '문서 없음' 이 아니다(429·서버 오류·네트워크). 다음에 다시 찾는다:")
        for name, where in rows:
            print(f"  - {name}: {', '.join(where)}")


def _print_no_doc(names: list[str]) -> None:
    if names:
        print("\n문서 없음 — 아무것도 바꾸지 않았다. 사용자가 이 목록을 확인한 뒤에만 검수 대기로 돌린다(Plan 12 §3):")
        print('  (확인한 이름만 scripts/audit_dictionary.py --downgrade "이름|이름" 으로 내린다. --apply 는 쓰지 않는다)')
        for n in names:
            print(f"  - {n}")


def import_(con: Connection, a: argparse.Namespace) -> None:
    raw = json.loads(Path(a.source).read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("import 파일은 판정 목록(JSON 배열)이어야 합니다.")
    records, bad = [], []
    for i, r in enumerate(raw):
        try:
            records.append(cc.AuditRecord.model_validate(r))
        except ValueError as e:
            bad.append((i, str(e).splitlines()[0][:160]))
    rep = cc.import_audit(con, records, queue=a.queue, store_evidence=a.store_evidence, model=a.model)
    counts = rep["counts"]
    print(f"판정 {len(records)}줄: " + " · ".join(f"{cc.LABEL[v]} {counts[v]}" for v in ("keep", "fix", "conflict", "not_a_meme", "no_doc")))
    for i, why in bad:
        print(f"  ! {i}번째 줄 형식 오류: {why}")
    rows = rep["queued"] if a.queue else rep["would_queue"]
    print(f"\n검수 큐에 {'올린' if a.queue else '올릴'} 제안 {len(rows)}건" + ("" if a.queue else " (--queue 로 올린다)"))
    for name, kind, why in rows:
        print(f"  - [{kind}] {name}: {why}")
    for name, why in rep["skipped"]:
        print(f"  건너뜀 {name}: {why}")
    if rep["dropped_urls"]:
        print(f"\n참고 문서의 문서 주소가 아니라 뺀 주소 {len(rep['dropped_urls'])}개(사유·문서·출처에 쓰지 않는다):")
        for name, url in rep["dropped_urls"]:
            print(f"  - {name}: {url}")
    if a.store_evidence:
        print(f"\n근거로 더한 발췌 {len(rep['evidence'])}건, 받지 않은 발췌 {len(rep['evidence_skipped'])}건")
        for name, url, why in rep["evidence_skipped"]:
            print(f"  - {name}: {url} — {why}")
    _print_no_doc(rep["no_doc"])


def judge(con: Connection, a: argparse.Namespace) -> None:
    from trend_agents.pipeline.gemini import local_ok

    if not local_ok():
        raise SystemExit("로컬 모델이 없어 judge 를 건너뜁니다 — USE_LOCAL_GEMMA=1 과 로컬 서버(Ollama·vLLM)의 GEMMA_LOCAL_MODEL 이 필요합니다.")
    _kym_note()
    terms = _terms(con, a.terms, a.limit)
    counts: Counter = Counter()
    missing, unreached = [], []
    for t in terms:
        if ds.pending_review(con, t.term_id):
            print(f"  건너뜀 {t.canonical}: 이미 검수 대기 중인 제안이 있음")
            continue
        try:
            res = cc.check(con, t, judging=True, store=a.store, queue=a.queue, log=a.queue)
        except Exception as e:  # noqa: BLE001 — 한 말의 형식 실패가 나머지를 막지 않는다
            counts[cc.ERROR] += 1
            print(f"  {t.canonical}: 판정 실패 {type(e).__name__}")
            continue
        counts[res["verdict"]] += 1
        if res["verdict"] == "no_doc":
            missing.append(t.canonical)
            continue
        if res["verdict"] == cc.UNREACHABLE:
            unreached.append((t.canonical, res["unreachable"]))
            continue
        extra = f" → {res['queued']}" if res["queued"] else ""
        print(f"  [{cc.LABEL.get(res['verdict'], res['verdict'])}] {t.canonical}: {res['reason']}{extra}")
        if res["draft"] is not None and not a.queue:
            print(f"      고칠 안 — 뜻: {res['draft'].definition} / 유래: {res['draft'].origin}")
    print("\n" + " · ".join(f"{cc.LABEL.get(k, k)} {v}" for k, v in counts.items()) + ("" if a.queue else "  (--queue 로 검수 큐에 올린다)"))
    _print_unreachable(unreached)
    _print_no_doc(missing)


def main() -> None:
    ap = argparse.ArgumentParser(description="사전 전수 대조 (Plan 12)")
    sub = ap.add_subparsers(dest="mode")
    c = sub.add_parser("collect", help="참고 문서 찾기 (기본)")
    c.add_argument("--store", action="store_true", help="찾은 문서를 wiki 근거로 더한다 (짧은 발췌·링크만)")
    i = sub.add_parser("import", help="밖에서 만든 판정 가져오기")
    i.add_argument("--from", dest="source", required=True, help="판정 목록 JSON 파일")
    i.add_argument("--queue", action="store_true", help="고칠 것·위키끼리 다름·밈이 아님을 검수 큐에 올린다")
    i.add_argument("--store-evidence", action="store_true", help="발췌를 wiki 근거로 더한다 (참고 문서·표제어가 든 것만)")
    i.add_argument("--model", default="import", help="대조 기록에 남길 판정 출처 이름 (기본 import)")
    j = sub.add_parser("judge", help="로컬 Gemma 로 판정 (제안만)")
    j.add_argument("--queue", action="store_true", help="제안을 검수 큐에 올리고 대조 기록을 남긴다")
    j.add_argument("--store", action="store_true", help="찾은 문서를 wiki 근거로 더한다")
    for p in (c, j):
        p.add_argument("--terms", default="", help="표제어·별칭·term_id, | 로 구분 (없으면 확인된 항목 전부)")
        p.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    if a.mode is None:
        a = ap.parse_args(["collect", *sys.argv[1:]])
    con = db.connect()
    {"collect": collect, "import": import_, "judge": judge}[a.mode](con, a)


if __name__ == "__main__":
    main()
