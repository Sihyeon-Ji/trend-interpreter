"""ingest.py unit tests — verified with fake Gemini responses, no API key.

Run: python -m pytest tests/test_ingest.py -q
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import tempfile
import unittest

import pytest

from pmo_agent import ingest, schedule  # noqa: E402
from pmo_agent.schedule import to_tasks  # noqa: E402

TODAY = dt.date(2026, 9, 21)


def tasks():
    return to_tasks(
        [
            {
                "key": "ECHO-1",
                "summary": "Requirements",
                "status": "Done",
                "assignee": "Kim",
                "points": 3,
            },
            {
                "key": "ECHO-2",
                "summary": "Schema design",
                "status": "In Progress",
                "assignee": "Lee",
                "points": 4,
                "deps": ["ECHO-1"],
                "duedate": "2026-09-24",
            },
            {
                "key": "ECHO-3",
                "summary": "API build",
                "status": "To Do",
                "assignee": "Park",
                "points": 5,
                "deps": ["ECHO-2"],
                "duedate": "2026-09-29",
            },
            {
                "key": "ECHO-4",
                "summary": "API documentation",
                "status": "To Do",
                "assignee": "Park",
                "points": 1,
            },
        ]
    )


def fake_response(payload):
    """Wrap it in the shape of a Gemini generateContent response."""
    return {
        "candidates": [{"content": {"parts": [{"text": json.dumps(payload, ensure_ascii=False)}]}}]
    }


def caller_returning(payload):
    def _c(parts):
        _c.parts = parts
        return fake_response(payload)

    return _c


class TestAttach(unittest.TestCase):
    def test_the_extension_picks_the_mime_type(self):
        self.assertEqual(ingest.mime_of("a/b/note.PNG"), "image/png")
        self.assertEqual(ingest.mime_of("note.jpeg"), "image/jpeg")

    def test_an_unknown_format_is_refused(self):
        with self.assertRaises(ValueError):
            ingest.mime_of("note.txt")

    def test_the_image_rides_along_as_base64(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG fake bytes")
            path = f.name
        try:
            part = ingest.attach(path)
            self.assertEqual(part["inline_data"]["mime_type"], "image/png")
            self.assertEqual(base64.b64decode(part["inline_data"]["data"]), b"\x89PNG fake bytes")
        finally:
            os.unlink(path)

    def test_too_large_is_refused(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"0")
            path = f.name
        try:
            ingest.MAX_BYTES, keep = 0, ingest.MAX_BYTES
            with self.assertRaises(ValueError):
                ingest.attach(path)
        finally:
            ingest.MAX_BYTES = keep
            os.unlink(path)


class TestBuildParts(unittest.TestCase):
    def test_it_sends_today_and_the_real_keys(self):
        head = ingest.build_parts("meeting note", today=TODAY, keys=["ECHO-1", "ECHO-2"])[0]["text"]
        self.assertIn("2026-09-21", head)
        self.assertIn("ECHO-1", head)
        self.assertIn("meeting note", head)

    def test_an_image_is_attached_as_a_part(self):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"jpeg")
            path = f.name
        try:
            parts = ingest.build_parts("note", [path], TODAY)
            self.assertEqual(len(parts), 2)
            self.assertIn("inline_data", parts[1])
        finally:
            os.unlink(path)


class TestParse(unittest.TestCase):
    def test_it_reads_normal_json(self):
        r = ingest.parse(
            fake_response({"updates": [{"task": "ECHO-2"}], "notes": ["a note"], "questions": []})
        )
        self.assertEqual(r["updates"][0]["task"], "ECHO-2")
        self.assertEqual(r["notes"], ["a note"])

    def test_an_empty_response_becomes_a_question(self):
        r = ingest.parse({"candidates": [{"content": {"parts": []}}]})
        self.assertEqual(r["updates"], [])
        self.assertTrue(r["questions"])

    def test_broken_json_does_not_kill_it(self):
        r = ingest.parse({"candidates": [{"content": {"parts": [{"text": "{not json at all"}]}}]})
        self.assertEqual(r["updates"], [])
        self.assertTrue(r["questions"])
        self.assertIn("raw", r)


class TestResolve(unittest.TestCase):
    def test_an_exact_key_passes_through(self):
        self.assertEqual(ingest.resolve("ECHO-2", tasks())[0], "ECHO-2")

    def test_case_is_ignored(self):
        self.assertEqual(ingest.resolve("echo-2", tasks())[0], "ECHO-2")

    def test_a_partial_title_match_is_found(self):
        self.assertEqual(ingest.resolve("schema", tasks())[0], "ECHO-2")

    def test_it_matches_whole_words_not_letters(self):
        # "search" inside "Competitor research" used to make a clear reference ambiguous.
        # The restraint was working; the ambiguity was invented.
        t = schedule.to_tasks(
            [
                {"key": "ECHO-1", "summary": "Search", "assignee": "Kim"},
                {"key": "ECHO-2", "summary": "Competitor research", "assignee": "Kim"},
            ]
        )
        assert ingest.resolve("search", t)[0] == "ECHO-1"
        assert ingest.resolve("research", t)[0] == "ECHO-2"

    def test_a_word_that_really_fits_two_tasks_still_goes_to_a_person(self):
        t = schedule.to_tasks(
            [
                {"key": "ECHO-1", "summary": "Authentication", "assignee": "Kim"},
                {"key": "ECHO-2", "summary": "Authentication approach", "assignee": "Kim"},
            ]
        )
        key, why = ingest.resolve("authentication", t)
        assert key is None and "ECHO-1" in why and "ECHO-2" in why

    def test_several_matches_go_to_a_person(self):
        key, why = ingest.resolve("API", tasks())  # matches both API tasks
        self.assertIsNone(key)
        self.assertIn("ECHO-3", why)
        self.assertIn("ECHO-4", why)

    def test_a_task_that_does_not_exist_is_refused(self):
        self.assertIsNone(ingest.resolve("deployment automation", tasks())[0])


class TestValidate(unittest.TestCase):
    def test_a_due_date_change_passes(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-3", "duedate": "2026-10-05", "confidence": 0.9}]},
            tasks(),
            TODAY,
        )
        self.assertEqual(v["resolved"][0]["key"], "ECHO-3")
        self.assertEqual(v["resolved"][0]["duedate"], "2026-10-05")
        self.assertEqual(v["resolved"][0]["duedate_was"], "2026-09-29")

    def test_a_task_that_does_not_exist_becomes_a_question(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-99", "duedate": "2026-10-05"}]}, tasks(), TODAY
        )
        self.assertEqual(v["resolved"], [])
        self.assertEqual(len(v["unresolved"]), 1)
        self.assertTrue(v["questions"])

    def test_a_non_iso_date_is_refused(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-3", "duedate": "next Tuesday"}]}, tasks(), TODAY
        )
        self.assertEqual(v["resolved"], [])
        self.assertIn("cannot read the date", v["unresolved"][0]["reason"])

    def test_a_nonsensical_date_is_refused(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-3", "duedate": "2099-01-01"}]}, tasks(), TODAY
        )
        self.assertEqual(v["resolved"], [])
        self.assertIn("makes no sense", v["unresolved"][0]["reason"])

    def test_nothing_to_change_is_refused(self):
        v = ingest.validate({"updates": [{"task": "ECHO-3", "confidence": 0.8}]}, tasks(), TODAY)
        self.assertEqual(v["resolved"], [])

    def test_status_and_note_ride_along(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-2", "status": "Done", "note": "review finished"}]},
            tasks(),
            TODAY,
        )
        self.assertEqual(v["resolved"][0]["status"], "Done")
        self.assertEqual(v["resolved"][0]["note"], "review finished")

    def test_it_keeps_the_model_questions(self):
        v = ingest.validate(
            {"updates": [], "questions": ["the note does not say who owns it"]}, tasks(), TODAY
        )
        self.assertIn("the note does not say who owns it", v["questions"])


class TestProposals(unittest.TestCase):
    def test_each_kind_of_change_maps_to_a_propose_tool(self):
        v = ingest.validate(
            {
                "updates": [
                    {
                        "task": "ECHO-3",
                        "duedate": "2026-10-05",
                        "status": "In Progress",
                        "note": "delayed",
                    }
                ]
            },
            tasks(),
            TODAY,
        )
        p = ingest.to_proposals(v)
        self.assertEqual(
            [x["tool"] for x in p],
            ["propose_field_update", "propose_transition", "propose_comment"],
        )
        self.assertEqual(p[0]["args"], {"key": "ECHO-3", "duedate": "2026-10-05"})

    def test_a_write_tool_is_a_proposal_and_never_runs(self):
        v = ingest.validate(
            {"updates": [{"task": "ECHO-3", "duedate": "2026-10-05"}]}, tasks(), TODAY
        )
        self.assertTrue(
            all(x["tool"].startswith(("propose_", "note")) for x in ingest.to_proposals(v))
        )


class TestImpact(unittest.TestCase):
    def test_pulling_a_due_date_in_creates_a_new_risk(self):
        # A one-day task forecast to finish 9/22 — pull its due date to 9/21 and it is late
        v = ingest.validate(
            {"updates": [{"task": "ECHO-4", "duedate": "2026-09-21"}]}, tasks(), TODAY
        )
        i = ingest.impact(v["resolved"], tasks(), TODAY)
        self.assertIn("ECHO-4", [x["key"] for x in i["newly_at_risk"]])

    def test_marking_it_done_pulls_the_forecast_in(self):
        v = ingest.validate({"updates": [{"task": "ECHO-2", "status": "Done"}]}, tasks(), TODAY)
        i = ingest.impact(v["resolved"], tasks(), TODAY)
        self.assertLess(i["predicted_finish_after"], i["predicted_finish_before"])

    def test_the_original_tasks_are_untouched(self):
        t = tasks()
        v = ingest.validate({"updates": [{"task": "ECHO-3", "duedate": "2026-10-05"}]}, t, TODAY)
        ingest.impact(v["resolved"], t, TODAY)
        self.assertEqual(t["ECHO-3"].duedate, dt.date(2026, 9, 29))


class TestIngest(unittest.TestCase):
    def test_the_whole_path_runs(self):
        caller = caller_returning(
            {
                "updates": [
                    {
                        "task": "schema",
                        "duedate": "2026-09-28",
                        "note": "the DB decision is late",
                        "confidence": 0.8,
                    },
                    {"task": "ECHO-99", "duedate": "2026-10-01"},
                ],
                "notes": ["team sync cancelled next Monday"],
                "questions": [],
            }
        )
        r = ingest.ingest("meeting note", tasks=tasks(), today=TODAY, caller=caller)
        self.assertEqual(r["resolved"][0]["key"], "ECHO-2")
        self.assertEqual(len(r["unresolved"]), 1)
        self.assertTrue(r["questions"])
        self.assertFalse(r["applied"])
        self.assertIsNotNone(r["impact"])
        json.dumps(r, ensure_ascii=False)

    def test_no_input_is_an_error(self):
        self.assertIn(
            "error", ingest.ingest(tasks=tasks(), today=TODAY, caller=caller_returning({}))
        )

    def test_nothing_read_means_no_impact(self):
        r = ingest.ingest(
            "note", tasks=tasks(), today=TODAY, caller=caller_returning({"updates": []})
        )
        self.assertEqual(r["resolved"], [])
        self.assertIsNone(r["impact"])

    def test_it_gives_the_model_the_real_key_list(self):
        caller = caller_returning({"updates": []})
        ingest.ingest("note", tasks=tasks(), today=TODAY, caller=caller)
        self.assertIn("ECHO-4", caller.parts[0]["text"])

    def test_with_no_key_the_call_itself_is_blocked(self):
        # llm.py is what reads the key. Emptying it here is what keeps the test off the network —
        # a unit test must never call an external API, under any circumstances.
        from pmo_agent import llm

        keep, llm.env = llm.env, lambda k, d="": "" if k == "GEMINI_API_KEY" else d
        try:
            with self.assertRaises(llm.LLMError):
                ingest.call([{"text": "x"}])
        finally:
            llm.env = keep


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestListeningToARecording:
    """Audio is the same path as a photo, with one difference that matters.

    A blurred word is visibly blurred — a person looking at the photo sees what the model
    was up against. A misheard word is not: the claim arrives as the same tidy JSON either
    way, and nobody re-listens to thirty minutes to audit a date. So a recording has to
    bring its transcript back, and a claim resting on a stretch nobody could make out has
    to be demoted rather than applied.
    """

    def heard(self, transcript, updates, **kw):
        return ingest.validate(
            {"updates": updates, "notes": [], "questions": [], "transcript": transcript},
            tasks(),
            TODAY,
            **kw,
        )

    def test_the_usual_audio_formats_are_accepted(self):
        for ext in (".m4a", ".mp3", ".wav", ".ogg", ".flac", ".aac", ".webm"):
            assert ingest.mime_of("meeting" + ext).startswith("audio/"), ext

    def test_a_format_nobody_asked_for_is_still_refused(self):
        with pytest.raises(ValueError):
            ingest.mime_of("meeting.mov")

    def test_it_knows_which_attachments_are_recordings(self):
        assert ingest.is_audio("a.m4a") and not ingest.is_audio("a.png")

    def test_the_prompt_asks_for_a_transcript_only_when_there_is_audio(self, tmp_path):
        rec = tmp_path / "standup.m4a"
        rec.write_bytes(b"not really audio, but it has the extension")
        pic = tmp_path / "note.png"
        pic.write_bytes(b"not really a png either")

        with_audio = ingest.build_parts("", [str(rec)], TODAY)[0]["text"]
        with_image = ingest.build_parts("", [str(pic)], TODAY)[0]["text"]
        assert "transcript" in with_audio and "listen" in with_audio
        assert "transcript" not in with_image

    def test_both_kinds_can_go_in_one_call(self, tmp_path):
        rec = tmp_path / "standup.m4a"
        rec.write_bytes(b"x")
        pic = tmp_path / "note.png"
        pic.write_bytes(b"y")
        head = ingest.build_parts("", [str(rec), str(pic)], TODAY)[0]["text"]
        assert "1 attached image" in head and "1 attached recording" in head

    def test_the_transcript_comes_back_with_the_claims(self):
        # The only thing a person can check a recording's claims against
        said = "Ada: authentication moves to the 28th."
        got = self.heard(said, [{"task": "ECHO-1", "duedate": "2026-09-28", "confidence": 0.9}])
        assert got["transcript"] == said
        assert got["resolved"][0]["duedate"] == "2026-09-28"

    def test_a_clear_recording_still_produces_proposals(self):
        got = self.heard(
            "Ada: authentication moves to the 28th.",
            [{"task": "ECHO-1", "duedate": "2026-09-28", "confidence": 0.75}],
        )
        assert len(got["resolved"]) == 1 and not got["unresolved"]

    def test_an_unsure_claim_from_a_muddy_recording_becomes_a_question(self):
        got = self.heard(
            "Ada: authentication moves to the [unclear].",
            [{"task": "ECHO-1", "duedate": "2026-09-28", "confidence": 0.4}],
        )
        assert got["resolved"] == []
        assert any("unclear" in q for q in got["questions"])
        assert got["unresolved"][0]["reason"] == "unclear audio"

    def test_a_sure_claim_survives_a_recording_that_was_muddy_elsewhere(self):
        # One lost word must not throw away everything else that was said plainly
        got = self.heard(
            "Ada: the [unclear] is fine. Authentication moves to the 28th.",
            [{"task": "ECHO-1", "duedate": "2026-09-28", "confidence": 0.95}],
        )
        assert len(got["resolved"]) == 1

    def test_an_unsure_claim_from_a_clear_recording_is_not_demoted(self):
        # The floor is about audio nobody could make out, not about low confidence per se
        got = self.heard(
            "Ada: authentication moves to the 28th.",
            [{"task": "ECHO-1", "duedate": "2026-09-28", "confidence": 0.3}],
        )
        assert len(got["resolved"]) == 1

    def test_text_and_photos_are_untouched_by_any_of_this(self):
        got = ingest.validate(
            {"updates": [{"task": "ECHO-1", "duedate": "2026-09-28", "confidence": 0.2}]},
            tasks(),
            TODAY,
        )
        assert len(got["resolved"]) == 1 and got["transcript"] == ""
