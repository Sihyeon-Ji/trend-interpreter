"""사전·파이프라인 상태의 PostgreSQL 저장 (시스템 오브 레코드). Spanner Graph 는 이 내용을 미러링한다.

원칙: Pydantic JSON 통째 + 조회용 컬럼. 삭제는 없다 — 뜻이 바뀌면 새 version, 이전 version 은 valid_to 를 닫는다.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timedelta, timezone

from ..config import CANTONESE_LANGS, STALE_AFTER_HOURS as _STALE_AFTER_HOURS
from ..schemas import Candidate, Evidence, Meaning, MeaningDraft, MeaningText, MemeFit, Term, TrendQuery, WikiTop
from . import db
from .db import Connection

# 목록 화면(사전 전체·검수 큐)을 만드는 동안만 표제어별 행을 표마다 한 번에 읽어 둔다. 표제어마다 조회하면 Cloud SQL 에서는
# 조회마다 네트워크 왕복이 붙어 1만여 개 표제어가 90초를 넘겼다(staging 10-03). 아래 읽기 함수들만 이 값을 보고, batched 블록 밖에서는 None 이다.
_BATCH: ContextVar[dict | None] = ContextVar("dictionary_batch", default=None)


_BATCH_SQL = {
    "terms": "SELECT term_id, json FROM terms WHERE term_id = ANY(?)",
    "meanings": "SELECT term_id, json, valid_to FROM meanings WHERE term_id = ANY(?) ORDER BY term_id, version",
    "evidences": "SELECT term_id, json FROM evidences WHERE term_id = ANY(?) ORDER BY term_id, observed_at DESC",
    "usage": "SELECT term_id, segment_id, generation, region, first_seen, share, COALESCE(source, 'model') FROM usage "
             "WHERE term_id = ANY(?) ORDER BY term_id, share DESC",
    "weekly": "SELECT term_id, week_start, count FROM mentions_weekly WHERE term_id = ANY(?) ORDER BY term_id, week_start DESC",
    "translations": "SELECT term_id, lang, json FROM translations WHERE term_id = ANY(?)",
    "readings": "SELECT term_id, lang, headword, reading FROM term_readings WHERE term_id = ANY(?)",
    "names": "SELECT term_id, lang, headword, name FROM term_names WHERE term_id = ANY(?)",
    "media": "SELECT term_id, kind, url, page_url, title, license, attribution FROM term_media "
             "WHERE term_id = ANY(?) ORDER BY term_id, kind DESC, added_at",
    "gate": "SELECT term_id, reasons_json FROM review_queue WHERE term_id = ANY(?) AND decision IS NULL AND COALESCE(kind, 'new')='new'",
    "outlets": "SELECT term_id, home, source, published_at FROM mention_samples WHERE term_id = ANY(?) AND home IS NOT NULL",
    "catalog": "SELECT term_id, categories_json FROM wiki_catalog WHERE term_id = ANY(?)",
}


@contextmanager
def batched(con: Connection, term_ids: list[str], tables: tuple[str, ...] = tuple(_BATCH_SQL)):
    """tables 에 든 표만 미리 읽는다. 고르지 않은 표의 읽기는 블록 안에서도 그대로 조회한다."""
    ids = list(dict.fromkeys(term_ids))
    batch: dict[str, dict[str, list[tuple]]] = {}
    for table in tables:
        grouped: dict[str, list[tuple]] = {}
        for row in con.execute(_BATCH_SQL[table], (ids,)).fetchall():
            grouped.setdefault(row[0], []).append(tuple(row[1:]))
        batch[table] = grouped
    token = _BATCH.set(batch)
    try:
        yield
    finally:
        _BATCH.reset(token)


def _cached(table: str, term_id: str) -> list[tuple] | None:
    """batched 블록이 그 표를 읽어 두었으면 그 표제어의 행, 아니면 None(직접 조회)."""
    batch = _BATCH.get()
    if batch is None or table not in batch:
        return None
    return batch[table].get(term_id, [])

DDL = """
CREATE TABLE IF NOT EXISTS trend_queries (
  term TEXT, region TEXT, rank BIGINT, source TEXT, date TEXT, score BIGINT, percent_gain BIGINT, approx_traffic TEXT,
  news_title TEXT, news_url TEXT, first_seen TEXT, json TEXT, PRIMARY KEY(term, region, source, date));
CREATE TABLE IF NOT EXISTS wiki_top (lang TEXT, date TEXT, rank BIGINT, article TEXT, views BIGINT, PRIMARY KEY(lang, date, article));
CREATE TABLE IF NOT EXISTS trend_class (
  key TEXT PRIMARY KEY, term TEXT, region TEXT, category TEXT, kind TEXT, is_term_candidate BIGINT, lang TEXT, classified_at TEXT, model TEXT);
