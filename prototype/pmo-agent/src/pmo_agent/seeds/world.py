"""데모 세계 — 하나의 이야기에서 모든 도구 데이터를 파생한다.

지금까지 보드·저장소·캘린더 시드를 따로 만들었다. 각자는 그럴듯했지만 **하나의 이야기가 없었다.**
그래서 "ECHO-5 가 20일째 멈췄다"까지는 나와도 "왜"에는 아무 데이터도 답하지 못했다.

이 모듈은 하루 단위로 프로젝트를 굴린다:

    각자에게 회의를 배정한다 → 남은 시간에 자기 태스크를 민다 → 사건이 터지면 막힌다

그 결과가 `World.facts` — **실제로 일어난 일**이다. 도구 데이터는 전부 여기서 투영된다:

    board     사람이 **기록한** 상태   (실제와 어긋나는 부분이 곧 신호다)
    repo      실제로 **한** 것          (커밋·PR)
    calendar  시간이 **간** 곳          (과거·미래 회의)

`World.truths` 는 정답지다. "무엇이 진짜 원인인가"를 적어 두고, 테스트가
에이전트 계산이 그걸 찾아내는지 검사한다 — 팀 워크플로 문서가 요구하는 성공/실패 케이스가 이것이다.

고정 시드라 몇 번을 돌려도 같은 세계가 나온다.

실행:
  python -m pmo_agent.seeds.world            요약 출력
  python -m pmo_agent.seeds.world --facts    날짜별 기록까지
"""

from __future__ import annotations

import datetime as dt
import json
import random
import sys
from dataclasses import dataclass, field

from pmo_agent import availability as av
from pmo_agent import schedule

PEOPLE = [
    ("한서준", "seojun-h", "seojun@echo.test"),
    ("민아름", "areum-m", "areum@echo.test"),
    ("오태경", "tk-oh", "taekyung@echo.test"),
    ("유하늘", "haneul-y", "haneul@echo.test"),
]

PHASES = [
    (
        "기획",
        [
            "요구사항 인터뷰",
            "사용자 시나리오 정리",
            "성공 지표 정의",
            "경쟁 제품 조사",
            "범위 확정",
            "리스크 목록 작성",
            "일정 초안",
        ],
    ),
    (
        "설계",
        [
            "정보구조 설계",
            "화면 흐름 설계",
            "데이터 모델 설계",
            "API 명세 작성",
            "인증 방식 결정",
            "에러 처리 규칙",
            "디자인 시스템 정리",
        ],
    ),
    (
        "구현",
        [
            "프로젝트 스캐폴딩",
            "인증 구현",
            "목록 화면 구현",
            "상세 화면 구현",
            "검색 구현",
            "알림 구현",
            "설정 화면 구현",
            "API 연동",
            "데이터 마이그레이션",
            "권한 처리",
            "로깅 추가",
            "성능 튜닝",
        ],
    ),
    (
        "검증",
        [
            "단위 테스트 보강",
            "통합 테스트",
            "브라우저 테스트",
            "접근성 점검",
            "부하 테스트",
            "보안 점검",
            "버그 수정 1차",
            "버그 수정 2차",
        ],
    ),
    (
        "출시",
        [
            "릴리스 노트 작성",
            "배포 리허설",
            "운영 문서화",
            "모니터링 대시보드",
            "출시 점검 회의",
            "출시",
        ],
    ),
]

BACK_DAYS = 18  # 오늘 기준 과거 영업일
FWD_DAYS = 25  # 미래 영업일 (캘린더용)

RECURRING = ("팀 정기 회의", 1.0)  # 월요일, 전원
PERSONAL = [("1:1", 0.5), ("스프린트 리뷰", 1.0), ("설계 리뷰", 1.5), ("고객 미팅", 2.0)]
INCIDENT_MEETING = ("장애 대응", 3.0)
WORKSHOP = ("전사 워크숍", av.WORKDAY_HOURS)


