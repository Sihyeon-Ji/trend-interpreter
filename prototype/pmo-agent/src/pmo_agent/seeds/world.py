"""The demo world — every tool's data derives from one story.

We used to build the board, repo and calendar seeds separately. Each looked
plausible on its own, but **there was no single story behind them.** So the
engine could say "ECHO-5 has been stuck for 20 days" and no data anywhere
could answer "why".

This module runs the project forward one day at a time:

    give everyone their meetings -> push their own tasks with what is left
    -> get blocked when the incident hits

The result is `World.facts` — **what actually happened.** Every tool's data is
projected from it:

    board     what people **wrote down**   (where it diverges from reality is the signal)
    repo      what was actually **done**   (commits, pull requests)
    calendar  where the time **went**      (past and future meetings)

`World.truths` is the answer key. It records "what the real cause was", and the
tests check that the agent's own calculation finds it — these are the
success/failure cases the team workflow document asks for.

The seed is fixed, so the same world comes out however often you run it.

Run:
  python -m pmo_agent.seeds.world            summary
  python -m pmo_agent.seeds.world --facts    with the day-by-day record
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
    ("Maya Okonkwo", "maya-o", "maya@echo.test"),
    ("Leo Fischer", "leo-f", "leo@echo.test"),
    ("Priya Raman", "priya-r", "priya@echo.test"),
    ("Noah Brandt", "noah-b", "noah@echo.test"),
]

PHASES = [
    (
        "Discovery",
        [
            "Requirements interviews",
            "User scenarios",
            "Success metrics",
            "Competitor research",
            "Scope lock",
            "Risk register",
            "Schedule draft",
        ],
    ),
    (
        "Design",
        [
            "Information architecture",
            "Screen flow",
            "Data model",
            "API spec",
            "Authentication approach",
            "Error handling rules",
            "Design system",
        ],
    ),
    (
        "Build",
        [
            "Project scaffolding",
            "Authentication",
            "List view",
            "Detail view",
            "Search",
            "Notifications",
            "Settings screen",
            "API client",
            "Data migration",
            "Permissions",
            "Logging",
            "Performance tuning",
        ],
    ),
    (
        "Hardening",
        [
            "Unit tests",
            "Integration tests",
            "Browser tests",
            "Accessibility audit",
            "Load tests",
            "Security review",
            "Round 1 QA fixes",
            "Round 2 QA fixes",
        ],
    ),
    (
        "Release",
        [
            "Release notes",
            "Deploy rehearsal",
            "Runbook",
            "Monitoring dashboard",
            "Launch review",
            "Launch",
        ],
    ),
]

BACK_DAYS = 35  # business days into the past, from today
# 18 used to be enough. Once phases became real gates the project no longer reached
# the build phase inside that window, so the incident planted there never fired and
# the demo had nothing to explain. A project has to be observed long enough to be
# mid-flight; seven weeks of history puts it there.
FWD_DAYS = 25  # business days into the future (for the calendar)

RECURRING = ("Team sync", 1.0)  # Mondays, everyone
PERSONAL = [("1:1", 0.5), ("Sprint review", 1.0), ("Design review", 1.5), ("Customer call", 2.0)]
INCIDENT_MEETING = ("Incident response", 3.0)
WORKSHOP = ("All-hands workshop", av.WORKDAY_HOURS)


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
    """The simulation result. Every tool's data comes out of this."""

    today: dt.date
    people: list
    tasks: dict
    facts: list  # {"day", "who", "kind", "key", "hours", "detail"}
    truths: list  # the answer key — what the real cause was
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
    """The task list: a gate between phases, and some serial work inside each one.

    Every task waits for the phase before it to finish. Only the *first* task of a phase
    used to, which let a release task start on day one because nothing happened to point
    at it — and a plan built on that put "launch review" in week one.

    The gate is the last task of a phase, and it depends on every other task in that
    phase, so "the phase is done" is what it actually means. Without that, the gate was
    one arbitrary task and a design task could be planned after the build that needed it.
    """
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
                deps.append(keys[-1])  # some work inside a phase is genuinely serial
            if prev_last and not deps:
                deps.append(prev_last)  # everything else waits on the gate
            out[key] = Task(
                key=key,
                phase=phase,
                title=title,
                points=float(rnd.choice([1, 2, 2, 3, 3, 5, 8])),
                owner=PEOPLE[n % len(PEOPLE)][0],
                deps=deps,
            )
            keys.append(key)
        # The phase's last task is its gate: it cannot finish until the rest of the phase
        # has. Reads naturally too — a design system comes after the designs, a launch
        # after everything that ships in it.
        gate = out[keys[-1]]
        gate.deps = sorted({*gate.deps, *keys[:-1]})
        prev_last = keys[-1]
    return out


