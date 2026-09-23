# 06 · MCTI(threat-overview-standalone)에서 가져올 것 (2026-09-15)

위치 `~/MCTI/threat-overview-standalone` — Next.js 14 해양 사이버 위협 인텔리전스 플랫폼. 같은 GPU 의 vLLM(Qwen3.6-35B-A3B-FP8 `:11437`, bge-m3 `:11438`)을 상시 서비스로 쓴다.
도메인은 다르지만 "LLM 을 배치 파이프라인에 넣고 조용히 망가지지 않게 하는" 문제를 6개월 먼저 겪었고, 그 흔적이 코드 주석에 실측 날짜와 함께 남아 있다.

## 이번에 바로 적용한 것 → `interpreters/local_chat.py`

| MCTI | trend-agents | 근거 |
|---|---|---|
| `lib/llm-client.ts` — Provider(ollama/vllm) 를 환경변수 한 줄로 전환, 기본 no-think | `LOCAL_LLM_BASE_URL` 비면 Ollama, 있으면 OpenAI 호환. Gemma `think=False`, Qwen `enable_thinking=false` | Qwen3.5+ 는 thinking 이 길어져 max_tokens 를 사고로 소진(08-28 실측) |
| `response_format`(guided decoding) 절대 미전송 | vLLM 경로에 `response_format` 없음. 스키마는 프롬프트에, 검증은 pydantic, 틀리면 1회 재질문 | vLLM 0.10.1 + Qwen FP8 에서 CUDA illegal memory access → EngineCore 사망(2026-06-11, 100건 동시 배치) |
| `extractJSON()` — 본문에서 `{...}` 만 추출 | `extract_json()` — 코드 펜스 제거 + 첫 객체/배열 | Ollama 0.20.7 + gemma4:e4b 는 `format` 을 무시하고 펜스·키 이름 변경(09-15 실측) |
| `reasoning_content` 폴백, `finish_reason=length` 면 실패 처리 | 동일 | 잘린 영어 CoT 가 번역·DB 에 유입되는 것 방지 |

## 다음에 참고할 것 (우선순위)

1. **`lib/ai-quality.ts` — AI 산출물 상시 품질 감시.** 2단: ① 결정론 체크(LLM 0회) — 최근 24h 산출물에서 혼입률·적체율·포기율을 SQL 로, ② canary — 정답이 고정된 문제 6개를 실제 호출 경로로 24h 마다. 배경: 모델 교체 후 한자 혼입 3~5배가 됐는데 사흘간 아무도 몰랐다.
   → trend: `docs/EVAL.md` 표를 자동화. 후보 지표: 번역 결과의 용어 원문 보존율, 재작성이 사전 문구를 그대로 붙인 비율(오늘 Qwen 에서 관측), spot 후보 중 `mentions()` 통과율. Gemma↔Qwen↔Gemini 를 바꿀 때 회귀를 바로 잡는다.
2. **`lib/translation-guard.ts` — 번역 환각 가드.** 번역문에 나온 고위험 엔티티는 원문(별칭 포함)에 앵커가 있어야 하고, 없으면 그 번역을 버린다. 판정은 문자열 대조 — LLM 에게 자기 번역을 검증시키지 않는다. 앵커는 넉넉하게(틀리는 방향이 "멀쩡한 번역을 버림"이 되도록).
   → trend: `gemma_translate` 결과에 용어 원문·인용된 다른 유행어·플랫폼·연도 보존 검사. `pipeline/match.mentions()` 가 이미 같은 철학이다.
3. **`lib/label-honesty.ts`, `lib/threat-actor-guard.ts` — 판정은 데이터, LLM 은 서술.** LLM 의 타입 주장은 속성으로만 남기고, 라벨은 정본 목록 일치·구문 규칙으로만 준다.
   → trend `verification.gate` 와 같은 원칙. 후보 kind(유행어·밈·노래·챌린지) 도 LLM 분류를 그대로 믿지 말고 근거 수·출처 다양성으로 승격.
4. ~~**`lib/orchestration/query-loop.ts` — 도구 호출 루프.**~~ → **09-16 적용 완료** (`pipeline/ask.py` + `pipeline/tools.py`). MCTI 챗봇은 껍데기가 아니라 자기 데이터(Neo4j 9곳·PG·SQLite·임베딩 의미검색)를 7개 도구로 읽는 에이전트다 — 그 구조를 그대로 가져왔다. 우리 도구는 검증된 사전과 급증 설명·보드를 읽고, 사전에 없으면 모른다고 답한 뒤 그 질문을 `lookups` 에 남긴다. 가져온 것: 마지막 턴 도구 제거, 연속 실패 차단기, 전체 시간 예산(80% 지점에서 중단), 잘못된 도구 인자는 실행 대신 모델에 피드백.