CREATE TABLE IF NOT EXISTS candidates (
  candidate_id TEXT PRIMARY KEY, norm TEXT, text TEXT, lang TEXT, count BIGINT, status TEXT, first_seen TEXT, last_seen TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS terms (
  term_id TEXT PRIMARY KEY, norm TEXT, canonical TEXT, lang TEXT, category TEXT, status TEXT, lifecycle TEXT,
  first_seen TEXT, last_seen TEXT, json TEXT, diffusion TEXT);
CREATE TABLE IF NOT EXISTS meanings (
  meaning_id TEXT PRIMARY KEY, term_id TEXT, version BIGINT, verification TEXT, valid_from TEXT, valid_to TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS evidences (
  evidence_id TEXT, term_id TEXT, kind TEXT, source_domain TEXT, url TEXT, observed_at TEXT, json TEXT, PRIMARY KEY(evidence_id, term_id));
-- source: datalab(네이버 데이터랩 실측) · model(조사 모델의 추정, Plan 15, 마이그레이션 010). 세대 비중을 이용자에게 보이는 것은 실측만이다.
CREATE TABLE IF NOT EXISTS usage (term_id TEXT, segment_id TEXT, generation TEXT, region TEXT, first_seen TEXT, share DOUBLE PRECISION, source TEXT, PRIMARY KEY(term_id, segment_id));
CREATE TABLE IF NOT EXISTS term_timeline (
  term_id TEXT, region TEXT, first_date TEXT, source_ko TEXT, source_en TEXT, url TEXT, updated_at TEXT, PRIMARY KEY(term_id, region));
CREATE TABLE IF NOT EXISTS mentions_weekly (term_id TEXT, week_start TEXT, count BIGINT, PRIMARY KEY(term_id, week_start));
-- 용어마다 뉴스 검색으로 언급을 마지막으로 잰 때(마이그레이션 006). collect.mentions 가 오래된 것부터 돌아가며 잰다.
-- region 은 돌아가며 재는 판의 지난번 차례(마이그레이션 013) — 영어는 다음에 다른 SG·MY·PH 영어판을 잰다.
CREATE TABLE IF NOT EXISTS mention_queries (term_id TEXT PRIMARY KEY, last_at TEXT, region TEXT);
-- 용어마다 뉴스 키워드 검색이 찾은 기사(마이그레이션 013, Plan 04) — 판(region)마다 표제어가 든 기사, 매체(source)와 그 매체의 나라
-- (home: 그 매체의 머리기사가 거의 다 나온 판, collect.source_homes). 근거가 아닌 기사는 news 에 넣지 않고 여기에만 둔다.
CREATE TABLE IF NOT EXISTS mention_samples (term_id TEXT, region TEXT, link TEXT, source TEXT, home TEXT, published_at TEXT, PRIMARY KEY(term_id, region, link));
-- 나라별 원본 언급(Plan 04, 마이그레이션 005). 대시보드가 고른 지역의 수치만 보이게 한다.
CREATE TABLE IF NOT EXISTS mentions_weekly_region (term_id TEXT, region TEXT, week_start TEXT, count BIGINT, PRIMARY KEY(term_id, region, week_start));
CREATE TABLE IF NOT EXISTS translations (term_id TEXT, lang TEXT, json TEXT, updated_at TEXT, model TEXT, PRIMARY KEY(term_id, lang));
-- 표제어 읽기(마이그레이션 026, 10-13): 원문 아래 작게 붙일 읽는 법. lang 은 읽는 사람의 화면 언어(ja 가타카나 · en 로마자 · ko 한글).
-- 수집 서버가 만들고 규칙으로 걸러(수집 서버 pipeline/readings.check) 스냅숏으로 들어온다. headword 는 만들 때의 표제어 — 표제어가 바뀌면 옛 읽기를 내지 않는다
CREATE TABLE IF NOT EXISTS term_readings (term_id TEXT, lang TEXT, headword TEXT, reading TEXT, source TEXT, updated_at TEXT, PRIMARY KEY(term_id, lang));
-- 나라별 이름(마이그레이션 028, 10-13): 외국에서 온 말의 원어 이름 — 그 화면 언어에서는 표제어 대신 이 이름을 보인다(규동 → 일본어 화면 牛丼)
CREATE TABLE IF NOT EXISTS term_names (term_id TEXT, lang TEXT, headword TEXT, name TEXT, source TEXT, url TEXT, updated_at TEXT, PRIMARY KEY(term_id, lang));
-- 검수 큐. 표제어마다 한 줄. kind(Plan 12, 마이그레이션 007): new(조사 결과 — 지금 판이 제안된 뜻) · correction(draft_json 이 고칠 안, 지금 뜻은 그대로 실림)
-- · conflict(docs_json 이 서로 다른 문서의 설명들) · retire(사전에서 뺄지). docs_json 은 제안의 근거가 된 참고 문서 [{wiki, url, summary, proposal}].
CREATE TABLE IF NOT EXISTS review_queue (
  term_id TEXT PRIMARY KEY, draft_json TEXT, reasons_json TEXT, evidence_count BIGINT, queued_at TEXT, decision TEXT, decided_at TEXT, decided_by TEXT,
  kind TEXT, docs_json TEXT);
CREATE TABLE IF NOT EXISTS research_log (term_id TEXT, researched_at TEXT, model TEXT, notes TEXT, urls_json TEXT, verification TEXT, reasons_json TEXT);
-- 문서 대조 기록(Plan 12, 마이그레이션 007). 판정·문서 주소·모델만 두고 문서 본문은 두지 않는다.
CREATE TABLE IF NOT EXISTS crosscheck_log (term_id TEXT, checked_at TEXT, verdict TEXT, doc_urls_json TEXT, model TEXT);
-- 검수 결정 기록(마이그레이션 008). 사람이 결정한 줄은 검수 큐가 덮기 전에 남는다 — 같은 제안을 다시 올리지 않는 데에도 쓴다.
CREATE TABLE IF NOT EXISTS review_history (
  term_id TEXT, kind TEXT, draft_json TEXT, reasons_json TEXT, docs_json TEXT, queued_at TEXT, decision TEXT, decided_at TEXT, decided_by TEXT,
  PRIMARY KEY(term_id, queued_at, decided_at));
-- 그림·영상을 찾아 본 때(research.backfill_media, 마이그레이션 009). 못 붙인 것을 오래된 것부터 다시 본다.
CREATE TABLE IF NOT EXISTS media_tried (term_id TEXT PRIMARY KEY, tried_at TEXT);
-- 위키 밈 분류(Plan 16, 마이그레이션 014): 표제어가 걸린 분류 이름들(종류·연대·나라). 제목·분류만, 본문 없음.
CREATE TABLE IF NOT EXISTS wiki_catalog (term_id TEXT, source TEXT, title TEXT, categories_json TEXT, fetched_at TEXT, PRIMARY KEY(term_id, source, title));
-- 사전 감사(pipeline/audit.py): 뜻 판마다 한 번. action = ok · rewritten · flagged · no_doc · error.
CREATE TABLE IF NOT EXISTS audit_log (term_id TEXT, meaning_id TEXT, checked_at TEXT, verdict TEXT, reasons_json TEXT, model TEXT, action TEXT, PRIMARY KEY(term_id, meaning_id));
-- 일괄 등재의 실패(오류·문서에 닿지 못함). scripts/catalog_import.py --retry-failed 가 다시 돈다.
CREATE TABLE IF NOT EXISTS catalog_failed (source TEXT, title TEXT, reason TEXT, at TEXT, PRIMARY KEY(source, title));
-- models: 그 실행이 부른 모델 ID(쉼표, 마이그레이션 011). 부르지 않았으면 NULL.
CREATE TABLE IF NOT EXISTS pipeline_runs (run_id TEXT, stage TEXT, started_at TEXT, finished_at TEXT, count BIGINT, status TEXT, note TEXT, models TEXT, model_calls TEXT);
CREATE TABLE IF NOT EXISTS gemini_calls (day TEXT PRIMARY KEY, count BIGINT);
CREATE TABLE IF NOT EXISTS board_cache (key TEXT PRIMARY KEY, json TEXT, generated_at TEXT);
CREATE TABLE IF NOT EXISTS trend_explanations (
  key TEXT PRIMARY KEY, term TEXT, region TEXT, date TEXT, trigger TEXT, confidence DOUBLE PRECISION, json TEXT, created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS edges (
  src_type TEXT, src_id TEXT, rel TEXT, dst_type TEXT, dst_id TEXT, evidence_id TEXT, created_at TEXT, PRIMARY KEY(src_type, src_id, rel, dst_type, dst_id));
CREATE TABLE IF NOT EXISTS shopping_trends (category TEXT, age TEXT, week TEXT, ratio DOUBLE PRECISION, PRIMARY KEY(category, age, week));
CREATE TABLE IF NOT EXISTS gen_curves (term_id TEXT, generation TEXT, date TEXT, ratio DOUBLE PRECISION, PRIMARY KEY(term_id, generation, date));
CREATE TABLE IF NOT EXISTS topic_notes (term_id TEXT, region TEXT, json TEXT, updated_at TEXT, model TEXT, PRIMARY KEY(term_id, region));
CREATE TABLE IF NOT EXISTS explain_cache (key TEXT PRIMARY KEY, lang TEXT, text TEXT, term_ids_json TEXT, plain TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS evidence_labels (evidence_id TEXT, term_id TEXT, polarity TEXT, risk TEXT, model TEXT, labeled_at TEXT,
  PRIMARY KEY(evidence_id, term_id));
CREATE TABLE IF NOT EXISTS reader_prefs (reader TEXT PRIMARY KEY, json TEXT, updated_at TEXT);
-- 표제어의 광고 쓰임 낱말(Plan 07, fit 단계, 마이그레이션 004). meaning_id 가 현재 뜻과 다르면 다시 붙인다.
CREATE TABLE IF NOT EXISTS term_fit (term_id TEXT PRIMARY KEY, meaning_id TEXT, json TEXT, model TEXT, labeled_at TEXT);
CREATE TABLE IF NOT EXISTS lookups (key TEXT PRIMARY KEY, text TEXT, lang TEXT, count BIGINT, first_at TEXT, last_at TEXT);
-- 표제어의 위키백과 월별 조회수(과거 관심 추이). 제목이 표제어인 문서만.
CREATE TABLE IF NOT EXISTS term_pageviews (term_id TEXT, lang TEXT, title TEXT, month TEXT, views BIGINT, PRIMARY KEY(term_id, lang, month));
CREATE TABLE IF NOT EXISTS pageviews_done (term_id TEXT PRIMARY KEY, at TEXT);
-- 검색 관심도(주별, 네이버 데이터랩 등). 값은 같이 부른 말끼리의 상대값 — 모양(그 말의 최고점 대비)만 생애주기와 별도로 쓴다.
CREATE TABLE IF NOT EXISTS search_interest (term_id TEXT, source TEXT, period TEXT, value REAL, fetched_at TEXT, PRIMARY KEY(term_id, source, period));
-- 콘텐츠(작품) 하나에서 나라마다 파생된 밈 — 조사 에이전트(pipeline/content_agent.py)가 위키를 읽고 찾은 것과 규칙 확인 결과.
-- 본문은 두지 않는다: 근거 주소와 그 문서 속 문장 하나(sentence)만. verified 는 규칙(근거 문서에 밈 이름 + 콘텐츠를 말함)이 정한다.
CREATE TABLE IF NOT EXISTS content_index (content_key TEXT PRIMARY KEY, name TEXT, labels_json TEXT, last_run TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS content_findings (run_id TEXT, content_key TEXT, name TEXT, region TEXT, description TEXT, quote TEXT,
  evidence_url TEXT, sentence TEXT, same_as TEXT, verified INTEGER, reason TEXT, term_id TEXT, created_at TEXT, PRIMARY KEY(run_id, name, region));
-- 나라가 다른 같은 밈 짝. 모델이 제안하고, 근거 문서끼리 서로의 이름·대사를 말할 때만 verified.
CREATE TABLE IF NOT EXISTS content_pairs (run_id TEXT, content_key TEXT, a TEXT, a_region TEXT, b TEXT, b_region TEXT, reason TEXT,
  verified INTEGER, why TEXT, PRIMARY KEY(run_id, a, b));
-- 에이전트가 걸은 길(생각·도구·인자·결과 앞부분) — 관리자 화면과 평가에 쓴다.
CREATE TABLE IF NOT EXISTS agent_trace (run_id TEXT, step INTEGER, thought TEXT, tool TEXT, args_json TEXT, result TEXT, at TEXT, PRIMARY KEY(run_id, step));
-- 표제어의 대표 그림·영상. 파일을 받아 오지 않고 주소만 둔다(저작권). license 가 빈 것은 화면에 내지 않는다.
CREATE TABLE IF NOT EXISTS term_media (
  term_id TEXT, kind TEXT, url TEXT, page_url TEXT, title TEXT, license TEXT, attribution TEXT, added_at TEXT,
  PRIMARY KEY(term_id, url));
"""
db.register_schema(DDL)



def now() -> datetime:
    return datetime.now(timezone.utc)


def now_s() -> str:
    return now().isoformat()


def norm(s: str) -> str:
    return "".join(s.split()).lower()


def ensure(con: Connection) -> None:
    con.executescript(DDL)


def new_id(prefix: str, seed: str | None = None) -> str:
    if seed:
        return f"{prefix}_{hashlib.sha1(seed.encode()).hexdigest()[:10]}"
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# ---------- 수집 ----------

def upsert_trend_queries(con: Connection, items: list[TrendQuery]) -> int:
    n = 0
    for q in items:
        cur = con.execute(
            """INSERT OR IGNORE INTO trend_queries VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (q.term, q.region, q.rank, q.source, q.date.isoformat(), q.score, q.percent_gain, q.approx_traffic,
             q.news_title, q.news_url, now_s(), q.model_dump_json()),
        )
        n += cur.rowcount
    con.commit()
    return n


def upsert_wiki_top(con: Connection, items: list[WikiTop]) -> int:
    n = 0
    for w in items:
        n += con.execute("INSERT OR IGNORE INTO wiki_top VALUES (?,?,?,?,?)", (w.lang, w.date.isoformat(), w.rank, w.article, w.views)).rowcount
    con.commit()
    return n


def unclassified_queries(con: Connection, regions: list[str] | None = None, limit: int = 200) -> list[dict]:
    """가장 최근 날짜 기준, 아직 분류되지 않은 (term, region) 조합."""
    q = """SELECT t.term, t.region, MAX(t.news_title) AS news_title, MAX(t.date) AS date
           FROM trend_queries t LEFT JOIN trend_class c ON c.key = lower(replace(t.term,' ','')) || '|' || t.region
           WHERE c.key IS NULL"""
    params: list = []
    if regions:
        q += f" AND t.region IN ({','.join('?' * len(regions))})"
        params += regions
    q += " GROUP BY t.term, t.region ORDER BY date DESC, MIN(t.rank) ASC LIMIT ?"
    params.append(limit)
    return [dict(zip(("term", "region", "news_title", "date"), r)) for r in con.execute(q, params).fetchall()]


def save_classifications(con: Connection, rows: list[dict], model: str) -> int:
    for r in rows:
        con.execute(
            "INSERT OR REPLACE INTO trend_class VALUES (?,?,?,?,?,?,?,?,?)",
            (f"{norm(r['term'])}|{r['region']}", r["term"], r["region"], r["category"], r["kind"], int(bool(r["is_term_candidate"])), r["lang"], now_s(), model),
        )
    con.commit()
    return len(rows)


# ---------- 후보 ----------

def upsert_candidate(con: Connection, text: str, lang: str, region: str | None, source: str, note: str = "") -> Candidate:
    # 광동어 코드(yue·yu)는 중국어로 모은다 — 같은 말이 zh·yu 두 후보로 갈려 목격 수가 나뉘었다(行得㗎啦, 09-28).
    # 홍콩 말인지는 config.home_region 이 광동어 글자로 가른다.
    lang = "zh" if (lang or "").lower() in CANTONESE_LANGS else lang
    key = norm(text)
    row = con.execute("SELECT json FROM candidates WHERE norm=? AND lang=?", (key, lang)).fetchone()
    t = now()
    if row:
        c = Candidate.model_validate_json(row[0])
        c.count += 1
        c.last_seen = t
        if c.status == "expired":
            c.status = "new"          # 만료된 말이 다시 나왔다 — 다시 기다린다
        if region and region not in c.regions:
            c.regions.append(region)
        if source not in c.sources:
            c.sources.append(source)  # type: ignore[arg-type]
    else:
        c = Candidate(candidate_id=new_id("c", f"{key}|{lang}"), text=text.strip(), lang=lang, regions=[region] if region else [],
                      sources=[source], first_seen=t, last_seen=t, note=note)  # type: ignore[list-item]
    con.execute(
        "INSERT OR REPLACE INTO candidates VALUES (?,?,?,?,?,?,?,?,?)",
        (c.candidate_id, key, c.text, c.lang, c.count, c.status, c.first_seen.isoformat(), c.last_seen.isoformat(), c.model_dump_json()),
    )
    con.commit()
    return c


def candidates(con: Connection, status: str = "new", limit: int = 50) -> list[Candidate]:
    rows = con.execute("SELECT json FROM candidates WHERE status=? ORDER BY count DESC, last_seen DESC LIMIT ?", (status, limit)).fetchall()
    return [Candidate.model_validate_json(r[0]) for r in rows]


def set_candidate_status(con: Connection, candidate_id: str, status: str) -> None:
    row = con.execute("SELECT json FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
    if not row:
        return
    c = Candidate.model_validate_json(row[0])
    c.status = status  # type: ignore[assignment]
    con.execute("UPDATE candidates SET status=?, json=? WHERE candidate_id=?", (status, c.model_dump_json(), candidate_id))
    con.commit()


# ---------- 용어 ----------

# 사람이 정한 값. 파이프라인 단계는 시작할 때 읽은 용어를 몇 분 뒤에 통째로 저장하므로, 그 사이 검수자가 바꾼 값을
# 옛 사본이 덮었다(2026-09-29 검토: track·risk·research·namu 모두).
HUMAN_FIELDS = ("risk_human", "risk_decided_by", "risk_decided_at")
# 리스크 필드는 리스크 단계(set_risk)와 검수자만 쓴다. 다른 단계의 자동 저장은 이 값을 저장된 쪽에서 가져온다 —
# 사람의 수준만 지키면 '실제 수준'(risk_level)이 옛 값으로 돌아가 둘이 어긋났다.
RISK_FIELDS = ("risk_level", "risk_reasons", "risk_checked_at", "risk_rule_level", *HUMAN_FIELDS)


def upsert_term(con: Connection, term: Term, *, human: bool = False) -> Term:
    """용어 저장. human=False(자동화)면 저장된 리스크 필드(사람의 결정 포함)와 '제외'(retired) 상태를 지킨다 —
    제외는 사람만 한다(검수 화면·검토 스크립트). 사람의 결정을 기록하는 쪽만 human=True 로 부른다."""
    if not human:
        row = con.execute("SELECT json, status FROM terms WHERE term_id=?", (term.term_id,)).fetchone()
        if row:
            stored = Term.model_validate_json(row[0])
            term = term.model_copy(update={f: getattr(stored, f) for f in RISK_FIELDS})
            if row[1] == "retired":
                term = term.model_copy(update={"status": "retired"})
    return _write_term(con, term)


def set_risk(con: Connection, term_id: str, rule_level, reasons: list[str], checked_at: datetime) -> Term | None:
    """리스크 단계의 저장 — 규칙의 판정(rule_level)과 이유를 받아 리스크 필드만 바꾸고 나머지(상태·별칭·사람의 결정)는 저장된 그대로 둔다.
    실제 수준은 **지금 저장된** 사람의 결정(risk_human)이 있으면 그것이다 — 판정한 때 읽은 사본으로 정하면, 그 사이 검수자가 내린 결정 옆에
    규칙의 수준이 적혀 화면·추천이 검수자와 다른 수준을 썼다(검토 3차)."""
    t = get_term(con, term_id)
    if not t:
        return None
    level, why = (t.risk_human, ["검수자가 정한 수준", *reasons]) if t.risk_human else (rule_level, reasons)
    return _write_term(con, t.model_copy(update={"risk_level": level, "risk_reasons": why, "risk_rule_level": rule_level,
                                                 "risk_checked_at": checked_at}))


def _write_term(con: Connection, term: Term) -> Term:
    con.execute(
        "INSERT OR REPLACE INTO terms VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (term.term_id, norm(term.canonical), term.canonical, term.lang, term.category, term.status, term.lifecycle,
         term.first_seen.isoformat() if term.first_seen else None, term.last_seen.isoformat() if term.last_seen else None, term.model_dump_json(),
         term.diffusion),
    )
    # 별칭 표는 용어 JSON 과 같은 트랜잭션에서 통째로 다시 만든다 (마이그레이션 001).
    con.execute("DELETE FROM term_aliases WHERE term_id=?", (term.term_id,))
    con.executemany("INSERT OR IGNORE INTO term_aliases VALUES (?,?)", [(norm(a), term.term_id) for a in term.aliases if norm(a)])
    con.commit()
    return term


def rebuild_aliases(con: Connection) -> int:
    """용어 JSON 에서 별칭 표를 통째로 다시 만든다. 용어를 upsert_term 밖에서 넣었을 때(이관 등) 쓴다."""
    con.execute("DELETE FROM term_aliases")
    rows = [(norm(a), t.term_id) for t in list_terms(con) for a in t.aliases if norm(a)]
    con.executemany("INSERT OR IGNORE INTO term_aliases VALUES (?,?)", rows)
    con.commit()
    return len(rows)


def get_term(con: Connection, term_id: str) -> Term | None:
    if (rows := _cached("terms", term_id)) is not None:
        row = next(iter(rows), None)
    else:
        row = con.execute("SELECT json FROM terms WHERE term_id=?", (term_id,)).fetchone()
    return Term.model_validate_json(row[0]) if row else None


def find_term(con: Connection, text: str) -> Term | None:
    """표준형 또는 별칭 일치."""
    key = norm(text)
    row = con.execute("SELECT json FROM terms WHERE norm=?", (key,)).fetchone()
    if not row:
        row = con.execute(
            "SELECT t.json FROM term_aliases a JOIN terms t ON t.term_id=a.term_id WHERE a.norm=? ORDER BY t.term_id LIMIT 1", (key,)
        ).fetchone()
    return Term.model_validate_json(row[0]) if row else None


def list_terms(con: Connection, statuses: tuple[str, ...] | None = None) -> list[Term]:
    if statuses:
        rows = con.execute(f"SELECT json FROM terms WHERE status IN ({','.join('?' * len(statuses))}) ORDER BY canonical", statuses).fetchall()
    else:
        rows = con.execute("SELECT json FROM terms ORDER BY canonical").fetchall()
    return [Term.model_validate_json(r[0]) for r in rows]


# ---------- 뜻 (버전) ----------

def current_meaning(con: Connection, term_id: str) -> Meaning | None:
    if (rows := _cached("meanings", term_id)) is not None:
        row = next((r for r in reversed(rows) if r[1] is None), None)
    else:
        row = con.execute("SELECT json FROM meanings WHERE term_id=? AND valid_to IS NULL ORDER BY version DESC LIMIT 1", (term_id,)).fetchone()
    return Meaning.model_validate_json(row[0]) if row else None


def list_meanings(con: Connection, term_id: str) -> list[Meaning]:
    if (rows := _cached("meanings", term_id)) is None:
        rows = con.execute("SELECT json FROM meanings WHERE term_id=? ORDER BY version", (term_id,)).fetchall()
    return [Meaning.model_validate_json(r[0]) for r in rows]


def add_meaning(con: Connection, term_id: str, draft: MeaningDraft, verification: str, citations: list[str], created_by: str = "research_agent",
                *, force: bool = False) -> Meaning:
    """새 version 을 만들고 이전 현행 version 의 valid_to 를 닫는다. 뜻이 같으면(정의·풀이 동일) 새 version 을 만들지 않고 현행을 돌려준다.
    force=True 면 그 비교 없이 새 version 을 만든다 — 사람이 유래·뉘앙스만 고친 안을 승인할 때(publish_fix)."""
    cur = current_meaning(con, term_id)
    if not force and cur and cur.definition == draft.definition and cur.expansion == draft.expansion and cur.verification == verification:
        return cur
    t = now()
    if cur:
        cur.valid_to = t
        con.execute("UPDATE meanings SET valid_to=?, json=? WHERE meaning_id=?", (t.isoformat(), cur.model_dump_json(), cur.meaning_id))
    version = (cur.version + 1) if cur else 1
    m = Meaning(**draft.model_dump(), meaning_id=new_id("m"), term_id=term_id, version=version, confidence=draft.self_confidence,
                verification=verification, valid_from=t, valid_to=None, created_by=created_by, citations=citations)  # type: ignore[arg-type]
    con.execute("INSERT INTO meanings VALUES (?,?,?,?,?,?,?)", (m.meaning_id, term_id, version, verification, t.isoformat(), None, m.model_dump_json()))
    # 뜻이 바뀌었으니 예전 언어판은 더 이상 이 뜻이 아니다. 지워야 번역 단계가 다시 만든다
    # (안 지우면 화면에 옛 뜻이 그대로 남는다 — 2026-09-16 실측).
    con.execute("DELETE FROM translations WHERE term_id=?", (term_id,))
    con.commit()
    return m


def publish_fix(con: Connection, term_id: str, draft: MeaningDraft, by: str, citations: list[str]) -> Meaning:
    """사람이 승인한 고칠 안을 새 판(verified_human)으로 싣고 이전 판의 valid_to 를 닫는다. 지우지 않는다(Plan 12 §3).
    add_meaning 의 '같은 뜻' 비교는 정의·풀이만 보므로 유래·뉘앙스만 고친 안이 버려졌다 — 뜻 칸이 하나라도 다르면 새 판이다.
    칸이 모두 같으면 새 판 없이 지금 판을 사람이 확인한 것으로 둔다."""
    cur = current_meaning(con, term_id)
    fields = set(MeaningDraft.model_fields)
    if cur and cur.model_dump(include=fields) == draft.model_dump(include=fields):
        if cur.verification != "verified_human":
            set_verification(con, cur.meaning_id, "verified_human", by)
        return current_meaning(con, term_id) or cur
    return add_meaning(con, term_id, draft, "verified_human", citations, created_by=by, force=True)


def set_verification(con: Connection, meaning_id: str, verification: str, by: str) -> None:
    row = con.execute("SELECT json FROM meanings WHERE meaning_id=?", (meaning_id,)).fetchone()
    if not row:
        return
    m = Meaning.model_validate_json(row[0])
    m.verification = verification  # type: ignore[assignment]
    m.created_by = by
    con.execute("UPDATE meanings SET verification=?, json=? WHERE meaning_id=?", (verification, m.model_dump_json(), meaning_id))
    con.commit()


# ---------- 근거·사용·추세 ----------

def set_pageviews(con: Connection, term_id: str, lang: str, title: str, rows: list[tuple[str, int]]) -> int:
    """rows: (YYYYMM, views). 한 번에 commit(월별 수백 행)."""
    con.executemany("INSERT OR REPLACE INTO term_pageviews VALUES (?,?,?,?,?)", [(term_id, lang, title, m, v) for m, v in rows])
    con.commit()
    return len(rows)


def set_interest(con: Connection, term_id: str, source: str, rows: list[tuple[str, float]], fetched_at: str) -> None:
    con.execute("DELETE FROM search_interest WHERE term_id=? AND source=?", (term_id, source))
    con.executemany("INSERT OR REPLACE INTO search_interest VALUES (?,?,?,?,?)", [(term_id, source, p, v, fetched_at) for p, v in rows])
    con.commit()


def get_interest(con: Connection, term_id: str, source: str) -> list[tuple[str, float]]:
    return [(p, v) for p, v in con.execute("SELECT period, value FROM search_interest WHERE term_id=? AND source=? ORDER BY period", (term_id, source))]


def get_pageviews(con: Connection, term_id: str) -> list[tuple[str, int]]:
    return [(m, v) for m, v in con.execute("SELECT month, views FROM term_pageviews WHERE term_id=? ORDER BY month", (term_id,))]


def pageview_peak(con: Connection, term_id: str) -> dict | None:
    """{lang, peak_month, peak_views, last12_views, first_month}. 조회수가 없으면 None."""
    rows = con.execute("SELECT lang, month, views FROM term_pageviews WHERE term_id=? ORDER BY month", (term_id,)).fetchall()
    if not rows:
        return None
    peak = max(rows, key=lambda r: r[2])
    return {"lang": rows[0][0], "peak_month": peak[1], "peak_views": peak[2],
            "last12_views": sum(r[2] for r in rows[-12:]), "first_month": rows[0][1]}

def add_evidences(con: Connection, term_id: str, evs: list[Evidence]) -> int:
    n = 0
    for e in evs:
        n += con.execute(
            "INSERT OR IGNORE INTO evidences VALUES (?,?,?,?,?,?,?)",
            (e.evidence_id, term_id, e.kind, e.source_domain, e.url, e.observed_at.isoformat(), e.model_dump_json()),
        ).rowcount
    con.commit()
    return n


def list_evidences(con: Connection, term_id: str) -> list[Evidence]:
    if (rows := _cached("evidences", term_id)) is None:
        rows = con.execute("SELECT json FROM evidences WHERE term_id=? ORDER BY observed_at DESC", (term_id,)).fetchall()
    return [Evidence.model_validate_json(r[0]) for r in rows]


def set_usage(con: Connection, term_id: str, rows: list[tuple[str, str, str, float]], source: str = "model") -> None:
    """rows: (generation, region, first_seen_iso, share). source: datalab(실측) · model(조사 모델 추정). 실측을 쓰면 그 나라의 추정 줄은 지운다."""
    if source != "model":
        for region in {r[1] for r in rows}:
            con.execute("DELETE FROM usage WHERE term_id=? AND region=? AND COALESCE(source, 'model')='model'", (term_id, region))
    for gen, region, first, share in rows:
        con.execute("INSERT OR REPLACE INTO usage VALUES (?,?,?,?,?,?,?)", (term_id, f"{region}-{gen}", gen, region, first, share, source))
    con.commit()


def clear_usage(con: Connection, term_id: str) -> None:
    con.execute("DELETE FROM usage WHERE term_id=?", (term_id,))
    con.commit()


def get_usage(con: Connection, term_id: str) -> list[dict]:
    if (rows := _cached("usage", term_id)) is None:
        rows = con.execute("SELECT segment_id, generation, region, first_seen, share, COALESCE(source, 'model') FROM usage WHERE term_id=? ORDER BY share DESC",
                           (term_id,)).fetchall()
    return [dict(zip(("segment_id", "generation", "region", "first_seen", "share", "source"), r)) for r in rows]


def set_timeline(con: Connection, term_id: str, rows: list[dict]) -> None:
    """나라별로 '언제 처음 나타났나' — 날짜를 대는 출처가 있을 때만 넣는다.

    usage.first_seen 은 이 자리에 쓸 수 없다. 조사 단계가 용어 하나의 날짜를 모든 나라에 똑같이 적고, 관측을 시작한 날(09-14)
    이전 것은 다 그날로 찍힌다. 그래서 지도의 이동 경로는 이 표에 있는 나라끼리만 긋는다.
    rows: {region, first_date (YYYY-MM-DD), source_ko, source_en, url}
    한 번 계산한 결과를 통째로 바꾼다 — 다시 계산해서 빠진 나라가 예전 기록으로 남아 경로에 그려지면 안 된다.
    """
    con.execute("DELETE FROM term_timeline WHERE term_id=?", (term_id,))
    for r in rows:
        con.execute("INSERT OR REPLACE INTO term_timeline VALUES (?,?,?,?,?,?,?)",
                    (term_id, r["region"], r["first_date"], r.get("source_ko", ""), r.get("source_en", ""), r.get("url", ""), now_s()))
    con.commit()


def get_timeline(con: Connection, term_id: str) -> list[dict]:
    return [dict(zip(("region", "first_date", "source_ko", "source_en", "url"), r))
            for r in con.execute("SELECT region, first_date, source_ko, source_en, url FROM term_timeline WHERE term_id=? ORDER BY first_date",
                                 (term_id,)).fetchall()]


def set_weekly(con: Connection, term_id: str, counts: dict[str, int]) -> None:
    for wk, c in counts.items():
        con.execute("INSERT OR REPLACE INTO mentions_weekly VALUES (?,?,?)", (term_id, wk, c))
    con.commit()


def set_weekly_region(con: Connection, term_id: str, counts: dict[str, dict[str, int]]) -> None:
    """counts: {나라: {주 시작일: 건수}}. 그 용어의 나라별 기록을 통째로 바꾼다(0 인 칸은 두지 않는다)."""
    con.execute("DELETE FROM mentions_weekly_region WHERE term_id=?", (term_id,))
    con.executemany("INSERT INTO mentions_weekly_region VALUES (?,?,?,?)",
                    [(term_id, r, wk, c) for r, weeks in counts.items() for wk, c in weeks.items() if c])
    con.commit()


def get_weekly_region(con: Connection, term_id: str) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for r, wk, c in con.execute("SELECT region, week_start, count FROM mentions_weekly_region WHERE term_id=?", (term_id,)).fetchall():
        out.setdefault(r, {})[wk] = c
    return out


def get_weekly(con: Connection, term_id: str, weeks: int = 12) -> list[tuple[str, int]]:
    if (rows := _cached("weekly", term_id)) is not None:
        rows = rows[:weeks]
    else:
        rows = con.execute("SELECT week_start, count FROM mentions_weekly WHERE term_id=? ORDER BY week_start DESC LIMIT ?", (term_id, weeks)).fetchall()
    return list(reversed(rows))


def set_translation(con: Connection, term_id: str, lang: str, text: MeaningText, model: str) -> None:
    con.execute("INSERT OR REPLACE INTO translations VALUES (?,?,?,?,?)", (term_id, lang, text.model_dump_json(), now_s(), model))
    con.commit()


def get_translation(con: Connection, term_id: str, lang: str) -> MeaningText | None:
    if (rows := _cached("translations", term_id)) is not None:
        row = next(((j,) for code, j in rows if code == lang), None)
    else:
        row = con.execute("SELECT json FROM translations WHERE term_id=? AND lang=?", (term_id, lang)).fetchone()
    return MeaningText.model_validate_json(row[0]) if row else None


def set_reading(con: Connection, term_id: str, lang: str, headword: str, reading: str, source: str) -> None:
    con.execute("INSERT OR REPLACE INTO term_readings VALUES (?,?,?,?,?,?)", (term_id, lang, headword, reading, source, now_s()))
    con.commit()


def set_name(con: Connection, term_id: str, lang: str, headword: str, name: str, source: str, url: str) -> None:
    con.execute("INSERT OR REPLACE INTO term_names VALUES (?,?,?,?,?,?,?)", (term_id, lang, headword, name, source, url, now_s()))
    con.commit()


def get_names(con: Connection, t: Term) -> dict[str, str]:
    """화면 언어 → 원어 이름. 지금 표제어로 만든 것만."""
    if (rows := _cached("names", t.term_id)) is None:
        rows = con.execute("SELECT lang, headword, name FROM term_names WHERE term_id=?", (t.term_id,)).fetchall()
    return {lang: n for lang, head, n in rows if head == t.canonical}


def get_readings(con: Connection, t: Term) -> dict[str, str]:
    """화면 언어 → 읽기. 지금 표제어로 만든 것만."""
    if (rows := _cached("readings", t.term_id)) is None:
        rows = con.execute("SELECT lang, headword, reading FROM term_readings WHERE term_id=?", (t.term_id,)).fetchall()
    return {lang: r for lang, head, r in rows if head == t.canonical}


# ---------- 검수 큐 · 리서치 로그 ----------

# 검수 큐의 제안 종류(Plan 12). new 는 조사 결과(지금 판이 제안된 뜻), 나머지 셋은 문서 대조의 제안이라 지금 뜻이 그대로 공개돼 있다.
REVIEW_KINDS = ("new", "correction", "conflict", "retire")
_REVIEW_COLS = "term_id, draft_json, reasons_json, evidence_count, queued_at, COALESCE(kind, 'new'), docs_json, decision, decided_at, decided_by"


def review_token(kind: str, queued_at: str, draft_json: str | None, docs_json: str | None) -> str:
    """제안 한 건의 표 — 올린 때와 내용이 같을 때만 같다. 결정은 화면이 본 표와 함께 오고, 다르면 409(오래된 화면이 다른 제안을 싣지 않게)."""
    return hashlib.sha1(f"{kind}|{queued_at}|{draft_json or ''}|{docs_json or ''}".encode()).hexdigest()[:16]


def proposal_fingerprint(kind: str, draft, docs: list[dict] | None) -> str:
    """제안의 내용 — 사람이 같은 내용을 이미 결정했는지 볼 때 쓴다. 올린 때·사유·요약은 빼고, 종류마다 검수자가 판단한 것만 본다:
    new·correction 은 고칠 안(뜻), conflict 는 문서마다의 주소와 고칠 안, retire 는 문서 주소(새 문서가 생기면 다시 볼 만하다)."""
    from ..verification import normalize_url

    def meaning(x):
        if x is None:
            return None
        data = x if isinstance(x, dict) else x.model_dump()
        return MeaningDraft.model_validate(data).model_dump()

    body: dict = {"kind": kind}
    if kind in ("new", "correction"):
        body["draft"] = meaning(draft)
    elif kind == "conflict":
        body["docs"] = sorted(({"url": normalize_url(d.get("url", "")), "proposal": meaning(d.get("proposal"))} for d in docs or []),
                              key=lambda d: d["url"])
    else:
        body["docs"] = sorted({normalize_url(d.get("url", "")) for d in docs or []})
    return hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _review_row(r) -> dict:
    return {"term_id": r[0], "draft": MeaningDraft.model_validate_json(r[1]) if r[1] else None, "reasons": json.loads(r[2] or "[]"),
            "evidence_count": r[3], "queued_at": r[4], "kind": r[5], "docs": json.loads(r[6]) if r[6] else [],
            "decision": r[7], "decided_at": r[8], "decided_by": r[9], "token": review_token(r[5], r[4], r[1], r[6])}


def _archive(con: Connection, r) -> None:
    """사람이 결정한 줄을 결정 기록에 남긴다(같은 결정은 한 번만). 게이트가 스스로 닫은 줄은 두지 않는다."""
    if r[7] is None or (r[9] or "") == "gate" or not r[4] or not r[8]:
        return
    con.execute("INSERT OR IGNORE INTO review_history VALUES (?,?,?,?,?,?,?,?,?)", (r[0], r[5], r[1], r[2], r[6], r[4], r[7], r[8], r[9]))


def queue_review(con: Connection, term_id: str, draft: MeaningDraft | None, reasons: list[str], evidence_count: int, *,
                 kind: str = "new", docs: list[dict] | None = None) -> bool:
    """검수 큐에 올린다(표제어마다 한 줄). kind 는 REVIEW_KINDS. correction 은 draft 가 고칠 안, conflict 는 docs 가 고를 수 있는 문서 설명들,
    retire 는 draft 없이 사유·문서만. 아직 결정하지 않은 **다른 종류**의 제안이 있으면 덮지 않고 False — 조사·점검 스크립트의 새 말(new)이
    사람이 보고 있는 고칠 안을 지우던 것(Plan 12 검토). 사람이 결정한 예전 줄은 덮기 전에 결정 기록(review_history)에 남긴다."""
    if kind not in REVIEW_KINDS:
        raise ValueError(f"검수 큐 종류가 아님: {kind}")
    row = con.execute(f"SELECT {_REVIEW_COLS} FROM review_queue WHERE term_id=?", (term_id,)).fetchone()
    if row is not None:
        if row[7] is None and row[5] != kind:
            return False
        _archive(con, row)
    con.execute(
        "INSERT OR REPLACE INTO review_queue (term_id, draft_json, reasons_json, evidence_count, queued_at, decision, decided_at, decided_by, kind, docs_json) "
        "VALUES (?,?,?,?,?,NULL,NULL,NULL,?,?)",
        (term_id, draft.model_dump_json() if draft is not None else None, json.dumps(reasons, ensure_ascii=False), evidence_count, now_s(),
         kind, json.dumps(docs, ensure_ascii=False) if docs else None),
    )
    con.commit()
    return True


def review_queue(con: Connection) -> list[dict]:
    rows = con.execute(f"SELECT {_REVIEW_COLS} FROM review_queue WHERE decision IS NULL ORDER BY queued_at DESC").fetchall()
    return [_review_row(r) for r in rows]


def pending_review(con: Connection, term_id: str) -> dict | None:
    """그 표제어의 아직 결정하지 않은 제안 (없으면 None)."""
    row = con.execute(f"SELECT {_REVIEW_COLS} FROM review_queue WHERE term_id=? AND decision IS NULL", (term_id,)).fetchone()
    return _review_row(row) if row else None


def under_review(con: Connection, term_id: str) -> bool:
    """문서 대조의 제안(고칠 안·위키끼리 다름·사전에서 뺄지)을 사람이 보고 있는가. 그 결정 전에는 조사·점검 스크립트가 지금 뜻을 바꾸지 않는다."""
    q = pending_review(con, term_id)
    return bool(q and q["kind"] != "new")


def pending_counts(con: Connection) -> dict[str, int]:
    """아직 결정하지 않은 제안 수 — 종류마다."""
    return dict(con.execute("SELECT COALESCE(kind, 'new'), COUNT(*) FROM review_queue WHERE decision IS NULL GROUP BY COALESCE(kind, 'new')").fetchall())


def decide_review(con: Connection, term_id: str, decision: str, by: str, *, kind: str | None = None) -> None:
    """kind 를 주면 그 종류의 대기 제안만 닫는다 — 조사가 스스로 닫는 것은 조사 결과(new)뿐이고, 문서 대조의 제안은 사람이 닫는다.
    사람의 결정(by 가 gate 가 아님)은 결정 기록에도 남긴다."""
    if kind:
        con.execute("UPDATE review_queue SET decision=?, decided_at=?, decided_by=? WHERE term_id=? AND decision IS NULL AND COALESCE(kind, 'new')=?",
                    (decision, now_s(), by, term_id, kind))
    else:
        con.execute("UPDATE review_queue SET decision=?, decided_at=?, decided_by=? WHERE term_id=?", (decision, now_s(), by, term_id))
    if by != "gate":
        row = con.execute(f"SELECT {_REVIEW_COLS} FROM review_queue WHERE term_id=?", (term_id,)).fetchone()
        if row is not None:
            _archive(con, row)
    con.commit()


def claim_review(con: Connection, term_id: str, queued_at: str, decision: str, by: str, *, commit: bool = True) -> bool:
    """검수자가 본 그 제안(올린 때가 같은 대기 줄)만 결정으로 닫는다 — 줄이 하나 바뀌어야 True. 두 사람이 같은 제안을 동시에 결정하거나
    그사이 새 제안이 올라왔으면 False(→ 409). commit=False 면 뒤따르는 쓰기(새 판 싣기)와 한 트랜잭션으로 묶인다."""
    n = con.execute("UPDATE review_queue SET decision=?, decided_at=?, decided_by=? WHERE term_id=? AND decision IS NULL AND queued_at=?",
                    (decision, now_s(), by, term_id, queued_at)).rowcount
    if n != 1:
        return False
    row = con.execute(f"SELECT {_REVIEW_COLS} FROM review_queue WHERE term_id=?", (term_id,)).fetchone()
    if row is not None:
        _archive(con, row)
    if commit:
        con.commit()
    return True


def human_decided(con: Connection, term_id: str, kind: str, draft, docs: list[dict] | None) -> bool:
    """사람이 같은 종류·같은 내용의 제안을 이미 결정했는가(승인·거절·지금 뜻 그대로). 다시 가져오기·문서 대조 재검사가 그 제안을 되살리지 않게."""
    want = proposal_fingerprint(kind, draft, docs)
    rows = con.execute("SELECT kind, draft_json, docs_json FROM review_history WHERE term_id=? AND kind=?", (term_id, kind)).fetchall()
    cur = con.execute("SELECT COALESCE(kind, 'new'), draft_json, docs_json, decision, decided_by FROM review_queue WHERE term_id=?", (term_id,)).fetchone()
    if cur is not None and cur[3] is not None and (cur[4] or "") != "gate" and cur[0] == kind:
        rows.append(cur[:3])
    return any(proposal_fingerprint(k, json.loads(d) if d else None, json.loads(c) if c else []) == want for k, d, c in rows)


def review_history(con: Connection, term_id: str) -> list[dict]:
    """그 표제어에 사람이 내린 검수 결정들, 오래된 것부터."""
    rows = con.execute("SELECT kind, queued_at, decision, decided_at, decided_by FROM review_history WHERE term_id=? ORDER BY decided_at", (term_id,)).fetchall()
    return [dict(zip(("kind", "queued_at", "decision", "decided_at", "decided_by"), r)) for r in rows]


def gate_reasons(con: Connection, term_id: str) -> list[str]:
    """게이트가 남긴 사유 — 조사 결과(new) 줄만. 문서 대조의 제안 사유는 게이트의 판단이 아니다."""
    if (rows := _cached("gate", term_id)) is not None:
        row = next(iter(rows), None)
    else:
        row = con.execute("SELECT reasons_json FROM review_queue WHERE term_id=? AND decision IS NULL AND COALESCE(kind, 'new')='new'",
                          (term_id,)).fetchone()
    return json.loads(row[0]) if row else []


def log_research(con: Connection, term_id: str, model: str, notes: str, urls: list[str], verification: str, reasons: list[str]) -> None:
    con.execute("INSERT INTO research_log VALUES (?,?,?,?,?,?,?)",
                (term_id, now_s(), model, notes[:4000], json.dumps(urls), verification, json.dumps(reasons, ensure_ascii=False)))
    con.commit()


def log_crosscheck(con: Connection, term_id: str, verdict: str, doc_urls: list[str], model: str) -> None:
    """문서 대조 한 번의 기록(Plan 12). 문서 본문은 두지 않는다 — 판정·문서 주소·모델만."""
    con.execute("INSERT INTO crosscheck_log VALUES (?,?,?,?,?)", (term_id, now_s(), verdict, json.dumps(doc_urls, ensure_ascii=False), model))
    con.commit()


def no_doc_since(con: Connection, term_id: str) -> datetime | None:
    """지금까지 이어진 '문서 없음' 판정의 첫 시각. 닿지 못함·판정 실패는 건너뛰고, 다른 판정(문서를 찾음)이 나오면 거기서 끊는다."""
    since = None
    for at, verdict in con.execute("SELECT checked_at, verdict FROM crosscheck_log WHERE term_id=? ORDER BY checked_at DESC", (term_id,)).fetchall():
        if verdict in ("unreachable", "error"):
            continue
        if verdict != "no_doc":
            break
        since = datetime.fromisoformat(at)
    return since


def last_crosschecks(con: Connection) -> dict[str, dict]:
    """표제어마다 마지막 대조 {checked_at, verdict, urls, model}."""
    out: dict[str, dict] = {}
    for tid, at, verdict, urls, model in con.execute(
            "SELECT term_id, checked_at, verdict, doc_urls_json, model FROM crosscheck_log ORDER BY checked_at").fetchall():
        out[tid] = {"checked_at": datetime.fromisoformat(at), "verdict": verdict, "urls": json.loads(urls or "[]"), "model": model or ""}
    return out


def last_researched(con: Connection, term_id: str, ok_only: bool = False) -> datetime | None:
    """마지막 조사 시각. ok_only 면 실패('error') 기록을 뺀다."""
    q = "SELECT MAX(researched_at) FROM research_log WHERE term_id=?" + (" AND verification != 'error'" if ok_only else "")
    row = con.execute(q, (term_id,)).fetchone()
    return datetime.fromisoformat(row[0]) if row and row[0] else None


# ---------- 실행 기록 · 예산 · 캐시 ----------

def run_start(con: Connection, stage: str) -> str:
    rid = new_id("r")
    con.execute("INSERT INTO pipeline_runs (run_id, stage, started_at, finished_at, count, status, note) VALUES (?,?,?,?,?,?,?)",
                (rid, stage, now_s(), None, 0, "running", ""))
    con.commit()
    return rid


def run_finish(con: Connection, run_id: str, count: int, status: str, note: str = "", models: list[str] | tuple[str, ...] = (),
               calls: dict[str, list[float]] | None = None) -> None:
    """models: 그 실행이 부른 모델 ID(Plan 06 완료 기준 1). 쉼표로 이어 두고, 부르지 않았으면 NULL.
    calls: 모델 ID → [호출 수, 걸린 초]. JSON 으로 두고, 잰 호출이 없으면 NULL."""
    mc = json.dumps({m: [int(n), round(s, 1)] for m, (n, s) in sorted(calls.items())}) if calls else None
    con.execute("UPDATE pipeline_runs SET finished_at=?, count=?, status=?, note=?, models=?, model_calls=? WHERE run_id=?",
                (now_s(), count, status, note[:500], ",".join(sorted(models)) or None, mc, run_id))
    con.commit()


def stage_counts_24h(con: Connection) -> dict[str, tuple[int, str, str]]:
    """(24시간 건수, 마지막 실행의 상태, 비고).

    상태는 **마지막 실행** 기준이다. 전에는 24시간 안에 오류가 한 번이라도 있으면 계속 '주의' 로 보여서,
    이미 고친 문제가 하루 종일 경고로 남았다(2026-09-16). 창 안에 있었던 실패는 비고에 해결됨으로 적어 둔다.
    """
    since = (now() - timedelta(hours=24)).isoformat()
    out: dict[str, tuple[int, str, str]] = {}
    rows = con.execute(
        "SELECT stage, SUM(count), COUNT(*) FILTER (WHERE status IN ('error','skipped')), COUNT(*) FROM pipeline_runs WHERE started_at>=? GROUP BY stage", (since,)
    ).fetchall()
    for stage, cnt, bad, total in rows:
        last = con.execute(
            "SELECT status, note FROM pipeline_runs WHERE stage=? AND started_at>=? ORDER BY started_at DESC LIMIT 1", (stage, since)
        ).fetchone()
        status, note = (last[0] or "", last[1] or "") if last else ("", "")
        if status not in ("error", "skipped"):
            status = "ok" if (cnt or 0) > 0 else "zero"
            if bad:
                note = (note + " " if note else "") + f"이전 {bad}회 실패, 마지막 실행은 정상"
        out[stage] = (cnt or 0, status, note)
    return out


def model_calls_24h(con: Connection) -> dict[str, dict[str, list[float]]]:
    """단계 → 모델 ID → [호출 수, 걸린 초], 최근 24시간 실행 기록의 합(관리 화면 '모델 기록'). 문장·출력 원문은 없다."""
    since = (now() - timedelta(hours=24)).isoformat()
    out: dict[str, dict[str, list[float]]] = {}
    for stage, raw in con.execute("SELECT stage, model_calls FROM pipeline_runs WHERE started_at>=? AND model_calls IS NOT NULL", (since,)).fetchall():
        try:
            calls = json.loads(raw)
        except (TypeError, ValueError):
            continue
        for model, (n, secs) in calls.items():
            c = out.setdefault(stage, {}).setdefault(model, [0, 0.0])
            c[0] += int(n)
            c[1] += float(secs)
    return out


def stage_last_runs(con: Connection) -> dict[str, tuple[str | None, str | None]]:
    """단계마다 마지막 실행의 (시작, 끝) 시각 — 관리 화면 '수집 현황'. 24시간 창과 상관없이 전체 기록에서."""
    rows = con.execute("SELECT stage, MAX(started_at), MAX(finished_at) FROM pipeline_runs GROUP BY stage").fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def gemini_budget_left(con: Connection, daily_budget: int, ledger: str = "") -> int:
    """ledger: '' 는 파이프라인, 'req:' 는 이용자 요청 — 같은 표에 날짜 앞에 붙여 따로 센다."""
    row = con.execute("SELECT count FROM gemini_calls WHERE day=?", (ledger + date.today().isoformat(),)).fetchone()
    return max(0, daily_budget - (row[0] if row else 0))


def gemini_spend(con: Connection, n: int = 1, ledger: str = "") -> None:
    con.execute("INSERT INTO gemini_calls VALUES (?,?) ON CONFLICT(day) DO UPDATE SET count=gemini_calls.count+excluded.count",
                (ledger + date.today().isoformat(), n))
    con.commit()


def cache_set(con: Connection, key: str, payload: str, generated_at: str | None = None) -> None:
    """generated_at 을 주면 그 시각을 지킨다 — 카드 하나를 고친 것이 '전체를 새로 만든 때' 로 보이지 않게."""
    con.execute("INSERT OR REPLACE INTO board_cache VALUES (?,?,?)", (key, payload, generated_at or now_s()))
    con.commit()


def cache_get(con: Connection, key: str) -> tuple[str, str] | None:
    row = con.execute("SELECT json, generated_at FROM board_cache WHERE key=?", (key,)).fetchone()
    return (row[0], row[1]) if row else None


def cache_stamp(con: Connection, key: str) -> tuple[str, str] | None:
    """(generated_at, 내용 해시) — 캐시 본문(대시보드 8.9MB)을 읽지 않고 바뀌었는지만 본다. 카드 하나를 고친 저장은 시각을 지키므로
    시각만으로는 모른다(cache_set) — 내용 해시를 함께 본다."""
    row = con.execute("SELECT generated_at, md5(json) FROM board_cache WHERE key=?", (key,)).fetchone()
    return (row[0], row[1]) if row else None


def verified_risk(con: Connection) -> dict[str, tuple[str | None, list[str], str | None]]:
    """확인된 용어마다 지금의 (리스크 수준, 이유, 점검 시각) — 용어 JSON 전체를 해석하지 않고 세 칸만 꺼낸다(대시보드 _live)."""
    rows = con.execute("SELECT term_id, json::jsonb->>'risk_level', json::jsonb->'risk_reasons', json::jsonb->>'risk_checked_at' "
                       "FROM terms WHERE status='verified'").fetchall()
    return {tid: (level, list(reasons or []), checked) for tid, level, reasons, checked in rows}


def count_terms(con: Connection, statuses: tuple[str, ...] | None = None) -> int:
    if not statuses:
        return con.execute("SELECT count(*) FROM terms").fetchone()[0]
    return con.execute(f"SELECT count(*) FROM terms WHERE status IN ({','.join('?' * len(statuses))})", statuses).fetchone()[0]


def explain_cache_get(con: Connection, lang: str, text: str) -> tuple[list[str], str | None] | None:
    key = hashlib.sha1(f"{lang}|{text.strip()}".encode()).hexdigest()
    row = con.execute("SELECT term_ids_json, plain FROM explain_cache WHERE key=?", (key,)).fetchone()
    return (json.loads(row[0]), row[1]) if row else None


def explain_cache_set(con: Connection, lang: str, text: str, term_ids: list[str], plain: str | None) -> None:
    key = hashlib.sha1(f"{lang}|{text.strip()}".encode()).hexdigest()
    con.execute("INSERT OR REPLACE INTO explain_cache VALUES (?,?,?,?,?,?)", (key, lang, text.strip()[:2000], json.dumps(term_ids), plain, now_s()))
    con.commit()


def brief_cache_get(con: Connection, key: str) -> str | None:
    """추천의 제품 이해 캐시 — 이용자 입력에서 나온 것이라 해석 캐시와 같은 표에 둔다(보존 기한·내보내기 제외·게시 때 삭제가 같게)."""
    row = con.execute("SELECT plain FROM explain_cache WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def brief_cache_set(con: Connection, key: str, payload: str) -> None:
    """원문은 남기지 않는다 — key 는 입력의 해시, text 칸은 비운다."""
    con.execute("INSERT OR REPLACE INTO explain_cache VALUES (?,?,?,?,?,?)", (key, "", "", "[]", payload, now_s()))
    con.commit()


# ---------- 급증 원인 설명 · 지식그래프 엣지 ----------

def save_explanation(con: Connection, x) -> None:
    key = f"{norm(x.term)}|{x.region}"
    row = con.execute("SELECT created_at FROM trend_explanations WHERE key=?", (key,)).fetchone()
    created = row[0] if row else now_s()
    con.execute("INSERT OR REPLACE INTO trend_explanations VALUES (?,?,?,?,?,?,?,?,?)",
                (key, x.term, x.region, x.date.isoformat(), x.trigger, x.self_confidence, x.model_dump_json(), created, now_s()))
    con.commit()


def get_explanation(con: Connection, term: str, region: str):
    from ..schemas import TrendExplanation

    row = con.execute("SELECT json, updated_at FROM trend_explanations WHERE key=?", (f"{norm(term)}|{region}",)).fetchone()
    return (TrendExplanation.model_validate_json(row[0]), datetime.fromisoformat(row[1])) if row else None


def explanations_by_region(con: Connection) -> dict[tuple[str, str], object]:
    from ..schemas import TrendExplanation

    out = {}
    for j in con.execute("SELECT json FROM trend_explanations").fetchall():
        x = TrendExplanation.model_validate_json(j[0])
        out[(norm(x.term), x.region)] = x
    return out


def add_edge(con: Connection, src_type: str, src_id: str, rel: str, dst_type: str, dst_id: str, evidence_id: str | None = None) -> None:
    con.execute("INSERT OR IGNORE INTO edges VALUES (?,?,?,?,?,?,?)", (src_type, src_id, rel, dst_type, dst_id, evidence_id, now_s()))
    con.commit()


def edges_from(con: Connection, src_type: str, src_id: str) -> list[dict]:
    return [dict(zip(("rel", "dst_type", "dst_id", "evidence_id"), r))
            for r in con.execute("SELECT rel, dst_type, dst_id, evidence_id FROM edges WHERE src_type=? AND src_id=?", (src_type, src_id)).fetchall()]


def prune_dangling_edges(con: Connection) -> int:
    """근거 행이 없는 EVIDENCED_BY 엣지 삭제. 09-15 02:09 이전 spikes 는 엣지만 남기고 근거를 저장하지 않았다 — 그 잔재 정리용(retention 단계)."""
    n = con.execute("DELETE FROM edges WHERE dst_type='evidence' AND dst_id NOT IN (SELECT evidence_id FROM evidences)").rowcount
    con.commit()
    return n


# ---------- 지식그래프 읽기 (edges → API·화면) ----------
# 노드: query(norm(term)|region) · actor(이름) · wiki(lang:제목) · evidence(evidence_id) · term(term_id)
# 엣지: EVIDENCED_BY · TRIGGERED_BY · ABOUT · IS_TERM — 전부 spikes 가 근거에 앵커된 것만 쓴다. 읽기도 판정 없이 있는 그대로 돌려준다.

def graph_query(con: Connection, key: str) -> dict | None:
    """급증 검색어 노드의 이웃. 엣지도 설명도 없으면 None."""
    rows = edges_from(con, "query", key)
    row = con.execute("SELECT term, region FROM trend_explanations WHERE key=?", (key,)).fetchone()
    if not rows and not row:
        return None
    term, region = (row[0], row[1]) if row else (key.rsplit("|", 1)[0], key.rsplit("|", 1)[-1] if "|" in key else "")
    return {"key": key, "term": term, "region": region, "explained": row is not None,
            "actors": [r["dst_id"] for r in rows if r["rel"] == "TRIGGERED_BY"],
            "wiki": [r["dst_id"] for r in rows if r["rel"] == "ABOUT"],
            "evidence_ids": [r["dst_id"] for r in rows if r["rel"] == "EVIDENCED_BY"],
            "term_id": next((r["dst_id"] for r in rows if r["rel"] == "IS_TERM"), None)}


def graph_shared_nodes(con: Connection, min_queries: int = 2, limit: int = 50) -> list[dict]:
    """여러 급증 검색어에 함께 걸린 인물·위키. 나라 수가 많은 것부터 — 같은 인물·사건이 나라를 건너 뜨는지 데이터로 본다(LLM 없음)."""
    by: dict[tuple[str, str], set[str]] = {}
    for dst_type, dst_id, src_id in con.execute("SELECT dst_type, dst_id, src_id FROM edges WHERE rel IN ('TRIGGERED_BY','ABOUT')").fetchall():
        by.setdefault((dst_type, dst_id), set()).add(src_id)
    out = [{"type": t, "id": i, "queries": sorted(srcs), "regions": sorted({k.rsplit("|", 1)[-1] for k in srcs})}
           for (t, i), srcs in by.items() if len(srcs) >= min_queries]
    out.sort(key=lambda x: (-len(x["regions"]), -len(x["queries"]), x["id"]))
    return out[:limit]


def graph_term_queries(con: Connection, term_id: str) -> list[dict]:
    """사전 용어에 IS_TERM 으로 연결된 급증 검색어 — 어느 나라 검색어가 이 표현이었나."""
    out = []
    for (key,) in con.execute("SELECT src_id FROM edges WHERE rel='IS_TERM' AND dst_type='term' AND dst_id=? ORDER BY created_at", (term_id,)).fetchall():
        row = con.execute("SELECT term, region, date FROM trend_explanations WHERE key=?", (key,)).fetchone()
        t, r = key.rsplit("|", 1) if "|" in key else (key, "")
        out.append({"key": key, "term": row[0] if row else t, "region": row[1] if row else r, "date": row[2] if row else None})
    return out


# ---------- 네이버 쇼핑인사이트 ----------

def upsert_shopping(con: Connection, category: str, age: str, points: list[dict]) -> int:
    """points: [{period, ratio}] — age 는 "all" 또는 "10"~"60"."""
    n = 0
    for p in points:
        n += con.execute("INSERT OR REPLACE INTO shopping_trends VALUES (?,?,?,?)", (category, age, p["period"], float(p["ratio"]))).rowcount
    con.commit()
    return n


def shopping_series(con: Connection) -> dict[tuple[str, str], list[tuple[str, float]]]:
    out: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for cat, age, wk, ratio in con.execute("SELECT category, age, week, ratio FROM shopping_trends ORDER BY week").fetchall():
        out.setdefault((cat, age), []).append((wk, ratio))
    return out


# ---------- 세대 곡선(네이버) · 주제 나라별 서술 ----------

def set_gen_curve(con: Connection, term_id: str, generation: str, points: list[dict]) -> None:
    con.execute("DELETE FROM gen_curves WHERE term_id=? AND generation=?", (term_id, generation))
    con.executemany("INSERT OR REPLACE INTO gen_curves VALUES (?,?,?,?)", [(term_id, generation, p["period"], float(p["ratio"])) for p in points])
    con.commit()


def get_gen_curves(con: Connection, term_id: str) -> dict[str, list[tuple[str, float]]]:
    out: dict[str, list[tuple[str, float]]] = {}
    for g, d, r in con.execute("SELECT generation, date, ratio FROM gen_curves WHERE term_id=? ORDER BY date", (term_id,)).fetchall():
        out.setdefault(g, []).append((d, r))
    return out


def set_topic_note(con: Connection, term_id: str, region: str, payload: str, model: str) -> None:
    con.execute("INSERT OR REPLACE INTO topic_notes VALUES (?,?,?,?,?)", (term_id, region, payload, now_s(), model))
    con.commit()


def get_topic_notes(con: Connection, term_id: str) -> dict[str, dict]:
    return {r: json.loads(j) for r, j in con.execute("SELECT region, json FROM topic_notes WHERE term_id=?", (term_id,)).fetchall()}


# 이용자 피드('최근 변화')에 내는 종류. 나머지(new_term 검증 전·recheck·candidate_meaning·reviewed)는 작업 기록이라 관리 화면용이다(화면 개편 2차 검토).
USER_UPDATE_KINDS = ("verified", "meaning_changed", "spike")
UPDATE_KINDS = ("new_term", "verified", "meaning_changed", "candidate_meaning", "spike", "recheck", "reviewed")


def recent_updates(con: Connection, hours: int = 48, limit: int | None = 60, kinds: tuple[str, ...] | None = None) -> list[dict]:
    """최근 변화: 새 용어, 확인된 뜻, 바뀐 뜻, 급증 설명, 재조사, 검수 결정. kinds 를 주면 그 종류만(한도는 거른 뒤에 적용)."""
    want = set(kinds) if kinds is not None else set(UPDATE_KINDS)
    since = (now() - timedelta(hours=hours)).isoformat()
    rows: list[dict] = []
    if "new_term" in want:
        for tid, canonical, first in con.execute("SELECT term_id, canonical, first_seen FROM terms WHERE first_seen>=?", (since,)).fetchall():
            rows.append({"kind": "new_term", "at": first, "label": canonical, "term_id": tid})
    if want & {"verified", "meaning_changed", "candidate_meaning"}:
        for tid, ver, vf, version in con.execute("SELECT term_id, verification, valid_from, version FROM meanings WHERE valid_from>=?", (since,)).fetchall():
            # 확인 전 뜻은 새 version 이라도 '뜻이 바뀐 밈' 이 아니다 — 이용자 피드에는 게이트를 통과한 뜻만
            kind = ("meaning_changed" if version > 1 else "verified") if ver.startswith("verified") else "candidate_meaning"
            if kind not in want:
                continue
            t = con.execute("SELECT canonical FROM terms WHERE term_id=?", (tid,)).fetchone()
            if not t:
                continue
            row = {"kind": kind, "at": vf, "label": t[0], "term_id": tid, "detail": ver}
            if kind == "meaning_changed":
                # 이전 뜻 — 번역은 지금 뜻에만 있으므로 원문 그대로 준다(화면이 표제어 언어로 lang 을 단다)
                prev = con.execute("SELECT json FROM meanings WHERE term_id=? AND version<? ORDER BY version DESC LIMIT 1", (tid, version)).fetchone()
                row["previous"] = (json.loads(prev[0]).get("definition") or None) if prev else None
            rows.append(row)
    if "spike" in want:
        for term, region, _created, updated, trig, j in con.execute(
                "SELECT term, region, created_at, updated_at, trigger, json FROM trend_explanations WHERE updated_at>=?", (since,)).fetchall():
            x = json.loads(j) if j else {}
            # 급증 이유 한 문장을 함께 준다 — 이름과 시각뿐이면 무엇이 일어났는지 알 수 없다(화면 개편 2차 검토)
            reason = {"ko": x.get("why_now") or "", "en": x.get("why_now_en") or x.get("why_now") or "", "ja": x.get("why_now_ja") or None} if trig != "unknown" else None
            rows.append({"kind": "spike", "at": updated, "label": term, "region": region, "detail": trig, "reason": reason})
    # 실패한 조사('error')는 이용자 피드에 낼 변화가 아니다
    if "recheck" in want:
        for tid, at, ver in con.execute("SELECT term_id, researched_at, verification FROM research_log WHERE researched_at>=? AND verification != 'error'", (since,)).fetchall():
            t = con.execute("SELECT canonical FROM terms WHERE term_id=?", (tid,)).fetchone()
            if t:
                rows.append({"kind": "recheck", "at": at, "label": t[0], "term_id": tid, "detail": ver})
    # 게이트가 스스로 닫은 것(decided_by='gate')은 검수 결정이 아니다 — 공개 피드에는 사람의 결정만
    if "reviewed" in want:
        for tid, decision, at in con.execute("SELECT term_id, decision, decided_at FROM review_queue WHERE decided_at>=? AND decision IS NOT NULL "
                                             "AND COALESCE(decided_by,'') != 'gate'", (since,)).fetchall():
            t = con.execute("SELECT canonical FROM terms WHERE term_id=?", (tid,)).fetchone()
            if t:
                rows.append({"kind": "reviewed", "at": at, "label": t[0], "term_id": tid, "detail": decision})
    from ..pipeline.match import unsafe

    def shown(r: dict) -> bool:
        # 공개 '최근 변화' 도 둘러보는 목록이다 — 욕설 표제어는 내지 않는다. 검수자가 '문제 없음' 으로 푼 것은 낸다(대시보드·나라 화면과 같게, 검토 3차)
        if not unsafe(r.get("label") or ""):
            return True
        t = get_term(con, r["term_id"]) if r.get("term_id") else None
        return bool(t and t.risk_level == "none")

    rows = [r for r in rows if shown(r)]
    rows.sort(key=lambda r: r["at"] or "", reverse=True)
    return rows[:limit]


def update_feed(con: Connection, hours: int = 48, kinds: tuple[str, ...] = USER_UPDATE_KINDS, limit: int = 100) -> dict:
    """'최근 변화' 화면용. 이용자 종류는 한 표현에 하루 한 행(가장 중요한 변화 하나)으로 줄이고, 종류별 합계는 자르기 전에 센다 —
    한도에 잘린 조각을 세면 건수가 전부인지 알 수 없다(화면 개편 2차 검토). 작업 기록 종류는 그대로 둔다(관리 화면에서 기록으로 본다)."""
    from ..verification import hidden_from_public, is_public_entry

    rank = {k: i for i, k in enumerate(("meaning_changed", "verified", "spike"))}
    best: dict[tuple, dict] = {}
    rest: list[dict] = []
    hidden: dict[str, bool] = {}
    public: dict[str, bool] = {}
    for r in recent_updates(con, hours=hours, limit=None, kinds=kinds):
        tid = r.get("term_id")
        if tid and tid not in hidden:
            t = get_term(con, tid)
            hidden[tid] = bool(t) and hidden_from_public(t.canonical, t.risk_level)
            public[tid] = is_public_entry(t, current_meaning(con, tid) if t else None)
        if tid and hidden[tid]:      # 공개 사전에서 숨긴 말(사용 자제·욕설·성적 표제어)은 피드에도 이름을 내지 않는다(10-09)
            continue
        # 이용자 종류는 지금 사전에 있는 말만 — 실렸다가 검수로 내려간 말(フェムテック·サウナー)의 링크가 404 였다(10-14)
        if tid and r["kind"] in rank and not public[tid]:
            continue
        if r["kind"] not in rank:
            rest.append(r)
            continue
        key = (r.get("term_id") or f"{norm(r['label'])}|{r.get('region') or ''}", (r["at"] or "")[:10])
        cur = best.get(key)
        # 같은 날 같은 표현이면 중요한 종류가, 같은 종류면 늦은 것이 남는다(시각순으로 들어오므로 먼저 온 것이 늦은 것)
        if cur is None or rank[r["kind"]] < rank[cur["kind"]]:
            best[key] = r
    rows = sorted([*best.values(), *rest], key=lambda r: r["at"] or "", reverse=True)
    counts = {k: 0 for k in kinds}
    for r in rows:
        counts[r["kind"]] = counts.get(r["kind"], 0) + 1
    return {"items": rows[:limit], "counts": counts, "total": len(rows)}


# 이용자가 읽는 게시본을 다시 쓰는 단계. 파이프라인 끝의 지도(board)·키워드 대시보드(dashboard)가 그때까지의 편집 결과를 모아
# 공개 캐시를 새로 만든다 — 수집·중간 단계만 끝난 실행은 게시본을 바꾸지 않는다(ADR 0001 '마지막 정상 갱신', Plan 05·06).
# 그래서 '게시가 멈췄나' 만 잰다. 두 단계는 저장된 행으로 다시 만들어 수집원이 모두 실패해도 'ok' 다 — 수집원 실패는
# 관리 화면 '수집 현황'(/pipeline/stages)과 health_check 의 '하루 안에 실패한 단계' 가 본다.
# 운영 게시 방법(Plan 06 1단계)이 무엇이든 운영 pipeline_runs 에 이 단계들의 'ok' 행을 남겨야 한다. 게시 단계를 따로 두면 그 이름을
# 여기에 더한다 — 아니면 운영 /meta 는 last_run=None·stale 을 계속 내고 유지보수 Job 은 매번 2 로 끝난다.
PUBLISH_STAGES = ("board", "dashboard")
# 게시가 이보다 오래되면 오래된 자료다. 23:15 실행 뒤 다음 날 09:15 실행까지 게시가 10시간 빈다(09-17~09-28 실측 10.0~10.5시간).
# 기본 12시간, 환경변수 STALE_AFTER_HOURS 로 바꾼다.
STALE_AFTER_HOURS = _STALE_AFTER_HOURS


def last_published(con: Connection) -> str | None:
    """마지막 정상 게시 시각: 게시 단계마다 마지막으로 성공('ok')한 때 중 이른 것. 한 번도 성공하지 않은 단계가 있으면 None.
    전에는 어느 단계든 끝난 때(0건·건너뜀 포함)라 수집만 돌아도 새 자료로 보였다 — 09-28 지도 단계가 19:33·23:33(한국 시각)에
    실패해 지도가 14:27 것이었는데도 23:33 을 냈다."""
    active = con.execute("SELECT p.published_at FROM publication_state s JOIN publications p ON p.publication_id=s.publication_id WHERE s.singleton=1").fetchone()
    if active:
        return active[0]
    marks = ",".join("?" * len(PUBLISH_STAGES))
    last = dict(con.execute(f"SELECT stage, MAX(finished_at) FROM pipeline_runs WHERE status='ok' AND stage IN ({marks}) GROUP BY stage",
                            PUBLISH_STAGES).fetchall())
    if not all(last.get(s) for s in PUBLISH_STAGES):
        return None
    return min(last.values(), key=datetime.fromisoformat)


def last_collected(con: Connection) -> str | None:
    """자료를 마지막으로 모은 때 — 수집 단계(collect.*)가 마지막으로 성공한 때. 화면의 '자료 수집' 시각이다.
    대시보드 캐시를 다시 만든 때(generated_at)를 갱신으로 보이면, 10-01 자료로 오늘 캐시를 만들어도 오늘 자료처럼 보였다(10-05)."""
    row = con.execute("SELECT MAX(finished_at) FROM pipeline_runs WHERE status='ok' AND stage LIKE 'collect.%'").fetchone()
    return row[0] if row and row[0] else None


def is_stale(published: str | None) -> bool:
    """게시가 없거나 STALE_AFTER_HOURS 보다 오래됐나."""
    return not published or now() - datetime.fromisoformat(published) > timedelta(hours=STALE_AFTER_HOURS)


# ---------- 로그인한 사람의 설정 (세대·나라) ----------
# 익명 방문자는 설정을 갖지 않는다 — 설명은 중립으로 나가고 재작성 캐시도 하나로 모인다(2026-09-16 결정).

def get_prefs(con: Connection, user: str) -> dict:
    row = con.execute("SELECT json FROM reader_prefs WHERE reader=?", (user,)).fetchone()
    return json.loads(row[0]) if row else {}


def set_prefs(con: Connection, user: str, prefs: dict) -> None:
    con.execute("INSERT OR REPLACE INTO reader_prefs VALUES (?,?,?)", (user, json.dumps(prefs, ensure_ascii=False), now_s()))
    con.commit()


# ---------- 해석 실패 메시지 (표현 발굴 재료) ----------

def log_lookup_miss(con: Connection, text: str, lang: str) -> None:
    """사전에 없는 표현이 든 메시지. 200자 이하만, 발굴 단계가 소비하면 지운다 — 사람이 쓴 문장을 오래 두지 않는다."""
    text = text.strip()
    if not text or len(text) > 200:
        return
    key = new_id("l", f"{lang}|{norm(text)}")
    t = now_s()
    con.execute("INSERT INTO lookups VALUES (?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET count=lookups.count+1, last_at=excluded.last_at", (key, text, lang, 1, t, t))
    con.commit()


def prune_user_text(con: Connection, cache_days: int = 7, lookup_days: int = 30) -> tuple[int, int]:
    """사람이 붙여 넣은 문장은 오래 두지 않는다. 해석 캐시는 cache_days, 못 답한 질문은 lookup_days 가 지나면 지운다 (2026-09-28 결정)."""
    cache_cutoff = (now() - timedelta(days=cache_days)).isoformat()
    lookup_cutoff = (now() - timedelta(days=lookup_days)).isoformat()
    cache = con.execute("DELETE FROM explain_cache WHERE created_at < ?", (cache_cutoff,)).rowcount
    lookups = con.execute("DELETE FROM lookups WHERE last_at < ?", (lookup_cutoff,)).rowcount
    con.commit()
    return cache, lookups


def pending_lookups(con: Connection, limit: int = 100) -> list[tuple[str, str, str]]:
    """(key, text, lang) — 많이 물어본 것부터."""
    return con.execute("SELECT key, text, lang FROM lookups ORDER BY count DESC, last_at DESC LIMIT ?", (limit,)).fetchall()


def delete_lookups(con: Connection, keys: list[str]) -> None:
    if keys:
        con.executemany("DELETE FROM lookups WHERE key=?", [(k,) for k in keys])
        con.commit()


# --- 대표 그림·영상 -----------------------------------------------------------
# 파일을 받아 두지 않는다. 위키미디어 공용(자유 라이선스)과 유튜브 주소만 두고, 라이선스·출처를 함께 보관한다.
# 영어판에 직접 올라온 공정이용 그림은 여기 들어오면 안 된다 (collectors/wikipedia_search.free_image 가 거른다).


def add_media(con: Connection, term_id: str, kind: str, url: str, *, page_url: str = "",
              title: str = "", license: str = "", attribution: str = "") -> None:
    if not url:
        return
    con.execute("INSERT OR REPLACE INTO term_media VALUES (?,?,?,?,?,?,?,?)",
                (term_id, kind, url, page_url, title[:200], license[:80], attribution[:200], now().isoformat()))
    con.commit()


def catalog_categories(con: Connection, term_id: str) -> list[list[str]]:
    """표제어가 걸린 위키 분류 이름들 — 문서(출처·제목)마다 한 묶음."""
    if (rows := _cached("catalog", term_id)) is None:
        rows = con.execute("SELECT categories_json FROM wiki_catalog WHERE term_id=?", (term_id,)).fetchall()
    return [json.loads(cats or "[]") for (cats,) in rows]


def get_media(con: Connection, term_id: str, limit: int = 4) -> list[dict]:
    if (rows := _cached("media", term_id)) is not None:
        rows = rows[:limit]
    else:
        rows = con.execute("SELECT kind, url, page_url, title, license, attribution FROM term_media "
                           "WHERE term_id=? ORDER BY kind DESC, added_at LIMIT ?", (term_id, limit)).fetchall()
    return [{"kind": k, "url": u, "page_url": p, "title": t, "license": lic, "attribution": a}
            for k, u, p, t, lic, a in rows]


def has_media(con: Connection, term_id: str) -> bool:
    return con.execute("SELECT 1 FROM term_media WHERE term_id=? LIMIT 1", (term_id,)).fetchone() is not None


def expire_candidates(con: Connection, days: int = 7, sources: tuple[str, ...] = ("spot",)) -> int:
    """한 번만 보이고 오래 묵은 후보를 만료시킨다. 두 번째 등장을 영원히 기다리면 대기열이 끝없이 자란다
    (2026-09-28 실측: 11일 동안 167 → 426, 그중 spot 출신 한 번짜리가 353)."""
    cutoff = (now() - timedelta(days=days)).isoformat()
    n = 0
    for cid, j in con.execute("SELECT candidate_id, json FROM candidates WHERE status='new'").fetchall():
        c = Candidate.model_validate_json(j)
        if c.count <= 1 and c.last_seen.isoformat() < cutoff and set(c.sources) <= set(sources):
            set_candidate_status(con, cid, "expired")
            n += 1
    return n


def has_candidate(con: Connection, text: str, lang: str) -> bool:
    return con.execute("SELECT 1 FROM candidates WHERE norm=? AND lang=?", (norm(text), lang)).fetchone() is not None


def set_evidence_labels(con: Connection, term_id: str, rows: list[tuple[str, str, str]], model: str) -> None:
    """rows: (evidence_id, polarity, risk)"""
    t = now_s()
    con.executemany("INSERT OR REPLACE INTO evidence_labels VALUES (?,?,?,?,?,?)",
                    [(eid, term_id, pol, risk, model, t) for eid, pol, risk in rows])
    con.commit()


def evidence_labels(con: Connection, term_id: str) -> dict[str, tuple[str, str]]:
    return {e: (p, r) for e, p, r in con.execute(
        "SELECT evidence_id, polarity, risk FROM evidence_labels WHERE term_id=?", (term_id,)).fetchall()}


def evidence_label_rows(con: Connection, term_id: str) -> dict[str, tuple[str, str, str, str]]:
    """근거 문장 분류를 화면에 보일 때 — (뉘앙스, 위험 유형, 붙인 모델, 붙인 때). 판정은 evidence_labels 를 쓴다."""
    return {e: (p, r, m or "", at or "") for e, p, r, m, at in con.execute(
        "SELECT evidence_id, polarity, risk, model, labeled_at FROM evidence_labels WHERE term_id=?", (term_id,)).fetchall()}


# ---------- 광고 쓰임 낱말 (Plan 07) ----------

def set_fit(con: Connection, term_id: str, meaning_id: str, fit: MemeFit, model: str) -> None:
    con.execute("INSERT OR REPLACE INTO term_fit VALUES (?,?,?,?,?)", (term_id, meaning_id, fit.model_dump_json(), model, now_s()))
    con.commit()


def all_fits(con: Connection) -> dict[str, tuple[str, MemeFit]]:
    """{term_id: (붙일 때의 meaning_id, MemeFit)}"""
    return {tid: (mid, MemeFit.model_validate_json(j)) for tid, mid, j in con.execute("SELECT term_id, meaning_id, json FROM term_fit").fetchall()}


# ---------- 언급 표본 (뉴스 검색을 누구에게 먼저 돌리나) ----------

def mention_sampled(con: Connection) -> dict[str, str]:
    return dict(con.execute("SELECT term_id, last_at FROM mention_queries").fetchall())


def mention_rotation(con: Connection) -> dict[str, str]:
    """용어마다 지난번 언급을 잰 나라 — 번갈아 재는 말(대만·홍콩 등)의 다음 차례를 정한다."""
    return dict(con.execute("SELECT term_id, region FROM mention_queries WHERE region IS NOT NULL").fetchall())


def mark_mention_sampled(con: Connection, term_id: str, region: str | None = None) -> None:
    con.execute("INSERT OR REPLACE INTO mention_queries VALUES (?,?,?)", (term_id, now_s(), region))
    con.commit()


def add_mention_samples(con: Connection, term_id: str, items: list, homes: dict[str, str]) -> None:
    """이 용어의 뉴스 키워드 검색이 찾은 기사(표제어가 든 것만 넘긴다)와 매체의 나라(homes). 같은 판의 같은 기사는 새로 본 값으로 바꾼다."""
    def utc(d: datetime | None) -> str:
        d = d or now()
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()

    con.executemany("INSERT OR REPLACE INTO mention_samples VALUES (?,?,?,?,?,?)",
                    [(term_id, n.region, n.link, n.source, homes.get(n.source), utc(n.published_at)) for n in items])
    con.commit()


def indicator_mentions(con: Connection, term_id: str) -> list[tuple[str, str]]:
    """근거(news)에 넣지 않은 키워드 검색 기사 — (판, 발행 시각). 같은 기사가 news 에 있으면 그쪽에서 센다(한 번만)."""
    return con.execute("SELECT m.region, m.published_at FROM mention_samples m WHERE m.term_id=? "
                       "AND NOT EXISTS (SELECT 1 FROM news n WHERE n.link=m.link)", (term_id,)).fetchall()


def mention_outlets(con: Connection, term_id: str, since: str) -> list[tuple[str, str]]:
    """(매체의 나라, 매체) — since 이후 발행된 키워드 검색 기사 가운데 나라를 아는 매체의 것마다(같은 매체가 여러 번 나온다)."""
    if (rows := _cached("outlets", term_id)) is not None:
        return [(home, source) for home, source, published in rows if published is not None and published >= since]
    return con.execute("SELECT home, source FROM mention_samples WHERE term_id=? AND home IS NOT NULL AND published_at >= ?",
                       (term_id, since)).fetchall()


# ---------- 커뮤니티 조사 차례 (Plan 04) ----------

def research_count(con: Connection, term_id: str) -> int:
    """이 용어를 조사한 횟수(실패 포함). 커뮤니티를 나라마다 번갈아 뒤질 때 차례로 쓴다."""
    return con.execute("SELECT COUNT(*) FROM research_log WHERE term_id=?", (term_id,)).fetchone()[0]
