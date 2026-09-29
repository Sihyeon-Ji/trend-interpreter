# Trend API 작업 규칙

저장소 공통 규칙은 루트 `AGENTS.md`가 우선이다. 이 파일은 `apps/trend-api`(Python API·파이프라인)와 `apps/trend-web`(Next.js 화면)에만 적용한다.
대회 요건·배점·마감은 `docs/대회/대회-브리프-원문.txt`, 방향은 `docs/트렌드/방향.md`, 설계 근거는 `docs/트렌드/조사/` 를 먼저 읽는다.

## 규칙

- Python 3.12, `uv` 로만 실행 (`uv run ...`, `uv add ...`). 전역 pip 사용 금지.
- `src/trend_agents/schemas.py` 가 파이프라인 계약이다. 수집·해석 모델(ShortsVideo, ShortsInterpretation…)과 사전 모델(Term, Meaning, Evidence, Segment)이 여기 있다. 필드를 바꾸면 Gemini `response_schema`, Ollama `format`, PostgreSQL 표, Spanner DDL(`storage/spanner_graph.ddl.sql`) 에 동시에 영향 → 바꾸기 전에 전부 확인.
- **판정은 데이터, LLM 은 서술.** 생애주기(`lifecycle.py`), 검증 상태(`verification.py`), 재검증 주기는 규칙 코드가 정한다. LLM 출력에 "검증됨" 같은 상태를 직접 쓰게 하지 않는다.
- 사전에는 검증 게이트를 통과한 Meaning 만 verified 로 들어간다. 뜻이 바뀌면 새 version 을 만들고 이전 version 의 `valid_to` 를 닫는다. 삭제하지 않는다.
- API 키는 `apps/trend-api/.env` 만. 코드·문서·커밋에 절대 넣지 않는다. `config.require()` 로 읽는다.
- **Gemini 클라이언트는 `model_client.client()` 한 곳에서만 만든다.** API 키를 쓰지 않고 Vertex AI(런타임 서비스 계정, `GCP_PROJECT_ID`)로 접속하며, `MODEL_PROVIDER=vertex`와 `MODEL_REQUESTS_ENABLED=true`가 모두 켜져야 호출한다. 로컬 기본값(mock)에서는 유료 모델을 호출하지 않는다.
- 관계형 데이터는 모두 PostgreSQL 이다(`DATABASE_URL`). 저장소 함수는 `storage/db.py` 어댑터를 통해서만 SQL 을 보내고, `?` 자리표시자와 `INSERT OR REPLACE/IGNORE` 를 그대로 쓴다(어댑터가 `ON CONFLICT` 로 바꾼다). 표를 추가하면 DDL 에 기본키를 적어야 REPLACE 가 동작한다.
- 기존 표의 변경·데이터 보정은 `storage/migrations/NNN_설명.sql` 새 파일로만 한다. 적용된 파일은 고치지 않는다(checksum 이 달라지면 연결을 거부한다).
- API 는 `db.pool()` 의 연결을 요청마다 빌려 쓴다. 응답 뒤에도 도는 작업(스트리밍 등)은 `db.session()` 으로 따로 빌린다. 이벤트 루프에서 연결을 기다리지 않는다.
- 로그는 `logging` 으로 표준 출력에만 낸다(`logging_setup.configure`). 파일 로그를 새로 만들지 않고, 사용자 문장·모델 출력·비밀값을 로그에 넣지 않는다.
- 사람이 쓴 문장을 저장하는 표는 보존 기간을 둔다. 해석 캐시 7일, 미해결 질문 30일(`prune_user_text`).
- `data/`, `*.db`, `*.zip` 은 커밋하지 않는다.
- 새 데이터 소스는 `collectors/`, 모델 호출은 `interpreters/`, 저장은 `storage/`, ADK 에이전트는 `agents/`. 단계별 실행 스크립트는 `scripts/test_*.py` 로, 키가 없으면 `SystemExit` 메시지로 안내하고 죽는다.
- 모델 ID 는 `config.py` 상수만 쓴다. 현재 `gemini-3.8-flash`, `gemma4:12b`(Ollama, `think=False`).
- 영상은 URL 만 저장, 파일로 받지 않는다 (저작권).
- 문서는 한국어. 제출물(README 최종본·덱·영상)만 영어.
- 이 저장소 밖으로 나가는 작업(GCP 리소스 생성, 배포, 결제)은 사용자 확인 후.

## 프론트 (`apps/trend-web/`)

