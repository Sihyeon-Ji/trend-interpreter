"""보드와 코드를 맞대는 층 — 한쪽만 봐서는 안 보이는 것을 찾는다.

Jira 는 '사람이 적은 상태'를 담고, GitHub 은 '실제로 일어난 일'을 담는다.
둘 다 맞아야 정상이고, 어긋나면 그게 신호다.

  · 티켓은 진행 중인데 코드 활동이 없다        → 멈춰 있는데 아무도 모른다
  · 티켓은 할 일인데 커밋이 이미 있다          → 상태가 현실을 못 따라간다
  · 티켓은 완료인데 PR 이 아직 열려 있다       → 조기 완료 처리
  · PR 이 며칠째 리뷰를 기다린다              → 사람 때문에 막힌 것 (capacity 와 같은 종류의 문제)

여기도 계산만 한다. 모델은 이 결과를 인용할 뿐이고, 쓰기는 승인 게이트를 거친다.
태스크-커밋 연결은 키 표기(ECHO-12)를 규칙으로 쓴다. 팀이 그 규칙을 안 쓰면 태스크 단위 신호는 비고,
저장소 단위 신호(기여 편중·리뷰 미가동·정체)는 그대로 나온다.
"""

from __future__ import annotations

import datetime as _dt
import re

from pmo_agent import schedule

KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d+)\b")
STALE_DAYS = 5  # 진행 중인데 이 기간 넘게 커밋이 없으면 '멈춤'으로 본다
REVIEW_WAIT_DAYS = 2  # PR 이 이 기간 넘게 리뷰를 기다리면 병목으로 본다


def keys_in(text: str) -> set:
    """문장에서 태스크 키를 뽑는다. 커밋 메시지·PR 제목·브랜치 이름에 쓴다."""
    return set(KEY_RE.findall((text or "").upper()))


def link(tasks: dict, commits: list, pulls: list) -> dict:
    """{태스크 키: {commits: [...], pulls: [...]}}. 보드에 없는 키는 버린다."""
    out: dict[str, dict[str, list]] = {k: {"commits": [], "pulls": []} for k in tasks}
    for c in commits:
        for k in keys_in(c.get("message", "")) & out.keys():
            out[k]["commits"].append(c)
    for p in pulls:
        found = keys_in(p.get("title", "")) | keys_in(p.get("branch", ""))
        for k in found & out.keys():
            out[k]["pulls"].append(p)
    return out


def _days(a: str, today: _dt.date) -> int | None:
    """ISO 날짜 문자열 → 오늘까지 경과 일수 (달력일)."""
    if not a:
        return None
    try:
        return (today - _dt.date.fromisoformat(a[:10])).days
    except ValueError:
        return None


def mismatches(tasks: dict, linked: dict, today: _dt.date) -> list:
    """보드 상태와 코드 활동이 어긋나는 태스크. 근거(커밋·PR)를 함께 준다."""
    out = []
    for k, t in tasks.items():
        cs, ps = linked.get(k, {}).get("commits", []), linked.get(k, {}).get("pulls", [])
        last = max((c["date"] for c in cs), default="")
        idle = _days(last, today)
        open_prs = [p for p in ps if p["state"] == "open"]
        in_progress = not t.is_done and (t.status or "").strip().lower() not in (
            "to do",
            "todo",
            "할 일",
            "할일",
            "backlog",
            "open",
            "",
        )

        if t.is_done and open_prs:
            out.append(
                _m(
                    k,
                    t,
                    "done_with_open_pr",
                    f"완료 처리됐는데 PR #{open_prs[0]['number']} 이 아직 열려 있다",
                    [p["url"] for p in open_prs],
                )
            )
        elif in_progress and not cs:
            out.append(_m(k, t, "no_code_activity", "진행 중인데 연결된 커밋이 하나도 없다", []))
        elif in_progress and idle is not None and idle >= STALE_DAYS:
            out.append(
                _m(
                    k,
                    t,
                    "stalled",
                    f"진행 중인데 마지막 커밋이 {idle}일 전({last})이다",
                    [c["url"] for c in cs[:2]],
                )
            )
        elif not in_progress and not t.is_done and cs:
            out.append(
                _m(
                    k,
                    t,
                    "undeclared_progress",
                    f"보드는 '{t.status}'인데 커밋이 {len(cs)}건 있다 (마지막 {last})",
                    [c["url"] for c in cs[:2]],
                )
            )

        for p in open_prs:
            wait = _days(p["updated"], today)
            if not p["draft"] and wait is not None and wait >= REVIEW_WAIT_DAYS:
                out.append(
                    _m(
                        k,
                        t,
                        "review_waiting",
                        f"PR #{p['number']} 이 {wait}일째 리뷰 대기 중이다"
                        + (
                            f" (리뷰어 {', '.join(p['reviewers'])})"
                            if p["reviewers"]
                            else " (리뷰어 미지정)"
                        ),
                        [p["url"]],
                    )
                )
    order = {
        "done_with_open_pr": 0,
        "stalled": 1,
        "review_waiting": 2,
        "no_code_activity": 3,
        "undeclared_progress": 4,
    }
    out.sort(key=lambda r: (order.get(r["kind"], 9), r["key"]))
    return out


