"""데모 보드 — world.py 시뮬레이션에서 '사람이 기록한 상태'만 투영한다.

예전에는 여기서 난수로 태스크를 만들었다. 그러면 "ECHO-5 가 멈췄다"까지는 나와도
"왜"에는 답할 데이터가 없었다. 지금은 세계가 먼저 있고, 보드는 그 세계의 한 단면이다.

보드에는 **기록 오차가 일부러 들어 있다** — 실제로는 착수했는데 '할 일'로 남아 있거나,
완료 처리됐는데 PR 이 열려 있는 식이다. 그 어긋남을 찾아내는 것이 에이전트의 일이다.

SETUP.md 3: 등장인물은 전부 가상이다.

실행:
  python -m pmo_agent.seeds.board            data/seed_state.json 생성
  python -m pmo_agent.seeds.board --print    저장하지 않고 요약만
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import schedule
from pmo_agent.adapters.memory import STORE
from pmo_agent.seeds import world as world_mod

PEOPLE = [name for name, _login, _email in world_mod.PEOPLE]  # 가상 인물
PHASES = world_mod.PHASES


def build(today: dt.date | None = None, project: str = "ECHO", seed: int = 20260922) -> list:
    """이슈 목록 (Jira search() 응답과 같은 모양)."""
    return world_mod.to_board(world_mod.simulate(today, seed), project)["issues"]


def planted(today: dt.date | None = None) -> list:
    """보드에 심어 둔 기록 오차 — 테스트와 평가 케이스가 정답지로 쓴다."""
    return world_mod.to_board(world_mod.simulate(today))["planted"]


def write(path: str | None = None, today: dt.date | None = None, project: str = "ECHO") -> dict:
    """로컬 보드 파일에 저장. 기존 파일은 덮어쓴다."""
    issues = build(today, project)
    target = path or STORE
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(
            {
                "project": project,
                "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
                "issues": issues,
            },
            handle,
            ensure_ascii=False,
            indent=1,
        )
    return {"path": target, "count": len(issues)}


def describe(issues: list, today: dt.date) -> dict:
    tasks = schedule.from_jira_issues(issues)
    summary = schedule.summary(tasks, today)
    return {
        "태스크": len(issues),
        "담당자": sorted({t.assignee for t in tasks.values() if t.assignee}),
        "완료": summary["done"],
        "임계경로": len(summary["critical_path"]),
        "위험": len(summary["risks"]),
        "계획 완료": summary["planned_finish"],
        "예측 완료": summary["predicted_finish"],
    }


if __name__ == "__main__":
    today = dt.date.today()
    issues = build(today)
    print(json.dumps(describe(issues, today), ensure_ascii=False, indent=1))
    print("\n기록 오차:", json.dumps(planted(today), ensure_ascii=False))
    if "--print" not in sys.argv:
        result = write(today=today)
        print(f"\n저장: {result['path']} ({result['count']}건)")
        print("사용: PMO_BACKEND=memory 로 두면 tools/approve 가 이 보드를 본다.")
