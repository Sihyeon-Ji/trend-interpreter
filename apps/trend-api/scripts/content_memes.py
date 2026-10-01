"""콘텐츠 하나에서 파생된 **밈만** 나라별로 모은다 (지식그래프 시험판 2판, 2026-10-01).
1판(위키 대표 분류 따라가기)은 시즌·등장인물·배우 문서만 나와 버렸다. 밈 쪽에서 출발한다:
- KR: 나무위키 '분류:<콘텐츠>' 문서 가운데 나무위키 밈 분류(wiki_catalog namu)에도 든 것 + 우리 사전에서 콘텐츠의 언어별 이름이 언급된 밈
- 영어권: Know Your Meme 하위 항목 — 그 항목 페이지가 'Part of a series on <콘텐츠>' 라고 적은 것만(제목·주소만 쓴다)
- 그 밖의 나라: Gemini + Google 검색이 출처와 함께 낸 후보 가운데, 출처 페이지에 밈 이름과 그 나라의 콘텐츠 이름이 둘 다 있는 것만
  uv run scripts/content_memes.py "Squid Game" squid-game "오징어 게임"
"""
from __future__ import annotations

import html
import json
import re
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.collectors import namuwiki  # noqa: E402
from trend_agents.pipeline import catalog  # noqa: E402
from trend_agents.pipeline.match import mentions  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

from trend_agents.config import BOT_UA  # noqa: E402
UA = {"User-Agent": BOT_UA}
LANG_REGION = {"ko": "KR", "ja": "JP", "zh": "TW", "zh-hant": "TW", "en": "US", "th": "TH", "id": "ID", "vi": "VN", "tl": "PH"}


def get(url: str, gap: float = 2.0) -> str:
    time.sleep(gap)
    try:
        r = httpx.get(url, headers=UA, timeout=25, follow_redirects=True)
        return r.text if r.status_code == 200 else ""
    except httpx.HTTPError:
        return ""


def plain(page: str) -> str:
    page = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page)))


def kym_children(slug: str, name: str) -> list[dict]:
    """하위 항목 후보 → 항목 페이지에 'Part of a series on <name>' 이 있는 것만."""
    cands: dict[str, str] = {}
    for page in range(1, 4):
        x = get(f"https://knowyourmeme.com/memes/subcultures/{slug}/children" + (f"/page/{page}" if page > 1 else ""))
        if not x:
            break
        for m in re.finditer(r'<a[^>]+href="(/memes/(?!subcultures)[a-z0-9\-]+)"[^>]*>(?:\s*<[^>]+>)*\s*([^<]{3,90})', x):
            cands.setdefault(m.group(1), html.unescape(m.group(2)).strip())
    out = []
    for path, title in cands.items():
        t = plain(get("https://knowyourmeme.com" + path))
        if re.search(r"Part of a series on\s+" + re.escape(name), t, re.I):
            out.append({"title": title, "url": "https://knowyourmeme.com" + path, "source": "Know Your Meme", "evidence": f"Part of a series on {name}"})
    return out


def korean(con, labels: dict, ko_name: str) -> list[dict]:
    namu_memes = {t for (t,) in con.execute("SELECT title FROM wiki_catalog WHERE source='namu'").fetchall()}
    docs, _ = namuwiki.category_page(ko_name)
    out = [{"title": d, "url": f"https://namu.wiki/w/{d}", "source": "나무위키", "evidence": f"분류:{ko_name} · 인터넷 밈 분류"} for d in docs if d in namu_memes]
    names = [v for v in labels.values() if v]
    for t in ds.list_terms(con, ("verified",)):
        m = ds.current_meaning(con, t.term_id)
        text = " ".join([m.definition or "", m.origin or "", m.nuance or ""]) if m else ""
        hit = next((n for n in names if mentions(text, n)), None)
        if hit and t.canonical not in names:
            out.append({"title": t.canonical, "term_id": t.term_id, "source": "사전", "evidence": f"뜻·유래에 '{hit}'", "region_of_term": sorted({u['region'] for u in ds.get_usage(con, t.term_id)})})
    return out


def gemini_local(con, name: str, labels: dict) -> list[dict]:
    """Gemini + Google 검색: 나라별 파생 밈 후보와 출처. 출처 페이지에 밈 이름·그 나라 콘텐츠 이름이 둘 다 있는 것만 받는다."""
    from google.genai import types

    from trend_agents.pipeline import gemini

    prompt = (f"'{name}' (작품)에서 파생되어 각 나라 인터넷에서 유행한 밈(유행어·짤·챌린지·패러디)을 찾아라. 나라: 일본, 대만·홍콩·중국, 태국, 인도네시아, 베트남, 필리핀, 미국.\n"
              "작품 자체·시즌·등장인물·배우·상품은 빼고 그 나라 사람들이 만든 밈만. 나라마다 최대 5개. 각 줄: 나라코드 | 그 나라에서 부르는 밈 이름(원어) | 한국어 한 줄 설명 | 그 밈을 설명한 웹 페이지 주소.\n"
              "확실하지 않으면 쓰지 마라.")
    resp, used = gemini.generate(con, prompt, types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())], temperature=0.2),
                                 model="gemini-3.5-flash", allow_local=False)
    text = resp.text or ""
    out = []
    for line in text.splitlines():
        parts = [p.strip(" *-") for p in line.split("|")]
        if len(parts) < 4 or not re.match(r"^[A-Z]{2}$", parts[0]):
            continue
        cc, meme, desc, url = parts[0], parts[1], parts[2], parts[3]
        url = (re.search(r"https?://\S+", url) or [None])[0] if not isinstance(re.search(r"https?://\S+", url), type(None)) else None
        if not url:
            continue
        page = plain(get(url, gap=1.0))
        local = [v for k, v in labels.items() if LANG_REGION.get(k) == cc] + [name]
        ok = bool(page) and mentions(page, meme) and any(mentions(page, n) for n in local)
        out.append({"region": cc, "title": meme, "desc": desc, "url": url, "source": "Gemini 검색", "verified_by_page": ok, "model": used})
    return out


def main() -> None:
    name, slug, ko_name = sys.argv[1], sys.argv[2], sys.argv[3]
    g = json.loads(Path(f"data/work/graph/{name}.json").read_text(encoding="utf-8"))
    labels = g["labels"]
    con = db.connect()
    res = {"name": name, "labels": labels, "KR": korean(con, labels, ko_name), "GLOBAL": kym_children(slug, name)}
    try:
        res["local"] = gemini_local(con, name, labels)
    except Exception as e:
        res["local_error"] = f"{type(e).__name__}: {e}"[:200]
    Path(f"data/work/graph/{slug}-memes.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("KR", len(res["KR"]), [x["title"] for x in res["KR"]])
    print("GLOBAL(KYM)", len(res["GLOBAL"]), [x["title"] for x in res["GLOBAL"]])
    for x in res.get("local", []):
        print("local", x["region"], x["title"], "| 출처 확인" if x["verified_by_page"] else "| 출처에 없음", x["url"][:70])
    if "local_error" in res:
        print("local_error", res["local_error"])


if __name__ == "__main__":
    main()
