"""규칙 코드는 결정론이라 테스트가 곧 명세다: 생애주기, 검증 게이트, 메시지 매칭."""
from datetime import datetime, timezone

from trend_agents.lifecycle import recheck_interval_days, stage
from trend_agents.pipeline.explain import match_terms, term_pattern
from trend_agents.pipeline.match import mentions, numeric_like
from trend_agents.schemas import Evidence, MeaningDraft, Term
from trend_agents.verification import gate


def ev(kind, domain, title, excerpt="", url=None):
    return Evidence(evidence_id=f"e_{domain}_{title[:8]}", kind=kind, url=url or f"https://{domain}/x", title=title, source_domain=domain,
                    observed_at=datetime.now(timezone.utc), excerpt=excerpt)


def test_lifecycle_stages():
    assert stage([], 0) == "unknown"
    assert stage([0, 0, 0, 0, 0], 10) == "dormant"
    assert stage([0, 0, 0, 0, 3], 1) == "emerging"
    assert stage([5, 5, 5, 5, 12], 20) == "rising"
    assert stage([5, 5, 20, 25, 24], 20) == "peak"
    assert stage([20, 20, 20, 20, 21], 20) == "steady"  # 평평한 곡선은 peak 가 아니다
    assert stage([30, 28, 20, 12, 8], 20) == "declining"
    assert recheck_interval_days("emerging") < recheck_interval_days("steady") < recheck_interval_days("dormant")


def test_gate_requires_anchored_independent_first_party_evidence():
    draft = MeaningDraft(definition="자연스러운 만남을 추구한다는 뜻", expansion="자연스러운 만남 추구", origin="2010년대 커뮤니티", nuance="캐주얼",
                         generations=["20s"], regions=["KR"], self_confidence=0.8)
    good = [ev("news", "mk.co.kr", "요즘 20대는 자만추, 자연스러운 만남 추구", "자만추는 자연스러운 만남 추구의 줄임말"),
            ev("web", "namu.wiki", "자만추 - 나무위키", "자만추: 자연스러운 만남 추구")]
    v, reasons = gate("자만추", draft, good, None)
    assert v == "verified_auto", reasons
    # 용어가 원문에 없는 근거는 세지 않는다 → 독립 출처 부족
    bad = [ev("web", "a.com", "무관한 글", "아무 말"), ev("news", "b.com", "다른 기사", "다른 내용")]
    v, reasons = gate("자만추", draft, bad, None)
    assert v == "unverified" and any("독립 출처" in r for r in reasons)
    # 풀이가 어떤 원문에도 없으면 환각 의심
    hallu = MeaningDraft(**{**draft.model_dump(), "expansion": "자동 만남 추적"})
    v, reasons = gate("자만추", hallu, good, None)
    assert v == "unverified" and any("환각" in r for r in reasons)


def test_term_pattern_boundaries():
    assert term_pattern("6-7").search("점수가 6-7 이래")
    assert not term_pattern("6-7").search("010-6-7-1234")
    assert not term_pattern("6-7").search("2026년 6 7월")
    assert not term_pattern("skibidi").search("Skibidiman")
    assert term_pattern("원영적 사고").search("원영적사고 가자")  # 한국어는 띄어쓰기 변형 허용
    assert term_pattern("La Peace").search("that's la peace fr")


def test_match_terms_orders_by_position():
    terms = [Term(term_id="a", canonical="자만추"), Term(term_id="b", canonical="저메추", aliases=["저메추좀"]), Term(term_id="c", canonical="6-7", lang="en")]
    got = match_terms("엄마 오늘 저메추 좀ㅋㅋ 나는 자만추 할래 6-7!", terms)
    assert [t.term_id for t in got] == ["b", "a", "c"]


def test_numeric_terms_need_a_meme_cue():
    assert numeric_like("6-7") and numeric_like("6 7") and not numeric_like("Remember November 2026")
    assert not mentions("SWAC Basketball Media Days Set for Oct. 6-7", "6-7", ["6 7", "six seven"])  # 날짜
    assert not mentions("5NEWS This Morning 6-7 a.m.", "6-7")  # 시간
    assert not mentions("이재명(1963년~)은 대한민국의 정치인", "6-7")
    assert mentions("The '6-7' meme can be annoying", "6-7")
    assert mentions("Skrilla six seven explained", "6-7", ["six seven"])  # 글자 별칭은 단서 없이도 참
    assert mentions("갓생 살기 시작", "갓생") and not mentions("Skibidiman", "skibidi")
    assert mentions("iPhone Duoは成功するか", "iPhone Duo") and mentions("BRICS峰会在新德里举行", "brics")  # 한자·가나 붙여쓰기


def test_gate_blocks_non_expressions():
    evs = [ev("news", "a.com", "aqi 100 in Jakarta", "aqi is high"), ev("news", "b.com", "aqi warning", "aqi"), ev("short", "youtube.com", "aqi", "aqi"),
           ev("wiki", "wikipedia.org", "AQI", "aqi is an index", url="https://en.wikipedia.org/wiki/AQI")]
    d = MeaningDraft(definition="Air quality index", origin="x", nuance="y", generations=["20s"], regions=["ID"], self_confidence=0.9, is_expression=False)
    v, reasons = gate("aqi", d, evs, None)
    assert v == "unverified" and any("사전 대상 아님" in r for r in reasons)
    assert gate("aqi", d.model_copy(update={"is_expression": True}), evs, None)[0] == "verified_auto"


# --- 위키백과 씨앗: 이름꼴 거르기와 '밈이 아님' 판정 (네트워크 없이) ---


def test_wiki_clean_title_keeps_meme_paren_drops_others():
    from trend_agents.collectors.wiki_memes import clean_title

    assert clean_title("6-7 (meme)") == "6-7"          # 밈 주석은 떼고 이름만
    assert clean_title("Guiana Brasileira (meme)") == "Guiana Brasileira"
    assert clean_title("Bombardiro Crocodilo") == "Bombardiro Crocodilo"
    # 짧은 영문 낱말·약어는 밈 문서라도 버린다. mentions() 가 아무 문장에나 걸려 엉뚱한 근거로
    # 게이트를 통과시키기 때문이다 (Ganpati Bappa Morya 자가확인 사고와 같은 종류). 필요하면 수동 등록.
    assert clean_title("NPC (밈)") is None
    # 괄호를 떼면 아무 문장에나 걸리는 말이 된다 → 통째로 버린다
    assert clean_title("Anxiety (Doechii song)") is None
    assert clean_title("Again (Fetty Wap song)") is None
    assert clean_title("List of Internet phenomena") is None
    assert clean_title("2024") is None
    assert clean_title("Yee") is None                  # 네 글자 이하 영문 한 낱말
    assert clean_title("Danh sách biểu tượng cảm xúc") is None   # 베트남어 목록 문서
    assert clean_title("網路流行語大賞") is None                  # 시상 행사는 표현이 아니다
    assert clean_title("傻眼貓咪") == "傻眼貓咪"


def test_unsafe_covers_target_region_chinese():
    """목표 지역(대만·홍콩)의 중국어 선정·욕설 표현도 사전·후보에서 거른다. 흔한 글자 하나로는 걸지 않는다."""
    from trend_agents.pipeline.match import unsafe

    assert unsafe("如果早知道男生也會被性侵") and unsafe("幹你娘")
    assert not unsafe("傻眼貓咪") and not unsafe("樹洞") and not unsafe("럭키비키")



def test_wiki_is_meme_rejects_songs_films_people_keeps_undescribed():
    from trend_agents.collectors.wiki_memes import is_meme

    # 분류가 이미 '인터넷 밈' 이라 했으므로 설명이 없으면 통과 — 새 문서가 여기 해당한다
    assert is_meme("") is True
    assert is_meme("2025 internet meme") is True
    assert is_meme("AI-generated character") is True
    assert is_meme("Slang term for developing charisma") is True
    assert is_meme("2025 studio album by Tyler, the Creator") is False
    assert is_meme("2025 video game") is False
    assert is_meme("British multinational airline company") is False
    assert is_meme("대한민국의 치킨 프렌차이즈 기업") is False
    assert is_meme("크레용팝의 노래") is False
    assert is_meme("米津玄師の楽曲") is False


def test_gate_accepts_wikipedia_as_first_party_but_needs_second_domain():
    """위키백과는 1차 근거로 인정하되, 영어판·한국어판 둘만으로는 '독립 출처 2개' 가 되지 않는다."""
    from datetime import datetime, timezone

    from trend_agents.schemas import Evidence, MeaningDraft
    from trend_agents.verification import gate

    def ev(eid: str, kind: str, domain: str, text: str) -> Evidence:
        return Evidence(evidence_id=eid, kind=kind, url=f"https://{domain}/{eid}", title=text,
                        source_domain=domain, observed_at=datetime.now(timezone.utc), excerpt=text)

    draft = MeaningDraft(definition="이탈리안 브레인로트 캐릭터", origin="unknown", nuance="장난스럽게 쓴다",
                         generations=["10s"], regions=["US"], self_confidence=0.9, is_expression=True)
    term = "Bombardiro Crocodilo"
    both_wiki = [ev("e1", "wiki", "wikipedia.org", f"{term} 는 AI 로 만든 캐릭터다"),
                 ev("e2", "wiki", "wikipedia.org", f"{term} is an AI-generated character")]
    _, reasons = gate(term, draft, both_wiki, None)
    assert not any("독립 출처" in r for r in reasons)      # 2026-09-30 사용자 결정: 참고 문서(위키)가 있으면 그것만으로 싣는다

    v, reasons = gate(term, draft, both_wiki + [ev("e3", "community", "bsky.app", f"{term} 진짜 웃김")], None)
    assert reasons == [] and v == "verified_auto"          # 1차 근거(위키) + 다른 출처 → 통과


def test_gate_blocks_model_web_hallucination_not_search_noise():
    """검색 잡음은 셈에서 빠질 뿐이지만, 모델이 근거라고 든 웹 링크에 용어가 없으면 환각으로 막는다."""
    from datetime import datetime, timezone

    from trend_agents.schemas import Evidence, MeaningDraft
    from trend_agents.verification import gate

    def ev(eid: str, kind: str, domain: str, text: str) -> Evidence:
        return Evidence(evidence_id=eid, kind=kind, url=f"https://{domain}/{eid}", title=text,
                        source_domain=domain, observed_at=datetime.now(timezone.utc), excerpt=text)

    term = "Tung Tung Tung Sahur"
    draft = MeaningDraft(definition="인도네시아에서 나온 AI 캐릭터", origin="unknown", nuance="장난스럽게",
                         generations=["10s"], regions=["ID"], self_confidence=0.9, is_expression=True)
    solid = [ev("e1", "wiki", "wikipedia.org", f"{term} is an AI-generated character"),
             ev("e2", "community", "bsky.app", f"{term} 너무 웃겨")]

    # 용어가 없는 커뮤니티 검색 결과가 섞여도 통과를 막지 않는다
    v, reasons = gate(term, draft, solid + [ev("e3", "community", "reddit.com", "관련 없는 잡담")], None)
    assert reasons == [] and v == "verified_auto"

    # 모델이 근거라며 내놓은 웹 링크에 용어가 없으면 막는다
    _, reasons = gate(term, draft, solid + [ev("e4", "web", "example.com", "전혀 다른 내용")], None)
    assert any("환각" in r for r in reasons)