- 디자인은 비공개 디자인 문서(`design/Notion/DESIGN.md`, 저장소에 넣지 않음)의 '앱' 쪽만: 흰 바탕·검정 글자·hairline·검정 primary 버튼. 파스텔 틴트, 색 띠, 글리프, 카드 그림자, 큰 마케팅 제목은 쓰지 않는다 (사용자 결정, `docs/트렌드/프론트엔드.md`).
- **이용자 화면과 관리자 화면(`/admin`)을 분리한다.** 이용자 화면에 에이전트·게이트·확신도·판 수 같은 내부 용어를 내지 않는다. 관리자 화면도 쉬운 한국어로.
- **익명은 설정을 갖지 않는다.** 지도·사전·해석은 로그인 없이 열리고 설명은 중립으로 나간다(재작성 캐시도 하나로 모인다). 세대·나라 설정은 로그인한 사람의 계정에 저장된다(`/me`, `reader_prefs`).
  `proxy.ts`(Next.js 16의 proxy 규칙): `/me` 는 로그인, `/admin` 은 그중 검수자(`session.reviewer`). 아니면 `/login` 또는 `/me?denied=review`.
  브라우저는 백엔드에 직접 쓰지 않는다 — 같은 사이트의 `app/api/prefs`·`app/api/review/[termId]` 가 세션과 권한을 확인하고 서버만 아는 `FRONTEND_API_TOKEN` 을 붙여 넘긴다. 저장 값은 `lib/reader.ts` 의 화이트리스트로 한 번 거른다. 결정한 사람 이름도 세션에서 가져오므로 검수 기록이 실제 계정이 된다.
  계정은 `.env` 의 `ACCOUNTS`(JSON, PBKDF2 해시) — `scripts/set_account.py` 로 만든다. 평문 비밀번호는 출력에 한 번만 보여 주고 파일에 남기지 않는다. 나중에 Firebase Auth 로 갈 때는 `auth.check_account` 와 `app/api/auth/login/route.ts` 두 곳만 바꾸면 세션·미들웨어·저장 구조는 그대로다.
- 화면 문구는 `lib/i18n.ts` 에 한국어·영어를 함께 넣는다 (키 누락은 타입 에러). 데이터 라벨은 `lib/labels.ts` 의 `L(locale)`. **유행어 원문은 번역하지 않는다**; 뜻·유래·뉘앙스만 `MeaningText` 로 언어별 보관하고, 번역은 백엔드 로컬 Gemma(`interpreters/gemma_translate.py`)가 만든다.
- `lib/contract/types.ts` 는 생성 파일이다. `schemas.py` 를 바꾸면 `apps/trend-api`에서 `uv run scripts/export_schema.py` 를 실행한 뒤 `apps/trend-web`에서 `pnpm contract` 로 다시 만든다. 손으로 고치지 않는다.
- 화면은 `lib/data.ts` 의 함수만 부른다. 예시 데이터는 `lib/sample/`, 실데이터는 서버 환경변수 `DATA_MODE=api`와 `TREND_API_URL`(둘 다 브라우저에 나가지 않는다).
- 해석 조립(`lib/explain.ts`)은 규칙 기반 매칭만. '쉽게 풀어 쓰면' 재작성은 단어 치환 금지 — 서버에서 로컬 Gemma(`interpreters/gemma_rewrite.py`)가 사전 뜻을 참고해 문장을 다시 쓴다. LLM 호출을 프론트에 넣지 않는다.
- **지도가 첫 화면(`/`)이고 제품의 큰 틀**(09-16 결정, 예전 `/map` 링크는 `/` 로 넘긴다. 메시지 해석은 `/explain`)이고 사전·메시지 해석은 그 안의 부품이다 (사용자 비전 09-14). 지구는 `globe.gl`(3D, 화면에서만 `import()`)로 `components/globe/trend-globe.tsx` 한 곳에 가두고, 상태·패널·비교표는 `components/trend-explorer.tsx` — Google Maps/Earth 는 결제 계정이 필요해 보류. 핵심 정보 구조는 **주제(Topic) + 나라별 변형(TopicVariant: 현지 이름·무엇이 달라졋나·현지 밈·엮인 현지 트렌드)**, 뷰 모델 `lib/trends/types.ts`(계약 미반영), 예시 `lib/sample/trend-board.ts`. 말풍선 오프셋은 `.globe-anchor` 안에서만(렌더러가 바깥 transform 을 덮어씀). `prefers-reduced-motion` 존중. 일반 페이지는 `components/page-shell.tsx` 로 960 컨테이너를 감싼다(루트 레이아웃은 전폭).
- 패키지 매니저는 `pnpm`. 새 shadcn 컴포넌트는 `pnpm dlx shadcn@latest add <name>`.

