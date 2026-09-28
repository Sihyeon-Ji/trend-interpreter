"""사전 전수 검토. 화면에 나가는 항목(verified)에서 '사전 항목답지 않은 것' 을 찾아 낸다.

게이트(verification.gate)는 '이 표현이 실재하는가' 를 본다. 여기서는 그 다음 질문을 본다 —
**뜻이 실제로 쓸모 있는가, 이게 애초에 표제어가 될 만한 말인가.**

찾는 것:
  되풀이   뜻이 표제어를 그대로 옮겨 적었다 ("AI slop" → "AI slop")
  빈말     "인터넷 밈", "ネット流行語の一つ" 처럼 분류만 적고 뜻이 없다
  미상     "근거 부족", "명확한 정의가 없으며" 처럼 모른다고 적었다
  번역없음 뜻이 외국어 그대로다 (한국어 화면에 일본어가 나간다)
  근거없음 근거가 0건인데 verified 다
  비표현   위키백과가 인물·사건·행사라고 설명한 것 (data/wiki_memes.json 의 설명문 대조)

  uv run scripts/review_dictionary.py                # 보고만
  uv run scripts/review_dictionary.py --demote       # 깃발이 붙은 항목을 needs_review 로 내린다 (삭제하지 않는다)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

# 뜻이 아니라 분류만 적은 것
_EMPTY = re.compile(
    r"^(인터넷\s*)?밈(\s*\(meme\))?\.?$|^ミーム$|ネット流行語の一つ|インターネット・?ミーム(の一つ)?[。.]?$|"
    r"^[^。.]{0,24}の一つ[。.]?$|^internet meme\.?$", re.I)
# 모른다고 적은 것
_UNKNOWN = re.compile(r"근거 부족|명확(한|하게) (사전적 )?(정의|의미)(는|가)? ?(없|제시되지)|특정 맥락에서 (사용|언급)되는|"
                      r"의미는 명확하지 않|정의되어 있지 않", re.I)
# 위키백과 설명이 '표현' 이 아니라고 말하는 것 — 사람, 그리고 말 자체가 아니라 말의 갈래를 설명하는 문서
_NOT_EXPR = re.compile(
    r"\b(born \d{4}|teenager|youtuber|streamer|influencer|rapper|singer|actor|actress|politician|businessman|"
    r"footballer|athlete|chef|suspect)\b|"
    r"\b(debates?|election|contests?|championship|tournament)\b|"
    r"の?(総称|一種)|[^。]{0,10}(スラング|俗語|ミーム|밈|유행어)\s*(の総称|全般|そのもの)|"
    r"シェフ|の愛称|\(\d{4}[–-]", re.I)
# 뜻이 표제어를 그대로 옮긴 번역에 그친 것 — "Looking for a Man in Finance" → "금융 분야의 남성을 찾는 것"
_TOO_SHORT = 26
# 뜻이 "누구누구다" 라고 사람을 소개하는 것. 표제어가 그 사람의 본명이면 유행어가 아니라 인명이다.
_PERSON_DEF = re.compile(r"(청소년|십대|소년|소녀|남성|여성|인물|사람|유튜버|스트리머|가수|배우|선수|셰프|요리사)"
                         r"(으?로 알려|이다|입니다|을 지칭|를 지칭|의 이름)|"
                         r"(と(呼ばれる|いう)人物|人物の(愛称|名前)ではなく本名)", re.I)
# 화면에서 내려야 할 깃발. 번역없음(채우면 됨)·짧은뜻(줄임말은 짧은 게 정답)은 뺀다.
DEMOTE = {"되풀이", "빈말", "미상", "뜻없음", "근거없음", "갈래이름", "비표현", "인명"}
# 동어반복은 깃발만 세운다 — "'내 추구미는 청순'처럼 쓴다" 같은 정상적인 용례 인용까지 걸려서,
# 규칙만으로는 진짜 동어반복과 가르지 못한다. 사람이 읽고 --names 로 내린다.

_JA = re.compile(r"[぀-ゟ゠-ヿ]")          # 히라가나·가타카나
_KO = re.compile(r"[가-힣]")


def _is_proper_name(term: str, description: str) -> bool:
    """표제어가 사람·행사의 고유명사인가. 별명·수식어는 아니다."""
    if term.lower() in description.lower():        # 설명이 그 이름을 그대로 부른다
        return True
    words = term.split()
    return len(words) in (2, 3) and all(w[:1].isupper() and w.isascii() for w in words)


def _norm(s: str) -> str:
    return re.sub(r"[^0-9a-z가-힣ぁ-んァ-ン一-鿿]", "", (s or "").lower())


def flags(con, t, m, wiki_desc: dict[str, str]) -> list[str]:
    out: list[str] = []
    d = (m.definition if m else "").strip()
    ev = con.execute("SELECT COUNT(*) FROM evidences WHERE term_id=?", (t.term_id,)).fetchone()[0]

    if not d:
        out.append("뜻없음")
    else:
        nd, nc = _norm(d), _norm(t.canonical)
        if nd == nc or (nc and nd.startswith(nc) and len(nd) <= len(nc) + 6):
            out.append("되풀이")
        if _EMPTY.search(d):
            out.append("빈말")
        if _UNKNOWN.search(d):
            out.append("미상")
        if len(d) < _TOO_SHORT and "되풀이" not in out and "빈말" not in out:
            out.append("짧은뜻")
        # 뜻이 표제어를 도로 가리킨다 — "'Chill Guy'로도 알려져 있음", "シャミ子が悪い、ということを指す言葉"
        if nc and nc in nd and len(nd) < len(nc) * 3 + 30 and "되풀이" not in out:
            out.append("동어반복")
        # 한국어 화면에 외국어 뜻이 그대로 나가는가 (ko 번역본이 없을 때만 문제)
        if _JA.search(d) and not _KO.search(d) and not ds.get_translation(con, t.term_id, "ko"):
            out.append("번역없음")
    if ev == 0:
        out.append("근거없음")
    if d and _PERSON_DEF.search(d) and _is_proper_name(t.canonical, d):
        out.append("인명")
    desc = wiki_desc.get(t.canonical.lower(), "")
    # 사람을 설명한다고 해서 표제어가 아닌 건 아니다 — '塩振りおじさん'(솔트배의 일본어 별명)처럼
    # **별명 자체가 유행어**인 경우가 있다. 표제어가 그 사람의 본명일 때만 사전 항목이 아니다.
    if desc and _NOT_EXPR.search(desc) and _is_proper_name(t.canonical, desc):
        out.append(f"비표현({desc[:30]})")
    # 표제어 자체가 '인터넷 밈·속어' 라는 갈래 이름이면 사전 항목이 아니라 목차다
    if re.fullmatch(r"(인터넷\s*)?(밈|유행어|슬랭|속어)|(internet\s+)?(memes?|slang)|インターネット(・?ミーム|スラング)|ネットスラング",
                    t.canonical.strip(), re.I):
        out.append("갈래이름")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demote", action="store_true",
                    help="쓸모없는 뜻·표제어가 아닌 것을 needs_review 로 내린다 (삭제하지 않는다). "
                         "번역없음·짧은뜻은 내리지 않는다 — 번역은 채우면 되고, 줄임말은 짧은 뜻이 정답이다")
    ap.add_argument("--status", default="verified")
    ap.add_argument("--names", help="사람이 읽고 판단한 표제어를 직접 내린다 (쉼표로 구분)")
    ap.add_argument("--reason", default="전수 검토(사람)", help="--names 와 함께 남길 사유")
    ap.add_argument("--reject", action="store_true",
                    help="--names 를 '사전 항목이 아님' 으로 확정한다 (retired + 뜻 rejected). "
                         "needs_review 와 달리 다시 조사해도 되살아나지 않는다")
    a = ap.parse_args()

    wiki_desc: dict[str, str] = {}
    cache = Path("data/wiki_memes.json")
    if cache.exists():
        for r in json.loads(cache.read_text(encoding="utf-8")):
            if r.get("term") and r.get("description"):
                wiki_desc[r["term"].lower()] = r["description"]

    con = db.connect()
    terms = ds.list_terms(con, tuple(a.status.split(",")))
    hit: list[tuple] = []
    for t in terms:
        m = ds.current_meaning(con, t.term_id)
        f = flags(con, t, m, wiki_desc)
        if f:
            hit.append((t, m, f))

    print(f"{a.status} {len(terms)}개 중 {len(hit)}개에 깃발\n")
    for t, m, f in sorted(hit, key=lambda x: x[0].canonical.lower()):
        print(f"  [{','.join(f)}] {t.canonical} ({t.lang})")
        print(f"      {(m.definition if m else '')[:96]}")
    print("\n깃발 종류:", dict(Counter(x.split("(")[0] for _, _, fs in hit for x in fs)))

    if a.names:
        want = [x.strip() for x in a.names.split(",") if x.strip()]
        done = 0
        for name in want:
            t = ds.find_term(con, name)
            if not t or t.status not in ("verified", "needs_review"):
                print(f"  건너뜀: {name} ({'없음' if not t else t.status})")
                continue
            m = ds.current_meaning(con, t.term_id)
            if a.reject:
                # 화면 검수의 '거부' 와 같은 경로. retired 는 재조사 대상에서 빠지므로 자동으로 되살아나지 않는다.
                if m:
                    ds.set_verification(con, m.meaning_id, "rejected", "audit")
                t.status = "retired"
            else:
                t.status = "needs_review"
            ds.upsert_term(con, t)
            if m:
                ds.queue_review(con, t.term_id, m, [a.reason], 0)
                ds.decide_review(con, t.term_id, "reject" if a.reject else "", "audit")
            done += 1
            print(f"  {'거부' if a.reject else '내림'}: {name} — {a.reason}")
        con.commit()
        print(f"\n{done}개를 {'사전 항목 아님(retired)' if a.reject else 'needs_review'} 로 처리했다.")
        return

    if a.demote:
        down = [(t, m, f) for t, m, f in hit if any(x.split("(")[0] in DEMOTE for x in f)]
        for t, m, f in down:
            t.status = "needs_review"
            ds.upsert_term(con, t)
            if m:
                ds.queue_review(con, t.term_id, m, [f"전수 검토: {', '.join(f)}"], 0)
        con.commit()
        print(f"\n{len(down)}개를 needs_review 로 내리고 검수 큐에 사유를 남겼다. 뜻과 판은 지우지 않았다.")
        for t, _, f in down:
            print(f"   {t.canonical} — {', '.join(f)}")


if __name__ == "__main__":
    main()
