"""Root-cause reconstruction tests — no network.

Two things are being checked, and the second is the important one:

  1. when the evidence is there, is the right cause found and ranked first
  2. when it is not, does it say so instead of picking something

A cause is only worth printing if a person can act on it. "Probably meetings" with no
hours behind it is worse than "nothing here explains it", because the first ends the
conversation and the second starts one.

Run: pytest -q
"""

from __future__ import annotations

import datetime as dt

from pmo_agent import cause, schedule
from pmo_agent.seeds import world as world_mod

TODAY = dt.date(2026, 9, 21)


def tasks(rows=None):
    return schedule.to_tasks(
        rows
        or [
            {
                "key": "T-1",
                "summary": "Authentication",
                "assignee": "Ada",
                "points": 5,
                "duedate": "2026-09-07",
            },
            {
                "key": "T-2",
                "summary": "Search",
                "assignee": "Ada",
                "points": 3,
                "duedate": "2026-09-18",
            },
        ]
    )


def commit(sha, key_words, day, who="Ada"):
    return {
        "sha": sha,
        "date": day,
        "author": who,
        "login": who,
        "name": who,
        "email": f"{who}@t.test",
        "message": key_words,
        "branch": "feat/x",
        "files": [],
    }


def meeting(day, hours, title, who="Ada"):
    return {"attendee": who, "date": day, "start": "10:00", "hours": hours, "title": title}


def quiet_task(duedate="2026-10-30"):
    """A task that is not overdue, so the window is only about recent silence."""
    return schedule.to_tasks(
        [{"key": "T-1", "summary": "Authentication", "assignee": "Ada", "duedate": duedate}]
    )["T-1"]


class TestWindow:
    def test_a_quiet_task_starts_at_its_last_commit(self):
        span = cause.window(quiet_task(), [{"date": "2026-09-14"}, {"date": "2026-09-09"}], TODAY)
        assert span["since"] == "2026-09-14"
        assert span["from"] == "last commit"

    def test_with_no_commits_it_falls_back_to_the_due_date(self):
        t = tasks()["T-1"]
        span = cause.window(t, [], TODAY)
        assert span["since"] == "2026-09-07"
        assert span["from"] == "due date"

    def test_an_overdue_task_reaches_back_to_its_due_date(self):
        # The question changes once a task is late: not "why so quiet lately" but "why is
        # this still not done". Anything since the due date is fair game for the answer.
        t = tasks()["T-1"]  # due 2026-09-07
        span = cause.window(t, [{"date": "2026-09-14"}], TODAY)
        assert span["since"] == "2026-09-07"
        assert span["from"] == "overdue since"

    def test_the_window_is_counted_in_business_days(self):
        # 2026-09-14 is a Monday; the following Monday is 5 business days on
        assert cause.window(quiet_task(), [{"date": "2026-09-14"}], TODAY)["days"] == 5


