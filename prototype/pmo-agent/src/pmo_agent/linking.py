"""Tie commits and pull requests to tasks — even with no ticket key.

This may be the most important file in the project.

We used to assume `ECHO-12` was written in the commit message. Some teams do
that; most do not, and **joining things up when it is missing is the reason
this agent exists.** Assume the key and you have built a tool that only works
for teams who were already integrated.

It uses four signals, all of them observable from the board and the repo:

    author   did the commit author own that task
    time     does the commit date fall in that task's active window
    words    do the message and branch share vocabulary with the task title
    path     do the changed files match the area that task touches

Scores are summed and the top candidate wins, but **only if it pulled far
enough clear of the runner-up.** When it is close we leave it unlinked — a
wrong link is worse than no link.

A confidence score comes back with every link, so the weak ones can be put to a
person as a question.
"""

from __future__ import annotations

import datetime as _dt
import re

KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")

# Weight per signal. Author and vocabulary are the most trustworthy.
W_AUTHOR = 0.30
W_WORDS = 0.35
W_PATH = 0.20
W_TIME = 0.15

ACCEPT = 0.45  # below this we do not link at all
MARGIN = 0.10  # the winner has to beat the runner-up by this much
WINDOW_DAYS = 21  # how far either side of the due date still counts as active

# Words that say nothing about *which* task this is: conventional-commit prefixes
# and the verbs every subject line uses. The Hangul entries are the same list for a
# repository written in Korean, which a real one this runs against may well be.
STOP = {
    "add",
    "and",
    "cases",
    "checks",
    "draft",
    "edge",
    "expand",
    "extend",
    "fixtures",
    "for",
    "handle",
    "handling",
    "implement",
    "improve",
    "outline",
    "response",
    "revise",
    "shape",
    "state",
    "the",
    "tidy",
    "up",
    "write",
    "feat",
    "fix",
    "docs",
    "test",
    "chore",
    "refactor",
    "style",
    "구현",
    "정리",
    "보강",
    "수정",
    "추가",
    "처리",
    "작성",
    "초안",
    "검토",
    "반영",
    "케이스",
    "픽스처",
    "절차",
    "항목",
    "형식",
    "조건",
    "상태",
    "관리",
    "빈",
    "보완",
}


def keys_in(text: str) -> set:
    """Pull task keys out of a string. If one is there, it is the strongest evidence."""
    return set(KEY_RE.findall((text or "").upper()))


def _words(text: str) -> set:
    """Keep only words that carry meaning: 2+ characters in Korean, 3+ in Latin script."""
    raw = re.split(r"[^0-9A-Za-z가-힣]+", (text or "").lower())
    out = set()
    for token in raw:
        if not token or token in STOP:
            continue
        if re.search(r"[가-힣]", token):
            if len(token) >= 2:
                out.add(token)
        elif len(token) >= 3:
            out.add(token)
    return out


def _features(text: str) -> set:
    """Comparison features — words, plus two cheap tricks for word forms.

    English inflects at the end: a commit says "notifications" where the task
    says "notification". So every word also goes in crudely stemmed.

    Korean glues its endings on instead, which turns one noun and that noun plus a
    suffix into two unrelated words. On whole words alone a commit about the runbook
    would never reach a task named after documenting it. Two-character slices of each
    Hangul word close that gap — see STOP below for the shared vocabulary they ignore.
    """
    out = set()
    for token in _words(text):
        out.add(token)
        if re.search(r"[가-힣]", token):
            if len(token) >= 2:
                out |= {token[i : i + 2] for i in range(len(token) - 1)}
        else:
            out.add(_stem(token))
    return out