def _m(key, t, kind, detail, evidence):
    return {
        "key": key,
        "summary": t.summary,
        "assignee": t.assignee,
        "status": t.status,
        "kind": kind,
        "detail": detail,
        "evidence": evidence,
    }


def merge_identities(commits: list) -> dict:
    """같은 사람을 둘로 세지 않는다.

    커밋 이메일이 GitHub 계정에 연결돼 있지 않으면 login 이 비고 git 이름만 남는다.
    (실제로 한 사람이 'shji'(이름)와 'Sihyeon-Ji'(login)로 갈려 집중도가 0.71 로 낮게 나왔다.)
    그래서 이메일을 동일인 기준으로 쓰고, 표시 이름은 login 이 있으면 그쪽을 쓴다.
    """
    groups: dict[str, dict] = {}
    for c in commits:
        gid = c.get("email") or c.get("login") or c.get("author") or "?"
        g = groups.setdefault(gid, {"commits": 0, "login": None, "names": set()})
        g["commits"] += 1
        if c.get("login"):
            g["login"] = c["login"]
        if c.get("name"):
            g["names"].add(c["name"])
    out: dict[str, dict] = {}
    for g in groups.values():
        label = g["login"] or (sorted(g["names"])[0] if g["names"] else "?")
        row = out.setdefault(label, {"author": label, "commits": 0, "aliases": set()})
        row["commits"] += g["commits"]
        row["aliases"] |= g["names"] - {label}
    for row in out.values():
        row["aliases"] = sorted(row["aliases"])
    return out


def team_activity(snapshot: dict, today: _dt.date, days: int = 14) -> dict:
    """저장소 단위 신호. 태스크 키 규칙을 안 써도 이건 나온다."""
    commits = [c for c in snapshot.get("commits", []) if (_days(c["date"], today) or 999) <= days]
    merged = merge_identities(commits)
    by = {k: v["commits"] for k, v in merged.items()}
    total = sum(by.values())
    top = max(by.values()) if by else 0
    pulls = snapshot.get("pulls", [])
    open_prs = [p for p in pulls if p["state"] == "open"]
    stale_prs = [
        p
        for p in open_prs
        if not p["draft"] and (_days(p["updated"], today) or 0) >= REVIEW_WAIT_DAYS
    ]
    last = max((c["date"] for c in snapshot.get("commits", [])), default="")

    notes = []
    if total and len(by) == 1:
        notes.append(f"최근 {days}일 커밋 {total}건이 전부 {next(iter(by))} 한 사람에게서 나왔다")
    elif total and top / total >= 0.8:
        who = max(by, key=lambda name: by[name])
        notes.append(f"최근 {days}일 커밋의 {round(top / total * 100)}%가 {who} 한 사람이다")
    if not pulls:
        notes.append("PR 이 한 건도 없다 — 리뷰 절차가 아직 돌지 않는다")
    if stale_prs:
        notes.append(f"{len(stale_prs)}건의 PR 이 {REVIEW_WAIT_DAYS}일 넘게 리뷰를 기다린다")
    gap = _days(last, today)
    if gap is not None and gap >= STALE_DAYS:
        notes.append(f"마지막 커밋이 {gap}일 전({last})이다")
    if not total:
        notes.append(f"최근 {days}일 동안 커밋이 없다")

    return {
        "window_days": days,
        "commits": total,
        "contributors": sorted(merged.values(), key=lambda r: -r["commits"]),
        "concentration": round(top / total, 2) if total else 0.0,
        "open_prs": len(open_prs),
        "stale_prs": len(stale_prs),
        "branches": len(snapshot.get("branches", [])),
        "last_commit": last,
        "notes": notes,
    }


def summary(tasks: dict, snapshot: dict, today: _dt.date | None = None, days: int = 14) -> dict:
    """툴·리포트가 그대로 쓰는 한 덩어리."""
    today = today or _dt.date.today()
    linked = link(tasks, snapshot.get("commits", []), snapshot.get("pulls", []))
    covered = sum(1 for v in linked.values() if v["commits"] or v["pulls"])
    in_use = covered > 0
    # 커밋·PR 에 태스크 키를 안 쓰는 저장소에서는 '커밋이 없다'를 알 수 없다.
    # 모르는 것을 경고로 내면 전부 잡음이 된다 — 규칙이 돌 때만 태스크 단위 신호를 낸다.
    note = (
        None
        if in_use
        else (
            "커밋·PR 에 태스크 키(예: ECHO-12)가 나타나지 않는다. "
            "태스크 단위 대조는 생략했다 — 활동이 없는 것이 아니라 연결할 근거가 없는 것이다."
        )
    )
    return schedule.iso(
        {
            "repo": snapshot.get("repo"),
            "today": today,
            "linked_tasks": covered,
            "total_tasks": len(tasks),
            "key_convention_in_use": in_use,
            "mismatches": mismatches(tasks, linked, today) if in_use else [],
            "note": note,
            "team": team_activity(snapshot, today, days),
        }
    )