class TestCauses:
    def test_meetings_in_the_window_become_a_cause_with_their_hours(self):
        t = tasks()
        events = [meeting(f"2026-09-{d:02d}", 4.0, "Incident response") for d in (14, 15, 16, 17)]
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, events, TODAY)
        kinds = [c["kind"] for c in r["causes"]]
        assert "owner_in_meetings" in kinds
        top = next(c for c in r["causes"] if c["kind"] == "owner_in_meetings")
        assert "16.0h" in top["detail"]
        assert "Incident response" in top["detail"]
        assert top["source"] == "calendar"

    def test_someone_elses_meetings_are_not_this_tasks_cause(self):
        t = tasks()
        events = [meeting("2026-09-15", 8.0, "Incident response", who="Bo")]
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, events, TODAY)
        assert "owner_in_meetings" not in [c["kind"] for c in r["causes"]]

    def test_work_on_other_tasks_separates_could_not_from_did_not(self):
        t = tasks()
        snapshot = {
            "commits": [commit("a1", "feat: implement search", "2026-09-15")],
            "pulls": [],
            "people": {"Ada": "Ada"},
        }
        r = cause.explain("T-1", t, snapshot, [], TODAY)
        elsewhere = next(c for c in r["causes"] if c["kind"] == "owner_worked_elsewhere")
        assert "T-2 Search" in elsewhere["evidence"]

    def test_an_open_dependency_accounts_for_the_whole_silence(self):
        t = tasks(
            [
                {"key": "T-1", "summary": "Authentication", "assignee": "Ada", "points": 5},
                {
                    "key": "T-2",
                    "summary": "Search",
                    "assignee": "Ada",
                    "points": 3,
                    "deps": ["T-1"],
                    "duedate": "2026-09-07",
                },
            ]
        )
        r = cause.explain("T-2", t, {"commits": [], "pulls": []}, [], TODAY)
        dep = next(c for c in r["causes"] if c["kind"] == "dependency_open")
        assert dep["days"] == r["window"]["days"]
        assert dep["source"] == "board"

    def test_causes_are_ranked_by_the_days_they_explain(self):
        t = tasks()
        events = [meeting(f"2026-09-{d:02d}", 8.0, "Workshop") for d in (14, 15, 16, 17, 18)]
        snapshot = {
            "commits": [commit("a1", "feat: implement search", "2026-09-15")],
            "pulls": [],
            "people": {"Ada": "Ada"},
        }
        r = cause.explain("T-1", t, snapshot, events, TODAY)
        days = [c["days"] for c in r["causes"]]
        assert days == sorted(days, reverse=True)


class TestRestraint:
    """The half that matters: not inventing a cause."""

    def test_with_no_evidence_it_says_so_and_names_no_cause(self):
        t = tasks()
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, [], TODAY)
        assert r["causes"] == []
        assert r["explained_days"] == 0
        assert "nothing in the board" in r["note"]
        assert "question for its owner" in r["note"]

    def test_the_leftover_is_stated_rather_than_hidden(self):
        # One meeting-heavy day cannot account for ten silent ones, and the report says so
        t = tasks()
        events = [meeting("2026-09-15", 4.0, "Design review")]
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, events, TODAY)
        assert r["unexplained_days"] > 0
        assert "are not" in r["note"]

    def test_an_unknown_key_is_an_error_not_a_guess(self):
        r = cause.explain("NOPE", tasks(), {"commits": [], "pulls": []}, [], TODAY)
        assert "error" in r and "available" in r

    def test_no_gap_means_nothing_to_explain(self):
        t = tasks(
            [
                {
                    "key": "T-1",
                    "summary": "Authentication",
                    "assignee": "Ada",
                    "duedate": "2026-10-30",
                },
                {"key": "T-2", "summary": "Search", "assignee": "Ada", "duedate": "2026-10-30"},
            ]
        )
        snapshot = {
            "commits": [commit("a1", "feat: implement authentication", TODAY.isoformat())],
            "pulls": [],
            "people": {"Ada": "Ada"},
        }
        r = cause.explain("T-1", t, snapshot, [], TODAY)
        assert r["window"]["days"] == 0
        assert "no gap to explain" in r["note"]


