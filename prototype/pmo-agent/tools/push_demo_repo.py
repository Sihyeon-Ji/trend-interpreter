"""시뮬레이션 세계를 진짜 GitHub 비공개 저장소로 올린다 (시연용).

왜 진짜 저장소가 필요한가: 시연에서 "저장소를 읽습니다"라고 말하려면 실제로 읽어야 한다.
JSON 픽스처는 테스트용으로 남기고, 시연만 진짜 API 를 탄다 (`REPO_BACKEND=github`).

왜 지금 올려야 하는가: **PR 생성 시각은 조작할 수 없다.** 커밋 날짜는 과거로 쓸 수 있지만
PR 은 항상 '지금' 만들어진다. 지금 열어 두면 시연 때는 진짜로 묵은 PR 이 된다.

구조:
  develop            완료된 작업의 커밋 (과거 날짜)
  feat/echo-NN       아직 안 끝난 작업 — 여기서 PR 을 연다

한계 (정직하게):
  · 커밋 작성자는 4명으로 보이지만 GitHub 계정과 연결되지는 않는다 (이메일이 가상이라서)
  · PR 작성자는 전부 인증된 계정 하나다
  · 협업자가 본인뿐이라 리뷰어 지정은 못 한다 — signals 는 '리뷰어 미지정'으로 처리한다

실행:
  python tools/push_demo_repo.py                 무엇을 올릴지 미리보기
  python tools/push_demo_repo.py --approve       실제 생성·푸시
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

DEFAULT_REPO = "echo-pmo-demo"
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
        raise RuntimeError(f"{' '.join(args[:3])} 실패: {(out.stderr or out.stdout)[:300]}")
    return (out.stdout or "").strip()


def plan(today: dt.date | None = None) -> dict:
    """올릴 내용. 열린 PR 만 실제로 만든다 — 머지된 PR 은 신호에 쓰이지 않는다."""
    world = world_mod.simulate(today)
    board = world_mod.to_board(world)
    repo = world_mod.to_repo(world, board)
    open_pulls = [p for p in repo["pulls"] if p["state"] == "open"]
    open_keys = {p["title"].split()[0] for p in open_pulls}
    trunk = [c for c in reversed(repo["commits"]) if _key(c) not in open_keys]
    return {
        "world": world,
        "board": board,
        "repo": repo,
        "open_pulls": open_pulls,
        "open_keys": open_keys,
        "trunk": trunk,  # 시간순 (오래된 것부터)
        "branch_commits": {
            key: [c for c in reversed(repo["commits"]) if _key(c) == key] for key in open_keys
        },
    }


def _key(commit: dict) -> str:
    return commit["message"].split()[0]


def _commit(cwd: str, commit: dict) -> None:
    """파일 한 줄을 더하고, 작성 시각을 과거로 못 박아 커밋한다."""
    key = _key(commit)
    path = os.path.join(cwd, "work", f"{key}.md")
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
            "# echo-pmo-demo\n\n"
            "PMO 에이전트 시연용 **가상** 저장소입니다. 실제 제품 코드가 아닙니다.\n\n"
            "`prototype/pmo-agent` 의 세계 시뮬레이션에서 생성됐습니다 — "
            "등장인물·작업 내용은 전부 가상입니다.\n"
        )
    run(["git", "add", "-A"], cwd)
    run(["git", "commit", "-m", "chore: 시연용 가상 저장소 초기화"], cwd)

    for commit in data["trunk"]:
        _commit(cwd, commit)

    for key, commits in sorted(data["branch_commits"].items()):
        if not commits:
            continue
        branch = f"feat/{key.lower()}"
        run(["git", "checkout", "-b", branch, BRANCH], cwd)
        for commit in commits:
            _commit(cwd, commit)
        run(["git", "checkout", BRANCH], cwd)


def push(data: dict, cwd: str, owner: str, name: str) -> dict:
    gh = gh_path()
    full = f"{owner}/{name}"
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
            "PMO 에이전트 시연용 가상 저장소 (합성 데이터)",
        ],
        cwd,
    )
    run(["git", "push", "--all", "origin"], cwd)

    made = []
    for pull in data["open_pulls"]:
        key = pull["title"].split()[0]
        branch = f"feat/{key.lower()}"
        if not data["branch_commits"].get(key):
            continue
        body = f"{pull['title']}\n\n시연용 가상 PR 입니다. 마지막 작업일: {pull['updated']}\n"
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
            made.append(f"{key}: 실패 {str(e)[:80]}")
    return {"repo": full, "pulls": made}


def main(argv: list) -> int:
    owner = run([gh_path(), "api", "user", "--jq", ".login"], os.getcwd())
    name = DEFAULT_REPO
    data = plan()
    print(f"대상: {owner}/{name}  (private)")
    print(f"  develop 커밋 {len(data['trunk'])}건")
    print(f"  브랜치 {len(data['branch_commits'])}개, PR {len(data['open_pulls'])}건")
    print("\n  열 PR:")
    for pull in data["open_pulls"][:6]:
        print(f"    {pull['title'][:48]:<48} 마지막 작업 {pull['updated']}")
    if len(data["open_pulls"]) > 6:
        print(f"    … 외 {len(data['open_pulls']) - 6}건")

    if "--approve" not in argv:
        print("\n미리보기입니다. 실제로 만들려면 --approve 를 붙이세요.")
        return 0

    cwd = tempfile.mkdtemp(prefix="echo-demo-")
    try:
        print("\n로컬 이력 생성 중…")
        build_local(data, cwd)
        print("GitHub 에 생성·푸시 중…")
        result = push(data, cwd, owner, name)
        print(f"\n완료: https://github.com/{result['repo']}")
        print(f"  PR {len(result['pulls'])}건 생성")
        print(f"\n.env 에 넣으세요:  GITHUB_REPO={result['repo']}")
        print("시연 시:  REPO_BACKEND=github")
    finally:
        shutil.rmtree(cwd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
