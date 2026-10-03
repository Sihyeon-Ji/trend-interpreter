"""밈 여부 평가 채점(scripts/score_meme_eval.py) — 층화 추정·재현율·일치율은 계산이다. DB·모델 없이 CSV 로."""
import csv
import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("score_meme_eval", Path(__file__).resolve().parents[1] / "scripts" / "score_meme_eval.py")
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


def write(folder: Path, rows: list[tuple]) -> None:
    """rows: (bucket, population, sampled, label, label2)"""
    with open(folder / "label.csv", "w", newline="", encoding="utf-8-sig") as lf, open(folder / "key.csv", "w", newline="", encoding="utf-8-sig") as kf:
        lw = csv.DictWriter(lf, ["no", "term", "label", "label2", "note"])
        kw = csv.DictWriter(kf, ["no", "term", "bucket", "population", "sampled", "labels_on", "labels_off", "wiki_categories"])
        lw.writeheader()
        kw.writeheader()
        for no, (b, pop, n, label, label2) in enumerate(rows, 1):
            lw.writerow({"no": no, "term": f"t{no}", "label": label, "label2": label2, "note": ""})
            kw.writerow({"no": no, "term": f"t{no}", "bucket": b, "population": pop, "sampled": n, "labels_on": 0, "labels_off": 0,
                         "wiki_categories": ""})


def test_weighted_precision_recall_and_mistake_lists(tmp_path):
    # 뺀 쪽: 감사관 묶음(모집단 100) 표본 4 중 밈 아님 3, 근거 0건 묶음(모집단 300) 표본 2 중 밈 아님 2
    # 남긴 쪽: 첫 쪽(30) 표본 2 중 밈 2, 확인 전(200) 표본 2 중 밈 아님 1 + unsure 1
    write(tmp_path, [("held_audit", 100, 4, "topic", ""), ("held_audit", 100, 4, "word", ""), ("held_audit", 100, 4, "word", ""),
                     ("held_audit", 100, 4, "expr", "expr"),
                     ("held_no_evidence", 300, 2, "topic", "topic"), ("held_no_evidence", 300, 2, "Word", "expr"),
                     ("top", 30, 2, "expr", ""), ("top", 30, 2, "meme_name", ""),
                     ("kept_unconfirmed", 200, 2, "word", ""), ("kept_unconfirmed", 200, 2, "unsure", "")])
    rows, bad = sc.load(tmp_path)
    assert bad == []
    s = sc.score(rows)
    est, lo, hi, missing = s["precision"]
    assert est == pytest.approx((100 * 0.75 + 300 * 1.0) / 400) and lo <= est <= hi and not missing
    assert s["held_memes_est"] == pytest.approx(25)                  # 감사관 묶음 100 × 밈 1/4
    assert s["recall"] == pytest.approx(375 / (375 + 200))           # 남긴 쪽 밈 아님: 확인 전 200 × 1/1(unsure 는 뺀다)
    assert s["top"][:2] == (2, 2)
    assert [r["term"] for r in s["wrongly_held"]] == ["t4"] and [r["term"] for r in s["left_in"]] == ["t9"]
    agree, n, bagree, _ = s["agreement"]
    assert n == 3 and agree == pytest.approx(2 / 3) and bagree == pytest.approx(2 / 3)   # 둘 다 붙인 것만 — t10 은 label2 가 빈칸
    report = sc.render(s, "x")
    assert "거르기 정밀도" in report and "t4" in report


def test_bad_labels_are_reported_and_blank_ones_mark_the_report_partial(tmp_path):
    write(tmp_path, [("top", 30, 2, "밈", ""), ("top", 30, 2, "", "")])
    _, bad = sc.load(tmp_path)
    assert len(bad) == 1 and "밈" in bad[0]
    write(tmp_path, [("top", 30, 2, "expr", ""), ("top", 30, 2, "", "")])
    rows, _ = sc.load(tmp_path)
    assert "아직 라벨이 다 붙지 않았다" in sc.render(sc.score(rows), "x")