@dataclass
class Person:
    name: str
    login: str
    email: str


@dataclass
class Task:
    key: str
    phase: str
    title: str
    points: float
    owner: str
    deps: list = field(default_factory=list)
    done_on: dt.date | None = None
    started_on: dt.date | None = None
    progress: float = 0.0

    @property
    def summary(self) -> str:
        return f"[{self.phase}] {self.title}"

    @property
    def done(self) -> bool:
        return self.done_on is not None


@dataclass
class World:
    """시뮬레이션 결과. 도구 데이터는 전부 여기서 나온다."""

    today: dt.date
    people: list
    tasks: dict
    facts: list  # {"day", "who", "kind", "key", "hours", "detail"}
    truths: list  # 정답지 — 무엇이 진짜 원인인가
    incident: dict

    def by_day(self, kind: str = "") -> dict:
        out: dict[str, list] = {}
        for f in self.facts:
            if kind and f["kind"] != kind:
                continue
            out.setdefault(f["day"], []).append(f)
        return out

    def worked_on(self, key: str) -> list:
        return [f for f in self.facts if f["kind"] == "work" and f["key"] == key]


def _tasks(project: str) -> dict:
    """태스크 목록. 같은 단계 안에서 일부는 직렬, 단계 사이는 마지막 → 첫 번째로 잇는다."""
    rnd = random.Random(7)
    out: dict[str, Task] = {}
    n, prev_last = 0, None
    for phase, titles in PHASES:
        keys: list[str] = []
        for i, title in enumerate(titles):
            n += 1
            key = f"{project}-{n}"
            deps = []
            if i > 0 and rnd.random() < 0.55:
                deps.append(keys[-1])
            if i == 0 and prev_last:
                deps.append(prev_last)
            out[key] = Task(
                key=key,
                phase=phase,
                title=title,
                points=float(rnd.choice([1, 2, 2, 3, 3, 5, 8])),
                owner=PEOPLE[n % len(PEOPLE)][0],
                deps=deps,
            )
            keys.append(key)
        prev_last = keys[-1]
    return out


_CACHE: dict[tuple, World] = {}


def simulate(today: dt.date | None = None, seed_value: int = 20260922) -> World:
    """하루씩 굴린다. 회의가 먼저 시간을 먹고, 남은 시간으로 태스크를 민다.

    같은 인자면 같은 세계를 돌려준다 — 보드·저장소·캘린더가 서로 다른 세계를 보면
    애써 만든 정합성이 깨진다.
    """
    key = (today or dt.date.today(), seed_value)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    return _CACHE.setdefault(key, _simulate(*key))


