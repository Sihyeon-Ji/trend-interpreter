# Gemma 파인튜닝·고도화 연구 데이터 요청 (초안)

작성일 **2026-10-01** · 상태 **수집 서버에서 10-01 10:35 에 한 번 뽑음(아래 '10-01 실행 결과'), Kaggle 게시는 대기** · 관련 [Plan 06](../plans/archive/06-gemma-on-cloud-run-gpu.md) · [Plan 16](../plans/archive/16-wiki-meme-catalog-and-tendency.md)

수집 서버 담당 팀원에게 부탁하는 데이터 목록이다. 실데이터는 **수집 서버의 DB**에만 있고 개발 PC의 DB는 비어 있거나 예시다. 뽑은 결과는 Kaggle 비공개 Dataset으로 올려 Kaggle 실험(Plan 06)과 학습 서버 QLoRA에 쓴다.

## 한 번에 뽑기

```bash
cd apps/trend-api
uv run scripts/export_research_data.py --list          # 묶음·표별 행 수만 확인
uv run scripts/export_research_data.py                 # DB 의 모든 표 → artifacts/research_export/<시각>/
uv run scripts/export_risk_sample.py --terms 100       # B-1 리스크 표본 → artifacts/risk_sample/
uv run scripts/audit_dataset.py > data/work/audit_sft.jsonl   # B-2 감사관 학습 데이터
```

`export_research_data.py`는 현재 스키마의 **모든 표**(로컬 기준 41개)를 표마다 `<표>.jsonl`로 뽑고 `manifest.json`(시각·서버 커밋·묶음별 행 수·Gemma 환경)을 남긴다. 아래 C·D의 묶음은 분류일 뿐이고 어디에도 없는 표는 `other`로 나간다. 사용자 문장·설정 표(`explain_cache`, `lookups`, `reader_prefs`)는 `user_text/` 하위 폴더에 따로 둔다. 이 폴더는 Kaggle에 올리지 않고 팀 밖으로 보내지 않으며, 보존 기한(해석 캐시 7일·미해결 질문 30일)이 지나면 지운다. 필요 없으면 `--skip-user-text`로 뺀다. 검수자 이름(`decided_by`, `risk_decided_by`)은 `reviewer-<해시 8자리>`로 바꾼다. 같은 사람은 같은 가명이 되지만 익명화는 아니므로 결과를 공개하지 않는다.

## A. 지금 파이프라인에서 Gemma가 하는 일

| 작업 | 코드 | 결과가 쌓이는 표 |
| --- | --- | --- |
| 근거 문장 리스크 분류(그 뜻인지·뉘앙스·위험) | `pipeline/risk.py` | `evidence_labels`, `terms` 리스크 필드 |
| 뜻 번역(언어판) | `interpreters/gemma_translate.py`, `pipeline/translate.py` | `translations` (`model`: gemma-local / team) |
| 나라별 해석 | `pipeline/topics.py` | `topic_notes` |
| 밈 성격 낱말(느낌·쓰임·분야·말투) | `pipeline/fit.py` | `term_fit` |
| 사전 감사관(뜻이 문서와 맞나) | `pipeline/audit.py` | `audit_log` |
| 문서 대조(일치·고칠 것·밈 아님) | `pipeline/crosscheck.py` | `crosscheck_log`, `review_queue` |
| 쉬운 말로 다시 쓰기 | `interpreters/gemma_rewrite.py` | 저장하지 않음 |
| 사전에 묻기(도구 호출) | `pipeline/ask.py` | 저장하지 않음 |

학습 정답은 **사람의 판정**만 쓴다: 리스크 표본의 `human_*`, `translations`의 `team` 행, 검수 결정, `verified_human` 판, 전수조사 판정. 모델 출력은 비교 기준선이다.

## B. 꼭 필요한 것 (별도 스크립트)

