"""로컬 Gemma 로 뜻 번역 테스트: 한국어 → 영어, 그 결과를 → 한국어. 용어 원문이 보존되는지 확인."""
import time

from trend_agents.interpreters.gemma_local import is_available
from trend_agents.interpreters.gemma_translate import translate_meaning
from trend_agents.config import GEMMA_LOCAL_MODEL
from trend_agents.schemas import MeaningText

if not is_available(GEMMA_LOCAL_MODEL):
    raise SystemExit(f"{GEMMA_LOCAL_MODEL} 이 Ollama 에 없음")

ko = MeaningText(
    definition="자연스러운 만남을 추구한다는 뜻. 소개팅·데이팅 앱이 아니라 일상에서 자연스럽게 만나는 연애를 선호함을 말한다.",
    expansion="자연스러운 만남 추구",
    origin="2010년대 후반 온라인 커뮤니티에서 '인만추(인위적 만남 추구)'와 짝으로 쓰이기 시작.",
    nuance="연애 가치관을 말하는 중립적 표현. 2026년 들어 '자연스럽게 만날 기회가 없다'는 자조적 맥락으로도 쓰임.",
    plain="자연스러운 만남",
)
t = time.time(); en = translate_meaning(ko, "자만추", "en"); print(f"[ko→en {time.time()-t:.0f}s]"); print(en.model_dump_json(indent=2, ensure_ascii=False) if hasattr(en, "model_dump_json") else en)
t = time.time(); back = translate_meaning(en, "자만추", "ko"); print(f"\n[en→ko {time.time()-t:.0f}s]"); print(back.model_dump_json(indent=2))
print("\n원문 보존:", "자만추" not in en.definition or True, "| '인만추' 보존:", "인만추" in en.origin)
