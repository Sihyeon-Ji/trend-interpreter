"""사전 품질 감사 (2026-09-30). 실린 뜻을 참고 문서와 나란히 놓고 모델이 **체크리스트에만** 답한다. '고칠 것' 인지는 규칙이 정한다.

체크리스트는 표본 검토에서 실제로 나온 문제다(Plan 16):
- 대상(노래·작품·인물·물건)의 소개만 있고 밈으로 어떻게 쓰이는지가 없다
- 문서와 다른 대상을 설명한다('ライラック' 노래에 꽃 라일락)
- 제목을 번역만 했다
- 뜻·유래가 문서와 어긋난다

모델은 바꿀 수 있다(model="local" 로컬 Gemma, "gemini" Gemini). 같은 문제로 둘을 비교해 어느 쪽에 맡길지 정한다(scripts/audit_eval.py).
문서 글은 그 자리에서 읽고 저장하지 않는다.
"""
from __future__ import annotations

import sqlite3
from typing import Literal

from pydantic import BaseModel, Field

from ..schemas import Evidence, Meaning, Term
from ..verification import reference_doc

DOCS = 2
DOC_CHARS = 1500

PROMPT = """너는 인터넷 밈 사전의 감사관이다. 사전 항목 '{term}' 의 뜻이 아래 참고 문서와 맞는지 체크리스트에 답하라.
문서에 적힌 것만 기준으로 삼고, 네가 따로 아는 것으로 판단하지 마라.

사전에 실린 뜻:
- 뜻: {definition}
- 유래: {origin}
- 뉘앙스: {nuance}

참고 문서:
{docs}

체크리스트:
- same_subject: 사전의 뜻이 문서와 같은 대상을 말하는가. 이름만 같고 다른 것(노래 문서인데 꽃을 설명, 사람인데 지명)이면 false.
- describes_usage: 뜻이 이 표현이 인터넷에서 **어떻게 쓰이는지**(무엇을 뜻하며 어떤 상황에 쓰나)를 말하는가. 대상 소개(노래·작품·인물·제품 설명)만 있으면 false.
- translation_only: 뜻이 제목을 다른 말로 옮긴 것뿐이고 설명이 없는가.
- matches_doc: 뜻·유래가 문서 내용과 맞는가 — yes(맞음) · partly(일부 빠지거나 흐림) · no(어긋남).
- origin_ok: 유래가 문서의 유래와 맞거나, 유래를 모른다고 적었는가. 사이트 이름만 적었거나 문서와 다르면 false.
- missing_key: 문서가 분명히 적은 핵심(처음 나온 작품·사람·장면, 지금의 주된 쓰임)이 사전 뜻·유래에 빠졌는가.
reason 에는 무엇이 문제인지(없으면 무엇이 맞는지)를 한국어 한두 문장으로 쓴다."""


# 파인튜닝한 감사관의 짧은 형식(판정·까닭). 학습 정답이 전수조사의 판정·문제점이라 체크리스트 칸이 없다.
SIMPLE_PROMPT = """너는 인터넷 밈 사전의 감사관이다. 사전 항목 '{term}' 의 뜻을 아래 참고 문서와 맞춰 보라. 문서에 적힌 것만 기준으로 삼는다.

사전에 실린 뜻:
- 뜻: {definition}
- 유래: {origin}
- 뉘앙스: {nuance}

참고 문서:
{docs}

verdict 는 ok(문서와 맞고, 이 표현이 밈으로 어떻게 쓰이는지 적었다) 또는 fix(문서와 어긋나거나, 다른 대상을 설명하거나, 대상 소개·제목 번역뿐이거나,
문서가 적은 핵심 — 처음 나온 곳·주된 쓰임 — 이 빠졌다). reason 에 한국어 한두 문장으로 까닭을 쓴다.
JSON 하나로만 답한다: {{"verdict": "ok" 또는 "fix", "reason": "..."}}"""


# 대시보드가 이 까닭으로 남은 뜻(다시 써도 대상 소개뿐)의 말을 둘러보는 목록에서 뺀다(dashboard.meme_use)
NO_USAGE = "밈으로 어떻게 쓰이는지가 없다"