_CACHE: dict[tuple, World] = {}


def simulate(today: dt.date | None = None, seed_value: int = 20260922) -> World:
    """Run it one day at a time. Meetings eat time first; what is left pushes tasks.

    The same arguments give back the same world — if the board, repo and calendar
    each looked at a different world, the consistency we worked for would be gone.
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

    # Root cause: an external IdP changes its spec and authentication stalls.
    # This is where the push into the whole hardening phase starts.
    blocked_key = next(k for k, t in tasks.items() if t.title == "Authentication")
    # The incident needs a task with some weight. Block a 1-pointer and it finishes
    # the moment it unblocks, so there is no "this slipped" story to tell.
    tasks[blocked_key].points = 8.0
    incident = {
        "key": blocked_key,
        "owner": tasks[blocked_key].owner,
        "title": "External IdP spec change",
        "day": "",  # the day the task became startable — set in the loop below
        "blocked_days": 8,
        "detail": "the identity provider changed its token format, forcing a redesign",
    }
    block_from: dt.date | None = None
    block_to: dt.date | None = None

    # Parked: a task someone started and never came back to. Unlike a block,
    # nobody notices. Pick it from what is *actually* in flight at park_from —
    # naming it up front risks picking something that has not even started.
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
            continue  # the future gets meetings only — work there is a forecast, not a record

        if not parked_key and day >= park_from:
            live = [t for t in tasks.values() if t.progress > 0 and not t.done]
            if live:
                parked_key = min(live, key=lambda t: (t.progress, t.key)).key

        for person in people:
            spent = sum(m["hours"] for m in meetings if m["who"] == person.name)
            free = max(0.0, 1.0 - spent / av.WORKDAY_HOURS)
            if free <= 0.05:
                continue
            # The incident fires the moment someone actually reaches for that task.
            # Fire it on the day it merely became startable and the block expires
            # before its owner ever gets there.
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
    """That day's meetings. During the incident the owner picks up response calls."""
    out = []
    if day.weekday() == 0:
        out += [
            {"who": n, "hours": RECURRING[1], "detail": RECURRING[0], "start": "10:00"}
            for n in names
        ]
    if offset == 6:  # six business days out, a whole day disappears
        out += [
            {"who": n, "hours": WORKSHOP[1], "detail": WORKSHOP[0], "start": "09:00"} for n in names
        ]
        return out
    # `day` is empty until the incident actually fires, and "" sorts before every date:
    # without the first clause the owner sat in response calls for an incident that had
    # not happened yet, from the first day of the simulation.
    started = incident["day"]
    in_incident = bool(started) and started <= day.isoformat() and offset < 0
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
    """What this person can push right now: dependencies met, and not blocked.

    If the blocked task is their turn, they stop rather than skip ahead — that is
    what really happens, people burn time in front of the thing that is stuck.
    That stall is the signal.
    """
    for key, task in tasks.items():
        if task.owner != owner or task.done:
            continue
        if any(not tasks[d].done for d in task.deps if d in tasks):
            continue
        if key == blocked_key and blocking:
            return None
        if key == parked_key and parked:
            continue  # parked — not blocked, just dropped. Move on to the next thing
        return key
    return None


