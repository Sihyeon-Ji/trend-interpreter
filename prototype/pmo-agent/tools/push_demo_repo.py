"""Push the simulated world into a real private GitHub repository (for the demo).

Why a real repository: to say "it reads the repository" in a demo, it has to actually read one.
The JSON fixtures stay for the tests; only the demo goes over the real API (`REPO_BACKEND=github`).

Why now: **a pull request's creation time cannot be faked.** Commit dates can be written into
the past; a PR is always created *now*. Open them today and by demo day they are genuinely stale.

Layout:
  develop          commits for finished work (backdated)
  feat/auth etc.   work still in flight — the pull requests are opened from here

No ticket keys in the commit messages. Real repositories are like that, and joining things up
without a key is what this agent does (src/pmo_agent/linking.py).

Limitations, stated plainly:
  · there appear to be four commit authors, none tied to GitHub accounts (fictional emails)
  · every pull request is authored by the one authenticated account
  · with one collaborator, reviewers cannot be assigned — signals says "no reviewer assigned"

Run:
  python tools/push_demo_repo.py                 preview what would be pushed
  python tools/push_demo_repo.py --approve       create and push for real
  python tools/push_demo_repo.py --approve --reset  replace an existing repo with fresh data
"""

from __future__ import annotations

import datetime as dt
import os
import shutil
import subprocess
import sys
import tempfile

from pmo_agent.adapters.github import gh_path
from pmo_agent.seeds import world as world_mod

DEFAULT_REPO = "echo-app"  # a name that reads like a product repo — it looks real in the demo
BRANCH = "develop"


def run(args: list, cwd: str, env: dict | None = None, check: bool = True) -> str:
    out = subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, **(env or {})},
    )
    if check and out.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])} failed: {(out.stderr or out.stdout)[:300]}")
    return (out.stdout or "").strip()


def plan(today: dt.date | None = None) -> dict:
    """What to push. Only open pull requests are created — merged ones carry no signal."""
    world = world_mod.simulate(today)
    board = world_mod.to_board(world)
    repo = world_mod.to_repo(world, board)
    link_truth = repo["link_truth"]
    open_pulls = [p for p in repo["pulls"] if p["state"] == "open"]
    # The PR titles have no keys either, so pair them up by branch
    branch_to_key = {}
    for key, task in world.tasks.items():
        branch_to_key[world_mod.artifact(task)["branch"]] = key
    open_keys = {branch_to_key.get(p["branch"], "") for p in open_pulls} - {""}
    trunk = [c for c in reversed(repo["commits"]) if _key(c, link_truth) not in open_keys]
    return {
        "world": world,
        "board": board,
        "repo": repo,
        "open_pulls": open_pulls,
        "open_keys": open_keys,
        "trunk": trunk,  # chronological (oldest first)
        "link_truth": link_truth,
        "branch_of": {key: world_mod.artifact(world.tasks[key])["branch"] for key in open_keys},
        "branch_commits": {
            key: [c for c in reversed(repo["commits"]) if _key(c, link_truth) == key]
            for key in open_keys
        },
    }


def _key(commit: dict, link_truth: dict) -> str:
    """Which task this commit belonged to — the commit itself does not say.

    To look like a real repository, the message must not carry a ticket key.
    Only the simulation's answer key (link_truth) knows where it goes.
    """
    return link_truth.get(commit["sha"], "")


def _commit(cwd: str, commit: dict) -> None:
    """Touch the real file the commit points at, and pin its authoring time to the past."""
    rel = (commit.get("files") or ["docs/notes.md"])[0]
    path = os.path.join(cwd, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"- {commit['date']} {commit['message']}\n")
    stamp = f"{commit['date']}T10:00:00+09:00"
    run(["git", "add", "-A"], cwd)
    run(
        ["git", "commit", "-m", commit["message"], "--date", stamp],
        cwd,
        env={
            "GIT_AUTHOR_NAME": commit["name"],
            "GIT_AUTHOR_EMAIL": commit["email"],
            "GIT_AUTHOR_DATE": stamp,
            "GIT_COMMITTER_NAME": commit["name"],
            "GIT_COMMITTER_EMAIL": commit["email"],
            "GIT_COMMITTER_DATE": stamp,
        },
    )


def build_local(data: dict, cwd: str) -> None:
    run(["git", "init", "-b", BRANCH], cwd)
    with open(os.path.join(cwd, "README.md"), "w", encoding="utf-8") as handle:
        handle.write(
            "# echo-app\n\n"
            "A **fictional** repository for demonstrating the PMO agent. Not real product code.\n\n"
            "Generated from the world simulation in `prototype/pmo-agent` — "
            "every person and every piece of work here is invented.\n"
        )
    run(["git", "add", "-A"], cwd)
    run(["git", "commit", "-m", "chore: initialise the demo repository"], cwd)

    for commit in data["trunk"]:
        _commit(cwd, commit)

    for key, commits in sorted(data["branch_commits"].items()):
        if not commits:
            continue
        branch = data["branch_of"][key]
        run(["git", "checkout", "-b", branch, BRANCH], cwd)
        for commit in commits:
            _commit(cwd, commit)
        run(["git", "checkout", BRANCH], cwd)


