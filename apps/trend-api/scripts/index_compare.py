"""'그 자리에서 읽기'(지금 챗봇: 사전 도구·조사해 둔 작품 밈·위키 직접 읽기)와 '색인에서 찾기'(index-pilot.db 조각 + 같은 모델)를
같은 질문으로 견준다(2026-10-06). 정답은 지난주 조사로 확인한 밈 이름 — 답에 그 이름이 있으면 맞힘.
  uv run scripts/index_compare.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.config import CHAT_MODEL  # noqa: E402
from trend_agents.pipeline import ask, gemini  # noqa: E402
from trend_agents.pipeline import doc_index as D  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

PILOT = Path(__file__).resolve().parents[1] / "data" / "index-pilot.db"
QS = [  # (질문, 정답 이름들, 갈래)
    ("오징어 게임에서 '이 게임 해 봤다'고 외치는 장면으로 만든 밈이 뭐야?", ["나는 이 게임을 해 봤어요", "I've played these games before"], "설명"),
    ("오징어 게임 때문에 유행한 '친한 친구'라는 뜻의 말은?", ["깐부"], "설명"),
    ("더 글로리에서 문동은이 박연진을 비꼬며 외친 응원 대사 밈은?", ["멋지다 연진아"], "묻힌 밈"),
    ("스파이 패밀리에서 아냐가 땅콩 좋아한다고 한 대사가 일본 유행어 상을 받았다던데 그 말이 뭐야?", ["ピーナッツが好き", "땅콩이 좋아", "땅콩 좋아"], "묻힌 밈"),
    ("오징어 게임 시즌3에서 한국에서 가장 반응이 컸던 대사는?", ["도시락"], "묻힌 밈"),
    ("오징어 게임의 무궁화 꽃이 피었습니다 놀이는 영어권에서 뭐라고 불러?", ["Red Light, Green Light", "Red Light Green Light"], "나라 사이"),
    ("축구 팬들이 오징어 게임을 패러디해서 상대 팀 창단 연도로 만든 구호가 있었다던데?", ["1907번 탈락", "1905번 탈락"], "묻힌 밈"),
    ("태국에서 더 글로리 때문에 생긴 학교폭력 폭로 해시태그는?", ["The Glory Thai", "TheGloryThai"], "나라 사이"),
    ("더 글로리와 군대를 합친 말이 뭐야?", ["더 군로리"], "묻힌 밈"),
    ("오징어 게임 달고나 뽑기는 해외에서 무슨 챌린지가 됐어?", ["Dalgona", "달고나 챌린지"], "나라 사이"),
    ("오징어 게임에서 기훈이 '얼음!'이라고 외친 장면은 영어권 밈에서 뭐라고 해?", ["Freeze"], "나라 사이"),
    ("스파이 패밀리 아냐가 거만하게 웃는 표정 밈 이름은?", ["Heh"], "설명"),
    ("오징어 게임에서 일남이 '이러다가는 다 죽어'라고 하는 대사 밈 알려줘", ["다 죽어"], "설명"),
    ("오징어 게임 시즌2에서 다 같이 원을 돌며 노래하는 게임은 뭐라고 불러?", ["둥글게 둥글게", "Mingle"], "설명"),
    ("인도네시아에서는 무궁화 꽃이 피었습니다를 뭐라고 불러?", ["Lampu merah"], "나라 사이"),
    ("오징어 게임 타노스 캐릭터가 랩으로 유행시킨 말은?", ["I'm a legend", "아임 어 레전드"], "묻힌 밈"),
]

RAG = """아래는 위키 문서에서 찾은 조각들이다. 이 조각에 있는 내용만으로 질문에 한국어 두세 문장으로 답하라.
밈 이름은 조각에 쓰인 그대로 적고, 근거가 된 문서 제목을 괄호로 붙여라. 조각에 답이 없으면 '찾지 못했다' 고만 하라.

질문: {q}

조각:
{ctx}"""


def norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", s or "")).lower()


def hit(text: str, golds: list[str]) -> bool:
    t = norm(text)
    return any(norm(g) in t for g in golds)


def main() -> None:
    con = db.connect()
    idx = D.connect(PILOT)
    rows = []
    for q, golds, kind in QS:
        t = time.time()
        a = ask.run(con, q, lang="ko", log_miss=False)
        live_s, live = time.time() - t, a.text
        t = time.time()
        found = D.search(idx, q, k=6)
        ctx = "\n\n".join(f"[{i}] {f['title']} > {f['heading']} ({f['url']})\n{f['text']}" for i, f in enumerate(found, 1))
        resp, _ = gemini.generate(con, RAG.format(q=q, ctx=ctx), model=CHAT_MODEL, allow_local=False)
        rag_s, rag = time.time() - t, (resp.text or "").strip()
        rows.append({"q": q, "kind": kind, "gold": golds, "live_ok": hit(live, golds), "rag_ok": hit(rag, golds),
                     "retrieved_ok": hit(" ".join(f["text"] + " " + f["title"] for f in found), golds),
                     "live_s": round(live_s, 1), "rag_s": round(rag_s, 1), "live": live[:300], "rag": rag[:300],
                     "sources": [f["url"] for f in found[:3]]})
        r = rows[-1]
        print(f"{'O' if r['live_ok'] else 'X'} 지금 {r['live_s']:5.1f}s | {'O' if r['rag_ok'] else 'X'} 색인 {r['rag_s']:5.1f}s "
              f"(조각에 {'있음' if r['retrieved_ok'] else '없음'}) | {kind} | {q[:40]}", flush=True)
    n = len(rows)
    for kind in dict.fromkeys(k for _, _, k in QS):
        rs = [r for r in rows if r["kind"] == kind]
        print(f"[{kind}] 지금 {sum(r['live_ok'] for r in rs)}/{len(rs)} · 색인 {sum(r['rag_ok'] for r in rs)}/{len(rs)}")
    print(f"전체 지금 {sum(r['live_ok'] for r in rows)}/{n} · 색인 {sum(r['rag_ok'] for r in rows)}/{n} (조각에 정답 {sum(r['retrieved_ok'] for r in rows)}/{n})"
          f" · 평균 시간 지금 {sum(r['live_s'] for r in rows) / n:.1f}s · 색인 {sum(r['rag_s'] for r in rows) / n:.1f}s")
    out = Path(__file__).resolve().parents[1] / "data" / "work" / f"index-compare-{time.strftime('%m%d-%H%M')}.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