class TestAgainstTheWorld:
    """The planted incident has to come back out."""

    def setup_method(self):
        self.world = world_mod.simulate()
        self.projected = world_mod.project(self.world)
        self.tasks = schedule.from_jira_issues(self.projected["board"]["issues"])
        self.truth = next(t for t in self.projected["truths"] if t["kind"] == "root_cause")

    def test_the_incident_meetings_surface_as_the_top_cause(self):
        r = cause.explain(
            self.truth["key"],
            self.tasks,
            self.projected["repo"],
            self.projected["calendar"]["events"],
            self.world.today,
        )
        assert r["causes"], "the planted incident produced no cause at all"
        meetings = [c for c in r["causes"] if c["kind"] == "owner_in_meetings"]
        assert meetings, "the incident calls are in the calendar but were not found"
        assert self.world.incident["key"] == self.truth["key"]
        # The incident calls should dominate that person's calendar across the window.
        # That is the only trace the incident leaves in any tool other than the notes.
        assert world_mod.INCIDENT_MEETING[0] in meetings[0]["detail"]
        assert self.world.incident["owner"] in meetings[0]["detail"]

    def test_an_overdue_task_is_explained_from_its_due_date(self):
        # Otherwise a fortnight lost to an incident falls outside the window the moment
        # somebody touches the task once, and goes unexplained.
        r = cause.explain(
            self.truth["key"],
            self.tasks,
            self.projected["repo"],
            self.projected["calendar"]["events"],
            self.world.today,
        )
        task = self.tasks[self.truth["key"]]
        if task.duedate and task.duedate < self.world.today:
            assert r["window"]["from"] == "overdue since"
            assert r["window"]["since"] == task.duedate.isoformat()

    def test_it_never_claims_more_than_the_window_holds(self):
        for row in cause.worst(
            self.tasks,
            self.projected["repo"],
            self.projected["calendar"]["events"],
            self.world.today,
            top=5,
        ):
            assert row["explained_days"] <= row["window"]["days"]

    def _worst(self, top=5):
        return cause.worst(
            self.tasks,
            self.projected["repo"],
            self.projected["calendar"]["events"],
            self.world.today,
            top=top,
        )

    def test_work_that_started_outranks_work_that_never_did(self):
        # All of them are silent, but only some ever began. A release task with no commits
        # weeks before its phase starts is a schedule question, not a mystery.
        rows = self._worst()
        began = [r["window"]["from"] in ("last commit", "overdue since") for r in rows]
        assert began[0], "the top answer was a task that had never been picked up"
        assert began == sorted(began, reverse=True)

    def test_within_a_group_the_longest_silence_comes_first(self):
        rows = self._worst()
        for group in (("last commit", "overdue since"), ("due date", "lookback")):
            spans = [r["window"]["days"] for r in rows if r["window"]["from"] in group]
            assert spans == sorted(spans, reverse=True)

    def test_finished_work_is_never_reported(self):
        assert all(not self.tasks[r["key"]].is_done for r in self._worst())

    def test_the_task_the_world_parked_is_found(self):
        parked = next(t for t in self.projected["truths"] if t["kind"] == "stalled")
        assert parked["key"] in [r["key"] for r in self._worst(top=8)]


