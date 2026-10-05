"""제목 색인(track.TitleIndex)은 제목마다 mentions() 를 부른 것과 같은 답을 내야 한다 – 생애주기 재계산을 빠르게 하려고 바꾼 것이라 판정이 달라지면 안 된다."""
import itertools

from trend_agents.pipeline.match import mentions
from trend_agents.pipeline.track import TitleIndex

TITLES = [
    "킹받네 진짜 킹받는 하루", "킹 받 네 라고 쓰는 사람들", "킹받", "오늘의 KINGBADNE",
    "Skibidi toilet is everywhere", "skibidi-toilet remix", "the skibidis are back", "SKIBIDI", "xskibidi",
    "6-7 meme explained", "score was 6-7 last night", "6 7", "67 and 6-7 trend on tiktok",
    "Rizz and gyatt", "rizzler", "no cap fr", "NO   CAP", "nocap",
    "ending with 킹받네", "킹받네 starting the next", "", "  ", "推し活 ブーム", "推し 活",
    "what does sigma mean", "Sigma male", "sigma6-7",
]
TERMS = [
    ("킹받네", []), ("킹 받네", []), ("skibidi", []), ("skibidi toilet", ["Skibidi"]), ("6-7", []), ("6 7", ["67"]),
    ("rizz", ["rizzler"]), ("no cap", []), ("推し活", []), ("sigma", ["6-7"]), ("", ["  "]), ("없는말", []),
]


def test_matches_mentions_on_every_title():
    index = TitleIndex(TITLES)
    for term, aliases in TERMS:
        expected = [i for i, title in enumerate(TITLES) if mentions(title, term, aliases)]
        assert index.matching(term, aliases) == expected, (term, aliases)


def test_neighbouring_titles_do_not_join_into_a_match():
    # 앞 제목의 끝과 뒤 제목의 시작이 이어 붙어 한 표기처럼 보이면 안 된다
    titles = ["no", "cap", "킹받", "네", "skibidi", "toilet"]
    index = TitleIndex(titles)
    for term in ("no cap", "킹받네", "skibidi toilet", "nocap"):
        assert index.matching(term, []) == [i for i, t in enumerate(titles) if mentions(t, term, [])]


def test_every_pair_of_short_titles():
    words = ["6-7", "meme", "킹받네", "Rizz", "rizz", "no cap"]
    titles = [" ".join(p) for p in itertools.permutations(words, 2)]
    index = TitleIndex(titles)
    for term, aliases in TERMS:
        assert index.matching(term, aliases) == [i for i, t in enumerate(titles) if mentions(t, term, aliases)]
