"""The day's queue — no network.

This is the front door, so what it must not do matters more than what it shows. The
research it was built from says knowledge workers lose 352 hours a year to *talking
about* work, not to a shortage of information, which means a panel that invents things
to look at makes the problem it claims to solve worse.

So the tests are about restraint.

**An empty queue says it is empty.** Manufacturing three items on a quiet day is how a
tool becomes another thing to check.

**Nothing is done, only prepared.** Every item carries `done: False` and the payload
says so out loud, because the difference between drafting a message and sending one is
the whole basis on which a person lets this near their board.

**Every item names its source.** 40% of desk workers have been handed AI output that
looked finished and was not. An item nobody can check is one they have to take on trust.

**The perishable goes first.** A closing option is the only kind that gets worse by
being left, so it outranks a message that will read the same tomorrow.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt

from pmo_agent import queue

TODAY = dt.date(2026, 9, 21)


def closing(*rows):
    return {"decisions": list(rows)}


def decision(
    key="ECHO-25", left=2, buys=3, expires="2026-09-23", owner="Leo Fischer", to="Aiko Tanaka"
):
    return {
        "key": key,
        "decision": f"move {key} to {to}",
        "summary": "Logging",
        "owner": owner,
        "to": to,
        "buys_days": buys,
        "days_left": left,
        "expires": expires,
    }


def alert(key="ECHO-25", crossing=("Quality",), tell=("Sofia Marchetti",)):
    return {
        "key": key,
        "summary": "Logging",
        "crosses_teams": list(crossing),
        "tell": [{"who": w} for w in tell],
        "draft": "ECHO-25 is holding up work of yours.",
    }


def change(key="ECHO-31", **kw):
    row = {
        "key": key,
        "summary": "Data migration",
        "evidence": "from the 2026-09-17 note",
        "quote": "we agreed to push this to the 30th",
    }
    row.update(kw)
    return row


# --------------------------------------------------------------- the quiet day


def test_empty_queue_says_so_rather_than_filling_itself():
    g = queue.build(today=TODAY)
    assert g["items"] == []
    assert g["more"] == 0
    assert "Nothing needs you today" in g["note"]


def test_empty_note_says_why_it_is_empty_not_just_that_it_is():
    # "Nothing to do" is only believable if it names what was looked at.
    note = queue.build(today=TODAY)["note"]
    for checked in ("decision", "blocked", "notes agree with the board"):
        assert checked in note


# ------------------------------------------------------- prepared, never done


def test_nothing_is_marked_done():
    g = queue.build(
        closing(decision()),
        [alert()],
        {"changes": [change(duedate="2026-09-30")]},
        ["who owns this?"],
        TODAY,
    )
    assert g["nothing_was_done"] is True
    assert [i["done"] for i in g["items"]] == [False] * len(g["items"])


def test_every_item_names_where_it_came_from():
    g = queue.build(
        closing(decision()),
        [alert()],
        {"changes": [change(status="In Progress")]},
        ["who owns this?"],
        TODAY,
    )
    assert g["items"]
    assert all(i.get("source") for i in g["items"])


def test_a_message_is_drafted_not_sent():
    (item,) = queue.from_alerts([alert()])
    assert item["kind"] == queue.TELL
    assert item["draft"]  # the wording is prepared
    assert item["done"] is False  # and it has gone nowhere


# ------------------------------------------------------------------- ordering


def test_the_closing_option_outranks_everything_else():
    g = queue.build(
        closing(decision()),
        [alert()],
        {"changes": [change(duedate="2026-09-30")]},
        ["a question"],
        TODAY,
    )
    assert [i["kind"] for i in g["items"]] == [
        queue.DECIDE,
        queue.TELL,
        queue.APPLY,
        queue.CHECK,
    ]


def test_among_decisions_the_soonest_to_close_is_first():
    g = queue.build(
        closing(
            decision("ECHO-33", left=6, to="Rui Alves"),
            decision("ECHO-25", left=0, to="Aiko Tanaka"),
        ),
        today=TODAY,
    )
    assert [i["key"] for i in g["items"]] == ["ECHO-25", "ECHO-33"]


def test_a_decision_closing_this_week_is_marked_urgent_and_a_later_one_is_not():
    early, late = queue.from_decisions(
        closing(
            decision("ECHO-25", left=queue.SOON_DAYS), decision("ECHO-33", left=queue.SOON_DAYS + 1)
        ),
        TODAY,
    )
    assert early["urgent"] is True
    assert late["urgent"] is False


def test_the_note_names_the_one_that_cannot_wait():
    note = queue.build(
        closing(
            decision("ECHO-25", left=0, to="Aiko Tanaka"),
            decision("ECHO-33", left=9, to="Rui Alves"),
        ),
        today=TODAY,
    )["note"]
    assert "2 things are waiting on you" in note
    assert "ECHO-25" in note
    assert "ECHO-33" not in note  # naming both is naming neither


def test_no_urgent_item_means_no_urgency_claimed():
    note = queue.build(closing(decision(left=30)), today=TODAY)["note"]
    assert "cannot wait" not in note


# -------------------------------------------------------------------- folding


def test_one_person_asked_about_five_tasks_is_one_row():
    # Five rows saying "move something to Aiko" are not five decisions. They are one
    # decision asked five times -- and it is Aiko's capacity that pays for all five, so
    # it is the recipient that makes it one question, not the desks it comes off.
    g = queue.build(closing(*[decision(f"ECHO-{n}", left=n) for n in range(5)]), today=TODAY)
    assert len(g["items"]) == 1
    assert g["counts"][queue.DECIDE] == 1


def test_the_folded_tasks_are_still_listed_not_thrown_away():
    g = queue.build(closing(*[decision(f"ECHO-{n}", left=n) for n in range(5)]), today=TODAY)
    (row,) = g["items"]
    assert [x["key"] for x in row["also"]] == ["ECHO-1", "ECHO-2", "ECHO-3", "ECHO-4"]


def test_the_soonest_to_close_leads_the_group():
    # It is what makes the group worth looking at today rather than on Friday.
    g = queue.build(closing(decision("ECHO-33", left=6), decision("ECHO-25", left=0)), today=TODAY)
    (row,) = g["items"]
    assert row["key"] == "ECHO-25"
    assert row["urgent"] is True


def test_two_recipients_are_two_decisions():
    g = queue.build(closing(decision("ECHO-25"), decision("ECHO-33", to="Rui Alves")), today=TODAY)
    assert len(g["items"]) == 2


def test_work_coming_off_two_different_desks_onto_one_is_still_one_question():
    # It is the same person being asked to take five things either way.
    g = queue.build(
        closing(decision("ECHO-25", owner="Leo Fischer"), decision("ECHO-33", owner="Maya")),
        today=TODAY,
    )
    assert len(g["items"]) == 1


def test_the_same_people_told_twice_is_one_message():
    g = queue.build(alerts=[alert("ECHO-25"), alert("ECHO-22")], today=TODAY)
    (row,) = g["items"]
    assert row["key"] == "ECHO-25"
    assert [x["key"] for x in row["also"]] == ["ECHO-22"]


def test_a_different_audience_is_a_different_message():
    g = queue.build(
        alerts=[alert("ECHO-25"), alert("ECHO-22", tell=("Maya Okonkwo",))], today=TODAY
    )
    assert len(g["items"]) == 2


def test_a_board_change_is_never_folded():
    # Two tasks moving to the same date are two edits to the board, not one.
    g = queue.build(
        reconciled={
            "changes": [
                change("ECHO-31", duedate="2026-09-30"),
                change("ECHO-32", duedate="2026-09-30"),
            ]
        },
        today=TODAY,
    )
    assert len(g["items"]) == 2


# -------------------------------------------------------------------- filters


def test_a_block_that_stays_inside_one_team_is_not_queued():
    # They find out at standup. Queueing it spends the reader's attention on a message
    # that was going to happen anyway.
    assert queue.from_alerts([alert(crossing=())]) == []


def test_a_crossing_block_with_nobody_to_tell_is_not_queued():
    assert queue.from_alerts([alert(tell=())]) == []


def test_the_crossed_boundary_is_the_stated_reason():
    (item,) = queue.from_alerts([alert(crossing=("Quality",))])
    assert "Quality" in item["why"]
    assert "standup" in item["why"]


# --------------------------------------------------------------- board changes


def test_a_date_change_shows_what_it_was_as_well_as_what_it_becomes():
    (item,) = queue.from_reconcile(
        {"changes": [change(duedate="2026-09-30", duedate_was="2026-09-24")]}
    )
    assert "2026-09-24" in item["title"]
    assert "2026-09-30" in item["title"]


def test_a_missing_previous_value_is_shown_as_absent_not_invented():
    (item,) = queue.from_reconcile({"changes": [change(duedate="2026-09-30")]})
    assert "— → 2026-09-30" in item["title"]


def test_a_change_carries_the_sentence_it_was_read_from():
    (item,) = queue.from_reconcile({"changes": [change(status="Done")]})
    assert item["quote"] == "we agreed to push this to the 30th"
    assert item["source"] == "meeting notes"


def test_every_item_carries_the_numbers_its_sentence_was_built_from():
    # Korean is written from these, never translated out of the English above. A
    # sentence somebody rewords must not quietly change what the other language says.
    g = queue.build(
        closing(decision()),
        [alert()],
        {"changes": [change(duedate="2026-09-30")]},
        ["who owns this?"],
        TODAY,
    )
    assert all(i.get("facts") for i in g["items"])


def test_the_headline_is_available_as_numbers_too():
    f = queue.build(closing(decision("ECHO-25", left=0)), today=TODAY)["note_facts"]
    assert f == {"total": 1, "key": "ECHO-25", "left": 0, "blind": []}


# -------------------------------------------------------------------- honesty


def test_a_question_the_agent_could_not_settle_is_queued_as_work():
    (item,) = queue.from_questions(["is ECHO-31 the one they meant?"])
    assert item["kind"] == queue.CHECK
    assert "could not settle" in item["why"]


def test_the_overflow_is_counted_not_dropped_silently():
    g = queue.build(
        closing(*[decision(f"ECHO-{n}", left=n, to=f"P{n}") for n in range(10)]),
        limit=3,
        today=TODAY,
    )
    assert len(g["items"]) == 3
    assert g["more"] == 7
    assert g["counts"][queue.DECIDE] == 10  # the count is of everything, not of the page


def test_counts_cover_every_kind_even_at_zero():
    g = queue.build(closing(decision()), today=TODAY)
    assert set(g["counts"]) == set(queue.ORDER)
    assert g["counts"][queue.TELL] == 0


# ------------------------------------------------------------------ blind spots


def test_an_empty_queue_that_checked_nothing_does_not_say_nothing_is_wrong():
    # All three sources sit behind an exception handler, so one 429 empties the queue.
    # The reassuring sentence would then be three claims about three things nobody
    # looked at — the same mistake cause.py already refuses to make about silent days.
    note = queue.build(today=TODAY, blind=[{"check": "decisions"}])["note"]
    assert "Nothing needs you today" not in note
    assert "could not be checked" in note
    assert "whether any option is about to close" in note


def test_a_truly_empty_queue_still_says_nothing_is_wrong():
    assert "Nothing needs you today" in queue.build(today=TODAY)["note"]


def test_a_queue_with_items_still_admits_what_it_could_not_check():
    note = queue.build(closing(decision()), today=TODAY, blind=[{"check": "notes"}])["note"]
    assert "1 things are waiting on you" in note
    assert "There may be more" in note
    assert "whether the notes agree with the board" in note


def test_what_failed_is_carried_so_a_caller_can_see_it():
    g = queue.build(today=TODAY, blind=[{"check": "notes", "error": "429 quota"}])
    assert g["blind"] == [{"check": "notes", "error": "429 quota"}]
    assert g["note_facts"]["blind"] == ["notes"]


def test_every_check_has_something_to_say_for_itself():
    # An unnamed failure in the sentence would read as a typo, not as a gap.
    assert set(queue.BLIND_SAYS) == set(queue.CHECKS)


def test_the_folding_scaffolding_does_not_reach_the_payload():
    g = queue.build(closing(decision(), decision("ECHO-33")), [alert()], today=TODAY)
    assert all("group_on" not in i for i in g["items"])
