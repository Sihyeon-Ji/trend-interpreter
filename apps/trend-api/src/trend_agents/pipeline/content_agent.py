"""콘텐츠 조사 에이전트 (2026-10-01). 콘텐츠 하나(예: 오징어 게임)에서 파생된 밈을 나라별로, 같은 밈끼리 짝지어 모은다.

Gemma 4 12B 가 도구(pipeline/web_tools)를 스스로 골라 쓴다 — 어느 문서를 열고, 어느 절을 읽고, 어느 링크를 따라갈지.
모델이 정하는 것은 탐색과 '찾은 밈' 의 서술뿐이고, 받을지는 규칙이 정한다(verify): 근거 페이지에 밈 이름이 실제로 있고,
그 페이지가 콘텐츠를 말하거나(콘텐츠 이름이 있음) Know Your Meme 의 그 갈래 항목('Part of a series on …')일 때만.
읽기(어디를 열지)와 뽑기(조각에서 밈 목록)는 따로 부른다 — 12B 가 한 걸음에 하나씩 기록하다 같은 것을 되풀이했다(10-01 실측).
나라 사이 같은 밈 짝은 끝에 모델이 제안하고(content_pairs), 근거 페이지끼리 서로의 이름·대사를 말할 때만 확인으로 둔다.
본문은 저장하지 않는다. 탐색 기록(agent_trace)과 결과(content_findings: 근거 문장 하나·주소)만 남긴다.
"""
from __future__ import annotations

import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from ..storage.db import Connection

from . import web_tools as W

MAX_STEPS = 30
QUOTES = re.compile(r"명대사|어록|대사|Quotes", re.I)       # 대사 목록 절 — 밈이 됐다는 말이 곁에 있는 대사만 받는다
CUE = re.compile(r"밈|유행|패러디|화제|짤|유행어|meme|viral|流行|ミーム|迷因", re.I)
CHAR_SUBPAGE = ("등장인물",)                               # 등장인물 문서는 인물 문서로 가는 길목 — 인물 문서의 명대사·밈 절을 읽는다
HOT = re.compile(r"밈|유행|패러디|파급|흥행|신드롬|인기|영향|반응|popular culture|Legacy|Cultural|impact|meme|response|社会|影響|反応|流行|迷因|影响|反響|ปรากฏการณ์|กระแส|Dampak|Fenomena|Tanggapan|Đón nhận|Ảnh hưởng", re.I)
OBS_CHARS = 2400
LANG_REGION = {"ja": "JP", "zh": "TW", "th": "TH", "id": "ID", "vi": "VN", "ko": "KR"}
REGIONS = ("KR", "JP", "TW", "HK", "CN", "US", "TH", "ID", "VN", "PH", "GLOBAL")

PROMPT = """너는 인터넷 밈 조사원이다. 목표: '{name}'({labels})에서 파생되어 각 나라에서 유행한 **밈**(짤·유행어·대사·챌린지·패러디)을 찾아 기록한다.
(나라 사이 짝짓기는 끝에 따로 한다 — 너는 많이, 여러 나라에서 찾는 데 집중하라).

도구 (한 번에 하나):
- open_page {{"url": 주소, "section": 절 이름 일부(선택), "offset": 이어 읽기(선택)}} — 나무위키·위키백과·Know Your Meme·Fandom 문서를 연다. 읽은 조각의 링크도 준다.
- search {{"site": "wikipedia"|"namu", "query": 검색어, "lang": "ko"|"en"|"ja"|"zh"|"th"|"id"|"vi"}}
- kym_children {{"slug": Know Your Meme 갈래 이름(예: "squid-game")}} — 그 갈래 아래 밈 항목을 모두 확인해 기록한다(영어권, 한 번이면 된다)
- extract {{"url": 주소, "section": 절 이름 일부(선택)}} — 그 절을 끝까지 읽어 밈을 모두 뽑아 기록한다. 절을 안 주면 밈이 있을 법한 절을 모두 읽는다.
  문서마다 한 번이면 된다. 밈이 있을 법한 문서를 찾았으면 open_page 대신 바로 extract 를 써라.
- finish {{}} — 더 찾을 것이 없을 때

규칙: 같은 걸음을 되풀이하지 마라. 한국(나무위키) → 영어권(Know Your Meme 하위 항목, 영어 위키백과) → 다른 나라 위키백과(ja·zh·th·id·vi, search 로 찾기) 순으로 넓혀라.
나무위키는 본문이 하위 문서('작품/흥행 및 파급력' 등)에 있는 일이 많다 — '하위 문서' 목록을 보고 들어가라. 밈 목록은 절 이름에 '밈'·'유행'·'패러디'·'파급' 이 든 곳에 있다.
주소는 결과에 나온 그대로 써라(지어내지 마라).
시작점(참고): {seeds}

지금까지 기록한 밈({n_found}개): {found}
나라별 찾은 수: {coverage}
아직 안 연 곳: {todo}
지금까지 연 주소: {visited}
최근 걸음: {history}
남은 단계: {left}

직전 결과:
{obs}

다음 한 걸음을 JSON 으로: {{"thought": "한국어 한 문장", "tool": 도구 이름, "args": {{…}}}}"""