def test_ask_drops_sentences_claiming_terms_that_do_not_exist():
    """사전에 없는 표제어를 '있다' 고 말하는 문장은 지운다 (인용 제품에서 지어내기는 치명적)."""
    from trend_agents.pipeline.ask import _drop_invented
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    q = "에스프레쏘 어쌔씨노 이런건 뭐야?"
    text = ("'에스프레쏘 어쌔씨노'는 사전에 없습니다. 대신 같은 계열의 표제어로는 'Espresso'가 있으며 참고하세요. "
            "이탈리안 브레인로트 계열입니다.")
    got = _drop_invented(con, text, q)
    assert "Espresso'가 있으며" not in got          # 없는 표제어를 있다고 한 문장은 사라진다
    assert "사전에 없습니다" in got                  # 사용자가 말한 이름을 되풀이한 문장은 남는다
    assert "이탈리안 브레인로트 계열입니다" in got     # 표제어를 주장하지 않는 문장도 남는다


def _seed(con, names, lang="en"):
    """표제어와 쓸 만한 뜻을 함께 넣는다 — 도구는 뜻이 없는 항목을 내놓지 않는다(usable)."""
    from datetime import datetime, timezone

    from trend_agents.schemas import MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds

    now = datetime.now(timezone.utc)
    for name in names:
        tid = ds.new_id("t", name)
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", category="meme",
                                 first_seen=now, last_seen=now))
        ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 를 가리키는 인터넷 표현이다.", origin="unknown",
                                              nuance="장난스럽게 쓴다", generations=["10s"], regions=["US"],
                                              self_confidence=0.9), "verified_auto", [])

def test_fuzzy_find_bridges_transliteration_spelling_gaps():
    """로마자 표기는 한두 글자씩 어긋난다. 그래도 같은 표제어를 찾아야 하고, 없는 말은 없다고 해야 한다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline.tools import _fuzzy_find
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    _seed(con, ("Tralalero Tralala", "Hawk tuah"))

    assert _fuzzy_find(con, "Tralalarelo Tralalala").canonical == "Tralalero Tralala"   # 모델이 적은 로마자
    assert _fuzzy_find(con, "Tralalero Tralla").canonical == "Tralalero Tralala"        # 사람이 친 오타
    assert _fuzzy_find(con, "Hawk Tua").canonical == "Hawk tuah"
    assert _fuzzy_find(con, "전혀 다른 말입니다") is None
    assert _fuzzy_find(con, "abc") is None                                              # 너무 짧으면 보지 않는다


def test_ask_back_pattern_is_replaced_by_what_was_found():
    """찾아 놓고 '보여드릴까요?' 하고 되묻지 않는다 — 사용자가 지적한 버릇."""
    from trend_agents.pipeline.ask import _ASKS_BACK, _DENIES

    assert _ASKS_BACK.search("이 계열의 표제어들을 보여드릴까요?")
    assert _ASKS_BACK.search("어떤 단어에 대해 비슷한 것을 찾고 싶으신가요? 말씀해 주세요.")
    assert not _ASKS_BACK.search("Tralalero Tralala 는 이탈리안 브레인로트의 첫 사례로 꼽힌다.")
    assert _DENIES.search("사전에 아직 없습니다")


def test_list_terms_category_alias_and_unknown_value():
    """모델이 넘기는 분류 이름(slang_meme, '유행어')을 실제 분류로 맞춘다. 모르는 값이면 거르지 않는다."""
    from trend_agents.pipeline.tools import _categories

    assert _categories("slang_meme") == ("slang", "meme")
    assert _categories("유행어") == ("slang",)
    assert _categories("meme") == ("meme",)
    assert _categories("무슨분류") == ()      # 모르는 값 → 필터 없음 (빈 목록을 내지 않는다)


def test_list_args_reads_generation_and_region_from_question():
    """'20대가 쓰는 말', '한국 유행어' 에서 조건을 읽어 되묻지 않고 바로 목록을 뽑는다."""
    from trend_agents.pipeline.ask import _list_args

    assert _list_args("20대가 쓰는 말 정리해줘") == {"generation": "20s"}
    assert _list_args("한국에서 요즘 쓰는 유행어") == {"region": "KR"}
    assert _list_args("일본 10대가 쓰는 밈") == {"generation": "10s", "region": "JP"}
    assert _list_args("요즘 밈 알려줘") == {}


def test_tool_arg_cleaner_handles_model_argument_leak():
    """작은 모델이 인자를 한 값에 몰아 넣는다 — 따옴표 뒤는 버리고 첫 값만 쓴다."""
    from trend_agents.pipeline.tools import _arg

    assert _arg({"category": "slang_meme', region='KR"}, "category") == "slang_meme"
    assert _arg({"region": "KR"}, "region") == "KR"
    assert _arg({"generation": ""}, "generation") == ""


def test_same_family_offers_entries_sharing_a_name_word():
    """이름이 정확히 없어도 낱말이 겹치는 표제어를 같은 계열로 내놓는다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline.tools import _same_family
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    _seed(con, ("Cappuccino Assassino", "Ballerina Cappuccina", "Hawk tuah"))

    got = [t.canonical for t in _same_family(con, "Espresso Assassino")]
    assert "Cappuccino Assassino" in got
    assert "Hawk tuah" not in got
    assert _same_family(con, "abc de") == []      # 짧은 낱말만 있으면 보지 않는다


def test_tidy_removes_tool_guardrail_text_from_answer():
    """도구가 모델에게 준 지시문이 사용자 답에 섞여 나오지 않는다."""
    from trend_agents.pipeline.ask import _tidy

    got = _tidy("같은 계열로는 'Cappuccino Assassino'가 있습니다. 이 목록에 있는 이름만 말하셔야 합니다.")
    assert "Cappuccino Assassino" in got
    assert "목록에 있는 이름만" not in got
    assert _tidy("사전에 없습니다. 다른 이름을 지어내지 마라.").startswith("사전에 없습니다")


