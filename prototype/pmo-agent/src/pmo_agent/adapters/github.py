"""GitHub 어댑터 — 코드에서 오는 '실제 진척' 신호를 읽는다.

보드(Jira)는 사람이 적은 상태를 담고, 여기는 실제로 일어난 일을 담는다.
둘을 맞대야만 나오는 것이 있다:
"티켓은 진행 중인데 8일째 커밋이 없다", "완료인데 PR 이 아직 열려 있다".

**읽기 전용이다.** 이 모듈에는 쓰기 메서드가 아예 없다 — 실수로 남의 저장소에 무언가를 만들 경로가
없다.
인증은 이미 로그인된 `gh` CLI 를 그대로 쓴다 (토큰을 .env 에 따로 두지 않는다).

설정: .env 의 GITHUB_REPO=owner/repo
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

from pmo_agent.env import env

TIMEOUT = 60
# Windows 에서 winget 설치 직후 PATH 가 갱신되지 않은 셸을 위한 보조 경로
FALLBACK_GH = r"C:\Program Files\GitHub CLI\gh.exe"


class GitHubError(RuntimeError):
    """gh 실행 또는 API 호출 실패."""


def gh_path() -> str:
    p = shutil.which("gh")
    if p:
        return p
    if os.path.exists(FALLBACK_GH):
        return FALLBACK_GH
    raise GitHubError(
        "gh CLI 를 찾을 수 없다. `winget install GitHub.cli` 후 새 터미널에서 `gh auth login`."
    )


class GitHub:
    """gh CLI 를 통해 저장소를 읽는다. 쓰기 메서드는 의도적으로 없다."""

    def __init__(self, repo: str | None = None):
        self.repo = (repo or env("GITHUB_REPO", "")).strip()
        if not self.repo or "/" not in self.repo:
            raise GitHubError("GITHUB_REPO 미설정 — .env 에 owner/repo 형식으로 넣어라")

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
            raise GitHubError(f"gh api 시간 초과: {path}") from None
        except OSError as e:
            raise GitHubError(f"gh 실행 실패: {e}") from None
        if out.returncode != 0:
            raise GitHubError(f"gh api {path} 실패: {(out.stderr or '')[:300]}")
        text = (out.stdout or "").strip()
        if not text:
            return []
        if jq:  # --jq 는 줄 단위 출력이라 각 줄을 파싱한다
            rows = []
            for line in text.splitlines():
                line = line.strip()
                if line:
                    rows.append(json.loads(line) if line[0] in '[{"' else line)
            return rows
        return json.loads(text)

    # ---------- 읽기 ----------
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
        """최근 커밋. 메시지 첫 줄과 작성자, 날짜만 남긴다."""
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
                    # 표시는 login 우선, 동일인 판정은 email 로 한다.
                    # 커밋 이메일이 계정에 연결돼 있지 않으면 login 이 비고 이름만 남는다.
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
        """PR 목록. 리뷰 대기 판단에 필요한 최소 필드만."""
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
        """PR 하나에 달린 커밋. 기본 브랜치에 아직 안 올라온 작업을 보기 위한 것."""
        raw = self._api(f"repos/{{repo}}/pulls/{int(number)}/commits?per_page=100")
        return self._shape(raw)

    def snapshot(self, commit_limit: int = 100) -> dict:
        """한 번에 필요한 것을 모아 온다 — 신호 계산은 agent/signals.py 가 한다.

        기본 브랜치 커밋만 보면 **진행 중인 작업이 통째로 안 보인다** — 아직 머지되지
        않았으니 당연하다. 그러면 "진행 중인데 커밋이 하나도 없다"는 엉뚱한 신호가 나온다.
        그래서 열린 PR 의 커밋을 함께 가져와 합친다.
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
                continue  # PR 하나를 못 읽어도 나머지는 살린다
        commits.sort(key=lambda c: c["date"], reverse=True)
        return {
            "repo": self.repo,
            "info": self.repo_info(),
            "commits": commits,
            "pulls": pulls,
            "branches": self.branches(),
        }


if __name__ == "__main__":
    g = GitHub()
    print("계정:", g.whoami(), "| 저장소:", g.repo)
    s = g.snapshot(20)
    print("기본 브랜치:", s["info"]["default_branch"], "| 브랜치", len(s["branches"]), "개")
    print("커밋", len(s["commits"]), "건 | PR", len(s["pulls"]), "건")
    for c in s["commits"][:5]:
        print(f"  {c['date']}  {c['author']:<12} {c['message'][:50]}")
