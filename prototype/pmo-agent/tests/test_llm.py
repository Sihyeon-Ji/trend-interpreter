"""llm.py tests — request assembly, retries and error handling, with no network.

A unit test never calls the real API. urlopen is replaced wholesale.

Run: python -m pytest tests/test_llm.py -q
"""

from __future__ import annotations

import io
import json
import unittest
import urllib.error

import pytest

from pmo_agent import llm  # noqa: E402

BODY = {"contents": [{"role": "user", "parts": [{"text": "hi"}]}]}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def ok(payload=None):
    return FakeResponse(
        json.dumps(payload or {"candidates": [{"content": {"parts": [{"text": "yes"}]}}]}).encode()
    )


def http_error(code):
    return urllib.error.HTTPError(
        "u", code, "err", {}, io.BytesIO(json.dumps({"error": {"code": code}}).encode())
    )


class LLMTestCase(unittest.TestCase):
    """Isolate both the environment and the network."""

    env = {
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-3.6-flash",
        "LLM_BACKEND": "aistudio",
    }

    def setUp(self):
        self.calls = []
        self.keep_env, llm.env = llm.env, lambda k, d="": self.env.get(k, d)
        self.keep_open, self.keep_sleep = llm.urllib.request.urlopen, llm.time.sleep
        llm.time.sleep = lambda s: None  # skip the retry wait
        llm.urllib.request.urlopen = self.fake_open

    def tearDown(self):
        llm.env = self.keep_env
        llm.urllib.request.urlopen = self.keep_open
        llm.time.sleep = self.keep_sleep

    def fake_open(self, req, timeout=None):
        self.calls.append(req)
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    responses = []


class TestRequestBuilding(LLMTestCase):
    def test_aistudio_puts_the_key_in_the_url(self):
        self.responses = [ok()]
        llm.generate(BODY)
        url = self.calls[0].full_url
        self.assertIn("generativelanguage.googleapis.com", url)
        self.assertIn("gemini-3.6-flash:generateContent", url)
        self.assertIn("key=test-key", url)

    def test_the_model_can_be_overridden_per_call(self):
        self.responses = [ok()]
        llm.generate(BODY, model="gemini-3.1-flash-lite")
        self.assertIn("gemini-3.1-flash-lite", self.calls[0].full_url)

    def test_with_no_key_it_never_calls(self):
        self.env = {"GEMINI_API_KEY": ""}
        self.responses = []
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY)
        self.assertEqual(self.calls, [])

    def test_the_body_goes_out_as_json(self):
        self.responses = [ok()]
        llm.generate(BODY)
        self.assertEqual(json.loads(self.calls[0].data), BODY)


class TestVertexBackend(LLMTestCase):
    env = {
        "LLM_BACKEND": "vertex",
        "GCP_PROJECT_ID": "echo-pmo-2026",
        "GCP_REGION": "asia-northeast3",
    }

    def test_a_missing_project_is_reported_straight_away(self):
        self.env = {"LLM_BACKEND": "vertex", "GCP_PROJECT_ID": ""}
        self.responses = []
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY)
        self.assertIn("GCP_PROJECT_ID", str(e.exception))

    def test_the_adc_token_rides_in_the_header(self):
        keep, llm._vertex_token = llm._vertex_token, lambda: "ya29.fake"
        self.responses = [ok()]
        try:
            llm.generate(BODY)
        finally:
            llm._vertex_token = keep
        req = self.calls[0]
        self.assertIn("aiplatform.googleapis.com", req.full_url)
        self.assertIn("echo-pmo-2026", req.full_url)
        self.assertEqual(req.get_header("Authorization"), "Bearer ya29.fake")
        self.assertNotIn("key=", req.full_url)  # the key never leaks into the URL

    def test_it_reads_the_backend_name(self):
        self.assertEqual(llm.backend(), "vertex")