def test_pick_video_rejects_titles_that_only_use_the_meme_as_a_hook():
    """밈을 소재로만 쓴 영상은 대표 영상이 아니다 — 제목 앞부분에 나와야 받는다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline.research import _pick_video
    from trend_agents.schemas import ShortsVideo, Term

    def v(vid: str, title: str) -> ShortsVideo:
        return ShortsVideo(video_id=vid, url=f"https://www.youtube.com/watch?v={vid}", title=title, channel="c",
                           region="US", source="search", published_at=datetime.now(timezone.utc),
                           duration_sec=30, view_count=1)

    term = Term(term_id="t1", canonical="Italian brainrot", lang="en", status="verified", category="meme",
                first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc))

    hook = v("a", "Can Starbucks Spell Italian Brainrot | Ep 7")
    ontopic = v("b", "Italian Brainrot characters explained")
    assert _pick_video([hook], term) is None                      # 소재로만 쓴 영상은 받지 않는다
    assert _pick_video([hook, ontopic], term).video_id == "b"     # 앞에 나오는 쪽을 고른다
    assert _pick_video([v("c", "완전 다른 영상")], term) is None


def test_expansion_is_only_an_abbreviation_expansion():
    """expansion 은 줄임말 풀이 자리다. 정의 문장이 들어오면 버린다."""
    import re

    def keep(expansion: str) -> bool:
        return not (len(expansion) > 40 or len(expansion.split()) > 8 or "." in expansion[:-1])

    assert keep("자연스러운 만남 추구")
    assert keep("Get Ready With Me")
    assert not keep("A series of Internet memes centered around surreal AI-generated pictures and videos.")
    assert not keep("AI가 생성한, 초현실적이고 부조리한 이미지들로 구성된 인터넷 밈 시리즈로, 종종 가짜 이탈리아어 이름이 붙는다")
    assert re.search(r"\w", "자연스러운 만남 추구")


def test_gate_rejects_empty_or_tautological_definition():
    """근거가 아무리 튼튼해도 뜻이 비었거나 표제어를 도로 옮겨 적었으면 사전에 올리지 않는다."""
    from datetime import datetime, timezone

    from trend_agents.schemas import Evidence, MeaningDraft
    from trend_agents.verification import gate

    def ev(eid: str, kind: str, domain: str, text: str) -> Evidence:
        return Evidence(evidence_id=eid, kind=kind, url=f"https://{domain}/{eid}", title=text,
                        source_domain=domain, observed_at=datetime.now(timezone.utc), excerpt=text)

    term = "Chill Guy"
    solid = [ev("e1", "wiki", "wikipedia.org", f"{term} is a digital artwork and Internet meme"),
             ev("e2", "community", "bsky.app", f"{term} 진짜 웃김")]

    def draft(d: str) -> MeaningDraft:
        return MeaningDraft(definition=d, origin="unknown", nuance="장난스럽게", generations=["10s"], regions=["US"],
                            self_confidence=0.9, is_expression=True)

    _, reasons = gate(term, draft(""), solid, None)
    assert any("뜻이 비었" in r for r in reasons)
    _, reasons = gate(term, draft("Chill Guy"), solid, None)
    assert any("뜻이 비었" in r for r in reasons)
    v, reasons = gate(term, draft("느긋한 표정의 개 캐릭터. 무심한 태도를 흉내 낼 때 쓴다."), solid, None)
    assert reasons == [] and v == "verified_auto"


def test_translation_target_language_check():
    """작은 모델이 입력을 그대로 돌려보내는 일이 잦다 — 대상 언어 글자가 있는지 본다."""
    from trend_agents.interpreters.gemma_translate import _in_target

    assert _in_target("오타쿠에게 상냥한 갸루", "ko")
    assert not _in_target("おたくに対して優しく接するギャル", "ko")   # 번역 안 됨
    assert _in_target("A chill dog character", "en")
    assert _in_target("インターネット・ミーム", "ja")


def test_hunt_rejects_question_fragments_and_category_words():
    """못 답한 질문에서 뽑은 말이 표제어가 될 자격이 있는지 코드가 가른다."""
    from trend_agents.pipeline.hunt import _GENERIC_TOKEN, _LIST_ASK, _PREDICATE, _is_mash

    # 목록을 달라는 질문은 표제어 수요가 아니다
    assert _LIST_ASK.search("20대가 쓰는 말 정리해줘")
    assert _LIST_ASK.search("요즘 일본에서 뭐가 떠?")
    assert not _LIST_ASK.search("에스프레쏘 어쌔씨노 이런건 뭐야?")

    # 갈래 낱말·서술부가 섞인 것은 이름이 아니다
    assert _GENERIC_TOKEN.search("최신 밈들")
    assert _GENERIC_TOKEN.search("AI생성으로 만든 캐릭터")
    assert _PREDICATE.search("20대가 쓰는 말")
    assert not _GENERIC_TOKEN.search("Espresso Assassino")
    assert not _PREDICATE.search("싹싹김치")

    assert _is_mash("asdfgh") and _is_mash("zxcvbn")
    assert not _is_mash("skibidi")


def test_live_lookup_keeps_only_snippets_that_contain_the_term():
    """실시간으로 찾아온 글도 그 말이 실제로 들어 있어야 쓴다 — 사전과 같은 앵커 규칙."""
    from datetime import datetime, timezone

    from trend_agents.pipeline.live import MAX_SNIPPETS
    from trend_agents.pipeline.match import mentions
    from trend_agents.schemas import Evidence

    def ev(text: str) -> Evidence:
        return Evidence(evidence_id="e1", kind="wiki", url="https://en.wikipedia.org/wiki/x", title=text,
                        source_domain="wikipedia.org", observed_at=datetime.now(timezone.utc), excerpt=text)

    term = "delulu"
    hit = ev("delulu is short for delusional")
    miss = ev("완전히 다른 이야기입니다")
    keep = [e for e in (hit, miss) if mentions(f"{e.title} {e.excerpt}", term)][:MAX_SNIPPETS]
    assert len(keep) == 1 and keep[0] is hit


def test_tidy_strips_markdown_emphasis():
    """화면은 평문이라 **굵게** 가 별표 그대로 보인다 — 떼고 내보낸다."""
    from trend_agents.pipeline.ask import _tidy

    assert _tidy("이들은 **특정 감정**을 표현합니다.") == "이들은 특정 감정을 표현합니다."
    assert _tidy("__밑줄__도 뗀다") == "밑줄도 뗀다"
    assert _tidy("2*3 은 곱셈이라 두지 않는다") == "2*3 은 곱셈이라 두지 않는다"


def test_one_word_question_is_detected_even_without_a_tool_call():
    """'6-7이 뭐야?' 처럼 한 낱말을 물으면, 모델이 엉뚱한 도구를 불러도 그 말을 못 찾았다고 적어 둔다."""
    from trend_agents.pipeline.ask import _asked_word

    assert _asked_word("6-7이 뭐야?") == "6-7"
    assert _asked_word("delulu가 뭐야?") == "delulu"
    assert _asked_word("럭키비키 뜻이 뭐야?") == "럭키비키"
    assert _asked_word("20대가 쓰는 말 왜 떴는지 알려줘") == ""   # 목록 질문은 아니다
    assert _asked_word("한국 최신 밈들 알려줘") == ""


def test_asks_back_covers_the_common_ways_of_asking_back():
    """되묻기 표현은 여러 꼴이다. 한 가지만 막으면 모델이 다른 꼴로 되묻는다."""
    from trend_agents.pipeline.ask import _ASKS_BACK

    for q in ("이 계열의 표제어들을 보여드릴까요?",
              "어떤 분야의 유행어 목록을 원하시나요? (예: slang_meme)",
              "어떤 말에 대해 알고 싶으신가요?",
              "구체적인 단어를 말씀해주시면 알려드릴 수 있습니다.",
              "무엇을 찾으시나요?",
              "slang_meme 카테고리로 20대가 쓰는 말 목록을 보여드릴 수 있습니다."):
        assert _ASKS_BACK.search(q), q
    for q in ("럭키비키는 나쁜 상황에서도 좋게 보는 태도를 뜻합니다.",
              "20대가 쓰는 말 12개입니다."):
        assert not _ASKS_BACK.search(q), q


def test_internal_tool_names_never_reach_the_user():
    """도구 이름·내부 구조는 이용자 화면에 낼 내용이 아니다 (CLAUDE.md)."""
    from trend_agents.pipeline.ask import CAN_DO, _META_ASK, _TOOL_LIST

    for q in ("너가 사용 가능한 도구들", "쓸 수 있는 기능 알려줘", "넌 뭘 할 수 있어?", "what tools do you have"):
        assert _META_ASK.search(q), q
    assert not _META_ASK.search("럭키비키 뜻이 뭐야?")

    leaked = "lookup_term 으로 찾고 search_terms 로 목록을 봅니다"
    assert len(set(_TOOL_LIST.findall(leaked))) >= 2
    assert "lookup_term" not in CAN_DO["ko"] and "lookup_term" not in CAN_DO["en"]


def test_recency_stage_uses_only_latest_usage_not_shape():
    """조사 근거로는 모양(오름·정점)을 말하지 않는다 — 마지막으로 쓰인 때만 본다(Plan 02)."""
    from datetime import datetime, timedelta, timezone

    from trend_agents.lifecycle import recency_stage

    now = datetime(2026, 9, 28, tzinfo=timezone.utc)
    assert recency_stage(None, now) == "unknown"
    assert recency_stage(now - timedelta(days=3), now) == "steady"
    assert recency_stage(now - timedelta(days=30), now) == "declining"
    assert recency_stage(now - timedelta(days=90), now) == "dormant"


def test_diffusion_stage_rules():
    """확산 단계는 출처 종류와 생애주기 규칙으로만 정한다(Plan 02)."""
    from trend_agents.lifecycle import diffusion

    assert diffusion({"community": 5}, "steady") == "underground"
    assert diffusion({"community": 5, "documented": 1}, "steady") is None   # 문서가 있으면 이미 자리 잡은 말 — 태동이 아니다
    assert diffusion({"community": 5, "short": 1}, "rising") == "spreading"
    assert diffusion({"news": 3, "community": 2}, "steady") == "mainstream"
    assert diffusion({"news": 1}, "declining") == "fading"
    assert diffusion({"news": 1}, "steady") is None          # 뉴스 한 건으로는 주류라 할 수 없다
    assert diffusion({}, "unknown") is None


def test_meaning_draft_drops_decades_and_blank_regions():
    """모델이 세대 자리에 연대('90s')를, 나라 자리에 빈 문자열을 넣어도 조사가 죽지 않고 그 값만 버린다 (2026-09-28)."""
    from trend_agents.schemas import MeaningDraft

    d = MeaningDraft.model_validate({"definition": "뜻", "origin": "유래", "nuance": "뉘앙스", "generations": ["90s", "20s", "2000s"],
                                     "regions": ["", " jp", "KOR", "GLOBAL", "kr", "KR"], "self_confidence": 0.5})
    assert d.generations == ["20s"]
    assert d.regions == ["JP", "GLOBAL", "KR"]


def test_failed_research_waits_for_the_recheck_interval(monkeypatch):
    """조사가 실패한 용어는 기록을 남겨 다음 실행에 다시 맨 앞에 잡히지 않는다 — 같은 세 용어가 이틀 동안 칸을 차지했다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import research
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="Temple fade", lang="en", status="researching", first_seen=now, last_seen=now))

    def boom(con, term):
        raise ValueError("형식 실패")

    monkeypatch.setattr(research, "research_one", boom)
    monkeypatch.setattr(research, "promote_candidates", lambda con, n: [])
    monkeypatch.setattr(research, "local_ok", lambda: True)
    research.run(con)
    assert ds.get_term(con, "t1").status == "needs_review"
    assert ds.last_researched(con, "t1") is not None
    assert [t.term_id for t in research.due_for_recheck(con, 10)] == []
    assert not any(u.get("term_id") == "t1" and u["kind"] == "recheck" for u in ds.recent_updates(con, hours=1))


def test_promotion_puts_trend_signals_before_namuwiki_backfill():
    """나무위키 분류(오래된 한국어 말 채우기)가 대만 위키·쇼츠 후보를 막지 않는다 — 뒤에 두고 한 번에 절반까지만(2026-09-29 검토)."""
    from trend_agents.pipeline.research import promote_candidates
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    for k in range(20):
        ds.upsert_candidate(con, f"나무말{k}", "ko", "KR", "namu", note="kind=slang namu=유행어")
    for name in ("傻眼貓咪", "山道猴子的一生"):
        ds.upsert_candidate(con, name, "zh", "TW", "wiki", note="kind=meme wiki=x")
    ds.upsert_candidate(con, "Tung Sahur", "en", "ID", "shorts", note="kind=meme")
    ds.upsert_candidate(con, "Tung Sahur", "en", "ID", "shorts", note="kind=meme")
    got = [t.canonical for t in promote_candidates(con, 8)]
    assert set(got[:3]) == {"傻眼貓咪", "山道猴子的一生", "Tung Sahur"}           # 위키·쇼츠가 먼저
    assert sum(1 for g in got if g.startswith("나무말")) == 4                     # 8칸의 절반까지


def test_model_only_reasons_do_not_close_documented_slang():
    """모델의 자기 판단(is_expression=false 등)만으로는 문서가 있는 말을 사람 큐에서 빼지 않는다. 뜻이 빈 것은 규칙이라 닫는다."""
    from trend_agents.pipeline.research import needs_human

    model_only = ["표현이 아니라 상품·기관·인물·일반 단어로 판단됨 — 사전 대상 아님"]
    assert not needs_human(model_only)                        # 문서가 없으면 닫는다(예전 그대로)
    assert needs_human(model_only, documented=True)           # 나무위키·위키백과 문서가 있으면 사람이 본다
    assert not needs_human(["뜻이 비었거나 표제어를 그대로 옮겨 적음"], documented=True)


def test_namuwiki_ranking_is_not_cited_as_google_trends():
    """나무위키 실시간 검색어를 'Google Trends' 로 적으면 한 사이트가 독립 출처 둘로 세졌다."""
    from datetime import date

    from trend_agents.pipeline.research import first_party_evidence
    from trend_agents.schemas import TrendQuery
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    ds.upsert_trend_queries(con, [TrendQuery(term="럭키비키", region="KR", rank=1, source="namu_rank", date=date.today())])
    ev = [e for e in first_party_evidence(con, "럭키비키", []) if e.kind == "datalab"]
    assert ev and ev[0].source_domain == "namu.wiki" and "Google" not in ev[0].title


