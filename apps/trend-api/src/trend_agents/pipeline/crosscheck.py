"""문서 대조(Plan 12) — 확인된 사전 항목을 참고 위키와 맞춰 본다. 판정은 데이터, 모델은 서술.

- '문서 없음' 만 규칙이 정한다: 저장된 근거와 새로 찾은 문서 가운데 표제어가 든 참고 문서(verification.reference_doc)가 없으면.
- 일치·고칠 것·위키끼리 다름·밈이 아님은 로컬 Gemma 가 사전 뜻과 문서 발췌를 나란히 보고 **제안**할 뿐이다. 상태·뜻은 바꾸지 않고
  고칠 것 → 고칠 안(correction), 위키끼리 다름 → 문서마다의 설명(conflict), 밈이 아님 → 사전에서 뺄지(retire) 로 검수 큐에 올린다.
  제안이 올라와 있는 동안 항목은 공개된 그대로다. 사람이 승인해야 새 판이 생기거나 빠진다(api.app._decide_proposal).
- 사람이 승인한 뜻(verified_human)도 대조하되 제안은 큐로만 간다. 사람이 보고 있는 제안이 있는 말은 건너뛴다.
- 문서 본문은 저장하지 않는다. 짧은 발췌·링크만 wiki 근거로, 대조 기록(crosscheck_log)에는 판정·문서 주소·모델만.

같은 규칙을 한 번 쓰는 스크립트(scripts/crosscheck_dictionary.py: 문서 모으기·전수조사 결과 가져오기·로컬 Gemma 판정)와
파이프라인 단계(run, research 다음)가 함께 쓴다.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import unquote, urlsplit

from pydantic import BaseModel, Field

from ..schemas import CrosscheckJudgement, Evidence, Meaning, MeaningDraft, MeaningFix, Term
from ..storage import dictionary_store as ds
from ..storage.db import Connection
from ..verification import REFERENCE_DOMAINS, anchor_hit, reference_doc
from .match import mentions
from .runs import stage

MAX_PER_RUN = 8          # 실행마다 대조하는 말 — 로컬 Gemma 판정 한 번이 수십 초라 한 바퀴의 시간을 묶는다
MAX_NAMU_PROBES = 20     # '나무위키 문서가 고쳐졌나' 를 물어보는 수(하루 캐시·2초 간격)
MAX_DOCS = 6             # 판정에 보이는 문서 수
UNJUDGED = "unjudged"    # 문서는 있는데 로컬 모델이 없어 판정하지 못함 — 모델이 생기면 다시 본다
ERROR = "error"          # 로컬 모델이 형식을 못 맞췄다 — RETRY_DAYS 뒤에 다시 본다(실행마다 같은 말이 칸을 차지하지 않게)
# '문서 없음' 도 RETRY_DAYS 뒤에 다시 본다. 수집기는 '없다' 와 '닿지 못했다'(위키백과 429 등)를 가르지 않아서 한 번의 실패가
# '문서 없음' 으로 남을 수 있고, 새 밈은 나중에 문서가 생긴다(2026-09-29 실측: ja.wikipedia 429 로 推し活 이 문서 없음).
RETRY_DAYS = 7
Verdict = Literal["keep", "fix", "conflict", "no_doc", "not_a_meme"]
KIND_OF = {"fix": "correction", "conflict": "conflict", "not_a_meme": "retire"}
LABEL = {"keep": "일치", "fix": "고칠 것", "conflict": "위키끼리 다름", "no_doc": "문서 없음", "not_a_meme": "밈이 아님", UNJUDGED: "판정 안 함",
         ERROR: "판정 실패"}
WIKI_NAME = {"namu.wiki": "나무위키", "wikipedia.org": "위키백과", "knowyourmeme.com": "Know Your Meme", "dic.pixiv.net": "pixiv 백과사전",
             "zh.moegirl.org.cn": "萌娘百科"}
HANGUL = re.compile(r"[가-힣]")


# ---------- 참고 문서 ----------

def reference_domain(url: str) -> str | None:
    """참고 문서 도메인(verification.REFERENCE_DOMAINS 가운데 하나). ko.wikipedia.org 는 wikipedia.org — 언어판이 달라도 한 출처다."""
    host = (urlsplit(url or "").hostname or "").lower()
    return next((d for d in REFERENCE_DOMAINS if host == d or host.endswith("." + d)), None)


def wiki_name(url: str) -> str:
    d = reference_domain(url)
    if d == "wikipedia.org":
        lang = (urlsplit(url).hostname or "").split(".")[0]
        return f"위키백과({lang})" if lang and lang not in ("www", "wikipedia") else "위키백과"
    return WIKI_NAME.get(d or "", urlsplit(url or "").hostname or url)


def sources(term: Term) -> list[str]:
    """Plan 12 §1 의 찾는 곳(순서대로): 'namu' · 'wiki:<언어>' · 'kym'. 萌娘百科는 수집기가 없어 아직 찾지 않는다.
    Know Your Meme 은 켜져 있을 때만(KNOWYOURMEME_ENABLED, 이용 약관 검토 전까지 기본 꺼짐)."""
    from ..collectors import knowyourmeme

    if term.lang == "ko":
        out = ["namu", "wiki:ko"]
    elif term.lang == "ja":
        out = ["wiki:ja", "kym"] + (["namu"] if any(HANGUL.search(a) for a in term.aliases) else [])
    elif term.lang == "en":
        out = ["kym", "wiki:en"]
    else:
        out = list(dict.fromkeys([f"wiki:{term.lang}", "wiki:en", "kym"]))
    return out if knowyourmeme.enabled() else [s for s in out if s != "kym"]


def gather(term: Term) -> list[Evidence]:
    """참고 위키에서 표제어가 든 문서를 찾는다(수집기마다 한 쪽). 네트워크가 실패한 곳은 건너뛴다."""
    from ..collectors import knowyourmeme, namuwiki
    from .research import wikipedia_doc

    out: list[Evidence] = []
    for src in sources(term):
        try:
            if src == "namu":
                names = [term.canonical] if term.lang == "ko" else []
                names += [a for a in term.aliases if HANGUL.search(a)]
                for name in list(dict.fromkeys(names))[:2]:
                    got = namuwiki.lookup(name)
                    if got:
                        out += got
                        break
            elif src == "kym":
                out += knowyourmeme.lookup(term.canonical, term.aliases)
            else:
                e, _ = wikipedia_doc(term.canonical, src.split(":", 1)[1])
                if e:
                    out.append(e)
        except Exception:
            continue
    return out


def documents(term: Term, evidences: list[Evidence]) -> list[Evidence]:
    """표제어(또는 별칭)가 든 참고 문서만, 주소마다 한 쪽. '문서 없음' 은 이것이 빈 것이다 — 규칙이 정한다."""
    seen: set[str] = set()
    out: list[Evidence] = []
    for e in evidences:
        if reference_doc(e) and anchor_hit(term.canonical, e, term.aliases) and e.url not in seen:
            seen.add(e.url)
            out.append(e)
    return out


def doc_entry(e: Evidence, summary: str | None = None, proposal: MeaningDraft | None = None) -> dict:
    """검수 큐의 docs_json 한 줄 — 위키 이름·주소·짧은 발췌(또는 요약)·고칠 안."""
    return {"wiki": wiki_name(e.url), "url": e.url, "summary": (e.excerpt if summary is None else summary)[:240],
            "proposal": proposal.model_dump() if proposal else None}


EXCERPT_MAX = 200


def clip(text: str, names: list[str] | tuple[str, ...], limit: int = EXCERPT_MAX) -> str:
    """limit 자 안으로 — 표제어(또는 별칭)가 처음 나오는 곳을 앞쪽에 두고 자른다. 앞에서부터 자르면 정작 그 말이 잘려 나간다."""
    from .match import term_pattern

    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    hits = [m.start() for m in (term_pattern(n).search(text) for n in names if n and n.strip()) if m]
    at = min(hits, default=0)
    span = limit - 2                                 # 앞뒤 말줄임표 자리
    start = max(0, min(at - span // 4, len(text) - span))
    return ("…" if start else "") + text[start:start + span] + ("…" if start + span < len(text) else "")


def excerpt_evidence(term: Term, url: str, title: str, text: str) -> tuple[Evidence | None, str]:
    """전수조사가 준 발췌를 wiki 근거로 — 주소가 참고 문서 도메인의 문서이고(verification.reference_doc) 발췌에 표제어가 있을 때만(match.mentions).
    본문은 두지 않는다: 표제어를 앞쪽에 두고 200자 안으로 자른다. Know Your Meme 은 켜져 있을 때만, 그리고 발췌 없이 주소·제목만
    (이용 약관, collectors/knowyourmeme.py). 돌려주는 것: (근거 또는 None, 받지 않은 까닭)."""
    from ..collectors import knowyourmeme

    domain = reference_domain(url)
    if not domain:
        return None, "참고 문서가 아님"
    kym = domain == "knowyourmeme.com"
    if kym and not knowyourmeme.enabled():
        return None, "Know Your Meme 은 꺼져 있음(KNOWYOURMEME_ENABLED)"
    if not mentions(text or "", term.canonical, term.aliases):
        return None, "발췌에 표제어가 없음"
    e = Evidence(evidence_id=ds.new_id("e", f"{url}|{term.canonical}"), kind="wiki", url=url,
                 title=_doc_title(domain, title or unquote(urlsplit(url).path.rsplit("/", 1)[-1])), source_domain=domain,
                 observed_at=datetime.now(timezone.utc), excerpt="" if kym else clip(text, [term.canonical, *term.aliases]))
    if not reference_doc(e):
        return None, "문서 주소가 아님"
    if not anchor_hit(term.canonical, e, term.aliases):
        return None, "남길 제목·발췌에 표제어가 없음"
    return e, ""


def _doc_title(domain: str, title: str) -> str:
    """수집기와 같은 제목 꼴 — 나무위키는 라이선스를 함께 적는다(collectors/namuwiki.py)."""
    title = re.sub(r"\s+", " ", title or "").strip()
    if domain == "namu.wiki":
        return f"나무위키: {title} (CC BY-NC-SA 2.0 KR)"[:200]
    if domain == "knowyourmeme.com":
        return f"Know Your Meme: {title}"[:200]
    return title[:200]


# ---------- 제안 ----------

def merged(current: Meaning | None, fix) -> MeaningDraft | None:
    """고칠 안(뜻·유래·뉘앙스)을 지금 실린 뜻 위에 얹는다 — 풀이·세대·나라·자기확신은 그대로. 바뀌는 칸이 없으면 None."""
    if current is None or fix is None:
        return None
    f = fix.model_dump() if isinstance(fix, BaseModel) else dict(fix)
    update = {k: str(f.get(k) or "").strip() for k in ("definition", "origin", "nuance")}
    update = {k: v for k, v in update.items() if v}
    base = MeaningDraft.model_validate(current.model_dump(include=set(MeaningDraft.model_fields)))
    draft = base.model_copy(update=update)
    return draft if update and draft != base else None


def reasons_for(verdict: str, problems: list[str], urls: list[str]) -> list[str]:
    """검수 화면의 사유 — 판정 이름, 문서와 다른 점, 참고 문서 주소(Plan 12 §3)."""
    return [f"문서 대조: {LABEL.get(verdict, verdict)}", *[p.strip() for p in problems if p and p.strip()],
            *[f"참고 문서: {u}" for u in dict.fromkeys(urls) if u]]


def propose(con: Connection, term: Term, verdict: str, reasons: list[str], *, draft: MeaningDraft | None = None,
            docs: list[dict] | None = None) -> str:
    """제안 하나를 검수 큐에 올린다. 상태·뜻은 바꾸지 않는다. 돌려주는 값: queued · pending(이미 사람이 볼 제안이 있음) ·
    not_listed(확인된 항목이 아님) · no_fix(고칠 안이 없거나 지금 뜻과 같음)."""
    kind = KIND_OF[verdict]
    stored = ds.get_term(con, term.term_id)
    if not stored or stored.status != "verified":
        return "not_listed"
    if ds.pending_review(con, term.term_id):
        return "pending"
    if kind == "correction" and draft is None:
        return "no_fix"
    ds.queue_review(con, term.term_id, draft if kind == "correction" else None, reasons,
                    len(ds.list_evidences(con, term.term_id)), kind=kind, docs=docs or None)
    return "queued"


# ---------- 로컬 Gemma 판정 (제안만) ----------

JUDGE_PROMPT = """사전 항목 '{term}' 의 뜻을 참고 문서 발췌와 맞춰 보라. 문서에 적힌 것만 근거로 삼고, 문서에 없는 사실은 만들지 마라.
이것은 제안일 뿐이고 사전을 바꾸는 것은 사람이다.

