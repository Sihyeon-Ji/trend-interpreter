"""콘텐츠 하나 → 나라(언어)별로 엮인 문서들 (지식그래프 시험판, 2026-10-01).

편집자가 이미 묶어 둔 것을 따라간다 — 모델 추정·임베딩 없이:
1. 위키데이터에서 콘텐츠의 QID 와 언어별 이름(같은 QID = 같은 것).
2. 콘텐츠의 대표 분류(P910) → 그 분류 항목의 언어별 위키백과 분류 이름(sitelinks).
3. 언어별 분류에 걸린 문서들 + 나무위키 '분류:<이름>' 문서들 → 그 나라에서 이 콘텐츠와 엮인 것.
4. 문서마다 우리 사전에 있는지(있으면 확인 여부·뜻)를 붙인다. 등장인물·회차·배우 문서가 섞이므로 밈인지는 사전·게이트가 가른다.
  uv run scripts/content_graph.py "Squid Game"
결과: data/work/graph/<이름>.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.collectors import namuwiki, wikipedia_category  # noqa: E402
from trend_agents.pipeline import catalog  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

from trend_agents.config import BOT_UA  # noqa: E402
UA = {"User-Agent": BOT_UA}
LANGS = {"ko": "KR", "ja": "JP", "zh": "TW", "en": "US", "th": "TH", "id": "ID", "vi": "VN", "tl": "PH", "ms": "MY"}


def wd(params: dict) -> dict:
    for _ in range(5):
        time.sleep(2)
        r = httpx.get("https://www.wikidata.org/w/api.php", params={**params, "format": "json"}, headers=UA, timeout=30)
        if r.status_code == 200 and r.text.startswith("{"):
            return r.json()
        time.sleep(int(r.headers.get("Retry-After", "30")) if r.headers.get("Retry-After", "").isdigit() else 30)
    return {}


def main() -> None:
    name = sys.argv[1]
    hit = wd({"action": "wbsearchentities", "search": name, "language": "en", "type": "item", "limit": 1}).get("search", [])
    if not hit:
        raise SystemExit("위키데이터에서 찾지 못했다")
    qid = hit[0]["id"]
    ent = wd({"action": "wbgetentities", "ids": qid, "props": "labels|claims|sitelinks"})["entities"][qid]
    labels = {k: v["value"] for k, v in ent.get("labels", {}).items() if k in LANGS or k in ("zh-hant", "zh-tw", "zh-hk")}
    cat_q = next((c["mainsnak"]["datavalue"]["value"]["id"] for c in ent.get("claims", {}).get("P910", []) if "datavalue" in c["mainsnak"]), None)
    cats = {}
    if cat_q:
        ce = wd({"action": "wbgetentities", "ids": cat_q, "props": "sitelinks"})["entities"][cat_q]
        cats = {k[:-4]: v["title"] for k, v in ce.get("sitelinks", {}).items() if k.endswith("wiki") and k[:-4] in LANGS}
    con = db.connect()
    out = {"name": name, "qid": qid, "labels": labels, "category_qid": cat_q, "by_lang": {}}
    for lang, cat in cats.items():
        docs = wikipedia_category.tree(lang, cat, depth=1, skip=catalog.PERSON_CAT.search)
        out["by_lang"][lang] = [{"title": t, **lookup(con, t)} for t in sorted(docs)]
    ko = labels.get("ko")
    if ko:
        docs, _subs = namuwiki.category_page(ko)
        out["by_lang"]["ko-namu"] = [{"title": t, **lookup(con, t)} for t in docs]
    path = Path("data/work/graph") / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{name} {qid} 이름 {labels}\n대표 분류 {cat_q}: {cats}")
    for lang, rows in out["by_lang"].items():
        inside = [r for r in rows if r["status"]]
        print(f"- {lang}: 문서 {len(rows)} · 사전에 있음 {len(inside)} · 예: {[r['title'] for r in rows[:8]]}")


def lookup(con, title: str) -> dict:
    t = ds.find_term(con, catalog.title_to_term(title) or title)
    if not t:
        return {"status": None}
    m = ds.current_meaning(con, t.term_id)
    return {"status": t.status, "term_id": t.term_id, "definition": (m.definition if m else "")[:120]}


if __name__ == "__main__":
    main()
