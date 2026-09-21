"""Korean renderings of what the agent worked out.

The product is English: the board, the commits, the notes, the answers. That is deliberate,
and it stays. This is for reading over the agent's shoulder — checking a run in the language
you think in is a different job from shipping it.

**Nothing here translates.** It re-renders. `cause.py` and `signals.py` each carry the
numbers their sentence was built from (`facts`), so the Korean is written from the same
numbers rather than from the English words. Translating the prose would mean parsing English
back out of a string somebody may have already changed, and the first time a sentence was
reworded the Korean would quietly say something else.

That is also why the calculation modules have no Korean in them. They compute; how a person
wants to read it is not their problem, and one of them speaking two languages would make
every future sentence twice the work.

A fact this does not know how to say comes back in English. A half-translated sentence with
a blank in it is worse than an English one.
"""

from __future__ import annotations

KO = "ko"
LANGS = ("en", KO)


def lang_of(value: str) -> str:
    """Normalise whatever arrived in the query string. Anything unknown means English."""
    found = (value or "").strip().lower().replace("_", "-").split("-")[0]
    return KO if found in ("ko", "kr", "kor") else "en"


def _n(value) -> str:
    """A number as a person would type it: 4, not 4.0."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(f)) if f == int(f) else f"{f:g}"


# --------------------------------------------------------------------------- causes
def cause_detail(row: dict) -> str:
    """One cause, in Korean, from the numbers rather than from the English."""
    f, kind = row.get("facts") or {}, row.get("kind")
    if kind == "dependency_open":
        return f"선행 작업 {_n(f.get('open'))}건이 아직 끝나지 않았습니다"
    if kind == "waiting_on_review":
        return f"PR #{f.get('number')}이 움직임 없이 열려 있습니다"
    if kind == "owner_in_meetings":
        said = f"{f.get('who')} 님이 이 기간에 회의로 {_n(f.get('hours'))}시간을 썼습니다"
        if f.get("top_title"):
            # The title is whatever the calendar says, so no Korean particle can be chosen
            # for it. Putting it after "로" sidesteps a 이/가 that would be wrong half the time.
            said += f". 가장 많은 건 “{f['top_title']}” 로 {_n(f.get('top_hours'))}시간입니다"
        return said
    if kind == "owner_worked_elsewhere":
        return (
            f"{f.get('who')} 님이 이 기간에 커밋 {_n(f.get('commits'))}건을 했지만, "
            f"이 작업에는 하나도 없습니다"
        )
    if kind == "decision_recorded":
        return row.get("detail", "")  # the note's own words; translating them would be a lie
    return row.get("detail", "")


def cause_note(row: dict) -> str:
    """The verdict: how much of the silence is accounted for, and what the rest is."""
    span = (row.get("window") or {}).get("days") or 0
    causes = row.get("causes") or []
    explained = row.get("explained_days") or 0

    if not span:
        if any(c.get("kind") == "decision_recorded" for c in causes):
            return "아직 기한이 지나지 않아 설명할 공백이 없습니다. 다만 이런 기록이 있습니다."
        return "설명할 공백이 없습니다. 오늘까지 활동이 이어지고 있습니다."
    if not causes:
        return (
            f"{_n(span)}영업일 동안 아무 활동이 없었고, 보드·저장소·달력 어디에도 "
            f"이유가 없습니다. 결론이 아니라 담당자에게 물어볼 질문입니다."
        )

    left = round(span - explained, 1)
    said = (
        f"멈춰 있던 {_n(span)}영업일 중 {_n(explained)}일은 이유가 설명됩니다. "
        f"나머지 {_n(left)}일은 설명되지 않습니다."
        if left > 0
        else f"멈춰 있던 {_n(span)}영업일이 모두 설명됩니다."
    )
    return f"{said} {_blind(row.get('trace'))}".strip()


WHERE = {"the repository": "저장소", "the calendar": "달력"}


def _blind(dark: dict | None) -> str:
    """Which kind of leftover this is — someone who did not come, or someone unobserved."""
    if not dark or not dark.get("workdays"):
        return ""
    if not dark.get("no_trace"):
        return (
            "그 기간 내내 다른 곳에서 일한 흔적이 있습니다. 그러니 나머지는 데이터의 "
            "공백이 아니라 담당자에게 물어볼 질문입니다."
        )
    where = "와 ".join(WHERE.get(x, x) for x in dark.get("looked_in") or [])
    return (
        f"그 {_n(dark['workdays'])}일 중 {_n(dark['with_trace'])}일은 {where}에 흔적이 있습니다. "
        f"나머지 {_n(dark['no_trace'])}일은 어디에도 없습니다 — 이유가 아니라 사각지대입니다."
    )


# --------------------------------------------------------------------------- signals
def signal_detail(row: dict) -> str:
    f, kind = row.get("facts") or {}, row.get("kind")
    if kind == "done_with_open_pr":
        return f"완료 처리됐지만 PR #{f.get('number')}이 아직 열려 있습니다"
    if kind == "no_code_activity":
        return "진행 중이지만 연결된 커밋이 하나도 없습니다"
    if kind == "stalled":
        return f"진행 중이지만 마지막 커밋이 {_n(f.get('idle_days'))}일 전입니다 ({f.get('last')})"
    if kind == "undeclared_progress":
        return (
            f"보드에는 '{f.get('status')}' 로 되어 있지만 커밋이 {_n(f.get('commits'))}건 있습니다 "
            f"(마지막 {f.get('last')})"
        )
    if kind == "review_waiting":
        who = ", ".join(f.get("reviewers") or [])
        return (
            f"PR #{f.get('number')}이 리뷰를 {_n(f.get('waited'))}일째 기다리고 있습니다 "
            f"({'리뷰어: ' + who if who else '리뷰어 미지정'})"
        )
    return row.get("detail", "")


KIND_LABEL = {
    "done_with_open_pr": "완료인데 PR 열림",
    "stalled": "멈춤",
    "review_waiting": "리뷰 대기",
    "no_code_activity": "커밋 없음",
    "undeclared_progress": "상태 미갱신",
}


# --------------------------------------------------------------------------- the rest
def risk_reason(text: str) -> str:
    """The few reasons a risk carries. Anything unrecognised stays as it is."""
    if text.startswith("forecast finish"):
        return text  # dates and numbers; the columns beside it already say this
    if text.startswith("past its due date of "):
        return f"기한({text.rsplit(' ', 1)[-1]})이 지났습니다"
    if "critical path" in text:
        return "임계 경로에 있습니다 (여유 0일)"
    if text.startswith("blocked by"):
        return text.replace("blocked by", "막혀 있다:")
    return text


SOURCES = {
    "status, dependencies, due dates": "상태 · 선행 관계 · 기한",
    "commits, pull requests, changed paths": "커밋 · 풀 리퀘스트 · 변경된 경로",
    "meeting hours per person": "사람별 회의 시간",
    "what was decided, in words": "무엇이 결정됐는지 — 문장으로",
}

AGENT = {
    "joins": "티켓 키 없는 커밋을 작업에 연결합니다 — 작성자·시각·어휘·경로",
    "computes": "모든 날짜와 일수를 직접 계산합니다 — schedule.py, capacity.py",
    "asks": "모델은 글과 그림을 읽기만 합니다. 숫자는 만들지 않습니다",
    "waits": "사람이 선택하기 전에는 보드에 아무것도 반영되지 않습니다",
}


# --------------------------------------------------------------------- roll-up
KIND_OF_WORK = {"build": "개발", "run": "운영"}
HEADLINE = {
    "achievable finish": "달성 가능 종료",
    "open now": "미해결",
    "could not read": "읽지 못함",
}
STATE = {"risk": "위험", "watch": "주의", "ok": "양호", "unknown": "모름"}


def rollup_note(payload: dict) -> str:
    """The one sentence over the roll-up. Built from the counts, not translated."""
    rows = payload.get("projects") or []
    if not rows:
        return "설정된 프로젝트가 없습니다."
    counts = payload.get("counts") or {}
    if counts.get("risk"):
        worst: dict = next((r for r in rows if r.get("state") == "risk"), {})
        why = worst.get("why") or "설명이 없습니다"
        return (
            f"{len(rows)}개 중 {counts['risk']}개가 손을 써야 합니다. "
            f"가장 나쁜 건 {worst.get('name', '')} — {why}"
        )
    if counts.get("watch"):
        return f"문제 있는 건 없습니다. {len(rows)}개 중 {counts['watch']}개는 지켜볼 만합니다."
    if counts.get("unknown") == len(rows):
        return "어느 프로젝트도 읽지 못했습니다."
    return f"{len(rows)}개 모두 계획대로입니다."


def health_note(payload: dict) -> str:
    """Is the queue keeping up, and is anything repeating. From the numbers, as always."""
    now, was = payload.get("open", 0), payload.get("open_was", 0)
    arrived, closed = payload.get("arrived", 0), payload.get("closed", 0)
    days = payload.get("window_days", 14)
    if not now and not arrived:
        return "미해결도 없고 새로 들어온 것도 없습니다. 보고할 큐가 없습니다."
    if closed >= arrived:
        said = (
            f"{days}일 동안 {arrived}건 들어오고 {closed}건 처리했습니다 — 큐가 따라가고 "
            f"있고, 미해결은 {now}건"
        )
        said += f"으로 {was}건에서 줄었습니다." if now < was else "입니다."
    else:
        said = (
            f"{days}일 동안 {arrived}건 들어오고 {closed}건 처리해서, 미해결이 "
            f"{was}건에서 {now}건으로 늘었습니다."
        )
    worst = next((r for r in payload.get("recurring") or [] if r.get("open")), None)
    if worst:
        said += (
            f" “{worst['fault']}” 이(가) {worst['times']}번 접수됐고 그중 {worst['open']}건이 "
            f"아직 열려 있습니다 — {worst['times']}개가 아니라 한 문제입니다."
        )
    return said


# ----------------------------------------------------------------------- the queue
def queue_title(item: dict) -> str:
    """What the row is, in Korean. Built from `facts`, never parsed back out of English."""
    f, kind = item.get("facts") or {}, item.get("kind")
    if kind == "decide":
        return f"{item.get('key', '')} → {f.get('to', '')} 님에게 넘기기"
    if kind == "tell":
        # No particle after the key: 이/가 depends on its last digit, and the key varies.
        return f"{f.get('who', '')} 님에게 알리기 — {item.get('key', '')} 때문에 막혀 있습니다"
    if kind == "apply":
        moves = []
        if f.get("duedate"):
            moves.append(f"기한 {f.get('duedate_was') or '—'} → {f['duedate']}")
        if f.get("status"):
            moves.append(f"상태 {f.get('status_was') or '—'} → {f['status']}")
        return f"{f.get('key', '')}: {' · '.join(moves) or '코멘트'}"
    return item.get("title", "")


def queue_why(item: dict) -> str:
    """Why it is on the list today."""
    f, kind = item.get("facts") or {}, item.get("kind")
    if kind == "decide":
        left = f.get("left", 0)
        when = "오늘이 지나면" if not left else f"영업일 {_n(left)}일 뒤에는"
        return (
            f"{f.get('owner', '')} 님의 일을 덜어냅니다. "
            f"영업일 {_n(f.get('buys'))}일을 벌 수 있고, {when} 의미가 없어집니다"
            f" — {f.get('expires', '')}까지"
        )
    if kind == "tell":
        teams = ", ".join(f.get("teams") or [])
        return f"{teams} 팀으로 넘어가는 건이라, 데일리 스탠드업에서는 나오지 않습니다"
    if kind == "apply":
        where = f.get("where") or ""
        return f"“{where}” 에서 읽었습니다" if where else "회의록에서 읽었습니다"
    if kind == "check":
        return "에이전트가 스스로 정하지 못했습니다"
    return item.get("why", "")


QUEUE_SOURCE = {
    "schedule + capacity": "일정 · 용량 계산",
    "board dependencies": "보드의 선행 관계",
    "meeting notes": "회의록",
    "the agent": "에이전트",
}


BLIND_SAYS = {
    "decisions": "닫히려는 선택지가 있는지",
    "blocked": "팀을 넘어 막혀 있는 사람이 있는지",
    "notes": "회의록과 보드가 어긋났는지",
}


def queue_note(payload: dict) -> str:
    """The one-line headline. An empty queue names what was looked at, or it is not believable."""
    f = payload.get("note_facts") or {}
    total = f.get("total") or 0
    missed = [BLIND_SAYS.get(b, b) for b in f.get("blind") or []]
    if not total:
        if missed:
            # 못 봤다와 없다는 다른 말입니다. 안심시키는 문장은 본 것에만 씁니다.
            return (
                "아무것도 오지 않았지만 없다는 뜻은 아닙니다 — "
                + ", ".join(missed)
                + " 확인하지 못했습니다."
            )
        return (
            "오늘은 확인할 게 없습니다. 닫히는 결정도, 팀을 넘어 막혀 있는 사람도, "
            "회의록과 어긋난 보드도 없습니다."
        )
    said = f"{_n(total)}건이 확인을 기다립니다"
    if f.get("key") and f.get("left") is not None:
        said += (
            f". 가장 급한 건 {f['key']} — 이 선택지가 사라지기까지 "
            f"영업일 {_n(f['left'])}일 남았습니다"
        )
    said += "."
    if missed:
        said += " 더 있을 수 있습니다 — " + ", ".join(missed) + " 확인하지 못했습니다."
    return said


def apply(payload: dict, what: str, lang: str) -> dict:
    """Re-render one endpoint's prose in `lang`. English is returned untouched.

    The structure never changes, only the sentences — so a caller that reads the numbers
    gets the same thing either way, and only the text a person reads moves.
    """
    if lang_of(lang) != KO:
        return payload

    if what == "cause":
        for row in payload.get("worst") or []:
            for c in row.get("causes") or []:
                c["detail"] = cause_detail(c)
            row["note"] = cause_note(row)
        if payload.get("notes_note"):
            payload["notes_note"] = "이 기간에 읽을 수 있는 회의록이 없습니다"
    elif what == "signals":
        for row in payload.get("mismatches") or []:
            row["detail"] = signal_detail(row)
            row["label"] = KIND_LABEL.get(row.get("kind", ""), row.get("kind", ""))
        if payload.get("note"):
            payload["note"] = _link_note(payload)
    elif what == "schedule":
        for row in payload.get("risks") or []:
            row["reasons"] = [risk_reason(x) for x in row.get("reasons") or []]
    elif what == "rollup":
        for row in payload.get("projects") or []:
            facts = row.get("why_facts")
            if facts:
                # Written again from the numbers, never translated from the English.
                row["why"] = cause_note(facts) if row.get("kind") != "run" else health_note(facts)
            row["kind_label"] = KIND_OF_WORK.get(row.get("kind", ""), row.get("kind", ""))
            row["state_label"] = STATE.get(row.get("state", ""), row.get("state", ""))
            row["headline_label"] = HEADLINE.get(
                row.get("headline_label", ""), row.get("headline_label", "")
            )
        payload["note"] = rollup_note(payload)
    elif what == "queue":
        for row in payload.get("items") or []:
            row["title"] = queue_title(row)
            row["why"] = queue_why(row)
            row["source"] = QUEUE_SOURCE.get(row.get("source", ""), row.get("source", ""))
            # `draft` stays as it is: it is a message for an English board, and a Korean
            # sentence pasted into that thread would be the wrong kind of help.
        payload["note"] = queue_note(payload)
    elif what == "health":
        payload["note"] = health_note(payload)
    elif what == "sources":
        for row in payload.get("sources") or []:
            row["supplies"] = SOURCES.get(row.get("supplies", ""), row.get("supplies", ""))
        payload["agent"] = {k: AGENT.get(k, v) for k, v in (payload.get("agent") or {}).items()}
    return payload


def _link_note(payload: dict) -> str:
    """How many links were inferred, said in Korean. Falls back when the shape is unfamiliar."""
    q = payload.get("link_quality") or {}
    inferred, total = q.get("inferred"), q.get("total")
    if inferred is None or total is None:
        return payload.get("note", "")
    return (
        f"연결 {_n(total)}건 중 {_n(inferred)}건은 커밋에 태스크 키가 없어 작성자, 시각, "
        f"어휘, 경로로 추론했습니다 (평균 확신도 {q.get('mean_confidence', '?')}). "
        f"확신도가 낮은 건은 확인이 필요합니다."
    )
