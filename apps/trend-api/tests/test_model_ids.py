"""모델 ID 기록 (Plan 06 완료 기준 1) — 로컬 편집 결과와 단계 실행마다 실제로 부른 모델을 남긴다. 모델은 부르지 않는다."""
from datetime import datetime, timezone
from types import SimpleNamespace

from trend_agents import config
from trend_agents.pipeline import gemini, local_llm, translate
from trend_agents.pipeline.runs import stage
from trend_agents.schemas import MeaningDraft, MeaningText, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def _models(con, name: str):
    return con.execute("SELECT models FROM pipeline_runs WHERE stage=?", (name,)).fetchone()[0]


def test_local_translation_records_the_exact_model(monkeypatch):
    """로컬 Gemma 번역은 'gemma-local' 이 아니라 실제 모델 ID 로 남는다 — gemini.generate 의 local:<모델> 과 같은 꼴.
    원작자 서버의 'gemma-local' 278건은 어느 모델이 썼는지 알 수 없었다(같은 시기 다른 표에는 12b·e4b·gpt-oss 가 섞여 있다)."""
    from trend_agents.interpreters import gemma_local, gemma_translate

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="자만추", lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.add_meaning(con, "t1", MeaningDraft(definition="자연스러운 만남을 추구한다는 뜻", origin="x", nuance="y", generations=["20s"],
                                           regions=["KR"], self_confidence=0.9), "verified_auto", [])
    monkeypatch.setattr(translate, "USE_LOCAL_GEMMA", True)
    monkeypatch.setattr(gemma_local, "is_available", lambda *a, **k: True)
    monkeypatch.setattr(gemma_translate, "translate_meaning",
                        lambda base, term, target, **k: MeaningText(definition=f"{term} ({target})", origin="x", nuance="y"))

    assert translate.run(con)["translate"].count == 2
    want = f"local:{config.GEMMA_LOCAL_MODEL}"
    assert {m for (m,) in con.execute("SELECT model FROM translations").fetchall()} == {want}
    assert _models(con, "translate") == want


def test_each_run_records_the_models_it_called(monkeypatch):
    """단계 실행 기록(pipeline_runs.models)에 그 실행이 부른 모델이 남는다 — 로컬 Gemma·Gemini 모두. 부르지 않은 단계는 비고,
    단계 밖(이용자 요청)의 호출은 어느 실행에도 붙지 않는다."""
    con = db.connect(":memory:")
    monkeypatch.setattr(gemini, "local_ok", lambda: True)
    monkeypatch.setattr(local_llm, "structured", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(gemini, "client", lambda: SimpleNamespace(models=SimpleNamespace(
        generate_content=lambda model, contents, config: SimpleNamespace(parsed={"ok": True}, text="ok"))))

    with stage(con, "local") as r:
        gemini.structured(con, "prompt", dict)
        r.count = 1
    assert r.status == "ok", r.note                 # 단계는 예외를 삼킨다 — 기록이 비는 까닭이 예외가 아닌지 먼저 본다
    assert _models(con, "local") == f"local:{config.GEMMA_LOCAL_MODEL}"

    with stage(con, "both") as r:
        gemini.structured(con, "prompt", dict)
        gemini.generate(con, "prompt", allow_local=False)
        r.count = 1
    assert r.status == "ok", r.note
    assert _models(con, "both") == ",".join(sorted({f"local:{config.GEMMA_LOCAL_MODEL}", config.GEMINI_MODEL}))

    with stage(con, "idle") as r:
        r.count = 1
    assert _models(con, "idle") is None

    gemini.structured(con, "prompt", dict)          # 단계 밖 — 기록할 실행이 없다
    assert [m for (m,) in con.execute("SELECT models FROM pipeline_runs ORDER BY started_at").fetchall()] == [
        f"local:{config.GEMMA_LOCAL_MODEL}", ",".join(sorted({f"local:{config.GEMMA_LOCAL_MODEL}", config.GEMINI_MODEL})), None]