사전에 실린 뜻:
- 뜻: {definition}
- 유래: {origin}
- 뉘앙스: {nuance}

참고 문서 발췌 (번호. 문서 — 발췌):
{docs}

verdict 는 넷 가운데 하나다.
- keep: 사전의 뜻·유래가 문서와 맞다. 표현이 달라도 뜻이 같으면 keep 이다.
- fix: 문서는 이 표현을 다루는데 사전의 뜻이나 유래가 문서와 다르거나 중요한 것이 빠졌다. proposal 에 고친 뜻·유래·뉘앙스를 한국어로 쓴다(바꿀 필요가 없는 칸은 빈 문자열).
- conflict: 문서들끼리 서로 다른 뜻이나 유래를 적었다. readings 에 문서 번호마다 그 문서가 적은 것을 한 문장으로 쓰고, 그 문서대로 고친 안이 있으면 proposal 에 쓴다.
- not_a_meme: 문서가 유행어·밈이 아니라 인물·작품·상품·일반 낱말을 다룬다.
reason 은 한국어 한두 문장으로, 무엇이 맞거나 다른지 문서 번호를 들어 쓴다."""


def judge(term: Term, meaning: Meaning | None, docs: list[Evidence]) -> tuple[CrosscheckJudgement, str]:
    """로컬 Gemma 에게 판정 이름·이유·고칠 안을 묻는다(스키마는 프롬프트에, interpreters/local_chat). Gemini 는 쓰지 않는다."""
    from ..config import GEMMA_LOCAL_MODEL
    from . import local_llm

    m = meaning
    lines = "\n".join(f"{i}. {wiki_name(e.url)} {e.title} — {e.excerpt}" for i, e in enumerate(docs[:MAX_DOCS], 1))
    prompt = JUDGE_PROMPT.format(term=term.canonical, definition=(m.definition if m else "") or "(없음)", origin=(m.origin if m else "") or "(없음)",
                                 nuance=(m.nuance if m else "") or "(없음)", docs=lines)
    return local_llm.structured(prompt, CrosscheckJudgement), f"local:{GEMMA_LOCAL_MODEL}"


def from_judgement(term: Term, meaning: Meaning | None, j: CrosscheckJudgement, docs: list[Evidence]) -> tuple[list[str], MeaningDraft | None, list[dict]]:
    """모델의 제안을 검수 큐의 모양(사유·고칠 안·문서들)으로. 고칠 안은 지금 뜻 위에 얹는다."""
    shown = docs[:MAX_DOCS]
    reasons = reasons_for(j.verdict, [j.reason], [e.url for e in shown])
    if j.verdict == "conflict":
        entries = []
        for r in j.readings:
            if 1 <= r.i <= len(shown):
                entries.append(doc_entry(shown[r.i - 1], r.summary or None, merged(meaning, r.proposal)))
        return reasons, None, entries or [doc_entry(e) for e in shown]
    return reasons, merged(meaning, j.proposal) if j.verdict == "fix" else None, [doc_entry(e) for e in shown]


# ---------- 한 말 대조 ----------

def check(con: Connection, term: Term, *, judging: bool, store: bool = True, queue: bool = True, log: bool = True) -> dict:
    """한 말을 대조한다. 참고 문서를 모으고(store 면 표제어가 든 문서를 wiki 근거로 더한다 — 짧은 발췌·링크뿐), '문서 없음' 은 규칙이 정하고,
    judging 이면 로컬 Gemma 의 제안을 받아 queue 면 검수 큐에 올린다. 상태·뜻은 바꾸지 않는다.
    돌려주는 것: {verdict, docs: [주소], queued: 결과 또는 None, model, reason, draft}"""
    stored = ds.list_evidences(con, term.term_id)
    found = gather(term)
    docs = documents(term, stored + found)
    if store:
        ds.add_evidences(con, term.term_id, [e for e in found if e in docs])
    urls = [e.url for e in docs]
    queued, reason, draft = None, "", None
    if not docs:
        verdict, model = "no_doc", "rule"
    elif not judging:
        verdict, model = UNJUDGED, ""
    else:
        meaning = ds.current_meaning(con, term.term_id)
        try:
            j, model = judge(term, meaning, docs)
        except Exception:
            if log:
                ds.log_crosscheck(con, term.term_id, ERROR, urls, "local")
            raise
        verdict, reason = j.verdict, j.reason
        if verdict in KIND_OF:
            reasons, draft, entries = from_judgement(term, meaning, j, docs)
            if queue:
                queued = propose(con, term, verdict, reasons, draft=draft, docs=entries)
    if log:
        ds.log_crosscheck(con, term.term_id, verdict, urls, model)
    return {"verdict": verdict, "docs": urls, "queued": queued, "model": model, "reason": reason, "draft": draft}


def _changed(con: Connection, term: Term, prev: dict, probe: bool) -> bool:
    """마지막 대조 뒤 참고 문서가 바뀌었나 — 그때 보지 못한 참고 문서 근거가 생겼거나(조사가 새 문서를 찾음),
    나무위키 문서가 그 뒤에 고쳐졌다(probe 일 때만 묻는다, 하루 캐시)."""
    if any(e.url not in prev["urls"] for e in documents(term, ds.list_evidences(con, term.term_id))):
        return True
    if probe and (term.lang == "ko" or any(HANGUL.search(a) for a in term.aliases)):
        from ..collectors import namuwiki

        name = term.canonical if term.lang == "ko" else next(a for a in term.aliases if HANGUL.search(a))
        ev = namuwiki.lookup(name)
        at = prev["checked_at"].replace(tzinfo=prev["checked_at"].tzinfo or timezone.utc)
        return bool(ev and ev[0].observed_at > at)
    return False


def targets(con: Connection, limit: int = MAX_PER_RUN, judging: bool = False) -> list[Term]:
    """대조할 말: 확인된 말 가운데 (1) 한 번도 대조하지 않은 것 — 로컬 모델이 있으면 문서만 보고 판정하지 못한 것도,
    판정 실패·문서 없음은 RETRY_DAYS 가 지난 것, (2) 마지막 대조 뒤 참고 문서가 바뀐 것(오래전에 본 것부터).
    사람이 보고 있는 제안이 있는 말은 건너뛴다."""
    last = ds.last_crosschecks(con)
    now = datetime.now(timezone.utc)
    fresh: list[tuple[int, Term]] = []
    seen: list[tuple[datetime, Term]] = []
    for t in ds.list_terms(con, ("verified",)):
        if ds.pending_review(con, t.term_id):
            continue
        prev = last.get(t.term_id)
        at = prev["checked_at"].replace(tzinfo=prev["checked_at"].tzinfo or timezone.utc) if prev else None
        if prev is None:
            fresh.append((0, t))
        elif judging and prev["verdict"] == UNJUDGED:
            fresh.append((1, t))
        elif judging and prev["verdict"] == ERROR and (now - at).days >= RETRY_DAYS:
            fresh.append((2, t))
        elif prev["verdict"] == "no_doc" and (now - at).days >= RETRY_DAYS:
            fresh.append((3, t))
        else:
            seen.append((at, t))
    out = [t for _, t in sorted(fresh, key=lambda x: x[0])][:limit]
    probes = 0
    for _, t in sorted(seen, key=lambda x: x[0]):
        if len(out) >= limit:
            break
        probe = (t.lang == "ko" or any(HANGUL.search(a) for a in t.aliases)) and probes < MAX_NAMU_PROBES
        probes += probe
        if _changed(con, t, last[t.term_id], probe):
            out.append(t)
    return out


def run(con: Connection, limit: int = MAX_PER_RUN) -> dict:
    """파이프라인 '문서 대조' 단계(research 다음). 모델이 없는 기본 개발 환경에서는 '문서 없음' 만 판정하고 모델을 부르지 않는다."""
    from .gemini import local_ok

    with stage(con, "crosscheck") as r:
        judging = local_ok()
        counts: Counter = Counter()
        for t in targets(con, limit, judging):
            try:
                res = check(con, t, judging=judging)
            except Exception as e:           # 한 말의 실패(모델 형식·네트워크)가 나머지를 막지 않는다
                r.note += f"{t.canonical}:{type(e).__name__} "
                continue
            counts[res["verdict"]] += 1
            r.detail[t.canonical] = LABEL.get(res["verdict"], res["verdict"]) + (f" → {res['queued']}" if res["queued"] else "")
            r.count += 1
        r.detail["판정"] = dict(counts)
        if not judging and r.count:
            r.note = (r.note + " " if r.note else "") + "로컬 모델 없음 — 문서 없음만 판정"
    return {"crosscheck": r}


# ---------- 전수조사 결과 가져오기 (scripts/crosscheck_dictionary.py import) ----------

class AuditAlternative(BaseModel):
    wiki: str = ""
    url: str
    summary: str = ""
    proposal: MeaningFix | None = None


class AuditExcerpt(BaseModel):
    url: str
    title: str = ""
    text: str


class AuditRecord(BaseModel):
    """밖에서 만든 판정 한 줄(Plan 12 전수조사). 목록(JSON 배열)으로 받는다."""

    term_id: str
    verdict: Verdict
    problems: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    proposal: MeaningFix | None = None
    alternatives: list[AuditAlternative] = Field(default_factory=list)
    excerpt: AuditExcerpt | None = None


def import_audit(con: Connection, records: list[AuditRecord], *, queue: bool = False, store_evidence: bool = False,
                 model: str = "import") -> dict:
    """전수조사 결과를 가져온다. 기본은 보고만 — 판정별 건수와 검수 큐에 올릴 것을 돌려준다.
    queue: fix → correction, conflict → conflict, not_a_meme → retire 로 검수 큐에 (사유에 판정 이름과 문서 주소). 일치는 기록만.
    store_evidence: 발췌를 wiki 근거로 — 참고 문서의 문서 주소이고 표제어가 든 발췌만.
    '문서 없음' 은 아무것도 바꾸지 않고 목록에만 싣는다(사용자가 먼저 확인한다). 다시 돌려도 근거·대기 제안이 겹치지 않는다 —
    이미 대기 중인 제안이 있는 말은 건너뛰고 보고한다. 사람이 승인한 뜻도 제안은 큐로만 간다(덮지 않는다)."""
    out: dict = {"counts": Counter(), "queued": [], "would_queue": [], "no_doc": [], "skipped": [], "evidence": [], "evidence_skipped": []}
    last = ds.last_crosschecks(con) if queue else {}
    for rec in records:
        t = ds.get_term(con, rec.term_id)
        if not t:
            out["skipped"].append((rec.term_id, "사전에 없는 항목"))
            continue
        out["counts"][rec.verdict] += 1
        if rec.verdict == "no_doc":
            out["no_doc"].append(t.canonical)
            continue
        if store_evidence and rec.excerpt:
            e, why = excerpt_evidence(t, rec.excerpt.url, rec.excerpt.title, rec.excerpt.text)
            if e is None:
                out["evidence_skipped"].append((t.canonical, rec.excerpt.url, why))
            elif ds.add_evidences(con, t.term_id, [e]):
                out["evidence"].append((t.canonical, e.url))
        urls = list(dict.fromkeys([*rec.sources, *[a.url for a in rec.alternatives]]))
        prev = last.get(t.term_id)
        fresh_log = queue and not (prev and prev["verdict"] == rec.verdict and prev["model"] == model)
        if rec.verdict == "keep":
            if fresh_log:
                ds.log_crosscheck(con, t.term_id, "keep", urls, model)
            continue
        kind = KIND_OF[rec.verdict]
        if t.status != "verified":
            out["skipped"].append((t.canonical, f"확인된 항목이 아님({t.status})"))
            continue
        if ds.pending_review(con, t.term_id):
            out["skipped"].append((t.canonical, "이미 검수 대기 중인 제안이 있음"))
            continue
        current = ds.current_meaning(con, t.term_id)
        draft = merged(current, rec.proposal) if rec.verdict == "fix" else None
        if rec.verdict == "fix" and draft is None:
            out["skipped"].append((t.canonical, "고칠 안이 없거나 지금 뜻과 같음"))
            continue
        if rec.verdict == "conflict":
            docs = [{"wiki": a.wiki or wiki_name(a.url), "url": a.url, "summary": a.summary[:240],
                     "proposal": (p.model_dump() if (p := merged(current, a.proposal)) else None)} for a in rec.alternatives]
        else:
            docs = [{"wiki": wiki_name(u), "url": u, "summary": "", "proposal": None} for u in rec.sources]
        reasons = reasons_for(rec.verdict, rec.problems, urls)
        if not queue:
            out["would_queue"].append((t.canonical, kind, reasons[1] if len(reasons) > 1 else reasons[0]))
            continue
        result = propose(con, t, rec.verdict, reasons, draft=draft, docs=docs)
        if result == "queued":
            out["queued"].append((t.canonical, kind, reasons[1] if len(reasons) > 1 else reasons[0]))
            if fresh_log:
                ds.log_crosscheck(con, t.term_id, rec.verdict, urls, model)
        else:
            out["skipped"].append((t.canonical, result))
    return out