def test_unsafe_does_not_fire_inside_other_words():
    """욕설 글자가 다른 낱말 안에 든 것은 걸지 않는다 — 'Koshitantan'·'시발점'·'남자지만' 이 '사용 자제' 가 됐다(2026-09-29)."""
    from trend_agents.pipeline.match import unsafe

    for w in ("Shikanoko Nokonoko Koshitantan", "시발점", "쳐다보지 마", "남자지만", "자지러지게", "gozaimashita"):
        assert not unsafe(w), w
    for w in ("씨발", "인실좆", "아헤가오", "motherfucker", "Roblox Shitpost Animation", "bullshit", "如果早知道男生也會被性侵"):
        assert unsafe(w), w


def test_dashboard_numbers_follow_the_chosen_region():
    """지역을 바꾸면 수치도 그 지역 것만 (Plan 04 완료 기준). 네이버 결과는 커뮤니티로 세지 않고, 욕설 표제어는 둘러보기에 없다.
    표제어 언어의 나라는 그 나라 글자로 쓴 말만 — 위키 일본어판에서 받은 영어 제목은 '전 세계'."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import dashboard
    from trend_agents.schemas import Evidence, MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    week = dashboard._weeks()[-1]

    def term(tid, name, lang, usage=()):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", first_seen=now, last_seen=now))
        ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance="y", generations=["20s"], regions=list(usage),
                                              self_confidence=0.9), "verified_auto", [])
        if usage:
            ds.set_usage(con, tid, [("20s", r, now.isoformat(), 1.0) for r in usage])

    term("oshi", "推し活", "ja", ("JP", "TW"))
    ds.set_weekly_region(con, "oshi", {"JP": {week: 125}, "TW": {week: 2}})
    ds.add_evidences(con, "oshi", [
        Evidence(evidence_id="c1", kind="community", url="c1", title="推し活 まとめ", source_domain="togetter.com", observed_at=now, excerpt="推し活"),
        Evidence(evidence_id="c2", kind="community", url="c2", title="推し活 心得", source_domain="dcard.tw", observed_at=now, excerpt="推し活"),
        Evidence(evidence_id="c3", kind="community", url="c3", title="推し活", source_domain="bsky.app", observed_at=now, excerpt="推し活"),
        Evidence(evidence_id="c4", kind="community", url="c4", title="노르웨이 축구", source_domain="naver:kin", observed_at=now, excerpt="축구"),
    ])
    term("cake", "The cake is a lie", "ja")                      # 일본어 위키에서 받은 영어 제목, 나라 정보 없음
    term("rude", "인실좆", "ko", ("KR",))
    dashboard.run(con)

    tw = next(c for c in dashboard.board(con, ["TW"]).rising + dashboard.board(con, ["TW"]).fading if c.term_id == "oshi")
    jp = next(c for c in dashboard.board(con, ["JP"]).rising + dashboard.board(con, ["JP"]).fading if c.term_id == "oshi")
    assert tw.mentions_4w == 2 and jp.mentions_4w == 125
    # 커뮤니티 글은 지표로만 센다 — 카드에 사이트 이름도 글도 없다(ADR 0003)
    everywhere = dashboard.card(con, "oshi")
    assert tw.communities == jp.communities == everywhere.communities == []
    assert not any(e.kind == "community" for c in (tw, jp, everywhere) for e in c.evidences)
    # 그래도 나라별 쓰임으로는 센다: 블루스키(전 세계 플랫폼)의 일본어 글은 일본으로 — 그 용어가 쓰이는 나라 가운데서 글자로 짐작한다(검토 3차).
    # 네이버 결과는 쓰임으로 세지 않는다(세면 'KR' 이 생긴다)
    stored = next(s for s in dashboard._load(con)[0] if s.card.term_id == "oshi")
    assert set(stored.last_used) == {"JP", "TW"} and tw.last_used and jp.last_used

    cake = dashboard.card(con, "cake")
    assert cake.regions == ["GLOBAL"]                            # 일본 카드가 아니다
    whole = dashboard.board(con)
    assert "rude" not in {c.term_id for c in whole.rising + whole.fading + whole.caution}   # 둘러보기에 욕설 표제어는 없다
    assert dashboard.card(con, "rude") is not None                                          # 사전에서 직접 찾으면 나온다


def test_rechecks_repair_blank_region_usage(monkeypatch):
    """예전 조사가 나라 자리에 '' 를 저장한 용어는 새 조사가 나라를 고친다 — 처음 한 번만 쓰면 영영 못 고쳤다."""
    from datetime import datetime, timezone

    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    ds.set_usage(con, "t1", [("20s", "", datetime.now(timezone.utc).isoformat(), 1.0)])
    existing = ds.get_usage(con, "t1")
    assert existing and not any(u["region"] for u in existing)
    ds.clear_usage(con, "t1")
    ds.set_usage(con, "t1", [("20s", "JP", datetime.now(timezone.utc).isoformat(), 1.0)])
    assert [u["region"] for u in ds.get_usage(con, "t1")] == ["JP"]


def test_rising_orders_by_recent_use_when_raw_mentions_are_zero():
    """원본 언급이 모두 0 이면 이름순이 아니라 가장 최근에 쓰인 글 순 — 그 지역의 글만 본다."""
    from datetime import datetime, timedelta, timezone

    from trend_agents.pipeline import dashboard
    from trend_agents.schemas import Evidence, MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name, days_ago in (("a", "가나다", 20), ("b", "하하하", 1)):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", lifecycle="steady", first_seen=now, last_seen=None))
        ds.add_meaning(con, tid, MeaningDraft(definition="뜻", origin="x", nuance="y", generations=["20s"], regions=["KR"], self_confidence=0.9),
                       "verified_auto", [])
        ds.set_usage(con, tid, [("20s", "KR", now.isoformat(), 1.0)])
        ds.add_evidences(con, tid, [Evidence(evidence_id=f"e{tid}", kind="community", url=f"u{tid}", title=f"{name} 글", source_domain="theqoo.net",
                                             observed_at=now - timedelta(days=days_ago), excerpt=name)])
    dashboard.run(con)
    rising = dashboard.board(con, ["KR"]).rising
    assert [c.term_id for c in rising] == ["b", "a"] and rising[0].last_used is not None
    assert dashboard.board(con, ["JP"]).rising == []           # 한국 글은 일본 순서에 쓰이지 않는다(카드도 없다)


def test_dashboard_follows_live_decisions_and_regions_round2():
    """캐시가 옛것이어도 화면은 지금의 결정을 따른다(제외·리스크), 검수자가 '문제 없음' 으로 푼 욕설 오탐은 보인다,
    베트남어는 글자로·인도네시아어는 언어로 나라를 정한다, 한국 연령대 정점은 한국을 고를 때만."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import dashboard
    from trend_agents.schemas import MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)

    def term(tid, name, lang, usage=()):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", lifecycle="steady", first_seen=now, last_seen=now))
        ds.add_meaning(con, tid, MeaningDraft(definition=f"{name} 뜻", origin="x", nuance="y", generations=["20s"], regions=list(usage),
                                              self_confidence=0.9), "verified_auto", [])
        if usage:
            ds.set_usage(con, tid, [("20s", r, now.isoformat(), 1.0) for r in usage])

    term("vn", "u là trời", "vi")
    term("idn", "anjay", "id")
    term("kr", "럭키비키", "ko", ("KR", "JP"))
    term("oops", "Koshitantan shit", "en", ("US",))
    dashboard.run(con)
    assert dashboard.card(con, "vn").regions == ["VN"] and dashboard.card(con, "idn").regions == ["ID"]

    ds.set_risk(con, "kr", "avoid", ["사전 뜻풀이에 적힌 주의점"], now)                # 캐시를 만든 뒤의 결정
    assert "kr" in {c.term_id for c in dashboard.board(con, ["KR"]).caution}
    t = ds.get_term(con, "kr")
    t.status = "retired"
    ds.upsert_term(con, t, human=True)
    assert "kr" not in {c.term_id for c in dashboard.cards(con, ["KR"])}

    assert "oops" not in {c.term_id for c in dashboard.cards(con, ["GLOBAL"])}
    t = ds.get_term(con, "oops")
    t.risk_human = "none"
    ds.upsert_term(con, t, human=True)                                                   # 검수자가 오탐을 풀었다
    ds.set_risk(con, "oops", "avoid", ["표제어 자체가 욕설·성적 표현이다."], now)       # 규칙이 여전히 사용 자제라고 해도 실제 수준은 검수자의 것
    assert "oops" in {c.term_id for c in dashboard.cards(con, ["GLOBAL"])}


def test_track_keeps_old_shorts_in_their_week_and_clears_stale_last_seen():
    """영상 행이 지워진 쇼츠는 해석한 날의 주로 센다(오늘이 아니라). 원본도 쓰임 근거도 없으면 마지막 본 때를 비운다."""
    from datetime import datetime, timedelta, timezone

    from trend_agents.pipeline import track
    from trend_agents.schemas import MemeRef, ShortsInterpretation, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=45)
    ds.upsert_term(con, Term(term_id="t1", canonical="skibidi", lang="en", status="verified", first_seen=old, last_seen=now))
    it = ShortsInterpretation(url="https://www.youtube.com/watch?v=v1", language="en", summary="s", target_generation=["10s"], why_viral="w",
                              explain_for_outsider="e", memes=[MemeRef(name="skibidi", kind="meme", origin_hypothesis="x", confidence=0.9)])
    con.execute("INSERT INTO interpretations VALUES (?,?,?,?)", ("v1", "test", old.isoformat(), it.model_dump_json()))
    con.commit()
    counts = track.weekly_counts(con, "skibidi", [])
    assert track._week(now.date()) not in counts and sum(counts.values()) == 1
    ds.upsert_term(con, Term(term_id="t2", canonical="없는말", lang="ko", status="verified", first_seen=old, last_seen=now))
    track.run(con)
    assert ds.get_term(con, "t2").last_seen is None


def test_mention_sampling_rotates_through_all_terms():
    """뉴스 검색으로 언급을 재는 칸은 한 번도 안 잰 것·오래된 것부터 돌아간다 — 같은 30개만 재던 것(검토 2차)."""
    from datetime import datetime, timezone

    from trend_agents.pipeline.collect import mention_order
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for k in range(5):
        ds.upsert_term(con, Term(term_id=f"t{k}", canonical=f"말{k}", lang="ko", status="verified", lifecycle="steady", first_seen=now, last_seen=now))
    terms = ds.list_terms(con, ("verified",))
    first = [t.term_id for t in mention_order(con, terms, 3)]
    for tid in first:
        ds.mark_mention_sampled(con, tid)
    second = [t.term_id for t in mention_order(con, terms, 3)]
    assert set(second[:2]) == {"t0", "t1", "t2", "t3", "t4"} - set(first)       # 아직 안 잰 두 말이 먼저


