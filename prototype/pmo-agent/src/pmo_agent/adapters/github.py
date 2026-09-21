"""The GitHub adapter — it reads the *actual progress* signal coming from the code.

The board (Jira) holds the status a person wrote down; this holds what really happened.
Some things only appear when the two are lined up:
"the ticket is in progress but there has been no commit for eight days", "it is done but the
pull request is still open".

**Read-only.** There is no write method in this module at all — there is no path by which we
could accidentally create something in someone else's repository.
Auth rides on an already logged-in `gh` CLI (no separate token in .env).

Setting: GITHUB_REPO=owner/repo in .env
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from pmo_agent.env import data_dir, env

TIMEOUT = 60
# A fallback path for Windows shells whose PATH has not refreshed after a winget install
FALLBACK_GH = r"C:\Program Files\GitHub CLI\gh.exe"


# ---------------------------------------------------------------------------
# The changed-file cache.
#
# `REPO_FILES=on` costs one API call per commit, and against a real repository that
# was 55 seconds for 64 commits — most of a demo's running time, paid again on
# every run.
#
# Caching it is not a guess about staleness. A git sha *is* the hash of the commit's
# content: the list of files a given sha touched cannot change, so a hit is as good
# as a fetch, forever. Only successful fetches are stored — a failed call produces
# an empty list, and remembering that would turn one bad network moment into a
# commit that permanently looks like it touched nothing.
# ---------------------------------------------------------------------------

CACHE_FILE = "commit_files.json"
CACHE_MAX = 4000  # per repository; a demo repo has tens, this is room to spare


def _cache_path():
    return data_dir() / CACHE_FILE


def cache_load() -> dict:
    try:
        with open(_cache_path(), encoding="utf-8") as handle:
            found = json.load(handle)
        return found if isinstance(found, dict) else {}
    except (OSError, ValueError):
        return {}  # no cache, or one somebody edited by hand. Either way, start over


def cache_save(cache: dict) -> None:
    for repo, entries in cache.items():
        if len(entries) > CACHE_MAX:
            # dicts keep insertion order, so the oldest entries are the ones at the front
            cache[repo] = dict(list(entries.items())[-CACHE_MAX:])
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(cache, handle)
    except OSError:
        pass  # a cache that cannot be written is a slow run, not a failure


class GitHubError(RuntimeError):
    """gh failed to run, or the API call failed."""


def gh_path() -> str:
    p = shutil.which("gh")
    if p:
        return p
    if os.path.exists(FALLBACK_GH):
        return FALLBACK_GH
    raise GitHubError(
        "cannot find the gh CLI. Run `winget install GitHub.cli`, "
        "then `gh auth login` in a new terminal."
    )


class GitHub:
    """Reads a repository through the gh CLI. There are deliberately no write methods."""

    def __init__(self, repo: str | None = None):
        self.repo = (repo or env("GITHUB_REPO", "")).strip()
        if not self.repo or "/" not in self.repo:
            raise GitHubError("GITHUB_REPO is not set — put owner/repo in .env")

    # ---------- low level ----------
    def _api(self, path: str, jq: str | None = None):
        cmd = [gh_path(), "api", path.replace("{repo}", self.repo)]
        if jq:
            cmd += ["--jq", jq]
        try:
            out = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=TIMEOUT,
                encoding="utf-8",
                errors="replace",
            )
        except subprocess.TimeoutExpired:
            raise GitHubError(f"gh api timed out: {path}") from None
        except OSError as e:
            raise GitHubError(f"could not run gh: {e}") from None
        if out.returncode != 0:
            raise GitHubError(f"gh api {path} failed: {(out.stderr or '')[:300]}")
        text = (out.stdout or "").strip()
        if not text:
            return []
        if jq:  # --jq prints line by line, so parse each line
            rows = []
            for line in text.splitlines():
                line = line.strip()
                if line:
                    rows.append(json.loads(line) if line[0] in '[{"' else line)
            return rows
        return json.loads(text)

    # ---------- reads ----------
    def whoami(self) -> str:
        r = self._api("user", ".login")
        return r[0] if r else "?"

    def repo_info(self) -> dict:
        r = self._api("repos/{repo}")
        return {
            "full_name": r.get("full_name"),
            "private": r.get("private"),
            "default_branch": r.get("default_branch"),
            "pushed_at": r.get("pushed_at"),
            "open_issues": r.get("open_issues_count"),
        }

    def commits(self, limit: int = 100, branch: str = "") -> list:
        """Recent commits, keeping only the subject line, the author and the date."""
        q = f"repos/{{repo}}/commits?per_page={min(int(limit), 100)}"
        if branch:
            q += f"&sha={branch}"
        return self._shape(self._api(q))

    @staticmethod
    def _shape(raw: list) -> list:
        out = []
        for c in raw:
            ca = c.get("commit", {}).get("author", {}) or {}
            login = (c.get("author") or {}).get("login")
            out.append(
                {
                    "sha": c["sha"][:7],
                    "date": (ca.get("date") or "")[:10],
                    # Display prefers login; identity is decided by email.
                    # If the commit email is not tied to an account, login comes
                    # back empty and only the git name remains.
                    "author": login or ca.get("name", "?"),
                    "login": login,
                    "name": ca.get("name", ""),
                    "email": (ca.get("email") or "").lower(),
                    "message": (c.get("commit", {}).get("message") or "").split("\n")[0],
                    "url": c.get("html_url", ""),
                }
            )
        return out

    def pulls(self, state: str = "all", limit: int = 50) -> list:
        """Pull requests, with only the fields the review-wait check needs."""
        raw = self._api(f"repos/{{repo}}/pulls?state={state}&per_page={min(int(limit), 100)}")
        return [
            {
                "number": p["number"],
                "title": p.get("title", ""),
                "state": p.get("state"),
                "draft": bool(p.get("draft")),
                "author": (p.get("user") or {}).get("login", "?"),
                "branch": (p.get("head") or {}).get("ref", ""),
                "created": (p.get("created_at") or "")[:10],
                "updated": (p.get("updated_at") or "")[:10],
                "merged": bool(p.get("merged_at")),
                "reviewers": [r.get("login") for r in (p.get("requested_reviewers") or [])],
                "url": p.get("html_url", ""),
            }
            for p in raw
        ]

    def reviews(self, number: int) -> list:
        raw = self._api(f"repos/{{repo}}/pulls/{int(number)}/reviews")
        return [
            {
                "user": (r.get("user") or {}).get("login", "?"),
                "state": r.get("state"),
                "at": (r.get("submitted_at") or "")[:10],
            }
            for r in raw
        ]

    def branches(self) -> list:
        return [b.get("name") for b in self._api("repos/{repo}/branches?per_page=100")]

    def collaborators(self) -> list:
        raw = self._api("repos/{repo}/collaborators?per_page=100")
        return [{"login": c.get("login"), "role": c.get("role_name")} for c in raw]

    def pull_commits(self, number: int) -> list:
        """The commits on one pull request — for seeing work not yet on the default branch."""
        raw = self._api(f"repos/{{repo}}/pulls/{int(number)}/commits?per_page=100")
        return self._shape(raw)

    def commit_files(self, sha: str) -> list:
        """The paths one commit touched. One API call each — the list endpoint omits them."""
        detail = self._api(f"repos/{{repo}}/commits/{sha}")
        return [f["filename"] for f in (detail.get("files") or [])]

    def snapshot(self, commit_limit: int = 100, with_files: bool = False) -> dict:
        """Fetch everything needed in one go — signals.py does the calculating.

        Look only at the default branch and **work in flight disappears entirely** — of course
        it does, it has not been merged. Then out comes the nonsense signal "in progress with
        no commits at all". So the open pull requests' commits are fetched and merged in.
        """
        pulls = self.pulls("all")
        commits = self.commits(commit_limit)
        seen = {c["sha"] for c in commits}
        for pull in pulls:
            if pull["state"] != "open":
                continue
            try:
                for commit in self.pull_commits(pull["number"]):
                    if commit["sha"] not in seen:
                        seen.add(commit["sha"])
                        commits.append(commit)
            except GitHubError:
                continue  # one unreadable pull request should not lose the rest
        commits.sort(key=lambda c: c["date"], reverse=True)
        if with_files:
            # Worth roughly a quarter more links and a good deal more confidence, because
            # the path is what separates two tasks the same person is working on. It costs
            # one API call per commit, which is why the caller has to ask for it — and why
            # the answers are kept: a sha's file list is fixed for good.
            cache = cache_load()
            mine = cache.setdefault(self.repo, {})
            fetched = 0
            for commit in commits:
                sha = commit["sha"]
                if sha in mine:
                    commit["files"] = list(mine[sha])
                    continue
                try:
                    commit["files"] = self.commit_files(sha)
                except GitHubError:
                    commit["files"] = []  # not remembered; a failure is not a fact
                    continue
                mine[sha] = commit["files"]
                fetched += 1
            if fetched:
                cache_save(cache)
        return {
            "repo": self.repo,
            "info": self.repo_info(),
            "commits": commits,
            "pulls": pulls,
            "branches": self.branches(),
        }


if __name__ == "__main__":
    g = GitHub()
    print("account:", g.whoami(), "| repo:", g.repo)
    s = g.snapshot(20)
    print("default branch:", s["info"]["default_branch"], "|", len(s["branches"]), "branches")
    print(len(s["commits"]), "commits |", len(s["pulls"]), "pull requests")
    for c in s["commits"][:5]:
        print(f"  {c['date']}  {c['author']:<12} {c['message'][:50]}")
