"""위키백과 검색·요약·조회 곡선. 키 없음. 급증 원인 조사에서 '이게 무엇인지'와 '언제부터 관심이 올랐는지'를 준다."""
from __future__ import annotations

from datetime import date, timedelta
from urllib.parse import quote

import re
import time
from difflib import SequenceMatcher

import httpx

from .wikipedia_top import UA

REGION_LANG = {"KR": "ko", "JP": "ja", "ID": "id", "TH": "th", "VN": "vi", "TW": "zh", "HK": "zh", "BR": "pt", "DE": "de", "MX": "es", "ES": "es", "AR": "es",
               "FR": "fr", "IT": "it", "TR": "tr", "SA": "ar", "EG": "ar"}


def lang_for(region: str) -> str:
    return REGION_LANG.get(region, "en")


def _get(url: str, params: dict | None, timeout: float) -> httpx.Response | None:
    """429·5xx 는 기다렸다 다시. 여러 표제어를 연달아 조사하면 위키백과가 429 를 낸다 (실측 09-16)."""
    for wait in (0, 3, 10):
        if wait:
            time.sleep(wait)
        try:
            r = httpx.get(url, params=params, headers={"User-Agent": UA}, timeout=timeout)
            if r.status_code in (429, 500, 502, 503):
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r
        except httpx.HTTPError:
            continue
    return None


def search(lang: str, query: str, limit: int = 3, timeout: float = 10.0) -> list[str]:
    r = httpx.get(f"https://{lang}.wikipedia.org/w/api.php", params={"action": "query", "list": "search", "srsearch": query, "srlimit": limit, "format": "json"},
                  headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return [h["title"] for h in r.json().get("query", {}).get("search", [])]


def summary(lang: str, title: str, timeout: float = 10.0) -> dict | None:
    r = _get(f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(title.replace(' ', '_'))}", None, timeout)
    if r is None or r.status_code != 200:
        return None
    j = r.json()
    return {"title": j.get("title", title), "extract": (j.get("extract") or "")[:600], "url": j.get("content_urls", {}).get("desktop", {}).get("page", "")}


FREE_LICENSE = re.compile(r"public domain|^cc[\s-]|cc0|creative commons", re.I)
# 표현 자체를 보여 주는 그림이 아니다 — 시세 그래프·로고·지도 따위
# "$CHILLGUY first month.png" 처럼 $ 로 시작하면 코인 시세 그래프다 — 표현을 보여 주는 그림이 아니다.
_NOT_PORTRAIT = re.compile(r"chart|graph|plot|price|logo|map|diagram|screenshot of (the )?(page|site)|File:\$", re.I)


def free_image(lang: str, title: str, term: str = "") -> dict | None:
    """문서에 딸린 그림 중 **자유 라이선스** 인 것 하나. 없으면 None.

    위키백과 그림은 두 갈래다. 위키미디어 공용(commons, imagerepository="shared")에 있는 것은 자유 라이선스라
    출처를 밝히고 쓸 수 있고, 영어판에 직접 올라온 것(upload.wikimedia.org/wikipedia/en/…)은 공정이용이라
    우리가 가져다 쓰면 안 된다 — 실측(09-16): Hawk tuah·Chill Guy 그림이 후자, Ballerina Cappuccina 는 퍼블릭 도메인.
    """
    r = _get(f"https://{lang}.wikipedia.org/w/api.php",
             {"action": "query", "prop": "images", "titles": title, "imlimit": "12", "format": "json", "formatversion": "2"}, 15.0)
    if r is None:
        return None
    try:
        pages = r.json().get("query", {}).get("pages", [])
    except ValueError:
        return None
    files = [i["title"] for i in ((pages[0].get("images") if pages else None) or [])
             if i["title"].lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))]
    if not files:
        return None
    # 파일 이름이 이 표현을 가리킬 때만 쓴다. 상위 문서에 딸린 다른 캐릭터 그림을 내주면 틀린 그림이 된다
    # (실측 09-16: "Bombardiro Crocodilo" 에 "Ballerina Cappuccina.png" 가 붙었다).
    # 파일 이름은 철자가 흔들린다("Cappucino assasino.webp" ↔ "Cappuccino Assassino") — 비슷한 정도로 본다.
    key = re.sub(r"[^a-z0-9]", "", term.lower())
    def _close(f: str) -> bool:
        stem = re.sub(r"^file:|\.[a-z]{3,4}$", "", f.lower())
        stem = re.sub(r"[^a-z0-9]", "", stem)
        return bool(key) and (key in stem or SequenceMatcher(None, key, stem).ratio() >= 0.75)

    files = [f for f in files if _close(f) and not _NOT_PORTRAIT.search(f)]
    if not files:
        return None

    for f in files[:6]:
        rr = _get(f"https://{lang}.wikipedia.org/w/api.php",
                  {"action": "query", "prop": "imageinfo", "iiprop": "extmetadata|url",
                   "iiurlwidth": "480", "titles": f, "format": "json", "formatversion": "2"}, 15.0)
        if rr is None:
            continue
        try:
            pg = (rr.json().get("query", {}).get("pages") or [{}])[0]
        except ValueError:
            continue
        if pg.get("imagerepository") != "shared":      # 공용이 아니면 공정이용 — 쓰지 않는다
            continue
        ii = (pg.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        lic = (md.get("LicenseShortName") or {}).get("value", "")
        if not FREE_LICENSE.search(lic):
            continue
        return {"url": ii.get("thumburl") or ii.get("url", ""), "full_url": ii.get("url", ""),
                "license": lic, "attribution": re.sub(r"<[^>]+>", "", (md.get("Artist") or {}).get("value", ""))[:120],
                "source_url": ii.get("descriptionurl", ""), "file": f}
    return None


def article_text(lang: str, title: str, timeout: float = 15.0) -> str:
    """문서 본문 평문. 요약(앞 600자)에 없는 이름을 찾을 때 쓴다 —
    개별 밈 문서는 대개 상위 문서로 넘어가고, 이름은 본문 중간 목록에 있다."""
    r = _get(f"https://{lang}.wikipedia.org/w/api.php",
             {"action": "query", "prop": "extracts", "explaintext": "1", "redirects": "1",
              "titles": title, "format": "json", "formatversion": "2"}, timeout)
    if r is None:
        return ""
    pages = r.json().get("query", {}).get("pages", [])
    return (pages[0].get("extract") or "") if pages else ""


def pageviews(lang: str, title: str, days: int = 14, timeout: float = 10.0) -> list[tuple[str, int]]:
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    r = httpx.get(
        f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/user/{quote(title.replace(' ', '_'))}/daily/{start:%Y%m%d}/{end:%Y%m%d}",
        headers={"User-Agent": UA}, timeout=timeout)
    if r.status_code != 200:
        return []
    return [(it["timestamp"][:8], it["views"]) for it in r.json().get("items", [])]