def test_mention_sampling_keeps_slots_for_terms_under_review():
    """확인된 말이 칸보다 많아도 검수 대기 말이 3분의 1 을 받는다 — 확인된 말이 늘 먼저라 검수 대기 말을 영영 재지 않았다(검토 3차)."""
    from datetime import datetime, timezone

    from trend_agents.pipeline.collect import mention_order
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for k in range(40):
        ds.upsert_term(con, Term(term_id=f"v{k:02d}", canonical=f"확인{k}", lang="ko", status="verified", lifecycle="steady", first_seen=now, last_seen=now))
    for k in range(3):
        ds.upsert_term(con, Term(term_id=f"r{k}", canonical=f"대기{k}", lang="ko", status="needs_review", lifecycle="unknown", first_seen=now, last_seen=now))
    terms = ds.list_terms(con, ("verified", "needs_review"))
    for t in terms:
        ds.mark_mention_sampled(con, t.term_id)                   # 모두 한 번씩 잰 뒤에도
    got = mention_order(con, terms, 30)
    assert len(got) == 30 and {t.term_id for t in got} >= {"r0", "r1", "r2"}
    assert len(mention_order(con, [t for t in terms if t.status == "verified"], 30)) == 30   # 한쪽이 모자라면 다른 쪽이 채운다

def test_research_skips_terms_rejected_after_the_stage_picked_them():
    """단계가 대상을 고른 뒤 사람이 제외한 말은 조사하지 않는다 — 네트워크에 가기 전에 끝난다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline.research import research_one
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = Term(term_id="t1", canonical="내린말", lang="ko", status="verified", first_seen=now, last_seen=now)
    ds.upsert_term(con, t)
    stale = ds.get_term(con, "t1")
    t.status = "retired"
    ds.upsert_term(con, t, human=True)
    assert research_one(con, stale) == ("rejected", [])


def test_public_lists_hide_profane_headwords_and_single_card_refresh_keeps_time():
    """나라 페이지·오늘의 변화도 둘러보는 목록이다. 카드 하나를 고쳐도 '갱신' 시각은 그대로."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import dashboard, views
    from trend_agents.schemas import MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name in (("ok", "럭키비키"), ("bad", "인실좆")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now))
        ds.add_meaning(con, tid, MeaningDraft(definition="뜻", origin="x", nuance="y", generations=["20s"], regions=["KR"], self_confidence=0.9),
                       "verified_auto", [])
        ds.set_usage(con, tid, [("20s", "KR", now.isoformat(), 1.0)])
    assert [r.term.term_id for r in views.country_page(con, "KR").terms] == ["ok"]
    assert "인실좆" not in {u["label"] for u in ds.recent_updates(con, hours=1)}
    dashboard.run(con)
    before = ds.cache_get(con, dashboard.CACHE_KEY)[1]
    dashboard.refresh_card(con, "ok")
    assert ds.cache_get(con, dashboard.CACHE_KEY)[1] == before


def test_korean_and_nuance_regexes_ignore_words_that_merely_contain_the_letters():
    from trend_agents.pipeline.match import unsafe
    from trend_agents.pipeline.risk import nuance_warning

    for w in ("거들떠보지도", "찾아보지도", "지켜보지", "피자지만", "의자지만", "먹어보지도", "감자지옥"):
        assert not unsafe(w), w
    for text in ("이성적인 판단", "차별화된 개성", "시험 성적이 좋다", "감성적인 말투"):
        assert nuance_warning(text) == "", text
    assert nuance_warning("성적으로 대상화하는 말이다.") and nuance_warning("혐오감을 줄 수 있다.")


def test_unsampled_weeks_do_not_read_as_decline():
    """용어별 뉴스 검색으로만 잡힌 언급 [.., 9, 96, 0, 0] 은 그 뒤로 재지 않았으면 '지는 중' 이 아니다 — 마지막 쓰임으로 본다(검토 2차).
    최근에 다시 쟀는데도 0 이면 그때는 모양으로 본다."""
    from datetime import datetime, timedelta, timezone

    from trend_agents.pipeline import track
    from trend_agents.schemas import Evidence, NewsItem, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="推し活", lang="ja", status="verified", first_seen=now - timedelta(days=200), last_seen=now))
    for k in range(40):
        when = now - timedelta(days=16 if k < 30 else 23)
        n = NewsItem(title=f"推し活 特集 {k}", link=f"n{k}", source="x", published_at=when, region="JP", query="推し活")
        con.execute("INSERT INTO news VALUES (?,?,?,?,?,?)", (n.link, n.region, n.query, when.isoformat(), when.isoformat(), n.model_dump_json()))
    con.commit()
    ds.add_evidences(con, "t1", [Evidence(evidence_id="c1", kind="community", url="https://togetter.com/li/1", title="推し活 まとめ",
                                          source_domain="togetter.com", observed_at=now - timedelta(days=1), excerpt="推し活")])
    track.run(con)
    assert ds.get_term(con, "t1").lifecycle == "steady"          # 어제 쓰인 글이 있다 — 재지 않은 두 주를 '0 건' 으로 읽지 않는다

    ds.mark_mention_sampled(con, "t1")                           # 오늘 다시 쟀는데 새 언급이 없다 → 그때는 모양으로
    track.run(con)
    assert ds.get_term(con, "t1").lifecycle in ("declining", "dormant", "peak", "steady")


# ---------- 검토 3차 ----------

def test_spot_skips_emoji_only_and_profane_candidates():
    """발굴 후보에 글자 없는 이모지·욕설은 넣지 않는다 — 목표 지역을 늘린 뒤 '😭😭'·'fucked' 가 후보로 들어왔다. 숫자 밈 '8+9' 는 남긴다."""
    from trend_agents.pipeline.spot import keep
    from trend_agents.schemas import SpottedTerm

    def p(term):
        return SpottedTerm(i=0, term=term, lang="en", kind="meme", confidence=0.9)

    assert not keep(p("😭😭"), "so sad 😭😭 today", lambda t: None)
    assert not keep(p("fucked"), "we are fucked lol", lambda t: None)
    assert keep(p("aura farming"), "peak aura farming right here", lambda t: None)
    assert keep(p("8+9"), "8+9 是什麼梗？他就是個 8+9 啦", lambda t: None)    # 숫자 밈 — 중국어 단서 낱말(梗)로도 통과한다
    assert not keep(p("8+9"), "他就是個 8+9 啦", lambda t: None)               # 단서가 없으면 그냥 숫자다


def test_verb_forms_are_not_profanity_and_sexual_nuance_nouns_warn():
    from trend_agents.pipeline.match import unsafe
    from trend_agents.pipeline.risk import nuance_warning

    for text in ("밤새 자지 않고 공부", "오늘 밤은 자지 마", "잠을 못 자지만 괜찮아", "자주 보지만 재미있다", "한 번 먹어 보지 뭐", "써 보지 그래?", "그냥 보지요"):
        assert not unsafe(text), text
    assert unsafe("보지") and unsafe("자지 사진")
    for text in ("성적 표현이 들어 있어 공식 계정에서는 피한다.", "성적 농담으로 쓰인다.", "여성을 성적 대상화하는 말이다.", "11월 한 달 동안의 성적 금욕을 뜻한다."):
        assert nuance_warning(text), text
    for text in ("이성적인 판단", "여성적인 말투", "시험 성적이 좋다", "성적 향상을 바라는 말"):
        assert nuance_warning(text) == "", text