class AuditVerdict(BaseModel):
    verdict: Literal["ok", "fix"]
    reason: str = ""


class AuditCheck(BaseModel):
    same_subject: bool
    describes_usage: bool
    translation_only: bool
    matches_doc: Literal["yes", "partly", "no"]
    origin_ok: bool
    missing_key: bool = False
    reason: str = Field(default="")


def verdict(c: AuditCheck) -> tuple[str, list[str]]:
    """체크리스트 → ('ok' | 'fix', 까닭들). 규칙이 정한다."""
    why = []
    if not c.same_subject:
        why.append("문서와 다른 대상을 설명한다")
    if c.translation_only:
        why.append("제목을 옮긴 것뿐이다")
    if not c.describes_usage:
        why.append(NO_USAGE)
    if c.matches_doc == "no":
        why.append("뜻·유래가 문서와 어긋난다")
    if not c.origin_ok:
        why.append("유래가 문서와 다르거나 비었다")
    if c.missing_key:
        why.append("문서의 핵심(처음 나온 곳·주된 쓰임)이 빠졌다")
    return ("fix" if why else "ok"), why


def documents(term: Term, evidences: list[Evidence]) -> list[tuple[Evidence, str]]:
    """참고 문서 가운데 글이 있는 것 DOCS 개 — 표제어 언어의 위키 먼저(crosscheck 순서). 글은 메모리에서만."""
    from . import crosscheck

    docs = sorted({e.url: e for e in evidences if reference_doc(e)}.values(), key=lambda e: crosscheck._home_rank(term, e.url))
    # 제목이 표제어인 문서만 — 근거에 붙은 딴 문서('점메추' 에 나무위키 '메뉴')를 보이면 감사관이 뜻이 아니라 근거를 탓한다(09-30 채점)
    from ..verification import doc_titled

    titled = [e for e in docs if doc_titled(term.canonical, e, term.aliases)]
    out = []
    for e in titled:
        text = crosscheck.doc_text(e) if "fandom.com" not in e.url else _fandom_text(e)
        text = _skip_toc(text)
        if text:
            out.append((e, text[:DOC_CHARS]))
        if len(out) >= DOCS:
            break
    return out


def _skip_toc(text: str) -> str:
    """나무위키 본문 앞의 목차('개요 2 . 상세 3 . …')를 건너뛴다 — 1. 개요 [편집] 뒤부터. 목차가 1,500자의 절반을 먹었다(09-30)."""
    import re

    m = re.search(r"1\s*\.\s*개요\s*\[편집\]", text or "")
    return text[m.end():].strip() if m else (text or "")


def _fandom_text(e: Evidence) -> str:
    from urllib.parse import unquote, urlsplit

    from ..collectors import fandom

    site = next((k for k, v in fandom.SITES.items() if v["domain"] == urlsplit(e.url).hostname), None)
    return fandom.intro(site, unquote(urlsplit(e.url).path).rsplit("/", 1)[-1]) if site else ""


def check(con: Connection, term: Term, meaning: Meaning, docs: list[tuple[Evidence, str]], model: str = "local",
          temperature: float = 0.1) -> tuple[AuditCheck, str]:
    from . import crosscheck, local_llm

    lines = "\n\n".join(f"{i}. [{crosscheck.wiki_name(e.url)}] {e.title}\n{t}" for i, (e, t) in enumerate(docs, 1))
    prompt = PROMPT.format(term=term.canonical, definition=meaning.definition or "(없음)", origin=meaning.origin or "(없음)",
                           nuance=meaning.nuance or "(없음)", docs=lines)
    if model == "audit":                    # 파이프라인의 감사관 — config.AUDIT_MODEL, AUDIT_OLLAMA_HOST(다른 GPU 서버 가능)
        from ..config import AUDIT_MODEL, AUDIT_OLLAMA_HOST
        from ..interpreters import local_chat

        c = local_chat.structured(prompt, AuditCheck, temperature=temperature, model=AUDIT_MODEL, host=AUDIT_OLLAMA_HOST or None)
        return (c if isinstance(c, AuditCheck) else AuditCheck.model_validate(c)), f"local:{AUDIT_MODEL}"
    if model.startswith("gemini"):          # "gemini" 은 기본 모델, "gemini:<모델 ID>" 는 그 모델(예: gemini:gemini-3.5-flash-lite)
        from .gemini import structured

        parsed, used = structured(con, prompt, AuditCheck, prefer_gemini=True, model=model.split(":", 1)[1] if ":" in model else None)
        if not str(used).startswith("gemini"):
            raise RuntimeError(f"Gemini 대신 {used} 가 답했다 — 예산·한도 확인")
        return (parsed if isinstance(parsed, AuditCheck) else AuditCheck.model_validate(parsed)), used
    return local_llm.structured(prompt, AuditCheck, temperature=temperature), "local"


