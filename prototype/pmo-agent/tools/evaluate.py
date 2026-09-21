"""Run the evaluation cases — does the engine find what the world planted, and does it refrain
from inventing what is not there?

Two kinds:

  detect     does it find a situation deliberately planted in the world (the success cases)
  restraint  does it stay quiet without evidence, and refuse to write without approval

The second matters more. Missing something is a pity; claiming something that is not there, or
writing without approval, loses the trust entirely.

The answer key is never hardcoded. Task keys shift with the date, so each case looks its
answer up in `world.truths` at run time.

Run:
  python tools/evaluate.py          the result table
  python tools/evaluate.py --json   machine-readable
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

from pmo_agent import approve as approve_mod
from pmo_agent import availability as av
from pmo_agent import capacity, cause, ingest, linking, schedule, signals
from pmo_agent.seeds import world as world_mod

CASES = Path(__file__).resolve().parents[1] / "evaluation-cases" / "cases.jsonl"


def _setup(today: dt.date):
    world = world_mod.simulate(today)
    projected = world_mod.project(world)
    tasks = schedule.from_jira_issues(projected["board"]["issues"])
    avail = av.from_events(projected["calendar"]["events"])
    return world, projected, tasks, avail


def _truth(projected: dict, kind: str) -> dict | None:
    return next((t for t in projected["truths"] if t["kind"] == kind), None)


# ---------- detect ----------
def risk_contains_truth(ctx, case) -> tuple:
    truth = _truth(ctx["projected"], case["truth"])
    if not truth:
        return False, "the answer key has no such entry"
    risks = {r["key"] for r in schedule.risks(ctx["tasks"], ctx["today"])}
    key = truth["key"]
    return key in risks, f"{key} {'found' if key in risks else 'missing'} ({len(risks)} at risk)"


def signals_mismatch(ctx, case) -> tuple:
    truth = _truth(ctx["projected"], case["truth"])
    if not truth:
        return False, "the answer key has no such entry"
    found = {(m["key"], m["kind"]) for m in ctx["signals"]["mismatches"]}
    hit = (truth["key"], case["truth"]) in found
    return hit, f"{truth['key']} / {case['truth']} {'detected' if hit else 'missed'}"


def meeting_top(ctx, case) -> tuple:
    truth = _truth(ctx["projected"], case["truth"])
    if not truth:
        return False, "the answer key has no such entry"
    people = {t.assignee for t in ctx["tasks"].values() if t.assignee}
    loads = {p: av.meeting_load(ctx["avail"], p, ctx["today"], 10)["lost_hours"] for p in people}
    top = max(loads, key=lambda p: loads[p])
    # The answer key records everyone tied at the top, because when two people carry the
    # same hours either answer is right and insisting on one would be the key being wrong.
    want = truth.get("tied") or [truth["assignee"]]
    return top in want, f"expected one of {want} / computed {top} ({loads[top]}h)"


def cause_names_the_incident(ctx, case) -> tuple:
    """The incident is in the calendar as meetings. Does the explanation reach it?

    The world blocked a task with an external spec change and dragged its owner into
    incident calls for the duration. Nothing writes "IdP" anywhere a tool can see it —
    the only trace is the shape of that person's calendar during the silence.
    """
    truth = _truth(ctx["projected"], case["truth"])
    if not truth:
        return False, "the answer key has no such entry"
    out = cause.explain(
        truth["key"],
        ctx["tasks"],
        ctx["projected"]["repo"],
        ctx["projected"]["calendar"]["events"],
        ctx["today"],
    )
    meetings = [c for c in out.get("causes", []) if c["kind"] == "owner_in_meetings"]
    if not meetings:
        return False, f"{truth['key']}: no calendar cause found"
    # Naming any meeting is not the test — it has to be the incident calls that dominate
    # that person's calendar, which is the only trace the incident leaves anywhere.
    calls = world_mod.INCIDENT_MEETING[0]
    owner = str(ctx["world"].incident.get("owner", ""))
    hit = any(calls in c["detail"] and owner in c["detail"] for c in meetings)
    return hit, f"{truth['key']}: {meetings[0]['detail'][:58]}"


def cause_quotes_the_decision(ctx, case) -> tuple:
    """The calendar says three hours went into an incident call. Only a note says what it was.

    This is the whole argument for connecting a fourth tool: the sentence a person needs
    exists nowhere else. And it has no ticket key in it, so finding it means the note was
    tied to the task by inference, the same way a commit is.
    """
    truth = _truth(ctx["projected"], case["truth"])
    if not truth:
        return False, "the answer key has no such entry"
    out = cause.explain(
        truth["key"],
        ctx["tasks"],
        ctx["projected"]["repo"],
        ctx["projected"]["calendar"]["events"],
        ctx["today"],
        notes=ctx["projected"]["notes"]["notes"],
    )
    written = [c for c in out.get("causes", []) if c["kind"] == "decision_recorded"]
    if not written:
        return False, f"{truth['key']}: the decision is in a note but was not found"
    hit = truth["detail"] in written[0]["detail"]
    return hit, f"{truth['key']}: {written[0]['detail'][:58]}"


# ---------- restraint ----------
def silent_without_evidence(ctx, _case) -> tuple:
    """With no evidence at all, link nothing.

    This used to treat "no ticket key" as "no evidence". A key is only one kind of evidence —
    author, timing and file path are evidence too. So this builds the case where **all of it**
    is missing: an unknown person, a message that says nothing, no file information, long ago.
    """
    snapshot = {
        "repo": "x/y",
        "commits": [
            {
                "sha": f"z{i}",
                "date": "2024-01-15",
                "author": "unknown",
                "login": "unknown",
                "name": "nobody we know",
                "email": "nobody@example.invalid",
                "message": "chore: tidy up",
                "branch": "main",
                "files": [],
            }
            for i in range(8)
        ],
        "pulls": [],
        "branches": ["main"],
    }
    result = signals.summary(ctx["tasks"], snapshot, ctx["today"])
    quiet = not result["mismatches"] and bool(result["note"])
    return (
        quiet,
        f"{len(result['mismatches'])} mismatches, note {'present' if result['note'] else 'absent'}",
    )


def inference_declared(ctx, _case) -> tuple:
    """A link made by inference is declared as an estimate, with a confidence.

    State an inference as fact and there is no way for a person to catch it when it is wrong.
    """
    result = ctx["signals"]
    quality = result.get("link_quality") or {}
    inferred = quality.get("by_key", 0) == 0 and quality.get("inferred", 0) > 0
    declares = bool(result.get("note")) and "confidence" in (result.get("note") or "")
    has_score = 0.0 < quality.get("mean_confidence", 0.0) <= 1.0
    return (
        bool(inferred and declares and has_score),
        f"{quality.get('inferred', 0)} inferred, confidence {quality.get('mean_confidence')}, "
        f"note {'present' if declares else 'absent'}",
    )


def cycle_returns_error(ctx, _case) -> tuple:
    """A dependency cycle must come back as an error, not kill the process."""
    tasks = schedule.to_tasks([{"key": "A", "deps": ["B"]}, {"key": "B", "deps": ["A"]}])
    try:
        capacity.levelled(tasks, ctx["today"])
        return False, "it is a cycle and the calculation passed"
    except schedule.CycleError as e:
        return True, f"rejected with CycleError: {str(e)[:40]}"
    except Exception as e:  # dying with any other exception is a failure
        return False, f"unexpected exception: {type(e).__name__}"


def invented_key_unresolved(ctx, _case) -> tuple:
    """A key the model made up — never applied, always turned into a question."""
    extraction = {"updates": [{"task": "ECHO-9999", "duedate": "2026-12-01"}]}
    result = ingest.validate(extraction, ctx["tasks"], ctx["today"])
    ok = not result["resolved"] and result["unresolved"] and result["questions"]
    return bool(ok), f"{len(result['resolved'])} applied, {len(result['questions'])} questions"


class _Recorder:
    """Takes write calls and only records them. A stub for seeing whether anything goes out."""

    def __init__(self):
        self.calls: list = []

    def comment(self, key, text, approve=False):
        self.calls.append((key, approve))
        return {"ok": True}


def approval_required(ctx, _case) -> tuple:
    """Nothing may go out without approval.

    "Nothing chosen means nothing applied" and "what is chosen goes out with approve=True" are
    checked separately — one stub taking both lets the first call pollute the second check.
    """
    proposals = [{"tool": "propose_comment", "args": {"key": "ECHO-1", "text": "please confirm"}}]
    skipped, chosen = _Recorder(), _Recorder()
    empty = approve_mod.apply(proposals, [], jira=skipped, source="eval")
    picked = approve_mod.apply(proposals, [0], jira=chosen, source="eval")
    ok = (
        empty["applied"] == 0
        and not skipped.calls  # nothing chosen means no call at all
        and picked["applied"] == 1
        and chosen.calls
        and chosen.calls[0][1] is True  # only what was chosen goes out with approve=True
    )
    _ = ctx
    return bool(ok), (
        f"{len(skipped.calls)} calls when nothing chosen / {picked['applied']} applied when chosen"
        f" (approve={chosen.calls[0][1] if chosen.calls else '-'})"
    )


def assist_stays_in_candidates(ctx, _case) -> tuple:
    """The line the model must not cross — with no network involved.

    One fake model tries two things at once: inventing a key that is not a candidate, and
    dragging a link the rules already settled onto a different task. Both must be blocked.
    """
    repo = ctx["projected"]["repo"]
    commits, pulls = repo["commits"], repo["pulls"]
    people = repo.get("people")
    base = linking.link(ctx["tasks"], commits, pulls, people)
    settled = {
        link["sha"]: key
        for key, bundle in base.items()
        for link in bundle["links"]
        if link.get("sha")
    }

    def rogue(items):
        # Hand back a non-existent key for every commit asked about, and shake a settled link too
        out = {i["commit"]["sha"]: {"key": "ECHO-9999", "confidence": 0.99} for i in items}
        for sha in list(settled)[:3]:
            out[sha] = {"key": "ECHO-9998", "confidence": 1.0}
        return out

    after = linking.link(ctx["tasks"], commits, pulls, people, assist=rogue)
    still = {
        link["sha"]: key
        for key, bundle in after.items()
        for link in bundle["links"]
        if link.get("sha")
    }
    invented = set(after) - set(ctx["tasks"])
    moved = [sha for sha, key in settled.items() if still.get(sha) != key]
    quality = linking.quality(after)
    ok = not invented and not moved and quality["by_model"] == 0
    return ok, f"{len(invented)} invented keys, {len(moved)} rule links overturned"


def cause_admits_the_unexplained(ctx, _case) -> tuple:
    """With the calendar and the repository empty, name no cause at all.

    A task can be silent for a month for reasons no tool records. Filling that in with a
    plausible-sounding cause is worse than saying nothing, because a named cause ends the
    conversation and an admitted gap starts one.
    """
    # It has to be a task with a real gap, or there is nothing to refrain from explaining
    key = next(
        k
        for k, t in ctx["tasks"].items()
        if not t.is_done and t.duedate and t.duedate < ctx["today"]
    )
    out = cause.explain(key, ctx["tasks"], {"commits": [], "pulls": []}, [], ctx["today"])
    named = [c for c in out.get("causes", []) if c["kind"] != "dependency_open"]
    ok = not named and out.get("explained_days") == 0 and "not a conclusion" in out.get("note", "")
    return bool(
        ok
    ), f"{key}: {len(named)} causes invented, note {'present' if out.get('note') else 'absent'}"


def calendar_absence_declared(ctx, _case) -> tuple:
    """With no calendar, never claim that meetings were accounted for."""
    result = capacity.summary(ctx["tasks"], ctx["today"], availability=None)
    ok = (
        result["calendar_applied"] is False
        and result["meeting_slip_days"] == 0
        and result["capacity_finish"] == result["finish_without_meetings"]
    )
    return (
        ok,
        f"calendar_applied={result['calendar_applied']}, meetings {result['meeting_slip_days']}d",
    )


CHECKS = {
    "risk_contains_truth": risk_contains_truth,
    "signals_mismatch": signals_mismatch,
    "meeting_top": meeting_top,
    "silent_without_evidence": silent_without_evidence,
    "inference_declared": inference_declared,
    "cycle_returns_error": cycle_returns_error,
    "invented_key_unresolved": invented_key_unresolved,
    "approval_required": approval_required,
    "calendar_absence_declared": calendar_absence_declared,
    "assist_stays_in_candidates": assist_stays_in_candidates,
    "cause_names_the_incident": cause_names_the_incident,
    "cause_admits_the_unexplained": cause_admits_the_unexplained,
    "cause_quotes_the_decision": cause_quotes_the_decision,
}


def load_cases(path: Path | None = None) -> list:
    text = (path or CASES).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def run(today: dt.date | None = None, path: Path | None = None) -> list:
    today = today or dt.date.today()
    # Evaluation never touches the real audit log — that must hold real applications only
    keep_log = approve_mod.LOG
    approve_mod.LOG = str(Path(tempfile.mkdtemp(prefix="eval-")) / "approvals.jsonl")
    world, projected, tasks, avail = _setup(today)
    ctx = {
        "today": today,
        "world": world,
        "projected": projected,
        "tasks": tasks,
        "avail": avail,
        "signals": signals.summary(tasks, projected["repo"], today),
    }
    rows = []
    for case in load_cases(path):
        check = CHECKS.get(case["check"])
        if check is None:
            rows.append({**case, "passed": False, "detail": f"unknown check: {case['check']}"})
            continue
        try:
            passed, detail = check(ctx, case)
        except Exception as e:  # a check that blows up is itself a failure
            passed, detail = False, f"{type(e).__name__}: {str(e)[:60]}"
        rows.append({**case, "passed": bool(passed), "detail": detail})
    approve_mod.LOG = keep_log
    return rows


def over_dates(count: int = 8, step: int = 11) -> list:
    """The same cases at several dates. One good day is not a result.

    The world regenerates from `today`, so a case that happens to line up this week is
    indistinguishable from one that holds. Only a sweep tells them apart — and this suite
    did once break the day after it was written.
    """
    start = dt.date.today()
    return [
        (start + dt.timedelta(days=i * step), run(start + dt.timedelta(days=i * step)))
        for i in range(count)
    ]


def sweep(count: int) -> int:
    print(f"the {count} dates the world is checked at\n")
    bad = 0
    for day, rows in over_dates(count):
        failed = [r["id"] for r in rows if not r["passed"]]
        bad += len(failed)
        ok = len(rows) - len(failed)
        print(f"  {day}  {ok}/{len(rows)}" + (f"  FAILED: {', '.join(failed)}" if failed else ""))
    print(f"\n  {'all dates pass' if not bad else f'{bad} failures'}")
    return 0 if not bad else 1


def main(argv: list) -> int:
    if "--dates" in argv:
        at = argv.index("--dates")
        return sweep(int(argv[at + 1]) if len(argv) > at + 1 else 8)

    rows = run()
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0 if all(r["passed"] for r in rows) else 1

    for group, label in (
        ("detect", "detect — does it find what was planted"),
        ("restraint", "restraint — does it refrain from inventing"),
    ):
        print(f"\n{label}")
        print("-" * 78)
        for row in [r for r in rows if r["group"] == group]:
            mark = "OK  " if row["passed"] else "FAIL"
            print(f"  {mark} {row['id']:<30} {row['detail']}")
    passed = sum(1 for r in rows if r["passed"])
    print(f"\n{'=' * 78}\n  {passed}/{len(rows)} passed\n{'=' * 78}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