## 파이프라인 (`src/trend_agents/pipeline/`)

- 단계는 `run(con) -> {이름: Result}` 하나씩, 입력·출력은 PostgreSQL 표. 순서 collect → classify → spikes → interpret → candidates → spot → namu → hunt → research → crosscheck → track → risk → naver → translate → fit → topics → board → dashboard (`scripts/run_pipeline.py`, `--loop` 로 상시). 자세한 것은 `docs/트렌드/파이프라인.md`.
- **파이프라인의 Gemini 호출은 `pipeline/gemini.py` 를 거친다** (하루 예산 `GEMINI_DAILY_BUDGET`, 503/429 재시도, `GEMINI_FALLBACK_MODEL` 폴백). 클라이언트는 `model_client.client()` 만 쓰고 단계 안에서 `genai.Client` 를 직접 만들지 않는다.
- 단계는 예외를 삼키고 `pipeline_runs` 에 `error`/`zero` 로 남긴다 — 한 단계의 실패가 다음 단계를 막지 않는다. 결과 dict 는 `with stage()` 블록 **밖에서** 돌려준다.
- **밈 정보는 커뮤니티 위키에서, 뉴스는 번짐을 재는 데(2026-09-28 출처 실측).** 한국어는 나무위키(`collectors/namuwiki.py`, `pipeline/namu.py`)가 사실상 표준이다 — 표제어 14개 중 13개에 문서, 문서마다 수정 시각. 실시간 검색어·분류:유행어로 발굴하고, 문서가 고쳐지면 다시 조사한다. CC BY-NC-SA 라 **본문을 저장하지 않고** 짧은 발췌·링크·시각만 근거로 쓴다. 넘겨받은 문서가 다른 것이면('샤갈'→'마르크 샤갈') 유행어 단서가 있는 문장만 받는다.
  GDELT 는 밈을 찾는 데 약하다(3시간 2만 건 뉴스 제목에 표제어 0번). Context 2.0(`collectors/gdelt_context.py`, 16초 간격·72시간)으로 이미 아는 말의 실제 쓰임 문장만 가져온다. DOC 2.0 은 429, GEO 2.0 은 내려감.
