"""스케줄 엔진 — CPM 임계경로 · 지연 전파 · 완료 예측. 순수 파이썬(표준 라이브러리만).

설계 원칙(SETUP.md): 숫자와 날짜는 전부 여기서 계산한다. Gemini 는 이 결과를 인용만 한다.
이 모듈은 Jira 를 import 하지 않는다 — dict 리스트만 받으므로 자격증명 없이 단위 테스트가 된다.
Jira 응답을 넣으려면 from_jira_issues() 로 변환해서 쓴다.

용어: ES/EF 가장 이른 시작·종료, LS/LF 가장 늦은 시작·종료, slack 여유일(0이면 임계경로).
기간은 전부 '영업일'(주말 제외) 단위이고, EF 는 그 날 업무 종료 시점을 가리킨다.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

DONE = {"done", "완료", "closed", "resolved", "종료"}

# 같은 뜻으로 쓰이는 상태 이름들. Jira 사이트 언어에 따라 '완료'/'Done' 이 섞이고,
# 모델은 영어로 답하는 경향이 있어 어댑터가 이 표로 이어 준다.
STATUS_ALIASES = [
    {"done", "완료", "종료", "closed", "resolved"},
    {"in progress", "진행 중", "진행중", "doing", "wip"},
    {"to do", "todo", "할 일", "할일", "backlog", "open"},
    {"in review", "리뷰 중", "검토", "review", "code review"},
]


def status_alike(a: str, b: str) -> bool:
    """두 상태 이름이 같은 뜻인가. 공백·대소문자 차이와 한/영 표기를 흡수한다."""
    na, nb = (a or "").strip().lower(), (b or "").strip().lower()
    if na == nb:
        return True

    def squish(value: str) -> str:
        return value.replace(" ", "")

    if squish(na) == squish(nb):
        return True
    return any(na in g and nb in g for g in STATUS_ALIASES)


DAYS_PER_POINT = 1.0  # 스토리포인트 1 = 영업일 1
DEFAULT_DURATION = 2.0  # 포인트가 없을 때 가정하는 기간(영업일)


class CycleError(ValueError):
    """의존관계에 순환이 있어 일정을 계산할 수 없다."""


# ---------- 영업일 계산 ----------
def is_workday(d: _dt.date, holidays=()) -> bool:
    return d.weekday() < 5 and d not in set(holidays)


def add_workdays(start: _dt.date, days: float, holidays=()) -> _dt.date:
    """start 에서 영업일 days 만큼 뒤의 날짜. 음수면 그만큼 앞으로 간다.
    days=0 이면 start 자신(주말이면 다음 영업일로 보정)."""
    d, n = start, int(round(days))
    step = _dt.timedelta(days=-1 if n < 0 else 1)
    while not is_workday(d, holidays):
        d += step
    for _ in range(abs(n)):
        d += step
        while not is_workday(d, holidays):
            d += step
    return d


def workdays_between(a: _dt.date, b: _dt.date, holidays=()) -> int:
    """a→b 영업일 수. b 가 a 보다 앞서면 음수."""
    if b < a:
        return -workdays_between(b, a, holidays)
    n, d = 0, a
    while d < b:
        d += _dt.timedelta(days=1)
        if is_workday(d, holidays):
            n += 1
    return n


def parse_date(v):
    if v is None or v == "":
        return None
    if isinstance(v, _dt.date):
        return v
    return _dt.date.fromisoformat(str(v)[:10])


# ---------- 태스크 ----------
@dataclass
class Task:
    key: str
    summary: str = ""
    status: str = ""
    assignee: str = ""
    duedate: _dt.date | None = None
    points: float | None = None
    deps: list = field(default_factory=list)  # 선행 태스크 key 목록 (이게 끝나야 시작 가능)
    progress: float = 0.0  # 0.0~1.0, 진행 중 태스크의 완료율

    @property
    def duration(self) -> float:
        return (self.points * DAYS_PER_POINT) if self.points else DEFAULT_DURATION

    @property
    def is_done(self) -> bool:
        return (self.status or "").strip().lower() in DONE

    @property
    def remaining(self) -> float:
        """남은 기간(영업일). 완료면 0, 진행 중이면 progress 반영."""
        if self.is_done:
            return 0.0
        return self.duration * (1.0 - min(max(self.progress, 0.0), 1.0))


def to_tasks(rows) -> dict:
    """dict(또는 Task) 리스트 → {key: Task}. 존재하지 않는 key 를 가리키는 deps 는 버린다."""
    out = {}
    for r in rows:
        if isinstance(r, Task):
            out[r.key] = r
            continue
        out[r["key"]] = Task(
            key=r["key"],
            summary=r.get("summary", "") or "",
            status=r.get("status", "") or "",
            assignee=r.get("assignee", "") or "",
            duedate=parse_date(r.get("duedate")),
            points=r.get("points"),
            deps=list(r.get("deps") or []),
            progress=float(r.get("progress") or 0.0),
        )
    for t in out.values():
        t.deps = [d for d in t.deps if d in out and d != t.key]
    return out


OWNER_PREFIX = "owner-"


def owner_label(fields: dict) -> str:
    """Jira 계정이 없는 가상 담당자를 라벨(owner-이름)로 싣는다.
    샌드박스에는 실제 계정이 하나뿐이라, 담당자별 부하를 보여주려면 이 폴백이 필요하다."""
    for label in fields.get("labels") or []:
        if label.startswith(OWNER_PREFIX):
            return label[len(OWNER_PREFIX) :]
    return ""


def from_jira_issues(issues) -> dict:
    """Jira search() 응답 → {key: Task}.

    Blocks 링크 해석: 이슈에 inwardIssue 가 있으면 '~에 의해 차단됨'(그 이슈가 선행),
    outwardIssue 가 있으면 '~를 차단함'(이 이슈가 그쪽의 선행).
    """
    rows, blocks = {}, []
    for i in issues:
        f = i.get("fields", {})
        rows[i["key"]] = {
            "key": i["key"],
            "summary": f.get("summary", ""),
            "status": ((f.get("status") or {}).get("name") or ""),
            "assignee": ((f.get("assignee") or {}) or {}).get("displayName") or owner_label(f),
            "duedate": f.get("duedate"),
            "points": f.get("customfield_10016"),
            "deps": [],
        }
        for link in f.get("issuelinks") or []:
            if "block" not in ((link.get("type") or {}).get("name", "")).lower():
                continue
            if link.get("inwardIssue"):
                blocks.append((link["inwardIssue"]["key"], i["key"]))
            if link.get("outwardIssue"):
                blocks.append((i["key"], link["outwardIssue"]["key"]))
    for pred, succ in blocks:
        if succ in rows and pred not in rows[succ]["deps"]:
            rows[succ]["deps"].append(pred)
    return to_tasks(rows.values())


# ---------- 그래프 ----------
def successors(tasks: dict) -> dict:
    succ: dict[str, list[str]] = {k: [] for k in tasks}
    for k, t in tasks.items():
        for d in t.deps:
            succ[d].append(k)
    return succ


def topo_order(tasks: dict) -> list:
    indeg = {k: len(t.deps) for k, t in tasks.items()}
    succ = successors(tasks)
    queue = sorted(k for k, n in indeg.items() if n == 0)
    order = []
    while queue:
        k = queue.pop(0)
        order.append(k)
        for s in sorted(succ[k]):
            indeg[s] -= 1
            if indeg[s] == 0:
                queue.append(s)
    if len(order) != len(tasks):
        raise CycleError("의존관계 순환: " + ", ".join(sorted(set(tasks) - set(order))))
    return order


# ---------- CPM ----------
def cpm(tasks: dict, start: _dt.date, holidays=()) -> dict:
    """임계경로 계산. 반환: {tasks: {key: {...}}, finish, duration_days, critical_path}"""
    order, succ = topo_order(tasks), successors(tasks)
    es: dict[str, float] = {}
    ef: dict[str, float] = {}
    for k in order:
        es[k] = max([ef[d] for d in tasks[k].deps], default=0.0)
        ef[k] = es[k] + tasks[k].duration
    total = max(ef.values(), default=0.0)
    ls: dict[str, float] = {}
    lf: dict[str, float] = {}
    for k in reversed(order):
        lf[k] = min([ls[s] for s in succ[k]], default=total)
        ls[k] = lf[k] - tasks[k].duration
    rows = {}
    for k in order:
        slack = round(ls[k] - es[k], 3)
        rows[k] = {
            "key": k,
            "summary": tasks[k].summary,
            "assignee": tasks[k].assignee,
            "status": tasks[k].status,
            "duration_days": tasks[k].duration,
            "es": add_workdays(start, es[k], holidays),
            "ef": add_workdays(start, ef[k], holidays),
            "ls": add_workdays(start, ls[k], holidays),
            "lf": add_workdays(start, lf[k], holidays),
            "slack_days": slack,
            "critical": slack <= 0.0001,
            "duedate": tasks[k].duedate,
            "deps": list(tasks[k].deps),
        }
    return {
        "tasks": rows,
        "finish": add_workdays(start, total, holidays),
        "duration_days": int(round(total)),
        "critical_path": [k for k in order if rows[k]["critical"]],
    }


# ---------- 완료 예측 ----------
def forecast(tasks: dict, today: _dt.date, holidays=()) -> dict:
    """남은 작업량 기준 예상 완료일. 완료 태스크는 0일로 보고 오늘부터 다시 굴린다."""
    order = topo_order(tasks)
    out: dict[str, dict] = {}
    ef: dict[str, float] = {}
    for k in order:
        t = tasks[k]
        ef[k] = max([ef[d] for d in t.deps], default=0.0) + t.remaining
        pred = add_workdays(today, ef[k], holidays)
        delay = workdays_between(t.duedate, pred, holidays) if t.duedate else 0
        out[k] = {
            "key": k,
            "summary": t.summary,
            "assignee": t.assignee,
            "status": t.status,
            "remaining_days": round(t.remaining, 2),
            "predicted_finish": pred,
            "duedate": t.duedate,
            "delay_days": max(0, delay) if t.duedate else None,
            "late": bool(t.duedate and delay > 0),
        }
    return {
        "tasks": out,
        "project_finish": add_workdays(today, max(ef.values(), default=0.0), holidays),
    }


def propagate(tasks: dict, key: str, slip_days: float, today: _dt.date, holidays=()) -> dict:
    """특정 태스크가 slip_days 만큼 밀렸을 때 후행 태스크가 각각 며칠씩 밀리는지.

    여유(slack)가 있으면 그만큼 흡수되고 남은 만큼만 전파된다.
    """
    if key not in tasks:
        return {"error": f"알 수 없는 태스크: {key}"}
    base = forecast(tasks, today, holidays)
    bumped = {k: Task(**dict(t.__dict__)) for k, t in tasks.items()}
    hit = bumped[key]
    hit.points = (tasks[key].remaining + slip_days) / DAYS_PER_POINT
    hit.progress, hit.status = 0.0, ""  # 밀린 만큼 남은 것으로 다시 본다
    after = forecast(bumped, today, holidays)
    moved = []
    for k in after["tasks"]:
        d = workdays_between(
            base["tasks"][k]["predicted_finish"], after["tasks"][k]["predicted_finish"], holidays
        )
        if d <= 0:
            continue
        new_finish = after["tasks"][k]["predicted_finish"]
        moved.append(
            {
                "key": k,
                "summary": tasks[k].summary,
                "assignee": tasks[k].assignee,
                "slip_days": d,
                "new_finish": new_finish,
                "duedate": tasks[k].duedate,
                "breaks_duedate": bool(tasks[k].duedate and new_finish > tasks[k].duedate),
            }
        )
    moved.sort(key=lambda r: (-r["slip_days"], r["key"]))
    return {
        "trigger": key,
        "slip_days": slip_days,
        "affected": moved,
        "project_finish_before": base["project_finish"],
        "project_finish_after": after["project_finish"],
    }


def risks(
    tasks: dict,
    today: _dt.date,
    start: _dt.date | None = None,
    slack_threshold: float = 1.0,
    holidays=(),
) -> list:
    """지연 위험 태스크를 근거와 함께 정렬해 반환. Gemini 가 그대로 인용할 수 있는 형태."""
    fc = forecast(tasks, today, holidays)["tasks"]
    cp = cpm(tasks, start or today, holidays)["tasks"]
    succ, out = successors(tasks), []
    for k, t in tasks.items():
        if t.is_done:
            continue
        why = []
        if fc[k]["late"]:
            why.append(
                f"예상 완료 {fc[k]['predicted_finish']} > 마감 {t.duedate} "
                f"({fc[k]['delay_days']}일 초과)"
            )
        if cp[k]["critical"]:
            why.append("임계경로 상의 태스크 (여유 0일)")
        elif cp[k]["slack_days"] <= slack_threshold:
            why.append(f"여유 {cp[k]['slack_days']}일뿐")
        if t.duedate and t.duedate < today:
            why.append(f"마감일 {t.duedate} 경과")
        if not why:
            continue
        out.append(
            {
                "key": k,
                "summary": t.summary,
                "assignee": t.assignee,
                "status": t.status,
                "duedate": t.duedate,
                "predicted_finish": fc[k]["predicted_finish"],
                "delay_days": fc[k]["delay_days"] or 0,
                "slack_days": cp[k]["slack_days"],
                "critical": cp[k]["critical"],
                "reasons": why,
                "blocks": sorted(succ[k]),
            }
        )
    out.sort(key=lambda r: (-r["delay_days"], r["slack_days"], r["key"]))
    return out


def summary(tasks: dict, today: _dt.date, start: _dt.date | None = None, holidays=()) -> dict:
    """리포트용 한 덩어리. 날짜는 ISO 문자열로 직렬화해 그대로 JSON 에 넣을 수 있다."""
    start = start or today
    c, f = cpm(tasks, start, holidays), forecast(tasks, today, holidays)
    return iso(
        {
            "today": today,
            "planned_finish": c["finish"],
            "predicted_finish": f["project_finish"],
            "slip_days": workdays_between(c["finish"], f["project_finish"], holidays),
            "total": len(tasks),
            "done": sum(1 for t in tasks.values() if t.is_done),
            "critical_path": c["critical_path"],
            "risks": risks(tasks, today, start, holidays=holidays),
        }
    )


def iso(o):
    """date 를 ISO 문자열로 바꾼 사본. JSON 직렬화용."""
    if isinstance(o, _dt.date):
        return o.isoformat()
    if isinstance(o, dict):
        return {k: iso(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [iso(v) for v in o]
    return o