def test_risk_stage_does_not_overwrite_a_decision_made_while_judging(monkeypatch):
    """판정하는 사이 검수자가 수준을 정하면, 저장되는 수준은 검수자의 것 — 옛 사본의 규칙 수준이 결정 옆에 적혀 화면·추천이 다른 수준을 썼다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import risk
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    ds.upsert_term(con, Term(term_id="t1", canonical="테스트밈", lang="ko", status="verified", first_seen=datetime.now(timezone.utc)))

    def judging(con_, term):
        t = ds.get_term(con, "t1")                         # 검수 화면이 이 순간에 '문제 없음' 으로 정했다
        t.risk_human = "none"
        ds.upsert_term(con, t, human=True)
        return "caution", ["위험 유형이 붙은 근거 2건"]

    monkeypatch.setattr(risk, "judge", judging)
    risk.apply(con, ds.get_term(con, "t1"))
    t = ds.get_term(con, "t1")
    assert t.risk_human == "none" and t.risk_level == "none" and t.risk_rule_level == "caution"
    assert t.risk_reasons[0] == "검수자가 정한 수준"


def test_public_feed_shows_reviewer_cleared_headwords():
    """'오늘의 변화' 도 검수자가 '문제 없음' 으로 푼 표제어는 낸다 — 대시보드·나라 화면과 같은 기준."""
    from datetime import datetime, timezone

    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name in (("y", "병신년"), ("z", "좆같은말")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="verified", first_seen=now, last_seen=now))
    t = ds.get_term(con, "y")
    t.risk_human = t.risk_level = "none"
    ds.upsert_term(con, t, human=True)
    labels = {r["label"] for r in ds.recent_updates(con)}
    assert "병신년" in labels and "좆같은말" not in labels


def test_evidence_without_the_headword_is_not_usage_nor_a_document():
    """검색이 끌어온 딴 글(표제어가 없는 근거)은 주별 언급·마지막 쓰임·문서 수·리스크 분류 문장에 들어가지 않고, 카드 근거로도 나가지 않는다
    (원작자 서버 실측: 근거 9,738건 중 1,882건 — '오살힘' 추천 근거가 한국 배우·KBS 드라마 위키백과 문서였다)."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import dashboard, risk, track
    from trend_agents.schemas import Evidence, MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    at = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="오살힘", lang="ko", status="verified", first_seen=at, last_seen=at))
    ds.add_meaning(con, "t1", MeaningDraft(definition="작지만 하루를 버티게 해 주는 것", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                           self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, "t1", [("20s", "KR", at.isoformat(), 1.0)])

    def ev(eid, kind, dom, url, text):
        return Evidence(evidence_id=eid, kind=kind, url=url, title=text, source_domain=dom, observed_at=at, excerpt=text)

    ds.add_evidences(con, "t1", [ev("ok", "community", "theqoo.net", "https://theqoo.net/1", "오늘도 오살힘 충전"),
                                 ev("off", "news", "news.example", "https://news.example/a", "소가죽 굿판 vs 오살 의식"),
                                 ev("doc", "web", "ko.wikipedia.org", "https://ko.wikipedia.org/wiki/x", "Wikipedia: 엄마가 미쳤어요 KBS 1TV 일일 드라마다.")])
    assert sum(track.evidence_weeks(con, "t1").values()) == 1
    assert track.usage_kinds(con, "t1") == {"community": 1}
    assert [e.evidence_id for e in risk._usage(con, ds.get_term(con, "t1"))] == ["ok"]
    dashboard.run(con)
    card = dashboard.card(con, "t1")
    assert card.evidences == [] and card.last_used is not None   # 표제어가 든 글은 커뮤니티 글뿐 — 쓰임으로만 세고 근거로 내지 않는다(ADR 0003)


def test_topics_store_only_evidence_that_names_the_term(monkeypatch):
    """주제 단계의 검색 결과 가운데 표제어가 든 것만 모델에 주고 근거로 저장한다."""
    import json  # noqa: F401
    from datetime import datetime, timezone

    from trend_agents.pipeline import topics
    from trend_agents.schemas import Evidence, MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="오살힘", lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.add_meaning(con, "t1", MeaningDraft(definition="작지만 하루를 버티게 해 주는 것", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                           self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, "t1", [("20s", "KR", now.isoformat(), 0.5), ("20s", "TW", now.isoformat(), 0.2)])

    def ev(eid, text):
        return Evidence(evidence_id=eid, kind="news", url=f"https://n.example/{eid}", title=text, source_domain="n.example", observed_at=now, excerpt=text)

    monkeypatch.setattr(topics, "gather", lambda con, term, region: [ev(f"ok-{region}", "오살힘 是什麼？"), ev(f"no-{region}", "소가죽 굿판 vs 오살 의식")])
    monkeypatch.setattr(topics, "local_ok", lambda: True)
    seen = []

    def fake(con, prompt, schema, **k):
        seen.append(prompt)
        return topics.VariantNote(local_name="오살힘", what_changed={"ko": "팬 커뮤니티에서 씀", "en": "Used by fans"}, self_confidence=0.6), "local:x"

    monkeypatch.setattr(topics, "structured", fake)
    topics.run(con)
    assert {e.evidence_id for e in ds.list_evidences(con, "t1")} == {"ok-KR", "ok-TW"}
    assert seen and not any("오살 의식" in p for p in seen)


def test_japanese_posts_on_global_platforms_count_for_japan():
    """블루스키·레딧 같은 전 세계 플랫폼 글은 글자로 나라를 짐작한다 — 그 용어가 쓰이는 나라 가운데서만."""
    from trend_agents.pipeline.dashboard import GLOBAL, text_region

    assert text_region("推し活 たのしい", ["JP", "TW"]) == "JP"
    assert text_region("推活好累", ["JP", "TW"]) == "TW"
    assert text_region("오늘도 오살힘", ["TW"]) == GLOBAL                # 그 용어의 나라가 아니면 짐작하지 않는다
    assert text_region("so true", ["KR"]) == GLOBAL


def test_measured_weeks_stop_at_the_last_news_search():
    """용어별 뉴스 검색으로 잰 주까지만 모양을 본다 — 9일 전에 잰 推し活 [..,9,96,0,0] 이 '지는 중' 이 됐다. 잰 주는 잰 날까지로 늘린다."""
    from datetime import date, datetime, timedelta, timezone

    from trend_agents.lifecycle import stage as life_stage
    from trend_agents.pipeline.track import _week, measured_series

    today = date.today()
    weeks = [_week(today - timedelta(weeks=i)) for i in range(11, -1, -1)]
    series = [1, 0, 0, 5, 0, 0, 0, 0, 9, 96, 0, 0]
    sampled = datetime.combine(date.fromisoformat(weeks[9]) + timedelta(days=6), datetime.min.time(), timezone.utc)   # 두 주 전 일요일
    got = measured_series(series, weeks, sampled)
    assert got == series[:10] and life_stage(got, 30) != "declining"
    tuesday = datetime.combine(date.fromisoformat(weeks[11]) + timedelta(days=1), datetime.min.time(), timezone.utc)
    flat = [7] * 11 + [2]                                                  # 이번 주 화요일까지 이틀 치
    assert measured_series(flat, weeks, tuesday)[-1] == 7 and life_stage(measured_series(flat, weeks, tuesday), 30) == "steady"


def test_recency_counts_from_the_last_look_while_it_is_fresh():
    """다시 조사하기 전에 '꾸준함' 이 저절로 '지는 중' 이 되지 않는다 — 마지막으로 찾아본 때를 기준으로(그 조사가 오래지 않았으면)."""
    from datetime import datetime, timedelta, timezone

    from trend_agents.lifecycle import recency_stage
    from trend_agents.pipeline.track import as_of_last_look

    now = datetime.now(timezone.utc)
    newest, look = now - timedelta(days=16), now - timedelta(days=5)
    assert recency_stage(newest, now=now) == "declining"
    assert recency_stage(newest, now=as_of_last_look(look, now)) == "steady"
    assert as_of_last_look(now - timedelta(days=40), now) == now          # 한 달 넘게 안 봤으면 지금 기준


def test_recheck_puts_dictionary_terms_before_the_review_backlog():
    from datetime import datetime, timezone

    from trend_agents.pipeline.research import due_for_recheck
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, status in (("a_review", "needs_review"), ("b_verified", "verified"), ("c_new", "researching")):
        ds.upsert_term(con, Term(term_id=tid, canonical=tid, lang="en", status=status, lifecycle="steady", first_seen=now))
    assert [t.term_id for t in due_for_recheck(con, 3)] == ["c_new", "b_verified", "a_review"]


def test_namu_recheck_backs_off_after_a_failure(monkeypatch):
    """나무위키 문서가 고쳐진 뒤 다시 조사하다 실패한 말은 재검증 주기만큼 쉰다 — 실행마다 같은 말이 칸과 예산을 차지했다."""
    from datetime import datetime, timedelta, timezone

    from trend_agents.pipeline import namu, research
    from trend_agents.schemas import Evidence, MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    ds.upsert_term(con, Term(term_id="t1", canonical="럭키비키", lang="ko", status="verified", lifecycle="steady", first_seen=now))
    ds.add_meaning(con, "t1", MeaningDraft(definition="나쁜 상황도 좋게 보는 말", origin="x", nuance="y", generations=["20s"], regions=["KR"],
                                           self_confidence=0.9), "verified_auto", [])
    ds.log_research(con, "t1", "ok", "", [], "verified_auto", [])
    con.execute("UPDATE research_log SET researched_at=?", ((now - timedelta(days=3)).isoformat(),))
    con.commit()
    edited = Evidence(evidence_id="n1", kind="wiki", url="https://namu.wiki/w/x", title="럭키비키", source_domain="namu.wiki",
                      observed_at=now - timedelta(days=1), excerpt="럭키비키")
    monkeypatch.setattr(namu.namuwiki, "ranking", lambda: [])
    monkeypatch.setattr(namu.namuwiki, "category", lambda cat: [])
    monkeypatch.setattr(namu.namuwiki, "lookup", lambda name: [edited])
    monkeypatch.setattr("trend_agents.pipeline.gemini.local_ok", lambda: True)
    calls = []

    def failing(con_, t):
        calls.append(t.term_id)
        raise ValueError("형식 실패")

    monkeypatch.setattr(research, "research_one", failing)
    namu.run(con)
    namu.run(con)
    assert calls == ["t1"]                                                   # 두 번째 실행은 쉰다


def test_dictionary_page_shows_only_evidence_that_names_the_term():
    """사전 화면의 근거 목록도 표제어가 든 것만 — 검색 지수(datalab)는 문장이 아니라 그대로 둔다. 커뮤니티 글은 표제어가 있어도 내지 않는다(ADR 0003)."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import views
    from trend_agents.schemas import Evidence, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    at = datetime.now(timezone.utc)
    t = ds.upsert_term(con, Term(term_id="t1", canonical="오살힘", lang="ko", status="verified", first_seen=at, last_seen=at))

    def ev(eid, kind, text):
        return Evidence(evidence_id=eid, kind=kind, url=f"https://x.example/{eid}", title=text, source_domain="x.example", observed_at=at, excerpt=text)

    ds.add_evidences(con, "t1", [ev("ok", "news", "요즘 뜨는 오살힘"), ev("off", "news", "소가죽 굿판 vs 오살 의식"),
                                 ev("lab", "datalab", "검색 추이 · 연령대별 20대 2026-03 피크"), ev("post", "community", "오늘도 오살힘 충전")])
    assert {e.evidence_id for e in views.term_record(con, t).evidences} == {"ok", "lab"}


# ---------- ADR 0003: 사전 등재 기준 — 참고 문서가 있는 말만 자동으로, 커뮤니티·SNS 글은 지표로만 ----------

def _lucky_draft():
    return MeaningDraft(definition="어떤 일이든 운 좋게 받아들이는 긍정적 태도", origin="장원영의 말에서", nuance="밝게 쓴다",
                        generations=["20s"], regions=["KR"], self_confidence=0.9)


def test_gate_lists_only_terms_with_a_reference_document():
    """자동으로 싣는 말은 참고 문서(나무위키·위키백과·Know Your Meme·pixiv 백과사전·萌娘百科)에 표제어가 든 문서가 있어야 한다.
    뉴스·커뮤니티 두 곳이 있어도 문서가 없으면 검수 대기. 홈페이지 주소·실시간 검색어·표제어가 없는 문서·커뮤니티 링크는 문서가 아니다."""
    from trend_agents.verification import NO_REFERENCE

    term, draft = "럭키비키", _lucky_draft()
    usage = [ev("news", "news.example", f"{term} 유행", f"{term} 가 유행이다"), ev("community", "bsky.app", f"{term} ㅋㅋ", f"완전 {term}잖아")]
    # 커뮤니티 글은 어떤 셈에도 들지 않아 뉴스 한 곳만 남는다(2026-09-30)
    assert gate(term, draft, usage, None) == ("unverified", ["용어가 실재하는 독립 출처 2개 미만", NO_REFERENCE])

    for kind, domain, url in (("wiki", "namu.wiki", "https://namu.wiki/w/x"), ("wiki", "wikipedia.org", "https://ko.wikipedia.org/wiki/x"),
                              ("web", "knowyourmeme.com", "https://knowyourmeme.com/memes/x"), ("web", "dic.pixiv.net", "https://dic.pixiv.net/a/x"),
                              ("web", "zh.moegirl.org.cn", "https://zh.moegirl.org.cn/x")):
        doc = ev(kind, domain, f"{term} 문서", f"{term} 는 긍정 밈이다", url=url)
        assert gate(term, draft, usage + [doc], None) == ("verified_auto", []), domain

    not_docs = [ev("wiki", "namu.wiki", f"나무위키: {term}", f"{term} 유래", url="https://namu.wiki/"),               # 홈페이지 주소
                ev("datalab", "namu.wiki", f"나무위키 실시간 검색어: {term}", term, url="https://namu.wiki/w/x"),     # 실시간 검색어
                ev("wiki", "namu.wiki", "나무위키: 장원영", "아이브의 멤버다", url="https://namu.wiki/w/y"),            # 표제어가 없는 문서
                ev("web", "theqoo.net", f"{term} 글", f"{term} 진짜", url="https://theqoo.net/1"),                    # 커뮤니티 링크
                ev("web", "notwikipedia.org", f"{term} 문서", f"{term} 는 밈", url="https://notwikipedia.org/w/x")]   # 글자만 비슷한 도메인
    for doc in not_docs:
        assert NO_REFERENCE in gate(term, draft, usage + [doc], None)[1], doc.url


def test_gate_does_not_demote_listed_terms_for_a_missing_document():
    """이미 실린 말을 다시 조사할 때는 이 규칙으로 강등하지 않는다 — 기존 항목은 문서 대조(Plan 12) 뒤 사람이 정리한다. 검수 대기 중인 말에는 그대로."""
    from trend_agents.schemas import Meaning
    from trend_agents.verification import NO_REFERENCE

    term, draft = "럭키비키", _lucky_draft()
    usage = [ev("news", "news.example", f"{term} 유행", f"{term} 가 유행이다"), ev("community", "bsky.app", f"{term} ㅋㅋ", f"완전 {term}잖아")]
    listed = Meaning(**draft.model_dump(), meaning_id="m1", term_id="t1", version=1, confidence=0.9, verification="verified_auto",
                     valid_from=datetime.now(timezone.utc))
    assert gate(term, draft, usage, listed) == ("verified_auto", [])
    assert NO_REFERENCE in gate(term, draft, usage, listed.model_copy(update={"verification": "unverified"}))[1]


def test_research_without_a_document_waits_for_a_person_who_can_publish_it(monkeypatch):
    """조사 단계: 참고 문서가 없으면 검수 대기로 가고 사람 큐에 쉬운 이유와 함께 남는다(자동으로 닫지 않는다). 문서가 있으면 바로 실린다.
    사람이 승인하면 문서가 없어도 실린다 — 그런 문서가 드문 지역의 예외 길."""
    from fastapi.testclient import TestClient

    from trend_agents.api import app as api
    from trend_agents.collectors import community, gdelt_context, namuwiki, naver_search, wiktionary
    from trend_agents.pipeline import research
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db
    from trend_agents.verification import NO_REFERENCE

    documented = {"원영적 사고"}
    monkeypatch.setattr(research, "budget_left", lambda con: 0)                  # Search grounding 없이 — 모은 근거로만(오프라인 조사)
    monkeypatch.setattr(research, "structured", lambda *a, **k: (_lucky_draft(), "local:test"))
    monkeypatch.setattr(research, "first_party_evidence", lambda con, term, *a, **k: [ev("news", "news.example", f"{term} 유행", f"요즘 {term} 가 유행이다")])
    monkeypatch.setattr(research, "_wikipedia_evidence", lambda *a, **k: [])
    monkeypatch.setattr(research, "attach_media", lambda *a, **k: 0)
    monkeypatch.setattr(wiktionary, "lookup", lambda *a, **k: [])
    monkeypatch.setattr(gdelt_context, "sentences", lambda *a, **k: [])
    monkeypatch.setattr(naver_search, "gather", lambda *a, **k: ([], []))
    monkeypatch.setattr(community, "gather", lambda term, *a, **k: ([ev("community", "bsky.app", f"{term} ㅋㅋ", f"완전 {term}")], []))
    monkeypatch.setattr(namuwiki, "lookup", lambda name: [ev("wiki", "namu.wiki", f"나무위키: {name}", f"{name}는 장원영에게서 나온 말이다",
                                                             url=f"https://namu.wiki/w/{name}")] if name in documented else [])

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name in (("t1", "럭키비키"), ("t2", "원영적 사고")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="ko", status="researching", first_seen=now, last_seen=now))
    v, reasons = research.research_one(con, ds.get_term(con, "t1"))
    assert v == "unverified" and NO_REFERENCE in reasons
    assert ds.get_term(con, "t1").status == "needs_review"
    q = ds.review_queue(con)
    assert [x["term_id"] for x in q] == ["t1"] and NO_REFERENCE in q[0]["reasons"]
    assert research.research_one(con, ds.get_term(con, "t2")) == ("verified_auto", [])
    assert ds.get_term(con, "t2").status == "verified"

    monkeypatch.setattr(api, "_con", con)
    monkeypatch.setenv("FRONTEND_API_TOKEN", "tok")
    m = ds.current_meaning(con, "t1")
    r = TestClient(api.app).post("/review/t1", json={"decision": "approve", "by": "kim", "meaning_id": m.meaning_id}, headers={"x-frontend-token": "tok"})
    assert r.status_code == 200 and ds.get_term(con, "t1").status == "verified"
    assert ds.current_meaning(con, "t1").verification == "verified_human"


def test_community_posts_are_recognised_on_any_path():
    """커뮤니티·SNS 글은 수집기가 붙인 종류(community)뿐 아니라 구글 뉴스가 기사로 준 한국 커뮤니티 글, 조사 모델이 든 커뮤니티·SNS 링크도 가린다.
    도메인은 그 사이트이거나 하위 도메인일 때만."""
    from trend_agents.collectors.community import is_community_post

    posts = [ev("community", "naver:cafearticle", "카페 글"), ev("news", "디시인사이드", "야갤 글", url="https://news.google.com/rss/articles/x"),
             ev("web", "gall.dcinside.com", "갤 글", url="https://gall.dcinside.com/board/view/?no=1"), ev("web", "x.com", "글", url="https://x.com/a/status/1"),
             ev("web", "forum.lowyat.net", "글", url="https://forum.lowyat.net/topic/1"), ev("community", "youtube.com/comments", "YouTube 댓글")]
    docs = [ev("news", "news.example", "기사"), ev("wiki", "namu.wiki", "나무위키: x", url="https://namu.wiki/w/x"),
            ev("short", "youtube.com", "쇼츠", url="https://www.youtube.com/shorts/abc"), ev("news", "lowyat.net", "기술 기사", url="https://lowyat.net/2026/x")]
    assert all(is_community_post(e) for e in posts) and not any(is_community_post(e) for e in docs)


def test_community_posts_are_signals_not_sources(monkeypatch):
    """커뮤니티·SNS 글은 마지막 쓰임·뉘앙스로 세지만 사전 항목·검수 화면·대시보드 카드·질문 답·'왜 뜨나' 근거에 제목·링크·사이트 이름으로 나가지 않는다."""
    from datetime import date

    from trend_agents.collectors.community import is_community_post
    from trend_agents.pipeline import board, dashboard, tools, views
    from trend_agents.schemas import TrendExplanation
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = ds.upsert_term(con, Term(term_id="t1", canonical="오살힘", lang="ko", status="verified", first_seen=now, last_seen=now))
    ds.add_meaning(con, "t1", MeaningDraft(definition="오늘을 살아갈 힘. 하루를 버티게 해 주는 것", origin="x", nuance="y", generations=["20s"],
                                           regions=["KR"], self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, "t1", [("20s", "KR", now.isoformat(), 1.0)])
    shown = [ev("news", "news.example", "요즘 뜨는 오살힘", "오살힘 이 뜬다", url="https://news.example/a"),
             ev("wiki", "namu.wiki", "나무위키: 오살힘", "오살힘은 오늘을 살아갈 힘의 줄임말이다", url="https://namu.wiki/w/오살힘")]
    posts = [ev("community", "bsky.app", "오살힘 ㅋㅋ", "오늘의 오살힘", url="https://bsky.app/profile/a/post/1"),
             ev("community", "naver:cafearticle", "네이버 카페 · 오살힘", "오살힘 모음", url="https://cafe.naver.com/x/1"),
             ev("news", "디시인사이드", "오살힘 짤 - 디시인사이드", "오살힘 짤", url="https://news.google.com/rss/articles/y"),
             ev("web", "theqoo.net", "오살힘 모음 - 더쿠", "오살힘 모음", url="https://theqoo.net/1")]
    ds.add_evidences(con, "t1", shown + posts)
    ds.set_evidence_labels(con, "t1", [(posts[0].evidence_id, "neutral", "none")], "test")
    names = ("bsky", "naver:cafe", "디시", "theqoo", "더쿠")

    assert {e.evidence_id for e in views.term_record(con, t).evidences} == {e.evidence_id for e in shown}
    ds.queue_review(con, "t1", MeaningDraft(**ds.current_meaning(con, "t1").model_dump(include=set(MeaningDraft.model_fields))), ["x"], 6)
    assert {e.evidence_id for e in views.review_items(con)[0].evidences} <= {e.evidence_id for e in shown}

    dashboard.run(con)
    card = dashboard.card(con, "t1")
    assert card.communities == [] and card.evidences and not any(is_community_post(e) for e in card.evidences)
    assert card.last_used is not None and card.tone.neutral == 1              # 쓰임·뉘앙스로는 센다

    ctx = tools.Ctx(con)
    said = tools.lookup_term(ctx, {"term": "오살힘"})
    assert "근거: 2건" in said and not any(n in said for n in names)
    assert ctx.cards[0]["evidence_count"] == 2                                 # '출처 n건 모두 보기' 는 사전 항목의 출처 수와 같다

    ds.save_explanation(con, TrendExplanation(term="오살힘", region="KR", date=date.today(), why_now="팬들이 쓴다", why_now_en="Fans use it",
                                              trigger="meme", self_confidence=0.8))
    ds.add_evidences(con, f"q|{ds.norm('오살힘')}|KR", shown[:1] + posts)
    [why] = board.why_list(con)
    assert [e.url for e in why.evidence] == [shown[0].url] and why.evidence_counts == {"news": 2, "community": 2, "web": 1}
    assert [e.url for e in views.query_graph(con, f"{ds.norm('오살힘')}|KR").evidence] == [shown[0].url]
    assert "근거: 1건" in tools.why_trending(tools.Ctx(con), {"term": "오살힘", "region": "KR"})


def test_community_collection_and_live_lookup_skip_dropped_sources(monkeypatch):
    """Lemmy·Hacker News 는 목표 지역 밖이라 모으지 않는다. 실시간 찾아보기는 이용자에게 출처가 보이므로 커뮤니티·SNS 를 읽지 않는다."""
    from trend_agents.collectors import community, wikipedia_search, wiktionary
    from trend_agents.pipeline import live

    def boom(*a, **k):
        raise RuntimeError("down")

    for name in ("google_indexed_posts", "reddit_search", "bluesky_search"):
        monkeypatch.setattr(community, name, boom)
    evs, notes = community.gather("delulu", "US")
    assert evs == [] and sorted(n.split(":")[0] for n in notes) == ["bluesky", "community_sites", "reddit"]

    monkeypatch.setattr(community, "bluesky_search", lambda *a, **k: (_ for _ in ()).throw(AssertionError("읽으면 안 됨")))
    monkeypatch.setattr(wikipedia_search, "summary", lambda *a, **k: None)
    monkeypatch.setattr(wikipedia_search, "search", lambda *a, **k: [])
    monkeypatch.setattr(wiktionary, "lookup", lambda *a, **k: [])
    assert all(fn() == [] for fn in live._sources("delulu", "ko"))


def test_representative_video_needs_a_meme_cue_or_the_bare_phrase():
    """대표 영상은 제목에 밈 단서가 있거나, 기호를 뺀 제목이 표현 그 자체일 때만 — 흔한 영어 한 낱말은 노래 제목과 겹쳐 그것만으로 받지 않는다(09-30)."""
    from datetime import datetime, timezone

    from trend_agents.pipeline.research import video_is_about
    from trend_agents.schemas import Term

    def t(name):
        now = datetime.now(timezone.utc)
        return Term(term_id="t", canonical=name, lang="en", status="verified", aliases=[], first_seen=now, last_seen=now)

    assert video_is_about(None, t("Surprised Pikachu"), "Surprised Pikachu Meme Explained")
    assert video_is_about(None, t("간 때문이야"), "간 때문이야")
    assert video_is_about(None, t("シャミ子が悪いんだよ"), "シャミ子が悪いんだよ #shorts")
    assert not video_is_about(None, t("vibe"), "VIBE")                          # 노래 제목
    assert not video_is_about(None, t("懶人包"), "『1.5週年前瞻懶人包、ULT機終極強化』SD Gundam")   # 평범한 뜻으로 쓴 게임 공지
    assert not video_is_about(None, t("relatable"), "🤣#relatable #cat #shorts")   # 해시태그로만


def test_generation_shares_shown_are_measured_only():
    """세대 비중은 네이버 데이터랩 실측만 보인다. 조사 모델의 추정은 '추정' 으로만 말하고, 실측이 들어오면 그 나라의 추정 줄은 지워진다(Plan 15)."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import tools
    from trend_agents.schemas import MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    for tid, name, lang in (("t_ja", "推し活", "ja"), ("t_ko", "럭키비키", "ko")):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang=lang, status="verified", aliases=[], first_seen=now, last_seen=now))
        ds.add_meaning(con, tid, MeaningDraft(definition="좋아하는 대상을 응원하는 활동", origin="x", nuance="y", generations=["20s"], regions=["JP"], self_confidence=0.9), "verified_auto", [])
    ds.set_usage(con, "t_ja", [("20s", "JP", now.isoformat(), 1.0)])                          # 모델 추정
    ds.set_usage(con, "t_ko", [("30s", "KR", now.isoformat(), 1.0)])                          # 모델 추정
    ds.set_usage(con, "t_ko", [("10s", "KR", now.isoformat(), 0.7), ("20s", "KR", now.isoformat(), 0.3)], source="datalab")
    assert {(u["generation"], u["source"]) for u in ds.get_usage(con, "t_ko")} == {("10s", "datalab"), ("20s", "datalab")}   # 추정 줄은 사라진다

    ctx = tools.Ctx(con=con)
    out = tools.term_usage(ctx, {"term": "推し活"})
    assert "실측 자료 없음" in out and "추정" in out
    assert ctx.cards[-1]["bars"] == []                                                         # 추정은 막대로 보이지 않는다
    assert tools.term_usage(ctx, {"term": "럭키비키"}) and [b["ratio"] for b in ctx.cards[-1]["bars"]] == [0.7, 0.3]