def _simulate(today: dt.date, seed_value: int) -> World:
    rnd = random.Random(seed_value)
    people = [Person(*p) for p in PEOPLE]
    tasks = _tasks("ECHO")
    names = [p.name for p in people]

    # 근본 원인: 외부 IdP 스펙이 바뀌어 인증 구현이 멈춘다.
    # 이것이 검증 단계 전체를 밀어내는 출발점이다.
    blocked_key = next(k for k, t in tasks.items() if t.title == "인증 구현")
    # 사건 대상은 덩치가 있어야 한다. 1포인트짜리가 막히면 풀리자마자 끝나
    # '지연됐다'는 이야기가 성립하지 않는다.
    tasks[blocked_key].points = 8.0
    incident = {
        "key": blocked_key,
        "owner": tasks[blocked_key].owner,
        "title": "외부 IdP 스펙 변경",
        "day": "",  # 태스크가 착수 가능해진 날 — 아래 루프에서 정해진다
        "blocked_days": 8,
        "detail": "인증 공급자가 토큰 형식을 바꿔 재설계가 필요해졌다",
    }
    block_from: dt.date | None = None
    block_to: dt.date | None = None

    # 방치: 착수만 하고 돌아오지 않는 태스크. 막힘과 달리 아무도 알아채지 못한다.
    # 대상은 park_from 시점에 '실제로 손대고 있던' 것 중에서 고른다 —
    # 미리 정해 두면 그 태스크가 아직 시작도 안 했을 수 있다.
    parked_key = ""
    park_from = schedule.add_workdays(today, -7)

    facts: list[dict] = []
    for offset in range(-BACK_DAYS, FWD_DAYS + 1):
        day = schedule.add_workdays(today, offset)
        iso = day.isoformat()
        future = offset > 0

        meetings = _meetings(day, offset, names, incident, rnd)
        for m in meetings:
            facts.append({**m, "day": iso, "kind": "meeting", "key": ""})

        if future:
            continue  # 미래는 회의만 만든다 — 작업은 예측의 몫이지 기록이 아니다

        if not parked_key and day >= park_from:
            live = [t for t in tasks.values() if t.progress > 0 and not t.done]
            if live:
                parked_key = min(live, key=lambda t: (t.progress, t.key)).key

        for person in people:
            spent = sum(m["hours"] for m in meetings if m["who"] == person.name)
            free = max(0.0, 1.0 - spent / av.WORKDAY_HOURS)
            if free <= 0.05:
                continue
            # 사건은 '그 태스크를 실제로 잡으려는 순간'에 터진다.
            # 단순히 착수 가능해진 날에 터뜨리면, 담당자 차례가 오기 전에 기간이 끝나 버린다.
            blocking = (
                block_from is not None and block_to is not None and block_from <= day < block_to
            )
            key = _next_task(
                tasks, person.name, blocked_key, blocking, parked_key, bool(parked_key)
            )
            if block_from is None and key == blocked_key:
                block_from = day
                block_to = schedule.add_workdays(day, incident["blocked_days"])
                incident["day"] = day.isoformat()
                blocking, key = True, None
            if key is None:
                if blocking and tasks[blocked_key].owner == person.name:
                    facts.append(
                        {
                            "day": iso,
                            "who": person.name,
                            "kind": "blocked",
                            "key": blocked_key,
                            "hours": round(free * av.WORKDAY_HOURS, 2),
                            "detail": incident["title"],
                        }
                    )
                continue
            task = tasks[key]
            if task.started_on is None:
                task.started_on = day
            task.progress += free
            facts.append(
                {
                    "day": iso,
                    "who": person.name,
                    "kind": "work",
                    "key": key,
                    "hours": round(free * av.WORKDAY_HOURS, 2),
                    "detail": task.title,
                }
            )
            if task.progress >= task.points:
                task.done_on = day
                facts.append(
                    {
                        "day": iso,
                        "who": person.name,
                        "kind": "done",
                        "key": key,
                        "hours": 0.0,
                        "detail": task.title,
                    }
                )

    truths = _truths(tasks, facts, incident, today, parked_key)
    return World(today, people, tasks, facts, truths, incident)


def _meetings(day: dt.date, offset: int, names: list, incident: dict, rnd) -> list:
    """그 날의 회의. 사건 기간에는 담당자에게 장애 대응이 더 붙는다."""
    out = []
    if day.weekday() == 0:
        out += [
            {"who": n, "hours": RECURRING[1], "detail": RECURRING[0], "start": "10:00"}
            for n in names
        ]
    if offset == 6:  # 앞으로 6영업일 뒤, 하루가 통째로 날아간다
        out += [
            {"who": n, "hours": WORKSHOP[1], "detail": WORKSHOP[0], "start": "09:00"} for n in names
        ]
        return out
    in_incident = incident["day"] <= day.isoformat() and offset < 0
    for n in names:
        if in_incident and n == incident["owner"] and rnd.random() < 0.6:
            out.append(
                {
                    "who": n,
                    "hours": INCIDENT_MEETING[1],
                    "detail": INCIDENT_MEETING[0],
                    "start": "14:00",
                }
            )
            continue
        if rnd.random() < (0.7 if n == incident["owner"] else 0.28):
            title, hours = rnd.choice(PERSONAL)
            out.append(
                {
                    "who": n,
                    "hours": hours,
                    "detail": title,
                    "start": rnd.choice(["11:00", "13:00", "16:00"]),
                }
            )
    return out