class Step(BaseModel):
    thought: str = ""
    tool: Literal["open_page", "search", "kym_children", "extract", "finish"]
    args: dict = Field(default_factory=dict)


EXTRACT = """아래는 '{url}' 문서의 한 조각이다. 이 조각에서 '{name}'({labels})에서 파생된 **밈**(짤·유행어·대사·챌린지·패러디·노래 개사)을 모두 뽑아라.
작품 자체·시즌·회차·등장인물 소개·배우·흥행 기록·공식 상품·광고 협찬은 밈이 아니다. 조각에 없는 것은 지어내지 마라.
각 항목: name = 조각에 쓰인 그대로의 밈 이름, region = 그 밈이 유행한 곳({regions}; 영어권 전반은 GLOBAL, 문서 언어만으로 정하지 말고 본문이 말하는 곳),
kind = 대사|유행어|짤|챌린지|노래|패러디|일회성(유명인·기업·구단이 한 번 따라 한 것, 광고) 가운데 하나,
description = 한국어 한 줄, quote = 대사가 있으면 그대로, sentence = 이 밈을 말한 조각 속 문장 하나를 **글자 그대로** 베낀 것.
'오징어 게임 패러디 영상' 처럼 작품 이름에 '패러디·영상·장면' 을 붙인 뭉뚱그린 말은 밈 이름이 아니다.
없으면 빈 목록.

조각:
{chunk}"""


class Meme(BaseModel):
    name: str
    region: str = "GLOBAL"
    kind: str = ""
    description: str = ""
    quote: str = ""
    sentence: str = ""


class Extracted(BaseModel):
    items: list[Meme] = Field(default_factory=list)


class Pair(BaseModel):
    a: str
    b: str
    reason: str = ""


class Pairs(BaseModel):
    items: list[Pair] = Field(default_factory=list)


PAIR = """아래는 '{name}'에서 파생된 밈들을 나라별로 모은 것이다. 같은 장면·대사·노래에서 나온 **같은 밈**인데 나라마다 이름이 다른 것끼리 짝지어라
(예: 한국의 '나는 이 게임을 해 봤어요!' ↔ 영어권의 "I've Played These Games Before!"). 나라가 다른 것끼리만. 확실하지 않으면 짝짓지 마라.
a, b 는 목록의 이름을 글자 그대로, reason 은 한국어 한 줄(어느 장면·대사인지).

{lines}"""


