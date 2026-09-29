"""사전 전수 점검. 확인된(verified) 항목마다 저장된 근거로 게이트를 다시 돌려 약한 항목을 찾고, 필요하면 근거를 더 모으거나 강등·제외한다.

  uv run scripts/audit_dictionary.py                      # 보고만
  uv run scripts/audit_dictionary.py --strengthen         # 약한 항목은 뉴스·커뮤니티·위키에서 근거를 더 모아 다시 판정
  uv run scripts/audit_dictionary.py --apply              # 그래도 약한 항목은 needs_review 로 강등 (공개 사전에서 빠짐, 검수 큐에 사유 기록)
  uv run scripts/audit_dictionary.py --reject "brics|very" --downgrade "Papa Aa Gaye"   # 표제어 이름으로 제외 / 강등 (구분자 |)

사람이 확인한(verified_human) 뜻은 '풀이가 근거 원문에 없음' 사유를 막지 않는다 — 풀이는 사람이 앵커다. 출처 수·1차 근거 부족은 그대로 막는다.
참고 문서가 없다는 사유(ADR 0003)도 사람이 확인한 뜻은 막지 않는다 — 사람의 승인이 문서가 드문 지역의 예외 길이다.
그 밖의 항목에는 참고 문서 규칙이 적용되므로, 문서 없는 말의 --apply 는 쓰지 않는다(Plan 12) — 사용자가 확인한 '문서 없음' 목록만
--downgrade "이름|이름" 으로 내린다. 문서 대조의 제안(고칠 안·위키끼리 다름·사전에서 뺄지)을 사람이 보고 있는 말은 내리지 않고 따로 보고한다.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.collectors import community, news_rss, wikipedia_search  # noqa: E402
from trend_agents.collectors.naver_search import for_model  # noqa: E402
from trend_agents.pipeline.match import mentions  # noqa: E402
from trend_agents.pipeline.research import first_party_evidence  # noqa: E402
from trend_agents.schemas import Evidence, MeaningDraft  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402
from trend_agents.verification import NO_REFERENCE, gate  # noqa: E402
from trend_agents.storage.db import Connection

REGION_BY_LANG = {"ko": "KR", "ja": "JP", "id": "ID", "de": "DE", "pt": "BR", "hi": "IN", "te": "IN", "es": "MX", "th": "TH", "vi": "VN"}
BY = "team"


def blocking(reasons: list[str], human: bool) -> list[str]:
    out = [r for r in reasons if not r.endswith("제외됨")]
    if human:
        out = [r for r in out if "어떤 근거 원문에도 없음" not in r and r != NO_REFERENCE]
    return out


def strengthen(con: Connection, t, evs: list[Evidence]) -> list[Evidence]:
    """뉴스 검색·커뮤니티·위키에서 용어를 실제로 말하는 근거만 더 모은다."""
    region = REGION_BY_LANG.get(t.lang, "US")
    have = {e.evidence_id for e in evs}
    new: list[Evidence] = []
    for q in [t.canonical, *t.aliases[:2]]:  # 표제어와 대표 별칭으로 찾는다 ('속담 오타 밈' 은 '모르는 개 산책' 으로 찍힌다)
        try:
            db.upsert_news(con, news_rss.fetch_news(region if region in news_rss.LOCALES else "US", query=q, limit=20))
        except Exception as e:  # noqa: BLE001
            print(f"    news 실패 {type(e).__name__}")
        try:
            new += community.gather(q, region)[0]
        except Exception as e:  # noqa: BLE001
            print(f"    community 실패 {type(e).__name__}")
    new += [e for e in first_party_evidence(con, t.canonical, t.aliases) if e.evidence_id not in have]
    try:
        lang = t.lang if t.lang in {"ko", "ja", "id", "de", "pt", "es", "en"} else "en"
        for title in wikipedia_search.search(lang, t.canonical, limit=2):
            sm = wikipedia_search.summary(lang, title)
            if sm and sm.get("extract"):
                url = sm.get("content_urls", {}).get("desktop", {}).get("page", f"https://{lang}.wikipedia.org/wiki/{title}")
                new.append(Evidence(evidence_id=ds.new_id("e", url), kind="web", url=url, title=f"Wikipedia: {title}", source_domain=f"{lang}.wikipedia.org",
                                    observed_at=ds.utcnow() if hasattr(ds, "utcnow") else __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
                                    excerpt=sm["extract"][:400]))
    except Exception as e:  # noqa: BLE001
        print(f"    wikipedia 실패 {type(e).__name__}")
    new = [e for e in new if e.evidence_id not in have and mentions(f"{e.title} {e.excerpt}", t.canonical, t.aliases)]
    if new:
        ds.add_evidences(con, t.term_id, new)
    return new


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strengthen", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--reject", default="", help="표제어, | 구분")
    ap.add_argument("--downgrade", default="", help="표제어, | 구분")
    a = ap.parse_args()
    con = db.connect()
    by_name = {t.canonical: t for t in ds.list_terms(con)}

    for name in [x.strip() for x in a.reject.split("|") if x.strip()]:
        t = by_name.get(name)
        m = ds.current_meaning(con, t.term_id) if t else None
        if not t:
            print(f"제외 실패(없음): {name}"); continue
        if m:
            ds.set_verification(con, m.meaning_id, "rejected", BY)
        t.status = "retired"; ds.upsert_term(con, t, human=True); ds.decide_review(con, t.term_id, "reject", BY)
        print(f"제외: {name} → retired")
    for name in [x.strip() for x in a.downgrade.split("|") if x.strip()]:
        t = by_name.get(name)
        m = ds.current_meaning(con, t.term_id) if t else None
        if not t or not m:
            print(f"강등 실패(없음): {name}"); continue
        if ds.under_review(con, t.term_id):   # 검수 대기의 새 말(new) 줄이 사람이 보고 있는 제안을 덮지 않게
            print(f"강등 건너뜀(문서 대조 제안 검수 중): {name}"); continue
        ds.set_verification(con, m.meaning_id, "unverified", BY)
        t.status = "needs_review"; ds.upsert_term(con, t, human=True)
        ds.queue_review(con, t.term_id, MeaningDraft(**m.model_dump(include=set(MeaningDraft.model_fields))), ["표현인지 불확실 — 사람이 판단"], ds_count(con, t.term_id))
        print(f"강등: {name} → needs_review")

    weak = []
    busy = []              # 문서 대조의 제안을 사람이 보고 있어 내리지 않은 말
    verified = ds.list_terms(con, ("verified",))
    for t in verified:
        m = ds.current_meaning(con, t.term_id)
        if not m:
            weak.append((t, ["뜻 없음"])); continue
        human = m.verification == "verified_human"
        draft = MeaningDraft(**m.model_dump(include=set(MeaningDraft.model_fields)))
        evs = ds.list_evidences(con, t.term_id) if hasattr(ds, "list_evidences") else _evidences(con, t.term_id)
        v, reasons = gate(t.canonical, draft, for_model(evs), None, aliases=t.aliases)
        bl = blocking(reasons, human)
        if bl and a.strengthen:
            new = strengthen(con, t, evs)
            evs = _evidences(con, t.term_id)
            v, reasons = gate(t.canonical, draft, for_model(evs), None, aliases=t.aliases)
            bl = blocking(reasons, human)
            print(f"  보강 {t.canonical}: +{len(new)}건 → {'통과' if not bl else '아직 부족'}")
        if bl:
            weak.append((t, bl))
            if a.apply and ds.under_review(con, t.term_id):
                busy.append(t)
            elif a.apply:
                if not human:  # 상태와 검증이 어긋나지 않게. 사람이 확인한 뜻은 기록을 지우지 않는다 — 아래 재승격 경로가 그 표시를 본다
                    ds.set_verification(con, m.meaning_id, "unverified", BY)
                t.status = "needs_review"; ds.upsert_term(con, t, human=True)
                ds.queue_review(con, t.term_id, draft, bl, len(evs))
    # 강등돼 있던 '사람이 확인한 뜻' 이 근거 보강으로 통과하면 다시 verified
    for t in ds.list_terms(con, ("needs_review",)):
        m = ds.current_meaning(con, t.term_id)
        if not m or m.verification != "verified_human":
            continue
        draft = MeaningDraft(**m.model_dump(include=set(MeaningDraft.model_fields)))
        evs = _evidences(con, t.term_id)
        v, reasons = gate(t.canonical, draft, for_model(evs), None, aliases=t.aliases)
        if not blocking(reasons, True):
            if a.apply:
                t.status = "verified"; ds.upsert_term(con, t, human=True); ds.decide_review(con, t.term_id, "approve", BY, kind="new")
            print(f"  복귀 {t.canonical}: 근거 통과{' → verified' if a.apply else ''}")
    print(f"\n확인된 항목 {len(verified)}개 중 근거가 약한 것 {len(weak)}개{' → needs_review 로 강등' if a.apply else ''}")
    for t, bl in weak:
        print(f"  - {t.canonical}: {'; '.join(bl)}")
    if busy:
        print(f"\n문서 대조 제안을 검수 중이라 내리지 않은 것 {len(busy)}개 — 검수를 마친 뒤 다시 본다:")
        for t in busy:
            print(f"  - {t.canonical}")


def _evidences(con: Connection, term_id: str) -> list[Evidence]:
    return [Evidence.model_validate_json(r[0]) for r in con.execute("SELECT json FROM evidences WHERE term_id=?", (term_id,))]


def ds_count(con: Connection, term_id: str) -> int:
    return con.execute("SELECT COUNT(*) FROM evidences WHERE term_id=?", (term_id,)).fetchone()[0]


if __name__ == "__main__":
    main()