def _next_task(tasks, owner, blocked_key, blocking, parked_key="", parked=False) -> str | None:
    """그 사람이 지금 밀 수 있는 태스크. 선행이 끝났고, 막히지 않은 것.

    막힌 태스크가 차례면 다음으로 넘어가지 않고 멈춘다 — 실제로도 담당자는
    자기 차례 작업이 막히면 그 앞에서 시간을 보낸다. 그 멈춤이 곧 신호다.
    """
    for key, task in tasks.items():
        if task.owner != owner or task.done:
            continue
        if any(not tasks[d].done for d in task.deps if d in tasks):
            continue
        if key == blocked_key and blocking:
            return None
        if key == parked_key and parked:
            continue  # 방치 — 막힌 게 아니라 손을 놓았다. 다음 일로 넘어간다
        return key
    return None


def _truths(tasks: dict, facts: list, incident: dict, today: dt.date, parked_key: str) -> list:
    """정답지 — 데이터에 심어 둔 '진짜 원인'. 테스트와 평가 케이스가 이걸 쓴다."""
    out = [
        {
            "kind": "root_cause",
            "key": incident["key"],
            "cause": incident["title"],
            "detail": incident["detail"],
            "since": incident["day"],
            "expect": "이 태스크가 멈춘 원인이 회의록과 캘린더 양쪽에 남아 있어야 한다",
        }
    ]

    # 일정 예측이 소비하는 건 '앞으로의' 회의다. 과거 회의는 왜 늦었는지를 설명하고,
    # 미래 회의는 앞으로 얼마나 쓸 수 있는지를 정한다 — 정답지는 후자로 잡는다.
    horizon = schedule.add_workdays(today, 10).isoformat()
    load: dict[str, float] = {}
    for f in facts:
        if f["kind"] == "meeting" and today.isoformat() <= f["day"] <= horizon:
            load[f["who"]] = load.get(f["who"], 0.0) + f["hours"]
    if load:
        who = max(load, key=lambda n: load[n])
        out.append(
            {
                "kind": "meeting_overload",
                "assignee": who,
                "hours": round(load[who], 1),
                "window_days": 10,
                "expect": "앞으로 회의가 가장 많은 사람이 가용 시간이 가장 적어야 한다",
            }
        )

    parked = tasks.get(parked_key)
    if parked and parked.started_on and not parked.done:
        out.append(
            {
                "kind": "stalled",
                "key": parked.key,
                "started": parked.started_on.isoformat(),
                "expect": "착수만 하고 방치된 태스크가 보드-코드 대조에서 잡혀야 한다",
            }
        )
    return out


def describe(world: World) -> dict:
    done = [t for t in world.tasks.values() if t.done]
    work = [f for f in world.facts if f["kind"] == "work"]
    meet = [f for f in world.facts if f["kind"] == "meeting"]
    blocked = [f for f in world.facts if f["kind"] == "blocked"]
    return {
        "기간": f"과거 {BACK_DAYS}영업일 ~ 미래 {FWD_DAYS}영업일",
        "태스크": f"{len(done)}/{len(world.tasks)} 완료",
        "작업 기록": len(work),
        "회의": len(meet),
        "막힌 날": len(blocked),
        "사건": f"{world.incident['title']} ({world.incident['day']}부터 "
        f"{world.incident['blocked_days']}영업일, {world.incident['key']})",
        "정답지": world.truths,
    }


if __name__ == "__main__":
    w = simulate()
    print(json.dumps(describe(w), ensure_ascii=False, indent=1))
    if "--facts" in sys.argv:
        print("\n날짜별 기록 (앞 30건):")
        for f in w.facts[:30]:
            print(f"  {f['day']}  {f['who']:<5} {f['kind']:<8} {f['key']:<9} {f['detail']}")