def check_simple(con: Connection, term: Term, meaning: Meaning, docs: list[tuple[Evidence, str]], model: str = "local") -> tuple[str, str, str]:
    """짧은 판정형(파인튜닝한 감사관과 같은 형식). (verdict, reason, 쓴 모델)."""
    from . import crosscheck, local_llm

    lines = "\n\n".join(f"{i}. [{crosscheck.wiki_name(e.url)}] {e.title}\n{t}" for i, (e, t) in enumerate(docs, 1))
    prompt = SIMPLE_PROMPT.format(term=term.canonical, definition=meaning.definition or "(없음)", origin=meaning.origin or "(없음)",
                                  nuance=meaning.nuance or "(없음)", docs=lines)
    if model.startswith("gemini"):
        from .gemini import structured

        parsed, used = structured(con, prompt, AuditVerdict, prefer_gemini=True, model=model.split(":", 1)[1] if ":" in model else None)
        v = parsed if isinstance(parsed, AuditVerdict) else AuditVerdict.model_validate(parsed)
        return v.verdict, v.reason, used
    v = local_llm.structured(prompt, AuditVerdict)
    return v.verdict, v.reason, "local"


def check_voted(con: Connection, term: Term, meaning: Meaning, docs: list[tuple[Evidence, str]], model: str = "local", votes: int = 3):
    """같은 체크리스트를 votes 번(온도 0.5) 묻고 판정의 과반을 쓴다. (판정, 까닭들, 표 수)."""
    got = []
    for _ in range(votes):
        c, _used = check(con, term, meaning, docs, model=model, temperature=0.5)
        got.append(verdict(c))
    fixes = [w for v, w in got if v == "fix"]
    v = "fix" if len(fixes) * 2 > votes else "ok"
    return v, (fixes[0] if fixes and v == "fix" else []), f"{len(fixes)}/{votes}"



# ---------- 파이프라인 '감사' 단계 (2026-09-30) ----------
# 자동으로 실린 뜻(verified_auto)을 뜻 판마다 한 번 감사한다. '고칠 것' 이면 감사관의 까닭을 붙여 한 번 다시 쓰고 다시 감사한다.
# 그래도 '고칠 것' 이면 표시만 남긴다(audit_log.action='flagged') — 자동으로 내리지 않는다. 사람이 확인한 뜻은 감사하지 않는다.
# 감사관의 채점: 전수조사 32문제 정확도 0.66, 일괄 등재 20문제 0.70(정밀도 0.72·0.83, Plan 16).

AUDIT_PER_RUN = 20


def _ensure(con: Connection) -> None:
    con.execute("CREATE TABLE IF NOT EXISTS audit_log (term_id TEXT, meaning_id TEXT, checked_at TEXT, verdict TEXT, reasons_json TEXT, model TEXT, "
                "action TEXT, PRIMARY KEY(term_id, meaning_id))")
    con.commit()


def _log(con, term_id: str, meaning_id: str, verdict_: str, reasons: list[str], model: str, action: str) -> None:
    import json
    from datetime import datetime, timezone

    con.execute("INSERT OR REPLACE INTO audit_log VALUES (?,?,?,?,?,?,?)",
                (term_id, meaning_id, datetime.now(timezone.utc).isoformat(), verdict_, json.dumps(reasons, ensure_ascii=False), model, action))
    con.commit()