def _norm(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", unicodedata.normalize("NFKC", s or "")).lower()


def _obs(tool: str, res: dict) -> str:
    """도구 결과를 모델이 읽을 만큼으로 줄인다."""
    if "error" in res:
        return f"[{tool}] 오류: {res['error']}"
    if tool == "open_page":
        links = "; ".join(f"{l['text']} → {l['url']}" for l in res.get("links", [])[:25])
        heads = ", ".join(res.get("headings", [])[:30])
        subs = "; ".join(f"{l['text']} → {l['url']}" for l in res.get("subpages", []))
        more = f" (이어 읽기 offset={res['next_offset']})" if res.get("next_offset") else ""
        hot = [h for h in res.get("headings", []) if HOT.search(h)]
        if hot:
            heads += "\n밈이 있을 법한 절(extract 의 section 으로): " + ", ".join(hot)
        return f"[open_page] {res['title']} {res['url']}{more}\n절: {heads}\n본문: {res['text'][:OBS_CHARS]}\n링크: {links}" + (f"\n하위 문서: {subs}" if subs else "")
    if tool == "extract":
        return f"[extract] {res['ok']}" + (f" (이어 읽기 offset={res['next_offset']})" if res.get("next_offset") else "")
    if tool == "kym_children":
        return f"[kym_children] {res.get('ok') or res.get('error')}"
    if tool == "search":
        return f"[{tool}] " + "; ".join(f"{r['title']} → {r['url']}" for r in res.get("results", [])[:30])
    return f"[{tool}] {json.dumps(res, ensure_ascii=False)[:600]}"


def run(con: Connection, key: str, name: str, labels: dict[str, str], seeds: list[str], max_steps: int = MAX_STEPS) -> str:
    """에이전트를 한 번 돌린다. 돌려주는 것: run_id."""
    from ..config import AUDIT_OLLAMA_HOST, RESEARCH_MODEL
    from ..interpreters import local_chat

    run_id = uuid.uuid4().hex[:10]
    found: list[dict] = []
    visited: list[str] = []
    obs = "(아직 없음 — 시작점 가운데 하나를 열어라)"
    def chat(prompt, schema):
        return local_chat.structured(prompt, schema, temperature=0.2, model=RESEARCH_MODEL, host=AUDIT_OLLAMA_HOST or None)

    fails = 0
    stuck = 0
    read: set[tuple[str, str]] = set()               # 읽은 (문서, 절)
    done: set[str] = set()                           # 같은 걸음(도구+인자) 되풀이 막기 — 첫 실행에서 같은 두 문서를 열 번 오갔다
    history: list[str] = []
    for step in range(max_steps):
        cov = {r: sum(f["region"] == r for f in found) for r in REGIONS}
        todo = [u for u in seeds if u.startswith("http") and W.canon(u) not in visited][:6]
        prompt = PROMPT.format(coverage=", ".join(f"{r} {n}" for r, n in cov.items()), todo=" | ".join(todo) or "없음",name=name, labels=", ".join(f"{k}:{v}" for k, v in labels.items()), regions="/".join(REGIONS), seeds=" | ".join(seeds),
                               n_found=len(found), found="; ".join(f"{f['name']}({f['region']})" for f in found) or "없음",
                               visited=" | ".join(visited[-12:]) or "없음", history=" / ".join(history[-8:]) or "없음",
                               left=max_steps - step, obs=obs)
        try:
            s = chat(prompt, Step)
        except Exception as e:                      # 형식 실패 — 세 번 이어지면 끊는다(차단기)
            fails += 1
            obs = f"직전 응답이 형식에 맞지 않았다({type(e).__name__}). JSON 하나로 답하라."
            if fails >= 3:
                break
            continue
        fails = 0
        a = s.args or {}
        sig = s.tool + json.dumps(a, ensure_ascii=False, sort_keys=True)
        rest = [u for u in seeds if (u.startswith("http") and W.canon(u) not in visited) or (u.startswith("kym_children") and u not in visited)]
        if (stuck >= 2 or s.tool == "finish") and rest:
            # 같은 걸음만 되풀이하거나 시작점을 남기고 끝내려 하면 남은 시작점을 규칙이 연다(스파이 패밀리에서 20걸음을 되풀이했다, 10-01)
            u = rest[0]
            s = (Step(thought="(규칙) 남은 시작점을 연다", tool="kym_children", args={"slug": u.split("=", 1)[1]}) if u.startswith("kym_children")
                 else Step(thought="(규칙) 남은 시작점을 연다", tool="extract", args={"url": u}))
            a = s.args
            sig = s.tool + json.dumps(a, ensure_ascii=False, sort_keys=True)
            visited.append(W.canon(u) if u.startswith("http") else u)     # 열지 못해도 다시 고르지 않는다
            stuck = 0
        if stuck >= 3 and not rest:                  # 갈 곳 없이 되풀이만 — 끝낸다
            _trace(con, run_id, step, Step(thought="(규칙) 되풀이만 이어져 끝낸다", tool="finish"), "끝")
            break
        if s.tool != "finish" and sig in done:
            stuck += 1
            obs = (f"[{s.tool}] 이미 한 걸음이다 — 결과는 같다. '아직 안 연 곳' 이나 찾은 수가 0 인 나라의 위키백과(search)로 가라."
                   + (" 갈 곳이 없으면 finish." if not any(u.startswith("http") and W.canon(u) not in visited for u in seeds) else ""))
            history.append(f"{s.tool}(되풀이 막힘)")
            _trace(con, run_id, step, s, "되풀이 막힘")
            continue
        done.add(sig)
        stuck = 0
        if s.tool == "finish":
            _trace(con, run_id, step, s, "끝")
            break
        if s.tool == "open_page":
            url = W.canon(str(a.get("url", "")))
            off = str(a.get("offset", "") or "0")
            res = (W.open_page(url, str(a.get("section", "") or ""), int(off)) if off.isdigit()
                   else {"error": "offset 은 숫자(직전 결과의 '이어 읽기 offset')만"})      # 잘못된 인자는 실행하지 않고 되돌린다
            if "error" not in res and url not in visited:
                visited.append(url)
        elif s.tool == "search":
            res = W.search(str(a.get("site", "wikipedia")), str(a.get("query", "")), str(a.get("lang", "ko")))
        elif s.tool == "kym_children":                # 갈래 항목은 제목이 곧 밈 이름 — 'Part of a series on' 확인은 코드가, 설명 한 줄만 모델이
            kids = W.kym_children(str(a.get("slug", ""))).get("results", [])
            visited.append(f"kym_children slug={a.get('slug', '')}")
            new = _kym(kids, name, chat, found)
            found.extend(new)
            res = {"ok": f"갈래 항목 {len(kids)}개 중 확인된 새 밈 {len(new)}개: " + ", ".join(g["name"] for g in new)}
        else:                                        # extract — 읽기와 뽑기를 나눈다(12B 는 걸음마다 하나씩 기록하다 같은 것을 되풀이했다)
            url = W.canon(str(a.get("url", "")))
            off = str(a.get("offset", "") or "0")
            page = W.open_page(url, str(a.get("section", "") or ""), int(off)) if off.isdigit() else {"error": "offset 은 숫자만"}
            if "error" in page:
                res = page
            else:
                if url not in visited:
                    visited.append(url)
                # 읽기는 도구가 꼼꼼히: 절을 주면 그 절 끝까지, 안 주면 밈이 있을 법한 절을 모두(12B 가 '2.4. 밈화' 를 건너뛰곤 했다)
                sec = str(a.get("section", "") or "")
                # 모델이 절을 골라도 밈이 있을 법한 절은 모두 읽는다(골라 준 절만 읽다가 '3.2. 밈화' 를 건너뛰었다, 10-01). 이미 읽은 절은 다시 읽지 않는다
                heads = list(dict.fromkeys(([sec] if sec else []) + [h.strip() for h in page.get("headings", []) if HOT.search(h)]))
                char_doc = any(url.endswith("/" + c) for c in CHAR_SUBPAGE)
                parts = [("", W.page_text(url))] if char_doc else [(h, W.section_text(url, h)) for h in heads]
                # '자세한 내용은 X 문서' 의 X — 하위 문서('작품/흥행 및 파급력')든 다른 문서('박연진')든. 등장인물 문서는 문서 전체에서 따라간다
                flat = [re.sub(r"\s+", " ", t) for _, t in parts]
                subs = list(dict.fromkeys(u for x, u in W.page_links(url) if "namu.wiki" in u and any(f"자세한 내용은 {x}" in t for t in flat)))[:10 if char_doc else 4]
                pages = [(page, [] if char_doc else parts)]
                for su in subs:
                    sp = W.open_page(su)
                    if "error" not in sp:
                        visited.append(su) if su not in visited else None
                        pages.append((sp, [(h.strip(), W.section_text(su, h.strip())) for h in sp.get("headings", []) if HOT.search(h) or QUOTES.search(h)]))
                got = []
                for pg, ps in pages:
                    for h, t in ps:
                        if (pg["url"], h) in read:
                            continue
                        read.add((pg["url"], h))
                        for i in range(0, len(t), W.CHUNK):
                            got += _extract({**pg, "text": t[i:i + W.CHUNK]}, name, labels, chat, quotes=bool(QUOTES.search(h)) and not HOT.search(h))
                    if pg is page and not ps and not char_doc and (pg["url"], "") not in read:
                        read.add((pg["url"], ""))
                        got += _extract(pg, name, labels, chat)
                if len(pages) > 1:
                    page["followed"] = [p["title"] for p, _ in pages[1:]]
                new = []
                for g in got:                            # 앞서 찾은 것·이번 묶음 안의 같은 이름은 하나로
                    if not any(_norm(f["name"]) == _norm(g["name"]) and f["region"] == g["region"] for f in found + new):
                        new.append(g)
                found.extend(new)
                res = {"ok": (f"하위 문서 {page['followed']} 도 읽음. " if page.get("followed") else "")
                       + (f"새로 {len(new)}개: " + ", ".join(f"{g['name']}({g['region']})" for g in new) if new else "새 밈 없음"),
                       "next_offset": page.get("next_offset")}
        obs = _obs(s.tool, res)
        history.append(f"{s.tool} {json.dumps(a, ensure_ascii=False)[:80]} → {'오류' if 'error' in res else 'ok'}")
        _trace(con, run_id, step, s, obs[:300])
    added = suggest(con, name, labels, found, visited)
    if added:
        found.extend(added)
        _trace(con, run_id, max_steps + 1, Step(thought="(Gemini) 아는 밈을 후보로 내고, 연 문서·나무위키 문서로 규칙이 확인", tool="finish"),
               "확인된 후보: " + ", ".join(f"{g['name']}({g['region']})" for g in added)[:280])
    verify(con, run_id, key, name, labels, found)
    pair(con, run_id, key, name, found, chat)
    # 나무위키가 부르는 이름도 찾는 이름으로 — 'SPY×FAMILY' 문서의 제목은 '스파이 패밀리' 다
    namu = next((W.page_title(u) for u in visited if u.startswith("https://namu.wiki/w/") and "/" not in u[len("https://namu.wiki/w/"):]), "")
    if namu and namu not in labels.values():
        labels = {**labels, "ko-namu": namu}
    con.execute("INSERT OR REPLACE INTO content_index VALUES (?,?,?,?,?)",
                (key, name, json.dumps(labels, ensure_ascii=False), run_id, datetime.now(timezone.utc).isoformat()))
    con.commit()
    return run_id


def find_content(con: Connection, q: str) -> tuple[str, str] | None:
    """콘텐츠 이름(어느 말로든) → (key, 이름). 조사한 적 없으면 None."""
    n = _norm(q)
    for key, name, labels in con.execute("SELECT content_key, name, labels_json FROM content_index"):
        if n and any(n == _norm(x) or n in _norm(x) for x in [key, name, *json.loads(labels).values()]):
            return key, name
    return None


def memes(con: Connection, key: str) -> tuple[list[dict], list[dict]]:
    """확인된 밈(여러 번 돌린 결과를 합친다 — 이름·나라마다 가장 최근 것)과 나라 사이 짝."""
    rows = con.execute("SELECT name, region, description, quote, evidence_url, sentence, term_id, created_at FROM content_findings "
                       "WHERE content_key=? AND verified=1 ORDER BY created_at", (key,)).fetchall()
    from .match import unsafe

    by = {(_norm(r[0]), r[1]): dict(zip(("name", "region", "description", "quote", "evidence_url", "sentence", "term_id"), r[:7]))
          for r in rows if not unsafe(r[0])}                 # 욕설이 든 대사 밈은 둘러보기에 내지 않는다(사전 목록과 같은 규칙)
    prs = con.execute("SELECT a, a_region, b, b_region, reason, verified FROM content_pairs WHERE content_key=?", (key,)).fetchall()
    pairs = list({(_norm(a), _norm(b)): {"a": a, "a_region": ar, "b": b, "b_region": br, "reason": why, "verified": bool(v)}
                  for a, ar, b, br, why, v in prs}.values())
    return list(by.values()), pairs


KYM_DESC = """다음은 '{name}' 에서 나온 영어권 밈들과 Know Your Meme 의 'About' 소개다. 각각 무슨 밈인지(어느 장면·대사에서 나와 어떻게 쓰이는지)
한국어 한 줄로 **네 말로** 써라 — 소개 문장을 옮겨 적지 마라. 모르면 빈 칸.
items: [{{"name": 그대로, "description": 한 줄}}]
{names}"""


class Desc(BaseModel):
    name: str
    description: str = ""


class Descs(BaseModel):
    items: list[Desc] = Field(default_factory=list)


def _kym(kids: list[dict], name: str, chat, found: list[dict]) -> list[dict]:
    """Know Your Meme 갈래 항목 — 'Part of a series on <name>' 이 있는 것만. 제목·주소만 쓴다(약관, Plan 12)."""
    have = {_norm(f["name"]) for f in found}
    ok = []
    for k in kids:
        if "/subcultures/" in k["url"] or not W.in_series(k["url"], name):
            continue
        title = re.sub(r"\s*\|\s*Know Your Meme\s*$", "", W.page_title(k["url"])).strip()     # 항목 페이지의 제목 — 목록의 그림 설명은 군말이 붙는다
        if not title:
            continue
        if _norm(title) in have:                     # 위키 본문에서 먼저 찾은 같은 밈 — 근거를 Know Your Meme 항목으로 바꾼다(그 밈의 제 문서)
            for f in found:
                if _norm(f["name"]) == _norm(title) and f["region"] == "GLOBAL":
                    f.update(name=title, evidence_url=k["url"], sentence=f"Part of a series on {name}")
            continue
        ok.append({"name": title[:80], "region": "GLOBAL", "description": "", "quote": "", "evidence_url": k["url"], "same_as": "",
                   "sentence": f"Part of a series on {name}"})
    if ok:
        try:
            lines = "\n".join(f"- {o['name']}: {re.sub(chr(10), ' ', W.section_text(o['evidence_url'], 'About'))[5:400]}" for o in ok)
            d = {}
            for i in range(0, len(ok), 8):                  # 8개씩 — 한 번에 24개면 12B 가 뒤쪽을 빠뜨렸다
                part = "\n".join(lines.split("\n")[i:i + 8])
                d.update({_norm(x.name): x.description for x in chat(KYM_DESC.format(name=name, names=part), Descs).items})
            for o in ok:
                o["description"] = d.get(_norm(o["name"]), "")[:200]
        except ValueError:
            pass
    return ok


def _extract(page: dict, name: str, labels: dict[str, str], chat, quotes: bool = False) -> list[dict]:
    """조각 하나에서 밈을 뽑는다. 이름과 근거 문장이 조각에 글자 그대로 있는 것만 남긴다(지어낸 것 거르기)."""
    chunk = page["text"]
    lang = (re.match(r"https://(\w+)\.wikipedia\.org", page["url"]) or [None, ""])[1]
    try:
        out = chat(EXTRACT.format(url=page["url"], name=name, labels=", ".join(labels.values()), regions="/".join(REGIONS), chunk=chunk), Extracted)
    except ValueError:
        return []
    nc = _norm(chunk)
    keep = []
    for m in out.items:
        nm = _norm(m.name)
        if not nm or nm not in nc or nm in {_norm(n) for n in [name, *labels.values()]} or m.kind.startswith("일회성"):
            continue
        if any(_norm(n) in nm for n in [name, *labels.values()]) and re.search(r"(패러디|영상|장면|비디오|밈)$", m.name.strip()):
            continue                                 # '오징어 게임 패러디 영상' 같은 뭉뚱그린 말
        sent = m.sentence.strip() if m.sentence and _norm(m.sentence) in nc else ""
        if quotes:                                       # 명대사 목록의 대사는 '밈이 됐다' 는 말이 곁(앞뒤 200자)에 있을 때만
            i = chunk.find(m.name.strip())
            if i < 0 or not CUE.search(chunk[max(0, i - 200): i + len(m.name) + 200]):
                continue
        if len(m.name.strip()) > 40 or re.search(r"(장면|모습|영상)$", m.name.strip()):
            continue                                 # 이름이 아니라 장면 설명이다('상우가 서울대 출신이라고 … 언급하는 장면')
        region = m.region if m.region in REGIONS else "GLOBAL"
        if re.search(r"[가-힣]", m.name):                # 한글 이름은 한국에서 부르는 이름이다 — 같은 밈의 영어 이름(GLOBAL)과 짝지어진다
            region = "KR"
        if region == "GLOBAL" and lang in LANG_REGION:      # 그 나라 말 위키백과에 그 나라 이름으로 적힌 것 — 그 나라의 이름이다
            region = LANG_REGION[lang]
        keep.append({"name": m.name.strip()[:80], "region": region, "description": m.description[:200],
                     "quote": m.quote[:200], "evidence_url": page["url"], "same_as": "", "sentence": sent[:300]})
    return keep


SUGGEST = """'{name}'({labels})에서 파생되어 실제로 유행한 밈(유행어·대사·짤·챌린지·패러디)을 나라별로 알려 줘.
나라: 한국(KR), 일본(JP), 대만(TW), 태국(TH), 인도네시아(ID), 베트남(VN), 필리핀(PH), 영어권(GLOBAL). 나라마다 최대 8개, 아는 것만.
작품·인물·배우 이름 자체나 공식 상품은 빼라. name 은 그 나라 사람들이 쓰는 그대로(번역하지 말 것), description 은 한국어 한 줄.
이미 찾은 것(다시 내지 마라): {have}"""


class Suggestions(BaseModel):
    items: list[Meme] = Field(default_factory=list)


def suggest(con: Connection, name: str, labels: dict[str, str], found: list[dict], visited: list[str]) -> list[dict]:
    """Gemini 가 아는 밈을 후보로 낸다(검색 grounding 없이 — 그 몫이 닫혀도 된다). 받을지는 규칙이 정한다:
    이번에 연 문서에 그 이름이 있고 곁(앞뒤 200자)에 밈이라는 말이 있거나, 그 이름의 나무위키 문서가 이 작품을 말할 때만.
    더 글로리에서 위키 본문만으로는 '멋지다 연진아' 같은 대표 밈을 놓쳤다(10-01) — 찾는 길을 넓히고 확인은 그대로 엄격하게."""
    from google.genai import types

    from ..config import LITE_MODEL
    from . import gemini

    if not gemini.configured():
        return []
    have = ", ".join(f["name"] for f in found)[:1500]
    try:
        resp, used = gemini.generate(con, SUGGEST.format(name=name, labels=", ".join(labels.values()), have=have or "없음"),
                                     types.GenerateContentConfig(response_mime_type="application/json", response_schema=Suggestions, temperature=0.2),
                                     model=LITE_MODEL, allow_local=False)
        cands = resp.parsed.items if resp.parsed else []
    except Exception:
        return []
    names = [n for n in [name, *labels.values()] if n]
    seen = {(_norm(f["name"]), f["region"]) for f in found}
    out = []
    for c in cands:
        nm = c.name.strip()
        region = c.region if c.region in REGIONS else "GLOBAL"
        if not nm or (_norm(nm), region) in seen or _norm(nm) in {_norm(n) for n in names} or len(nm) > 40:
            continue
        hit = None
        for u in visited:                                # 1) 이번에 읽은 문서 — 이름 곁에 밈이라는 말
            if not u.startswith("http"):
                continue
            t = W.page_text(u)
            i = t.find(nm)
            if i >= 0 and CUE.search(t[max(0, i - 200): i + len(nm) + 200]):
                sent = next((x for x in re.split(r"(?<=[.!?。])\s+|\n", t) if nm in x), "")[:300]
                hit = (u, sent)
                break
        if not hit and re.search(r"[가-힣]", nm):
            # 2) 나무위키가 그 말을 이 작품(또는 하위·인물 문서)으로 넘겨준다 — 편집자가 그 말을 이 작품의 표현으로 올려 둔 것
            #    ('멋지다 연진아' → '더 글로리', 10-01). 넘기지 않는 제 문서면 첫머리가 이 작품을 말해야 한다.
            for v in dict.fromkeys([nm, nm.rstrip("!?.~… "), re.sub(r"[!?.~…]+", "", nm).strip()]):
                u = W.canon(f"https://namu.wiki/w/{v}")
                pg = W.open_page(u)
                if "error" in pg:
                    continue
                title, t = pg["title"], W.page_text(u)
                to_content = any(title.startswith(n) for n in names) or any(W.page_title(x) == title for x in visited if x.startswith("http"))
                if (title != v and to_content) or (title == v and any(n in t[:1500] for n in names)):
                    hit = (u, f"나무위키 '{v}' → '{title}'" if title != v else next((x for x in re.split(r"(?<=[.!?。])\s+|\n", t) if any(n in x for n in names)), "")[:300])
                    break
        if not hit:
            # 3) 사전에 이미 확인된 표제어이고 그 뜻·유래가 이 작품을 말한다(게이트가 참고 문서로 확인한 것)
            from ..storage import dictionary_store as ds

            t = ds.find_term(con, nm) or ds.find_term(con, re.sub(r"[!?.~…]+", "", nm).strip())
            m = ds.current_meaning(con, t.term_id) if t and t.status == "verified" else None
            if m and any(n in f"{m.definition} {m.origin}" for n in names):
                ref = next((e.url for e in ds.list_evidences(con, t.term_id) if e.url and W.allowed(e.url)), "")
                hit = (ref, f"사전 표제어 '{t.canonical}' (확인됨)")
        if hit:
            seen.add((_norm(nm), region))
            out.append({"name": nm, "region": "KR" if re.search(r"[가-힣]", nm) else region, "description": c.description[:200],
                        "quote": "", "evidence_url": hit[0], "same_as": "", "sentence": hit[1], "checked": hit[1].startswith(("나무위키 '", "사전 표제어 '"))})
    return out


NEAR = 300


def _near(text: str, a: str, b: str) -> bool:
    """정규화한 본문에서 a 가 나온 자리 앞뒤 NEAR 글자 안에 b 가 있는가. a 가 본문에 없으면(다른 문서가 근거) b 만 있어도 된다."""
    if not a or not b or b not in text:
        return False
    spots = [m.start() for m in re.finditer(re.escape(a), text)]
    return not spots or any(b in text[max(0, i - NEAR): i + len(a) + NEAR] for i in spots)


def pair(con: Connection, run_id: str, key: str, name: str, found: list[dict], chat) -> None:
    """나라가 다른 같은 밈 짝. 모델이 제안하고, 규칙이 확인한다: 한쪽 근거 페이지에 다른 쪽 이름(또는 같은 대사)이 있으면 확인, 아니면 '제안' 으로만."""
    if len({f["region"] for f in found}) < 2:
        return
    lines = "\n".join(f"- [{f['region']}] {f['name']}: {f['description']}" + (f" (대사: {f['quote']})" if f["quote"] else "") for f in found)
    try:
        out = chat(PAIR.format(name=name, lines=lines), Pairs)
    except ValueError as e:
        print("짝짓기 실패:", str(e)[:200])
        return
    print("짝 제안", len(out.items), [(p.a, p.b) for p in out.items][:20])
    by = {_norm(f["name"]): f for f in found}
    tag = re.compile(r"^\s*\[[A-Z]+\]\s*")              # 모델이 목록의 '[KR] ' 머리를 함께 베낀다
    for p in out.items:
        fa, fb = by.get(_norm(tag.sub("", p.a))), by.get(_norm(tag.sub("", p.b)))
        if not fa or not fb or fa["region"] == fb["region"]:
            continue
        ta, tb = _norm(W.page_text(fa["evidence_url"])), _norm(W.page_text(fb["evidence_url"]))
        quotes = [q for q in (fa["quote"], fb["quote"]) if len(_norm(q)) >= 4]
        # 한 문서에 둘 다 있는 것만으로는 안 된다(나무위키 한 절에 밈이 수십 개) — 한쪽 이름 가까이(NEAR 글자 안)에 다른 쪽 이름이 있어야 한다
        # 근거 문서가 서로 달라야 한다 — 한 문서 안에서 가까이 있는 두 밈은 같은 밈이 아니라 나란히 적힌 밈인 일이 많았다
        # ('The Glory Thai' 와 '문동은의 대사', 10-01). 다른 나라의 그 밈 문서가 이 이름을 말해야 같은 밈이다.
        hit = W.canon(fa["evidence_url"]) != W.canon(fb["evidence_url"]) and (
            _near(ta, _norm(fa["name"]), _norm(fb["name"])) or _near(tb, _norm(fb["name"]), _norm(fa["name"]))
            or any(_norm(q) in ta and _norm(q) in tb for q in quotes))
        con.execute("INSERT OR REPLACE INTO content_pairs VALUES (?,?,?,?,?,?,?,?,?)",
                    (run_id, key, fa["name"], fa["region"], fb["name"], fb["region"], p.reason[:200], int(hit),
                     "" if hit else "다른 나라 쪽 문서가 이 이름·대사를 말하지 않음(모델 제안)"))
    con.commit()


def _trace(con, run_id: str, step: int, s: Step, result: str) -> None:
    con.execute("INSERT OR REPLACE INTO agent_trace VALUES (?,?,?,?,?,?,?)",
                (run_id, step, s.thought[:300], s.tool, json.dumps(s.args, ensure_ascii=False)[:500], result, datetime.now(timezone.utc).isoformat()))
    con.commit()


def verify(con: Connection, run_id: str, key: str, name: str, labels: dict[str, str], found: list[dict]) -> None:
    """받을지는 규칙이 정한다: 근거 페이지(이번에 연 것)에 밈 이름이 있고, 그 페이지가 콘텐츠를 말하거나 Know Your Meme 그 갈래 항목일 때."""
    from ..storage import dictionary_store as ds

    names = [n for n in [name, *labels.values()] if n]
    now = datetime.now(timezone.utc).isoformat()
    for f in found:
        url = W.canon(f["evidence_url"]) if f["evidence_url"] else ""
        text = W.page_text(url) if url and W.allowed(url) else ""
        has_name = bool(text) and _norm(f["name"]) in _norm(text)
        about = bool(text) and (any(_norm(n) in _norm(text) for n in names) or ("knowyourmeme.com" in url and W.in_series(url, name)))
        if f.get("checked"):                         # suggest 가 넘겨주기·사전으로 이미 확인했다(넘겨받은 작품 문서에 그 말이 없을 수 있다)
            has_name = about = True
        why = "" if has_name and about else ("근거 페이지를 열 수 없음" if not text else "근거 페이지에 밈 이름이 없음" if not has_name else "근거 페이지가 콘텐츠를 말하지 않음")
        t = ds.find_term(con, f["name"])
        con.execute("INSERT OR REPLACE INTO content_findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (run_id, key, f["name"], f["region"], f["description"], f["quote"], url, f.get("sentence", ""), f["same_as"], int(not why), why,
                     t.term_id if t else None, now))
    con.commit()


