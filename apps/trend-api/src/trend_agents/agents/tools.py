"""ADK 에이전트가 부르는 도구. 전부 결정론적 파이프라인 단계·조회를 감싼다 — 판정은 여기(규칙)가 하고, 에이전트는 순서·보고만 맡는다."""
from __future__ import annotations

from ..pipeline import board, candidates, classify, collect, interpret, naver, research, spikes, track, translate, views
from ..storage import dictionary_store as ds
from ..storage import sqlite_store as db

_con = db.connect()


def _report(results: dict) -> dict:
    return {k: {"count": r.count, "status": r.status, "note": r.note, **{dk: dv for dk, dv in r.detail.items() if dk != "trace"}} for k, r in results.items()}


def run_collect() -> dict:
    """Collect fresh data from every source (YouTube, news RSS, Google Trends RSS + BigQuery, Wikipedia, mention tracking). Returns per-source counts."""
    return _report(collect.run(_con))


def run_classify() -> dict:
    """Label new trending search queries with a category and whether they are worth a dictionary entry (index-mapped batches)."""
    return _report(classify.run(_con))


def run_spikes() -> dict:
    """Detect sudden surges and investigate why (news, Wikipedia, YouTube, communities) → anchored why-now explanations and graph edges."""
    return _report(spikes.run(_con))


def run_interpret() -> dict:
    """Have Gemini watch pending top shorts (8 per request) and extract memes, slang, songs with confidence."""
    return _report(interpret.run(_con))


def run_candidates() -> dict:
    """Extract dictionary candidates from classified queries and interpreted shorts; dedupe against existing terms."""
    return _report(candidates.run(_con))


def run_research() -> dict:
    """Promote candidates, research meanings, collect anchored evidence and run the verification gate (verified_auto or review queue)."""
    return _report(research.run(_con))


def run_track() -> dict:
    """Recompute weekly mention counts and lifecycle stage for every term (deterministic rules)."""
    return _report(track.run(_con))


def run_naver() -> dict:
    """Korean generation signal: Naver DataLab per-age search peaks for Korean terms; shopping insight category trends."""
    return _report(naver.run(_con))


def run_translate() -> dict:
    """Create ko/en meaning texts for verified terms (term itself is never translated)."""
    return _report(translate.run(_con))


def run_board() -> dict:
    """Rebuild the country × category board and cross-country topics from classified queries, explanations and dictionary links."""
    return _report(board.run(_con))


def pipeline_health() -> dict:
    """Stage counts in the last 24 hours with status (ok / zero / warn)."""
    return {s.key: {"label": s.label, "count_24h": s.count_24h, "status": s.status, "note": s.note} for s in views.pipeline_stages(_con)}


def review_queue_summary() -> dict:
    """What humans still need to decide: queued proposals with gate reasons, plus auto/manual verification counts."""
    items = views.review_items(_con)
    stats = views.review_stats(_con)
    return {"stats": stats.model_dump(), "queued": [{"term": i.canonical, "reasons": i.reasons, "evidence": i.evidence_count} for i in items[:20]]}


def dictionary_lookup(term: str) -> dict:
    """Look up a term in the verified dictionary (canonical or alias). Returns current meaning and status, or not_found."""
    t = ds.find_term(_con, term)
    if not t:
        return {"found": False, "term": term}
    m = ds.current_meaning(_con, t.term_id)
    return {"found": True, "term": t.canonical, "status": t.status, "lifecycle": t.lifecycle,
            "meaning": m.model_dump(mode="json") if m else None, "evidence_count": len(ds.list_evidences(_con, t.term_id))}
