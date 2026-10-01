"""위키 밈 분류를 통째로 사전 후보로 (Plan 16). 나무위키 분류:인터넷 밈·분류:유행어 나무에서 문서 제목과 걸린 분류만 받는다(본문 없음).

- 분류는 데이터다: 종류(인터넷 밈/음식·게임·동물…), 연대·연도(2020년대 인터넷 밈…), 나라(인터넷 밈/일본·대만·홍콩…)를
  wiki_catalog 에 그대로 두고, 나라는 사용 지역(usage, source='catalog')으로 쓴다. 모델이 추정하지 않는다.
- 뜻은 가벼운 조사(research_one(lean=True))가 위키 문서·사전만 보고 로컬 모델로 쓴다. 등재는 같은 게이트가 정한다(ADR 0003).
- 분류에 든 문서라도 표제어가 아닌 것(인물·작품 문서가 '인터넷 밈/인물' 에 걸린 것)은 게이트의 '표현이 아님' 이 거른다.
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone

from ..schemas import Term
from ..storage import dictionary_store as ds

# 나라 이름 → 지역. 나라가 갈리지 않는 묶음(동남아시아·다국적·기타 국가·중화권)은 지역을 두지 않는다.
COUNTRY = {"한국": "KR", "대한민국": "KR", "일본": "JP", "대만": "TW", "홍콩": "HK", "중국": "CN", "미국": "US", "북미": "US", "영미권": "US",
           "서양권": "US", "러시아": "RU", "독일": "DE", "이탈리아": "IT", "태국": "TH", "베트남": "VN", "필리핀": "PH", "인도": "IN",
           "폴란드": "PL", "핀란드": "FI", "스웨덴": "SE", "이집트": "EG", "동남아시아": "", "다국적": "", "기타 국가": "", "중화권": ""}
# 사람 분류 — 사람 이름 문서라 표제어가 아니다(09-30 실측: 6,995개 가운데 가장 큰 덩어리). 성인물은 싣지 않는다.
PERSON = {"가수", "배우", "기업인", "기자", "교육인", "기타 인물", "농구 감독", "농구 선수", "만화가", "성우", "스포츠 감독", "야구 감독", "야구 선수",
          "예능인", "요리사", "운동선수", "인물", "인터넷 방송인", "정치인", "종교인", "체육인", "축구 감독", "축구 선수", "프로게이머", "게임 개발자"}
SKIP_GENRES = PERSON | {"성인물"}
# 위키백과(태국어·인도네시아어) 사람 분류 — 분류 이름에 이 낱말이 들어 있으면 사람 문서다.
PERSON_CAT = re.compile(r"บุคคล|คนดัง|เน็ตไอดอล|นักร้อง|นักแสดง|Tokoh|Selebritas|YouTuber|Selebriti|Penyanyi|Aktor|Aktris|Pesohor", re.I)
MEME_CUE = re.compile(r"밈|유행|패러디|짤|드립|합성|챌린지|틱톡|유튜브|쇼츠|커뮤니티|인터넷|meme|ミーム|梗|迷因", re.I)
CLUB = re.compile(r".+ FC$")


def meta(categories: list[str]) -> dict:
    """걸린 분류들 → {genres, countries, decade, year, slang}. 모두 분류 이름에서 읽는다.
    '인터넷 밈/음악/일본' 은 종류 음악 + 나라 일본, '인터넷 밈/일본 광고' 는 광고 + 일본, '인터넷 밈/리버풀 FC' 는 축구."""
    genres, countries, regions, decade, year = set(), set(), set(), None, None
    for c in categories:
        m = re.fullmatch(r"인터넷 밈/(.+)", c)
        if m:
            parts = m.group(1).split("/")
            head = parts[0]
            for p in parts[1:]:
                if p in COUNTRY:
                    countries.add(p)
                else:
                    genres.add(p)
            if head in COUNTRY:
                countries.add(head)
            elif CLUB.fullmatch(head):
                genres.add("축구")
            else:
                sp = head.split(" ", 1)
                if len(sp) == 2 and sp[0] in COUNTRY and sp[1] in ("광고", "게임"):
                    countries.add(sp[0])
                    genres.add(sp[1])
                else:
                    genres.add(head)
        tag = re.fullmatch(r"(year|region):(.+)", c)          # 위키데이터·Fandom 에서 온 말의 꼬리표
        if tag and tag.group(1) == "year" and tag.group(2).isdigit():
            year = int(tag.group(2))
        elif tag:
            regions.add(tag.group(2))
        if PERSON_CAT.search(c):
            genres.add("인물")
        w = re.search(r"(?:มีมในปี พ\.ศ\. (\d{4})|Meme internet yang diperkenalkan (?:pada )?(?:tahun )?(\d{4}))$", c)
        if w:
            n = int(w.group(1) or w.group(2))
            year = n - 543 if n > 2400 else n
        y = (re.fullmatch(r"(\d{4})년 인터넷 밈", c) or re.fullmatch(r"(\d{4})年流行用語", c)
             or re.search(r"Internet memes introduced in (\d{4})$", c) or re.search(r"(\d{4})年の(?:インターネット・)?ミーム$", c)
             or re.search(r"(\d{4})年(?:网络|網路|網絡)(?:流行语|流行語|迷因)$", c))      # 영어·일본어·중국어 위키백과의 연도 분류(10-01)
        if y:
            year = int(y.group(1))
        d = re.fullmatch(r"(\d{4})년대 인터넷 밈", c)
        if d:
            decade = int(d.group(1))
    if year and not decade:
        decade = year // 10 * 10
    regions |= {COUNTRY[c] for c in countries if COUNTRY.get(c)}
    return {"genres": sorted(genres), "countries": sorted(countries), "regions": sorted(regions), "decade": decade, "year": year,
            "slang": "유행어" in categories or any(c.startswith("유행어/") for c in categories) or any("用語" in c or "潮語" in c for c in categories)}


def title_to_term(title: str) -> str | None:
    """문서 제목 → 표제어. 구분 꼬리 '(유행어)' 류는 떼고, 긴 제목·틀 문구는 버린다."""
    t = re.sub(r"\s*\([^)]*\)$", "", title).strip()
    if not t or len(t) > 30 or "/" in t or "XX" in t:
        return None
    return t


def script_lang(text: str) -> str:
    if re.search(r"[가-힣]", text):
        return "ko"
    if re.search(r"[぀-ヿ]", text):
        return "ja"
    if re.search(r"[一-鿿]", text):
        return "zh"
    if re.search(r"[฀-๿]", text):
        return "th"
    return "en" if re.search(r"[A-Za-z]", text) else ""


def order(entries: dict[str, list[str]]) -> list[tuple[str, dict]]:
    """넣는 순서: 모자란 지역(대만·홍콩·일본·서양권)과 2020년대를 먼저 — 평가에서 해외 후보가 비었다(Plan 09 2차)."""
    want = {"대만": 0, "홍콩": 0, "동남아시아": 0, "태국": 0, "베트남": 0, "필리핀": 0, "일본": 1, "미국": 1, "영미권": 1, "서양권": 1, "중국": 2, "인도": 2}

    def key(item):
        m = item[1]
        return (min((want.get(c, 3) for c in m["countries"]), default=3), 0 if m["decade"] == 2020 else 1 if m["decade"] == 2010 else 2, item[0])

    items = [(title, meta(cats)) for title, cats in entries.items()]
    return sorted(items, key=key)


def record(con: Connection, term_id: str, title: str, source: str, categories: list[str]) -> None:
    con.execute("INSERT OR REPLACE INTO wiki_catalog VALUES (?,?,?,?,?)",
                (term_id, source, title, json.dumps(categories, ensure_ascii=False), datetime.now(timezone.utc).isoformat()))
    con.commit()


def add(con: Connection, title: str, categories: list[str], source: str = "namu", aliases: list[str] | tuple[str, ...] = ()) -> Term | None:
    """분류 문서 하나를 조사할 표제어로 세운다. 이미 있는 말은 분류 기록만 남긴다. 세운 표제어(또는 None)."""
    m = meta(categories)
    if set(m["genres"]) & SKIP_GENRES:
        return None
    name = title_to_term(title)
    if not name:
        return None
    have = ds.find_term(con, name) or next((ds.find_term(con, a) for a in aliases if a and ds.find_term(con, a)), None)
    if have:
        record(con, have.term_id, title, source, categories)
        return None
    lang = script_lang(name) or {"TW": "zh", "HK": "zh", "CN": "zh", "JP": "ja", "KR": "ko", "TH": "th", "ID": "id"}.get(next(iter(m["regions"]), ""), "en")   # '1450' 처럼 글자가 없는 제목
    region = next(iter(m["regions"]), None)
    if lang == "en" and region in ("TH", "ID"):       # 위키백과 th·id 의 로마자 제목은 그 나라 말 문서의 이름이다
        lang = {"TH": "th", "ID": "id"}[region]
    now = datetime.now(timezone.utc)
    t = Term(term_id=ds.new_id("t", f"{unicodedata.normalize('NFKC', name).lower()}|{lang}"), canonical=name, lang=lang, status="researching",
             category="slang" if m["slang"] else "meme", aliases=[a for a in dict.fromkeys(aliases) if a and a != name][:6],
             first_seen=now, last_seen=now)
    ds.upsert_term(con, t)
    record(con, t.term_id, title, source, categories)
    if region:
        # 나라는 위키 분류가 정한 데이터다 — 세대는 모르므로 'all'. 조사가 모델 추정으로 덮지 않는다(나라 줄이 이미 있으면 쓰지 않는다)
        ds.set_usage(con, t.term_id, [("all", region, now.isoformat(), 1.0)], source="catalog")
    return t


def prepare_fandom(con: Connection, t: Term, site: str, title: str) -> bool:
    """PTT鄉民百科·香港網絡大典 문서: 첫머리를 메모리에서만 보이고(research.WIKI_CONTEXT), 짧은 발췌·링크를 근거로."""
    from ..collectors import fandom
    from . import research

    text = fandom.intro(site, title)
    if not text:
        return False
    ds.add_evidences(con, t.term_id, [fandom.evidence(site, title, text)])
    research.WIKI_CONTEXT[t.canonical] = [x.strip() for x in re.split(r"(?<=[。！？.!?])", text) if len(x.strip()) > 6][:6]
    return True


def prepare_wikipedia(con: Connection, t: Term, source: str, title: str) -> bool:
    """위키백과(th·id) 분류 문서: 첫머리를 메모리에서만 보이고(research.WIKI_CONTEXT), 짧은 발췌·링크를 근거로."""
    from ..collectors import wikipedia_category as wc
    from . import research

    text = wc.intro(wc.SOURCES[source]["lang"], title)
    if not text:
        return False
    ds.add_evidences(con, t.term_id, [wc.evidence(source, title, text)])
    research.WIKI_CONTEXT[t.canonical] = [x.strip() for x in re.split(r"(?<=[。！？.!?])\s", text) if len(x.strip()) > 6][:6]
    return True


def prepare_wikidata(con: Connection, t: Term, item: dict) -> bool:
    """위키데이터 항목: 외부 문서 ID 로 참고 문서 링크(주소·제목만)를 붙인다 — 그 사이트에는 요청하지 않는다. 나무위키 ID 가 있으면 개요도 본다."""
    from ..collectors import wikidata_memes

    evs = wikidata_memes.evidences(item, t.canonical)
    if evs:
        ds.add_evidences(con, t.term_id, evs)
    namu = item["ext"].get("P8885")
    return bool(evs) | (prepare(con, t, namu) if namu else False)


def prepare(con: Connection, t: Term, title: str) -> bool:
    """조사 전에 그 말을 데려온 나무위키 문서를 붙인다: 짧은 발췌·링크는 근거로 저장하고(나무위키 규칙과 같다),
    개요 앞 몇 문장은 조사 모델에게 **메모리에서만** 보인다(research.WIKI_CONTEXT, 저장하지 않는다).
    제목이 한글이 아닌 말(Campfire song song·See Tình)은 조사가 나무위키를 찾지 않아 뜻이 비었다(09-30 실측). 문서에 닿았나."""
    from ..collectors import namuwiki
    from . import research

    ev = namuwiki.lookup(title)
    if ev:
        ds.add_evidences(con, t.term_id, ev)
    body = namuwiki.page_text(title) or ""
    i = body.find("개요")
    text = re.sub(r"\[\d+\]|\[편집\]", "", re.sub(r"\s+", " ", body[i + 2:] if i >= 0 else body))
    all_sents = [x.strip() for x in re.split(r"(?<=[.!?다])\s", text) if 10 < len(x.strip()) < 300]
    # 개요 앞 세 문장 + 밈으로 쓰인 이야기(노래·작품 문서는 개요가 작품 설명이고 밈 이야기는 뒤쪽 절에 있다, 09-30)
    meme = [x for x in all_sents[3:] if MEME_CUE.search(x)][:6]
    sents = all_sents[:3] + meme
    if sents:
        research.WIKI_CONTEXT[t.canonical] = sents
    return bool(ev or sents)


def prepare_trendaword(con: Connection, t: Term, p: dict) -> bool:
    """Trend A Word 게시글: 그 단어가 든 한 문장·링크를 근거로, 뜻·용례 문장은 메모리에서만 조사 모델에게 보인다."""
    from ..collectors import trendaword
    from . import research

    ds.add_evidences(con, t.term_id, [trendaword.evidence(p)])
    lines = p["sentences"] + [f"용례: {u}" for u in p.get("usage", [])]
    if lines:
        research.WIKI_CONTEXT[t.canonical] = lines[:8]
    return bool(lines)


def add_trendaword(con: Connection, p: dict) -> Term | None:
    """게시글 하나 → 표제어(한국, 호 날짜의 해). 이미 있는 말이면 근거만 더한다."""
    from ..collectors import trendaword

    year = (p.get("date") or "")[:4]
    cats = ["region:KR", "유행어"] + ([f"year:{year}"] if year.isdigit() else [])
    t = add(con, p["word"], cats, source="trendaword")
    if t is None:
        have = ds.find_term(con, title_to_term(p["word"]) or p["word"])
        if have:
            ds.add_evidences(con, have.term_id, [trendaword.evidence(p)])
        return None
    prepare_trendaword(con, t, p)
    return t
