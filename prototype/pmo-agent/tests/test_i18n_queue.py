"""The Korean front door — no network.

Choosing 한국어 and getting English back is worse than no toggle at all: the reader
trusts the switch, so anything still in English reads as something the agent decided not
to say. That is what these guard.

**Written from the numbers, not from the English.** Every item carries `facts`, and the
Korean is built from those. Translating the prose would mean parsing English back out of
a string somebody may already have reworded — and the first time that happened, the
Korean would quietly say something else.

**Particles are never guessed.** `ECHO-25가` is right and `ECHO-22가` is wrong, and which
one it is depends on the last digit of a key that varies. So the sentences are shaped not
to need one, and a test says so.

**Two things stay English on purpose.** The draft is outgoing text for an English board,
and a question is the model's own wording about an English note.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt

from pmo_agent import i18n, queue

TODAY = dt.date(2026, 9, 21)

# The particles a naive translation would reach for. After a task key or a person's name
# the right one depends on the last sound, which nothing here can know.
GUESSED = ("가 ", "이 ", "를 ", "을 ", "은 ", "는 ", "와 ", "과 ")


def decision(key="ECHO-25", left=2, buys=3, owner="Leo Fischer", to="Aiko Tanaka"):
    return {
        "key": key,
        "decision": f"move {key} to {to}",
        "summary": "Logging",
        "owner": owner,
        "to": to,
        "buys_days": buys,
        "days_left": left,
        "expires": "2026-09-23",
    }


def alert(key="ECHO-25"):
    return {
        "key": key,
        "summary": "Logging",
        "crosses_teams": ["Quality"],
        "tell": [{"who": "Sofia Marchetti"}, {"who": "Hannah Reid"}],
        "draft": "ECHO-25 is holding up work of yours.",
    }


def change(key="ECHO-31", **kw):
    row = {"key": key, "summary": "Data migration", "evidence": "2026-09-17 standup", "quote": "q"}
    row.update(kw)
    return row


def ko(**kw):
    return i18n.apply(queue.build(today=TODAY, **kw), "queue", "ko")


def has_hangul(text):
    return any("가" <= ch <= "힣" for ch in text)


# ------------------------------------------------------------------ it is Korean


def test_every_line_a_person_reads_is_korean():
    g = ko(
        closing={"decisions": [decision()]},
        alerts=[alert()],
        reconciled={"changes": [change(duedate="2026-09-30")]},
        questions=["who owns this?"],
    )
    assert has_hangul(g["note"])
    for row in g["items"]:
        assert has_hangul(row["why"]), row["why"]
        assert has_hangul(row["source"]), row["source"]


def test_the_titles_are_korean_too():
    g = ko(
        closing={"decisions": [decision()]},
        alerts=[alert()],
        reconciled={"changes": [change(status="Done")]},
    )
    assert all(has_hangul(r["title"]) for r in g["items"])


def test_an_empty_queue_says_in_korean_what_it_looked_at():
    # "할 일 없음" alone is not believable. Naming the three checks is what makes it so.
    note = ko()["note"]
    assert has_hangul(note)
    for checked in ("결정", "막혀", "보드"):
        assert checked in note


# ------------------------------------------------------ built from numbers


def test_the_headline_count_comes_from_the_facts_not_the_english():
    g = ko(closing={"decisions": [decision("ECHO-25", left=0), decision("ECHO-33", to="Rui")]})
    assert g["note_facts"]["total"] == 2
    assert "2건이 확인을 기다립니다" in g["note"]


def test_the_urgent_one_is_named_with_its_days():
    g = ko(closing={"decisions": [decision("ECHO-25", left=0)]})
    assert "ECHO-25" in g["note"]
    assert "영업일 0일" in g["note"]


def test_a_decision_that_closes_today_does_not_say_in_zero_days():
    # "0일 뒤에는" is arithmetic showing through. Today is a word, not a number.
    (row,) = ko(closing={"decisions": [decision(left=0)]})["items"]
    assert "오늘이 지나면" in row["why"]
    assert "0일 뒤" not in row["why"]


def test_a_later_decision_counts_the_days():
    (row,) = ko(closing={"decisions": [decision(left=3)]})["items"]
    assert "영업일 3일 뒤에는" in row["why"]


def test_a_board_change_shows_both_dates_and_marks_a_missing_one():
    (row,) = ko(reconciled={"changes": [change(duedate="2026-09-30")]})["items"]
    assert "기한 — → 2026-09-30" in row["title"]


def test_a_board_change_names_the_note_it_came_from():
    (row,) = ko(reconciled={"changes": [change(status="Done")]})["items"]
    assert "2026-09-17 standup" in row["why"]


# ------------------------------------------------------------------ particles


def test_no_particle_is_guessed_after_a_task_key():
    g = ko(
        closing={"decisions": [decision()]},
        alerts=[alert()],
        reconciled={"changes": [change(duedate="2026-09-30")]},
    )
    for row in g["items"]:
        for particle in GUESSED:
            assert f"{row['key']}{particle}" not in row["title"], row["title"]


def test_no_particle_is_guessed_after_a_person_name():
    (row,) = ko(closing={"decisions": [decision(to="Aiko Tanaka")]})["items"]
    for particle in GUESSED:
        assert f"Aiko Tanaka{particle}" not in row["title"]


def test_the_title_names_who_would_take_it_not_who_already_has_it():
    # The bug this replaces told you to hand the work to the person holding it.
    (row,) = ko(closing={"decisions": [decision(owner="Leo Fischer", to="Aiko Tanaka")]})["items"]
    assert "Aiko Tanaka 님에게 넘기기" in row["title"]
    assert "Leo Fischer" not in row["title"]
    assert "Leo Fischer 님의 일을 덜어냅니다" in row["why"]


# -------------------------------------------------------- deliberately English


def test_the_draft_stays_in_english_because_it_is_going_to_an_english_board():
    (row,) = ko(alerts=[alert()])["items"]
    assert row["draft"] == "ECHO-25 is holding up work of yours."


def test_a_question_keeps_the_models_own_wording():
    (row,) = ko(questions=["is ECHO-31 the one they meant?"])["items"]
    assert row["title"] == "is ECHO-31 the one they meant?"
    assert has_hangul(row["why"])  # but why it is here is still explained in Korean


# ---------------------------------------------------------------- untouched


def test_english_is_returned_exactly_as_it_was():
    built = queue.build(closing={"decisions": [decision()]}, today=TODAY)
    assert i18n.apply(dict(built), "queue", "en") == built


def test_the_numbers_are_the_same_in_both_languages():
    # Only the sentences move. A caller reading the figures gets one answer either way.
    built = queue.build(closing={"decisions": [decision()]}, today=TODAY)
    said = i18n.apply(queue.build(closing={"decisions": [decision()]}, today=TODAY), "queue", "ko")
    assert said["counts"] == built["counts"]
    assert said["note_facts"] == built["note_facts"]
    assert [r["days_left"] for r in said["items"]] == [r["days_left"] for r in built["items"]]


def test_an_unfamiliar_source_is_passed_through_rather_than_blanked():
    # A blank where a word should be is worse than an English word.
    row = {"kind": "decide", "source": "something new", "facts": {}, "key": "", "title": "x"}
    payload = {"items": [row], "note_facts": {"total": 1}}
    assert i18n.apply(payload, "queue", "ko")["items"][0]["source"] == "something new"


# ------------------------------------------------------------------ blind spots


def test_the_korean_empty_queue_does_not_reassure_about_what_it_could_not_check():
    g = i18n.apply(queue.build(today=TODAY, blind=[{"check": "notes"}]), "queue", "ko")
    assert "확인할 게 없습니다" not in g["note"]
    assert "확인하지 못했습니다" in g["note"]
    assert "회의록과 보드가 어긋났는지" in g["note"]


def test_the_korean_queue_with_items_admits_the_gap_too():
    g = i18n.apply(
        queue.build(closing={"decisions": [decision()]}, today=TODAY, blind=[{"check": "blocked"}]),
        "queue",
        "ko",
    )
    assert "1건이 확인을 기다립니다" in g["note"]
    assert "더 있을 수 있습니다" in g["note"]


def test_every_check_is_sayable_in_korean():
    # A missing name would put a bare English key in the middle of a Korean sentence.
    assert set(i18n.BLIND_SAYS) == set(queue.CHECKS)
