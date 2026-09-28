"""위키백과 밈 분류에서 '알려진 표현' 목록을 받아 온다. 키 불필요, 저작권은 제목만 쓰므로 문제없다.

왜 필요한가: 지금 후보는 전부 '지금 뜨는 것'에서만 온다(트렌드·쇼츠·발굴). 반년 전에 정점을 찍은 밈은
후보 대기열에 아예 들어오지 못한다 — 이탈리안 브레인로트 계열이 Tung Tung Tung Sahur 하나만 있는 이유다.

여기서 가져오는 것은 **이름뿐**이다. 뜻은 기존 조사·검증 단계가 평소대로 만들고, 위키 문서는 근거 하나로만 쓴다
(`wikipedia_search.summary`). 사전을 위키로 채우는 게 아니라, 조사할 거리를 위키에서 받아 온다.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import httpx

UA = "trend-agents/0.1 (AI Builder Cup 2026 prototype)"
TIMEOUT = 15.0

# 언어판별 밈 분류. 연도 분류는 최근 것이 알짜라 따로 둔다.
CATEGORIES: dict[str, list[str]] = {
    "en": ["Category:Internet memes introduced in 2025", "Category:Internet memes introduced in 2024", "Category:Internet memes"],
    "ko": ["분류:인터넷 밈"],
    "ja": ["Category:インターネット・ミーム"],
    "id": ["Kategori:Meme Internet"],
    # 목표 지역(ADR 0001): 중국어는 대만·홍콩으로 본다. 태국어·타갈로그어 위키에는 밈 분류가 없고, 말레이어·베트남어
    # 분류는 영어 밈(Anonymous·T-pose…)을 옮긴 문서라 그 나라 밈으로 잘못 붙는다(09-28 실측) — 넣지 않는다.
    "zh": ["Category:网络流行语"],
}
LANG_REGION = {"en": "US", "ko": "KR", "ja": "JP", "id": "ID", "zh": "TW"}

# 목록·설명 문서는 표현이 아니다. 괄호 주석이 붙은 것은 살린다("6-7 (meme)" → "6-7").
SKIP = ("List of", "목록", "일람", "Daftar", "Danh sách", "列表", "一覽", "一览", "大賞", "Internet meme", "인터넷 밈", "インターネット・ミーム", "Meme Internet",
        "Category:", "분류:", "Template:", "틀:")

# 괄호 주석을 떼도 되는 것 — 뗀 이름이 그대로 표제어다.
OK_PAREN = re.compile(r"^(meme|밈|ミーム|internet meme|인터넷 밈|유행어|slang|dance|챌린지)$", re.I)

# 분류에 들어 있다는 것 자체가 '인터넷 밈' 이라는 뜻이다 — 그래서 설명은 **걸러내는 데만** 쓴다.
# (새로 생긴 문서는 설명이 아직 없다. Ballerina Cappuccina·Bombardiro Crocodilo 가 전부 그 경우였다.)
_NOT_TERM = re.compile(
    r"\b(song|album|single|film|movie|book|novel|manga|anime series|television series|tv series|season of|franchise|"
    r"video game|mobile game|game by|board game|platform|website|web series|app\b|"
    r"company|corporation|airline|brand|restaurant|chain|product|drink|toy|collectible|cryptocurrency|"
    r"band|rapper|singer|musician|actor|actress|streamer|youtuber|influencer|internet personality|"
    r"footballer|politician|businessman|racehorse|league|club|"
    r"born \d{4}|\(\d{4}[–-]|murder|suspect|scandal|incident|conspiracy|"
    r"fictional character|cartoon character|dog breed|martial art|historiographical|"
    r"tour operator|musical artist|advertising campaign|advertisement|photograph|feud|social media duo|"
    r"parties hosted|newspaper|magazine)\b|"
    r"노래|음반|싱글|영화|드라마|만화|게임|웹사이트|기업|프렌차이즈|프랜차이즈|브랜드|음료|"
    r"가수|래퍼|배우|선수|정치인|유튜버|스트리머|등장인물|품종|무예|\d{4}년 출생|"
    r"の楽曲|のアルバム|のシングル|の映画|の漫画|のゲーム|のキャラクター|登場人物|テレビアニメ|"
    r"歌手|俳優|声優|企業|チェーン|商品|飲料|プラットフォーム|ウェブサイト|品種|馬\b|"
    r"歌曲|專輯|专辑|電影|电影|電視劇|电视剧|遊戲|游戏|公司|演員|演员|政治人物|網站|网站",
    re.I)


def is_meme(description: str) -> bool:
    """분류가 이미 '인터넷 밈' 이라고 했다. 설명이 노래·영화·사람·회사라고 반박할 때만 버린다."""
    return not _NOT_TERM.search(description or "")


CACHE = Path("data/wiki_memes.json")   # 받아 온 원천 자료. 거르기는 읽을 때 하므로 규칙을 고쳐도 다시 받지 않는다


def _api(lang: str, data: dict) -> dict:
    """위키백과 API 한 번. 429/5xx 는 기다렸다 다시 — 목록 받기는 급한 일이 아니다."""
    url = f"https://{lang}.wikipedia.org/w/api.php"
    for wait in (0, 5, 20, 60):
        if wait:
            time.sleep(wait)
        try:
            r = httpx.post(url, data={**data, "format": "json", "formatversion": "2"},
                           headers={"User-Agent": UA}, timeout=TIMEOUT)
            if r.status_code in (429, 500, 502, 503):
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError:
            continue
    raise RuntimeError(f"wikipedia {lang} 응답 없음")


def _members(lang: str, category: str, limit: int) -> list[str]:
    j = _api(lang, {"action": "query", "list": "categorymembers", "cmtitle": category,
                    "cmlimit": str(min(limit, 500)), "cmtype": "page"})
    return [m["title"] for m in j.get("query", {}).get("categorymembers", [])]


def clean_title(title: str) -> str | None:
    """문서 제목을 표제어 후보로. 목록·안내 문서와 '이름만으로는 뜻이 안 서는 것'을 버린다.

    괄호 주석은 그것이 '밈'일 때만 뗀다. "Anxiety (Doechii song)" 의 괄호를 떼면 남는 "Anxiety" 는
    아무 문장에나 걸리는 말이 되고, 게이트가 엉뚱한 근거로 통과시킨다 — 그래서 통째로 버린다.
    """
    if not title or any(s in title for s in SKIP):
        return None
    t, _, rest = title.partition(" (")
    t = t.strip()
    if rest and not OK_PAREN.match(rest.rstrip(")").strip()):
        return None
    if not t or len(t) > 40:
        return None
    if t.isdigit():                                   # 연도·숫자 문서
        return None
    if t.isascii() and t.isalpha() and len(t) <= 4:   # "Yee" — 너무 흔해 아무 데나 걸린다
        return None                                   # 숫자꼴("6-7")은 mentions() 가 밈 단서를 따로 요구하므로 살린다
    return t


def _descriptions(lang: str, titles: list[str]) -> dict[str, str]:
    """문서별 한 줄 설명. 위키백과가 스스로 '2025 internet meme' 인지 'song by Doechii' 인지 말해 준다."""
    out: dict[str, str] = {}
    for i in range(0, len(titles), 50):               # API 한 번에 50건
        j = _api(lang, {"action": "query", "prop": "description", "titles": "|".join(titles[i : i + 50])})
        for pg in j.get("query", {}).get("pages", []):
            out[pg.get("title", "")] = pg.get("description", "") or ""
        time.sleep(1.0)                               # 예의상 간격
    return out



def _simplified(titles: list[str]) -> set[str]:
    """간체로 쓴 중국어 제목. 대만·홍콩 표기와 다르면 간체다 — 중국 본토의 말은 목표 지역 밖이다(ADR 0001).
    간체·번체가 같은 글자로만 된 제목(三高男 등)은 가릴 수 없어 남긴다. 조사·게이트가 대만·홍콩 근거로 다시 거른다."""
    out: set[str] = set()
    for i in range(0, len(titles), 50):
        j = _api("zh", {"action": "query", "prop": "info", "inprop": "varianttitles", "titles": "|".join(titles[i : i + 50])})
        for pg in j.get("query", {}).get("pages", []):
            v, t = pg.get("varianttitles") or {}, pg.get("title", "")
            if v and t not in (v.get("zh-tw"), v.get("zh-hk")):
                out.add(t)
        time.sleep(1.0)                               # 예의상 간격
    return out


def _fetch_raw(langs: tuple[str, ...], per_category: int) -> list[dict]:
    """[{title, term, lang, description}] — 분류 구성원과 그 한 줄 설명. 거르지 않는다."""
    raw: list[dict] = []
    for lang in langs:
        titles: list[str] = []
        for cat in CATEGORIES.get(lang, []):
            try:
                titles += _members(lang, cat, per_category)
            except Exception:
                continue
        keep = [t for t in dict.fromkeys(titles) if clean_title(t)]
        if lang == "zh" and keep:
            simplified = _simplified(keep)
            keep = [t for t in keep if t not in simplified]
        desc = _descriptions(lang, keep) if keep else {}
        raw += [{"title": t, "term": clean_title(t), "lang": lang, "description": desc.get(t, "")} for t in keep]
    return raw


def known_memes(langs: tuple[str, ...] = ("en", "ko", "ja", "id", "zh"), per_category: int = 200, *, cache: bool = True) -> list[dict]:
    """[{term, lang, region, source_title, description}] — 노래·영화·사람이 아닌 밈 이름만."""
    raw: list[dict] = []
    if cache and CACHE.exists():
        raw = json.loads(CACHE.read_text(encoding="utf-8"))
    # 캐시에 없는 언어만 새로 받는다 — 언어판을 늘려도 이미 받은 것을 다시 받지 않는다
    missing = tuple(lang for lang in langs if not any(r.get("lang") == lang for r in raw))
    if missing:
        raw += _fetch_raw(missing, per_category)
        if cache and raw:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")

    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for r in raw:
        t, lang = r.get("term"), r.get("lang", "en")
        if not t or lang not in langs or (lang, t.lower()) in seen or not is_meme(r.get("description", "")):
            continue
        seen.add((lang, t.lower()))
        out.append({"term": t, "lang": lang, "region": LANG_REGION.get(lang, "US"),
                    "source_title": r.get("title", t), "description": r.get("description", "")})
    return out