class TestRetry(LLMTestCase):
    """The retry loop on its own — fallback is off, to isolate one model's behaviour."""

    env = {
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-3.6-flash",
        "GEMINI_FALLBACK_MODEL": "",
        "LLM_BACKEND": "aistudio",
    }

    def test_overload_is_retried(self):
        self.responses = [http_error(503), http_error(429), ok()]
        self.assertTrue(llm.generate(BODY, verbose=False))
        self.assertEqual(len(self.calls), 3)

    def test_exhausting_the_retries_raises(self):
        self.responses = [http_error(503)] * llm.RETRIES
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(len(self.calls), llm.RETRIES)

    def test_our_own_bug_is_raised_at_once(self):
        self.responses = [http_error(400)]
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY, verbose=False)
        self.assertEqual(len(self.calls), 1)  # retrying a 400 changes nothing
        self.assertIn("400", str(e.exception))

    def test_the_error_body_goes_into_the_message(self):
        self.responses = [http_error(404)]
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY, verbose=False)
        self.assertIn("error", str(e.exception))

    def test_a_network_error_is_retried_too(self):
        self.responses = [urllib.error.URLError("dropped"), ok()]
        self.assertTrue(llm.generate(BODY, verbose=False))


class TestFallbackModel(LLMTestCase):
    env = {
        "GEMINI_API_KEY": "k",
        "GEMINI_MODEL": "gemini-3.6-flash",
        "GEMINI_FALLBACK_MODEL": "gemini-3.5-flash",
        "LLM_BACKEND": "aistudio",
    }

    def models_called(self):
        return [u.full_url.split("/models/")[1].split(":")[0] for u in self.calls]

    def test_a_main_model_that_keeps_overloading_moves_to_the_fallback(self):
        self.responses = [http_error(503)] * llm.RETRIES + [ok()]
        self.assertTrue(llm.generate(BODY, verbose=False))
        called = self.models_called()
        self.assertEqual(called[0], "gemini-3.6-flash")
        self.assertEqual(called[-1], "gemini-3.5-flash")

    def test_a_config_error_does_not_fall_back(self):
        # A missing key is missing for every model. This used to announce a fallback here too.
        self.env = {**self.env, "GEMINI_API_KEY": ""}
        self.responses = []
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY, verbose=False)
        self.assertEqual(self.calls, [])
        self.assertIsNone(e.exception.status)

    def test_the_status_code_rides_on_the_exception(self):
        self.responses = [http_error(400)]
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY, verbose=False)
        self.assertEqual(e.exception.status, 400)

    def test_it_is_not_fooled_by_a_number_inside_the_body(self):
        # A 400 is not a fallback case even when '503' happens to appear in the response body
        import io as _io
        import urllib.error as _ue

        err = _ue.HTTPError("u", 400, "bad", {}, _io.BytesIO(b'{"error":"token 503 invalid"}'))
        self.responses = [err]
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(len(self.calls), 1)

    def test_anything_but_overload_keeps_the_same_model(self):
        self.responses = [http_error(400)]
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(set(self.models_called()), {"gemini-3.6-flash"})

    def test_turning_the_fallback_off_leaves_one_model(self):
        self.env = {**self.env, "GEMINI_FALLBACK_MODEL": ""}
        self.responses = [http_error(503)] * llm.RETRIES
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(set(self.models_called()), {"gemini-3.6-flash"})

    def test_a_failing_fallback_raises_too(self):
        self.responses = [http_error(503)] * (llm.RETRIES * 2)
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(len(self.calls), llm.RETRIES * 2)


class TestLogSafety(LLMTestCase):
    """A failed progress message must not cost the request (the Windows cp949 incident)."""

    def test_retries_continue_even_when_printing_blows_up(self):
        import builtins

        keep = builtins.print

        def boom(*a, **k):
            raise UnicodeEncodeError("cp949", "x", 0, 1, "illegal multibyte sequence")

        builtins.print = boom
        self.responses = [http_error(429), ok()]
        try:
            self.assertTrue(llm.generate(BODY, verbose=True))
        finally:
            builtins.print = keep
        self.assertEqual(len(self.calls), 2)

    def test_the_log_function_swallows_exceptions(self):
        import builtins

        keep, builtins.print = (
            builtins.print,
            lambda *a, **k: (_ for _ in ()).throw(OSError("closed")),
        )
        try:
            llm._log("anything")
        finally:
            builtins.print = keep


