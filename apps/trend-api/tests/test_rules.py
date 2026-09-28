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
    evs = [ev("news", "a.com", "aqi 100 in Jakarta", "aqi is high"), ev("news", "b.com", "aqi warning", "aqi"), ev("short", "youtube.com", "aqi", "aqi")]
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
    assert any("독립 출처" in r for r in reasons)          # 위키만으로는 통과 못 한다

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
        return Evidence(evidence_id="e1", kind="community", url="https://lemmy.world/x", title=text,
                        source_domain="lemmy.world", observed_at=datetime.now(timezone.utc), excerpt=text)

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
