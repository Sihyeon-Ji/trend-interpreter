"""09-15 백엔드 감사에서 고친 것: 근거 PK, 고아 엣지 정리, 밈 이름 동일성, 숫자꼴 단서."""
from datetime import datetime, timezone

import pytest

from trend_agents.pipeline.match import mentions, same_term
from trend_agents.schemas import Evidence
from trend_agents.storage import dictionary_store as ds
from trend_agents.storage import store as db


def ev(url="https://a.com/x", title="6-7 meme"):
    return Evidence(evidence_id=ds.new_id("e", url), kind="news", url=url, title=title, source_domain="a.com", observed_at=datetime.now(timezone.utc), excerpt=title)


def test_same_evidence_attaches_to_query_card_and_term():
    con = db.connect(":memory:")
    e = ev()
    assert ds.add_evidences(con, "q|6-7|US", [e]) == 1
    assert ds.add_evidences(con, "t_67", [e]) == 1  # 단일 PK 였다면 0 — 용어가 급증 근거를 잃었다
    assert [x.evidence_id for x in ds.list_evidences(con, "t_67")] == [e.evidence_id]
    assert ds.add_evidences(con, "t_67", [e]) == 0  # 같은 (근거, 용어) 는 중복 저장 안 함


def test_prune_dangling_edges_keeps_live_ones():
    con = db.connect(":memory:")
    e = ev()
    ds.add_evidences(con, "q|x|KR", [e])
    ds.add_edge(con, "query", "x|KR", "EVIDENCED_BY", "evidence", e.evidence_id)
    ds.add_edge(con, "query", "x|KR", "EVIDENCED_BY", "evidence", "e_ghost")
    ds.add_edge(con, "query", "x|KR", "TRIGGERED_BY", "actor", "누군가")
    assert ds.prune_dangling_edges(con) == 1
    assert sorted(r["dst_id"] for r in ds.edges_from(con, "query", "x|KR")) == [e.evidence_id, "누군가"]


def test_same_term_ignores_spacing_and_needs_no_cue():
    assert same_term("6-7", "6-7", ["6 7", "six seven"])
    assert same_term("Six Seven", "6-7", ["six seven"])
    assert same_term("aura  farming", "aura farming")
    assert not same_term("6-7 a.m.", "6-7")
    assert not same_term("", "6-7")


def test_numeric_term_cue_accepts_meaning_questions():
    assert mentions("What does 6-7 mean?", "6-7")
    assert mentions("6-7 뜻이 뭐예요", "6-7")
    assert not mentions("Game ends 6-7 in overtime", "6-7")  # 점수는 여전히 아님


def test_news_rss_uses_a_bounded_http_call(monkeypatch):
    """feedparser 에 URL 을 그대로 주면 타임아웃 없이 무한 대기한다(09-16 실측: 파이프라인 정지)."""
    import httpx

    from trend_agents.collectors import news_rss

    seen = {}

    class Resp:
        content = (b'<?xml version="1.0"?><rss version="2.0"><channel>'
                   b'<item><title>Port hit by ransomware</title><link>https://a.com/x</link>'
                   b'<pubDate>Mon, 15 Sep 2026 09:00:00 GMT</pubDate><source url="https://a.com">A News</source></item>'
                   b'</channel></rss>')

        def raise_for_status(self):
            return None

    def fake_get(url, **kw):
        seen.update(url=url, **kw)
        return Resp()

    monkeypatch.setattr(httpx, "get", fake_get)
    items = news_rss.fetch_news("KR", query="밈")

    assert seen["timeout"] == news_rss.TIMEOUT and seen["timeout"] > 0  # 무한 대기 금지
    assert "hl=ko" in seen["url"] and "q=%EB%B0%88" in seen["url"]
    assert [i.title for i in items] == ["Port hit by ransomware"]
    assert items[0].region == "KR" and items[0].query == "밈" and items[0].source == "A News"


