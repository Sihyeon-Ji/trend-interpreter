"""로컬 Gemma 편집 결과의 규칙 지표 (Plan 06 완료 기준 6 · Plan 09 'Gemma 편집 품질'). 모델을 부르지 않는다.

이미 저장된 편집 결과를 산출물·모델별로 잰다. 사람이 판정할 것(근거에 없는 주장·국가별 차이 오류)은 표에 빈칸으로 두고 표본 CSV 로 내보낸다.
  번역(translations)          원래 뜻에 표제어가 있으면 번역문에도 그대로 있는가 — mentions(), 별칭 제외(옮겨 적거나 번역하면 훼손)
  국가별 해석(topic_notes)     현지 이름이 표제어·별칭 그대로이거나 인용한 근거에 있는가 / 현지 밈이 인용한 근거(evidence_ids)의 문장에 있는가
                              (보이는 출처인지, 이용자에게 내지 않는 커뮤니티 글에만 있는지 나눈다 — ADR 0003) / evidence_ids 가 있고 근거 표에서 찾아지는가
  근거 분류(evidence_labels)   분류한 문장에 표제어가 있는가, 딴 이야기(offtopic)로 본 몫
  쓰임 낱말(term_fit)          건수와 처리 시간만
  뜻 초안(조사)                게이트 통과, 사람 수정률 — 사람이 정한 초안(승인·제외, 사람이 쓴 새 판으로 바뀜) 가운데 제외·교체한 몫.
                              초안의 모델은 뜻 판이 생긴 직후의 research_log 로 정한다. 검수 큐에는 게이트에 걸린 것만 가므로 대기·미검토 수를 함께 적는다
  처리 시간                    그 단계 실행 시간 ÷ 그 실행에서 만든 건수(수집·저장 포함). 결과의 저장 시각이 든 실행(pipeline_runs)으로 묶는다

  uv run scripts/eval_editing.py --sqlite /path/to/trend-copy.db    # 원작자 서버 DB 사본 (sqlite3 원본.db ".backup 사본.db")
  uv run scripts/eval_editing.py                                    # DATABASE_URL 의 PostgreSQL — 읽기 전용(스키마·마이그레이션을 건드리지 않는다)

표준 출력에 docs/트렌드/평가.md 에 붙일 표를 내고, 저장소 루트의 artifacts/eval/ 에 JSON 과 사람이 채울 -judge.csv 를 남긴다(artifacts/ 는 커밋하지 않는다).
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.collectors.community import is_community_post  # noqa: E402
from trend_agents.pipeline.match import evidence_mentions, mentions, same_term  # noqa: E402
from trend_agents.schemas import Evidence  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "artifacts" / "eval"
SOURCE_FIELDS = ("definition", "expansion", "origin", "nuance")
TEXT_FIELDS = SOURCE_FIELDS + ("plain",)
# 조사는 뜻 판을 저장한 뒤 미디어 붙이기·검수 큐를 거쳐 조사 기록을 남긴다(research.research_one) — 그 사이 몇 초~수십 초
DRAFT_LOG_WINDOW = timedelta(minutes=5)
STAGE_OF = {"translations": "translate", "topic_notes": "topics", "evidence_labels": "risk", "term_fit": "fit"}


def _at(s: str | None) -> datetime | None:
    if not s:
        return None
    t = datetime.fromisoformat(s)
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _terms(con) -> dict[str, tuple[str, list[str]]]:
    return {tid: (canon, json.loads(j).get("aliases") or []) for tid, canon, j in con.execute("SELECT term_id, canonical, json FROM terms").fetchall()}


def _evidences(con) -> dict[tuple[str, str], Evidence]:
    return {(eid, tid): Evidence.model_validate_json(j) for eid, tid, j in con.execute("SELECT evidence_id, term_id, json FROM evidences").fetchall()}


def seconds_per_item(con, stage: str, rows: list[tuple[str, str]]) -> dict[str, tuple[float, int]]:
    """{모델: (건당 초, 시간을 잰 건수)}. 저장 시각이 든 단계 실행의 시간을 그 실행에서 만든 건수로 나눈다(모델이 섞이면 건수 비율로 나눈다)."""
    runs = [(a, b) for a, b in ((_at(s), _at(f)) for s, f in con.execute(
        "SELECT started_at, finished_at FROM pipeline_runs WHERE stage=? AND finished_at IS NOT NULL", (stage,)).fetchall()) if a and b]
    by_run: dict[int, Counter] = defaultdict(Counter)
    for at, model in rows:
        t = _at(at)
        hit = next((i for i, (a, b) in enumerate(runs) if t and a <= t <= b), None)
        if hit is not None:
            by_run[hit][model] += 1
    spent: Counter = Counter()
    timed: Counter = Counter()
    for i, c in by_run.items():
        a, b = runs[i]
        total = sum(c.values())
        for model, n in c.items():
            spent[model] += (b - a).total_seconds() * n / total
            timed[model] += n
    return {m: (spent[m] / timed[m], timed[m]) for m in timed}


def translations(con, terms) -> dict[str, dict]:
    current = {tid: json.loads(j) for tid, j in con.execute("SELECT term_id, json FROM meanings WHERE valid_to IS NULL").fetchall()}
    out: dict[str, dict] = defaultdict(lambda: {"rows": 0, "ko": [0, 0], "en": [0, 0], "no_meaning": 0, "lost": []})
    rows = con.execute("SELECT term_id, lang, json, updated_at, model FROM translations").fetchall()
    for tid, lang, j, _, model in rows:
        g = out[model or "(없음)"]
        g["rows"] += 1
        canon = terms.get(tid, ("", []))[0]
        m = current.get(tid)
        if not m or not canon:
            g["no_meaning"] += 1
            continue
        src = " ".join(str(m.get(k) or "") for k in SOURCE_FIELDS)
        if not mentions(src, canon):
            continue                                      # 원래 뜻에 표제어가 없으면 잴 것이 없다
        text = json.loads(j)
        kept = mentions(" ".join(str(text.get(k) or "") for k in TEXT_FIELDS), canon)
        pair = g.setdefault(lang, [0, 0])
        pair[0] += kept
        pair[1] += 1
        if not kept:
            g["lost"].append(f"{canon} ({lang})")         # 사람이 볼 것 — 옮겨 적었나(훼손), 되풀이하지 않았을 뿐인가
    for model, (sec, n) in seconds_per_item(con, STAGE_OF["translations"], [(at, m or "(없음)") for *_, at, m in rows]).items():
        out[model]["seconds"], out[model]["timed"] = round(sec, 2), n
    return dict(out)


def topic_notes(con, terms, evidences) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(Counter)
    rows = con.execute("SELECT term_id, region, json, updated_at, model FROM topic_notes").fetchall()
    for tid, region, j, _, model in rows:
        g = out[model or "(없음)"]
        n = json.loads(j)
        canon, aliases = terms.get(tid, ("", []))
        g["rows"] += 1
        g["blank_region"] += not (region or "").strip()
        ids = n.get("evidence_ids") or []
        cited = [evidences[(e, tid)] for e in ids if (e, tid) in evidences]
        g["with_ids"] += bool(ids)
        g["ids"] += len(ids)
        g["ids_found"] += len(cited)
        visible = "\n".join(f"{e.title} {e.excerpt}" for e in cited if not is_community_post(e))
        posts = "\n".join(f"{e.title} {e.excerpt}" for e in cited if is_community_post(e))
        name = (n.get("local_name") or "").strip()
        g["name_kept"] += bool(name) and (name == canon or name in aliases or mentions(visible, name))
        for x in n.get("local_memes") or []:
            label = (x.get("label") or "").strip()
            if not label:
                continue
            g["memes"] += 1
            g["echo"] += same_term(label, canon, aliases)    # 현지 밈 자리에 표제어를 되풀이했다
            g["visible" if mentions(visible, label) else "community_only" if mentions(posts, label) else "unanchored"] += 1
    result = {m: dict(c) for m, c in out.items()}
    for model, (sec, k) in seconds_per_item(con, STAGE_OF["topic_notes"], [(at, m or "(없음)") for *_, at, m in rows]).items():
        result[model]["seconds"], result[model]["timed"] = round(sec, 2), k
    return result


def evidence_labels(con, terms, evidences) -> dict[str, dict]:
    out: dict[str, dict] = defaultdict(Counter)
    rows = con.execute("SELECT evidence_id, term_id, polarity, labeled_at, model FROM evidence_labels").fetchall()
    for eid, tid, polarity, _, model in rows:
        g = out[model or "(없음)"]
        g["rows"] += 1
        g["offtopic"] += polarity == "offtopic"
        e = evidences.get((eid, tid))
        canon, aliases = terms.get(tid, ("", []))
        g["anchored"] += bool(e and canon and evidence_mentions(e, canon, aliases))
    result = {m: dict(c) for m, c in out.items()}
    for model, (sec, k) in seconds_per_item(con, STAGE_OF["evidence_labels"], [(at, m or "(없음)") for *_, at, m in rows]).items():
        result[model]["seconds"], result[model]["timed"] = round(sec, 3), k
    return result


def term_fit(con) -> dict[str, dict]:
    rows = con.execute("SELECT term_id, labeled_at, model FROM term_fit").fetchall()
    out = {m: {"rows": n} for m, n in Counter(m or "(없음)" for *_, m in rows).items()}
    for model, (sec, k) in seconds_per_item(con, STAGE_OF["term_fit"], [(at, m or "(없음)") for _, at, m in rows]).items():
        out[model]["seconds"], out[model]["timed"] = round(sec, 3), k
    return out


def drafts(con) -> dict[str, dict]:
    """조사가 만든 뜻 판(초안)을 모델별로. 사람이 쓴 판(시드·검수자)은 셈에서 빼고, 그 판이 기계 초안을 바꾼 것이면 '교체' 로 센다."""
    logs: dict[str, list] = defaultdict(list)
    for tid, at, model, verification in con.execute(
            "SELECT term_id, researched_at, model, verification FROM research_log WHERE verification != 'error'").fetchall():
        logs[tid].append((_at(at), model, verification))
    waiting = {tid for (tid,) in con.execute("SELECT term_id FROM review_queue WHERE decision IS NULL").fetchall()}
    versions: dict[str, list] = defaultdict(list)
    for tid, version, verification, valid_from, valid_to, j in con.execute(
            "SELECT term_id, version, verification, valid_from, valid_to, json FROM meanings").fetchall():
        # created_by: 사람이 승인·제외하면 그 사람(검수 화면의 계정·검토 스크립트의 이름)으로 바뀐다(ds.set_verification)
        versions[tid].append((version, verification, _at(valid_from), valid_to, json.loads(j).get("created_by") or ""))

    def origin(tid: str, start: datetime | None):
        """뜻 판이 생긴 직후의 조사 기록 (모델, 그때 게이트 판정). 없으면 사람이 쓴 판."""
        hits = sorted((at, m, v) for at, m, v in logs[tid] if start and at and start <= at <= start + DRAFT_LOG_WINDOW)
        return (hits[0][1], hits[0][2]) if hits else None

    out: dict[str, dict] = defaultdict(Counter)
    for tid, vs in versions.items():
        vs.sort(key=lambda v: v[0])
        made = [origin(tid, v[2]) for v in vs]
        for i, (_, verification, _, valid_to, by) in enumerate(vs):
            if made[i] is None:
                continue
            model, gate = made[i]
            g = out[model]
            g["drafts"] += 1
            g["gate_passed"] += gate == "verified_auto"
            replaced = i + 1 < len(vs) and made[i + 1] is None      # 다음 판을 사람이 썼다
            rejected = verification == "rejected"
            approved = verification == "verified_human" and not replaced
            g["decided"] += rejected or replaced or approved
            g["corrected"] += rejected or replaced
            if rejected or replaced or approved:
                g[f"decided_by:{vs[i + 1][4] if replaced else by}"] += 1
            g["pending"] += valid_to is None and verification == "unverified" and tid in waiting
            g["published_unreviewed"] += gate == "verified_auto" and not (rejected or replaced or approved)
    return {m: dict(c) for m, c in out.items()}


def measure(con) -> dict:
    terms, evidences = _terms(con), _evidences(con)
    return {"translations": translations(con, terms), "topic_notes": topic_notes(con, terms, evidences),
            "evidence_labels": evidence_labels(con, terms, evidences), "term_fit": term_fit(con), "drafts": drafts(con)}


# ---------- 표 ----------

def _n(x: int) -> str:
    return f"{x:,}"


def _frac(a: int, b: int) -> str:
    return f"{_n(a)}/{_n(b)} ({a / b:.0%})" if b else "—"


def _sec(g: dict, note: str = "") -> str:
    return f"{g['seconds']:.2f}초{note}" if g.get("seconds") is not None else "—"


MODEL_NOTE = {"gemma-local": " (모델 미기록)", "team": " (팀이 쓴 시드)"}


def table(m: dict) -> str:
    head = ("| 산출물 | 모델 | 건수 | 표제어 원문 보존 | 근거 앵커 | 근거 id | 건당 처리 시간 | 사람 수정률 | 근거에 없는 주장 (사람) | 국가별 차이 오류 (사람) |\n"
            "| --- | --- | ---: | --- | --- | --- | ---: | --- | --- | --- |")
    rows = [head]
    for model, g in sorted(m["translations"].items(), key=lambda x: -x[1]["rows"]):
        keep = " · ".join(f"{lang} {_frac(*g[lang])}" for lang in ("ko", "en") if g.get(lang) and g[lang][1])
        rows.append(f"| 번역 ko·en | `{model}`{MODEL_NOTE.get(model, '')} | {_n(g['rows'])} | {keep or '—'} | — | — | {_sec(g)} | 고치는 화면 없음 |  | — |")
    for model, g in sorted(m["topic_notes"].items(), key=lambda x: -x[1]["rows"]):
        memes = (f"현지 밈 {_n(g.get('memes', 0))}: 보이는 근거 {_n(g.get('visible', 0))} · 커뮤니티 글에만 {_n(g.get('community_only', 0))} · "
                 f"없음 {_n(g.get('unanchored', 0))} (표제어 되풀이 {_n(g.get('echo', 0))})")
        ids = f"있음 {_frac(g.get('with_ids', 0), g['rows'])} · 찾음 {_frac(g.get('ids_found', 0), g.get('ids', 0))}"
        rows.append(f"| 국가별 해석 | `{model}` | {_n(g['rows'])} | 현지 이름 {_frac(g.get('name_kept', 0), g['rows'])} | {memes} | {ids} | "
                    f"{_sec(g, ' (수집 포함)')} | 고치는 화면 없음 |  |  |")
    for model, g in sorted(m["evidence_labels"].items(), key=lambda x: -x[1]["rows"]):
        rows.append(f"| 근거 분류 | `{model}` | {_n(g['rows'])} | — | 표제어가 든 문장 {_frac(g.get('anchored', 0), g['rows'])} · 딴 이야기로 봄 "
                    f"{_frac(g.get('offtopic', 0), g['rows'])} | — | {_sec(g)} | 표본 검토 전(`risk_sample.py`) | — | — |")
    for model, g in sorted(m["term_fit"].items(), key=lambda x: -x[1]["rows"]):
        rows.append(f"| 쓰임 낱말 | `{model}` | {_n(g['rows'])} | — | — | — | {_sec(g)} | — | — | — |")
    for model, g in sorted(m["drafts"].items(), key=lambda x: -x[1]["drafts"]):
        who = " · ".join(f"{k.split(':', 1)[1]} {v}" for k, v in sorted(g.items()) if k.startswith("decided_by:"))
        human = ((f"{_frac(g['corrected'], g['decided'])} 제외·교체 (결정 {who})" if g.get("decided") else "사람이 정한 것 없음")
                 + f" · 검수 대기 {_n(g.get('pending', 0))} · 사람이 안 보고 실린 것 {_n(g.get('published_unreviewed', 0))}")
        rows.append(f"| 뜻 초안(조사) | `{model}` | {_n(g['drafts'])} | — | 게이트 통과 {_frac(g.get('gate_passed', 0), g['drafts'])} | — | — | {human} | — | — |")
    return "\n".join(rows)


# ---------- 사람이 채울 표본 ----------

def judge_rows(con, per_model: int, seed: int) -> list[dict]:
    """번역·국가별 해석을 모델마다 per_model 개씩 (팀이 쓴 시드 제외). 사람이 '근거에 없는 주장'·'국가별 차이 오류' 를 채운다."""
    rng = random.Random(seed)
    terms, evidences = _terms(con), _evidences(con)
    current = {tid: json.loads(j) for tid, j in con.execute("SELECT term_id, json FROM meanings WHERE valid_to IS NULL").fetchall()}
    out: list[dict] = []
    by_model: dict[str, list] = defaultdict(list)
    for tid, lang, j, model in con.execute("SELECT term_id, lang, json, model FROM translations ORDER BY term_id, lang").fetchall():
        if model != "team":
            by_model[model or "(없음)"].append((tid, lang, j))
    for model, rows in sorted(by_model.items()):
        for tid, lang, j in rng.sample(rows, min(per_model, len(rows))):
            m, text = current.get(tid) or {}, json.loads(j)
            out.append({"산출물": "번역", "모델": model, "term_id": tid, "표제어": terms.get(tid, ("", []))[0], "언어·나라": lang,
                        "원래 뜻": " / ".join(str(m.get(k) or "") for k in SOURCE_FIELDS)[:600],
                        "편집 결과": " / ".join(str(text.get(k) or "") for k in TEXT_FIELDS)[:600], "인용한 근거": ""})
    notes: dict[str, list] = defaultdict(list)
    for tid, region, j, model in con.execute("SELECT term_id, region, json, model FROM topic_notes ORDER BY term_id, region").fetchall():
        notes[model or "(없음)"].append((tid, region, j))
    for model, rows in sorted(notes.items()):
        for tid, region, j in rng.sample(rows, min(per_model, len(rows))):
            n = json.loads(j)
            cited = [evidences[(e, tid)] for e in n.get("evidence_ids") or [] if (e, tid) in evidences]
            memes = ", ".join(x.get("label", "") for x in n.get("local_memes") or [])
            out.append({"산출물": "국가별 해석", "모델": model, "term_id": tid, "표제어": terms.get(tid, ("", []))[0], "언어·나라": region,
                        "원래 뜻": str((current.get(tid) or {}).get("definition") or "")[:300],
                        "편집 결과": f"{(n.get('what_changed') or {}).get('ko', '')} / 현지 이름: {n.get('local_name', '')} / 현지 밈: {memes}"[:600],
                        "인용한 근거": " | ".join(e.title for e in cited if not is_community_post(e))[:600]})
    for r in out:
        r.update({"근거에 없는 주장(개수)": "", "국가별 차이 오류(예/아니오)": "", "메모": ""})
    return out


def _connect(path: str | None):
    if path:
        p = Path(path)
        if not p.exists():
            raise SystemExit(f"DB 사본이 없습니다: {p}")
        return sqlite3.connect(f"file:{p}?mode=ro", uri=True), p.name
    from trend_agents.storage import db

    return db.connect_read_only(), "DATABASE_URL"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sqlite", help="원작자 서버 DB 사본(.db). 읽기 전용으로 연다. 없으면 DATABASE_URL 의 PostgreSQL(읽기 전용)")
    ap.add_argument("--sample", type=int, default=10, help="사람이 채울 표본 — 산출물·모델마다 몇 개")
    ap.add_argument("--seed", type=int, default=20260929)
    a = ap.parse_args()
    con, source = _connect(a.sqlite)
    result = measure(con)
    rows = judge_rows(con, a.sample, a.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    (OUT / f"editing-{stamp}.json").write_text(json.dumps({"source": source, "generated_at": stamp, "metrics": result},
                                                          ensure_ascii=False, indent=2), encoding="utf-8")
    with open(OUT / f"editing-{stamp}-judge.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["산출물"])
        w.writeheader()
        w.writerows(rows)
    print(table(result))
    print(f"\n표본 {len(rows)}건 → {OUT / f'editing-{stamp}-judge.csv'}")


if __name__ == "__main__":
    main()