# ---------------------------------------------------------------------------
# 투영 — 세계에서 각 도구가 기록하는 것만 뽑아낸다.
#
# 보드는 사람이 '적은' 것이라 실제와 어긋날 수 있다. 그 어긋남을 의도적으로 심는다.
# 저장소와 캘린더는 기계가 남긴 것이라 사실과 일치한다.
# 셋을 맞대면 어긋남이 드러난다 — 그게 이 데모의 전부다.
# ---------------------------------------------------------------------------

VERBS = ["구현", "정리", "수정", "보강", "리팩터"]


def _plan_duedates(world: World) -> dict:
    """프로젝트 시작 시점에 세운 '원래 계획'. 실제로 늦어진 태스크는 여기서 마감을 넘긴다."""
    start = schedule.add_workdays(world.today, -BACK_DAYS)
    finish: dict[str, float] = {}
    out: dict[str, dt.date] = {}
    for key, task in world.tasks.items():
        begin = max([finish[d] for d in task.deps if d in finish], default=0.0)
        finish[key] = begin + task.points
        out[key] = schedule.add_workdays(start, finish[key])
    return out


def to_board(world: World, project: str = "ECHO") -> dict:
    """사람이 기록한 보드. 기록 오차를 의도적으로 심는다.

    심는 것 둘:
      status_lag      실제로는 손대고 있는데 보드는 아직 '할 일'
      premature_done  보드는 '완료'인데 PR 이 안 닫혀 있다 (to_repo 가 짝을 맞춘다)
    """
    due = _plan_duedates(world)
    started = [t for t in world.tasks.values() if t.started_on and not t.done]
    done = [t for t in world.tasks.values() if t.done]
    lag = started[-1].key if started else ""
    premature = done[-1].key if done else ""

    issues, planted = [], []
    for key, task in world.tasks.items():
        if task.done:
            status = "완료"
        elif task.started_on:
            status = "진행 중"
        else:
            status = "할 일"
        if key == lag:
            status = "할 일"  # 기록이 현실을 못 따라간 경우
        issues.append(
            {
                "key": key,
                "fields": {
                    "summary": task.summary,
                    "status": {"name": status},
                    "assignee": None,  # 실계정이 없어 담당자는 라벨로 싣는다
                    "labels": [f"{schedule.OWNER_PREFIX}{task.owner}"],
                    "duedate": due[key].isoformat(),
                    "customfield_10016": task.points,
                    "issuelinks": [],
                },
            }
        )
    by_key = {i["key"]: i for i in issues}
    for key, task in world.tasks.items():
        for dep in task.deps:
            if dep in by_key:
                by_key[dep]["fields"]["issuelinks"].append(
                    {"type": {"name": "Blocks"}, "outwardIssue": {"key": key}}
                )
    if lag:
        planted.append(
            {
                "key": lag,
                "kind": "undeclared_progress",
                "detail": "실제로는 착수했는데 보드는 '할 일'로 남아 있다",
            }
        )
    if premature:
        planted.append(
            {
                "key": premature,
                "kind": "done_with_open_pr",
                "detail": "보드는 완료인데 PR 이 아직 열려 있다",
            }
        )
    return {
        "project": project,
        "issues": issues,
        "planted": planted,
        "_lag": lag,
        "_premature": premature,
    }