class TestNotes:
    """The fourth tool: the only one that says *what* was decided."""

    def note(self, day, title, body, who="Ada"):
        return {"date": day, "author": who, "title": title, "body": body}

    def test_a_note_about_the_task_names_the_reason(self):
        t = tasks()
        written = [
            self.note(
                "2026-09-10",
                "Incident response — authentication",
                "The identity provider changed its token format. Authentication cannot move "
                "until we agree the new shape.",
            )
        ]
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, [], TODAY, notes=written)
        first = r["causes"][0]
        assert first["kind"] == "decision_recorded"
        assert first["source"] == "notes"
        assert "token format" in first["detail"]

    def test_a_written_decision_is_pinned_first(self):
        # It explains the reason, not the duration, so it carries no days — and still leads
        t = tasks()
        written = [
            self.note(
                "2026-09-10",
                "Incident response — authentication",
                "Authentication is blocked on the identity provider.",
            )
        ]
        events = [meeting(f"2026-09-{d:02d}", 8.0, "Workshop") for d in (14, 15, 16)]
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, events, TODAY, notes=written)
        assert r["causes"][0]["kind"] == "decision_recorded"
        assert r["causes"][0]["days"] == 0
        assert len(r["causes"]) > 1

    def test_a_decision_adds_no_days_to_the_tally(self):
        t = tasks()
        written = [self.note("2026-09-10", "Incident response — authentication", "Blocked.")]
        bare = cause.explain("T-1", t, {"commits": [], "pulls": []}, [], TODAY)
        with_note = cause.explain("T-1", t, {"commits": [], "pulls": []}, [], TODAY, notes=written)
        assert with_note["explained_days"] == bare["explained_days"]

    def test_a_note_that_says_nothing_specific_is_ignored(self):
        t = tasks()
        written = [self.note("2026-09-10", "Team sync", "Went through the board. Nothing to flag.")]
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, [], TODAY, notes=written)
        assert "decision_recorded" not in [c["kind"] for c in r["causes"]]

    def test_a_note_that_fits_two_tasks_equally_is_about_neither(self):
        t = tasks(
            [
                {"key": "T-1", "summary": "Search", "assignee": "Ada", "duedate": "2026-09-07"},
                {"key": "T-2", "summary": "Search", "assignee": "Ada", "duedate": "2026-09-07"},
            ]
        )
        written = [self.note("2026-09-10", "Design review — search", "Search is on hold.")]
        for key in ("T-1", "T-2"):
            r = cause.explain(key, t, {"commits": [], "pulls": []}, [], TODAY, notes=written)
            assert "decision_recorded" not in [c["kind"] for c in r["causes"]]

    def test_a_written_decision_shows_before_anything_is_overdue(self):
        # The useful moment for "what is blocking this" is before the due date passes,
        # not after. A task with no silence still has a story if someone wrote one.
        t = tasks(
            [
                {
                    "key": "T-1",
                    "summary": "Authentication",
                    "assignee": "Ada",
                    "duedate": "2026-10-30",
                },
                {"key": "T-2", "summary": "Search", "assignee": "Ada", "duedate": "2026-10-30"},
            ]
        )
        written = [
            self.note(
                "2026-09-10",
                "Incident response — authentication",
                "Authentication is blocked on the identity provider.",
            )
        ]
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, [], TODAY, notes=written)
        assert r["window"]["days"] == 0
        assert r["causes"][0]["kind"] == "decision_recorded"
        assert "written down about it" in r["note"]

    def test_a_note_outside_the_window_is_not_used(self):
        t = tasks()
        # Older than the lookback, so it is not evidence about now
        written = [
            self.note("2026-05-01", "Incident response — authentication", "Blocked on the IdP.")
        ]
        r = cause.explain("T-1", t, {"commits": [], "pulls": []}, [], TODAY, notes=written)
        assert "decision_recorded" not in [c["kind"] for c in r["causes"]]

    def test_the_worlds_written_decision_comes_back(self):
        world = world_mod.simulate()
        projected = world_mod.project(world)
        t = schedule.from_jira_issues(projected["board"]["issues"])
        truth = next(x for x in projected["truths"] if x["kind"] == "decision_recorded")
        r = cause.explain(
            truth["key"],
            t,
            projected["repo"],
            projected["calendar"]["events"],
            world.today,
            notes=projected["notes"]["notes"],
        )
        written = [c for c in r["causes"] if c["kind"] == "decision_recorded"]
        assert written, "the decision is in a note but was not found"
        assert truth["detail"] in written[0]["detail"]

    def test_no_note_carries_a_ticket_key(self):
        # The whole point: a team writing minutes does not annotate them with issue IDs
        import re

        projected = world_mod.project(world_mod.simulate())
        pattern = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d+\b")
        for note in projected["notes"]["notes"]:
            assert not pattern.search(f"{note['title']} {note['body']}"), note


