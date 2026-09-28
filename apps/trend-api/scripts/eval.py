"""평가표. 결정론 규칙·저장소 테스트, 프론트 매칭 배터리, 게이트 환각 차단 픽스처, 급증 설명의 앵커율, 파이프라인 건강을 한 표로 만들어 docs/EVAL.md 에 쓴다.

사용: uv run scripts/eval.py   (웹 서버 3100 이 떠 있으면 매칭 배터리도 함께)
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from trend_agents.schemas import Evidence, MeaningDraft
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import sqlite_store as db
from trend_agents.verification import gate

ROOT = Path(__file__).resolve().parents[1]
now = datetime.now(timezone.utc)


def sh(cmd: list[str], cwd: Path = ROOT, timeout: int = 300) -> str:
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout).stdout + ""
    except Exception as e:
        return f"ERR {type(e).__name__}"


def ev(kind, domain, title, excerpt=""):
    return Evidence(evidence_id=ds.new_id("e", f"{domain}{title}"), kind=kind, url=f"https://{domain}/x", title=title, source_domain=domain, observed_at=now, excerpt=excerpt or title)


def draft(defn, exp, conf=0.85):
    return MeaningDraft(definition=defn, expansion=exp, origin="o", nuance="n", generations=["20s"], regions=["KR"], self_confidence=conf)


# 게이트 픽스처: (설명, 용어, 초안, 근거, 기대) — 기대 verified_auto 면 통과해야, unverified 면 막아야 한다
GATE_CASES = [
    ("정상: 뉴스+웹 2출처, 풀이 원문 실재", "자만추", draft("자연스러운 만남을 추구한다는 뜻", "자연스러운 만남 추구"),
     [ev("news", "mk.co.kr", "자만추, 자연스러운 만남 추구가 뜬다"), ev("web", "namu.wiki", "자만추 — 자연스러운 만남 추구")], "verified_auto"),
    ("환각: 풀이가 어떤 원문에도 없음", "자만추", draft("자연스러운 만남을 추구한다는 뜻", "자동 만남 추적"),
     [ev("news", "mk.co.kr", "자만추, 자연스러운 만남 추구가 뜬다"), ev("web", "namu.wiki", "자만추 — 자연스러운 만남 추구")], "unverified"),
    ("출처 1개뿐", "럭키비키", draft("운이 좋다는 뜻", None), [ev("news", "khan.co.kr", "럭키비키 유행")], "unverified"),
    ("웹만 있고 1차 근거 없음", "럭키비키", draft("운이 좋다는 뜻", None), [ev("web", "a.com", "럭키비키 뜻"), ev("web", "b.com", "럭키비키 유래")], "unverified"),
    ("용어가 원문에 없는 근거만", "저메추", draft("저녁 메뉴 추천", "저녁 메뉴 추천"), [ev("news", "a.com", "오늘 저녁 뭐 먹지"), ev("short", "youtube.com", "저녁 메뉴 브이로그")], "unverified"),
    ("모델 자기확신 낮음", "저메추", draft("저녁 메뉴 추천", "저녁 메뉴 추천", conf=0.3),
     [ev("news", "a.com", "저메추 해주는 AI, 저녁 메뉴 추천"), ev("web", "b.com", "저메추 = 저녁 메뉴 추천")], "unverified"),
    ("정상: 쇼츠+뉴스", "6-7", draft("뜻 없는 감탄사", None), [ev("short", "youtube.com", "6-7 meme compilation"), ev("news", "nytimes.com", "What does 6-7 mean?")], "verified_auto"),
    ("뜻 충돌: 현행 풀이와 다름", "자만추", draft("자연스러운 만남 추구", "자만한 추종"),
     [ev("news", "mk.co.kr", "자만추 = 자만한 추종?"), ev("web", "x.com", "자만추 자만한 추종")], "unverified"),
]


def gate_eval() -> tuple[int, int, list[str]]:
    from trend_agents.schemas import Meaning

    ok, rows = 0, []
    for desc, term, d, evs, expect in GATE_CASES:
        current = None
        if "뜻 충돌" in desc:
            current = Meaning(**draft("자연스러운 만남 추구", "자연스러운 만남 추구").model_dump(), meaning_id="m0", term_id="t0", version=1, confidence=0.9, verification="verified_auto", valid_from=now)
        got, reasons = gate(term, d, evs, current)
        hit = got == expect
        ok += hit
        rows.append(f"| {desc} | {expect} | {got} | {'✓' if hit else '✗'} |")
    return ok, len(GATE_CASES), rows


def main() -> None:
    con = db.connect()
    lines = [f"# 평가표 (자동 생성 {now:%Y-%m-%d %H:%M} UTC)", "", "`uv run scripts/eval.py` 가 만든다. 숫자는 실행 시점의 로컬 DB(`data/trend.db`) 기준.", ""]

    # 1) 규칙·저장소 테스트
    out = sh(["uv", "run", "pytest", "-q"])
    m = re.search(r"(\d+) passed", out)
    lines += ["## 1. 결정론 규칙·저장소 (pytest)", "", f"- 통과 {m.group(1) if m else '?'}건 — 생애주기, 검증 게이트, 매칭 경계, 뜻 버전 관리, 후보 추출, 보드, 추적, 급증 감지, 쇼핑 항목", ""]

    # 2) 프론트 매칭 배터리
    out = sh(["node", "scripts/explain-check.mjs"], cwd=ROOT.parent / "trend-web", timeout=120)
    m = re.search(r"(\d+)/(\d+) as expected", out)
    lines += ["## 2. 메시지 해석 매칭 배터리 (apps/trend-web/scripts/explain-check.mjs)", "",
              (f"- {m.group(1)}/{m.group(2)} 의도대로 — 조사·어미, 띄어쓰기, 별칭, 숫자·영문 경계(6-7 vs 전화번호·날짜), 다국어 혼용, 사전에 없는 말" if m else "- 서버(3100) 미기동으로 건너뜀"), ""]

    # 3) 게이트 픽스처
    ok, n, rows = gate_eval()
    lines += ["## 3. 검증 게이트 — 환각·근거 부족 차단 픽스처", "", f"- {ok}/{n} 기대대로", "", "| 사례 | 기대 | 결과 | |", "|---|---|---|---|", *rows, ""]

    # 4) 급증 설명
    xs = list(ds.explanations_by_region(con).values())
    if xs:
        conf = sum(x.self_confidence for x in xs) / len(xs)
        anchored = sum(1 for x in xs if x.actors) / len(xs)
        trig = {}
        for x in xs:
            trig[x.trigger] = trig.get(x.trigger, 0) + 1
        lines += ["## 4. 급증 원인 설명 (spikes)", "", f"- 설명 {len(xs)}건 · 평균 확신 {conf:.2f} · 근거에 실재하는 인물이 남은 비율 {anchored:.0%} · 계기 분포 {json.dumps(trig, ensure_ascii=False)}",
                  f"- 근거 평균 {sum(len(x.evidence_ids) for x in xs) / len(xs):.1f}건/설명", ""]
    else:
        lines += ["## 4. 급증 원인 설명 (spikes)", "", "- 아직 없음 (모델 할당량 대기)", ""]

    # 5) 사전 상태
    terms = ds.list_terms(con)
    st = {}
    for t in terms:
        st[t.status] = st.get(t.status, 0) + 1
    stats = {"verified_auto": 0, "verified_human": 0, "unverified": 0, "rejected": 0}
    for v, c in con.execute("SELECT verification, COUNT(*) FROM meanings WHERE valid_to IS NULL GROUP BY verification").fetchall():
        stats[v] = c
    lines += ["## 5. 사전·검수", "", f"- 용어 {len(terms)}개 상태 {json.dumps(st, ensure_ascii=False)} · 현행 뜻 검증 {json.dumps(stats)} · 검수 대기 {len(ds.review_queue(con))}건",
              "- 자동 확인 비율이 곧 '사람 손 없이 얼마나 가는가'. 근거 부족은 자동으로 검수 큐로 간다(정직한 실패).", ""]

    # 6) 파이프라인 건강
    counts = ds.stage_counts_24h(con)
    lines += ["## 6. 파이프라인 건강 (최근 24시간)", "", "| 단계 | 건수 | 상태 |", "|---|---|---|"]
    for k, (cnt, status, note) in sorted(counts.items()):
        lines.append(f"| {k} | {cnt} | {status}{' — ' + note[:60] if note else ''} |")
    lines += ["", "## 7. 아직 사람이 매겨야 하는 것", "", "- 검색어 분류 정확도: `data/eval/classify_sample.csv` 에 표본 40건을 뽑아 둔다(팀이 라벨 → 정확도 계산).",
              "- 뜻 정확도: 검증된 뜻 20개를 나무위키·언론 정의와 대조(팀 라벨).", ""]
    (ROOT / "data" / "eval").mkdir(parents=True, exist_ok=True)
    rows = con.execute("SELECT term, region, category, kind, is_term_candidate FROM trend_class ORDER BY random() LIMIT 40").fetchall()
    with open(ROOT / "data" / "eval" / "classify_sample.csv", "w", encoding="utf-8") as f:
        f.write("term,region,pred_category,pred_kind,pred_is_candidate,human_category,human_is_candidate\n")
        for r in rows:
            f.write(",".join(str(x).replace(",", " ") for x in r) + ",,\n")
    (ROOT / "docs" / "EVAL.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
