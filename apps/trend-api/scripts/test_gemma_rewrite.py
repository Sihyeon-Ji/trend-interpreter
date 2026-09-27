"""'쉽게 풀어 쓰면' 재작성 테스트. 규칙 치환("완전 오히려 좋아잖아?") 대비 자연스러운지 본다."""
import time

from trend_agents.config import GEMMA_LOCAL_MODEL
from trend_agents.interpreters.gemma_local import is_available
from trend_agents.interpreters.gemma_rewrite import GlossaryItem, rewrite_plain

if not is_available(GEMMA_LOCAL_MODEL):
    raise SystemExit(f"{GEMMA_LOCAL_MODEL} 이 Ollama 에 없음")

ko_text = "엄마 오늘 저메추 좀ㅋㅋ 소개팅은 됐고 나는 자만추 할래. 시험은 망했는데 완전 럭키비키잖아? 원영적 사고 가자"
ko_gl = [GlossaryItem(term="저메추", meaning="저녁 메뉴를 추천해 달라는 말"),
         GlossaryItem(term="자만추", meaning="소개팅이나 앱이 아니라 일상에서 자연스럽게 만나는 연애를 하겠다는 뜻"),
         GlossaryItem(term="럭키비키", meaning="나쁜 상황에서도 '오히려 운이 좋다'고 여기는 태도"),
         GlossaryItem(term="원영적 사고", meaning="어떤 일이든 자기에게 유리하게 해석하는 초긍정 사고방식")]
en_text = "ngl that boat kid is pure aura farming 😭 6-7!! bro is so skibidi"
en_gl = [GlossaryItem(term="aura farming", meaning="repeating cool-looking moves to look impressive on purpose"),
         GlossaryItem(term="6-7", meaning=None),
         GlossaryItem(term="skibidi", meaning="a filler word with no fixed meaning, roughly 'silly' or 'ridiculous'")]

for lang, text, gl in (("ko", ko_text, ko_gl), ("en", en_text, en_gl)):
    for i in range(2):  # 안정성: 두 번 돌려 편차 확인
        t = time.time(); out = rewrite_plain(text, gl, lang); print(f"[{lang} #{i+1} {time.time()-t:.0f}s] {out}")
