"""테스트는 연결마다 임시 스키마(db.connect(":memory:"))를 쓴다. 세션 시작 때 이전에 남은 임시 스키마를 치운다."""
import pytest

from trend_agents.storage import db


@pytest.fixture(scope="session", autouse=True)
def _clean_ephemeral_schemas():
    db.drop_ephemeral_schemas(stale=True)
    yield
    db.drop_ephemeral_schemas()


@pytest.fixture(autouse=True)
def _fresh_model_chain(monkeypatch):
    """Gemini 모델 사슬의 프로세스 상태(503 으로 쉬는 모델·분당 간격)는 시험마다 비운다 — 앞 시험의 503 이 다음 시험의 첫 모델을 바꿨다."""
    from trend_agents.pipeline import gemini

    monkeypatch.setattr(gemini, "_busy", {})
    monkeypatch.setattr(gemini, "_last_call", {})


@pytest.fixture(autouse=True)
def _no_real_index(monkeypatch, tmp_path):
    """시험은 실제 위키 색인(data/index.db)·임베딩 서버를 쓰지 않는다 — 챗봇 시험이 색인을 미리 찾고 Gemini 로 다시 답해 회차마다 결과가 달랐다(트윈 10-06)."""
    from trend_agents.pipeline import doc_index, tools

    monkeypatch.setattr(doc_index, "INDEX_PATH", tmp_path / "no-index.db")
    monkeypatch.setattr(tools, "_INDEX", None)
