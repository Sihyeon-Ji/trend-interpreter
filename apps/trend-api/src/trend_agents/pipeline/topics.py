"""주제(나라를 건너간 용어)의 나라별 차이 서술. 사용 지역이 2개 이상인 검증 용어마다, 각 나라의 근거(뉴스·커뮤니티·위키)를 모아
'그 나라에서는 무엇으로 바뀌었나'와 현지 밈 이름을 모델이 쓰고, 이름은 근거 원문에 실재하는 것만 남긴다. 실행당 6개 변형."""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ..collectors import community, news_rss, wikipedia_search
from ..collectors.naver_search import for_model
from ..schemas import Evidence, Text2
from ..storage import dictionary_store as ds
from .gemini import BudgetExhausted, budget_left, local_ok, structured
from .match import evidence_mentions, mentions
from .research import first_party_evidence
from .runs import stage
from ..storage.db import Connection

PER_RUN = 6


class VariantNote(BaseModel):
    local_name: str = Field(description="그 나라에서 이 용어를 부르는 표기. 근거에 없으면 원래 표기 그대로")
    what_changed: Text2 = Field(description="이 나라에서 무엇이 달라졌나 1~2문장 (ko/en/ja — 일본어 화면용 ja 도 쓴다)")
    local_memes: list[dict] = Field(default_factory=list, description="[{label, note_ko, note_en}] 근거 원문에 나오는 현지 밈·놀이·대사만")
    self_confidence: float = Field(ge=0, le=1)


PROMPT = """아래는 '{term}' 이(가) {region} 에서 어떻게 쓰이는지 보여 주는 근거다. 이것만 보고 JSON 으로 답하라.
- local_name: 그 나라에서 부르는 표기. 근거에 다른 표기가 없으면 "{term}" 그대로.
- what_changed: 원래 뜻·쓰임과 비교해 이 나라에서 무엇이 달라졌나(누가 어떻게 쓰나, 어떤 사건·인물과 엮였나). ko 와 en 각 1~2문장. 근거에 없으면 "근거 부족: 확인되지 않음" / "Insufficient evidence".
- local_memes: 근거 원문에 실제로 나오는 현지 밈·놀이·대사 이름만 (label, note_ko, note_en). 추측 금지.
- self_confidence: 근거가 차이를 직접 말하면 0.8 이상, 간접이면 0.5, 없으면 0.2 이하.

원래 뜻: {definition}

근거:
{notes}"""


def gather(con: Connection, term: str, region: str) -> list[Evidence]:
    evs: list[Evidence] = []
    news_region = region if region in news_rss.LOCALES else "US"
    try:
        for n in news_rss.fetch_news(news_region, query=term, limit=10):
            from urllib.parse import urlparse

            evs.append(Evidence(evidence_id=ds.new_id("e", n.link), kind="news", url=n.link, title=n.title[:200], source_domain=(n.source or urlparse(n.link).netloc).lower().replace(" ", ""),
                                observed_at=n.published_at or datetime.now(timezone.utc), excerpt=n.title))
    except Exception:
        pass
    c_evs, _ = community.gather(term, region)
    evs += c_evs
    try:
        lang = wikipedia_search.lang_for(region)
        for title in wikipedia_search.search(lang, term, limit=1):
            sm = wikipedia_search.summary(lang, title)
            if sm and sm["extract"]:
                evs.append(Evidence(evidence_id=ds.new_id("e", sm["url"] or title), kind="web", url=sm["url"], title=f"Wikipedia: {sm['title']}", source_domain=f"{lang}.wikipedia.org",
                                    observed_at=datetime.now(timezone.utc), excerpt=sm["extract"][:300]))
    except Exception:
        pass
    return evs


def run(con: Connection) -> dict:
    with stage(con, "topics") as r:
        todo: list[tuple] = []
        for t in ds.list_terms(con, ("verified",)):
            regions = sorted({u["region"] for u in ds.get_usage(con, t.term_id)})
            if len(regions) < 2:
                continue
            notes = ds.get_topic_notes(con, t.term_id)
            for reg in regions:
                if reg not in notes:
                    todo.append((t, reg))
        r.detail["pending"] = len(todo)
        for t, reg in todo[:PER_RUN]:
            if budget_left(con) < 1 and not local_ok():
                r.note = "예산 부족"
                break
            # 검색 결과 가운데 표제어가 실제로 든 것만 — 거르지 않고 저장해 딴 글('오살힘' 에 2022년 '오살 의식' 기사·KBS 드라마 문서)이
            # 사전 근거로 나가고 생애주기·리스크 입력을 부풀렸다(2026-09-29, 검토 3차)
            evs = [e for e in for_model(gather(con, t.canonical, reg) + first_party_evidence(con, t.canonical, t.aliases))
                   if evidence_mentions(e, t.canonical, t.aliases)]
            m = ds.current_meaning(con, t.term_id)
            shown, posts = community.for_prompt(evs)   # 커뮤니티·SNS 글은 건수만 — 현지 밈의 앵커도 보이는 출처에서만(ADR 0003)
            lines = [f"- [{e.kind}] {e.source_domain}: {e.title}" + (f" — {e.excerpt}" if e.excerpt and e.excerpt != e.title else "") for e in shown[:25]] + ([posts] if posts else [])
            try:
                parsed, model = structured(con, PROMPT.format(term=t.canonical, region=reg, definition=(m.definition if m else ""), notes="\n".join(lines) or "- (근거 없음)"), VariantNote, temperature=0.2)
            except BudgetExhausted as e:
                r.note = str(e)
                break
            except Exception as e:  # 한 주제의 형식 실패가 나머지를 막지 않는다
                r.note += f"{t.canonical}@{reg}:{type(e).__name__} "
                continue
            v = parsed if isinstance(parsed, VariantNote) else VariantNote.model_validate(parsed)
            corpus = "\n".join(f"{e.title} {e.excerpt}" for e in shown)
            v.local_memes = [x for x in v.local_memes if x.get("label") and mentions(corpus, x["label"])]  # 앵커: 근거 원문에 실재하는 밈만 (match.mentions 한 규칙)
            if not shown:
                v.self_confidence = min(v.self_confidence, 0.2)
            payload = v.model_dump()
            payload["evidence_ids"] = [e.evidence_id for e in evs[:20]]
            ds.add_evidences(con, t.term_id, evs)
            import json

            ds.set_topic_note(con, t.term_id, reg, json.dumps(payload, ensure_ascii=False), model)
            r.detail[f"{t.canonical}@{reg}"] = f"conf {v.self_confidence} memes {len(v.local_memes)} ev {len(evs)}"
            r.count += 1
    return {"topics": r}