| 순위 | 데이터 | 뽑는 방법 | 부탁 | 쓸 곳 |
| --- | --- | --- | --- | --- |
| ★★★ | 리스크 표본 | `export_risk_sample.py --terms 100` → `risk_sample_*.csv` + `.env.json` | `human_*` 칸(그 뜻인지·뉘앙스·위험·용어 수준)을 **모델 결과를 보지 않고** 채운다. 20용어만이라도 좋다 | 프롬프트 비교, 리스크 QLoRA 정답·평가 세트 |
| ★★★ | 감사관 학습·시험 | `audit_dataset.py`, 그리고 `data/work/crosscheck/audit.json`, `data/work/audit_holdout.jsonl`, `data/work/audit_holdout_labels.json` | 그대로 보낸다 | 12B QLoRA 재현(Plan 16), Kaggle 학습 비교. **참고 문서 본문이 들어 있으므로 반드시 비공개** |
| ★ | 서버 Gemma 환경 | `ollama --version`, `ollama list`, `.env`의 `GEMMA_LOCAL_MODEL` 값만 | `manifest.json`에도 일부 남는다 | 실험 조건 맞추기. 서버가 `gemma4:e4b`로 돈다는 기록이 있어 확인한다 |

## C. 사람 판정과 기준선 (`export_research_data.py`)

| 묶음 | 표 | 왜 필요한가 |
| --- | --- | --- |
| `labels` | `translations` | `team` 행(09-29 기준 약 96개)이 사람 정답, `gemma-local`(약 276개)과 짝지어 번역 비교·학습 |
| `labels` | `review_history`, `review_queue` | 승인·거절된 안의 짝 → 선호 학습(DPO), 감사관 평가 |
| `labels` | `meanings` | 고치기 전 판과 고친 판, `verified_human` 여부 → 틀린 뜻 감지·수정 학습 |
| `labels` | `terms` | 표제어·상태·생애주기·리스크(사람 결정 포함) |
| `model_outputs` | `evidence_labels`, `term_fit`, `topic_notes`, `audit_log`, `crosscheck_log` | 지금 모델이 만든 값. 사람 정답과 대조하는 기준선 |
| `evidence` | `evidences` | 근거 문장·출처·시각. 리스크·감사·밈 판별의 입력 |

## D. 추가 연구 후보

| 연구 | 묶음·데이터 | 기대 효과 |
| --- | --- | --- |
| **Gemini → Gemma 증류** | `distill`: `interpretations`(쇼츠 해석), `research_log`(검색 grounding 조사) | Gemini가 하는 해석·조사를 Gemma가 대신하면 비용이 줄고 오프라인으로 돈다. 대회의 Gemma 활용 근거 |
| **밈인지 판별기** | `negatives`: `candidates`(expired 포함), `terms`의 `auto_rejected`, 그 뜻이 아닌 근거 문장 | 수집 초기에 쓰레기를 거르는 작은 분류기(E2B·E4B) |
| **표기 묶기** | `negatives`: `term_aliases` | 반복·된소리·로마자로 흔들리는 표기를 같은 말로 찾기 |
| **나라별 뉘앙스** | `model_outputs`의 `topic_notes`, `timeseries`의 `mentions_weekly_region` | 같은 밈의 나라별 차이 설명 품질. 서비스의 핵심 차별점 |
| **생애주기 예측** | `timeseries`: `mentions_weekly`, `term_timeline` | Gemma 학습보다 시계열 연구. 언제 뜨고 지는지 |
| **도구 호출(사전에 묻기)** | `scripts/eval_chat.py` 질문 세트 + 도구 호출 기록(새로 남겨야 함) | `/ask` 루프의 함수 호출 정확도 학습·평가 |
| **추천·생성 평가** | `scripts/eval_recommend.py` 결과 20개 사례 + 사람 적합도 점수 | 추천 근거·카피 품질의 사람 평가 세트(Plan 09) |
| **멀티모달** | `term_media`(URL만), 쇼츠 해석 | Gemma 4 이미지 입력으로 밈 그림 이해. 저작권 때문에 파일은 받지 않는다 |

도구 호출 기록, 추천 사람 점수, `term_media`는 지금 스크립트에 없다. 필요해지면 따로 만든다.

## 지킬 것