- **사전은 참고 문서가 있는 밈만, 커뮤니티·SNS 글은 지표로만(ADR 0003, 2026-09-29 사용자 결정).** 자동 등재는 나무위키·위키백과·Know Your Meme·pixiv 백과·萌娘百科에 표제어가 든 문서가 있을 때만(`verification.reference_doc`), 없으면 사람 검수로만 싣는다. 디시·더쿠·네이버 카페/지식iN·Bluesky·Reddit 같은 글은 생애주기·순위·리스크를 재는 데만 쓰고 이용자에게 제목·인용·링크·사이트 이름으로 내지 않으며(`collectors.community.is_community_post`), 모델 프롬프트에도 내용 없이 건수만 넣는다(`community.for_prompt`). 리스크 이유도 기사·영상만 인용한다.
- **문서 대조(`pipeline/crosscheck.py`, Plan 12)는 실린 뜻을 참고 위키와 맞춰 보고 검수 큐에 제안만 올린다 — 상태·뜻은 바꾸지 않는다.** '문서 없음' 은 규칙(`verification.reference_doc`)이, 일치·고칠 것·위키끼리 다름·밈이 아님은 로컬 Gemma 가 제안하고(모델이 없으면 건너뜀), 전수조사 결과는 `scripts/crosscheck_dictionary.py import` 로 가져온다. 검수 큐는 종류가 있다(`review_queue.kind`: new·correction·conflict·retire) — 문서 대조의 제안이 올라와 있는 동안 지금 뜻은 공개된 그대로이고, 사람이 승인해야 새 판(`verified_human`, 이전 판 `valid_to` 닫음)이 되거나 빠진다. 결정 API 는 `meaning_id`·`kind` 가 대기 중인 제안과 다르면 409. 그 사이 조사는 그 말을 다시 조사하지 않는다. Know Your Meme 수집기는 이용 약관 때문에 기본 꺼짐(`KNOWYOURMEME_ENABLED`) — 켜도 문서 주소와 제목만 남긴다.
- **사람이 승인한 뜻(`verified_human`)은 자동 조사가 덮지 않는다.** 재조사 대상에서 빼고, `research_one` 도 바로 돌아간다. 사람 검수 큐에는 뜻은 멀쩡한데 근거가 모자란 것만 남긴다(`research.needs_human`) — '표현이 아니다'·빈 뜻은 `auto_rejected` 로 닫고 표제어는 그대로 둔다.
- **조사는 `last_seen` 을 바꾸지 않는다**(밖에서 마지막으로 본 때). 사용 기록(`usage`)은 처음 조사 때만 쓴다. spot 에서 한 번만 본 후보는 7일 뒤 `expired`.
- **밈 추천(`pipeline/recommend.py`, Plan 07)은 순위를 규칙이 매긴다.** 요청 때 모델은 한 번: 사진·문구 → 제품 설명(`ProductBrief`, Gemini 우선). 비교는 `fit` 단계가 표제어마다 미리 붙인 닫힌 낱말(`MemeFit`: 느낌·쓰임·분야·말투)과 제품 설명의 같은 낱말 겹침 + 퍼진 정도·생애주기·리스크 가감이다 — 자유 낱말 겹침은 우연만 남았다(라떼 설명에 135개 중 3개, 전부 우연). 사용 자제·저속한 말투는 후보에서 빼고, **이유는 모델이 쓰지 않는다**: 겹친 낱말(점수의 근거)·사전 뜻·그 나라의 국가별 해석(topics 단계, 확신 0.5 이상)으로 화면이 구성한다(2026-09-28 Gemma 로컬 편집 결정). 결과물을 쓸 지역은 `generate.writable`(그 지역에서 쓰이고 그 말의 글자·로마자로 쓴 표기가 있는 곳). 사진은 메모리에서만(Starlette 임시 파일 한도를 올리고 큰 요청은 폼을 읽기 전에 막는다). 모델이 아예 없는 개발 환경만 고정 예시 설명을 쓰고, 모델이 있는데 실패하면 오류로 알린다 — 남의 예시로 추천하지 않는다.
- **만들기(`pipeline/generate.py`, Plan 08)는 요청 때 Gemini 생성 한 번**(다시 만들어도 두 번). 사전 대조 검사는 규칙이다: 고른 밈이 카피에 있나(`mentions`), 욕설·선정(`unsafe`), X 가중 글자 수(한글·가나·한자 2), 제품 설명의 '피할 것'. 걸린 안은 한 번 다시 만들고 또 걸리면 코드(`Dropped.code`)와 함께 뺀다. 다시 만들기가 실패해도 통과한 안은 돌려준다. '쓸 때 조심' 은 검수 화면의 인용문이 아니라 사전 뜻풀이의 주의점·위험 유형으로만 만든다. 이용자 요청의 Gemini 는 모델마다 한 번만 시도하고 기다리지 않으며 429·503 은 요청 장부에서 돌려놓는다. 모델을 부르는 요청은 인스턴스당 동시에 둘(`api.app.MODEL_SLOTS`).
- **못 답한 질문이 다음 조사 거리다(`pipeline/hunt.py`).** 지금 파이프라인은 '밀어내기'라 지금 뜨는 것만 들어온다 — 사람이 물었는데 없던 말은 `lookups` 에 쌓이고, hunt 가 거기서 표현 이름을 뽑아(한글 표기는 원어 표기까지) 표제어로 세우면 research 가 그 이름으로 인터넷을 직접 뒤진다. 판정은 코드가 한다: 질문 원문에 실제로 있는 말만 받고(앵커), 목록 요청·번역 부탁·갈래 낱말·자판 난타는 버린다.
- **자동 저장은 사람의 결정을 덮지 않는다(2026-09-29 검토).** 단계는 시작할 때 읽은 용어를 몇 분 뒤 통째로 저장하므로, `ds.upsert_term(con, t)`(자동)는 저장된 리스크 필드(`RISK_FIELDS`, 사람의 결정 포함)와 '제외'(retired) 상태를 저장된 쪽에서 가져온다. 사람의 결정을 기록하는 곳(검수 API·검토 스크립트)만 `human=True`. 리스크 단계는 `ds.set_risk` 로 리스크 필드만 쓰고, 오래 도는 단계(track·risk)는 저장 직전 용어를 다시 읽어 자기 필드만 바꾼다. 조사는 네트워크 단계 뒤 사람의 승인을 다시 확인한다.
- 후보 → 용어 승격은 규칙(2회 이상 등장 또는 쇼츠 '유행어·노래', 위키 문서가 있거나 사람이 직접 물어본 것은 1회)이고, verified 는 `verification.gate` 만 정한다. 근거 발췌는 용어가 실제로 들어 있는 원문 문장만. 용어가 들어 있는지는 `pipeline/match.py` 의 `mentions()` 로만 판단한다(숫자꼴 용어는 밈 단서가 같이 있어야 함).
- **사전에 묻기(`pipeline/ask.py`)는 도구 호출 루프다** — MCTI `lib/orchestration/query-loop.ts` 패턴. 모델은 `pipeline/tools.py` 의 읽기 전용 도구(lookup_term·search_terms·why_trending·country_trends·term_usage)로만 사전·그래프를 보고, 그 밖의 이야기는 하지 않는다. 마지막 턴에는 도구를 주지 않아 답을 강제하고, 연속 실패는 차단기로 끊고, 잘못된 인자는 실행하지 않고 오류를 모델에 되돌린다. 답하지 못한 질문은 `lookups` 에 쌓여 발굴(spot) 단계의 재료가 된다.
  화면(`/explain`)은 입력을 셋으로 나눈다: '해석해줘' 같은 부탁이면 부탁하는 말을 떼고 본문을 풀어 쓰고, 묻는 말이면 루프로, 그냥 붙여 넣은 메시지면 규칙 매칭 + 근거 카드로.
  **찾기는 느슨하게, 판정은 엄격하게.** `match.loose_key`(반복·된소리 무시)·`strip_particle`(조사 제거)·`keywords`(뜻으로 찾기)는 도구가 항목을 *찾을 때만* 쓴다 — 게이트의 `mentions()` 는 그대로 엄격하다.
  도구를 한 번도 안 부른 답은 사전에 근거하지 않은 말이므로, 코드가 직접 찾아 그 결과로 다시 답하게 한다. 도구가 찾은 것이 있으면 모델이 '없다' 고 말할 수 없다.
