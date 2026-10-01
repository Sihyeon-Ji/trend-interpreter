"""위키데이터의 인터넷 밈 항목(Q2927074 와 그 하위 갈래) — 이름(여러 언어)·생긴 날짜(P571)·나라(P495)·외부 문서 ID. 공식 SPARQL, CC0.

왜: 과거 비교에 쓸 '생긴 해' 와 나라별 이름이 한데 있다(2026-09-30 실측: 1,036개 가운데 314개에 날짜).
그리고 **자동 수집을 막은 사이트의 문서가 있다는 사실**을 그 사이트에 요청하지 않고 안다 — 니코니코 대백과(P6900)·pixiv 백과사전(P11408)은
이 서버의 요청을 403 으로 막는다. 막은 곳을 우회하지 않고, 위키데이터 편집자가 이어 둔 ID 로 **주소와 제목만** 근거로 쓴다(Know Your Meme 과 같은 규칙).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from ..schemas import Evidence

from ..config import BOT_UA as UA  # noqa: E402
ENDPOINT = "https://query.wikidata.org/sparql"
CACHE = Path("data/cache/wikidata_memes.json")
CACHE_TTL_S = 7 * 24 * 3600
LANGS = ("ko", "ja", "zh", "zh-hant", "zh-tw", "zh-hk", "en", "th", "vi", "id", "tl")

# 외부 문서 ID → (도메인, 주소 틀, 이름)
EXTERNAL = {
    "P6900": ("dic.nicovideo.jp", "https://dic.nicovideo.jp/a/{}", "ニコニコ大百科"),
    "P11408": ("dic.pixiv.net", "https://dic.pixiv.net/a/{}", "pixiv百科事典"),
    "P5737": ("zh.moegirl.org.cn", "https://zh.moegirl.org.cn/{}", "萌娘百科"),
    "P8885": ("namu.wiki", "https://namu.wiki/w/{}", "나무위키"),
    "P13484": ("knowyourmeme.com", "https://knowyourmeme.com/memes/{}", "Know Your Meme"),
}

QUERY = """SELECT ?m ?inc ?iso (GROUP_CONCAT(DISTINCT CONCAT(LANG(?l), "\\t", ?l); SEPARATOR="\\n") AS ?labels)
  (GROUP_CONCAT(DISTINCT ?ext; SEPARATOR="\\n") AS ?exts) WHERE {
  ?m wdt:P31/wdt:P279* wd:Q2927074 .
  OPTIONAL { ?m wdt:P571 ?inc . }
  OPTIONAL { ?m wdt:P495 ?c . ?c wdt:P297 ?iso . }
  OPTIONAL { ?m rdfs:label ?l . FILTER(LANG(?l) IN (%s)) }
  OPTIONAL { VALUES ?p { %s } ?m ?p ?v . BIND(CONCAT(STRAFTER(STR(?p), "direct/"), "\\t", STR(?v)) AS ?ext) }
} GROUP BY ?m ?inc ?iso"""


def memes(cache: bool = True) -> list[dict]:
    """[{qid, labels: {lang: 이름}, year, countries: [ISO], ext: {P번호: ID}}]. 하루가 아니라 일주일 캐시(자주 바뀌지 않는다)."""
    if cache and CACHE.exists() and time.time() - CACHE.stat().st_mtime < CACHE_TTL_S:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    q = QUERY % (", ".join(f'"{x}"' for x in LANGS), " ".join(f"wdt:{p}" for p in EXTERNAL))
    r = httpx.get(ENDPOINT, params={"query": q}, headers={"User-Agent": UA, "Accept": "application/sparql-results+json"}, timeout=90)
    r.raise_for_status()
    by: dict[str, dict] = {}
    for b in r.json()["results"]["bindings"]:
        qid = b["m"]["value"].rsplit("/", 1)[1]
        it = by.setdefault(qid, {"qid": qid, "labels": {}, "year": None, "countries": [], "ext": {}})
        for line in b.get("labels", {}).get("value", "").split("\n"):
            if "\t" in line:
                lang, name = line.split("\t", 1)
                it["labels"].setdefault(lang, name)
        for line in b.get("exts", {}).get("value", "").split("\n"):
            if "\t" in line:
                p, v = line.split("\t", 1)
                it["ext"].setdefault(p, v)
        inc = b.get("inc", {}).get("value", "")
        if inc[:4].isdigit():
            y = int(inc[:4])
            it["year"] = min(y, it["year"] or y)
        iso = b.get("iso", {}).get("value")
        if iso and iso not in it["countries"]:
            it["countries"].append(iso)
    out = list(by.values())
    if cache:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def evidences(item: dict, name: str) -> list[Evidence]:
    """외부 문서 ID → 참고 문서 근거(주소·제목만, 발췌 없음). 그 사이트에는 요청하지 않는다."""
    now = datetime.now(timezone.utc)
    out = []
    for p, (domain, tmpl, site) in EXTERNAL.items():
        v = item["ext"].get(p)
        if not v:
            continue
        url = tmpl.format(quote(v.replace(" ", "_") if domain != "namu.wiki" else v, safe="()_-:"))
        out.append(Evidence(evidence_id=f"e_wd_{item['qid']}_{p}", kind="wiki", url=url, title=f"{site}: {name}"[:200],
                            source_domain=domain, observed_at=now, excerpt=""))
    return out
