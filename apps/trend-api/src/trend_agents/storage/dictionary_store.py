"""사전·파이프라인 상태의 PostgreSQL 저장 (시스템 오브 레코드). Spanner Graph 는 이 내용을 미러링한다.

원칙: Pydantic JSON 통째 + 조회용 컬럼. 삭제는 없다 — 뜻이 바뀌면 새 version, 이전 version 은 valid_to 를 닫는다.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone

from ..schemas import Candidate, Evidence, Meaning, MeaningDraft, MeaningText, MemeFit, Term, TrendQuery, WikiTop
from . import db
from .db import Connection

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
CREATE TABLE IF NOT EXISTS usage (term_id TEXT, segment_id TEXT, generation TEXT, region TEXT, first_seen TEXT, share DOUBLE PRECISION, PRIMARY KEY(term_id, segment_id));
CREATE TABLE IF NOT EXISTS term_timeline (
  term_id TEXT, region TEXT, first_date TEXT, source_ko TEXT, source_en TEXT, url TEXT, updated_at TEXT, PRIMARY KEY(term_id, region));
CREATE TABLE IF NOT EXISTS mentions_weekly (term_id TEXT, week_start TEXT, count BIGINT, PRIMARY KEY(term_id, week_start));
-- 용어마다 뉴스 검색으로 언급을 마지막으로 잰 때(마이그레이션 006). collect.mentions 가 오래된 것부터 돌아가며 잰다.
CREATE TABLE IF NOT EXISTS mention_queries (term_id TEXT PRIMARY KEY, last_at TEXT);
-- 나라별 원본 언급(Plan 04, 마이그레이션 005). 대시보드가 고른 지역의 수치만 보이게 한다.
CREATE TABLE IF NOT EXISTS mentions_weekly_region (term_id TEXT, region TEXT, week_start TEXT, count BIGINT, PRIMARY KEY(term_id, region, week_start));
CREATE TABLE IF NOT EXISTS translations (term_id TEXT, lang TEXT, json TEXT, updated_at TEXT, model TEXT, PRIMARY KEY(term_id, lang));
CREATE TABLE IF NOT EXISTS review_queue (
  term_id TEXT PRIMARY KEY, draft_json TEXT, reasons_json TEXT, evidence_count BIGINT, queued_at TEXT, decision TEXT, decided_at TEXT, decided_by TEXT);
CREATE TABLE IF NOT EXISTS research_log (term_id TEXT, researched_at TEXT, model TEXT, notes TEXT, urls_json TEXT, verification TEXT, reasons_json TEXT);
CREATE TABLE IF NOT EXISTS pipeline_runs (run_id TEXT, stage TEXT, started_at TEXT, finished_at TEXT, count BIGINT, status TEXT, note TEXT);
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


def set_risk(con: Connection, term_id: str, level, reasons: list[str], rule_level, checked_at: datetime) -> Term | None:
    """리스크 단계의 저장 — 리스크 필드만 바꾸고 나머지(상태·별칭·사람의 결정)는 저장된 그대로 둔다."""
    t = get_term(con, term_id)
    if not t:
        return None
    return _write_term(con, t.model_copy(update={"risk_level": level, "risk_reasons": reasons, "risk_rule_level": rule_level,
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
    row = con.execute("SELECT json FROM meanings WHERE term_id=? AND valid_to IS NULL ORDER BY version DESC LIMIT 1", (term_id,)).fetchone()
    return Meaning.model_validate_json(row[0]) if row else None


def list_meanings(con: Connection, term_id: str) -> list[Meaning]:
    rows = con.execute("SELECT json FROM meanings WHERE term_id=? ORDER BY version", (term_id,)).fetchall()
    return [Meaning.model_validate_json(r[0]) for r in rows]


def add_meaning(con: Connection, term_id: str, draft: MeaningDraft, verification: str, citations: list[str], created_by: str = "research_agent") -> Meaning:
    """새 version 을 만들고 이전 현행 version 의 valid_to 를 닫는다. 뜻이 같으면(정의·풀이 동일) 새 version 을 만들지 않고 현행을 돌려준다."""
    cur = current_meaning(con, term_id)
    if cur and cur.definition == draft.definition and cur.expansion == draft.expansion and cur.verification == verification:
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
    rows = con.execute("SELECT json FROM evidences WHERE term_id=? ORDER BY observed_at DESC", (term_id,)).fetchall()
    return [Evidence.model_validate_json(r[0]) for r in rows]


def set_usage(con: Connection, term_id: str, rows: list[tuple[str, str, str, float]]) -> None:
    """rows: (generation, region, first_seen_iso, share)"""
    for gen, region, first, share in rows:
        con.execute("INSERT OR REPLACE INTO usage VALUES (?,?,?,?,?,?)", (term_id, f"{region}-{gen}", gen, region, first, share))
    con.commit()


def clear_usage(con: Connection, term_id: str) -> None:
    con.execute("DELETE FROM usage WHERE term_id=?", (term_id,))
    con.commit()


def get_usage(con: Connection, term_id: str) -> list[dict]:
    return [dict(zip(("segment_id", "generation", "region", "first_seen", "share"), r))
            for r in con.execute("SELECT segment_id, generation, region, first_seen, share FROM usage WHERE term_id=? ORDER BY share DESC", (term_id,)).fetchall()]


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
    rows = con.execute("SELECT week_start, count FROM mentions_weekly WHERE term_id=? ORDER BY week_start DESC LIMIT ?", (term_id, weeks)).fetchall()
    return list(reversed(rows))


def set_translation(con: Connection, term_id: str, lang: str, text: MeaningText, model: str) -> None:
    con.execute("INSERT OR REPLACE INTO translations VALUES (?,?,?,?,?)", (term_id, lang, text.model_dump_json(), now_s(), model))
    con.commit()


def get_translation(con: Connection, term_id: str, lang: str) -> MeaningText | None:
    row = con.execute("SELECT json FROM translations WHERE term_id=? AND lang=?", (term_id, lang)).fetchone()
    return MeaningText.model_validate_json(row[0]) if row else None


# ---------- 검수 큐 · 리서치 로그 ----------

def queue_review(con: Connection, term_id: str, draft: MeaningDraft, reasons: list[str], evidence_count: int) -> None:
    con.execute(
        "INSERT OR REPLACE INTO review_queue VALUES (?,?,?,?,?,NULL,NULL,NULL)",
        (term_id, draft.model_dump_json(), json.dumps(reasons, ensure_ascii=False), evidence_count, now_s()),
    )
    con.commit()


def review_queue(con: Connection) -> list[dict]:
    rows = con.execute("SELECT term_id, draft_json, reasons_json, evidence_count, queued_at FROM review_queue WHERE decision IS NULL ORDER BY queued_at DESC").fetchall()
    return [{"term_id": r[0], "draft": MeaningDraft.model_validate_json(r[1]), "reasons": json.loads(r[2]), "evidence_count": r[3], "queued_at": r[4]} for r in rows]


def decide_review(con: Connection, term_id: str, decision: str, by: str) -> None:
    con.execute("UPDATE review_queue SET decision=?, decided_at=?, decided_by=? WHERE term_id=?", (decision, now_s(), by, term_id))
    con.commit()


def gate_reasons(con: Connection, term_id: str) -> list[str]:
    row = con.execute("SELECT reasons_json FROM review_queue WHERE term_id=? AND decision IS NULL", (term_id,)).fetchone()
    return json.loads(row[0]) if row else []


def log_research(con: Connection, term_id: str, model: str, notes: str, urls: list[str], verification: str, reasons: list[str]) -> None:
    con.execute("INSERT INTO research_log VALUES (?,?,?,?,?,?,?)",
                (term_id, now_s(), model, notes[:4000], json.dumps(urls), verification, json.dumps(reasons, ensure_ascii=False)))
    con.commit()


def last_researched(con: Connection, term_id: str, ok_only: bool = False) -> datetime | None:
    """마지막 조사 시각. ok_only 면 실패('error') 기록을 뺀다."""
    q = "SELECT MAX(researched_at) FROM research_log WHERE term_id=?" + (" AND verification != 'error'" if ok_only else "")
    row = con.execute(q, (term_id,)).fetchone()
    return datetime.fromisoformat(row[0]) if row and row[0] else None


# ---------- 실행 기록 · 예산 · 캐시 ----------

def run_start(con: Connection, stage: str) -> str:
    rid = new_id("r")
    con.execute("INSERT INTO pipeline_runs VALUES (?,?,?,?,?,?,?)", (rid, stage, now_s(), None, 0, "running", ""))
    con.commit()
    return rid


def run_finish(con: Connection, run_id: str, count: int, status: str, note: str = "") -> None:
    con.execute("UPDATE pipeline_runs SET finished_at=?, count=?, status=?, note=? WHERE run_id=?", (now_s(), count, status, note[:500], run_id))
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


def explain_cache_get(con: Connection, lang: str, text: str) -> tuple[list[str], str | None] | None:
    key = hashlib.sha1(f"{lang}|{text.strip()}".encode()).hexdigest()
    row = con.execute("SELECT term_ids_json, plain FROM explain_cache WHERE key=?", (key,)).fetchone()
    return (json.loads(row[0]), row[1]) if row else None


def explain_cache_set(con: Connection, lang: str, text: str, term_ids: list[str], plain: str | None) -> None:
    key = hashlib.sha1(f"{lang}|{text.strip()}".encode()).hexdigest()
    con.execute("INSERT OR REPLACE INTO explain_cache VALUES (?,?,?,?,?,?)", (key, lang, text.strip()[:2000], json.dumps(term_ids), plain, now_s()))
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


def recent_updates(con: Connection, hours: int = 48, limit: int = 60) -> list[dict]:
    """최근 변화: 새 용어, 확인된 뜻, 바뀐 뜻, 급증 설명, 재조사, 검수 결정."""
    since = (now() - timedelta(hours=hours)).isoformat()
    rows: list[dict] = []
    for tid, canonical, first in con.execute("SELECT term_id, canonical, first_seen FROM terms WHERE first_seen>=?", (since,)).fetchall():
        rows.append({"kind": "new_term", "at": first, "label": canonical, "term_id": tid})
    for tid, ver, vf, version in con.execute("SELECT term_id, verification, valid_from, version FROM meanings WHERE valid_from>=?", (since,)).fetchall():
        t = con.execute("SELECT canonical FROM terms WHERE term_id=?", (tid,)).fetchone()
        if not t:
            continue
        kind = "meaning_changed" if version > 1 else ("verified" if ver.startswith("verified") else "candidate_meaning")
        rows.append({"kind": kind, "at": vf, "label": t[0], "term_id": tid, "detail": ver})
    for term, region, created, updated, trig in con.execute("SELECT term, region, created_at, updated_at, trigger FROM trend_explanations WHERE updated_at>=?", (since,)).fetchall():
        rows.append({"kind": "spike", "at": updated, "label": term, "region": region, "detail": trig})
    # 실패한 조사('error')는 이용자 피드에 낼 변화가 아니다
    for tid, at, ver in con.execute("SELECT term_id, researched_at, verification FROM research_log WHERE researched_at>=? AND verification != 'error'", (since,)).fetchall():
        t = con.execute("SELECT canonical FROM terms WHERE term_id=?", (tid,)).fetchone()
        if t:
            rows.append({"kind": "recheck", "at": at, "label": t[0], "term_id": tid, "detail": ver})
    # 게이트가 스스로 닫은 것(decided_by='gate')은 검수 결정이 아니다 — 공개 피드에는 사람의 결정만
    for tid, decision, at in con.execute("SELECT term_id, decision, decided_at FROM review_queue WHERE decided_at>=? AND decision IS NOT NULL "
                                         "AND COALESCE(decided_by,'') != 'gate'", (since,)).fetchall():
        t = con.execute("SELECT canonical FROM terms WHERE term_id=?", (tid,)).fetchone()
        if t:
            rows.append({"kind": "reviewed", "at": at, "label": t[0], "term_id": tid, "detail": decision})
    from ..pipeline.match import unsafe

    rows = [r for r in rows if not unsafe(r.get("label") or "")]   # 공개 '오늘의 변화' 도 둘러보는 목록이다 — 욕설 표제어는 내지 않는다
    rows.sort(key=lambda r: r["at"] or "", reverse=True)
    return rows[:limit]


def last_finished(con: Connection) -> str | None:
    row = con.execute("SELECT MAX(finished_at) FROM pipeline_runs WHERE status IN ('ok','zero','skipped')").fetchone()
    return row[0] if row else None


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


def get_media(con: Connection, term_id: str, limit: int = 4) -> list[dict]:
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


def mark_mention_sampled(con: Connection, term_id: str) -> None:
    con.execute("INSERT OR REPLACE INTO mention_queries VALUES (?,?)", (term_id, now_s()))
    con.commit()