def test_news_rss_breaker_stops_asking_a_dead_upstream(monkeypatch):
    """상류가 전부 503 이면(09-16 실측) 로케일·용어마다 15초씩 기다리지 않고 이번 실행은 건너뛴다."""
    import httpx

    from trend_agents.collectors import news_rss

    calls = {"n": 0}

    def dead(url, **kw):
        calls["n"] += 1
        raise httpx.HTTPStatusError("503", request=None, response=None)

    monkeypatch.setattr(httpx, "get", dead)
    news_rss.reset_breaker()
    for _ in range(news_rss.BREAKER_TRIP):
        with pytest.raises(httpx.HTTPStatusError):
            news_rss.fetch_news("KR")
    assert calls["n"] == news_rss.BREAKER_TRIP
    with pytest.raises(news_rss.Unavailable):  # 차단기가 내려간 뒤에는 요청 자체를 안 한다
        news_rss.fetch_news("US")
    assert calls["n"] == news_rss.BREAKER_TRIP
    news_rss.reset_breaker()
    with pytest.raises(httpx.HTTPStatusError):
        news_rss.fetch_news("US")
    assert calls["n"] == news_rss.BREAKER_TRIP + 1


def test_news_rss_breaker_resets_after_a_success(monkeypatch):
    import httpx

    from trend_agents.collectors import news_rss

    state = {"fail": True}

    class Ok:
        content = b'<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'

        def raise_for_status(self):
            return None

    def flaky(url, **kw):
        if state["fail"]:
            raise httpx.ConnectTimeout("slow")
        return Ok()

    monkeypatch.setattr(httpx, "get", flaky)
    news_rss.reset_breaker()
    for _ in range(news_rss.BREAKER_TRIP - 1):
        with pytest.raises(httpx.ConnectTimeout):
            news_rss.fetch_news("KR")
    state["fail"] = False
    assert news_rss.fetch_news("KR") == []  # 한 번 성공하면 카운터가 풀린다
    state["fail"] = True
    for _ in range(news_rss.BREAKER_TRIP - 1):
        with pytest.raises(httpx.ConnectTimeout):
            news_rss.fetch_news("KR")  # 차단기가 아직 안 내려갔다


def test_news_rss_bad_region_does_not_trip_the_upstream_breaker():
    from trend_agents.collectors import news_rss

    news_rss.reset_breaker()
    with pytest.raises(KeyError):
        news_rss.fetch_news("없는지역")
    assert news_rss._fails == 0


def test_collect_run_resets_the_news_breaker(monkeypatch):
    """차단기 초기화가 collect.run 안에 있어야 ADK 에이전트 경로(tools.run_collect)도 매번 다시 시도한다."""
    from trend_agents.collectors import news_rss
    from trend_agents.pipeline import collect

    con = db.connect(":memory:")
    monkeypatch.setattr(collect, "YOUTUBE_API_KEY", "")           # 네트워크 없이
    monkeypatch.setattr(collect.news_rss, "fetch_news", lambda *a, **k: [])
    monkeypatch.setattr(collect.gt, "trending_now", lambda *a, **k: [])
    monkeypatch.setattr(collect.gt, "latest_refresh_date", lambda *a, **k: None)  # BigQuery 안 탄다
    monkeypatch.setattr(collect.wikipedia_top, "top_articles", lambda *a, **k: [])
    news_rss._fails = news_rss.BREAKER_TRIP                        # 이전 실행에서 내려간 상태
    collect.run(con, mention_terms=0)
    assert news_rss._fails == 0


def test_interpretations_are_dropped_when_they_cannot_be_attributed():
    """모델이 url 을 지어내고 개수까지 다르면(09-16 실사고: 8개 요청 → 7개 응답, 'video1'…) 순서를 믿을 수 없다."""
    from trend_agents.interpreters.gemini_video import _attribute
    from trend_agents.schemas import ShortsInterpretation

    def it(url):
        return ShortsInterpretation(url=url, language="ko", summary="s", memes=[], target_generation=["all"],
                                    why_viral="w", explain_for_outsider="e", risk_flags=[])

    urls = ["https://youtube.com/shorts/aaa", "https://youtube.com/shorts/bbb", "https://youtube.com/shorts/ccc"]
    kept, dropped = _attribute([it("video1"), it("video2")], urls)   # 개수 불일치 + 가짜 id
    assert kept == [] and dropped == 2
    kept, dropped = _attribute([it("https://youtube.com/shorts/ccc"), it("example")], urls)  # 진짜 하나만 살린다
    assert [k.url for k in kept] == ["https://youtube.com/shorts/ccc"] and dropped == 1
    kept, dropped = _attribute([it("x"), it("y"), it("z")], urls)    # 개수가 같으면 순서가 대응
    assert [k.url for k in kept] == urls and dropped == 0


def test_password_is_hashed_and_checked_in_constant_time():
    from trend_agents import auth

    h = auth.hash_password("열려라 참깨")
    assert h.startswith("pbkdf2$200000$") and "열려라" not in h
    assert auth.verify_password("열려라 참깨", h)
    assert not auth.verify_password("열려라 참깨 ", h)
    assert not auth.verify_password("x", "형식이 아닌 값") and not auth.verify_password("x", "")


