"""리스크 표본(scripts/risk_sample.py, Plan 03) — 층 나누기·필수 표현·일치율은 규칙이다. 모델 없이 임시 스키마로.
표본과 검수자의 수준은 저장소에 커밋하는 표본 파일에 남는다 — 운영의 사람의 결정(risk_human)은 보지도 쓰지도 않는다."""
import csv
import importlib.util
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from trend_agents.schemas import Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db

_spec = importlib.util.spec_from_file_location("risk_sample", Path(__file__).resolve().parents[1] / "scripts" / "risk_sample.py")
rs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rs)
QUOTAS = {"avoid": 2, "caution": 4, "none": 2, "hold": 1}
REQUIRED = ("懶人包", "gaslighting", "brah", "FOMO", "없는말")


def _rewrite(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rs.COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def test_risk_sample_is_stratified_and_keeps_required_terms():
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    levels = {"avoid": ["懶人包", "gaslighting", "거지근성"], "caution": ["brah", "FOMO", "viral video", "밈1", "밈2", "밈3"],
              "none": ["없음1", "없음2", "없음3", "없음4"], "hold": ["보류1", "보류2", "보류3"]}
    for level, names in levels.items():
        for name in names:
            ds.upsert_term(con, Term(term_id=f"t_{name}", canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now))
            ds.set_risk(con, f"t_{name}", None if level == "hold" else level, [f"{level} 이유"], now)
    ds.upsert_term(con, Term(term_id="t_new", canonical="판정전", lang="ko", status="verified", first_seen=now, last_seen=now))
    rows = rs.checked_terms(con)
    assert len(rows) == 16 and "t_new" not in {r["term_id"] for r in rows}      # 리스크 단계가 아직 보지 않은 말은 뽑지 않는다

    sample, missing = rs.draw(rows, QUOTAS, REQUIRED, seed=7)
    assert missing == ["없는말"]
    assert Counter(r["rule"] for r in sample) == QUOTAS                          # 층마다 정한 수 — 필수 표현도 제 층의 자리를 쓴다
    assert {"懶人包", "gaslighting", "brah", "FOMO"} <= {r["canonical"] for r in sample}
    assert rs.draw(rows, QUOTAS, REQUIRED, seed=7)[0] == sample                  # 같은 목록·같은 시드면 같은 표본
    assert "懶人包 ★" in rs.checklist(sample)
    con.close()


def test_reviewer_levels_are_written_in_the_sample_file_and_scored_against_the_level_they_saw(tmp_path):
    """검수자는 표본 파일에 수준을 적는다. 일치는 뽑을 때의 규칙 수준(체크리스트에 적힌 값)과 견준다 — DB 를 보지 않으므로
    뒤에 규칙이 판정을 바꾸거나 누가 운영 화면에서 수준을 골라도 셈이 바뀌지 않는다."""
    names = [("懶人包", "avoid"), ("gaslighting", "avoid"), ("brah", "caution"), ("FOMO", "caution"), ("보류1", "hold"), ("없음1", "none")]
    sample = [{"term_id": f"t{i}", "canonical": n, "rule": lv, "reasons": [f"{lv} 이유", "둘째 이유"], "required": i < 2}
              for i, (n, lv) in enumerate(names)]
    path = tmp_path / "sample.csv"
    rs.save(path, sample)
    rows = rs.load(path)
    assert [r["term_id"] for r in rows] == [f"t{i}" for i in range(6)]         # 표본은 term_id 로 고정된다
    assert (rows[0]["필수"], rows[0]["규칙 수준"], rows[0]["규칙의 이유(첫 줄)"], rows[4]["규칙 수준"]) == ("★", "사용 자제", "avoid 이유", "판단 보류")
    assert rs.agreement(rows)["reviewed"] == 0                                   # 빈칸은 검토 전

    filled = {"懶人包": "주의", "gaslighting": "사용 자제", "brah": "none", "보류1": "판단 보류"}   # 한국어 이름도 코드도 받는다
    for r in rows:
        r["검수자가 정한 수준"], r["검수자"] = (filled[r["표현"]], "kim") if r["표현"] in filled else ("", "")
    _rewrite(path, rows)
    res = rs.agreement(rs.load(path))
    assert (res["reviewed"], res["agree"], res["total"]) == (4, 2, 6)
    assert res["by_level"] == {"avoid": [1, 2], "caution": [0, 1], "none": [0, 0], "hold": [1, 1]}
    assert res["confusion"] == {"avoid->avoid": 1, "avoid->caution": 1, "caution->none": 1, "hold->hold": 1}
    assert [r["agree"] for r in res["rows"]] == [False, True, False, None, True, None]

    rows = rs.load(path)
    rows[3]["검수자가 정한 수준"] = "안전"
    _rewrite(path, rows)
    with pytest.raises(ValueError, match="4번 FOMO"):
        rs.agreement(rs.load(path))


def test_draw_does_not_replace_a_sample_under_review(tmp_path, monkeypatch):
    """말의 목록이 실행마다 바뀌어 다시 뽑으면 다른 표본이 된다 — 있는 표본 파일은 --force 없이는 덮어쓰지 않는다."""
    copy = tmp_path / "copy.db"
    raw = sqlite3.connect(copy)
    raw.execute("CREATE TABLE terms (term_id TEXT, canonical TEXT, status TEXT, json TEXT)")
    checked = json.dumps({"risk_checked_at": "2026-09-29T14:27:37Z", "risk_rule_level": "none", "risk_reasons": ["근거에 위험 신호가 없다."]})
    raw.executemany("INSERT INTO terms VALUES (?,?,?,?)", [(f"t{i}", f"말{i}", "verified", checked) for i in range(3)])
    raw.commit()
    raw.close()
    path = tmp_path / "sample.csv"
    path.write_text("검토 중인 표본\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["risk_sample.py", "draw", "--sqlite", str(copy), "--sample", str(path)])
    with pytest.raises(SystemExit, match="--force"):
        rs.main()
    assert path.read_text(encoding="utf-8") == "검토 중인 표본\n"

    monkeypatch.setattr(sys, "argv", ["risk_sample.py", "draw", "--sqlite", str(copy), "--sample", str(path), "--force"])
    rs.main()
    assert [(r["term_id"], r["규칙 수준"], r["검수자가 정한 수준"]) for r in rs.load(path)] == [(f"t{i}", "없음", "") for i in range(3)]