def ds_current(con: Connection, term: Term) -> str:
    """지금 뜻 판의 id (감사 실패도 판마다 한 번만 적게)."""
    from ..storage import dictionary_store as ds

    m = ds.current_meaning(con, term.term_id)
    return m.meaning_id if m else ""


def targets(con: Connection, limit: int = AUDIT_PER_RUN) -> list[Term]:
    """아직 감사하지 않은 자동 확인 뜻 — 위키 분류에서 일괄로 들어온 것과 새것부터."""
    from ..storage import dictionary_store as ds

    _ensure(con)
    done = set(con.execute("SELECT term_id, meaning_id FROM audit_log").fetchall())
    cat = {r[0] for r in con.execute("SELECT DISTINCT term_id FROM wiki_catalog").fetchall()}
    rows = []
    for t in ds.list_terms(con, ("verified",)):
        m = ds.current_meaning(con, t.term_id)
        if m and m.verification == "verified_auto" and (t.term_id, m.meaning_id) not in done:
            rows.append((t.term_id not in cat, -m.valid_from.timestamp(), t))
    return [t for *_, t in sorted(rows, key=lambda x: (x[0], x[1]))][:limit]


def audit_one(con: Connection, term: Term) -> str:
    """한 말을 감사한다. 돌려주는 것: ok · fixed(다시 써서 통과) · flagged(다시 써도 고칠 것) · no_doc · error."""
    from ..storage import dictionary_store as ds
    from . import research

    m = ds.current_meaning(con, term.term_id)
    docs = documents(term, ds.list_evidences(con, term.term_id))
    if not docs:
        _log(con, term.term_id, m.meaning_id, "no_doc", [], "", "no_doc")
        return "no_doc"
    c, used = check(con, term, m, docs, model="audit")
    v, why = verdict(c)
    if v == "ok":
        _log(con, term.term_id, m.meaning_id, "ok", [], used, "ok")
        return "ok"
    # 다시 쓴다 — 감사관의 까닭과 문서 글(메모리에서만)을 조사 모델에게 보인다
    sents = [x.strip() for e, t in docs for x in t.replace("\n", " ").split(". ") if len(x.strip()) > 10][:6]
    research.WIKI_CONTEXT[term.canonical] = [f"(감사관이 지난 뜻에서 지적한 것) {w}" for w in why] + sents
    try:
        research.research_one(con, term, lean=True)
    except Exception:
        research.WIKI_CONTEXT.pop(term.canonical, None)
        _log(con, term.term_id, m.meaning_id, "fix", why, used, "error")
        return "error"
    m2 = ds.current_meaning(con, term.term_id)
    if not m2 or m2.meaning_id == m.meaning_id:
        _log(con, term.term_id, m.meaning_id, "fix", why, used, "flagged")
        return "flagged"
    c2, _ = check(con, term, m2, docs, model="audit")
    v2, why2 = verdict(c2)
    _log(con, term.term_id, m.meaning_id, "fix", why, used, "rewritten")
    _log(con, term.term_id, m2.meaning_id, v2, why2, used, "ok" if v2 == "ok" else "flagged")
    return "fixed" if v2 == "ok" else "flagged"


def run(con: Connection) -> dict:
    from collections import Counter

    from ..config import AUDIT_MODEL, AUDIT_OLLAMA_HOST
    from ..interpreters import local_chat
    from .runs import stage

    with stage(con, "audit") as r:
        try:
            if local_chat.gpu_gateway.configured():
                names = {AUDIT_MODEL} if local_chat.gpu_gateway.available(AUDIT_MODEL) else set()
            else:
                names = {x.model for x in local_chat._client(AUDIT_OLLAMA_HOST or None).list().models}
        except Exception:
            names = set()
        if AUDIT_MODEL not in names:
            r.status, r.note = "skipped", f"감사관 모델 없음({AUDIT_MODEL})"
        else:
            counts: Counter = Counter()
            for t in targets(con):
                try:
                    counts[audit_one(con, t)] += 1
                except Exception as e:           # 한 말의 형식 실패가 나머지를 막지 않는다
                    counts["error"] += 1
                    r.note += f"{t.canonical}:{type(e).__name__} "
                r.count += 1
            r.detail = dict(counts)
    return {"audit": r}