- **사용자 문장 표는 `user_text/`에만 둔다.** `explain_cache`, `lookups`, `reader_prefs`는 함께 뽑히지만 Kaggle Dataset·학습 데이터에 넣지 않는다. `lookups`로 연구할 때는 원문 대신 뽑아낸 표제어 이름만 쓴다.
- **커뮤니티 글**(디시·더쿠·Reddit 등)은 학습 입력으로 써도 결과물에 인용하지 않는다([ADR 0003](../adr/0003-사전-등재-기준.md)).
- **나무위키(CC BY-NC-SA)** 발췌와 참고 문서 본문이 들어 있으므로 공개 Dataset·공개 모델로 내보내지 않는다.
- 결과는 Git에 커밋하지 않는다(`artifacts/`, `data/`). Kaggle에는 **비공개 Dataset**으로만 올리고 필요한 팀원만 Collaborator로 더한다.
- 뽑을 때마다 `manifest.json`의 시각·커밋을 Dataset 버전 메모에 적는다.

## 10-01 실행 결과 (수집 서버 192.168.100.22)

수집 서버는 아직 트윈 저장소(SQLite `data/trend.db`)로 돈다. 같은 스크립트를 트윈의 `scripts/`에 두고 돌렸다(트윈 커밋 `791664b`). 결과는 그 서버의 `~/trend/artifacts/`에 있고 Git·Kaggle에는 아직 올리지 않았다.

| 무엇 | 파일 | 양 |
| --- | --- | --- |
| C·D 전체 표 | `research_export/20261001_1034/` (+ `manifest.json`) | 43개 표, 193 MB. 표제어 7,623 · 뜻 판 8,431 · 근거 문장 29,314 · 번역 292 · 검수 기록 107 · 검수 대기 3,089 · 감사 기록 1,490 · 문서 대조 164 · 근거 분류 2,142 · 조사 기록 8,410 · 주간 언급 91,714 · 위키 월별 조회수 25,481 |
| 에이전트 기록(새 묶음 `agent`) | 같은 폴더 `agent_trace`·`content_*` | 위키를 직접 읽은 조사 에이전트의 걸음 287 · 찾은 밈 94 · 나라 사이 짝 9 – '도구 호출' 연구의 첫 기록 |
| B-1 리스크 표본 | `risk_sample/risk_sample_20261001_1035.csv` + `.env.json` | 용어 100 · 문장 954 · 수준 사용 자제 12 / 주의 30 / 없음 29 / 보류 29. `human_*` 는 빈칸 |
| B-2 감사관 | `audit/` | `audit_sft_v5.jsonl`(371줄: 학습 319·시험 32·시험2 20, 정답은 Claude 판정) · `audit_labels_sonnet.json`(220) · `audit_sft.jsonl`(전수조사 판정판) · `audit_holdout*` · `audit.json`. **참고 문서 본문이 들어 있다 – 비공개** |
| B ★ Gemma 환경 | `gemma_env.json` | 아래 |

**서버 Gemma 환경.** 파이프라인의 로컬 모델(`GEMMA_LOCAL_MODEL`)은 **`gemma4:e4b`**(digest `c6eb396dbd59`, Ollama 0.34.0)다 – 리스크 표본의 `.env.json`도 e4b 다. Kaggle 첫 실행의 `gemma4:12b`(`6114515d63c1`)는 이 서버에도 같은 digest 로 있지만 파이프라인 기본값이 아니므로, 서버와 비교하려면 노트북을 e4b 로 돌리거나 서버 표본을 12B 로 다시 분류해야 한다. 감사·조사 에이전트는 학습 서버(192.168.100.23, Ollama 0.34.0)의 `gemma4:12b`(`4eb23ef187e2`, 22 와 digest 가 다르다)와 QLoRA 판 `trend-audit:12b-v5`를 쓴다.

**스크립트 고침(10-01).** 모든 표 목록을 PostgreSQL 의 `information_schema` 로만 읽어 SQLite 에서 죽던 것을 둘 다 읽게, 결과 폴더를 트윈·팀 어느 쪽에서 돌려도 저장소 루트로, 검수자 가명 바꾸기에서 사람이 아닌 단계 이름(`team`·`audit`·`gate` 등)은 그대로 두게 했다(모두 가명이 되면 사람 결정과 자동 결정을 가를 수 없다). 묶음에 `agent`·`catalog`·`term_pageviews` 를 더했다. 트윈에는 `term_aliases`·`term_timeline` 이 없어 표에 없다(별칭은 `terms` 안에 있다).
