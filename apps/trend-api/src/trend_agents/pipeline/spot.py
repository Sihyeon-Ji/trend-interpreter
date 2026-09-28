"""후보 발굴(spot). 최근 쇼츠 제목·커뮤니티 글·'해석 실패' 메시지에서 로컬 Gemma 가 '뜻을 찾아볼 표현'을 뽑는다.
모델은 제안만 한다: 표현이 원문 줄에 실재해야 하고(앵커), 후보 규칙상 두 번 이상 목격돼야 승격되며, 뜻은 게이트가 판정한다."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from collections import defaultdict

from ..schemas import ShortsVideo, SpottedTerm
from ..storage import dictionary_store as ds
from .gemini import BudgetExhausted, local_ok, structured
from .match import mentions
from .runs import stage
from ..storage.db import Connection

BATCH = 20
MIN_CONFIDENCE = 0.6
PROMPT = """You spot slang, memes, catchphrases, abbreviations and challenge names in short texts ({region_note}). For EACH numbered line return zero or more objects with the same "i".
Only expressions whose MEANING an outsider (another generation or country) would have to look up.
Skip: names of people, brands, products, places, shows, songs' artists; ordinary words; hashtags, handles, URLs; numbers and dates.
term: the expression exactly as written in the line (original script, no # or @). lang: ISO 639-1 of the term. kind: slang | meme | song | challenge | none. confidence 0-1.
If a line has nothing, return one object for it with kind "none". Return exactly one JSON list.

Lines:
{items}"""


def gather_lines(con: Connection, videos: int = 100, community: int = 60, lookups: int = 60) -> tuple[list[dict], list[str]]:
    """(줄 목록, 소비한 lookups 키). 줄: text·region·source."""
    lines: list[dict] = []
    since = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    for (j,) in con.execute("SELECT json FROM videos WHERE last_seen >= ? ORDER BY view_count DESC LIMIT ?", (since, videos)).fetchall():
        v = ShortsVideo.model_validate_json(j)
        lines.append({"text": v.title[:160], "region": v.region or "US", "source": "shorts"})
    for title, excerpt, term_id in con.execute(
        "SELECT json::jsonb->>'title', json::jsonb->>'excerpt', term_id FROM evidences "
        "WHERE kind='community' AND observed_at >= ? ORDER BY observed_at DESC LIMIT ?", (since, community)).fetchall():
        text = (excerpt or title or "")[:160]
        region = term_id.rsplit("|", 1)[-1] if term_id.startswith("q|") else "US"  # 급증 검색어 근거는 'q|검색어|나라', 용어 근거는 나라 정보가 없다
        if text:
            lines.append({"text": text, "region": region if len(region) == 2 else "US", "source": "community"})
    keys: list[str] = []
    for key, text, lang in ds.pending_lookups(con, lookups):
        lines.append({"text": text[:160], "region": "KR" if lang == "ko" else "US", "source": "lookup"})
        keys.append(key)
    seen: set[str] = set()
    out = []
    for ln in lines:
        k = ln["text"].strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(ln)
    return out, keys


def _prompt(chunk: list[dict]) -> str:
    regions = sorted({c["region"] for c in chunk})
    items = "\n".join(f'{i}. {c["text"]}' for i, c in enumerate(chunk))
    return PROMPT.format(region_note="regions " + ", ".join(regions), items=items)


def keep(p: SpottedTerm, line: str, existing) -> bool:
    """규칙 필터: 모델 제안 중 원문에 실재하고, 이름·태그·숫자가 아니고, 아직 사전에 없는 것만."""
    t = p.term.strip()
    if p.kind == "none" or p.confidence < MIN_CONFIDENCE or not (1 < len(t) <= 30) or len(t.split()) > 4:
        return False
    if any(ch in t for ch in "#@/") or t.replace(" ", "").replace("-", "").isdigit():
        return False
    if not mentions(line, t):
        return False  # 줄에 없는 표현 = 환각
    return not existing(t)


def run(con: Connection, max_batches: int = 8) -> dict:
    with stage(con, "spot") as r:
        if not local_ok():
            r.note = "로컬 Gemma 없음 — 발굴은 로컬 모델로만 (Gemini 예산 보호)"
            return {"spot": r}
        lines, keys = gather_lines(con)
        spotted: dict[tuple[str, str], dict] = defaultdict(lambda: {"count": 0, "regions": set(), "kind": "meme", "sample": ""})
        done = 0
        for b in range(0, min(len(lines), BATCH * max_batches), BATCH):
            chunk = lines[b:b + BATCH]
            try:
                parsed, _ = structured(con, _prompt(chunk), list[SpottedTerm])
            except BudgetExhausted as e:
                r.note = str(e)
                break
            except Exception as e:  # 한 배치의 파싱 실패가 나머지를 막지 않는다
                r.note += f"batch{b // BATCH}:{type(e).__name__} "
                continue
            done += len(chunk)
            for p in parsed or []:
                p = p if isinstance(p, SpottedTerm) else SpottedTerm.model_validate(p)
                if not (0 <= p.i < len(chunk)) or not keep(p, chunk[p.i]["text"], lambda t: ds.find_term(con, t)):
                    continue
                key = (p.term.strip().lower(), p.lang[:2].lower() or "en")
                s = spotted[key]
                s["count"] += 1
                s["regions"].add(chunk[p.i]["region"])
                s["kind"] = "song" if p.kind == "song" else "meme"  # 발굴 후보는 두 번 이상 보여야 승격 (kind=meme 규칙)
                s["sample"] = s["sample"] or p.term.strip()
        n = 0
        for (_, lang), s in spotted.items():
            for region in sorted(s["regions"]):  # 줄마다 한 번씩 → 같은 표현이 여러 줄에 나오면 count 가 오른다
                ds.upsert_candidate(con, s["sample"], lang, region, "spot", note=f"kind={s['kind']}; spot")
                n += 1
        ds.delete_lookups(con, keys)  # 사람이 쓴 문장은 소비 즉시 지운다
        r.count = n
        r.detail.update({"lines": len(lines), "labeled": done, "spotted": len(spotted), "lookups": len(keys)})
    return {"spot": r}
