"""가상 저장소 — world.py 시뮬레이션에서 '실제로 한 것'만 투영한다.

보드는 사람이 적은 것이라 틀릴 수 있지만, 커밋과 PR 은 기계가 남긴 사실이다.
그래서 둘을 맞대면 어긋남이 드러난다 — 그게 signals.py 가 찾는 것이다.

커밋은 세계에서 그 사람이 **실제로 그 태스크를 민 날**에만 생긴다.
회의로 하루가 날아간 날에는 커밋이 없다. 그 공백이 곧 "왜 진도가 안 나갔나"의 근거다.

읽기 전용 데이터다 — 이 모듈은 아무것도 푸시하지 않는다.

실행:
  python -m pmo_agent.seeds.repo            data/repo_state.json 생성
  python -m pmo_agent.seeds.repo --print    저장하지 않고 요약만
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent.adapters.memory_repo import STORE
from pmo_agent.seeds import world as world_mod

REPO = "echo-team/echo-pmo-demo"
LOGIN = {name: login for name, login, _email in world_mod.PEOPLE}
EMAIL = {name: email for name, _login, email in world_mod.PEOPLE}


def build(today: dt.date | None = None, seed_value: int = 20260922) -> dict:
    """저장소 스냅샷. planted 에는 **보드와 맞대야 드러나는 어긋남까지** 담는다.

    review_waiting 은 저장소만 봐도 알 수 있지만, undeclared_progress 와
    done_with_open_pr 은 보드 상태를 함께 봐야 판정된다. 정답지는 한 곳에 모아 둔다.
    """
    world = world_mod.simulate(today, seed_value)
    board = world_mod.to_board(world)
    data = world_mod.to_repo(world, board, REPO)
    data["planted"] = board["planted"] + data["planted"]
    return data


def write(path: str | None = None, today: dt.date | None = None) -> dict:
    data = build(today)
    target = path or STORE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1)
    return {
        "path": target,
        "commits": len(data["commits"]),
        "pulls": len(data["pulls"]),
        "planted": len(data["planted"]),
    }


def describe(data: dict) -> dict:
    return {
        "저장소": data["repo"],
        "커밋": len(data["commits"]),
        "PR": len(data["pulls"]),
        "브랜치": len(data["branches"]),
        "심어둔 어긋남": data["planted"],
    }


if __name__ == "__main__":
    data = build()
    print(json.dumps(describe(data), ensure_ascii=False, indent=1))
    if "--print" not in sys.argv:
        result = write()
        print(
            f"\n저장: {result['path']}  "
            f"(커밋 {result['commits']} · PR {result['pulls']} · 어긋남 {result['planted']})"
        )
        print("사용: REPO_BACKEND=memory 로 두면 signals 가 이 저장소를 본다.")
