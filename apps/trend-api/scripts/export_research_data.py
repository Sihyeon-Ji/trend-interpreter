"""Gemma 파인튜닝·고도화 연구용 데이터 내보내기 (2026-10-01). 수집 서버에서 돌려 DB 의 모든 표를 JSONL 로 뽑는다.
무엇을 왜 뽑는지는 docs/AI-개발/Gemma-연구-데이터-요청.md 에 있다. 모델을 부르지 않고 DB 는 읽기만 한다.

  uv run scripts/export_research_data.py --list                 # 묶음·표별 행 수만 본다(파일을 만들지 않음)
  uv run scripts/export_research_data.py                        # 모든 표
  uv run scripts/export_research_data.py --group labels --group model_outputs
  uv run scripts/export_research_data.py --skip-user-text       # 사용자 문장 표는 빼고
  uv run scripts/export_research_data.py --limit 200            # 표마다 200행만(시험 삼아)

결과는 저장소 루트의 artifacts/research_export/<시각>/ 에 둔다(artifacts/ 는 커밋하지 않는다).
표마다 <표>.jsonl 한 개와 manifest.json(시각·커밋·행 수·서버의 Gemma 환경)을 남긴다. Kaggle 에는 비공개 Dataset 으로만 올린다.

현재 스키마의 모든 표를 읽는다. 아래 GROUPS 는 manifest 의 분류일 뿐이고, 어디에도 없는 표는 'other' 로 나간다.
사용자 문장·설정을 담은 표(USER_TEXT)는 user_text/ 하위 폴더에 따로 둔다 — Kaggle 에 올리는 폴더에 섞지 않고,
보존 기한(해석 캐시 7일·미해결 질문 30일)이 지나면 지운다.
검수자 이름(decided_by·risk_decided_by)은 'reviewer-<해시 8자리>' 로 바꾼다 — 같은 사람은 같은 가명이 되지만 익명화는 아니다.
리스크 표본(export_risk_sample.py)과 감사관 학습 데이터(audit_dataset.py)는 각자의 스크립트로 뽑는다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from export_risk_sample import environment  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

OUT = Path(__file__).resolve().parents[3] / "artifacts" / "research_export"

GROUPS: dict[str, tuple[str, ...]] = {
    # 사람의 판정·정답이 들어 있는 표 — 학습·평가의 정답 후보
    "labels": ("terms", "meanings", "translations", "review_history", "review_queue"),
    # 지금 Gemma(또는 Gemini)가 만든 값 — 정답이 아니라 비교 기준선
    "model_outputs": ("evidence_labels", "term_fit", "topic_notes", "audit_log", "crosscheck_log"),
    # 근거 문장 — 리스크·감사·밈 판별 입력
    "evidence": ("evidences",),
    # Gemini 가 만든 해석·조사 — Gemini → Gemma 증류 실험
    "distill": ("interpretations", "research_log"),
    # 밈이 아닌 것·같은 말 묶기 — 판별기와 표기 묶기 실험
    "negatives": ("candidates", "term_aliases"),
    # 시계열 — 생애주기·지역 확산 연구
    "timeseries": ("mentions_weekly", "mentions_weekly_region", "term_timeline"),
}
USER_TEXT = ("explain_cache", "lookups", "reader_prefs")
REVIEWER_COLUMNS = ("decided_by",)
REVIEWER_JSON_KEYS = ("risk_decided_by", "decided_by")


def pseudonym(name: object) -> object:
    if not isinstance(name, str) or not name:
        return name
    return "reviewer-" + hashlib.sha256(name.encode()).hexdigest()[:8]


def scrub(row: dict) -> dict:
    for column in REVIEWER_COLUMNS:
        if column in row:
            row[column] = pseudonym(row[column])
    raw = row.get("json")
    if isinstance(raw, str) and any(key in raw for key in REVIEWER_JSON_KEYS):
        try:
            data = json.loads(raw)
        except ValueError:
            return row
        if isinstance(data, dict):
            for key in REVIEWER_JSON_KEYS:
                if key in data:
                    data[key] = pseudonym(data[key])
            row["json"] = json.dumps(data, ensure_ascii=False)
    return row


def tables(con) -> list[str]:
    cur = con.execute("SELECT table_name FROM information_schema.tables "
                      "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE' ORDER BY table_name")
    return [row[0] for row in cur.fetchall()]


def group_of(table: str) -> str:
    if table in USER_TEXT:
        return "user_text"
    return next((g for g, members in GROUPS.items() if table in members), "other")


def count(con, table: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def dump(con, table: str, path: Path, limit: int | None) -> int:
    cur = con.execute(f"SELECT * FROM {table}" + (" LIMIT ?" if limit else ""), (limit,) if limit else None)
    columns = [d[0] for d in cur.description]
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for values in cur:
            row = scrub(dict(zip(columns, values)))
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", action="append", choices=[*sorted(GROUPS), "other", "user_text"], help="묶음(여러 번 줄 수 있다). 없으면 전부")
    ap.add_argument("--skip-user-text", action="store_true", help="사용자 문장 표(USER_TEXT)를 빼고 뽑는다")
    ap.add_argument("--limit", type=int, help="표마다 이만큼만")
    ap.add_argument("--list", action="store_true", help="행 수만 보고 파일을 만들지 않는다")
    args = ap.parse_args()

    con = db.connect()
    picked = [t for t in tables(con)
              if (not args.group or group_of(t) in args.group) and not (args.skip_user_text and t in USER_TEXT)]
    if args.list:
        for table in sorted(picked, key=lambda t: (group_of(t), t)):
            print(f"{group_of(table):<14} {table:<24} {count(con, table):>10}")
        return

    out = OUT / f"{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=True)
    manifest = {"exported_at": datetime.now().astimezone().isoformat(timespec="seconds"), "limit": args.limit,
                "groups": {}, "user_text_dir": None, "environment": environment(include_community=True)}
    for table in sorted(picked, key=lambda t: (group_of(t), t)):
        group = group_of(table)
        folder = out / "user_text" if group == "user_text" else out
        folder.mkdir(exist_ok=True)
        n = dump(con, table, folder / f"{table}.jsonl", args.limit)
        manifest["groups"].setdefault(group, {})[table] = n
        if group == "user_text":
            manifest["user_text_dir"] = "user_text/"
        print(f"{group:<14} {table:<24} {n:>10}")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    env = manifest["environment"]
    print(f"{out}  커밋 {env['git_commit'][:12] or '?'} · {env['model']} · Ollama {env['ollama_version'] or '?'}")
    if manifest["user_text_dir"]:
        print(f"사용자 문장 표는 {out / 'user_text'} — Kaggle 에 올리지 않는다")


if __name__ == "__main__":
    main()