def test_sign_in_needs_a_configured_account(monkeypatch):
    import json

    from trend_agents import auth

    monkeypatch.delenv("ACCOUNTS", raising=False)
    assert auth.check_account("admin", "아무거나") is None  # 계정이 없으면 아무도 못 들어온다

    monkeypatch.setenv("ACCOUNTS", json.dumps([
        {"user": "kim", "hash": auth.hash_password("s3cret"), "reviewer": True},
        {"user": "lee", "hash": auth.hash_password("pw2")},
    ]))
    assert auth.check_account("kim", "s3cret") == auth.Account("kim", reviewer=True)
    assert auth.check_account("lee", "pw2") == auth.Account("lee", reviewer=False)
    assert auth.check_account("kim", "pw2") is None and auth.check_account("없는사람", "s3cret") is None
    assert auth.check_account("김검수", "s3cret") is None  # 한글 아이디도 500 이 아니라 그냥 통과 못 함
    monkeypatch.setenv("ACCOUNTS", "망가진 JSON")
    assert auth.check_account("kim", "s3cret") is None  # 형식이 깨져도 열리지 않는다


def test_only_reviewers_can_review(monkeypatch):
    import json

    from trend_agents import auth

    monkeypatch.setenv("ACCOUNTS", json.dumps([
        {"user": "kim", "hash": auth.hash_password("x"), "reviewer": True},
        {"user": "lee", "hash": auth.hash_password("y")},
    ]))
    assert auth.is_reviewer("kim") and not auth.is_reviewer("lee") and not auth.is_reviewer("없는사람")


def test_frontend_token_is_locked_by_default(monkeypatch):
    from trend_agents import auth

    monkeypatch.delenv("FRONTEND_API_TOKEN", raising=False)
    assert not auth.frontend_token_ok("무엇이든")  # 토큰 미설정 = 잠김
    monkeypatch.setenv("FRONTEND_API_TOKEN", "tok123")
    assert auth.frontend_token_ok("tok123")
    assert not auth.frontend_token_ok("tok124") and not auth.frontend_token_ok(None) and not auth.frontend_token_ok("")


def test_prefs_are_per_account():
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    assert ds.get_prefs(con, "lee") == {}          # 설정한 적 없으면 빈 값 → 설명이 중립으로 나간다
    ds.set_prefs(con, "lee", {"gen": "20s", "region": "KR"})
    ds.set_prefs(con, "kim", {"gen": "40s"})
    assert ds.get_prefs(con, "lee") == {"gen": "20s", "region": "KR"}
    assert ds.get_prefs(con, "kim") == {"gen": "40s"}
    ds.set_prefs(con, "lee", {})                    # 비우기
    assert ds.get_prefs(con, "lee") == {}


def test_stage_status_follows_the_latest_run_not_the_worst(monkeypatch):
    """고친 문제가 24시간 내내 '주의' 로 남지 않아야 한다(2026-09-16)."""
    from trend_agents.pipeline import views
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")

    def run(stage, count, status, note="", ago_min=0):
        rid = ds.run_start(con, stage)
        ds.run_finish(con, rid, count, status, note)
        if ago_min:
            # SQLite datetime() 은 'YYYY-MM-DD HH:MM:SS'(공백 구분)로 돌려주는데 저장은 ISO('T')다.
            # 문자열로 비교하는 질의에서 ' ' < 'T' 라 같은 날짜면 범위 밖으로 밀려난다 —
            # UTC 자정 직후에만 테스트가 깨지던 원인(2026-09-17). 파이썬에서 ISO 로 만들어 넣는다.
            from datetime import datetime, timedelta, timezone

            when = (datetime.now(timezone.utc) - timedelta(minutes=ago_min)).isoformat()
            con.execute("UPDATE pipeline_runs SET started_at=? WHERE run_id=?", (when, rid))
            con.commit()

    run("classify", 0, "error", "모델 형식 실패", ago_min=120)
    run("classify", 90, "ok", ago_min=5)          # 고친 뒤 정상
    run("collect.news", 0, "error", "상류 503", ago_min=10)   # 아직 실패 중
    by = {s.key: s for s in views.pipeline_stages(con)}

    assert by["classify"].status == "ok" and by["classify"].count_24h == 90
    assert "이전 1회 실패" in (by["classify"].note or "")     # 있었던 일은 감추지 않는다
    assert by["collect.news"].status == "warn" and "503" in (by["collect.news"].note or "")


