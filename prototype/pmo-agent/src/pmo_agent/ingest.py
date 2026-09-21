"""Notes and handwritten photos → proposed schedule changes. The Gemini multimodal path.

Design rule (straight from SETUP.md): the model only *reads*. It pulls out what a photo or a
sentence says, and nothing else — whether the task exists, whether the date makes sense, what it
does to the schedule, all of that is decided by the code in this file and by schedule.py.
A task key or a relative date the model made up is caught here and turned into a
question for a person.

There is exactly one network call, call(), and it is injectable — which is how everything else
unit-tests with no API key.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import re
import sys

from pmo_agent import llm, schedule

MAX_BYTES = 15 * 1024 * 1024  # inline attachment ceiling (past this you need the Files API)
MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".pdf": "application/pdf",
}

EXTRACT_SYSTEM = """You read meeting notes and handwritten notes and extract project changes. Rules:
1) Extract only what is written. Do not guess or fill in. If something is unreadable, write what you
can read and lower the confidence.
2) Dates must be written YYYY-MM-DD. Convert phrases like "next Tuesday" against the date you are
   given as today. If you are unsure, leave duedate empty and put it in question.
3) Write the task exactly as the document does (its key 'ECHO-12' if one is there, otherwise the
   title text). Never invent a key.
4) Do not compute schedules. How many days something slips, or what is on the
   critical path, is not your job.
5) Anything that needs checking with an owner goes in question."""

SCHEMA = {
    "type": "object",
    "properties": {
        "updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "task key or title text"},
                    "duedate": {"type": "string", "description": "YYYY-MM-DD, empty if none"},
                    "status": {
                        "type": "string",
                        "description": "e.g. Done, In Progress. Empty if none",
                    },
                    "note": {"type": "string", "description": "anything to leave as a comment"},
                    "confidence": {"type": "number", "description": "0.0-1.0 reading confidence"},
                },
                "required": ["task"],
            },
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "general remarks not tied to a task",
        },
        "questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "questions to put to a person",
        },
    },
    "required": ["updates"],
}


# ---------- building the input (no key needed) ----------
def mime_of(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext not in MIME:
        raise ValueError(
            f"unsupported format: {ext or path} (supported: {', '.join(sorted(MIME))})"
        )
    return MIME[ext]


def attach(path: str) -> dict:
    """File → a Gemini inline_data part. Refuses anything over the size ceiling."""
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise ValueError(
            f"{os.path.basename(path)} is too large ({size / 1048576:.1f}MB > 15MB). "
            f"Shrink it and try again."
        )
    with open(path, "rb") as f:
        return {
            "inline_data": {"mime_type": mime_of(path), "data": base64.b64encode(f.read()).decode()}
        }


def build_parts(text: str = "", images=(), today: dt.date | None = None, keys=()) -> list:
    """The parts to send. Real task keys go along too, to cut down on invention."""
    today = today or dt.date.today()
    head = [f"Today is {today.isoformat()}."]
    if keys:
        head.append("Task keys that really exist in this project: " + ", ".join(sorted(keys)[:200]))
    if text:
        head.append("Note:\n" + text)
    if images:
        head.append(f"Also take in what can be read from the {len(images)} attached image(s).")
    return [{"text": "\n\n".join(head)}] + [attach(p) for p in images]


# ---------- the model call (the only place a key is needed) ----------
def call(parts: list) -> dict:
    """The Gemini multimodal call. A JSON schema is enforced so no free prose creeps in.
    Retries, error bodies and backend switching are llm.py's job."""
    return llm.generate(
        {
            "contents": [{"role": "user", "parts": parts}],
            "systemInstruction": {"parts": [{"text": EXTRACT_SYSTEM}]},
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": SCHEMA,
            },
        }
    )


