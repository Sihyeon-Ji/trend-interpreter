"""Gemini function calling 툴 레이어.
설계 원칙: 모델은 '무엇을 할지' 고르고 설명만 한다.
일정·지연 계산은 schedule.py(순수 파이썬)가, 실제 반영은 승인 후 jira 어댑터가 한다.
읽기 툴은 바로 실행, 쓰기 툴은 dry_run 결과(제안)만 돌려주고 사람이 승인해야 반영된다."""

from __future__ import annotations

import datetime as dt
import json

from pmo_agent import availability as avail_mod
from pmo_agent import capacity, schedule, signals
from pmo_agent.adapters.jira import Jira
from pmo_agent.env import env
from pmo_agent.ports import Board, Calendar, Repo

_j: Board | None = None


def jira() -> Board:
    """PM 도구 백엔드. PMO_BACKEND=memory 면 로컬 보드, 기본은 Jira.
    두 어댑터의 반환 모양이 같아서 이 위의 코드는 어느 쪽인지 알 필요가 없다."""
    global _j
    if _j is None:
        if env("PMO_BACKEND", "jira").lower() in ("memory", "local", "file"):
            from pmo_agent.adapters.memory import MemoryBoard

            _j = MemoryBoard(project=env("JIRA_PROJECT_KEY", "ECHO"))
        else:
            _j = Jira()
    return _j


_r: Repo | None = None


def repo() -> Repo:
    """코드 신호 백엔드. REPO_BACKEND=memory 면 로컬 저장소, 기본은 GitHub.
    보드 어댑터와 같은 방식이라 위쪽 코드는 어느 쪽인지 알 필요가 없다."""
    global _r
    if _r is None:
        if env("REPO_BACKEND", "github").lower() in ("memory", "local", "file"):
            from pmo_agent.adapters.memory_repo import MemoryRepo

            _r = MemoryRepo()
        else:
            from pmo_agent.adapters.github import GitHub

            _r = GitHub()
    return _r


_c: Calendar | None = None


def calendar() -> Calendar:
    """가용 시간 백엔드. CALENDAR_BACKEND=memory 면 로컬 캘린더, 기본은 MS Graph(Outlook)."""
    global _c
    if _c is None:
        if env("CALENDAR_BACKEND", "msgraph").lower() in ("memory", "local", "file"):
            from pmo_agent.adapters.memory_calendar import MemoryCalendar

            _c = MemoryCalendar()
        else:
            from pmo_agent.adapters.ms_calendar import MSCalendar

            _c = MSCalendar()
    return _c


def _availability() -> dict | None:
    """캘린더가 붙어 있으면 가용률 표를, 없으면 None(전원 온전히 가용)을 돌려준다.

    캘린더 연결 실패가 일정 계산 전체를 막으면 안 된다 — 없으면 없는 대로 계산한다.
    """
    try:
        return avail_mod.from_busy_hours(calendar().busy_hours(30))
    except Exception:
        return None


def _today(today: str = "") -> dt.date:
    """툴 인자로 받은 날짜 문자열 → date. 비었으면 오늘. 모델이 날짜를 지어내도 여기서 걸러진다."""
    return schedule.parse_date(today) or dt.date.today()


def _fetch(jql: str = "", limit: int = 200) -> dict:
    """Jira 이슈를 읽어 {key: Task} 로 변환.

    스케줄 계산 함수들의 공통 입구 — 테스트는 여기만 갈아끼우면 된다.
    """
    return schedule.from_jira_issues(
        jira().search(jql or f"project = {jira().project}", limit=limit)
    )


# ---- 실행 함수 (이름이 곧 Gemini 에 노출되는 함수명) ----
def list_tasks(status: str = "", assignee: str = "", limit: int = 50) -> dict:
    jql = [f"project = {jira().project}"]
    if status:
        jql.append(f'status = "{status}"')
    if assignee:
        jql.append(f'assignee = "{assignee}"')
    issues = jira().search(" AND ".join(jql) + " ORDER BY duedate ASC", limit=limit)
    deps = schedule.from_jira_issues(issues)
    return {
        "count": len(issues),
        "tasks": [
            {
                "key": i["key"],
                "summary": i["fields"]["summary"],
                "status": (i["fields"].get("status") or {}).get("name"),
                "assignee": ((i["fields"].get("assignee") or {}) or {}).get("displayName"),
                "duedate": i["fields"].get("duedate"),
                "points": i["fields"].get("customfield_10016"),
                "deps": deps[i["key"]].deps if i["key"] in deps else [],
            }
            for i in issues
        ],
    }