def to_repo(
    world: World, board: dict | None = None, repo_name: str = "echo-team/echo-pmo-demo"
) -> dict:
    """저장소 — 기계가 남긴 사실. work 기록이 있는 날에만 커밋이 생긴다."""
    board = board or to_board(world)
    premature = board.get("_premature", "")
    rnd = random.Random(31)
    logins = {p.name: p.login for p in world.people}
    emails = {p.name: p.email for p in world.people}

    commits: list[dict] = []
    pulls: list[dict] = []
    planted: list[dict] = []
    for n, fact in enumerate(f for f in world.facts if f["kind"] == "work"):
        task = world.tasks[fact["key"]]
        commits.append(
            {
                "sha": f"{n + 1:07x}",
                "date": fact["day"],
                "author": logins[fact["who"]],
                "login": logins[fact["who"]],
                "name": fact["who"],
                "email": emails[fact["who"]],
                "message": f"{fact['key']} {task.title} {rnd.choice(VERBS)}",
                "branch": f"feat/{fact['key'].lower()}",
                "url": f"https://github.com/{repo_name}/commit/{n + 1:07x}",
            }
        )

    # 리뷰는 회의가 가장 많은 사람에게 몰린다 — 병목이 겹치는 현실적인 조합
    overload = next((t["assignee"] for t in world.truths if t["kind"] == "meeting_overload"), "")
    for key, task in world.tasks.items():
        days = [f["day"] for f in world.worked_on(key)]
        if not days:
            continue
        number = 100 + len(pulls) + 1
        merged = task.done and key != premature
        reviewer = next((p.name for p in world.people if p.name != task.owner), "")
        if overload and overload != task.owner:
            reviewer = overload
        pulls.append(
            {
                "number": number,
                "title": f"{key} {task.title}",
                "state": "closed" if merged else "open",
                "draft": False,
                "author": logins[task.owner],
                "branch": f"feat/{key.lower()}",
                "created": days[0],
                "updated": days[-1],
                "merged": merged,
                "reviewers": [logins[reviewer]] if reviewer and not merged else [],
                "url": f"https://github.com/{repo_name}/pull/{number}",
            }
        )
        if not merged and (world.today - dt.date.fromisoformat(days[-1])).days >= 2:
            planted.append(
                {
                    "key": key,
                    "kind": "review_waiting",
                    "detail": f"PR #{number} 가 {days[-1]} 이후 리뷰 대기",
                }
            )

    branches = ["develop", "main"] + sorted({c["branch"] for c in commits})[:10]
    return {
        "repo": repo_name,
        "info": {
            "full_name": repo_name,
            "private": True,
            "default_branch": "develop",
            "pushed_at": max((c["date"] for c in commits), default=""),
        },
        "commits": sorted(commits, key=lambda c: c["date"], reverse=True),
        "pulls": pulls,
        "branches": branches,
        "collaborators": [{"login": p.login, "role": "write"} for p in world.people],
        "planted": planted,
    }


def to_calendar(world: World) -> dict:
    """캘린더 — 시간이 간 곳. 과거와 미래를 둘 다 담는다.

    과거 회의가 있어야 "왜 그때 진도가 안 나갔나"에 답할 수 있다.
    미래 회의가 있어야 "앞으로 얼마나 쓸 수 있나"를 계산할 수 있다.
    """
    events = [
        {
            "attendee": f["who"],
            "date": f["day"],
            "start": f.get("start", "10:00"),
            "hours": f["hours"],
            "title": f["detail"],
        }
        for f in world.facts
        if f["kind"] == "meeting"
    ]
    events.sort(key=lambda e: (e["date"], e["start"], e["attendee"]))
    planted = [dict(t) for t in world.truths if t["kind"] == "meeting_overload"]
    full = [e for e in events if e["hours"] >= av.WORKDAY_HOURS]
    if full:
        planted.append(
            {
                "kind": "workshop",
                "date": full[0]["date"],
                "detail": "전원 하루 소진 — 그 날은 아무 진도도 나가지 않는다",
            }
        )
    return {
        "source": "echo-team/demo-calendar",
        "horizon_days": FWD_DAYS,
        "events": events,
        "planted": planted,
    }


def project(world: World) -> dict:
    """세 도구 데이터 + 합쳐진 정답지."""
    board = to_board(world)
    repo = to_repo(world, board)
    cal = to_calendar(world)
    truths = list(world.truths) + board["planted"] + repo["planted"]
    return {"board": board, "repo": repo, "calendar": cal, "truths": truths}
