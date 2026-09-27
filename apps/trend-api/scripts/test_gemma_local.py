"""로컬 Gemma(Ollama) 세대 판정 테스트. 키 불필요, 모델만 있으면 됨."""
import sys
import time

from trend_agents.config import GEMMA_LOCAL_MODEL
from trend_agents.interpreters.gemma_local import is_available, read_generation

model = sys.argv[1] if len(sys.argv) > 1 else GEMMA_LOCAL_MODEL
if not is_available(model):
    raise SystemExit(f"{model} 이 Ollama 에 없음. `ollama pull {model}` 후 재실행")

SAMPLES = [
    "야 그거 완전 럭키비키잖아 ㅋㅋ 원영적 사고 가자",
    "부장님 이번 기획안 킹받네요... 그래도 갓생 살아야죠",
    "어제 모임 재밌었어요. 다음에도 시간 되면 뵙겠습니다.",
    "이거 알잘딱깔센으로 해줘 그리고 오늘 저메추 좀",
]
for s in SAMPLES:
    t = time.time()
    r = read_generation(s, model=model)
    print(f"\n[{time.time()-t:4.1f}s] {s}")
    print(f"   -> {r.detected_generation} (conf {r.confidence:.2f}) slang={r.slang_terms}")
    print(f"      {r.plain_explanation}")