def test_a_reference_document_alone_lists_the_term_and_community_posts_never_count():
    """2026-09-30 사용자 결정: 참고 문서에 표제어가 든 문서가 있으면 그것만으로 싣는다. 커뮤니티·SNS 글은 몇 곳이든 셈에 들지 않는다.
    위키 밈 분류에 든 말은 모델의 '표현이 아님' 판단으로 막지 않는다. 빈 뜻은 여전히 막는다."""
    from trend_agents.verification import NO_REFERENCE

    term, draft = "럭키비키", _lucky_draft()
    namu = ev("wiki", "namu.wiki", f"나무위키: {term}", f"{term} 는 긍정 밈이다", url="https://namu.wiki/w/x")
    assert gate(term, draft, [namu], None) == ("verified_auto", [])                       # 문서 하나로
    posts = [ev("community", d, f"{term} 글", f"완전 {term}잖아", url=f"https://{d}/1") for d in ("bsky.app", "dcinside.com", "theqoo.net")]
    v, reasons = gate(term, draft, posts, None)
    assert v == "unverified" and NO_REFERENCE in reasons and any("독립 출처" in r for r in reasons)   # 커뮤니티 세 곳이어도
    song = draft.model_copy(update={"is_expression": False})
    assert gate(term, song, [namu], None)[0] == "unverified"                               # 분류 밖의 말은 '표현이 아님' 이 막는다
    assert gate(term, song, [namu], None, catalogued=True) == ("verified_auto", [])         # 위키 밈 분류에 든 말은 막지 않는다
    empty = draft.model_copy(update={"definition": ""})
    assert gate(term, empty, [namu], None, catalogued=True)[0] == "unverified"             # 빈 뜻은 여전히 막는다


