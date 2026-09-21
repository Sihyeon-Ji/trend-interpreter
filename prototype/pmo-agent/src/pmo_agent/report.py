"""주간 리포트 — schedule.py 의 계산 결과를 마크다운으로 옮긴다.

여기에 계산은 없다. 숫자는 전부 schedule.py 가 내고, 이 파일은 배치와 문장만 담당한다.
Gemini 도 쓰지 않는다 — 리포트는 매주 같은 모양이어야 하고, 같은 보드에서 같은 글이 나와야 한다.

한계를 문서에 적어 둔다: 보드에 '언제 완료됐는지'가 없어서 '이번 주에 끝난 일'은 알 수 없다.
대신 승인 로그(logs/approvals.jsonl)로 '이번 주에 무엇을 반영했는지'를 보여준다.

실행:
  PMO_BACKEND=memory python agent/report.py            리포트 출력
  PMO_BACKEND=memory python agent/report.py --save     reports/ 에 저장
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

from pmo_agent import availability as avail_mod
from pmo_agent import capacity as cap
from pmo_agent import schedule, signals
from pmo_agent.env import logs_dir, reports_dir

OUT_DIR = str(reports_dir())
LOG = str(logs_dir() / "approvals.jsonl")
TOP_RISKS = 8


def _d(v) -> str:
    return v.isoformat() if isinstance(v, dt.date) else (v or "-")


def question_for(r: dict) -> str:
    """위험 한 건 → 담당자에게 물을 한 문장 (SYSTEM 규칙 4 를 코드로 고정)."""
    who = r.get("assignee") or "담당자"
    if r.get("delay_days"):
        base = (
            f"{who}님, {r['key']}({r['summary']})가 마감 {_d(r['duedate'])}보다 "
            f"{r['delay_days']}일 늦을 것으로 보입니다"
        )
    elif r.get("critical"):
        base = f"{who}님, {r['key']}({r['summary']})는 여유가 없는 임계경로 작업입니다"
    else:
        base = f"{who}님, {r['key']}({r['summary']})의 여유가 {r['slack_days']}일뿐입니다"
    if r.get("blocks"):
        base += f" — 끝나야 {', '.join(r['blocks'][:3])}가 시작됩니다"
    return base + ". 현재 진행 상황과 예상 완료일을 알려주실 수 있을까요?"


def workload(tasks: dict) -> list:
    """담당자별 남은 작업량. 누구에게 몰려 있는지 보는 용도."""
    by: dict[str, dict] = {}
    for t in tasks.values():
        if t.is_done:
            continue
        row = by.setdefault(
            t.assignee or "(미배정)",
            {"assignee": t.assignee or "(미배정)", "count": 0, "days": 0.0},
        )
        row["count"] += 1
        row["days"] += t.remaining
    for row in by.values():
        row["days"] = round(row["days"], 1)
    return sorted(by.values(), key=lambda r: -r["days"])


def due_soon(tasks: dict, today: dt.date, within: int = 5) -> list:
    """앞으로 N영업일 안에 마감인 미완료 태스크."""
    limit = schedule.add_workdays(today, within)
    out = [t for t in tasks.values() if not t.is_done and t.duedate and today <= t.duedate <= limit]
    return sorted(out, key=lambda t: (t.duedate, t.key))


def committed_finish(tasks: dict) -> dt.date | None:
    """팀이 약속한 완료일 = 태스크 마감일 중 가장 늦은 것.

    CPM 으로 '오늘 시작하면 언제 끝나나'를 계획값으로 쓰면 예측값과 거의 같아져 비교가 무의미해진다.
    리포트에서 의미 있는 비교는 '약속한 날 vs 지금 예측' 이다.
    """
    ds = [t.duedate for t in tasks.values() if t.duedate]
    return max(ds) if ds else None


def overdue(tasks: dict, today: dt.date) -> list:
    """마감일이 이미 지났는데 안 끝난 것."""
    out = [t for t in tasks.values() if not t.is_done and t.duedate and t.duedate < today]
    return sorted(out, key=lambda t: (t.duedate, t.key))


def recent_approvals(since: dt.date, path: str | None = None) -> list:
    """since 이후 실제로 반영된 변경. 승인 로그가 없으면 빈 목록."""
    p = path or LOG
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("ok") and (r.get("at") or "")[:10] >= since.isoformat():
                out.append(r)
    return out


def weekly(
    tasks: dict,
    today: dt.date | None = None,
    approvals_path: str | None = None,
    project: str = "ECHO",
    rebalance: bool = True,
    done_recent: list | None = None,
    code: dict | None = None,
    availability: dict | None = None,
) -> str:
    """주간 리포트 마크다운 한 덩어리."""
    today = today or dt.date.today()
    since = schedule.add_workdays(today, -5)
    c = schedule.cpm(tasks, today)
    f = schedule.forecast(tasks, today)
    rs = schedule.risks(tasks, today)
    done = sum(1 for t in tasks.values() if t.is_done)
    committed = committed_finish(tasks)
    slip = schedule.workdays_between(committed, f["project_finish"]) if committed else 0
    late = overdue(tasks, today)

    L = [f"# {project} 주간 리포트 — {today.isoformat()}", ""]

    L += [
        "## 한눈에",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 진행 | {done}/{len(tasks)}건 완료 ({round(done / max(len(tasks), 1) * 100)}%) |",
        f"| 약속한 완료일 | {_d(committed)} |",
        f"| 예측 완료일 | **{_d(f['project_finish'])}** ({'+' if slip > 0 else ''}{slip}영업일) |",
        f"| 임계경로 | {len(c['critical_path'])}건 |",
        f"| 지연 위험 | {len(rs)}건 |",
        f"| 마감 경과 | {len(late)}건 |",
        "",
    ]

    if slip > 0:
        L += [
            f"> 예측이 약속한 완료일보다 **{slip}영업일** 늦습니다. 아래 위험 항목이 원인입니다.",
            "",
        ]
    elif slip < 0:
        L += [f"> 예측이 약속한 완료일보다 {abs(slip)}영업일 빠릅니다.", ""]

    if done_recent is not None:
        L += ["## 이번 주에 끝난 일", ""]
        if done_recent:
            L += ["| 태스크 | 담당 |", "|---|---|"]
            L += [f"| {t.key} {t.summary} | {t.assignee or '-'} |" for t in done_recent]
        else:
            L.append("없습니다.")
        L.append("")

    L += ["## 지연 위험", ""]
    if not rs:
        L += ["없습니다.", ""]
    else:
        L += [
            "| 태스크 | 담당 | 마감 | 예상 완료 | 지연 | 여유 | 근거 |",
            "|---|---|---|---|---|---|---|",
        ]
        for r in rs[:TOP_RISKS]:
            L.append(
                f"| {r['key']} {r['summary']} | {r['assignee'] or '-'} | {_d(r['duedate'])} | "
                f"{_d(r['predicted_finish'])} | {r['delay_days'] or 0}일 | {r['slack_days']}일 | "
                f"{r['reasons'][0]} |"
            )
        if len(rs) > TOP_RISKS:
            L.append(f"| … | | | | | | 외 {len(rs) - TOP_RISKS}건 |")
        L.append("")

    L += [
        "## 임계경로",
        "",
        (" → ".join(f"`{k}`" for k in c["critical_path"]) if c["critical_path"] else "없음"),
        "",
        "이 경로가 밀리면 프로젝트 완료일이 그대로 밀립니다.",
        "",
    ]

    soon = due_soon(tasks, today)
    L += ["## 이번 주 마감 예정", ""]
    if soon:
        L += ["| 태스크 | 담당 | 마감 |", "|---|---|---|"]
        L += [f"| {t.key} {t.summary} | {t.assignee or '-'} | {_d(t.duedate)} |" for t in soon]
    else:
        L.append("없습니다.")
    L.append("")

    if late:
        L += ["## 마감 경과", "", "| 태스크 | 담당 | 마감 | 상태 |", "|---|---|---|---|"]
        L += [
            f"| {t.key} {t.summary} | {t.assignee or '-'} | {_d(t.duedate)} | {t.status} |"
            for t in late[:TOP_RISKS]
        ]
        if len(late) > TOP_RISKS:
            L.append(f"| … | | | 외 {len(late) - TOP_RISKS}건 |")
        L.append("")

    L += ["## 담당자별 남은 작업", "", "| 담당 | 건수 | 남은 영업일 |", "|---|---|---|"]
    L += [f"| {w['assignee']} | {w['count']} | {w['days']} |" for w in workload(tasks)]
    L.append("")

    # --- 사람 용량을 반영한 일정 ---
    lv = cap.levelled(tasks, today, availability=availability)
    lv_plain = cap.levelled(tasks, today) if availability else lv
    L += [
        "## 실현 가능한 일정",
        "",
        "| 기준 | 완료일 |",
        "|---|---|",
        f"| 의존관계만 반영 | {_d(lv['unconstrained_finish'])} |",
    ]
    if availability:
        # 각 제약이 며칠씩 더하는지 분리해서 보여준다 — 합쳐 놓으면 원인을 못 짚는다
        meeting_slip = schedule.workdays_between(lv_plain["project_finish"], lv["project_finish"])
        L += [
            f"| 사람 용량 반영 | {_d(lv_plain['project_finish'])} |",
            f"| **회의 시간까지 반영** | **{_d(lv['project_finish'])}** "
            f"(+{lv['slip_vs_unconstrained']}영업일, 이 중 회의가 {meeting_slip}일) |",
            "",
        ]
    else:
        L += [
            f"| **사람 용량까지 반영** | **{_d(lv['project_finish'])}** "
            f"(+{lv['slip_vs_unconstrained']}영업일) |",
            "",
            "> 캘린더가 연결되지 않아 전원이 하루를 온전히 쓴다고 가정했습니다. "
            "회의를 반영하면 더 늦어집니다.",
            "",
        ]
    if lv["bottleneck"]:
        b = lv["bottleneck"]
        L += [
            f"> 병목은 **{b['assignee']}** 입니다 — 남은 {b['busy_days']}영업일, 가동률 "
            f"{b['utilization']}. "
            f"이 사람이 비는 {_d(b['free_at'])}가 프로젝트의 하한선입니다.",
            "",
        ]
    if availability:
        L += [
            "| 담당 | 남은 영업일 | 회의로 잃는 시간 | 실가용 | 가동률 | 마지막 작업 종료 |",
            "|---|---|---|---|---|---|",
        ]
        for r in lv["resources"]:
            m = avail_mod.meeting_load(availability, r["assignee"], today, 10)
            L.append(
                f"| {r['assignee']} | {r['busy_days']} | {m['lost_hours']}시간 |"
                f" {m['available_days']}/10일 | {r['utilization']} | {_d(r['free_at'])} |"
            )
    else:
        L += [
            "| 담당 | 동시 처리 | 남은 영업일 | 가동률 | 마지막 작업 종료 |",
            "|---|---|---|---|---|",
        ]
        L += [
            f"| {r['assignee']} | {r['capacity']}건 | {r['busy_days']} | {r['utilization']} | "
            f"{_d(r['free_at'])} |"
            for r in lv["resources"]
        ]
    L.append("")
    waiting = cap.blocked_by_people(lv)
    if waiting:
        L += [
            "선행 작업은 끝났는데 **담당자가 바빠서** 기다리는 태스크입니다. 의존관계가 아니라 "
            "사람이 원인입니다.",
            "",
            "| 태스크 | 담당 | 대기 | 시작 예정 |",
            "|---|---|---|---|",
        ]
        L += [
            f"| {w['key']} {w['summary']} | {w['assignee']} | {w['waiting_days']}일 | "
            f"{_d(w['start'])} |"
            for w in waiting
        ]
        L.append("")

    if rebalance:
        rb = cap.rebalance(tasks, today, availability=availability)
        L += ["## 재배치 제안", ""]
        if rb["moves"]:
            L += [
                f"아래 {len(rb['moves'])}건을 옮기면 완료일이 **{_d(rb['before'])} → "
                f"{_d(rb['after'])}"
                f" ({rb['gain_days']}영업일 단축)** 됩니다.",
                "",
                "| 태스크 | 이동 | 단축 | 이동 후 완료일 |",
                "|---|---|---|---|",
            ]
            L += [
                f"| {m['key']} {m['summary']} | {m['from']} → {m['to']} | {m['gain_days']}일 | "
                f"{_d(m['new_finish'])} |"
                for m in rb["moves"]
            ]
            L += [
                "",
                "제안일 뿐이며 반영되지 않았습니다. 실제 이동은 담당자 합의가 필요합니다.",
                "",
            ]
        else:
            L += ["옮겨서 단축할 수 있는 태스크가 없습니다.", ""]

    if code:
        L += [
            "## 보드와 코드의 대조",
            "",
            f"저장소 `{code.get('repo', '?')}` 기준. 보드에 적힌 상태와 실제 커밋·PR 을 맞대 본 "
            f"결과입니다.",
            "",
        ]
        t = code.get("team") or {}
        L += [
            "| 항목 | 값 |",
            "|---|---|",
            f"| 최근 {t.get('window_days', 14)}일 커밋 | {t.get('commits', 0)}건 |",
            f"| 기여 집중도 | {t.get('concentration', 0)} (1.0 이면 한 사람) |",
            f"| 열린 PR | {t.get('open_prs', 0)}건 (리뷰 정체 {t.get('stale_prs', 0)}건) |",
            f"| 마지막 커밋 | {t.get('last_commit') or '-'} |",
            "",
        ]
        for n in t.get("notes") or []:
            L.append(f"> {n}")
        if t.get("notes"):
            L.append("")
        if code.get("note"):
            L += [f"> {code['note']}", ""]
        ms = code.get("mismatches") or []
        if ms:
            L += [
                "보드와 코드가 어긋난 태스크입니다. 한쪽만 봐서는 보이지 않습니다.",
                "",
                "| 태스크 | 담당 | 종류 | 내용 |",
                "|---|---|---|---|",
            ]
            L += [
                f"| {m['key']} {m['summary']} | {m['assignee'] or '-'} | `{m['kind']}` | "
                f"{m['detail']} |"
                for m in ms[:TOP_RISKS]
            ]
            if len(ms) > TOP_RISKS:
                L.append(f"| … | | | 외 {len(ms) - TOP_RISKS}건 |")
            L.append("")
        elif code.get("key_convention_in_use"):
            L += ["어긋난 태스크가 없습니다.", ""]

    L += ["## 확인 필요", ""]
    if rs:
        L += [f"{i}. {question_for(r)}" for i, r in enumerate(rs[:5], 1)]
    else:
        L.append("없습니다.")
    L.append("")

    ap = recent_approvals(since, approvals_path)
    L += [f"## 최근 반영 내역 ({_d(since)} 이후)", ""]
    if ap:
        L += ["| 시각 | 변경 | 대상 |", "|---|---|---|"]
        L += [
            f"| {r['at']} | {r['tool'].replace('propose_', '')} | "
            f"{r['args'].get('key', '-')} "
            f"{json.dumps({k: v for k, v in r['args'].items() if k != 'key'}, ensure_ascii=False)} "
            f"|"
            for r in ap
        ]
    else:
        L.append("없습니다.")
    L += [
        "",
        "---",
        "",
        "숫자는 전부 `schedule.py`(CPM·영업일)와 `capacity.py`(자원 제약)가 계산했습니다. 주말은 "
        "제외됩니다.",
        "보드-코드 대조는 커밋·PR 에 태스크 키(ECHO-12)가 적혀 있을 때만 태스크 단위로 동작합니다.",
        "용량 반영 일정은 담당자 1인당 동시 1건을 가정합니다. 실제 팀 운영 방식이 다르면 capacity "
        "인자로 조정합니다.",
        "'이번 주에 끝난 일'은 보드의 상태 변경 이력에서 가져옵니다 — 에이전트를 거치지 않은 "
        "변경도 포함됩니다.",
        "",
    ]
    return "\n".join(L)


def save(text: str, today: dt.date | None = None, out_dir: str | None = None) -> str:
    today = today or dt.date.today()
    d = out_dir or OUT_DIR
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"weekly-{today.isoformat()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


if __name__ == "__main__":
    from pmo_agent.tools import _availability, _fetch, jira

    today = dt.date.today()
    board = jira()
    done_recent = None
    try:
        done_recent = list(schedule.from_jira_issues(board.done_since(7)).values())
    except Exception as e:  # 이력 조회를 지원하지 않는 백엔드면 섹션을 생략한다
        print(f"(완료 이력 조회 생략: {str(e)[:80]})", file=sys.stderr)
    code = None
    try:
        from pmo_agent.tools import repo

        code = signals.summary(_fetch(), repo().snapshot(100), today)
    except Exception as e:  # 저장소가 없거나 인증이 없으면 이 섹션만 생략한다
        print(f"(코드 신호 생략: {str(e)[:80]})", file=sys.stderr)
    text = weekly(
        _fetch(),
        today,
        project=getattr(board, "project", "ECHO"),
        done_recent=done_recent,
        code=code,
        availability=_availability(),
    )
    print(text)
    if "--save" in sys.argv:
        print(f"\n저장: {save(text, today)}")