def test_answer_drops_tool_name_citations():
    """작은 모델이 근거로 도구 이름을 적는다 — 사람에게는 뜻 없는 말이라 지운다(09-16 실측)."""
    from trend_agents.pipeline.ask import _tidy

    assert _tidy("AI slop 은 20대가 씁니다.\n\n(근거: term_usage)") == "AI slop 은 20대가 씁니다."
    assert _tidy("한국에서 뜹니다. (근거: country_trends 도구 결과)") == "한국에서 뜹니다."
    assert _tidy("근거는 3건입니다.") == "근거는 3건입니다."          # 진짜 근거 표기는 남긴다
    assert _tidy("표제어 저메추 (확인됨)") == "표제어 저메추 (확인됨)"  # 도구 이름이 없는 괄호는 건드리지 않는다


def test_broken_tool_call_in_text_is_recovered():
    """gemma4:e4b 가 도구 호출을 본문으로 흘린다(09-16 실측) — 그대로 화면에 내보내지 않고 복구해서 부른다."""
    from trend_agents.pipeline.ask import _leaked_call

    c = _leaked_call('search_terms{query:<|"|>AI 생성 캐릭터<|"|>}<tool_call|>')
    assert c is not None and c.name == "search_terms" and c.args == {"query": "AI 생성 캐릭터"}
    c2 = _leaked_call('lookup_term(term="저메추")')
    assert c2 is not None and c2.name == "lookup_term" and c2.args == {"term": "저메추"}
    assert _leaked_call("사전에 아직 없습니다.") is None          # 평범한 답은 건드리지 않는다
    assert _leaked_call("nosuchtool{x: 1}") is None              # 없는 도구 이름은 복구하지 않는다


def test_model_cannot_deny_what_the_tools_found(monkeypatch):
    """도구가 찾았는데 모델이 '사전에 없습니다' 라고 하면(09-16 실측) 찾은 것을 내보낸다 — 판정은 데이터가 한다."""
    from trend_agents.interpreters import local_chat
    from trend_agents.pipeline import ask, tools as T
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    monkeypatch.setattr(T, "run_tool", lambda ctx, n, a: (ctx.offer("Tung Tung Tung Sahur", "이탈리안 브레인로트 밈 캐릭터"), "찾음")[1])
    turns = iter([("", [local_chat.ToolCall(id="1", name="search_terms", args={"query": "나무 통 캐릭터"})]),
                  ("사전에 아직 없습니다.", [])])
    monkeypatch.setattr(local_chat, "chat_with_tools", lambda *a, **k: next(turns))
    ask.reset_breaker()
    out = ask.run(con, "그 나무 통 캐릭터 밈 뭐였지?")
    assert "Tung Tung Tung Sahur" in out.text and "없습니다" not in out.text


def test_japanese_screen_gets_japanese_answer_and_japanese_denials_are_caught(monkeypatch):
    """일본어 화면은 일본어로 답한다(10-14) — 지시문이 일본어 답을 시키고, 모델의 일본어 '없다' 도 찾은 것으로 덮는다."""
    from trend_agents.interpreters import local_chat
    from trend_agents.pipeline import ask, tools as T
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    seen = []
    monkeypatch.setattr(T, "run_tool", lambda ctx, n, a: (ctx.offer("Tung Tung Tung Sahur", "イタリアン・ブレインロットのキャラクター"), "찾음")[1])
    turns = iter([("", [local_chat.ToolCall(id="1", name="search_terms", args={"query": "木の樽のキャラ"})]),
                  ("辞書にはまだ載っていません。", [])])
    monkeypatch.setattr(local_chat, "chat_with_tools", lambda messages, tools: (seen.append(messages[0]["content"]), next(turns))[1])
    ask.reset_breaker()
    out = ask.run(con, "木の樽のキャラのミームって何だっけ？", "ja")
    assert "日本語で" in seen[0] and "한국어로, 군더더기" not in seen[0]
    assert out.text.startswith("お探しの言葉は「Tung Tung Tung Sahur」")
    assert ask.CAN_DO["ja"] and ask.MSG["ja"]["none"].endswith("。")
    assert ask._COUNT.sub(ask._COUNT_OUT["ja"], "（出典：推し活、근거 65건）") == "（出典：推し活、根拠65件）"
