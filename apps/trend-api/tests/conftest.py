"""테스트는 연결마다 임시 스키마(db.connect(":memory:"))를 쓴다. 세션 시작 때 이전에 남은 임시 스키마를 치운다."""
import pytest

from trend_agents.storage import db


@pytest.fixture(scope="session", autouse=True)
def _clean_ephemeral_schemas():
    db.drop_ephemeral_schemas(stale=True)
    yield
    db.drop_ephemeral_schemas()