def _truths(tasks: dict, facts: list, incident: dict, today: dt.date, parked_key: str) -> list:
    """The answer key — the "real cause" planted in the data. Tests and cases read it."""
    out = [
        {
            "kind": "root_cause",
            "key": incident["key"],
            "cause": incident["title"],
            "detail": incident["detail"],
            "since": incident["day"],
            "expect": "why this task stalled should be visible in both notes and calendar",
        }
    ]

    # Forecasting consumes *future* meetings. Past ones explain why things slipped;
    # future ones set how much time is left. The answer key uses the latter.
    horizon = schedule.add_workdays(today, 10).isoformat()
    load: dict[str, float] = {}
    for f in facts:
        if f["kind"] == "meeting" and today.isoformat() <= f["day"] <= horizon:
            load[f["who"]] = load.get(f["who"], 0.0) + f["hours"]
    if load:
        # Two people can sit on the same number of hours, and when they do, "who has the
        # most meetings" has two right answers. Naming one and calling the other wrong
        # would be the answer key lying, so every person at the top is recorded.
        peak = max(load.values())
        tied = sorted(n for n, h in load.items() if peak - h <= peak * 0.02)
        out.append(
            {
                "kind": "meeting_overload",
                "assignee": tied[0],
                "tied": tied,
                "hours": round(peak, 1),
                "window_days": 10,
                "expect": "whoever has the most meetings ahead should have the least time",
            }
        )

    parked = tasks.get(parked_key)
    if parked and parked.started_on and not parked.done:
        out.append(
            {
                "kind": "stalled",
                "key": parked.key,
                "started": parked.started_on.isoformat(),
                "expect": "a started-then-parked task should surface in the board/code check",
            }
        )
    return out


def describe(world: World) -> dict:
    done = [t for t in world.tasks.values() if t.done]
    work = [f for f in world.facts if f["kind"] == "work"]
    meet = [f for f in world.facts if f["kind"] == "meeting"]
    blocked = [f for f in world.facts if f["kind"] == "blocked"]
    return {
        "window": f"{BACK_DAYS} business days back .. {FWD_DAYS} forward",
        "tasks": f"{len(done)}/{len(world.tasks)} done",
        "work_records": len(work),
        "meetings": len(meet),
        "blocked_days": len(blocked),
        "incident": f"{world.incident['title']} (from {world.incident['day']}, "
        f"{world.incident['blocked_days']} business days, {world.incident['key']})",
        "truths": world.truths,
    }


if __name__ == "__main__":
    w = simulate()
    print(json.dumps(describe(w), ensure_ascii=False, indent=1))
    if "--facts" in sys.argv:
        print("\nday-by-day record (first 30):")
        for f in w.facts[:30]:
            print(f"  {f['day']}  {f['who']:<5} {f['kind']:<8} {f['key']:<9} {f['detail']}")


# ---------------------------------------------------------------------------
# Projections — pull out only what each tool would have recorded.
#
# The board is what a person *wrote*, so it can diverge from reality. We plant
# that divergence on purpose. The repo and calendar are machine records, so they
# match the facts. Line all three up and the divergence shows. That is the demo.
# ---------------------------------------------------------------------------


def _plan_duedates(world: World) -> dict:
    """The plan as it was set at kickoff. Tasks that really slipped blow past it.

    Dependencies only, from the project start — the same basis `schedule.risks` forecasts
    on. That matching matters more than it looks: build the plan with capacity applied and
    compare it against a dependency-only forecast, and the two biases cancel. A task that
    lost eight days to an incident comes out exactly on plan, and "at risk" means nothing.

    Capacity belongs in the comparison capacity.py makes — committed finish against
    achievable finish — not hidden inside the due dates.
    """
    start = schedule.add_workdays(world.today, -BACK_DAYS)
    fresh = schedule.to_tasks(
        [
            {
                "key": key,
                "summary": task.summary,
                "assignee": task.owner,
                "points": task.points,
                "deps": list(task.deps),
            }
            for key, task in world.tasks.items()
        ]
    )
    placed = schedule.cpm(fresh, start)["tasks"]
    return {key: row["ef"] for key, row in placed.items()}


