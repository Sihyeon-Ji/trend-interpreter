"""The approval gate — a proposal is applied only after a person has seen it and picked it.

This file is the only place in the project that passes approve=True.
Gemini cannot reach it (it is not in DECLARATIONS or REGISTRY — test_approve.py checks that).

Approval means one thing: a person typed numbers at the CLI. Even "approve everything" has to be
typed as `all` by the user.

Whatever is applied gets a line in logs/approvals.jsonl — what, when, and with what result.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import tools
from pmo_agent.adapters.jira import Jira, WriteBlocked
from pmo_agent.env import logs_dir

LOG = str(logs_dir() / "approvals.jsonl")

# proposal name → the function that applies it. Anything not listed here is not applicable (notes).
APPLIERS = {
    "propose_field_update": lambda j, a: j.set_fields(
        a["key"], {k: v for k, v in a.items() if k != "key"}, approve=True
    ),
    "propose_transition": lambda j, a: j.transition(a["key"], a["to_status"], approve=True),
    "propose_comment": lambda j, a: j.comment(a["key"], a["text"], approve=True),
}


def describe(p: dict) -> str:
    """One proposal as a single line a person can read."""
    tool, a = p.get("tool", "?"), p.get("args") or {}
    if tool == "propose_field_update":
        bits = ", ".join(f"{k}={v}" for k, v in a.items() if k != "key")
        return f"{a.get('key')}  field change  {bits}"
    if tool == "propose_transition":
        return f"{a.get('key')}  status → {a.get('to_status')}"
    if tool == "propose_comment":
        return f'{a.get("key")}  comment  "{(a.get("text") or "")[:60]}"'
    if tool == "note":
        return f'(not applied) note  "{(a.get("text") or "")[:60]}"'
    return f"{tool}  {json.dumps(a, ensure_ascii=False)[:70]}"


def render(proposals: list, impact: dict | None = None) -> str:
    """The approval screen. Only applicable proposals get a number."""
    lines, n = [], 0
    for p in proposals:
        if p.get("tool") in APPLIERS:
            n += 1
            lines.append(f" [{n:>2}] {describe(p)}")
        else:
            lines.append(f"      {describe(p)}")
    if not lines:
        lines.append("      (nothing proposed)")
    out = ["Proposed changes — nothing has been applied yet", "-" * 62, *lines]
    if impact:
        out += [
            "-" * 62,
            f" forecast finish  {impact.get('predicted_finish_before')} → "
            f"{impact.get('predicted_finish_after')}",
            f" tasks at risk    {impact.get('risks_before')} → {impact.get('risks_after')}",
        ]
        for r in impact.get("newly_at_risk") or []:
            out.append(f"   new risk  {r['key']} {r.get('summary', '')}")
    return "\n".join(out)


def appliable(proposals: list) -> list:
    """Only the numbered (that is, actually applicable) proposals, in order."""
    return [p for p in proposals if p.get("tool") in APPLIERS]


def select(answer: str, count: int) -> list:
    """User input → zero-based indices. Empty, n and q all mean nothing was chosen.
    Only 'all' approves everything; anything else has to be typed out as numbers."""
    s = (answer or "").strip().lower()
    if s in ("", "n", "no", "q", "quit", "none"):
        return []
    if s in ("a", "all"):
        return list(range(count))
    picked = []
    for chunk in s.replace(" ", ",").split(","):
        if not chunk:
            continue
        if "-" in chunk[1:]:  # a range such as 3-5
            a, _, b = chunk.partition("-")
            if a.isdigit() and b.isdigit():
                picked += list(range(int(a), int(b) + 1))
            continue
        if chunk.isdigit():
            picked.append(int(chunk))
    return sorted({i - 1 for i in picked if 1 <= i <= count})


def log(entry: dict) -> None:
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def apply(proposals: list, indices, jira: Jira | None = None, source: str = "") -> dict:
    """Apply only what was chosen. One failure does not stop the rest.

    A blocked write (WriteBlocked) is caught and recorded — an attempt to write to a live domain
    is exactly the thing that needs a record.
    """
    items = appliable(proposals)
    j = jira or tools.jira()
    done, at = [], dt.datetime.now().isoformat(timespec="seconds")
    for i in sorted(set(indices)):
        if not 0 <= i < len(items):
            done.append({"index": i + 1, "ok": False, "error": "no such number"})
            continue
        p = items[i]
        rec = {"at": at, "source": source, "tool": p["tool"], "args": p.get("args") or {}}
        try:
            rec["result"] = APPLIERS[p["tool"]](j, p.get("args") or {})
            rec["ok"] = True
        except WriteBlocked as e:
            rec.update(ok=False, error=f"write blocked: {e}", blocked=True)
        except Exception as e:
            rec.update(ok=False, error=str(e)[:300])
        log(rec)
        done.append(
            {
                "index": i + 1,
                "desc": describe(p),
                "ok": rec["ok"],
                **({"error": rec["error"]} if not rec["ok"] else {}),
            }
        )
    return {
        "applied": sum(1 for d in done if d["ok"]),
        "failed": sum(1 for d in done if not d["ok"]),
        "skipped": len(items) - len(done),
        "results": done,
    }


def gate(proposals: list, impact: dict | None = None, source: str = "", ask=input) -> dict:
    """Interactive approval. Swap `ask` and the tests can drive it non-interactively."""
    items = appliable(proposals)
    print(render(proposals, impact))
    if not items:
        return {"applied": 0, "failed": 0, "skipped": 0, "results": []}
    print("-" * 62)
    print(" Type the numbers to apply (e.g. 1,3 or 1-3). all = everything, Enter = nothing")
    picked = select(ask(" > "), len(items))
    if not picked:
        print(" Nothing was applied.")
        return {"applied": 0, "failed": 0, "skipped": len(items), "results": []}
    where = getattr(tools.jira(), "site", "?")  # the Jira site, or 'local'
    print(f"\n About to apply the following (target: {where}):")
    for i in picked:
        print("   -", describe(items[i]))
    if (ask(" Really apply? (type yes) ") or "").strip().lower() not in ("yes", "y"):
        print(" Cancelled. Nothing applied.")
        return {"applied": 0, "failed": 0, "skipped": len(items), "results": []}
    out = apply(proposals, picked, source=source)
    print(f"\n applied {out['applied']} / failed {out['failed']} — log: {LOG}")
    for r in out["results"]:
        print(
            ("   OK  " if r["ok"] else "   FAIL")
            + r.get("desc", "")
            + ("" if r["ok"] else f"  ({r.get('error')})")
        )
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else ""
    blob = json.load(open(src, encoding="utf-8")) if src else json.load(sys.stdin)
    gate(blob.get("proposals") or [], blob.get("impact"), source=src or "stdin")
