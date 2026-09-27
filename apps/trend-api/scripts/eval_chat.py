"""챗봇 답변 평가. 여러 모양의 질문을 던져 **객관적으로 확인 가능한 것**만 채점한다.

'답이 좋아 보인다' 는 채점 기준이 못 된다. 여기서 보는 것은 규칙으로 판정할 수 있는 것들이다:
지어내지 않았는가, 질문 모양에 맞는 답인가, 되묻지 않았는가, 마크다운·도구 이름·내부 지시문이 새지 않았는가.

프롬프트를 고칠 때마다 이걸 돌려 **전체 점수**를 본다. 한 질문만 좋아지고 나머지가 나빠지면 고친 게 아니다.

  uv run scripts/eval_chat.py                 # 전체
  uv run scripts/eval_chat.py --only word     # 한 모양만
  uv run scripts/eval_chat.py --runs 3        # 같은 질문 3번씩 (흔들림 보기)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.pipeline.tools import usable  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import sqlite_store as db  # noqa: E402

WEB = "http://127.0.0.1:3100/api/chat"

# shape: 이 질문에 어떤 모양의 답이 나와야 하는가
CASES = [
    # 사전에 있는 한 낱말
    {"id": "word-known", "shape": "term", "q": "럭키비키 뜻이 뭐야?"},
    {"id": "word-known2", "shape": "term", "q": "추구미가 무슨 뜻이야?"},
    # 한글로 적은 외래어 (원어로 사전에 있음)
    {"id": "word-translit", "shape": "term", "q": "트랄랄레로 트랄랄라 뜻이 뭐야?"},
    # 사전에 없지만 인터넷에는 있음
    {"id": "word-live", "shape": "live", "q": "delulu가 뭐야?", "term": "delulu"},
    {"id": "word-live2", "shape": "live", "q": "Labubu가 뭐야?", "term": "Labubu"},
    # 아무 데도 없음
    {"id": "word-none", "shape": "none", "q": "끄뜨쁘흐뜨가 뭐야?"},
    # 뜻으로 찾기 (이름을 모를 때)
    {"id": "by-meaning", "shape": "term", "q": "AI로 만든 이탈리아 캐릭터 밈 이름이 뭐였지?"},
    # 목록
    {"id": "list", "shape": "list", "q": "20대가 쓰는 말 정리해줘"},
    {"id": "list-why", "shape": "list", "q": "한국에서 쓰는 말들 왜 떴는지 알려줘"},
    # 누가 쓰나
    {"id": "usage", "shape": "any", "q": "럭키비키 누가 써?"},
    # 붙여 넣은 문장
    {"id": "explain", "shape": "explain", "q": "오늘 진짜 럭키비키잖아 ㅋㅋ 추구미 찾았다 이게 무슨 뜻이야?"},
    # 앞을 받는 말
    {"id": "meta", "shape": "any", "q": "너가 사용 가능한 도구들 알려줘"},
    {"id": "followup", "shape": "any", "q": "비슷한것도 없어?",
     "history": [{"role": "user", "content": "에스프레쏘 어쌔씨노 이런건 뭐야?"},
                 {"role": "assistant", "content": "사전에 아직 없습니다."}]},
]

# 별도 묶음. 위 CASES 에 맞춰 고친 것이 **다른 질문에도 통하는지** 보려고 따로 둔다.
# 프롬프트를 손볼 때 이쪽은 보지 않고 고친 뒤, 마지막에만 돌려서 일반화를 확인한다.
HELD_OUT = [
    {"id": "h-word-known", "shape": "term", "q": "자만추가 무슨 말이야?"},
    {"id": "h-word-known2", "shape": "term", "q": "알잘딱깔센 뜻 알려줘"},
    {"id": "h-translit", "shape": "term", "q": "퉁퉁퉁퉁 사후르 뭐야?"},
    {"id": "h-live", "shape": "live", "q": "rizz가 뭐야?", "term": "rizz"},
    {"id": "h-none", "shape": "none", "q": "뷁쓰뮈뜨가 뭐야?"},
    {"id": "h-by-meaning", "shape": "term", "q": "점심 메뉴 골라달라고 할 때 쓰는 줄임말이 뭐였지?"},
    {"id": "h-list", "shape": "list", "q": "요즘 10대가 쓰는 표현 뭐가 있어?"},
    {"id": "h-list-why", "shape": "list", "q": "한국 유행어들은 어디서 시작된 거야?"},
    {"id": "h-usage", "shape": "any", "q": "추구미 어느 나라에서 써?"},
    {"id": "h-explain", "shape": "explain", "q": "야 오늘 느좋이다 진짜 무공해 그 자체 이거 해석 좀"},
    {"id": "h-meta", "shape": "any", "q": "넌 뭘 할 수 있어?"},
    # 더 다양한 모양 — 나라·유래·비교·영어·오타·긴 문장
    {"id": "h-country", "shape": "any", "q": "요즘 일본에서 뭐가 떠?"},
    {"id": "h-origin", "shape": "term", "q": "밤티는 어디서 나온 말이야?"},
    {"id": "h-compare", "shape": "any", "q": "영크크랑 늙크크 차이가 뭐야?"},
    {"id": "h-english", "shape": "any", "q": "what does skibidi mean?"},
    {"id": "h-typo", "shape": "term", "q": "럭키 비키가 뭐야?"},
    {"id": "h-long", "shape": "explain", "q": "친구가 카톡으로 '오늘 점메추 좀 ㅋㅋ 나 완전 무공해 스타일로 가고싶음' 이랬는데 무슨 말이야?"},
    {"id": "h-when", "shape": "any", "q": "추구미 언제부터 쓰기 시작했어?"},
    {"id": "h-who", "shape": "any", "q": "밤티는 누가 주로 써?"},
]

TOOL_NAMES = r"lookup_term|search_terms|why_trending|country_trends|term_usage|list_terms"
MD = re.compile(r"\*\*.+?\*\*|__.+?__")
ASKS_BACK = re.compile(r"(보여|알려|찾아|검색해)\s*드릴까요|말씀해\s*주(세요|시겠)|어떤\s*\S{0,12}(단어|표현|밈|유행어)|무엇을\s*(찾|알)")
GUARD = re.compile(r"지어내지|목록에 있는 이름만|사전에 없다고만 답")
DENY = re.compile(r"사전에\S*\s*(아직\s*)?없|검증된 사전에 없|찾을 수 없|지금 찾아보니")
QUOTED = re.compile(r"['\"“”‘’]([^'\"“”‘’\n]{2,40})['\"“”‘’]")
CLAIMS = re.compile(r"(사전|표제어|등재|수록|계열)[^.!?\n]{0,40}(있으며|있습니다|있어요|올라\s*있)|등재|수록")
CLAIM_EV = re.compile(r"근거[는가]?\s*\d+\s*건|\d+\s*건의 근거")


def ask(text: str, history: list | None = None, timeout: int = 240) -> dict:
    """질문 경로는 진행 상황을 흘려보낸다(SSE) — 마지막 result 만 쓴다. 해석 경로는 그냥 JSON."""
    body = json.dumps({"text": text, "locale": "ko", "history": history or [], "eval": True}).encode()
    req = urllib.request.Request(WEB, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8")
        if "text/event-stream" not in (r.headers.get("content-type") or ""):
            return json.loads(raw)
    out: dict = {"kind": "answer", "answer": "", "cards": [], "termIds": [], "steps": []}
    for chunk in raw.split("\n\n"):
        ev = re.search(r"^event:\s*(.+)$", chunk, re.M)
        data = re.search(r"^data:\s*(.+)$", chunk, re.M)
        if not ev or not data:
            continue
        try:
            payload = json.loads(data.group(1))
        except ValueError:
            continue
        if ev.group(1).strip() == "progress":
            out["steps"].append(payload.get("label", ""))
        elif ev.group(1).strip() == "result":
            out.update({"answer": payload.get("answer", ""), "cards": payload.get("cards", []),
                        "termIds": payload.get("term_ids", [])})
    return out


def check(con, case: dict, res: dict) -> list[str]:
    """어긴 규칙 목록. 비어 있으면 통과."""
    bad: list[str] = []
    kind = res.get("kind")
    answer = str(res.get("answer") or "")
    cards = res.get("cards") or []
    types = {c.get("type") for c in cards}
    term_ids = res.get("termIds") or []

    if kind == "explain":
        plain = str((res.get("result") or {}).get("plain") or "")
        if not plain:
            bad.append("해석 결과 없음")
        if case["shape"] not in ("explain", "any"):
            bad.append(f"모양 어긋남(explain, 기대 {case['shape']})")
        return bad

    # --- 어느 질문에나 적용되는 규칙 ---
    if not answer.strip():
        bad.append("빈 답")
    if MD.search(answer):
        bad.append("마크다운 강조")
    if re.search(TOOL_NAMES, answer):
        bad.append("도구 이름 노출")
    if GUARD.search(answer):
        bad.append("내부 지시문 노출")
    if ASKS_BACK.search(answer):
        bad.append("되묻기")
    if len(answer) > 900:
        bad.append(f"너무 김({len(answer)}자)")
    # 표제어가 '있다' 고 주장하는 문장만 본다 — 어원 설명("'추구(하는)'와 '미'가 합쳐진 말")은 인용이 아니다
    for sent in re.split(r"(?<=[.!?])\s+", answer):
        if not CLAIMS.search(sent):
            continue
        for name in QUOTED.findall(sent):
            if name.lower() in case["q"].lower():
                continue
            if not ds.find_term(con, name) and not any(name in str(c) for c in cards):
                bad.append(f"없는 표제어를 있다고 함: {name}")
                break
    if CLAIM_EV.search(answer) and not term_ids:
        bad.append("근거 건수를 말했는데 표제어가 없음")
    if case["id"].endswith("meta") and len(res.get("steps") or []) < 2:
        return bad          # 속을 묻는 말은 도구를 부르지 않고 바로 답한다 — 진행 표시가 없어도 된다
    # 오래 걸려도 무엇을 하는 중인지 보여야 한다 — 진행 표시가 오지 않으면 화면이 멈춘 것처럼 보인다
    if len(res.get("steps") or []) < 2:
        bad.append("진행 표시 없음")

    # --- 모양별 규칙 ---
    # 사전은 계속 자란다. "아직 없는 말" 로 적어 둔 질문이 그새 사전에 오르면
    # 실시간 찾아보기가 아니라 사전으로 답하는 게 맞다 — 기대 모양을 데이터에 맞춰 바꾼다.
    shape = case["shape"]
    # 제품과 같은 잣대를 쓴다: 표제어가 있어도 뜻이 쓸 수 없으면 '없는 것' 으로 다룬다(tools.usable).
    if shape == "live" and case.get("term"):
        hit = ds.find_term(con, case["term"])
        if hit and usable(con, hit):
            shape = "term"
    if shape == "term":
        if "term" not in types:
            bad.append("표제어 카드 없음")
        if DENY.search(answer) and "term" not in types:
            bad.append("사전에 있는데 없다고 함")
    elif shape == "list":
        lst = next((c for c in cards if c.get("type") == "list"), None)
        if not lst:
            bad.append("목록 카드 없음")
        elif len(lst.get("items", [])) < 3:
            bad.append("목록이 너무 짧음")
        elif answer.count("\n-") >= 3 or answer.startswith("사전에 "):
            bad.append("표를 본문에 그대로 옮김")
    elif shape == "live":
        if "live" not in types:
            bad.append("실시간 카드 없음")
        if not DENY.search(answer):
            bad.append("검증 전임을 밝히지 않음")
    elif shape == "none":
        if types:
            bad.append(f"없는 말인데 카드가 나옴({types})")
        if not DENY.search(answer):
            bad.append("없다고 말하지 않음")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--held", action="store_true", help="따로 둔 묶음으로 일반화 확인")
    a = ap.parse_args()

    con = db.connect()
    pool = HELD_OUT if a.held else CASES
    cases = [c for c in pool if not a.only or a.only in c["id"]]
    rows, total_bad = [], 0
    for c in cases:
        for n in range(a.runs):
            t0 = time.time()
            try:
                res = ask(c["q"], c.get("history"))
            except Exception as e:
                rows.append((c["id"], n, [f"호출 실패 {type(e).__name__}"], 0.0, ""))
                total_bad += 1
                continue
            bad = check(con, c, res)
            total_bad += 1 if bad else 0
            head = str(res.get("answer") or (res.get("result") or {}).get("plain") or "")[:70].replace("\n", " ")
            rows.append((c["id"], n, bad, time.time() - t0, head))

    print(f"{'질문':<16} {'회':<3} {'초':<5} 결과")
    for cid, n, bad, el, head in rows:
        mark = "통과" if not bad else "실패: " + ", ".join(bad)
        print(f"{cid:<16} {n:<3} {el:<5.1f} {mark}")
        if bad:
            print(f"{'':<26}답: {head}")
    ok = len(rows) - total_bad
    print(f"\n점수 {ok}/{len(rows)} ({ok * 100 // max(1, len(rows))}%)")


if __name__ == "__main__":
    main()