def _stem(token: str) -> str:
    """Strip common English endings. Crude on purpose — no dependency, no surprises."""
    for suffix in ("ations", "ation", "ing", "ers", "er", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def _overlap(left: set, right: set) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _date(value: str):
    try:
        return _dt.date.fromisoformat((value or "")[:10])
    except ValueError:
        return None


def score(commit: dict, task, people: dict | None = None) -> tuple:
    """Score and evidence for one commit against one task."""
    reasons = []
    total = 0.0

    author = commit.get("name") or commit.get("author") or ""
    login = commit.get("login") or ""
    alias = (people or {}).get(task.assignee, task.assignee)
    if task.assignee and (author == task.assignee or login == alias):
        total += W_AUTHOR
        reasons.append("author owns the task")

    text = f"{commit.get('message', '')} {commit.get('branch', '')}"
    word_score = _overlap(_features(text), _features(task.summary))
    if word_score > 0:
        total += W_WORDS * min(1.0, word_score * 2.5)
        reasons.append(f"shared vocabulary {word_score:.2f}")

    files = " ".join(commit.get("files") or [])
    path_score = _overlap(
        _features(files.replace("/", " ").replace("_", " ")), _features(task.summary)
    )
    if path_score > 0:
        total += W_PATH * min(1.0, path_score * 3.0)
        reasons.append("file path matches the area")

    when, due = _date(commit.get("date", "")), task.duedate
    if when and due and abs((when - due).days) <= WINDOW_DAYS:
        near = 1.0 - abs((when - due).days) / WINDOW_DAYS
        total += W_TIME * near
        reasons.append(f"{abs((when - due).days)} days from the due date")

    return round(min(1.0, total), 3), reasons


def candidates(commit: dict, tasks: dict, people: dict | None = None, top: int = 5) -> list:
    """The top-scoring candidates, for telling a model "pick from these".

    Ask without a list and the model invents keys that do not exist. Show it only
    what it is allowed to choose.
    """
    ranked = []
    for key, task in tasks.items():
        value, reasons = score(commit, task, people)
        if value > 0:
            ranked.append({"key": key, "score": value, "reasons": reasons})
    ranked.sort(key=lambda r: -r["score"])
    return ranked[:top]


def link_commit(commit: dict, tasks: dict, people: dict | None = None) -> dict | None:
    """Tie one commit to its most likely task. When it is close, leave it alone."""
    explicit = keys_in(f"{commit.get('message', '')} {commit.get('branch', '')}") & tasks.keys()
    if explicit:
        key = sorted(explicit)[0]
        return {"key": key, "how": "key", "confidence": 1.0, "reasons": ["task key in the commit"]}

    ranked = []
    for key, task in tasks.items():
        value, reasons = score(commit, task, people)
        if value > 0:
            ranked.append((value, key, reasons))
    if not ranked:
        return None
    ranked.sort(reverse=True)
    best, runner = ranked[0], (ranked[1] if len(ranked) > 1 else (0.0, "", []))
    if best[0] < ACCEPT or best[0] - runner[0] < MARGIN:
        return None  # not sure enough — a wrong link is worse than no link
    return {"key": best[1], "how": "inferred", "confidence": best[0], "reasons": best[2]}


def link(
    tasks: dict,
    commits: list,
    pulls: list,
    people: dict | None = None,
    assist=None,
) -> dict:
    """{task key: {commits, pulls, links}}.

    Each entry in `links` records how the link was made and how confident it is,
    so the report can keep "inferred" and "confirmed" apart.

    Pass `assist` and **only what the rules could not settle** goes to the model.
    Links already decided are untouched — the model is not there to overwrite the
    calculation, only to judge where the calculation stayed silent.
    """
    out: dict[str, dict] = {key: {"commits": [], "pulls": [], "links": []} for key in tasks}
    unresolved = []
    for commit in commits:
        found = link_commit(commit, tasks, people)
        if not found:
            unresolved.append(commit)
            continue
        out[found["key"]]["commits"].append(commit)
        out[found["key"]]["links"].append({**found, "sha": commit.get("sha", "")})

    if assist and unresolved:
        for commit, decided in _ask_model(assist, unresolved, tasks, people):
            out[decided["key"]]["commits"].append(commit)
            out[decided["key"]]["links"].append({**decided, "sha": commit.get("sha", "")})
    for pull in pulls:
        probe = {
            "message": pull.get("title", ""),
            "branch": pull.get("branch", ""),
            "name": "",
            "login": pull.get("author", ""),
            "date": pull.get("updated", ""),
            "files": [],
        }
        found = link_commit(probe, tasks, people)
        if not found:
            continue
        out[found["key"]]["pulls"].append(pull)
        out[found["key"]]["links"].append({**found, "pull": pull.get("number")})
    return out


KEY_CONVENTION_SHARE = 0.5  # above this share of key-links, call it a key-using team


def _ask_model(assist, commits: list, tasks: dict, people: dict | None):
    """Give the model candidates and let it choose. Every answer is validated.

    Keys outside the candidate set, out-of-range confidence and empty values are
    dropped. Take what the model invented at face value and the rule that code
    produces the numbers collapses right here.
    """
    items = []
    for commit in commits:
        options = candidates(commit, tasks, people)
        if len(options) < 2:
            continue  # nothing to choose between, so nothing to ask
        items.append({"commit": commit, "candidates": options, "tasks": tasks})
    if not items:
        return []
    try:
        answers = assist(items) or {}
    except Exception:
        return []  # if the model fails, the rule-made links must still stand
    out = []
    for item in items:
        sha = item["commit"].get("sha", "")
        answer = answers.get(sha)
        if not answer:
            continue
        key = answer.get("key", "")
        allowed = {c["key"] for c in item["candidates"]}
        confidence = float(answer.get("confidence") or 0.0)
        if key not in allowed or not 0.0 < confidence <= 1.0:
            continue
        reason = str(answer.get("reason", ""))[:120]
        out.append(
            (
                item["commit"],
                {
                    "key": key,
                    "how": "model",
                    "confidence": round(confidence, 3),
                    "reasons": [f"model call: {reason}" if reason else "model call"],
                },
            )
        )
    return out


def quality(linked: dict) -> dict:
    """How solid the links are. The report carries this as its evidence.

    `by_key_convention` means "does this team use ticket keys" — true only when
    most links came from keys, not one or two. A single stale branch name should
    not flip the judgement for a whole project.
    """
    links = [x for v in linked.values() for x in v["links"]]
    explicit = [x for x in links if x["how"] == "key"]
    inferred = [x for x in links if x["how"] == "inferred"]
    by_model = [x for x in links if x["how"] == "model"]
    confident = [x for x in inferred + by_model if x["confidence"] >= 0.6]
    return {
        "total": len(links),
        "by_key": len(explicit),
        "inferred": len(inferred),
        "by_model": len(by_model),
        "inferred_confident": len(confident),
        "linked_tasks": sum(1 for v in linked.values() if v["commits"] or v["pulls"]),
        "mean_confidence": (
            round(sum(x["confidence"] for x in links) / len(links), 2) if links else 0.0
        ),
        "by_key_convention": bool(links) and len(explicit) / len(links) >= KEY_CONVENTION_SHARE,
    }