def parse(resp: dict) -> dict:
    """Gemini response → {updates, notes, questions}.

    A broken response comes back as an empty result plus a question, never as an exception.
    """
    parts = ((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    raw = "".join(p.get("text", "") for p in parts).strip()
    if not raw:
        return {
            "updates": [],
            "notes": [],
            "questions": ["The model read nothing at all. Check whether the photo is blurred."],
        }
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "updates": [],
            "notes": [],
            "questions": ["The model's response could not be parsed. Try again."],
            "raw": raw[:500],
        }
    return {
        "updates": list(data.get("updates") or []),
        "notes": list(data.get("notes") or []),
        "questions": list(data.get("questions") or []),
    }


# ---------- validation (no key needed) ----------
def _mentions(needle: str, haystack: str) -> bool:
    """Does the title contain this phrase as words, rather than as letters?

    A plain substring test made "search" match "Competitor research", which turned a
    clear reference into a question about two tasks. The restraint was working; the
    ambiguity was invented. Whole words only.
    """
    words = re.escape(needle.strip())
    return bool(re.search(rf"(?<![0-9a-z]){words}(?![0-9a-z])", haystack, re.IGNORECASE))


def resolve(name: str, tasks: dict) -> tuple:
    """What the model called a task → a real key. Returns (key or None, reason).
    Key match first, then a whole-word title match. If several match, a person chooses."""
    if not name:
        return None, "the task is empty"
    s = name.strip()
    for k in tasks:
        if k.lower() == s.lower():
            return k, ""
    hits = [k for k, t in tasks.items() if _mentions(s, t.summary or "")]
    if len(hits) == 1:
        return hits[0], ""
    if len(hits) > 1:
        return None, f"'{s}' matches several tasks: {', '.join(sorted(hits))}"
    return None, f"no task matches '{s}'"


def validate(extraction: dict, tasks: dict, today: dt.date, max_ahead_days: int = 400) -> dict:
    """Model output → changes that can be applied (resolved) / things to ask about (unresolved).
    Only passes what names a real task, with an ISO date in a sensible range."""
    resolved, unresolved = [], []
    questions = list(extraction.get("questions") or [])
    for u in extraction.get("updates") or []:
        key, why = resolve(str(u.get("task") or ""), tasks)
        if not key:
            unresolved.append({"said": u.get("task"), "reason": why, "raw": u})
            continue
        item = {
            "key": key,
            "summary": tasks[key].summary,
            "assignee": tasks[key].assignee,
            "confidence": float(u.get("confidence") or 0.0),
        }
        due = (u.get("duedate") or "").strip()
        if due:
            try:
                d = schedule.parse_date(due)
            except ValueError:
                unresolved.append(
                    {"said": u.get("task"), "reason": f"cannot read the date: '{due}'", "raw": u}
                )
                continue
            if abs((d - today).days) > max_ahead_days:
                unresolved.append(
                    {"said": u.get("task"), "reason": f"the date makes no sense: {d}", "raw": u}
                )
                continue
            item["duedate"] = d.isoformat()
            item["duedate_was"] = tasks[key].duedate.isoformat() if tasks[key].duedate else None
        if (u.get("status") or "").strip():
            item["status"] = u["status"].strip()
        if (u.get("note") or "").strip():
            item["note"] = u["note"].strip()
        if len(item) <= 4:  # key/summary/assignee/confidence only = nothing actually changes
            unresolved.append({"said": u.get("task"), "reason": "nothing to change", "raw": u})
            continue
        resolved.append(item)
    for r in unresolved:
        questions.append(f"{r['reason']} — from: '{r['said']}'. Which task is meant?")
    return {
        "resolved": resolved,
        "unresolved": unresolved,
        "notes": list(extraction.get("notes") or []),
        "questions": questions,
    }


def impact(resolved: list, tasks: dict, today: dt.date) -> dict:
    """What the changes would do to the schedule. Every number comes from schedule.py."""
    after = {k: schedule.Task(**dict(t.__dict__)) for k, t in tasks.items()}
    for r in resolved:
        t = after[r["key"]]
        if r.get("duedate"):
            t.duedate = schedule.parse_date(r["duedate"])
        if r.get("status"):
            t.status = r["status"]
    before_s, after_s = schedule.summary(tasks, today), schedule.summary(after, today)
    was = {x["key"] for x in before_s["risks"]}
    return {
        "predicted_finish_before": before_s["predicted_finish"],
        "predicted_finish_after": after_s["predicted_finish"],
        "risks_before": len(before_s["risks"]),
        "risks_after": len(after_s["risks"]),
        "newly_at_risk": [x for x in after_s["risks"] if x["key"] not in was],
    }


def to_proposals(v: dict) -> list:
    """Validated changes → the propose_* calls for the approval gate. Nothing runs here."""
    out = []
    for r in v.get("resolved") or []:
        if r.get("duedate"):
            out.append(
                {"tool": "propose_field_update", "args": {"key": r["key"], "duedate": r["duedate"]}}
            )
        if r.get("status"):
            out.append(
                {"tool": "propose_transition", "args": {"key": r["key"], "to_status": r["status"]}}
            )
        if r.get("note"):
            out.append({"tool": "propose_comment", "args": {"key": r["key"], "text": r["note"]}})
    for n in v.get("notes") or []:
        out.append(
            {"tool": "note", "args": {"text": n}}
        )  # a remark tied to no task — it only reaches the report
    return out


# ---------- putting it together ----------
def ingest(
    text: str = "", images=(), tasks: dict | None = None, today: dt.date | None = None, caller=call
) -> dict:
    """Note or image → validated change proposals, schedule impact, and questions for a person.
    Swap `caller` and it runs with no network (which is what the tests do)."""
    tasks = tasks or {}
    today = today or dt.date.today()
    if not text and not images:
        return {"error": "there has to be either note text or an image."}
    parts = build_parts(text, images, today, keys=tasks.keys())
    v = validate(parse(caller(parts)), tasks, today)
    v["proposals"] = to_proposals(v)
    v["impact"] = impact(v["resolved"], tasks, today) if v["resolved"] else None
    v["applied"] = False  # nothing is applied before approval
    return schedule.iso(v)


if __name__ == "__main__":
    from pmo_agent.tools import _fetch

    args = [a for a in sys.argv[1:]]
    imgs = [a for a in args if os.path.splitext(a)[1].lower() in MIME]
    memo = " ".join(a for a in args if a not in imgs)
    print(json.dumps(ingest(memo, imgs, _fetch()), ensure_ascii=False, indent=1))
