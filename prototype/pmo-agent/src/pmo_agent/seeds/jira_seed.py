"""시드를 실제 Jira 샌드박스에 생성한다.

data/seed.py 가 만든 40건을 그대로 Jira 이슈로 올린다 — 요약·마감일·스토리포인트·상태·Blocks
의존관계까지.

담당자: 샌드박스에는 실제 계정이 하나뿐이라 가상 인물 4명을 배정할 수 없다.
        대신 `owner-<이름>` 라벨로 싣고, schedule.owner_label() 이 이를 담당자로 읽는다.

상태: 이 프로젝트의 상태 이름이 한국어(할 일/진행 중/완료)라 시드의 영어 상태를 매핑한다.

안전: 쓰기는 WRITE_ALLOWLIST 를 통과해야 하고, 이 스크립트는 --approve 없이는 아무것도 만들지
않는다.

실행:
  python data/seed_jira.py                    무엇을 만들지 미리보기 (dry-run)
  python data/seed_jira.py --approve          실제 생성
  python data/seed_jira.py --approve --limit 3   앞 3건만 (연결 확인용)
  python data/seed_jira.py --approve --from 3    앞 3건은 건너뛰고 이어서
"""

from __future__ import annotations

import datetime as dt
import sys

from pmo_agent import schedule
from pmo_agent.adapters.jira import Jira, WriteBlocked
from pmo_agent.seeds import board as seed

STATUS_MAP = {"To Do": "할 일", "In Progress": "진행 중", "In Review": "진행 중", "Done": "완료"}


def plan(today: dt.date | None = None, limit: int = 0) -> list:
    """생성할 이슈 목록 (Jira 필드 형태로 정리)."""
    issues = seed.build(today or dt.date.today())
    if limit:
        keys = {i["key"] for i in issues[:limit]}
        issues = issues[:limit]
        for i in issues:  # 범위 밖을 가리키는 링크는 떼어낸다
            i["fields"]["issuelinks"] = [
                link
                for link in i["fields"]["issuelinks"]
                if link.get("outwardIssue", {}).get("key") in keys
            ]
    out = []
    for i in issues:
        f = i["fields"]
        out.append(
            {
                "seed_key": i["key"],
                "summary": f["summary"],
                "duedate": f["duedate"],
                "points": f["customfield_10016"],
                "owner": (f.get("assignee") or {}).get("displayName", ""),
                "status": STATUS_MAP.get((f.get("status") or {}).get("name", ""), "할 일"),
                "blocks": [
                    link["outwardIssue"]["key"]
                    for link in f["issuelinks"]
                    if "outwardIssue" in link
                ],
            }
        )
    return out


def create(
    jira: Jira,
    rows: list,
    approve: bool = False,
    pre: dict | None = None,
    link_rows: list | None = None,
) -> dict:
    """이슈 생성 → 상태 전이 → 링크 연결. seed_key → 실제 Jira key 매핑을 돌려준다.

    pre: 이미 만들어 둔 seed_key→실제key (이어서 시드할 때).
    link_rows: 링크를 걸 대상 행 (기본은 이번에 만든 rows). 이어서 시드할 때는 전체를 넘긴다.
    """
    mapping, errors = dict(pre or {}), []
    fresh = set()
    for r in rows:
        extra = {"labels": [f"{schedule.OWNER_PREFIX}{r['owner']}"] if r["owner"] else []}
        if r["points"]:
            extra["customfield_10016"] = r["points"]
        try:
            res = jira.create_issue(
                r["summary"], duedate=r["duedate"], extra=extra, approve=approve
            )
        except WriteBlocked as e:
            return {"error": f"쓰기 차단: {e}", "created": mapping}
        except Exception as e:
            errors.append({"seed_key": r["seed_key"], "step": "create", "error": str(e)[:200]})
            continue
        if not approve:
            mapping[r["seed_key"]] = "(dry-run)"
            continue
        mapping[r["seed_key"]] = res["key"]
        fresh.add(r["seed_key"])
        if r["status"] != "할 일":
            try:
                jira.transition(res["key"], r["status"], approve=True)
            except Exception as e:
                errors.append(
                    {"seed_key": r["seed_key"], "step": "transition", "error": str(e)[:200]}
                )
    if approve:
        for r in link_rows or rows:
            for b in r["blocks"]:
                # 이번에 새로 만든 쪽이 한 쪽이라도 끼어야 건다 — 기존 링크 중복 생성을 피한다
                if (
                    r["seed_key"] in mapping
                    and b in mapping
                    and (r["seed_key"] in fresh or b in fresh)
                ):
                    try:
                        jira.link(mapping[r["seed_key"]], mapping[b], approve=True)
                    except Exception as e:
                        errors.append(
                            {"seed_key": r["seed_key"], "step": "link", "error": str(e)[:200]}
                        )
    return {"created": mapping, "errors": errors}


def main(argv) -> None:
    approve = "--approve" in argv
    limit = 0
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    start = int(argv[argv.index("--from") + 1]) if "--from" in argv else 0
    all_rows = plan(limit=limit)
    # 이미 만든 앞부분은 건너뛴다. 키가 1:1로 맞으므로 seed_key 를 그대로 실제 key 로 쓴다.
    pre = {r["seed_key"]: r["seed_key"] for r in all_rows[:start]}
    rows = all_rows[start:]
    j = Jira()
    print(f"대상: {j.site} / 프로젝트 {j.project}")
    print(f"생성할 이슈 {len(rows)}건  (담당자는 owner-* 라벨로 기록)")
    for r in rows[:5]:
        print(
            f"  {r['seed_key']:>8}  {r['summary'][:34]:<34} {r['status']:<6} "
            f"마감 {r['duedate']} · {r['points']}점 · {r['owner']}"
            + (f" · blocks {','.join(r['blocks'])}" if r["blocks"] else "")
        )
    if len(rows) > 5:
        print(f"  … 외 {len(rows) - 5}건")
    if not approve:
        print("\n미리보기입니다. 실제로 만들려면 --approve 를 붙이세요.")
        return
    print("\n생성 중…")
    out = create(j, rows, approve=True, pre=pre, link_rows=all_rows)
    if out.get("error"):
        print(" ", out["error"])
        return
    print(f" 생성 {len(out['created']) - len(pre)}건, 오류 {len(out['errors'])}건")
    for e in out["errors"][:5]:
        print("  오류:", e)


if __name__ == "__main__":
    main(sys.argv[1:])
