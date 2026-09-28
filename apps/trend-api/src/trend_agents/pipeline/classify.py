"""2단계 분류. 트렌드 검색어에 카테고리와 '사전 후보 여부'를 붙인다. 인덱스 매핑 배치 JSON — 순서가 어긋나면 그 배치는 버린다."""
from __future__ import annotations


from ..config import REGIONS_FOCUS
from ..schemas import TrendClassification
from ..storage import dictionary_store as ds
from .gemini import BudgetExhausted, local_ok, structured
from .runs import stage
from ..storage.db import Connection

BATCH = 40
PROMPT = """You label trending Google search queries from {region_note}. For EACH item return one object with the same "i".
category: one of slang_meme | song_challenge | fashion_beauty | food | product | people_content | sports_event
  - people_content: celebrities, shows, films, games, creators, politicians, news figures
  - sports_event: matches, teams, tournaments, elections, weather, disasters, holidays, exams
  - slang_meme: slang, memes, catchphrases, internet phenomena, challenges that are words/phrases
kind: slang_meme | song | challenge | person | event | sports | product | food | fashion | place | other
is_term_candidate: true ONLY if the query is a slang term, meme, abbreviation, catchphrase or challenge name whose MEANING people would look up. Names of people, teams, places, companies, movies are false.
lang: ISO 639-1 of the query text.
term: copy the query text of that line EXACTLY as written (this is how we check the lines did not shift).
Do not invent items. Return exactly {n} objects.

Items:
{items}"""


def _norm(s: str) -> str:
    return "".join((s or "").split()).lower()


def _batch_prompt(rows: list[dict]) -> str:
    regions = sorted({r["region"] for r in rows})
    items = "\n".join(f'{i}. "{r["term"]}" (region {r["region"]}{", news: " + r["news_title"][:80] if r.get("news_title") else ""})' for i, r in enumerate(rows))
    return PROMPT.format(region_note=", ".join(regions), n=len(rows), items=items)


def run(con: Connection, max_batches: int = 6) -> dict:
    with stage(con, "classify") as r:
        batch = 15 if local_ok() else BATCH  # 12b 로컬 모델은 작은 배치가 안정적
        if local_ok():
            max_batches *= 2  # 로컬은 예산이 없다 — 미분류 적체(09-15 실측 600건+)를 따라잡게 한 번에 더 돈다
        rows = ds.unclassified_queries(con, regions=REGIONS_FOCUS, limit=batch * max_batches)
        if len(rows) < batch * max_batches:
            rows += ds.unclassified_queries(con, limit=batch * max_batches - len(rows))
        done = 0
        for b in range(0, len(rows), batch):
            chunk = rows[b:b + batch]
            if not chunk:
                break
            try:
                parsed, model = structured(con, _batch_prompt(chunk), list[TrendClassification])
            except BudgetExhausted as e:
                r.note = str(e)
                break
            except Exception as e:  # 한 배치의 형식 실패가 나머지 배치를 막지 않는다
                r.note += f"batch{b // batch}:{type(e).__name__} "
                continue
            labels = [p if isinstance(p, TrendClassification) else TrendClassification.model_validate(p) for p in (parsed or [])]
            # 작은 모델은 열다섯 줄 중 몇 줄을 빠뜨린다(실측: 배치 15 → 57%, 배치 6 → 77%).
            # 예전에는 80% 에 못 미치면 배치를 통째로 버려서 **맞게 분류된 줄까지 함께 버렸다**.
            # 이제 모델이 되읊은 표현이 그 줄의 표현과 같은지 확인해 맞는 줄만 살린다.
            by_i = {p.i: p for p in labels}
            saved, wrong = [], 0
            for i, row in enumerate(chunk):
                p = by_i.get(i)
                if not p:
                    continue
                if p.term and _norm(p.term) != _norm(row["term"]):
                    wrong += 1          # 줄이 어긋났다 — 이 줄은 버린다
                    continue
                saved.append({**row, "category": p.category, "kind": p.kind, "is_term_candidate": p.is_term_candidate, "lang": p.lang})
            if wrong:
                r.note += f"batch{b // batch}: 줄 어긋남 {wrong}건 제외 "
            if not saved:
                r.note += f"batch{b // batch}: 매핑 0건 "
                continue
            done += ds.save_classifications(con, saved, model)
        r.count = done
        r.detail["pending"] = max(0, len(rows) - done)
    return {"classify": r}
