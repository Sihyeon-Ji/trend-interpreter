"""밈 여부 평가 채점 — export_meme_eval_sample.py 가 만든 표본에 사람이 라벨을 붙인 뒤 돌린다. DB·모델 없이 CSV 만 읽는다.

  uv run scripts/score_meme_eval.py artifacts/meme_eval/KR-20261003-0642

label.csv 의 label(첫째 사람)·label2(둘째 사람, 선택)와 key.csv 의 묶음·가중치를 no 로 맞춰:
  - 화면 첫 쪽(top)의 밈 비율
  - 거르기 정밀도: 뺀 말 가운데 실제로 밈이 아닌 몫 — 묶음 가중치로 전체를 추정(층화 추정, 95% 구간)
  - 거르기 재현율: 밈이 아닌 말 전체(추정) 가운데 뺀 몫
  - 까닭별(감사관·근거 0건) 정밀도, 잘못 뺀 밈·남은 밈 아님 목록, 두 사람 일치율(카파)
결과를 같은 폴더의 score.md 에 쓰고 화면에도 낸다. unsure 와 빈칸은 비율 계산에서 뺀다(건수는 따로 보인다).
"""
from __future__ import annotations

import argparse
import csv
import math
from collections import Counter
from pathlib import Path

MEME = {"expr", "meme_name"}
NOT_MEME = {"topic", "word"}
LABELS = MEME | NOT_MEME | {"unsure"}
HELD = ("held_audit", "held_no_evidence")
KEPT = ("top", "kept_confirmed", "kept_unconfirmed")
BUCKET_NAME = {"top": "화면 첫 쪽", "held_audit": "뺌 – 감사관", "held_no_evidence": "뺌 – 쓰인 글 0건",
               "kept_confirmed": "남김 – 쓰임 확인", "kept_unconfirmed": "남김 – 확인 전"}


def norm(label: str) -> str:
    return (label or "").strip().lower().replace("-", "_").replace(" ", "_")


def kind(label: str) -> str | None:
    """'meme' · 'not' · 'unsure' · None(빈칸)."""
    x = norm(label)
    return "meme" if x in MEME else "not" if x in NOT_MEME else "unsure" if x == "unsure" else None