class TestTrace:
    """Telling "they did not come here" apart from "nobody can see them".

    Both land in the same leftover number, and they are opposite problems. The first is a
    question for a person; the second is a question about which system nobody connected.
    """

    SINCE = dt.date(2026, 9, 7)  # a Monday
    UNTIL = dt.date(2026, 9, 12)  # the Saturday after, so five working days

    def trace(self, commits=(), events=(), who="Ada", calendar=True):
        return cause._trace(list(commits), list(events), who, self.SINCE, self.UNTIL, calendar)

    def test_the_weekend_is_not_a_missing_day(self):
        got = cause._trace(
            [commit("a", "work", "2026-09-07")],
            [],
            "Ada",
            dt.date(2026, 9, 7),
            dt.date(2026, 9, 14),
            False,
        )
        assert got["workdays"] == 5

    def test_a_commit_anywhere_is_a_trace(self):
        got = self.trace([commit("a", "other work", "2026-09-08")], calendar=False)
        assert (got["with_trace"], got["no_trace"]) == (1, 4)

    def test_an_unlinked_commit_still_counts(self):
        # The linker's own uncertainty must not come out as somebody's missing day. This
        # takes the raw snapshot, so a commit nothing could be made of is still a trace.
        got = self.trace([commit("a", "wip", "2026-09-08")], calendar=False)
        assert got["no_trace"] == 4

    def test_a_meeting_alone_is_a_trace(self):
        got = self.trace(events=[meeting("2026-09-09", 1.0, "Team sync")])
        assert got["with_trace"] == 1

    def test_a_day_with_both_is_counted_once(self):
        got = self.trace(
            [commit("a", "work", "2026-09-08")], [meeting("2026-09-08", 1.0, "Team sync")]
        )
        assert (got["with_trace"], got["no_trace"]) == (1, 4)

    def test_somebody_elses_activity_is_not_theirs(self):
        got = self.trace(
            [commit("a", "work", "2026-09-08"), commit("b", "work", "2026-09-09", who="Bo")]
        )
        assert got["with_trace"] == 1

    def test_a_name_that_matches_nothing_gives_no_count(self):
        # A Jira assignee whose name never matches a git author would otherwise read as
        # invisible every single day, which says nothing about them at all
        assert self.trace([commit("a", "work", "2026-09-08", who="Bo")]) is None
        assert self.trace(who="") is None

    def test_without_a_calendar_it_says_where_it_looked(self):
        got = self.trace([commit("a", "work", "2026-09-08")], calendar=False)
        assert got["looked_in"] == ["the repository"]

    def test_with_a_calendar_it_says_both(self):
        got = self.trace([commit("a", "work", "2026-09-08")])
        assert got["looked_in"] == ["the repository", "the calendar"]


class TestTraceInTheNote:
    def test_a_blind_spot_is_named_as_one(self):
        dark = {
            "workdays": 10,
            "with_trace": 6,
            "no_trace": 4,
            "looked_in": ["the repository"],
            "first": "",
            "last": "",
        }
        said = cause._blind(dark)
        assert "on the other 4 there is none at all" in said
        assert "blind spot" in said

    def test_a_visible_person_turns_it_into_a_question(self):
        dark = {
            "workdays": 10,
            "with_trace": 10,
            "no_trace": 0,
            "looked_in": ["the repository"],
            "first": "",
            "last": "",
        }
        said = cause._blind(dark)
        assert "question for them" in said
        assert "blind spot" not in said

    def test_with_nothing_to_say_it_says_nothing(self):
        assert cause._blind(None) == ""
        assert cause._blind({"workdays": 0, "with_trace": 0, "no_trace": 0, "looked_in": []}) == ""

    def test_the_explanation_carries_it(self):
        t = tasks()
        got = cause.explain(
            "T-1",
            t,
            {"commits": [commit("a", "search tweaks", "2026-09-15")], "pulls": []},
            [meeting("2026-09-16", 6.0, "Incident response")],
            TODAY,
        )
        assert got["trace"]["workdays"] == got["window"]["days"]
        assert got["trace"]["no_trace"] <= got["trace"]["workdays"]

    def test_an_unknown_owner_leaves_the_note_alone(self):
        # Nobody named Ada in either tool: the sentence must not appear at all
        t = tasks()
        got = cause.explain("T-1", t, {"commits": [], "pulls": []}, [], TODAY)
        assert got["trace"] is None
        assert "blind spot" not in got["note"]