def push(data: dict, cwd: str, owner: str, name: str, reset: bool = False) -> dict:
    """Create the repository if it is not there, or replace its contents (--reset).

    Replacing does not delete the repository — deletion needs a separate scope (delete_repo),
    and there is no reason to ask a person for more permission just to change demo data.
    Instead the history is force-pushed, leftover pull requests are closed, and unused branches go.
    """
    gh = gh_path()
    full = f"{owner}/{name}"
    exists = (
        subprocess.run(
            [gh, "repo", "view", full, "--json", "name"], capture_output=True, text=True
        ).returncode
        == 0
    )

    if not exists:
        run(
            [
                gh,
                "repo",
                "create",
                full,
                "--private",
                "--source=.",
                "--push",
                "--description",
                "The Echo product repository (synthetic data for the PMO agent demo)",
            ],
            cwd,
        )
    else:
        if not reset:
            raise RuntimeError(f"{full} already exists. Add --reset to replace it.")
        for number in _open_pr_numbers(gh, full):
            run(
                [
                    gh,
                    "pr",
                    "close",
                    str(number),
                    "--repo",
                    full,
                    "--comment",
                    "Closing while the demo data is rebuilt in a new shape.",
                ],
                cwd,
                check=False,
            )
        run(["git", "remote", "add", "origin", f"https://github.com/{full}.git"], cwd, check=False)
        run(["git", "push", "--force", "origin", BRANCH], cwd)
        for stale in _remote_branches(gh, full):
            if stale not in {BRANCH, *data["branch_of"].values()}:
                run(
                    [gh, "api", "-X", "DELETE", f"repos/{full}/git/refs/heads/{stale}"],
                    cwd,
                    check=False,
                )

    run(["git", "push", "--force", "--all", "origin"], cwd)

    made = []
    by_branch = {v: k for k, v in data["branch_of"].items()}
    for pull in data["open_pulls"]:
        branch = pull["branch"]
        key = by_branch.get(branch, "")
        if not key or not data["branch_commits"].get(key):
            continue
        body = f"{pull['title']}\n\nA fictional demo PR. Last worked on: {pull['updated']}\n"
        try:
            url = run(
                [
                    gh,
                    "pr",
                    "create",
                    "--repo",
                    full,
                    "--base",
                    BRANCH,
                    "--head",
                    branch,
                    "--title",
                    pull["title"],
                    "--body",
                    body,
                ],
                cwd,
            )
            made.append(url.splitlines()[-1] if url else key)
        except RuntimeError as e:
            made.append(f"{key}: failed {str(e)[:80]}")
    return {"repo": full, "pulls": made}


def _open_pr_numbers(gh: str, full: str) -> list:
    out = subprocess.run(
        [
            gh,
            "pr",
            "list",
            "--repo",
            full,
            "--state",
            "open",
            "--json",
            "number",
            "--jq",
            ".[].number",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return [int(x) for x in (out or "").split() if x.isdigit()]


def _remote_branches(gh: str, full: str) -> list:
    out = subprocess.run(
        [gh, "api", f"repos/{full}/branches", "--jq", ".[].name"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    ).stdout
    return [x.strip() for x in (out or "").splitlines() if x.strip()]


def main(argv: list) -> int:
    owner = run([gh_path(), "api", "user", "--jq", ".login"], os.getcwd())
    name = DEFAULT_REPO
    data = plan()
    print(f"target: {owner}/{name}  (private)")
    print(f"  {len(data['trunk'])} commits on develop")
    print(f"  {len(data['branch_commits'])} branches, {len(data['open_pulls'])} pull requests")
    print("\n  pull requests to open:")
    for pull in data["open_pulls"][:6]:
        print(f"    {pull['title'][:48]:<48} last worked on {pull['updated']}")
    if len(data["open_pulls"]) > 6:
        print(f"    … and {len(data['open_pulls']) - 6} more")

    if "--approve" not in argv:
        print("\nThis is a preview. Add --approve to create them.")
        return 0

    cwd = tempfile.mkdtemp(prefix="echo-demo-")
    try:
        print("\nbuilding local history…")
        build_local(data, cwd)
        print("creating and pushing to GitHub…")
        result = push(data, cwd, owner, name, reset="--reset" in argv)
        print(f"\ndone: https://github.com/{result['repo']}")
        print(f"  {len(result['pulls'])} pull requests created")
        print(f"\nPut this in .env:  GITHUB_REPO={result['repo']}")
        print("For the demo:  REPO_BACKEND=github")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