def to_board(world: World, project: str = "ECHO") -> dict:
    """The board as a person kept it. Recording errors are planted on purpose.

    Two of them:
      status_lag      work is actually under way but the board still says To Do
      premature_done  the board says Done while the PR is still open (to_repo pairs it up)

    Neither lands on the parked task. A task that is both parked *and* mislabelled To Do
    shows up as a status lag and never as a stall, because a stall is only visible on work
    the board thinks is in progress — one planted signal quietly eating another.
    """
    due = _plan_duedates(world)
    parked = next((t["key"] for t in world.truths if t["kind"] == "stalled"), "")
    started = [t for t in world.tasks.values() if t.started_on and not t.done and t.key != parked]
    done = [t for t in world.tasks.values() if t.done]
    lag = started[-1].key if started else ""
    premature = done[-1].key if done else ""

    issues, planted = [], []
    for key, task in world.tasks.items():
        if task.done:
            status = "Done"
        elif task.started_on:
            status = "In Progress"
        else:
            status = "To Do"
        if key == lag:
            status = "To Do"  # the record has not caught up with reality
        issues.append(
            {
                "key": key,
                "fields": {
                    "summary": task.summary,
                    "status": {"name": status},
                    "assignee": None,  # no real accounts, so the owner rides on a label
                    "labels": [schedule.owner_tag(task.owner)],
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
                "detail": "work has started but the board still says To Do",
            }
        )
    if premature:
        planted.append(
            {
                "key": premature,
                "kind": "done_with_open_pr",
                "detail": "the board says Done while the pull request is still open",
            }
        )
    return {
        "project": project,
        "issues": issues,
        "planted": planted,
        "_lag": lag,
        "_premature": premature,
    }


def to_repo(world: World, board: dict | None = None, repo_name: str = "echo-team/echo-app") -> dict:
    """The repository — the machine's record of fact.

    **No ticket keys in commit messages.** Real repositories look like this, and
    joining things up when the key is missing is what this agent is for. Put the
    keys in and we would only ever solve the easy version, the one string
    matching already handles.

    Which commit belonged to which task is kept separately in `link_truth` — the
    answer key for link accuracy. Adapters never expose it.
    """
    board = board or to_board(world)
    premature = board.get("_premature", "")
    rnd = random.Random(31)
    logins = {p.name: p.login for p in world.people}
    emails = {p.name: p.email for p in world.people}

    commits: list[dict] = []
    pulls: list[dict] = []
    planted: list[dict] = []
    link_truth: dict[str, str] = {}
    seen: dict[str, int] = {}

    for n, fact in enumerate(f for f in world.facts if f["kind"] == "work"):
        task = world.tasks[fact["key"]]
        info = artifact(task)
        index = seen.get(task.key, 0)
        seen[task.key] = index + 1
        sha = f"{n + 1:07x}"
        commits.append(
            {
                "sha": sha,
                "date": fact["day"],
                "author": logins[fact["who"]],
                "login": logins[fact["who"]],
                "name": fact["who"],
                "email": emails[fact["who"]],
                "message": commit_subject(task, index, rnd),
                "branch": info["branch"],
                "files": [info["path"]],
                "url": f"https://github.com/{repo_name}/commit/{sha}",
            }
        )
        link_truth[sha] = task.key

    # Reviews pile onto whoever has the most meetings — bottlenecks really do stack
    overload = next((t["assignee"] for t in world.truths if t["kind"] == "meeting_overload"), "")
    for key, task in world.tasks.items():
        days = [f["day"] for f in world.worked_on(key)]
        if not days:
            continue
        info = artifact(task)
        number = 100 + len(pulls) + 1
        merged = task.done and key != premature
        reviewer = next((p.name for p in world.people if p.name != task.owner), "")
        if overload and overload != task.owner:
            reviewer = overload
        pulls.append(
            {
                "number": number,
                "title": commit_subject(task, 0, rnd),
                "state": "closed" if merged else "open",
                "draft": False,
                "author": logins[task.owner],
                "branch": info["branch"],
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
                    "detail": f"PR #{number} has been waiting on review since {days[-1]}",
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
        # name <-> login map, used to tie commit authors to board assignees.
        # In a real setup this is something the team configures once.
        "people": {p.name: p.login for p in world.people},
        "planted": planted,
        "link_truth": link_truth,
    }


def to_calendar(world: World) -> dict:
    """The calendar — where the time went. It holds both past and future.

    Past meetings are what let us answer "why did nothing move that week".
    Future meetings are what let us compute "how much time is actually left".
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
                "detail": "everyone's day is gone — nothing moves that day",
            }
        )
    return {
        "source": "echo-team/demo-calendar",
        "horizon_days": FWD_DAYS,
        "events": events,
        "planted": planted,
    }


# An incident is not one sentence stamped on a fortnight of calls. The first note is
# where the problem gets named; the ones after it are two weeks of not getting an answer,
# which is what actually keeps the task parked.
#
# Every note opens with the incident's name, the way a recurring call's minutes do. That
# is not decoration: `cause.py` surfaces whichever note covers the task best and breaks a
# tie by recency, so the reason has to survive into the later ones or the agent ends up
# quoting "chased them again" with nothing behind it.
FOLLOW_UPS = (
    "still no written spec from the provider. {Thing} stays parked.",
    "sketched two shapes for the new token handling. Neither is safe to build on until "
    "the provider says which is real, so {thing} does not move this week.",
    "provider acknowledged the ticket, no date given. {Thing} stays parked and the phase "
    "behind it stays off the plan.",
    "walked the team through the blast radius. Everything downstream of {thing} is waiting "
    "on the same answer.",
)


def _incident_thread(incident: dict, thing: str, days: list) -> list:
    """The incident calls as a thread: one note that explains, then the waiting."""
    opening = (
        f"{incident['title']}: {incident['detail']}. "
        f"{thing.capitalize()} cannot move until we agree the new shape, "
        f"so it stays parked and the phase behind it slips."
    )
    out = []
    for i, day in enumerate(days):
        follow = FOLLOW_UPS[(i - 1) % len(FOLLOW_UPS)].format(thing=thing, Thing=thing.capitalize())
        out.append(
            {
                "date": day,
                "author": incident["owner"],
                "title": f"{INCIDENT_MEETING[0]} — {thing}",
                "body": opening if i == 0 else f"{incident['title']}, call {i + 1}: {follow}",
            }
        )
    return out


def to_notes(world: World) -> dict:
    """Meeting notes — the one place a *decision* is written in words.

    The calendar says someone spent three hours in an incident call. It cannot say what
    the incident was. Only a note does, and a note is prose: no ticket key, no structure,
    written by whoever happened to be in the room.

    That is deliberate. Tying a note to a task is the same inference problem as tying a
    commit to one, so linking.py does it — put a key in the note and the demo proves
    nothing. What the note *does* carry is the sentence a person would actually type.
    """
    rnd = random.Random(101)
    incident = world.incident
    blocked = world.tasks[incident["key"]]
    thing = blocked.title.lower()
    notes: list = []
    incident_days: list = []

    for fact in world.facts:
        if fact["kind"] != "meeting" or fact["day"] > world.today.isoformat():
            continue
        title = fact.get("detail", "")
        if title == INCIDENT_MEETING[0] and fact["who"] == incident["owner"]:
            incident_days.append(fact["day"])
        elif title == RECURRING[0] and rnd.random() < 0.35:
            notes.append(
                {
                    "date": fact["day"],
                    "author": fact["who"],
                    "title": title,
                    "body": "Went through the board. Nothing new to flag.",
                }
            )

    notes += _incident_thread(incident, thing, sorted(set(incident_days)))

    # One note per person per day is enough; several people take notes in the same call
    seen, unique = set(), []
    for note in sorted(notes, key=lambda n: (n["date"], n["author"])):
        mark = (note["date"], note["author"], note["title"])
        if mark in seen:
            continue
        seen.add(mark)
        unique.append(note)
    return {
        "source": "echo-team/notes",
        "notes": unique,
        "planted": [
            {
                "kind": "decision_recorded",
                "key": incident["key"],
                "detail": incident["title"],
                "expect": "the words behind the stall are written in a note, with no ticket key",
            }
        ],
    }


def project(world: World) -> dict:
    """All four tools' data plus a merged answer key."""
    board = to_board(world)
    repo = to_repo(world, board)
    cal = to_calendar(world)
    notes = to_notes(world)
    truths = list(world.truths) + board["planted"] + repo["planted"] + notes["planted"]
    return {"board": board, "repo": repo, "calendar": cal, "notes": notes, "truths": truths}


# ---------------------------------------------------------------------------
# The table that makes the repository look real.
#
# Commits in a real repository carry no ticket key. Some teams add one, but far
# more do not, and joining things up when it is missing is what this agent is
# for. So the demo data carries no keys either.
#
# Which commit belonged to which task is kept separately, in `link_truth` — the
# answer key we measure link accuracy against. Adapters never expose it.
# ---------------------------------------------------------------------------

# task title -> (slug, area, component used in the commit subject)
ARTIFACTS = {
    "Requirements interviews": ("requirements", "docs", "requirements"),
    "User scenarios": ("user-scenarios", "docs", "user scenarios"),
    "Success metrics": ("success-metrics", "docs", "success metrics"),
    "Competitor research": ("competitors", "docs", "competitor research"),
    "Scope lock": ("scope", "docs", "scope"),
    "Risk register": ("risks", "docs", "the risk register"),
    "Schedule draft": ("schedule", "docs", "the schedule"),
    "Information architecture": ("information-architecture", "docs", "information architecture"),
    "Screen flow": ("screen-flow", "docs", "screen flow"),
    "Data model": ("data-model", "api", "the data model"),
    "API spec": ("api-spec", "docs", "the API spec"),
    "Authentication approach": ("auth-decision", "docs", "the authentication approach"),
    "Error handling rules": ("error-handling", "api", "error handling"),
    "Design system": ("design-system", "web", "the design system"),
    "Project scaffolding": ("scaffolding", "api", "project scaffolding"),
    "Authentication": ("auth", "api", "authentication"),
    "List view": ("list-view", "web", "the list view"),
    "Detail view": ("detail-view", "web", "the detail view"),
    "Search": ("search", "api", "search"),
    "Notifications": ("notifications", "api", "notifications"),
    "Settings screen": ("settings", "web", "the settings screen"),
    "API client": ("api-client", "web", "the API client"),
    "Data migration": ("migration", "api", "data migration"),
    "Permissions": ("permissions", "api", "permissions"),
    "Logging": ("logging", "api", "logging"),
    "Performance tuning": ("performance", "api", "performance"),
    "Unit tests": ("unit-tests", "tests", "unit tests"),
    "Integration tests": ("integration-tests", "tests", "integration tests"),
    "Browser tests": ("browser-tests", "tests", "browser tests"),
    "Accessibility audit": ("accessibility", "tests", "accessibility checks"),
    "Load tests": ("load-tests", "tests", "load tests"),
    "Security review": ("security", "tests", "security checks"),
    "Round 1 QA fixes": ("qa-round1", "api", "round 1 QA fixes"),
    "Round 2 QA fixes": ("qa-round2", "web", "round 2 QA fixes"),
    "Release notes": ("release-notes", "ops", "release notes"),
    "Deploy rehearsal": ("deploy-rehearsal", "ops", "the deploy rehearsal"),
    "Runbook": ("runbook", "ops", "the runbook"),
    "Monitoring dashboard": ("monitoring", "ops", "the monitoring dashboard"),
    "Launch review": ("launch-review", "docs", "the launch review"),
    "Launch": ("launch", "ops", "the launch"),
}

PATHS = {
    "api": "apps/api/src/builder_cup/{slug}.py",
    "web": "apps/web/src/{slug}.tsx",
    "docs": "docs/{slug}.md",
    "tests": "tests/test_{under}.py",
    "ops": "ops/{slug}.md",
}

# Verb phrases that take the component as their object, so the subject line
# reads the way a real commit does: "feat: implement authentication".
ASPECTS = {
    "docs": ["outline", "draft", "revise", "expand"],
    "api": [
        "implement",
        "harden error handling in",
        "tidy the response shape of",
        "handle edge cases in",
        "refactor",
    ],
    "web": [
        "implement",
        "tidy state handling in",
        "handle the empty state in",
        "improve accessibility in",
    ],
    "tests": ["add", "extend", "tidy fixtures for"],
    "ops": ["write up", "expand", "add checks to"],
}

# Shorthand the team falls into once a task is under way. Nobody writes
# "the monitoring dashboard" five commits in a row — they start naming the
# piece they are touching. This is where linking gets genuinely hard, and it is
# the realistic case, not a handicap we invented.
ALIASES = {
    "Requirements interviews": "the interview notes",
    "User scenarios": "the user journeys",
    "Success metrics": "the KPI list",
    "Competitor research": "the market scan",
    "Scope lock": "what is in and out",
    "Risk register": "the risk list",
    "Schedule draft": "the timeline",
    "Information architecture": "the IA map",
    "Screen flow": "the navigation map",
    "Data model": "the schema",
    "API spec": "the endpoint contract",
    "Authentication approach": "the token flow",
    "Error handling rules": "error responses",
    "Design system": "the component library",
    "Project scaffolding": "the service skeleton",
    "Authentication": "the sign-in flow",
    "List view": "the results grid",
    "Detail view": "the item page",
    "Search": "query handling",
    "Notifications": "alerts",
    "Settings screen": "the preferences page",
    "API client": "the request layer",
    "Data migration": "the backfill",
    "Permissions": "access control",
    "Logging": "structured logs",
    "Performance tuning": "query latency",
    "Unit tests": "coverage gaps",
    "Integration tests": "the end-to-end suite",
    "Browser tests": "the browser suite",
    "Accessibility audit": "keyboard navigation",
    "Load tests": "the load harness",
    "Security review": "the security checklist",
    "Round 1 QA fixes": "the first-round findings",
    "Round 2 QA fixes": "the second-round findings",
    "Release notes": "the changelog",
    "Deploy rehearsal": "the deploy dry run",
    "Runbook": "the on-call guide",
    "Monitoring dashboard": "the alert board",
    "Launch review": "the go/no-go notes",
    "Launch": "the rollout",
}

PREFIX = {"docs": "docs", "api": "feat", "web": "feat", "tests": "test", "ops": "chore"}
ALT_PREFIX = {
    "api": ["fix", "refactor"],
    "web": ["fix", "style"],
    "tests": ["test"],
    "docs": ["docs"],
    "ops": ["chore"],
}


def artifact(task: Task) -> dict:
    """What one task leaves behind in the repo — file path, branch, subject parts."""
    slug, area, component = ARTIFACTS.get(task.title, (task.title, "docs", task.title))
    path = PATHS[area].format(slug=slug, under=slug.replace("-", "_"))
    # Few repositories put feat/ on documentation work — the prefix follows the area too
    prefix = {"docs": "docs", "tests": "test", "ops": "chore"}.get(area, "feat")
    return {
        "slug": slug,
        "area": area,
        "component": component,
        "path": path,
        "branch": f"{prefix}/{slug}",
    }


def commit_subject(task: Task, index: int, rnd) -> str:
    """An ordinary-looking commit subject, with no ticket key in it.

    The first commit names the thing in full; later ones drop into the team's
    shorthand, the way real history reads.
    """
    info = artifact(task)
    area = info["area"]
    prefix = PREFIX[area] if index == 0 else rnd.choice([PREFIX[area]] + ALT_PREFIX[area])
    aspect = ASPECTS[area][index % len(ASPECTS[area])]
    component = info["component"] if index < 2 else ALIASES.get(task.title, info["component"])
    return f"{prefix}: {aspect} {component}"
