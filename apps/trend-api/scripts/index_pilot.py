"""색인 시험판 (2026-10-06): 작품 셋(오징어 게임·더 글로리·스파이 패밀리)의 나무위키·위키백과 문서를 링크로 두 단계까지 모아 따로 색인한다.
'그 자리에서 읽기'(지금 챗봇)와 '색인에서 찾기'를 같은 질문으로 견주는 데만 쓴다(scripts/index_compare.py).
Know Your Meme 은 약관 때문에 제목만 조각으로 넣는다.
  uv run scripts/index_pilot.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from trend_agents.pipeline import doc_index as D  # noqa: E402
from trend_agents.pipeline import web_tools as W  # noqa: E402

PILOT = Path(__file__).resolve().parents[1] / "data" / "index-pilot.db"
NAMU_SEEDS = ["오징어 게임", "오징어 게임/흥행 및 파급력", "오징어 게임/등장인물", "오징어 게임/탐구", "오징어 게임/평가",
              "더 글로리", "더 글로리/등장인물", "더 글로리/탐구", "더 글로리/평가", "SPY×FAMILY", "SPY×FAMILY/등장인물", "SPY×FAMILY(애니메이션)"]
WIKI = ["https://en.wikipedia.org/wiki/Squid_Game", "https://ja.wikipedia.org/wiki/イカゲーム", "https://zh.wikipedia.org/wiki/魷魚遊戲系列",
        "https://th.wikipedia.org/wiki/สควิดเกม_เล่นลุ้นตาย", "https://id.wikipedia.org/wiki/Squid_Game", "https://vi.wikipedia.org/wiki/Trò_chơi_con_mực",
        "https://en.wikipedia.org/wiki/The_Glory_(TV_series)", "https://ja.wikipedia.org/wiki/ザ・グローリー_～輝かしき復讐～", "https://zh.wikipedia.org/wiki/黑暗榮耀",
        "https://en.wikipedia.org/wiki/Spy_×_Family", "https://ja.wikipedia.org/wiki/SPY×FAMILY", "https://zh.wikipedia.org/wiki/SPY×FAMILY",
        "https://en.wikipedia.org/wiki/Squid_Game_season_2", "https://en.wikipedia.org/wiki/Squid_Game_season_3", "https://en.wikipedia.org/wiki/Anya_Forger"]
KYM = ["squid-game", "spy-x-family"]
MAX_NAMU = 220


def follow(url: str) -> list[str]:
    """'자세한 내용은 X 문서' 의 X 와 하위 문서."""
    text = re.sub(r"\s+", " ", W.page_text(url))
    return [u for x, u in W.page_links(url) if "namu.wiki/w/" in u and (f"자세한 내용은 {x}" in text or u.startswith(url + "/"))]


def main() -> None:
    idx = D.connect(PILOT)
    namu = [W.canon(f"https://namu.wiki/w/{t}") for t in NAMU_SEEDS]
    seen = list(dict.fromkeys(namu))
    for depth in range(2):
        nxt = []
        for u in list(seen):
            if len(seen) + len(nxt) >= MAX_NAMU:
                break
            nxt += [v for v in follow(u) if v not in seen and v not in nxt]
        seen += nxt[:MAX_NAMU - len(seen)]
        print(f"나무위키 {depth + 1}단계까지 {len(seen)}개", flush=True)
    urls = seen + [W.canon(u) for u in WIKI]
    for i, u in enumerate(urls, 1):
        if not idx.execute("SELECT 1 FROM docs WHERE url=? AND fetched_at IS NOT NULL", (u,)).fetchone():
            r = D.index_one(idx, u)
            if i % 20 == 0 or r not in ("new", "same"):
                print(f"  {i}/{len(urls)} {r} {u[:70]}", flush=True)
    import numpy as np

    for slug in KYM:                                   # 제목만
        for k in W.kym_children(slug).get("results", []):
            u = k["url"]
            if idx.execute("SELECT 1 FROM docs WHERE url=?", (u,)).fetchone() or "/subcultures/" in u:
                continue
            title = re.sub(r"\s*\|\s*Know Your Meme\s*$", "", W.page_title(u)) or k["title"]
            cid = idx.execute("INSERT INTO chunks(url, ord, heading, text) VALUES (?,?,?,?)", (u, 0, "", f"{title} (Know Your Meme, {slug})")).lastrowid
            idx.execute("INSERT INTO chunk_vec(id, emb) VALUES (?,?)", (cid, np.asarray(D.embed([title])[0], dtype=np.float32).tobytes()))
            idx.execute("INSERT INTO docs(url, site, lang, title, fetched_at, n_chunks) VALUES (?,?,?,?,datetime('now'),1)", (u, "kym", "en", title))
            idx.commit()
    print(D.stats(idx))


if __name__ == "__main__":
    main()
