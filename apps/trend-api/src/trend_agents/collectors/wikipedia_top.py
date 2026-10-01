"""위키백과 페이지뷰 API — 언어판별 일간 조회 상위. 키 없음, User-Agent 만."""
from __future__ import annotations

from datetime import date, timedelta

import httpx

from ..schemas import WikiTop

from ..config import BOT_UA as UA  # noqa: E402
SKIP_PREFIX = ("위키백과:", "특수:", "파일:", "틀:", "분류:", "Special:", "Wikipedia:", "File:", "Template:", "Category:", "Portal:",
               "特別:", "Wikipedia:", "ファイル:", "Template:", "Istimewa:", "Wikipedia:", "Berkas:", "พิเศษ:", "วิกิพีเดีย:", "Đặc_biệt:", "Wikipedia:")
SKIP_TITLES = {"대문", "Main_Page", "メインページ", "Halaman_Utama", "หน้าหลัก", "Trang_Chính", "Wikipedia:首页", "首页", "Wikipédia:Página_principal", "Wikipedia:Hauptseite", "Wikipedia:Portada"}
# 언어판 ↔ 대표 국가 (보드에서 지역 신호로 쓸 때)
LANG_REGION = {"ko": "KR", "ja": "JP", "id": "ID", "th": "TH", "vi": "VN", "zh": "TW", "en": "US", "pt": "BR", "de": "DE", "es": "MX", "hi": "IN"}


def top_articles(lang: str, day: date | None = None, limit: int = 40, timeout: float = 15.0) -> list[WikiTop]:
    # 위키미디어는 UTC 하루가 끝나고 몇 시간 뒤에 집계를 올린다 → 전날치가 404 면 이틀 전
    for back in ([1, 2] if day is None else [0]):
        d = day or (date.today() - timedelta(days=back))
        url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/{d:%Y/%m/%d}"
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=timeout)
        if r.status_code == 404 and day is None and back == 1:
            continue
        r.raise_for_status()
        break
    out: list[WikiTop] = []
    for a in r.json()["items"][0]["articles"]:
        t = a["article"]
        if t.startswith(SKIP_PREFIX) or t in SKIP_TITLES or t.endswith("Main_Page"):
            continue
        out.append(WikiTop(lang=lang, date=d, rank=len(out) + 1, article=t.replace("_", " "), views=a["views"]))
        if len(out) >= limit:
            break
    return out
