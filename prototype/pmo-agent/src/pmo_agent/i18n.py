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