def get_task(key: str) -> dict:
    i = jira().issue(key)
    f = i["fields"]
    return {
        "key": i["key"],
        "summary": f["summary"],
        "status": (f.get("status") or {}).get("name"),
        "assignee": ((f.get("assignee") or {}) or {}).get("displayName"),
        "duedate": f.get("duedate"),
        "links": [
            {
                "type": link["type"]["name"],
                "inward": (link.get("inwardIssue") or {}).get("key"),
                "outward": (link.get("outwardIssue") or {}).get("key"),
            }
            for link in (f.get("issuelinks") or [])
        ],
    }


def analyze_schedule(today: str = "", limit: int = 200) -> dict:
    """전체 일정 분석 — 계획/예측 완료일, 임계경로, 지연 위험 목록.

    숫자는 전부 schedule.py 가 계산한다.
    """
    tasks = _fetch(limit=limit)
    if not tasks:
        return {"error": "태스크가 없다. 프로젝트 키와 시드 데이터를 확인하라."}
    try:
        return schedule.summary(tasks, _today(today))
    except schedule.CycleError as e:
        return {
            "error": str(e),
            "hint": "Blocks 링크가 순환한다. 일정 계산 전에 링크를 고쳐야 한다.",
        }


def simulate_delay(key: str, days: float, today: str = "") -> dict:
    """'이 태스크가 N영업일 밀리면 무엇이 얼마나 밀리는가' 시뮬레이션.

    여유(slack)로 흡수되는 부분은 전파되지 않는다.
    """
    tasks = _fetch()
    if key not in tasks:
        return {"error": f"{key} 를 찾을 수 없다.", "available": sorted(tasks)[:20]}
    try:
        return schedule.iso(schedule.propagate(tasks, key, float(days), _today(today)))
    except schedule.CycleError as e:
        return {"error": str(e)}


def analyze_capacity(today: str = "", limit: int = 200) -> dict:
    """담당자 용량을 반영한 '실현 가능한' 완료일. 의존성만 본 예측과 나란히 돌려준다.
    한 사람이 동시에 여러 건을 못 한다는 제약이 들어가므로 보통 더 늦고, 그게 현실이다."""
    tasks = _fetch(limit=limit)
    if not tasks:
        return {"error": "태스크가 없다."}
    try:
        return capacity.summary(tasks, _today(today), availability=_availability())
    except schedule.CycleError as e:
        return {"error": str(e)}


def suggest_rebalance(today: str = "", max_moves: int = 3) -> dict:
    """병목 담당자의 태스크를 누구에게 옮기면 완료일이 며칠 당겨지는지 계산한다.

    제안일 뿐 반영하지 않는다.
    """
    tasks = _fetch()
    if not tasks:
        return {"error": "태스크가 없다."}
    try:
        return schedule.iso(capacity.rebalance(tasks, _today(today), max_moves=int(max_moves)))
    except schedule.CycleError as e:
        return {"error": str(e)}


def analyze_signals(today: str = "", days: int = 14) -> dict:
    """보드 상태와 실제 코드 활동을 맞대 어긋남을 찾는다.
    '티켓은 진행 중인데 커밋이 없다', '완료인데 PR 이 열려 있다', 'PR 이 리뷰 대기 중이다' 등.
    보드만 봐서는 알 수 없는 것이라, 진척이 의심될 때 쓴다."""
    tasks = _fetch()
    if not tasks:
        return {"error": "태스크가 없다."}
    try:
        return signals.summary(tasks, repo().snapshot(100), _today(today), days=int(days))
    except Exception as e:
        return {
            "error": f"저장소를 읽지 못했다: {str(e)[:200]}",
            "hint": (
                "GITHUB_REPO 설정과 gh 인증을 확인하거나 REPO_BACKEND=memory 로 로컬 저장소를 쓴다."
            ),
        }


def propose_comment(key: str, text: str) -> dict:
    """담당자에게 남길 코멘트 제안 (즉시 반영되지 않음)."""
    return jira().comment(key, text, approve=False)


def propose_field_update(key: str, duedate: str = "", summary: str = "") -> dict:
    """마감일/요약 변경 제안 (즉시 반영되지 않음)."""
    fields = {}
    if duedate:
        fields["duedate"] = duedate
    if summary:
        fields["summary"] = summary
    return jira().set_fields(key, fields, approve=False)


def propose_transition(key: str, to_status: str) -> dict:
    """상태 전이 제안 (즉시 반영되지 않음)."""
    return jira().transition(key, to_status, approve=False)


REGISTRY = {
    f.__name__: f
    for f in (
        list_tasks,
        get_task,
        analyze_schedule,
        simulate_delay,
        analyze_capacity,
        suggest_rebalance,
        analyze_signals,
        propose_comment,
        propose_field_update,
        propose_transition,
    )
}

