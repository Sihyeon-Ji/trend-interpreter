"""expansion 칸에 들어간 '뜻 설명' 을 비운다.

expansion 은 줄임말 풀이 자리다 (자만추 → "자연스러운 만남 추구"). 그런데 모델이 근거 원문의 정의 문장을
통째로 넣었고, 화면에서 뜻 앞에 굵게 붙어 나왔다 (사용자 지적 2026-09-16).

뜻(definition)은 건드리지 않는다. 판(version)도 새로 만들지 않는다 — 잘못 담긴 칸 하나를 비우는 것이지
뜻이 바뀐 게 아니기 때문이다. 조사 단계에도 같은 규칙을 넣어 두었으니 다음부터는 애초에 들어오지 않는다.

  uv run scripts/fix_expansion.py --dry
  uv run scripts/fix_expansion.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.storage import sqlite_store as db  # noqa: E402

MAX_LEN = 40
MAX_WORDS = 8


def looks_like_definition(expansion: str) -> bool:
    """줄임말 풀이가 아니라 뜻 설명이다."""
    return len(expansion) > MAX_LEN or len(expansion.split()) > MAX_WORDS or "." in expansion[:-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    con = db.connect()
    rows = con.execute("SELECT meaning_id, json FROM meanings").fetchall()
    fixed = 0
    for mid, j in rows:
        d = json.loads(j)
        exp = d.get("expansion")
        if not exp or not looks_like_definition(exp):
            continue
        fixed += 1
        if fixed <= 10:
            print(f"  {mid}: {exp[:70]}")
        if not a.dry:
            d["expansion"] = None
            con.execute("UPDATE meanings SET json=? WHERE meaning_id=?", (json.dumps(d, ensure_ascii=False), mid))
    if not a.dry:
        con.commit()
    print(f"\n{'확인만 함' if a.dry else '비움'}: {fixed}개 판 / 전체 {len(rows)}개")


if __name__ == "__main__":
    main()
