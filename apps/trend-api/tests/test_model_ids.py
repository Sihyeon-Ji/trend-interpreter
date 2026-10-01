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
    원작자 서버의 'gemma-local' 286건(09-29 23:58 사본)은 어느 모델이 썼는지 알 수 없었다(같은 시기 다른 표에는 12b·e4b·gpt-oss 가 섞여 있다).
    남긴 이름은 실제로 넘긴 모델과 같아야 한다 — 호출과 이름이 따로 놀면 기록이 거짓이 된다."""
    from trend_agents.interpreters import gemma_local, gemma_translate

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="자만추", lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.add_meaning(con, "t1", MeaningDraft(definition="자연스러운 만남을 추구한다는 뜻", origin="x", nuance="y", generations=["20s"],
                                           regions=["KR"], self_confidence=0.9), "verified_auto", [])
    monkeypatch.setattr(translate, "USE_LOCAL_GEMMA", True)
    monkeypatch.setattr(gemma_local, "is_available", lambda *a, **k: True)
    called = []

    def fake_translate(base, term, target, **k):
        called.append(k.get("model"))
        return MeaningText(definition=f"{term} ({target})", origin="x", nuance="y")

    monkeypatch.setattr(gemma_translate, "translate_meaning", fake_translate)

    assert translate.run(con)["translate"].count == 2
    assert called == [config.GEMMA_LOCAL_MODEL] * 2
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


def test_video_interpretation_records_the_model_that_answered(monkeypatch):
    """영상 해석은 gemini.py 를 거치지 않는다 — 기본 모델이 503 이면 실행 기록에는 실제로 답한 폴백 모델만 남는다."""
    from google.genai import errors

    from trend_agents.pipeline import interpret
    from trend_agents.schemas import ShortsVideo

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    db.upsert_videos(con, [ShortsVideo(video_id="v1", url="https://www.youtube.com/shorts/v1", title="t", channel="c", published_at=now,
                                       duration_sec=30, view_count=10, region=config.REGIONS_FOCUS[0], source="most_popular")])
    tried = []

    def fake_interpret(urls, model):
        tried.append(model)
        if model == config.GEMINI_MODEL:
            raise errors.APIError(503, {"error": {"message": "overloaded"}})
        return SimpleNamespace(items=[], dropped=0)

    monkeypatch.setattr(interpret, "interpret_shorts", fake_interpret)
    r = interpret.run(con, max_batches=1)["interpret"]
    assert r.status != "error", r.note
    assert tried == [config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL]
    assert _models(con, "interpret") == config.GEMINI_FALLBACK_MODEL


def test_grounded_research_records_the_model_that_answered(monkeypatch):
    """검색 grounding 조사도 gemini.py 를 거치지 않는다 — 먼저 부른 모델이 503 이면 실행 기록에는 실제로 답한 모델만 남는다."""
    from google.genai import errors

    from trend_agents.collectors import community, gdelt_context, namuwiki, naver_search, wiktionary
    from trend_agents.pipeline import research

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    term = Term(term_id="t1", canonical="자만추", lang="ko", status="researching", first_seen=now, last_seen=now)
    ds.upsert_term(con, term)
    tried = []

    def fake_research(name, model):
        tried.append(model)
        if model == config.GEMINI_FALLBACK_MODEL:
            raise errors.APIError(503, {"error": {"message": "overloaded"}})
        return MeaningDraft(definition="자연스러운 만남을 추구한다는 뜻", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                            self_confidence=0.9), [], "grounded notes"

    monkeypatch.setattr(research, "research_term", fake_research)
    monkeypatch.setattr(gemini, "GEMINI_SEARCH_GROUNDING", True)      # 무료 등급에서는 꺼 둔다(config) — 이 시험은 grounding 경로를 본다
    monkeypatch.setattr(research, "promote_candidates", lambda con, n: [term])
    monkeypatch.setattr(research, "due_for_recheck", lambda con, n: [])
    for name in ("web_evidence", "first_party_evidence", "_wikipedia_evidence"):      # 네트워크·DB 수집은 비워 둔다
        monkeypatch.setattr(research, name, lambda *a, **k: [])
    monkeypatch.setattr(research, "attach_media", lambda *a, **k: 0)
    monkeypatch.setattr(wiktionary, "lookup", lambda *a, **k: [])
    monkeypatch.setattr(namuwiki, "lookup", lambda *a, **k: [])
    monkeypatch.setattr(gdelt_context, "sentences", lambda *a, **k: [])
    monkeypatch.setattr(community, "gather", lambda *a, **k: ([], []))
    monkeypatch.setattr(naver_search, "gather", lambda *a, **k: ([], []))

    r = research.run(con)["research"]
    assert r.count == 1, r.note
    assert tried == [config.GEMINI_FALLBACK_MODEL, config.GEMINI_MODEL]     # 조사는 3.5 부터(영상 해석과 할당량을 나눈다)
    assert _models(con, "research") == config.GEMINI_MODEL
