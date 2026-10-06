"""문서 색인 (2026-10-06). 사전·조사 에이전트·챗봇이 '그 자리에서 웹을 긁지 않고' 미리 모아 둔 위키 본문에서 찾는다.

무엇을: 사전 표제어의 참고 문서(evidences)와 위키 밈 분류(wiki_catalog)에 든 문서 — 나무위키·위키백과(여러 언어)·Fandom(PTT·홍콩)·Trend A Word.
어떻게: 본문을 절·조각(약 700자)으로 나눠 bge-m3 로 임베딩하고 sqlite-vec 로 찾는다. 색인은 data/index.db 하나(수집 DB 와 따로).
얼마나 자주: 하루 두 번(scripts/index_update.py). 위키백과는 판 번호로 바뀐 문서만, 나무위키는 오래 안 본 문서부터 한 번에 정한 수만큼
(요청 간격 3초 — 전부 다시 받으면 4시간이 넘는다). 처음 보는 문서·새 표제어의 문서가 먼저다.

나무위키 본문(CC BY-NC-SA)도 저장한다(2026-10-06 사용자 결정): 색인은 이 서버 안에서 답변·에이전트가 근거를 찾는 데에만 쓰고,
화면·API 응답에는 지금처럼 짧은 발췌와 문서 주소만 내보낸다. 찾은 조각에는 늘 문서 주소가 붙어 출처를 밝힌다.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from . import web_tools as W

INDEX_PATH = Path(os.getenv("INDEX_PATH", str(Path(__file__).resolve().parents[3] / "data" / "index.db")))
EMBED_MODEL = os.getenv("INDEX_EMBED_MODEL", "bge-m3")
DIM = 1024
SIZE, OVERLAP = 700, 120

DDL = f"""
CREATE TABLE IF NOT EXISTS docs (url TEXT PRIMARY KEY, site TEXT, lang TEXT, title TEXT, rev TEXT, text_hash TEXT,
  fetched_at TEXT, checked_at TEXT, n_chunks INT, priority INT DEFAULT 0, error TEXT);
