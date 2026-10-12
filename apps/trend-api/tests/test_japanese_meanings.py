"""일본어 화면의 뜻(계획서 ktwoo-copy-flow-and-japanese-ui B §3). 일본어판은 로컬 Gemma 로만 만들고(Gemini 예산을 쓰지 않는다),
API 는 있으면 일본어판을, 없으면 원문과 '번역 없음' 표시(ja_pending)를 돌려준다. 승인 배치 게시도 일본어판을 받는다. 모델 없이."""
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from trend_agents.pipeline import dashboard, translate, views
from trend_agents.schemas import MeaningDraft, MeaningText, Term
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import publication_inputs as inputs
from trend_agents.storage import publications as pub
from trend_agents.storage import store as db


def _term(con, tid, name, lang, definition):
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", lifecycle="steady", first_seen=now, last_seen=now))
    ds.add_meaning(con, tid, MeaningDraft(definition=definition, origin="x", nuance="y", generations=["20s"], regions=["JP"],
                                          self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, tid, [("20s", "JP", now.isoformat(), 1.0)])


def test_japanese_is_translated_only_with_the_local_model_and_after_english_and_korean(monkeypatch):
    con = db.connect(":memory:")
    _term(con, "lv", "럭키비키", "ko", "나쁜 상황에서도 좋은 면을 찾는 태도.")
    calls = []
    monkeypatch.setattr(translate, "make_text", lambda _c, name, m, lang: calls.append(lang) or (MeaningText(definition=f"{lang} 뜻", origin="o", nuance="n"), "test"))

    monkeypatch.setattr(translate, "local_ready", lambda: False)
    translate.run(con)
    assert calls == ["en", "ko"]                               # 로컬 모델이 없으면 일본어판은 만들지 않는다
    monkeypatch.setattr(translate, "local_ready", lambda: True)
    translate.run(con)
    assert calls == ["en", "ko", "ja"]                         # 이미 있는 판은 건너뛰고 일본어만
    assert ds.get_translation(con, "lv", "ja").definition == "ja 뜻"


def test_japanese_never_falls_back_to_gemini(monkeypatch):
    monkeypatch.setattr(translate, "USE_LOCAL_GEMMA", False)
    monkeypatch.setattr(translate, "structured", lambda *a, **kw: pytest.fail("Gemini 를 불렀다"))
    m = SimpleNamespace(definition="뜻", expansion=None, origin="o", nuance="n")
    with pytest.raises(RuntimeError):
        translate.make_text(None, "럭키비키", m, "ja")


def test_cards_and_entries_carry_the_japanese_meaning_or_say_it_is_missing():
    con = db.connect(":memory:")
    _term(con, "lv", "럭키비키", "ko", "나쁜 상황에서도 좋은 면을 찾는 태도.")
    _term(con, "ok", "推し活", "ja", "好きなアイドルを応援する活動。")          # 원문 뜻이 이미 일본어
    dashboard.run(con)
    cards = {c.term_id: c for c in dashboard.cards(con, ["JP"])}
    assert cards["lv"].ja_pending and cards["lv"].gloss_ja == "나쁜 상황에서도 좋은 면을 찾는 태도."
    assert not cards["ok"].ja_pending and cards["ok"].gloss_ja == "好きなアイドルを応援する活動。"
    assert views.term_record(con, ds.get_term(con, "lv")).ja is None

    ds.set_translation(con, "lv", "ja", MeaningText(definition="悪い状況でも良い面を見つける態度。", origin="o", nuance="n"), "local:test")
    dashboard.run(con)
    card = {c.term_id: c for c in dashboard.cards(con, ["JP"])}["lv"]
    assert not card.ja_pending and card.gloss_ja == "悪い状況でも良い面を見つける態度。"
    assert views.term_record(con, ds.get_term(con, "lv")).ja.definition == "悪い状況でも良い面を見つける態度。"


def test_old_cached_cards_without_the_japanese_field_still_load():
    old = dashboard.KeywordCard.model_validate({
        "term_id": "x", "canonical": "x", "lang": "ko", "category": "slang", "gloss_ko": "뜻", "gloss_en": "meaning", "regions": ["KR"],
        "lifecycle": "steady", "weekly": [], "mentions_4w": 0, "search": [], "tone": {}, "evidences": []})
    assert old.gloss_ja == "" and old.ja_pending is False     # 화면은 빈 gloss_ja 를 '翻訳なし' 로 본다


def test_an_approved_batch_publishes_a_japanese_translation():
    con = db.connect(":memory:")
    ds.upsert_term(con, Term(term_id="t_one", canonical="t_one", status="verified"))
    ds.add_meaning(con, "t_one", MeaningDraft(definition="a documented published definition", origin="origin", nuance="nuance",
                                              generations=["20s"], regions=["KR"], self_confidence=0.9), "verified_auto", [])
    content = inputs.translation_inputs(con, ["t_one"], "fixed-snapshot", "a" * 64)
    run = {"input_sha256": hashlib.sha256(content).hexdigest(), "model": "gemma4:12b", "model_digest": "b" * 64, "gemma_translate_sha256": "c" * 64}
    row = json.loads(content.splitlines()[0])
    result = {"term_id": "t_one", "term": row["term"], "source": row["entry"], "expected_meaning_id": row["expected_meaning_id"],
              "derived_from_sha256": row["derived_from_sha256"], "ja": {"definition": "日本語の意味", "origin": "由来", "nuance": "ニュアンス"},
              "target": "ja", "error": None, **{k: run[k] for k in ("model", "model_digest", "gemma_translate_sha256", "input_sha256")}}
    out = (json.dumps(result) + "\n").encode()

    with pytest.raises(pub.PublicationError, match="invalid_translation_output"):
        inputs.pack_translations(content, out, run, "as-english")          # 영어판으로 싸면 영어 칸이 없다
    with pytest.raises(pub.PublicationError, match="invalid_translation_language"):
        inputs.pack_translations(content, out, run, "as-thai", lang="th")
    batch, _ = inputs.pack_translations(content, out, run, "translation-ja", lang="ja")
    assert list(batch.items[0].translations) == ["ja"]
    staged = pub.stage(con, batch)
    pub.review(con, batch.batch_id, staged["payload_sha256"], "reviewer", approve=True)
    pub.publish(con, batch.batch_id)
    assert ds.get_translation(con, "t_one", "ja").definition == "日本語の意味"
    assert ds.get_translation(con, "t_one", "en") is None
    con.close()


def test_producer_writes_the_target_language_and_will_not_resume_a_different_one(monkeypatch, tmp_path):
    from trend_agents.interpreters import gemma_translate

    spec = importlib.util.spec_from_file_location("translation_producer_ja", Path(__file__).resolve().parents[3] /
                                                  "models/kaggle/translate/translate_meanings.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    src, out = tmp_path / "input", tmp_path / "output"
    code = src / "trend_agents/interpreters/gemma_translate.py"
    code.parent.mkdir(parents=True)
    code.write_text("fixed prompt code")
    out.mkdir()
    source = {"term_id": "t_one", "term": "one", "entry": {"definition": "source", "origin": "o", "nuance": "n", "expansion": None},
              "expected_meaning_id": "m_one", "derived_from_sha256": "a" * 64}
    (src / "terms.jsonl").write_text(json.dumps(source) + "\n")
    targets = []
    monkeypatch.setattr(runner, "OUT", out)
    monkeypatch.setattr(runner, "TARGET", "ja")
    monkeypatch.setattr(runner, "find_input", lambda: src)
    monkeypatch.setattr(runner, "start_ollama", lambda: ("test-version", "b" * 64))
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="synthetic-gpu"))
    monkeypatch.setattr(gemma_translate, "translate_meaning", lambda base, term, target, **kw:
                        targets.append(target) or MeaningText(definition="日本語", origin="o", nuance="n"))
    original_path = runner.sys.path[:]
    try:
        runner.main()
    finally:
        runner.sys.path[:] = original_path
    result = json.loads((out / "translations.jsonl").read_text())
    assert targets == ["ja"] and result["ja"]["definition"] == "日本語" and result["target"] == "ja" and "en" not in result
    assert json.loads((out / "run.json").read_text())["target"] == "ja"

    monkeypatch.setattr(runner, "TARGET", "en")                 # 같은 결과 파일에 영어판을 이어 붙이지 않는다
    monkeypatch.setattr(runner, "start_ollama", lambda: pytest.fail("mixed resume started GPU"))
    with pytest.raises(SystemExit, match="translation_resume_source_conflict"):
        runner.main()