def test_catalog_adds_a_meme_with_its_categories_and_country_and_media_backfill_records_tries(monkeypatch):
    """위키 밈 분류(Plan 16): 제목으로 표제어를 세우고 분류·나라(usage source=catalog)를 남긴다. 사람 분류는 넣지 않는다.
    그림·영상 채우기는 못 붙인 것도 찾아 본 때를 남긴다(PostgreSQL 에서 INSERT OR REPLACE 가 되는지)."""
    from trend_agents.pipeline import catalog, research
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    t = catalog.add(con, "고양이 밈 (유행어)", ["인터넷 밈/동물", "인터넷 밈/일본", "2024년 인터넷 밈"])
    assert t and t.canonical == "고양이 밈" and t.status == "researching"
    assert [(u["region"], u["source"]) for u in ds.get_usage(con, t.term_id)] == [("JP", "catalog")]
    assert catalog.meta(["인터넷 밈/음악/일본", "2024년 인터넷 밈"]) == {"genres": ["음악"], "countries": ["일본"], "regions": ["JP"], "decade": 2020, "year": 2024, "slang": False}
    assert catalog.add(con, "아무개", ["인터넷 밈/정치인/대한민국"]) is None                  # 사람 문서
    assert catalog.add(con, "고양이 밈", ["인터넷 밈/동물"]) is None                            # 이미 있는 말은 분류만 남긴다
    t.status = "verified"
    ds.upsert_term(con, t)
    monkeypatch.setattr(research, "attach_media", lambda *a, **k: 0)
    assert research.backfill_media(con, limit=2, searches=0) == 0
    assert con.execute("SELECT count(*) FROM media_tried").fetchone()[0] == 1
    research.backfill_media(con, limit=2, searches=0)                                          # 두 번째도 된다(같은 줄을 바꾼다)


def test_research_counts_reference_documents_already_stored(monkeypatch):
    """일괄 등재가 미리 붙인 참고 문서(PTT鄉民百科 등)도 조사의 판정에 든다 — 이번 조사가 다시 찾지 않았다고 빠지면 문서가 있는 말이 떨어졌다(09-30)."""
    from datetime import datetime, timezone

    from trend_agents.collectors import knowyourmeme, wiktionary
    from trend_agents.pipeline import research
    from trend_agents.schemas import Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    monkeypatch.setattr(research, "budget_left", lambda con: 0)
    monkeypatch.setattr(research, "structured", lambda *a, **k: (_lucky_draft(), "local:test"))
    monkeypatch.setattr(research, "first_party_evidence", lambda *a, **k: [])
    monkeypatch.setattr(research, "_wikipedia_evidence", lambda *a, **k: [])
    monkeypatch.setattr(research, "attach_media", lambda *a, **k: 0)
    monkeypatch.setattr(wiktionary, "lookup", lambda *a, **k: [])
    monkeypatch.setattr(knowyourmeme, "enabled", lambda: False)
    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)
    t = Term(term_id="t_tw", canonical="多蛙", lang="zh", status="researching", aliases=[], first_seen=now, last_seen=now)
    ds.upsert_term(con, t)
    ds.add_evidences(con, "t_tw", [ev("wiki", "pttpedia.fandom.com", "PTT鄉民百科: 多蛙", "多蛙 起源於 2020 年 股票板", url="https://pttpedia.fandom.com/zh/wiki/多蛙")])
    assert research.research_one(con, t, lean=True) == ("verified_auto", [])


def test_risk_catches_sensitive_topics_without_usage_sentences():
    """위키에서 들어온 말은 쓰임 문장이 없어 판단 보류로만 남았다. 뜻풀이가 민감한 소재를 다루거나 위키 분류가 정치·종교 밈이면 '주의'(09-30).
    과자 논쟁 같은 '전쟁' 은 잡지 않는다."""
    from datetime import datetime, timezone

    from trend_agents.pipeline import catalog, risk
    from trend_agents.schemas import MeaningDraft, Term
    from trend_agents.storage import dictionary_store as ds
    from trend_agents.storage import store as db

    con = db.connect(":memory:")
    now = datetime.now(timezone.utc)

    def put(tid, name, definition):
        ds.upsert_term(con, Term(term_id=tid, canonical=name, lang="en", status="verified", aliases=[], first_seen=now, last_seen=now))
        ds.add_meaning(con, tid, MeaningDraft(definition=definition, origin="x", nuance="y", generations=["20s"], regions=["US"], self_confidence=0.9), "verified_auto", [])
        return ds.get_term(con, tid)

    assert risk.judge(con, put("a", "Heil meme", "나치 경례를 흉내 내는 밈"))[0] == "caution"
    assert risk.judge(con, put("b", "Kinoko war", "과자 두 종류를 두고 벌이는 전쟁 같은 논쟁"))[0] is None
    t = put("c", "Some slogan", "어떤 구호를 따라 하는 밈")
    catalog.record(con, "c", "Some slogan", "namu", ["인터넷 밈/정치 및 사회"])
    level, reasons = risk.judge(con, t)
    assert level == "caution" and "정치 및 사회" in reasons[0]


def test_trendaword_posts_count_as_reference_documents_only_on_that_path():
    """Trend A Word(maily.so/trendaword) 게시글은 참고 문서다(2026-09-30 사용자 요청). maily.so 의 다른 뉴스레터는 아니다."""
    from trend_agents.verification import reference_doc

    assert reference_doc(ev("web", "maily.so", "Trend A Word #629: 볼무떨천", "볼무떨천 뜻", url="https://maily.so/trendaword/posts/knrjkv10zld"))
    assert not reference_doc(ev("web", "maily.so", "다른 레터", "볼무떨천", url="https://maily.so/other/posts/abc"))
    assert not reference_doc(ev("web", "maily.so", "Trend A Word", "볼무떨천", url="https://maily.so/trendaword"))
