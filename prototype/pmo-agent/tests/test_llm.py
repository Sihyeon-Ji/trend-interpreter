"""llm.py tests — request assembly, retries and error handling, with no network.

A unit test never calls the real API. urlopen is replaced wholesale.

Run: python -m pytest tests/test_llm.py -q
"""

from __future__ import annotations

import io
import json
import unittest
import urllib.error

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
