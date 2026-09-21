"""Who has actually worked where — so a proposed handover is one that could happen.

`capacity.rebalance` searches for a task to move off the bottleneck. Left to itself it
treats people as interchangeable units of time, and cheerfully proposes that whoever is
free take over the data migration, having never touched the API in their life. The date it
promises is real arithmetic on a move nobody would make.

The repository already knows better. Someone who has committed to `apps/api/...` a dozen
times can plausibly pick up another API task; someone who has only ever touched `docs/`
cannot, or at least not at the speed the arithmetic assumes.

So: an area is the leading part of a changed path, a person is familiar with the areas
they have committed to, and a handover to someone unfamiliar is not offered.

Two deliberate softenings, because this is evidence about people and it will be wrong:

  · a task whose area cannot be determined is open to anyone. Absence of evidence is not
    evidence of incapacity
  · a repository nobody has any history in (a fresh one, or one where no commit linked)
    disables the whole check rather than blocking every move

Pure calculation. Nothing here asks a model who seems competent.
"""

from __future__ import annotations

MIN_COMMITS = 2  # one commit in an area is a drive-by; two is a pattern
UNKNOWN = ""


def area_of(path: str) -> str:
    """The directory a file lives in, two levels deep at most.

        apps/api/src/builder_cup/auth.py  ->  apps/api
        docs/api-spec.md                  ->  docs
        README.md                         ->  (unknown)

    Two levels, because one is usually too coarse (`apps` holds everything) and three is
    usually too fine (every feature looks like its own speciality). Only *directories*
    count: taking the first two parts of `docs/api-spec.md` made the file itself an area,
    so every document looked like a separate speciality and nobody was familiar with any
    of them.
    """
    parts = [p for p in (path or "").replace("\\", "/").split("/") if p and p != "."]
    if len(parts) <= 1:
        return UNKNOWN  # a file at the root belongs to no area in particular
    return "/".join(parts[: 2 if len(parts) > 2 else 1])


def by_person(linked: dict, commits: list) -> dict:
    """{person: {area: commits}} from the commits that were tied to a task.

    It reads every commit, not only the linked ones — a person's history is a fact about
    them, and does not depend on whether this agent worked out which task it belonged to.
    """
    _ = linked
    out: dict[str, dict[str, int]] = {}
    for commit in commits or []:
        who = (commit.get("name") or commit.get("author") or "").strip()
        if not who:
            continue
        for path in commit.get("files") or []:
            area = area_of(path)
            if not area:
                continue
            out.setdefault(who, {})
            out[who][area] = out[who].get(area, 0) + 1
    return out


def task_areas(linked: dict) -> dict:
    """{task key: the area its own commits live in}, when its commits agree on one."""
    out: dict[str, str] = {}
    for key, bundle in (linked or {}).items():
        counts: dict[str, int] = {}
        for commit in bundle.get("commits") or []:
            for path in commit.get("files") or []:
                area = area_of(path)
                if area:
                    counts[area] = counts.get(area, 0) + 1
        if counts:
            out[key] = max(counts, key=lambda a: counts[a])
    return out


def checker(linked: dict, commits: list, min_commits: int = MIN_COMMITS):
    """Build `can_take(task, person)` for capacity.rebalance, or None when it cannot judge.

    Returning None rather than a permissive function matters: a caller can then say "no
    handover evidence" instead of quietly implying every proposed move was vetted.
    """
    history = by_person(linked, commits)
    areas = task_areas(linked)
    if not history or not areas:
        return None

    def can_take(task, person: str) -> bool:
        area = areas.get(getattr(task, "key", ""), UNKNOWN)
        if not area:
            return True  # nothing known about the work — not a reason to refuse
        return history.get(person, {}).get(area, 0) >= min_commits

    return can_take


def summary(linked: dict, commits: list) -> dict:
    """What the check is working from, for a report that has to show its evidence."""
    history = by_person(linked, commits)
    return {
        "people": {who: sorted(areas) for who, areas in sorted(history.items())},
        "task_areas": task_areas(linked),
        "min_commits": MIN_COMMITS,
    }