def load(folder: Path) -> tuple[list[dict], list[str]]:
    """label.csv 와 key.csv 를 no 로 합친다. 돌려주는 것: (행들, 잘못 적힌 라벨 안내)."""
    with open(folder / "key.csv", encoding="utf-8-sig", newline="") as f:
        keys = {r["no"]: r for r in csv.DictReader(f)}
    rows, bad = [], []
    with open(folder / "label.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            k = keys.get(r["no"])
            if k is None:
                bad.append(f"no {r['no']}: key.csv 에 없는 번호")
                continue
            for col in ("label", "label2"):
                if r.get(col, "").strip() and norm(r[col]) not in LABELS:
                    bad.append(f"no {r['no']} ({k['term']}): {col} '{r[col]}' 은 {'/'.join(sorted(LABELS))} 가운데 하나가 아니다")
            rows.append({**k, "label": norm(r.get("label", "")), "label2": norm(r.get("label2", "")), "note": r.get("note", "")})
    return rows, bad


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def _strata(rows: list[dict]) -> dict[str, dict]:
    """묶음마다 모집단 N, 판정된 표본 수 n, 그 가운데 밈 m."""
    out: dict[str, dict] = {}
    for r in rows:
        s = out.setdefault(r["bucket"], {"N": int(r["population"]), "n": 0, "m": 0, "labeled": 0, "unsure": 0, "rows": 0})
        s["rows"] += 1
        k = kind(r["label"])
        if k is not None:
            s["labeled"] += 1
        if k == "unsure":
            s["unsure"] += 1
        if k in ("meme", "not"):
            s["n"] += 1
            s["m"] += k == "meme"
    return out


def _not_meme_share(strata: dict[str, dict], buckets: tuple[str, ...]) -> tuple[float, float, float, bool]:
    """묶음들을 합친 모집단에서 밈이 아닌 몫의 층화 추정과 95% 구간. 마지막 값은 판정이 하나도 없는 묶음이 있었나."""
    have = [strata[b] for b in buckets if b in strata]
    missing = any(s["n"] == 0 for s in have) or len(have) < len([b for b in buckets if b in strata])
    have = [s for s in have if s["n"] > 0]
    total = sum(s["N"] for s in have)
    if not total:
        return math.nan, math.nan, math.nan, True
    est = sum(s["N"] * (1 - s["m"] / s["n"]) for s in have) / total
    var = sum((s["N"] / total) ** 2 * (lambda p: p * (1 - p))(s["m"] / s["n"]) / s["n"] * (1 - s["n"] / s["N"] if s["N"] else 0)
              for s in have if s["n"] > 1)
    half = 1.96 * math.sqrt(var)
    return est, max(0.0, est - half), min(1.0, est + half), missing


def kappa(pairs: list[tuple[str, str]]) -> float:
    """두 사람의 밈/밈 아님 판정 일치(코헨 카파)."""
    n = len(pairs)
    if n == 0:
        return math.nan
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in set(ca) | set(cb)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def score(rows: list[dict]) -> dict:
    strata = _strata(rows)
    held_N = sum(strata[b]["N"] for b in HELD if b in strata)
    prec = _not_meme_share(strata, HELD)
    by_reason = {b: _not_meme_share(strata, (b,)) for b in HELD if b in strata}
    # 재현율: 밈 아닌 말 가운데 뺀 몫 = 뺀 쪽의 밈 아님(추정) / (뺀 쪽 + 남긴 쪽의 밈 아님)
    held_not = prec[0] * held_N if held_N and not math.isnan(prec[0]) else math.nan
    kept_have = [b for b in KEPT if b in strata and strata[b]["n"]]
    kept_not = sum(strata[b]["N"] * (1 - strata[b]["m"] / strata[b]["n"]) for b in kept_have)
    recall = held_not / (held_not + kept_not) if held_not + kept_not else math.nan
    top = strata.get("top", {"n": 0, "m": 0})
    pairs = [(kind(r["label"]), kind(r["label2"])) for r in rows
             if kind(r["label"]) in ("meme", "not") and kind(r["label2"]) in ("meme", "not")]
    both = [(r["label"], r["label2"]) for r in rows if kind(r["label"]) is not None and kind(r["label2"]) is not None]
    return {
        "strata": strata,
        "labels": Counter(r["label"] or "(빈칸)" for r in rows),
        "top": (top["m"], top["n"], wilson(top["m"], top["n"])),
        "precision": prec, "by_reason": by_reason,
        "recall": recall, "held_N": held_N, "held_memes_est": held_N - held_not if not math.isnan(held_not) else math.nan,
        "wrongly_held": [r for r in rows if r["bucket"] in HELD and kind(r["label"]) == "meme"],
        "left_in": [r for r in rows if r["bucket"] in KEPT and kind(r["label"]) == "not"],
        "agreement": (sum(a == b for a, b in both) / len(both) if both else math.nan, len(both),
                      sum(a == b for a, b in pairs) / len(pairs) if pairs else math.nan, kappa(pairs)),
        "complete": all(s["labeled"] == s["rows"] for s in strata.values()),
    }


def _pct(x: float) -> str:
    return "–" if x is None or math.isnan(x) else f"{x:.0%}"


def _range(lo: float, hi: float) -> str:
    return "–" if math.isnan(lo) else f"{lo:.0%}–{hi:.0%}"


def render(s: dict, folder: str) -> str:
    st = s["strata"]
    lines = [f"# 밈 여부 평가 채점 – `{folder}`", ""]
    if not s["complete"]:
        lines += ["> 아직 라벨이 다 붙지 않았다. 아래 수는 붙은 것만으로 낸 중간 결과다.", ""]
    m, n, (lo, hi) = s["top"]
    p, plo, phi, pmiss = s["precision"]
    wrong = "–" if math.isnan(s["held_memes_est"]) else f"{s['held_memes_est']:,.0f}"
    lines += ["## 요약", "",
              f"- 화면 첫 쪽의 밈 비율: **{_pct(m / n if n else math.nan)}** ({m}/{n}, 95% {_range(lo, hi)})",
              f"- 거르기 정밀도(뺀 말 가운데 밈이 아닌 몫): **{_pct(p)}** (95% {_range(plo, phi)}){' – 판정 없는 묶음 있음' if pmiss else ''}",
              f"- 잘못 뺀 밈 추정: 뺀 {s['held_N']:,}개 가운데 약 **{wrong}개**",
              f"- 거르기 재현율(밈 아닌 말 가운데 뺀 몫, 추정): **{_pct(s['recall'])}**", ""]
    lines += ["## 까닭별 정밀도", "", "| 까닭 | 뺀 수 | 밈 아닌 몫 | 95% 구간 |", "| --- | ---: | ---: | --- |"]
    for b, (e, l, h, _) in s["by_reason"].items():
        lines.append(f"| {BUCKET_NAME[b]} | {st[b]['N']:,} | {_pct(e)} | {_range(l, h)} |")
    lines += ["", "## 묶음별", "", "| 묶음 | 모집단 | 표본 | 판정 | unsure | 밈 비율 | 95% 구간 |", "| --- | ---: | ---: | ---: | ---: | ---: | --- |"]
    for b in (*KEPT[:1], *HELD, *KEPT[1:]):
        if b in st:
            x = st[b]
            wl, wh = wilson(x["m"], x["n"])
            lines.append(f"| {BUCKET_NAME[b]} | {x['N']:,} | {x['rows']} | {x['n']} | {x['unsure']} | {_pct(x['m'] / x['n'] if x['n'] else math.nan)} | "
                         f"{_range(wl, wh)} |")
    lines += ["", "## 라벨 분포", "", " · ".join(f"`{k}` {v}" for k, v in sorted(s["labels"].items(), key=lambda kv: -kv[1])), ""]
    agree, nb, bagree, kap = s["agreement"]
    if nb:
        lines += ["## 두 사람 일치", "", f"- 두 사람이 모두 붙인 {nb}개: 다섯 갈래 일치 {_pct(agree)} · 밈/밈 아님 일치 {_pct(bagree)} · 카파 {kap:.2f}", ""]

    def table(title: str, rs: list[dict]) -> list[str]:
        out = [f"## {title} ({len(rs)})", ""]
        if not rs:
            return out + ["없음", ""]
        out += ["| no | 표제어 | 라벨 | 묶음 | 근거 분류(그 뜻·딴 이야기) | 위키 분류 | 메모 |", "| ---: | --- | --- | --- | --- | --- | --- |"]
        for r in sorted(rs, key=lambda r: int(r["no"])):
            cats = r["wiki_categories"].replace("|", ", ")[:60]
            out.append(f"| {r['no']} | {r['term']} | `{r['label']}` | {BUCKET_NAME[r['bucket']]} | {r['labels_on']}·{r['labels_off']} | {cats} | "
                       f"{r['note'].replace('|', '/')[:60]} |")
        return out + [""]

    lines += table("잘못 뺀 밈 – 규칙을 늦출 곳", s["wrongly_held"])
    lines += table("남은 밈 아님 – 규칙을 더할 곳", s["left_in"])
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path, help="export_meme_eval_sample.py 가 만든 폴더")
    a = ap.parse_args()
    rows, bad = load(a.folder)
    if bad:
        raise SystemExit("라벨을 고쳐 주세요:\n  " + "\n  ".join(bad))
    report = render(score(rows), a.folder.name)
    (a.folder / "score.md").write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