class TestTheDaysAreCountedOnce:
    """Adding the causes up double-counts, and the cap used to hide it.

    A person in meetings on Tuesday who also committed to another task on Tuesday had
    Tuesday claimed twice. The total was then capped at the length of the window, so the
    overcount did not read as an error — it came out as "all N silent business days are
    accounted for", which is the most confident thing this module can say.

    Every test here is about one day being worth one day.
    """

    def busy_week(self, meetings, elsewhere_days=()):
        """A task silent since Monday, with the owner's week described explicitly."""
        t = tasks(
            [
                {"key": "T-1", "summary": "Authentication", "assignee": "Ada", "duedate": None},
                {"key": "T-2", "summary": "Search", "assignee": "Ada", "duedate": None},
            ]
        )
        commits = [commit("seed", "authentication groundwork", "2026-09-14")]
        commits += [commit(f"e{i}", "search tweaks", day) for i, day in enumerate(elsewhere_days)]
        return cause.explain(
            "T-1",
            t,
            {"commits": commits, "pulls": []},
            [meeting(day, hours, "Workshop") for day, hours in meetings],
            dt.date(2026, 9, 21),
            notes=[],
        )

    def test_a_full_day_of_meetings_and_a_commit_elsewhere_is_one_day(self):
        got = self.busy_week([("2026-09-15", 8.0)], elsewhere_days=["2026-09-15"])
        assert got["explained_days"] == 1.0
        assert got["overlap"] == 1.0, "the two causes each claimed the same Tuesday"

    def test_the_same_two_causes_on_different_days_are_two_days(self):
        got = self.busy_week([("2026-09-15", 8.0)], elsewhere_days=["2026-09-16"])
        assert got["explained_days"] == 2.0
        assert got["overlap"] == 0.0

    def test_half_a_day_of_meetings_is_half_a_day(self):
        got = self.busy_week([("2026-09-15", 4.0)])
        assert got["explained_days"] == 0.5

    def test_meetings_longer_than_a_day_still_buy_one_day(self):
        # Overlapping invitations are ordinary; 12 hours in a day is a calendar artefact
        got = self.busy_week([("2026-09-15", 12.0)])
        assert got["explained_days"] == 1.0

    def test_an_overcount_no_longer_reads_as_a_full_account(self):
        # This is the case the cap hid: claims well over the window, union well under it
        got = self.busy_week(
            [(d, 8.0) for d in ("2026-09-15", "2026-09-16", "2026-09-17")],
            elsewhere_days=["2026-09-15", "2026-09-16", "2026-09-17"],
        )
        assert sum(c["days"] for c in got["causes"]) > got["explained_days"]
        assert "All" not in got["note"]
        assert got["explained_days"] < got["window"]["days"]

    def test_it_never_claims_more_days_than_the_window_holds(self):
        got = self.busy_week(
            [(d, 8.0) for d in ("2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18")],
            elsewhere_days=["2026-09-15", "2026-09-16", "2026-09-17", "2026-09-18"],
        )
        assert got["explained_days"] <= got["window"]["days"]
        assert got["unexplained_days"] >= 0

    def test_an_open_dependency_accounts_for_the_whole_window(self):
        t = tasks(
            [
                {"key": "T-1", "summary": "Authentication", "assignee": "Ada", "deps": ["T-2"]},
                {"key": "T-2", "summary": "Search", "assignee": "Bo", "status": "To Do"},
            ]
        )
        got = cause.explain(
            "T-1",
            t,
            {"commits": [commit("a", "authentication start", "2026-09-14")], "pulls": []},
            [],
            TODAY,
        )
        assert got["explained_days"] == got["window"]["days"]
        assert "All" in got["note"]

    def test_a_weekend_is_not_a_day_anybody_has_to_account_for(self):
        # 2026-09-19 and 20 are a Saturday and Sunday
        got = self.busy_week([("2026-09-19", 8.0), ("2026-09-20", 8.0)])
        assert got["explained_days"] == 0.0

    def test_overlap_is_never_negative(self):
        got = self.busy_week([("2026-09-15", 2.0)])
        assert got["overlap"] >= 0
