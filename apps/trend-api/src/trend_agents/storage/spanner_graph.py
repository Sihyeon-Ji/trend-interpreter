"""Spanner Graph 위의 사전 지식 그래프.

로컬: Spanner 에뮬레이터 (SPANNER_EMULATOR_HOST=localhost:9010, 인메모리 — 재시작 시 초기화).
배포: Spanner 90일 무료 체험 인스턴스 (Graph·벡터 검색 포함). ADK 연결은 MCP Toolbox `spanner` 소스.
"""
from __future__ import annotations

import os
from pathlib import Path

from google.cloud import spanner
from google.cloud.spanner_v1 import param_types
from google.cloud.spanner_v1.database import Database

from ..schemas import Evidence, Meaning, Segment, Term

def _load_ddl() -> list[str]:
    text = Path(__file__).with_name("spanner_graph.ddl.sql").read_text()
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("--"))  # 주석 줄 제거 후 분리
    return [s.strip() for s in body.split(";") if s.strip()]


DDL = _load_ddl()


def connect(project: str, instance_id: str = "trend-dev", database_id: str = "dictionary") -> Database:
    """에뮬레이터면 인스턴스·DB 를 만들고, 클라우드면 있는 것에 붙는다."""
    client = spanner.Client(project=project)
    emulator = bool(os.getenv("SPANNER_EMULATOR_HOST"))
    inst = client.instance(
        instance_id,
        configuration_name=f"projects/{project}/instanceConfigs/emulator-config" if emulator else None,
        display_name="trend dictionary",
        node_count=1,
    )
    if emulator and not inst.exists():
        inst.create().result(120)
    db = inst.database(database_id, ddl_statements=DDL)
    if not db.exists():
        db.create().result(300)
    return db


def upsert_term(db: Database, t: Term) -> None:
    with db.batch() as b:
        b.insert_or_update(
            "Term",
            ("term_id", "canonical", "lang", "status", "lifecycle", "first_seen", "last_seen"),
            [(t.term_id, t.canonical, t.lang, t.status, t.lifecycle, t.first_seen, t.last_seen)],
        )


def add_meaning(db: Database, m: Meaning, evidences: list[Evidence]) -> None:
    """새 버전을 넣고, 같은 term 의 열린 이전 버전은 valid_to 를 닫는다."""
    def txn(tx):
        tx.execute_update(
            "UPDATE Meaning SET valid_to = @now WHERE term_id = @tid AND valid_to IS NULL AND version < @v",
            params={"now": m.valid_from, "tid": m.term_id, "v": m.version},
            param_types={"now": param_types.TIMESTAMP, "tid": param_types.STRING, "v": param_types.INT64},
        )
        tx.insert_or_update(
            "Meaning",
            ("meaning_id", "term_id", "version", "definition", "expansion", "origin", "nuance", "confidence",
             "verification", "valid_from", "valid_to", "created_by", "citations"),
            [(m.meaning_id, m.term_id, m.version, m.definition, m.expansion, m.origin, m.nuance, m.confidence,
              m.verification, m.valid_from, m.valid_to, m.created_by, m.citations)],
        )
        tx.insert_or_update("TermHasMeaning", ("term_id", "meaning_id"), [(m.term_id, m.meaning_id)])
        for e in evidences:
            tx.insert_or_update(
                "Evidence", ("evidence_id", "kind", "url", "title", "source_domain", "observed_at", "excerpt"),
                [(e.evidence_id, e.kind, e.url, e.title, e.source_domain, e.observed_at, e.excerpt)],
            )
            tx.insert_or_update("MeaningSupportedBy", ("meaning_id", "evidence_id", "weight"), [(m.meaning_id, e.evidence_id, 1.0)])
    db.run_in_transaction(txn)


def link_variant(db: Database, variant_id: str, canonical_id: str) -> None:
    with db.batch() as b:
        b.insert_or_update("TermVariantOf", ("term_id", "canonical_term_id"), [(variant_id, canonical_id)])


def mark_used_by(db: Database, term_id: str, seg: Segment, first_seen, share: float) -> None:
    with db.batch() as b:
        b.insert_or_update("Segment", ("segment_id", "generation", "region"), [(seg.segment_id, seg.generation, seg.region)])
        b.insert_or_update("TermUsedBy", ("term_id", "segment_id", "first_seen", "share"), [(term_id, seg.segment_id, first_seen, share)])


def lookup_verified(db: Database, canonical: str) -> list[dict]:
    """GQL: 검증된 현행 뜻 + 근거. 답변 에이전트는 이 결과 밖의 내용을 말하지 않는다."""
    q = """
    GRAPH TrendGraph
    MATCH (t:Term {canonical: @c})-[:HAS_MEANING]->(m:Meaning)-[:SUPPORTED_BY]->(e:Evidence)
    WHERE m.valid_to IS NULL AND m.verification IN ('verified_auto', 'verified_human')
    RETURN t.canonical AS term, m.version AS version, m.expansion AS expansion, m.definition AS definition,
           m.confidence AS confidence, m.verification AS verification, e.kind AS ev_kind, e.url AS ev_url
    """
    with db.snapshot() as snap:
        rows = snap.execute_sql(q, params={"c": canonical}, param_types={"c": param_types.STRING})
        return [dict(zip(("term", "version", "expansion", "definition", "confidence", "verification", "ev_kind", "ev_url"), r)) for r in rows]


def spread_path(db: Database, canonical: str) -> list[dict]:
    """GQL: 어느 세대·국가에서 먼저 쓰였나 (first_seen 순) = 세대 간 확산 지연."""
    # 에뮬레이터가 GQL 안의 ORDER BY 를 무시함(2026-09 실측) → SQL GRAPH_TABLE 로 감싸고 바깥에서 정렬
    q = """
    SELECT segment, first_seen, share FROM GRAPH_TABLE(TrendGraph
      MATCH (t:Term {canonical: @c})-[u:USED_BY]->(s:Segment)
      COLUMNS (s.segment_id AS segment, u.first_seen AS first_seen, u.share AS share)
    ) ORDER BY first_seen
    """
    with db.snapshot() as snap:
        rows = snap.execute_sql(q, params={"c": canonical}, param_types={"c": param_types.STRING})
        return [dict(zip(("segment", "first_seen", "share"), r)) for r in rows]


def resolve_variant(db: Database, text: str) -> str | None:
    """변형(자만추하다) → 대표형(자만추). VARIANT_OF 한 홉."""
    q = """
    GRAPH TrendGraph
    MATCH (v:Term {canonical: @c})-[:VARIANT_OF]->(t:Term)
    RETURN t.canonical AS canonical
    """
    with db.snapshot() as snap:
        rows = list(snap.execute_sql(q, params={"c": text}, param_types={"c": param_types.STRING}))
        return rows[0][0] if rows else None
