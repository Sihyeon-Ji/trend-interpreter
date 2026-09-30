"""local_chat: JSON 추출과 스키마 재시도 — 네트워크 없이 _chat 을 바꿔 끼운다."""
import pytest
from pydantic import BaseModel

from trend_agents.interpreters import local_chat


class Out(BaseModel):
    detected_generation: str
    confidence: float


def test_extract_json_strips_fences_and_prose():
    assert local_chat.extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert local_chat.extract_json('결과입니다: {"a": {"b": [1, 2]}} 끝') == '{"a": {"b": [1, 2]}}'
    assert local_chat.extract_json("[1, 2]") == "[1, 2]"
    with pytest.raises(ValueError):
        local_chat.extract_json("JSON 없음")


def test_structured_retries_once_when_keys_are_wrong(monkeypatch):
    # Ollama 0.20 + gemma4:e4b 실측: 펜스로 감싸고 키 이름을 바꿔 낸다 → 한 번 다시 묻고 성공해야 한다
    answers = iter(['```json\n{"세대": "20s", "confidence": 0.9}\n```', '{"detected_generation": "20s", "confidence": 0.9}'])
    asked = []

    def fake_chat(prompt, temperature, model, json_schema=None, host=None):
        asked.append(prompt)
        return next(answers)

    monkeypatch.setattr(local_chat, "_chat", fake_chat)
    out = local_chat.structured("판정하라", Out)
    assert out.detected_generation == "20s"
    assert len(asked) == 2
    assert "detected_generation" in asked[0]  # 스키마가 프롬프트에 들어간다
    assert "맞지 않았다" in asked[1] and "맞지 않았다" not in asked[0]
    assert "ValidationError" not in asked[1] and "detected_generation" in asked[1]  # 오류 원문은 넣지 않고 모양만 다시


def test_structured_gives_up_after_two_failures(monkeypatch):
    monkeypatch.setattr(local_chat, "_chat", lambda *a, **k: '{"x": 1}')
    with pytest.raises(ValueError):
        local_chat.structured("판정하라", Out)


def test_extract_json_closes_unfinished_array():
    # gemma4:e4b 실측: 마지막 항목 뒤에서 ]} 를 닫지 않고 멈춘다
    cut = '{"items": [{"i": 0, "kind": "a"}, {"i": 1, "kind": "b"}'
    assert local_chat.extract_json(cut) == cut + "]}"
    # }}] 처럼 닫는 순서가 어긋난 경우(가장 잦은 실측)
    assert local_chat.extract_json('{"items": [{"i": 0}, {"i": 1, "lang": "en"}}]') == '{"items": [{"i": 0}, {"i": 1, "lang": "en"}]}'
    assert local_chat.extract_json('{"a": "열린 문자열') == '{"a": "열린 문자열"}'


def test_describe_schema_is_compact_with_enums():
    from typing import Literal
    from pydantic import TypeAdapter, create_model

    class Item(BaseModel):
        i: int
        kind: Literal["slang_meme", "song"]
        note: str | None = None

    W = create_model("W", items=(list[Item], ...))
    shape = local_chat.describe_schema(TypeAdapter(W).json_schema())
    assert shape == '{"items": [{"i": int, "kind": "slang_meme"|"song", "note": str|null}, ...]}'
    assert "$defs" not in shape and "title" not in shape


def test_structured_list_keeps_valid_items_and_drops_bad_ones(monkeypatch):
    # Ollama 0.34 + gemma4:e4b 실측: 15건 중 3건이 enum 위반 → 배치 전체가 죽지 않고 12건은 살아야 한다
    from typing import Literal
    from pydantic import TypeAdapter, create_model

    class Item(BaseModel):
        i: int
        kind: Literal["a", "b"]

    W = create_model("W", items=(list[Item], ...))
    monkeypatch.setattr(local_chat, "_chat", lambda *a, **k: '{"items": [{"i": 0, "kind": "a"}, {"i": 1, "kind": "zzz"}, {"i": 2, "kind": "b"}]}')
    out = local_chat.structured("분류", TypeAdapter(W))
    assert [x.i for x in out.items] == [0, 2]


def test_structured_list_all_bad_still_raises(monkeypatch):
    from typing import Literal
    from pydantic import TypeAdapter, create_model

    class Item(BaseModel):
        kind: Literal["a"]

    W = create_model("W", items=(list[Item], ...))
    monkeypatch.setattr(local_chat, "_chat", lambda *a, **k: '{"items": [{"kind": "x"}]}')
    with pytest.raises(ValueError):
        local_chat.structured("분류", TypeAdapter(W))


def test_sanitize_restores_byte_tokens():
    """gemma4:e4b 가 한글 한 글자를 <0xEB><0x9D><0x95> 로 흘린다(09-16 실측) — 화면에 깨져 보이지 않게 되돌린다."""
    assert local_chat.sanitize("눈에 <0xEB><0x9D><0x95>니다") == "눈에 띕니다"
    assert local_chat.sanitize("정상 문장") == "정상 문장"
    assert local_chat.sanitize("깨진 <0xFF> 조각") == "깨진  조각"   # 못 되돌리면 지운다