class TestHelpers(LLMTestCase):
    def test_it_joins_the_text_parts(self):
        r = {"candidates": [{"content": {"parts": [{"text": "a"}, {"text": "b"}]}}]}
        self.assertEqual(llm.text_of(r), "ab")

    def test_an_empty_response_is_handled(self):
        self.assertEqual(llm.text_of({}), "")
        self.assertEqual(llm.parts_of({}), [])

    def test_it_hands_the_parts_back_as_they_are(self):
        r = {"candidates": [{"content": {"parts": [{"functionCall": {"name": "x"}}]}}]}
        self.assertEqual(llm.parts_of(r), [{"functionCall": {"name": "x"}}])


if __name__ == "__main__":
    unittest.main(verbosity=2)


QUOTA_429 = """{
  "error": {
    "code": 429,
    "message": "You exceeded your current quota. Quota exceeded for metric:
      generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20,
      model: gemini-3.6-flash. Please retry in 21.75660148s.",
    "status": "RESOURCE_EXHAUSTED",
    "details": [
      {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
       "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                       "quotaValue": "20"}]},
      {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "21s"}
    ]
  }
}"""

BURST_429 = """{
  "error": {
    "code": 429, "status": "RESOURCE_EXHAUSTED",
    "details": [
      {"@type": "type.googleapis.com/google.rpc.QuotaFailure",
       "violations": [{"quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier"}]},
      {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "3s"}
    ]
  }
}"""


class TestReadingA429:
    """A 429 is two different problems wearing one number.

    A per-minute burst limit clears in seconds and is worth waiting out. A free-tier *day*
    limit does not come back until tomorrow, and waiting four seconds for it is four
    seconds of a demo spent on a call that cannot succeed. The body says which.
    """

    def test_it_reads_the_wait_the_provider_asked_for(self):
        assert llm._wait_hint(QUOTA_429) == 21.0
        assert llm._wait_hint(BURST_429) == 3.0

    def test_a_fractional_wait_is_read_too(self):
        assert llm._wait_hint('{"retryDelay": "1.5s"}') == 1.5

    def test_no_hint_is_none_rather_than_zero(self):
        # Zero would read as "retry immediately", which is the opposite of "it did not say"
        assert llm._wait_hint('{"error": {"code": 503}}') is None
        assert llm._wait_hint("") is None

    def test_it_tells_a_daily_limit_from_a_burst_one(self):
        assert llm._daily_quota(QUOTA_429)
        assert not llm._daily_quota(BURST_429)
        assert not llm._daily_quota("")


