"""Ask Gemini about the links, and only the ones the rules could not settle.

The rule in this project is: code produces the numbers, the model makes the calls.
**Which commit belongs to which task** is a judgement, not a calculation — this is
exactly where a model earns its place.

The guardrails still apply:

  · links the rules already settled are untouched. The model answers only where they were silent
  · it gets candidates and picks from them. Ask with no list and it invents keys
  · every answer is validated (is the key a candidate, is the confidence in range)
  · if it does not know it picks `unknown`. Not linking beats forcing a choice
  · if the call fails outright, the rule-made links are still standing

Questions are batched to keep the cost down. One call per commit would mean dozens
of calls per demo run.
"""

from __future__ import annotations

import json

from pmo_agent import llm

UNKNOWN = "unknown"
BATCH = 20  # commits per request

SYSTEM = """You classify which work item a commit belongs to. Rules:
1) Choose only from the candidates given. Never invent a key that is not listed.
2) If you are not confident, set key to "unknown". Do not force a choice.
3) confidence is 0.0-1.0 and should honestly reflect how sure you are.
4) reason is one sentence: what you saw that led to the call. Answer in English."""

SCHEMA = {
    "type": "object",
    "properties": {
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sha": {"type": "string"},
                    "key": {"type": "string", "description": "one of the candidates, or unknown"},
                    "confidence": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["sha", "key", "confidence"],
            },
        }
    },
    "required": ["links"],
}


def build_prompt(items: list) -> str:
    """Commits and candidates in a shape the model can read. Scores ride along as a hint."""
    lines = ["For each commit below, choose the work item it belongs to.", ""]
    for item in items:
        commit = item["commit"]
        lines.append(f"[commit {commit.get('sha', '')}]")
        lines.append(f"  message: {commit.get('message', '')}")
        lines.append(f"  branch: {commit.get('branch', '')}")
        if commit.get("files"):
            lines.append(f"  files: {', '.join(commit['files'][:3])}")
        lines.append(f"  author: {commit.get('name') or commit.get('author', '')}")
        lines.append(f"  date: {commit.get('date', '')}")
        lines.append("  candidates:")
        for option in item["candidates"]:
            task = item["tasks"][option["key"]]
            lines.append(
                f"    - {option['key']}: {task.summary} "
                f"(owner {task.assignee or 'unassigned'}, due {task.duedate or 'none'}, "
                f"rule score {option['score']})"
            )
        lines.append("")
    return "\n".join(lines)


def parse(response: dict) -> dict:
    """Response → {sha: {key, confidence, reason}}. A broken response comes back empty."""
    raw = llm.text_of(response)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    out = {}
    for row in data.get("links") or []:
        sha = str(row.get("sha") or "")
        key = str(row.get("key") or "")
        if not sha or not key or key == UNKNOWN:
            continue  # an "I don't know" answer links nothing
        out[sha] = {
            "key": key,
            "confidence": row.get("confidence"),
            "reason": row.get("reason", ""),
        }
    return out


def assistant(caller=None, batch: int = BATCH):
    """Build the function to hand to `linking.link(assist=...)`.

    Swap `caller` and it runs without a network — the same trick ingest.py uses.

    The returned function carries a `stats` dict recording what actually happened: how
    many commits were put to the model, how many it placed, and how many batches failed.
    A failed batch is not an error here — the commits in it stay unlinked, which is the
    honest outcome — but it is invisible from the outside, and a caller reporting "with
    model assist" when every call was rate-limited would be publishing a rules-only
    number under a different name. Whoever says "assisted" should be able to show it was.
    """
    call = caller or _gemini
    stats: dict = {"asked": 0, "answered": 0, "batches": 0, "failed_batches": 0, "error": ""}

    def assist(items: list) -> dict:
        # linking hands over candidate keys only, so attach the task bodies to read
        out: dict = {}
        stats["asked"] += len(items)
        for start in range(0, len(items), batch):
            chunk = items[start : start + batch]
            stats["batches"] += 1
            try:
                got = parse(call(build_prompt(chunk)))
            except llm.LLMError as e:
                # one failed batch should not take the others down
                stats["failed_batches"] += 1
                stats["error"] = " ".join(str(e).split())[:110]
                continue
            stats["answered"] += len(got)
            out.update(got)
        return out

    assist.stats = stats  # type: ignore[attr-defined]
    return assist


def _gemini(prompt: str) -> dict:
    return llm.generate(
        {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": SCHEMA,
            },
        }
    )