CREATE TABLE IF NOT EXISTS chunks (id INTEGER PRIMARY KEY, url TEXT, ord INT, heading TEXT, text TEXT);
CREATE INDEX IF NOT EXISTS chunks_url ON chunks(url);
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vec USING vec0(id INTEGER PRIMARY KEY, emb float[{DIM}] distance_metric=cosine);
"""


def connect(path: Path | str | None = None) -> Connection:
    import sqlite_vec

    p = Path(path or INDEX_PATH)
    if str(p) != ":memory:":
        p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p), check_same_thread=False, timeout=60)
    con.enable_load_extension(True)
    sqlite_vec.load(con)
    con.enable_load_extension(False)
    con.executescript(DDL)
    return con


def _hosts() -> list[str]:
    """임베딩할 Ollama — INDEX_EMBED_HOST, AUDIT_OLLAMA_HOST, 이 서버 순. 10-06 부터 23번 VRAM 을 반납해 둘 다 비워 두고 이 서버를 쓴다."""
    from ..config import AUDIT_OLLAMA_HOST

    return [h for h in dict.fromkeys([os.getenv("INDEX_EMBED_HOST", ""), AUDIT_OLLAMA_HOST, "http://127.0.0.1:11434"]) if h]


def embed(texts: list[str]) -> list[list[float]]:
    last: Exception | None = None
    for host in _hosts():
        try:
            out: list[list[float]] = []
            for i in range(0, len(texts), 64):
                r = httpx.post(f"{host}/api/embed", json={"model": EMBED_MODEL, "input": texts[i:i + 64]}, timeout=180)
                r.raise_for_status()
                out += r.json()["embeddings"]
            return out
        except Exception as e:      # 다음 호스트로
            last = e
    raise RuntimeError(f"임베딩 서버에 닿지 못함: {last}")


def site_of(url: str) -> tuple[str, str]:
    h = (urlsplit(url).hostname or "").lower()
    if h == "namu.wiki":
        return "namu", "ko"
    if h.endswith(".wikipedia.org"):
        return "wikipedia", h.split(".")[0]
    if h.endswith(".fandom.com"):
        return "fandom", "zh"
    if h == "maily.so":
        return "trendaword", "ko"
    return h, ""


# ── 무엇을 색인하나 ───────────────────────────────────────────────

def targets(trend: Connection) -> dict[str, int]:
    """{주소: 우선순위}. 확인된 표제어의 참고 문서 > 검수 대기 > 위키 밈 분류 목록."""
    out: dict[str, int] = {}
    q = ("SELECT DISTINCT e.url, t.status FROM evidences e JOIN terms t ON t.term_id = e.term_id "
         "WHERE t.status IN ('verified','needs_review') AND (e.url LIKE 'https://namu.wiki/w/%' OR e.url LIKE 'https://%.wikipedia.org/wiki/%' "
         "OR e.url LIKE 'https://%.fandom.com/wiki/%' OR e.url LIKE 'https://maily.so/trendaword/posts/%')")
    for url, status in trend.execute(q):
        u = W.canon(url.split("#")[0])
        if W.allowed(u):
            out[u] = max(out.get(u, 0), 2 if status == "verified" else 1)
    wiki = {"namu": "https://namu.wiki/w/{}", "pttpedia": "https://pttpedia.fandom.com/zh/wiki/{}", "evchk": "https://evchk.fandom.com/zh/wiki/{}"}
    for source, title in trend.execute("SELECT source, title FROM wiki_catalog"):
        if source.startswith("wiki-"):
            u = f"https://{source[5:]}.wikipedia.org/wiki/{title.replace(' ', '_')}"
        elif source in wiki:
            u = wiki[source].format(title)
        else:
            continue
        u = W.canon(u)
        if W.allowed(u):
            out.setdefault(u, 0)
    return out


# ── 조각 나누기 ───────────────────────────────────────────────────

_HEAD = re.compile(r"(?m)^\s*(?:(\d+(?:\.\d+)*\.\s[^\n\[]{1,60}?)\s*\[편집\]|§ ([^\n]{1,80}))\s*$")


def chunks_of(title: str, text: str) -> list[tuple[str, str]]:
    """[(절 이름, 조각)] — 절 경계에서 끊고, 긴 절은 SIZE 자씩(OVERLAP 겹침)."""
    parts: list[tuple[str, str]] = []
    pos, head = 0, ""
    for m in list(_HEAD.finditer(text)) + [None]:
        end = m.start() if m else len(text)
        body = re.sub(r"\n\s*\n+", "\n", text[pos:end]).strip()
        if len(body) >= 40:
            for i in range(0, len(body), SIZE - OVERLAP):
                piece = body[i:i + SIZE]
                if len(piece) >= 40:
                    parts.append((head, piece))
                if i + SIZE >= len(body):
                    break
        if m:
            head, pos = (m.group(1) or m.group(2) or "").strip(), m.end()
    return parts


# ── 받기·갱신 ─────────────────────────────────────────────────────

def _wiki_revs(urls: list[str]) -> dict[str, str]:
    """위키백과 문서들의 마지막 판 번호(50개씩 한 번에). 바뀐 문서만 다시 받으려고."""
    out: dict[str, str] = {}
    by_lang: dict[str, list[str]] = {}
    for u in urls:
        by_lang.setdefault(urlsplit(u).hostname.split(".")[0], []).append(u)
    for lang, us in by_lang.items():
        for i in range(0, len(us), 50):
            batch = us[i:i + 50]
            titles = {unquote(urlsplit(u).path[len("/wiki/"):]).replace("_", " "): u for u in batch}
            W._wait(f"{lang}.wikipedia.org")
            try:
                r = httpx.get(f"https://{lang}.wikipedia.org/w/api.php", params={"action": "query", "prop": "info", "titles": "|".join(titles),
                              "format": "json", "formatversion": "2"}, headers={"User-Agent": W.UA}, timeout=30)
                data = r.json().get("query", {})
            except Exception:
                continue
            norm = {n["to"]: n["from"] for n in data.get("normalized", [])}
            for p in data.get("pages", []):
                src = titles.get(norm.get(p.get("title"), p.get("title")))
                if src and "lastrevid" in p:
                    out[src] = str(p["lastrevid"])
    return out


def index_one(idx: Connection, url: str, rev: str = "") -> str:
    """문서 하나를 받아 조각·임베딩을 바꾼다. 돌려주는 것: new · updated · same · missing · error."""
    now = datetime.now(timezone.utc).isoformat()
    site, lang = site_of(url)
    page = W._fetch(url)
    if page is None:
        idx.execute("INSERT INTO docs(url, site, lang, checked_at, error) VALUES (?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET checked_at=excluded.checked_at, error=excluded.error",
                    (url, site, lang, now, "unreachable"))
        idx.commit()
        return "missing"
    title, text, _ = W._parse(url, page)
    if site == "namu":
        m = re.search(r"(20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d)", page)
        rev = rev or (m.group(1) if m else "")
    h = hashlib.sha1(text.encode()).hexdigest()
    old = idx.execute("SELECT text_hash FROM docs WHERE url=?", (url,)).fetchone()
    if old and old[0] == h:
        idx.execute("UPDATE docs SET checked_at=?, rev=?, error=NULL WHERE url=?", (now, rev, url))
        idx.commit()
        return "same"
    parts = chunks_of(title, text)
    vecs = embed([f"{title} > {hd}\n{tx}" if hd else f"{title}\n{tx}" for hd, tx in parts]) if parts else []
    ids = [r[0] for r in idx.execute("SELECT id FROM chunks WHERE url=?", (url,))]
    if ids:
        idx.executemany("DELETE FROM chunk_vec WHERE id=?", [(i,) for i in ids])
        idx.execute("DELETE FROM chunks WHERE url=?", (url,))
    import numpy as np

    for k, ((hd, tx), v) in enumerate(zip(parts, vecs)):
        cid = idx.execute("INSERT INTO chunks(url, ord, heading, text) VALUES (?,?,?,?)", (url, k, hd, tx)).lastrowid
        idx.execute("INSERT INTO chunk_vec(id, emb) VALUES (?,?)", (cid, np.asarray(v, dtype=np.float32).tobytes()))
    idx.execute("INSERT INTO docs(url, site, lang, title, rev, text_hash, fetched_at, checked_at, n_chunks, error) VALUES (?,?,?,?,?,?,?,?,?,NULL) "
                "ON CONFLICT(url) DO UPDATE SET title=excluded.title, rev=excluded.rev, text_hash=excluded.text_hash, fetched_at=excluded.fetched_at, "
                "checked_at=excluded.checked_at, n_chunks=excluded.n_chunks, error=NULL", (url, site, lang, title, rev, h, now, now, len(parts)))
    idx.commit()
    return "updated" if old else "new"


def update(idx: Connection, trend: Connection, namu_budget: int = 1200, other_budget: int = 3000,
           deadline: float | None = None, log=print) -> dict:
    """한 바퀴: 대상 목록을 맞추고, 위키백과는 판 번호가 바뀐 것·처음 보는 것만, 나무위키·그 밖은 처음 보는 것 → 오래 안 본 것 순으로 정한 수만큼."""
    tg = targets(trend)
    for u, p in tg.items():
        idx.execute("INSERT INTO docs(url, site, lang, priority) VALUES (?,?,?,?) ON CONFLICT(url) DO UPDATE SET priority=excluded.priority",
                    (u, *site_of(u), p))
    idx.commit()
    stats: dict[str, int] = {}
    rows = idx.execute("SELECT url, site, rev, checked_at FROM docs ORDER BY (checked_at IS NOT NULL), priority DESC, checked_at").fetchall()
    wiki = [r for r in rows if r[1] == "wikipedia"]
    revs = _wiki_revs([r[0] for r in wiki])
    queue = [(u, revs.get(u, "")) for u, _, rev, _ in wiki if revs.get(u) and revs.get(u) != rev][:other_budget]
    queue += [(u, "") for u, s, _, ch in rows if s in ("fandom", "trendaword") and ch is None][:max(0, other_budget - len(queue))]
    queue += [(u, "") for u, s, _, _ in rows if s == "namu"][:namu_budget]
    log(f"대상 {len(tg)} · 이번에 볼 문서 {len(queue)} (위키백과 바뀜·처음 {sum(1 for u, r in queue if r)})")
    for i, (u, rev) in enumerate(queue, 1):
        if deadline and time.time() > deadline:
            log("시간이 다 됐다 — 다음 바퀴에서 이어 간다")
            break
        try:
            r = index_one(idx, u, rev)
        except Exception as e:
            r = "error"
            idx.execute("UPDATE docs SET checked_at=?, error=? WHERE url=?", (datetime.now(timezone.utc).isoformat(), f"{type(e).__name__}"[:80], u))
            idx.commit()
        stats[r] = stats.get(r, 0) + 1
        if i % 100 == 0:
            log(f"  {i}/{len(queue)} {stats}")
    return stats


# ── 찾기 ──────────────────────────────────────────────────────────

_GENERIC = {"밈", "유행어", "유행", "대사", "장면", "이름", "뭐라고", "불러", "부르는", "알려줘", "있었다던데", "만든", "유행시킨", "나온",
            "때문에", "뜻의", "말은", "말이", "됐어", "유행한", "무슨", "가장", "어떤", "다던데"}


def _terms(query: str) -> list[str]:
    """낱말 검색에 쓸 말 — 따옴표 안의 말을 먼저, 그다음 조사를 뗀 낱말(두 글자 이상)."""
    from .match import keywords, strip_particle

    quoted = [q.strip(" !?.~") for q in re.findall(r"['\"‘“]([^'\"’”]{2,30})['\"’”]", query)]
    words = []
    for w in keywords(re.sub(r"['\"‘“’”]", " ", query)):
        w = strip_particle(w)[-1]
        if len(w) >= 2 and w not in _GENERIC:
            words.append(w)
    return list(dict.fromkeys([q for q in quoted if q] + words))[:10]


def _keyword_hits(idx: Connection, terms: list[str], limit: int) -> list[tuple[int, float, str]]:
    """[(조각 id, 점수, 처음 걸린 드문 말)] — 드문 말일수록 무겁게(문서 빈도의 역수)."""
    total = max(1, idx.execute("SELECT count(*) FROM chunks").fetchone()[0])
    score: dict[int, float] = {}
    first: dict[int, tuple[float, str]] = {}
    for t in terms:
        ids = [r[0] for r in idx.execute("SELECT id FROM chunks WHERE text LIKE ? LIMIT 3000", (f"%{t}%",))]
        if not ids or len(ids) > total * 0.05:          # 조각 스무 개에 하나 넘게 나오는 말(작품 이름 등)은 가르지 못한다
            continue
        w = __import__("math").log(total / len(ids))
        for i in ids:
            score[i] = score.get(i, 0) + w
            if i not in first or w > first[i][0]:
                first[i] = (w, t)
    top = sorted(score.items(), key=lambda x: -x[1])[:limit]
    return [(i, sc, first[i][1]) for i, sc in top]


def _snippet(text: str, term: str | None, width: int = 230) -> str:
    i = text.find(term) if term else -1
    if i < 0:
        return text[:2 * width]
    a = max(0, i - width)
    return ("…" if a else "") + text[a:i + len(term) + width] + ("…" if i + len(term) + width < len(text) else "")


def search(idx: Connection, query: str, k: int = 8, lang: str | None = None, site: str | None = None) -> list[dict]:
    """뜻으로 찾기(임베딩)와 낱말로 찾기(드문 말일수록 무겁게)를 섞어(RRF) 가까운 조각들 — 문서 주소·제목·절·발췌.
    뜻으로만 찾으면 '친한 친구' 질문에 '깐부' 문단을 놓쳤고, 낱말로만 찾으면 설명으로 묻는 질문을 놓친다(10-06 시험)."""
    import numpy as np

    v = np.asarray(embed([query])[0], dtype=np.float32).tobytes()
    vec = [r[0] for r in idx.execute("SELECT id FROM chunk_vec WHERE emb MATCH ? AND k = ? ORDER BY distance", (v, 40))]
    terms = _terms(query)
    kw = _keyword_hits(idx, terms, 40)
    hit_term = {i: t for i, _, t in kw}
    rrf: dict[int, float] = {}
    for rank, i in enumerate(vec):
        rrf[i] = rrf.get(i, 0) + 1 / (60 + rank)
    for rank, (i, _, _) in enumerate(kw):
        rrf[i] = rrf.get(i, 0) + 1 / (60 + rank)
    out: list[dict] = []
    seen: dict[str, int] = {}
    shown: set[str] = set()
    for i, sc in sorted(rrf.items(), key=lambda x: -x[1]):
        row = idx.execute("SELECT c.url, c.heading, c.text, d.title, d.site, d.lang FROM chunks c JOIN docs d ON d.url = c.url WHERE c.id=?",
                          (i,)).fetchone()
        if not row:
            continue
        url, head, text, title, s, lg = row
        snip = _snippet(text, hit_term.get(i))
        if (lang and lg != lang) or (site and s != site) or seen.get(url, 0) >= 2 or snip[:120] in shown:
            continue
        seen[url] = seen.get(url, 0) + 1
        shown.add(snip[:120])
        out.append({"url": url, "title": title, "heading": head, "text": snip, "site": s, "lang": lg,
                    "score": round(sc, 4), "by": "+".join(x for x, ok in (("뜻", i in vec), ("낱말", i in hit_term)) if ok)})
        if len(out) >= k:
            break
    return out


def stats(idx: Connection) -> dict:
    by = {s: (n, f, c) for s, n, f, c in idx.execute(
        "SELECT site, count(*), sum(fetched_at IS NOT NULL), sum(n_chunks) FROM docs GROUP BY site")}
    return {"docs": by, "chunks": idx.execute("SELECT count(*) FROM chunks").fetchone()[0]}