# ---- Gemini 선언 (google-genai types.FunctionDeclaration 호환 dict) ----
DECLARATIONS = [
    {
        "name": "list_tasks",
        "description": (
            "프로젝트의 태스크 목록을 마감일 순으로 조회한다. 상태/담당자로 필터 가능. deps 는 "
            "선행 태스크 키다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "assignee": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_task",
        "description": "태스크 하나의 상세와 의존관계(blocks 등)를 조회한다.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "예: ECHO-12"}},
            "required": ["key"],
        },
    },
    {
        "name": "analyze_schedule",
        "description": (
            "프로젝트 전체 일정을 계산한다. 계획 완료일·예측 완료일·지연 일수·임계경로·지연 위험 "
            "태스크와 그 근거를 돌려준다. 일정이나 지연을 묻는 질문에는 반드시 이 툴을 먼저 "
            "호출한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {"type": "string", "description": "기준일 YYYY-MM-DD. 비우면 오늘"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "simulate_delay",
        "description": (
            "특정 태스크가 N영업일 밀렸을 때 후행 태스크와 프로젝트 완료일이 얼마나 밀리는지 "
            "계산한다. '만약' 질문에 사용한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "days": {"type": "number", "description": "밀리는 영업일 수"},
                "today": {"type": "string"},
            },
            "required": ["key", "days"],
        },
    },
    {
        "name": "analyze_capacity",
        "description": (
            "담당자별 처리 용량과 캘린더(회의로 먹힌 시간)를 반영해 "
            "실현 가능한 완료일을 계산한다. "
            "의존성만 본 예측과의 차이, "
            "병목 담당자, 사람이 바빠서 대기 중인 태스크를 돌려준다. '누가 과부하인가', '일정이 "
            "정말 가능한가' 같은 질문에 쓴다."
        ),
        "parameters": {
            "type": "object",
            "properties": {"today": {"type": "string"}, "limit": {"type": "integer"}},
        },
    },
    {
        "name": "suggest_rebalance",
        "description": (
            "병목 담당자의 태스크를 다른 사람에게 옮겨 완료일을 당길 수 있는지 계산한다. 어떤 "
            "태스크를 누구에게 옮기면 며칠 당겨지는지 돌려준다. 제안일 뿐 반영되지 않는다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {"type": "string"},
                "max_moves": {"type": "integer", "description": "탐색할 이동 건수 (기본 3)"},
            },
        },
    },
    {
        "name": "analyze_signals",
        "description": (
            "보드 상태와 실제 코드 활동(커밋·PR)을 대조해 어긋난 태스크를 찾는다. 멈춰 있는 작업, "
            "조기 완료 처리, 리뷰 대기 PR, 기여 편중을 돌려준다. 진척이 실제로 나고 있는지 물을 때 "
            "쓴다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "today": {"type": "string"},
                "days": {"type": "integer", "description": "활동 집계 기간(일), 기본 14"},
            },
        },
    },
    {
        "name": "propose_comment",
        "description": (
            "담당자에게 남길 코멘트를 제안한다. 실제로 등록되지 않으며 사람 승인이 필요하다."
        ),
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "text": {"type": "string"}},
            "required": ["key", "text"],
        },
    },
    {
        "name": "propose_field_update",
        "description": "마감일 또는 요약 변경을 제안한다. 승인 전에는 반영되지 않는다.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "duedate": {"type": "string", "description": "YYYY-MM-DD"},
                "summary": {"type": "string"},
            },
            "required": ["key"],
        },
    },
    {
        "name": "propose_transition",
        "description": "상태 전이를 제안한다. 승인 전에는 반영되지 않는다.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "to_status": {"type": "string"}},
            "required": ["key", "to_status"],
        },
    },
]

SYSTEM = """너는 프로젝트 PMO 보조 에이전트다. 규칙:
1) 일정·지연·임계경로·부하·코드활동 숫자는 네가 만들지 않는다. analyze_schedule / simulate_delay /
analyze_capacity / suggest_rebalance / analyze_signals 의 응답 값만 인용한다. 계산이 필요하면 툴을
부르고, 툴을 못 부르면 모른다고 답한다.
2) 변경은 반드시 propose_* 툴로 '제안'만 한다. 직접 반영하지 않는다.
3) 근거를 태스크 키와 함께 제시한다 (예: ECHO-12가 ECHO-19를 block).
4) 확인이 필요하면 담당자에게 물을 질문을 한 문장으로 제안한다.
5) 완료일을 말할 때는 analyze_capacity 의 capacity_finish(사람 용량 반영)를 기준으로 답하고,
의존성만 본 예측과 다르면 그 차이를 함께 밝힌다.
답변은 한국어, 간결하게."""


def dispatch(name: str, args: dict) -> dict:
    fn = REGISTRY.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**(args or {}))
    except Exception as e:
        return {"error": str(e)[:300]}


if __name__ == "__main__":
    print(json.dumps(analyze_schedule(), ensure_ascii=False, indent=1))
