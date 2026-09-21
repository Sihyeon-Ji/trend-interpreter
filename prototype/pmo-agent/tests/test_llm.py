"""llm.py 테스트 — 네트워크 없이 요청 조립·재시도·오류 처리를 검증한다.

단위 테스트는 절대 실제 API 를 호출하지 않는다. urlopen 을 통째로 갈아끼운다.

실행: python -m unittest discover -s tests -v      (D:/echo-pmo 에서)
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
        json.dumps(payload or {"candidates": [{"content": {"parts": [{"text": "네"}]}}]}).encode()
    )


def http_error(code):
    return urllib.error.HTTPError(
        "u", code, "err", {}, io.BytesIO(json.dumps({"error": {"code": code}}).encode())
    )


class LLMTestCase(unittest.TestCase):
    """환경과 네트워크를 둘 다 격리한다."""

    env = {
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-3.6-flash",
        "LLM_BACKEND": "aistudio",
    }

    def setUp(self):
        self.calls = []
        self.keep_env, llm.env = llm.env, lambda k, d="": self.env.get(k, d)
        self.keep_open, self.keep_sleep = llm.urllib.request.urlopen, llm.time.sleep
        llm.time.sleep = lambda s: None  # 재시도 대기는 건너뛴다
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
    def test_aistudio_는_키를_URL에_싣는다(self):
        self.responses = [ok()]
        llm.generate(BODY)
        url = self.calls[0].full_url
        self.assertIn("generativelanguage.googleapis.com", url)
        self.assertIn("gemini-3.6-flash:generateContent", url)
        self.assertIn("key=test-key", url)

    def test_모델을_인자로_덮어쓸_수_있다(self):
        self.responses = [ok()]
        llm.generate(BODY, model="gemini-3.1-flash-lite")
        self.assertIn("gemini-3.1-flash-lite", self.calls[0].full_url)

    def test_키가_없으면_호출하지_않는다(self):
        self.env = {"GEMINI_API_KEY": ""}
        self.responses = []
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY)
        self.assertEqual(self.calls, [])

    def test_본문이_JSON으로_실린다(self):
        self.responses = [ok()]
        llm.generate(BODY)
        self.assertEqual(json.loads(self.calls[0].data), BODY)


class TestVertexBackend(LLMTestCase):
    env = {
        "LLM_BACKEND": "vertex",
        "GCP_PROJECT_ID": "echo-pmo-2026",
        "GCP_REGION": "asia-northeast3",
    }

    def test_프로젝트가_없으면_바로_알려준다(self):
        self.env = {"LLM_BACKEND": "vertex", "GCP_PROJECT_ID": ""}
        self.responses = []
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY)
        self.assertIn("GCP_PROJECT_ID", str(e.exception))

    def test_ADC_토큰을_헤더에_싣는다(self):
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
        self.assertNotIn("key=", req.full_url)  # 키가 URL 에 새지 않는다

    def test_백엔드_이름을_읽는다(self):
        self.assertEqual(llm.backend(), "vertex")


class TestRetry(LLMTestCase):
    """재시도 루프만 따로 본다 — 폴백을 꺼서 모델 하나에 대한 동작을 격리한다."""

    env = {
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-3.6-flash",
        "GEMINI_FALLBACK_MODEL": "",
        "LLM_BACKEND": "aistudio",
    }

    def test_과부하는_재시도한다(self):
        self.responses = [http_error(503), http_error(429), ok()]
        self.assertTrue(llm.generate(BODY, verbose=False))
        self.assertEqual(len(self.calls), 3)

    def test_재시도를_다_쓰면_오류를_올린다(self):
        self.responses = [http_error(503)] * llm.RETRIES
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(len(self.calls), llm.RETRIES)

    def test_코드_문제는_즉시_올린다(self):
        self.responses = [http_error(400)]
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY, verbose=False)
        self.assertEqual(len(self.calls), 1)  # 400 은 재시도해도 소용없다
        self.assertIn("400", str(e.exception))

    def test_오류_본문을_메시지에_담는다(self):
        self.responses = [http_error(404)]
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY, verbose=False)
        self.assertIn("error", str(e.exception))

    def test_네트워크_오류도_재시도한다(self):
        self.responses = [urllib.error.URLError("끊김"), ok()]
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

    def test_주모델이_계속_과부하면_대체모델로_넘어간다(self):
        self.responses = [http_error(503)] * llm.RETRIES + [ok()]
        self.assertTrue(llm.generate(BODY, verbose=False))
        called = self.models_called()
        self.assertEqual(called[0], "gemini-3.6-flash")
        self.assertEqual(called[-1], "gemini-3.5-flash")

    def test_설정_오류는_폴백하지_않는다(self):
        # 키가 없는 것은 모델을 바꿔도 같다. 예전에는 여기서도 '대체 모델로 넘어간다'고 알렸다.
        self.env = {**self.env, "GEMINI_API_KEY": ""}
        self.responses = []
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY, verbose=False)
        self.assertEqual(self.calls, [])
        self.assertIsNone(e.exception.status)

    def test_상태코드가_예외에_실린다(self):
        self.responses = [http_error(400)]
        with self.assertRaises(llm.LLMError) as e:
            llm.generate(BODY, verbose=False)
        self.assertEqual(e.exception.status, 400)

    def test_본문에_낀_숫자에_속지_않는다(self):
        # 응답 본문에 '503' 이 우연히 들어 있어도 400 은 폴백 대상이 아니다
        import io as _io
        import urllib.error as _ue

        err = _ue.HTTPError("u", 400, "bad", {}, _io.BytesIO(b'{"error":"token 503 invalid"}'))
        self.responses = [err]
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(len(self.calls), 1)

    def test_과부하가_아니면_모델을_바꾸지_않는다(self):
        self.responses = [http_error(400)]
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(set(self.models_called()), {"gemini-3.6-flash"})

    def test_폴백을_끄면_한_모델만_쓴다(self):
        self.env = {**self.env, "GEMINI_FALLBACK_MODEL": ""}
        self.responses = [http_error(503)] * llm.RETRIES
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(set(self.models_called()), {"gemini-3.6-flash"})

    def test_대체모델도_실패하면_오류를_올린다(self):
        self.responses = [http_error(503)] * (llm.RETRIES * 2)
        with self.assertRaises(llm.LLMError):
            llm.generate(BODY, verbose=False)
        self.assertEqual(len(self.calls), llm.RETRIES * 2)


class TestLogSafety(LLMTestCase):
    """안내 문구 출력이 실패해도 요청은 살아 있어야 한다 (Windows cp949 사고 재발 방지)."""

    def test_출력이_터져도_재시도가_계속된다(self):
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

    def test_로그_함수는_예외를_삼킨다(self):
        import builtins

        keep, builtins.print = (
            builtins.print,
            lambda *a, **k: (_ for _ in ()).throw(OSError("closed")),
        )
        try:
            llm._log("아무거나")
        finally:
            builtins.print = keep


class TestHelpers(LLMTestCase):
    def test_텍스트_파트를_이어붙인다(self):
        r = {"candidates": [{"content": {"parts": [{"text": "가"}, {"text": "나"}]}}]}
        self.assertEqual(llm.text_of(r), "가나")

    def test_빈_응답도_처리한다(self):
        self.assertEqual(llm.text_of({}), "")
        self.assertEqual(llm.parts_of({}), [])

    def test_파트를_그대로_돌려준다(self):
        r = {"candidates": [{"content": {"parts": [{"functionCall": {"name": "x"}}]}}]}
        self.assertEqual(llm.parts_of(r), [{"functionCall": {"name": "x"}}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
