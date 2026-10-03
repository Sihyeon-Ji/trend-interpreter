"""Vertex AI 유료 호출의 한 달 금액 상한(GEMINI_MONTHLY_USD). 예산 알림은 지출을 막지 않으므로, 응답의 실제 사용량으로 센 금액
장부가 상한에 닿으면 더 부르지 않는다. 호출 한 번의 최악 비용을 정하려고 출력 토큰에 상한을 건다. 네트워크 없이."""
from types import SimpleNamespace

import pytest

from trend_agents.pipeline import gemini
from trend_agents.storage import store as db

USAGE = SimpleNamespace(prompt_token_count=1000, tool_use_prompt_token_count=None, candidates_token_count=500,
                        thoughts_token_count=1000)


def fake(monkeypatch, seen, usage=USAGE):
    class Models:
        def generate_content(self, model, contents, config):
            seen.append((model, config.max_output_tokens))
            return SimpleNamespace(parsed={"ok": True}, usage_metadata=usage)

    monkeypatch.setattr(gemini, "client", lambda: SimpleNamespace(models=Models()))
    monkeypatch.setattr(gemini, "configured", lambda: True)
    monkeypatch.setattr(gemini, "local_ok", lambda: False)


def capped(monkeypatch, usd):
    monkeypatch.setattr(gemini, "GEMINI_MONTHLY_USD", usd)
    monkeypatch.setattr(gemini, "GEMINI_MODELS", ["gemini-3.8-flash", "gemini-3-flash-preview", "gemini-3.5-flash-lite"])


def test_actual_usage_is_charged_including_reasoning_tokens(monkeypatch):
    con = db.connect(":memory:")
    seen = []
    fake(monkeypatch, seen)
    capped(monkeypatch, 20)
    gemini.generate(con, "prompt", model="gemini-3.8-flash", request=True)
    # 입력 1,000 × $0.75 + (출력 500 + 추론 1,000) × $3.75, 100만 토큰당
    assert gemini.spent_usd(con) == pytest.approx((1000 * 0.75 + 1500 * 3.75) / 1_000_000)


def test_the_monthly_cap_stops_calls_before_they_are_sent(monkeypatch):
    con = db.connect(":memory:")
    seen = []
    fake(monkeypatch, seen)
    capped(monkeypatch, 20)
    gemini._bump(con, gemini._month_key(), 20 * gemini.MICRO_USD - gemini._reserve("gemini-3.5-flash-lite") + 1)
    with pytest.raises(gemini.BudgetExhausted):
        gemini.generate(con, "prompt", model="gemini-3.8-flash", request=True)
    assert seen == []


def test_unpriced_models_are_skipped_and_cheaper_ones_remain(monkeypatch):
    con = db.connect(":memory:")
    seen = []
    fake(monkeypatch, seen)
    capped(monkeypatch, 20)
    gemini._bump(con, gemini._month_key(), 20 * gemini.MICRO_USD - gemini._reserve("gemini-3.5-flash-lite"))
    _, used = gemini.generate(con, "prompt", model="gemini-3.8-flash", request=True)
    assert used == "gemini-3.5-flash-lite" and seen[0][0] == "gemini-3.5-flash-lite"


def test_output_tokens_are_bounded_unless_the_caller_asks_for_fewer(monkeypatch):
    con = db.connect(":memory:")
    seen = []
    fake(monkeypatch, seen)
    gemini.generate(con, "prompt", model="gemini-3.8-flash", request=True)
    gemini.generate(con, "prompt", gemini.types.GenerateContentConfig(max_output_tokens=100),
                    model="gemini-3.8-flash", request=True)
    assert [tokens for _, tokens in seen] == [gemini.GEMINI_MAX_OUTPUT_TOKENS, 100]


def test_without_usage_metadata_the_worst_case_is_charged_and_no_cap_means_no_block(monkeypatch):
    con = db.connect(":memory:")
    seen = []
    fake(monkeypatch, seen, usage=None)
    monkeypatch.setattr(gemini, "GEMINI_MONTHLY_USD", 0)
    gemini.generate(con, "prompt", model="gemini-3.8-flash", request=True)
    assert gemini._count(con, gemini._month_key()) == gemini._reserve("gemini-3.8-flash")
    assert gemini.affordable(con, "unpriced-model")