5. **`lib/correlation-agents.ts` — 다중 에이전트 상관분석.** messages+tools → tool_calls → 실행 → 피드백 → 반복. circuit breaker(연속 실패 시 도구 비활성), 긴 대화 압축, 폴백(의도 기반 도구 선택 → 병렬 실행 → 합성).
   → trend `agents/team.py` 는 ADK SequentialAgent 로 도구=결정론 단계라 구조는 이미 맞다(09-15: `ADK_MODEL=local` 로 에이전트 모델도 로컬 전환 가능, LiteLLM). 가져올 것은 circuit breaker(한 단계가 연속 실패하면 건너뛰고 `review_queue` 에 알림)와 예산 소진 시 폴백 보고(이미 `_budget_guard` 로 절반은 있음).
6. **큐 분리(`chatLimit` vs `backgroundLimit`).** 배치가 100건을 던지면 인터랙티브 응답이 200초 뒤로 밀렸다.
   → `/explain` 재작성(사용자 대기)과 `translate`/`spot`(배치)이 같은 로컬 모델을 쓰면 같은 문제. Ollama 는 순차 처리라 더 심하다. `--loop` 와 API 를 같이 띄울 때는 배치 단계를 야간으로 몰거나 배치만 vLLM(continuous batching)으로.
7. **`scripts/with-vllm.sh` — 앱 라이프사이클이 모델 서버를 내리지 않게.** 과거 dev 종료마다 `compose down` 이 임베딩 컨테이너를 지워 12일 무음 정지.
   → trend 는 Ollama/vLLM 을 소유하지 않으므로 "있으면 쓰고 없으면 Gemini" 인 현재 방식 유지. 상태 확인은 `local_chat.available()` 한 곳.
8. **`lib/daily-brief.ts`** — KST 달력일 기준 하루 1회 idempotent 생성, 저신뢰 소스 블랙리스트를 수집이 아니라 요약 입력에서만 배제.
   → `board`/`topic_notes` 를 일별로 남길 때 참고.

## 이 머신에서의 로컬 모델 실측 (09-15, RTX 6000 Ada 48GB — MCTI vLLM 이 44GB 점유)

| 백엔드 | 속도 | 한국어 유행어 품질 | 비고 |
|---|---|---|---|
| Ollama `gemma4:e4b` (100% GPU, 3.4GB) | 배치 6.1초, 126 tok/s | 럭키비키·알잘딱깔센·저메추 뜻 정확, 재작성 자연스러움 | 대회 필수 기술(Gemma) 충족. **기본값** |
| Ollama `gemma4-26b-a3b` (100% GPU, 17GB) | 배치 5.9초, 136 tok/s | e4b 보다 나음(자만추의 '인위적 만남' 대비까지 살림) | 여유 VRAM 이 1GB 만 남는다 — 박스가 한가할 때만 |
| vLLM `gpt-oss`(Qwen3.6-35B-A3B-**AWQ**, MCTI 공유) | 137 tok/s, 12동시 894 tok/s | 럭키비키=행운의 비키니, 원영적 사고=드라마 등 오답 | 배선 확인·빠른 반복용. 제출물에는 쓰지 않음 |
| Gemini | 무료 등급 모델당 하루 20회 | 영상 해석·grounding 전용 | `pipeline/gemini.py` 예산 가드 |

**09-16: MCTI vLLM 을 FP8→AWQ 로 바꿔 VRAM 13.6GB 를 회수했다.** FP8 이 44.5GB 를 잡고 있을 때 Gemma 는 CPU 66% 로 밀려 배치가 22초~3분 37초로 흔들렸고, 그래서 classify·research 가 실패했다. AWQ 는 28.9GB 만 쓰고 오히려 더 빠르다(단일 +37%, 12동시 +88%) — MoE 디코드가 메모리 대역폭에 묶여 있어서다. 품질은 compat 6/6 과 한국어 픽스처 9문항 모두 동등. 실측·롤백은 `~/MCTI/threat-overview-standalone/scripts/_llm-ab/ROLLBACK.md`.

## 하지 말 것

- `vllm-mcti-embed` 컨테이너는 건드리지 않는다 (12일 무음 정지 이력). `vllm-mcti-chat` 은 09-16 에 AWQ·util 0.62 로 바꿨다 — 더 내리면 KV cache 가 얇아진다(시작 로그의 'GPU KV cache size' 가 10만 토큰 아래면 0.66).
- 공유 vLLM 에 `response_format` / `guided_json` 전송 금지.
- Ollama 는 다른 프로젝트(sda-*, allblue, mcti-classifier)도 쓰는 공용 서버 — 버전 업그레이드는 확인 후.