class TestWhatItDoesAboutIt:
    def attempts(self, monkeypatch, body, code=429):
        """Count the calls and the sleeping, with the network and the clock replaced."""
        log = {"calls": 0, "slept": 0.0}

        def call(*_a, **_k):
            log["calls"] += 1
            raise urllib.error.HTTPError("u", code, "err", {}, io.BytesIO(body.encode()))

        monkeypatch.setattr(llm.urllib.request, "urlopen", call)
        monkeypatch.setattr(llm.time, "sleep", lambda s: log.__setitem__("slept", log["slept"] + s))
        return log

    def test_a_used_up_daily_quota_is_not_retried_at_all(self, monkeypatch):
        log = self.attempts(monkeypatch, QUOTA_429)
        with pytest.raises(llm.LLMError):
            llm._attempt({}, "gemini-3.6-flash", 10, verbose=False)
        assert log["calls"] == 1, "it retried a quota that does not come back today"
        assert log["slept"] == 0.0

    def test_a_burst_limit_is_waited_out_for_exactly_as_long_as_asked(self, monkeypatch):
        log = self.attempts(monkeypatch, BURST_429)
        with pytest.raises(llm.LLMError):
            llm._attempt({}, "gemini-3.6-flash", 10, verbose=False)
        assert log["calls"] == llm.RETRIES
        assert log["slept"] == 3.0 * (llm.RETRIES - 1), "it should honour 3s, not guess 1+2+4"

    def test_a_wait_longer_than_we_will_sit_for_moves_on(self, monkeypatch):
        log = self.attempts(monkeypatch, '{"error":{"code":429},"retryDelay": "300s"}')
        with pytest.raises(llm.LLMError):
            llm._attempt({}, "gemini-3.6-flash", 10, verbose=False)
        assert log["calls"] == 1
        assert log["slept"] == 0.0

    def test_with_no_hint_it_still_backs_off_the_old_way(self, monkeypatch):
        log = self.attempts(monkeypatch, '{"error": {"code": 503}}', code=503)
        with pytest.raises(llm.LLMError):
            llm._attempt({}, "gemini-3.6-flash", 10, verbose=False)
        assert log["calls"] == llm.RETRIES
        assert log["slept"] == 1 + 2 + 4

    def test_the_advice_is_found_even_when_it_sits_late_in_the_body(self, monkeypatch):
        """The real bug this guards: the body was cut to 500 characters before being read.

        Google puts a long explanatory `message` first and `details` — the quota id and the
        retry delay — after it. Truncating early meant every 429 looked like one that came
        with no advice, so the retries went ahead against a quota that had no chance of
        clearing. Against the live API that was seven wasted seconds per model, twice.
        """
        padding = "Quota exceeded. " * 40  # comfortably past the old 500-character cut
        body = (
            '{"error": {"code": 429, "message": "'
            + padding
            + '", "details": [{"violations": [{"quotaId": '
            + '"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}, '
            + '{"retryDelay": "21s"}]}}'
        )
        assert body.index("quotaId") > 500, "this test is not reproducing the old cut"

        log = self.attempts(monkeypatch, body)
        with pytest.raises(llm.LLMError):
            llm._attempt({}, "gemini-3.6-flash", 10, verbose=False)
        assert log["calls"] == 1
        assert log["slept"] == 0.0

    def test_the_message_it_raises_stays_short(self, monkeypatch):
        # Reading the whole body is for understanding it; a wall of JSON in a report is not
        long_body = '{"error": {"code": 503, "message": "' + ("x" * 3000) + '"}}'
        self.attempts(monkeypatch, long_body, code=503)
        with pytest.raises(llm.LLMError) as caught:
            llm._attempt({}, "gemini-3.6-flash", 10, verbose=False)
        assert len(str(caught.value)) < llm.SHOWN + 60

    def test_the_daily_flag_survives_the_truncation(self, monkeypatch):
        # The message is cut for display and the quota id is at the end of it, so reading
        # the flag back out of the message would lose exactly the case it is there for
        padding = "Quota exceeded. " * 40
        body = (
            '{"error": {"code": 429, "message": "'
            + padding
            + '", "details": [{"violations": [{"quotaId": '
            + '"GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}}'
        )
        self.attempts(monkeypatch, body)
        with pytest.raises(llm.LLMError) as caught:
            llm._attempt({}, "gemini-3.6-flash", 10, verbose=False)
        assert caught.value.daily is True
        assert "PerDay" not in str(caught.value), "this test is not exercising the truncation"

    def test_an_ordinary_failure_is_not_flagged_daily(self, monkeypatch):
        self.attempts(monkeypatch, '{"error": {"code": 503}}', code=503)
        with pytest.raises(llm.LLMError) as caught:
            llm._attempt({}, "gemini-3.6-flash", 10, verbose=False)
        assert caught.value.daily is False

    def test_the_daily_case_still_reaches_the_fallback_model(self, monkeypatch):
        # Giving up on a model early must not mean giving up on the answer: the fallback
        # has a quota of its own
        tried: list = []

        def attempt(_body, m, _timeout, _verbose):
            tried.append(m)
            if len(tried) == 1:
                raise llm.LLMError(f"Gemini 429: {QUOTA_429}", status=429)
            return {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

        monkeypatch.setattr(llm, "_attempt", attempt)
        monkeypatch.setattr(llm, "model_name", lambda: "gemini-3.6-flash")
        monkeypatch.setattr(llm, "fallback_model", lambda: "gemini-3.5-flash")
        assert llm.text_of(llm.generate({}, verbose=False)) == "ok"
        assert tried == ["gemini-3.6-flash", "gemini-3.5-flash"]
