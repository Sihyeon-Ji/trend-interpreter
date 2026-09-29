"""ADR 0003 — 모델에게 보이는 근거: 커뮤니티·SNS 글은 내용 없이 몇 건인지만(사용자 결정 09-29 'AI 가 얼마나 쓰는지만 지표로 보게')."""
from datetime import datetime, timezone

from trend_agents.collectors.community import for_prompt
from trend_agents.pipeline.research import offline_notes
from trend_agents.schemas import Evidence


def _ev(kind: str, domain: str, title: str, url: str) -> Evidence:
    return Evidence(evidence_id=f"e_{abs(hash(url))}", kind=kind, url=url, title=title, source_domain=domain,
                    observed_at=datetime(2026, 9, 29, tzinfo=timezone.utc), excerpt=title)


def test_prompt_notes_count_posts_without_their_text():
    evs = [_ev("community", "bsky.app", "럭키비키 ㅋㅋ 오늘도 똥글", "https://bsky.app/profile/x/post/1"),
           _ev("news", "디시인사이드", "럭키비키 갤러리 글", "https://gall.dcinside.com/board/view/?id=1"),   # 기사로 들어온 커뮤니티 글
           _ev("news", "중앙일보", "'럭키비키' 원영적 사고 열풍", "https://www.joongang.co.kr/article/1"),
           _ev("wiki", "namu.wiki", "원영적 사고", "https://namu.wiki/w/원영적 사고")]
    shown, note = for_prompt(evs)
    assert [e.source_domain for e in shown] == ["중앙일보", "namu.wiki"]
    assert "2건" in note
    notes = offline_notes(evs)
    assert "똥글" not in notes and "갤러리 글" not in notes and "bsky" not in notes
    assert "원영적 사고 열풍" in notes and "커뮤니티·SNS 글 2건" in notes
    assert for_prompt(shown) == (shown, "")        # 글이 없으면 알림 줄도 없다