- API 는 `api/app.py`(FastAPI). 응답 뷰 모델은 `pipeline/views.py` — 프론트 `apps/trend-web/lib/types.ts` 와 1:1 로 유지한다. `/explain` 은 용어 id 와 재작성 문장만 돌려주고 문장 조립은 프론트가 한다.
- 테스트: 저장소 루트에서 `docker compose run --rm --build check` 가 이 패키지의 pytest도 실행한다. 직접 돌릴 때는 PostgreSQL 을 가리키는 `DATABASE_URL` 을 주고 `uv run --project apps/trend-api --locked pytest -q apps/trend-api/tests`. 규칙·저장소·보드는 네트워크 없이 인메모리 SQLite 로 테스트한다.

## 로컬 인프라

일상 개발은 저장소 루트의 `docker compose up -d` 로 API(8000)와 웹(3000)을 띄운다(`docs/개발환경/개발-명령어.md`). 아래는 로컬 모델·Spanner 실험이 필요할 때만 호스트에서 켠다.

```bash
ollama serve                       # 로컬 Gemma (brew ollama ≥ 0.34)
docker start spanner-emu || docker run -d --name spanner-emu -p 9010:9010 -p 9020:9020 gcr.io/cloud-spanner-emulator/emulator
```
로컬 모델 호출은 `interpreters/local_chat.py` 한 곳. `LOCAL_LLM_BASE_URL` 이 비면 Ollama, OpenAI 호환 서버(vLLM) 주소면 그쪽 — 스키마는 프롬프트에 넣고 응답 JSON 을 꺼내 검증한다(서버 스키마 강제에 기대지 않음, Ollama 0.20 실측·vLLM guided decoding 크래시 전례). ADK 에이전트 자신의 모델은 기본 Gemini, `ADK_MODEL=local` 이면 같은 로컬 모델(LiteLLM, `agents/team.py`).

Spanner 에뮬레이터는 인메모리다. 재시작하면 사전이 비워진다. 지속 데이터는 PostgreSQL(로컬 Compose `db`, 운영 Cloud SQL)에만.

## 심사 기준 상시 체크

기술 40 / 임팩트 25 / 혁신 25 / UX 10. "조회·요약에서 끝나는 챗봇"이 되지 않게: 실행 단계, 사람 승인 지점(검수 큐), 근거 인용, 버전 이력, eval 표를 유지한다. UI 에 과투자하지 않는다.
