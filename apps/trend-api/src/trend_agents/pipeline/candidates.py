"""2b단계 후보 추출. 분류에서 '뜻을 찾아볼 가치'가 있다고 본 검색어 + Gemini 가 쇼츠에서 읽어낸 밈 이름 → 후보. 이미 사전에 있으면 후보가 아니다."""
from __future__ import annotations


from ..schemas import ShortsInterpretation
from ..storage import dictionary_store as ds
from .runs import stage
from ..storage.db import Connection

MEME_KINDS = {"slang", "meme", "song", "dance"}
TREND_DICT_KINDS = {"slang_meme", "song", "challenge"}  # 분류가 이렇게 본 검색어만 사전 후보. 인물·상품·사건·일반 단어는 지도에만 남는다
MIN_MEME_CONFIDENCE = 0.6


def run(con: Connection) -> dict:
    with stage(con, "candidates") as r:
        expired = ds.expire_candidates(con)   # 한 번만 보고 7일 묵은 spot 후보 — 대기열이 끝없이 자라지 않게
        n = 0
        for term, region, lang, kind in con.execute("SELECT term, region, lang, kind FROM trend_class WHERE is_term_candidate=1").fetchall():
            if kind not in TREND_DICT_KINDS or ds.find_term(con, term):
                continue
            ds.upsert_candidate(con, term, lang or "en", region, "trend", note=f"kind={kind}")
            n += 1
        rows = con.execute(
            "SELECT i.json, v.region FROM interpretations i LEFT JOIN videos v ON v.video_id = i.video_id"
        ).fetchall()
        for j, region in rows:
            it = ShortsInterpretation.model_validate_json(j)
            for m in it.memes:
                name = m.name.split("(")[0].strip()  # "Papa Aa Gaye (Dad is here)" → 원어만
                if m.kind in MEME_KINDS and m.confidence >= MIN_MEME_CONFIDENCE and 1 < len(name) <= 30 and len(name.split()) <= 4:
                    if ds.find_term(con, name):
                        continue
                    ds.upsert_candidate(con, name, it.language or "en", region, "shorts", note=f"kind={m.kind}; {m.origin_hypothesis[:160]}")
                    n += 1
        r.count = n
        r.detail["new_candidates"] = len(ds.candidates(con, "new", 1000))
        r.detail["expired"] = expired
    return {"candidates": r}
