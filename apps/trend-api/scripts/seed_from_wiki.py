"""위키백과 밈 분류에서 '알려진 표현' 이름을 받아 후보 대기열에 넣는다.

지금 후보는 전부 '지금 뜨는 것'에서만 온다(트렌드·쇼츠·발굴). 반년 전에 정점을 찍은 밈은 대기열에 들어오지 못해,
이탈리안 브레인로트 계열이 한 건밖에 없었다(2026-09-16). 여기서는 **이름만** 받아 오고, 뜻·근거·검증은 기존
research 단계가 평소대로 만든다 — 사전을 위키로 채우는 게 아니라 조사할 거리를 위키에서 받는다.
홍콩 분류(香港網絡迷因·香港網絡文化·香港俚語)는 늘 함께 받아 홍콩 말로 두고, 영어 밈은 설명이 목표 지역을 대면 그 나라로 둔다(Plan 04).

  uv run scripts/seed_from_wiki.py --dry           # 무엇이 들어갈지 보기만
  uv run scripts/seed_from_wiki.py                 # 최근 분류(2024·2025)만
  uv run scripts/seed_from_wiki.py --all           # 전체 밈 분류까지
  uv run scripts/seed_from_wiki.py --region HK     # 이 나라로 정해진 것만 (HK·TH·ID …)
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.collectors import wiki_memes  # noqa: E402
from trend_agents.pipeline.match import unsafe  # noqa: E402
from trend_agents.storage import dictionary_store as ds  # noqa: E402
from trend_agents.storage import store as db  # noqa: E402

RECENT = {"en": ["Category:Internet memes introduced in 2025", "Category:Internet memes introduced in 2024"],
          "ko": ["분류:인터넷 밈"], "ja": ["Category:インターネット・ミーム"], "id": ["Kategori:Meme Internet"],
          "zh": ["Category:网络流行语"]}   # 목표 지역 대만·홍콩. 다른 언어판을 넣지 않은 이유는 collectors/wiki_memes.py


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--all", action="store_true", help="전체 밈 분류까지 (수백 건)")
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--lang", help="이 언어만 (en/ko/ja/id/zh). 조사 순서는 last_seen 이 최신인 것부터라,\n                                   먼저 조사시키고 싶은 언어를 나중에 넣으면 된다")
    ap.add_argument("--region", help="이 나라로 정해진 것만 (예: HK — 홍콩 분류와 광동어 제목, TH — 설명에 태국이 나온 영어 밈)")
    a = ap.parse_args()

    if not a.all:
        wiki_memes.CATEGORIES = RECENT
    rows = wiki_memes.known_memes()
    con = db.connect()

    new, known = [], 0
    if a.lang:
        rows = [r for r in rows if r["lang"] == a.lang]
    if a.region:
        rows = [r for r in rows if r["region"] == a.region]
    for r in rows[: a.limit]:
        if unsafe(r["term"]):          # 사전에 올릴 말이 아니다 — 조사 예산도 쓰지 않는다
            continue
        if ds.find_term(con, r["term"]):
            known += 1
            continue
        new.append(r)

    print(f"위키에서 {len(rows)}개 · 사전에 이미 있는 것 {known}개 · 후보로 넣을 것 {len(new)}개")
    print("  나라별:", dict(Counter(r["region"] for r in new).most_common()))
    for r in new[:15]:
        print(f"  - {r['term']} ({r['lang']})")
    if len(new) > 15:
        print(f"  … 외 {len(new) - 15}개")
    if a.dry:
        print("\n--dry 이므로 넣지 않았다.")
        return

    for r in new:
        # kind=meme 으로 표시해 둔다 — 승격 규칙(DICT_KINDS)이 읽는 자리다. 두 번째 등장을 기다리는 '밈' 규칙을 그대로 따른다.
        ds.upsert_candidate(con, r["term"], r["lang"], r["region"], "wiki", note=f"kind=meme wiki={r['source_title']}")
    print(f"\n후보 {len(new)}개 등록. 이제 research 단계가 평소대로 조사·검증한다 (uv run scripts/run_pipeline.py --stages research)")


if __name__ == "__main__":
    main()