ORDER = ("KR", "JP", "TW", "HK", "CN", "TH", "ID", "VN", "PH", "US", "GLOBAL")


def view(con: Connection, key: str) -> dict | None:
    """화면용: 밈 하나가 한 줄 — 같은 밈의 나라별 이름(확인된 짝으로 묶음)을 함께. 여러 나라에 걸친 밈부터."""
    row = con.execute("SELECT name, labels_json, updated_at FROM content_index WHERE content_key=?", (key,)).fetchone()
    if not row:
        return None
    found, pairs = memes(con, key)
    idx = {(_norm(f["name"]), f["region"]): i for i, f in enumerate(found)}
    parent = list(range(len(found)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    reasons: dict[int, str] = {}
    for p in pairs:
        ia, ib = idx.get((_norm(p["a"]), p["a_region"])), idx.get((_norm(p["b"]), p["b_region"]))
        if p["verified"] and ia is not None and ib is not None:
            parent[root(ia)] = root(ib)
            reasons[root(ib)] = p["reason"]
    groups: dict[int, list[dict]] = {}
    for i, f in enumerate(found):
        groups.setdefault(root(i), []).append(f)
    rank = {r: n for n, r in enumerate(ORDER)}
    memes_out = []
    for r, vs in groups.items():
        vs.sort(key=lambda f: rank.get(f["region"], 99))
        memes_out.append({"variants": [{k: f[k] for k in ("name", "region", "description", "quote", "evidence_url", "sentence", "term_id")} for f in vs],
                          "same_scene": reasons.get(r, "")})
    memes_out.sort(key=lambda m: (-len({v["region"] for v in m["variants"]}), rank.get(m["variants"][0]["region"], 99), m["variants"][0]["name"]))
    regions = sorted({v["region"] for m in memes_out for v in m["variants"]}, key=lambda r: rank.get(r, 99))
    return {"content": {"key": key, "name": row[0], "labels": json.loads(row[1])}, "regions": regions, "memes": memes_out, "updated_at": row[2]}


def contents(con: Connection) -> list[dict]:
    out = []
    for key, name, labels, at in con.execute("SELECT content_key, name, labels_json, updated_at FROM content_index ORDER BY updated_at DESC"):
        found, _ = memes(con, key)
        out.append({"key": key, "name": name, "labels": json.loads(labels), "memes": len(found),
                    "regions": sorted({f["region"] for f in found}, key=lambda r: ORDER.index(r) if r in ORDER else 99), "updated_at": at})
    return out
