# 04 · 살아있는 사전(지식 그래프)과 상시 리서치 에이전트 (2026-09-14)

질문: "트렌드는 빨리 바뀌는데 어떻게 따라가나? 위키/사전처럼 검증된 것만 쌓고, 에이전트가 계속 추적·검증해서 그것만 답하게 할 수 없나?"
답: 그게 이 제품의 핵심 자산이다. 트렌드 DB 를 '해석 결과 로그'가 아니라 **버전 이력이 있는 검증된 사전** 으로 만들고, 에이전트 4개가 그 사전을 돌본다.

## 1. 빠르게 바뀌는 것을 따라가는 방법 — 에이전트 루프

```
① 발견 (6h)        쇼츠 해석 결과의 memes[] · 뉴스 제목 · 데이터랩 급상승어 → 후보 용어
                    · 대표형/변형 정규화, 임베딩 유사도로 기존 항목과 대조 → 없으면 Term(candidate) + 리서치 작업
② 리서치 (작업 단위) Gemini + Google Search grounding 으로 뜻·풀이·유래·세대·뉘앙스 조사 → MeaningDraft + 출처 URL
                    · 우리 DB 의 1차 근거(등장 쇼츠, 데이터랩 곡선, 뉴스)를 함께 붙임
③ 검증 게이트 (규칙) 독립 출처 ≥2 + 1차 근거 ≥1 + 자기확신 ≥0.5 + 현행 뜻과 무충돌 → verified_auto
                    · 하나라도 실패 → needs_review (사람 검수 큐). 사람이 승인하면 verified_human
                    · LLM 은 '검증됨' 을 스스로 붙일 수 없다 (참고 아키텍처의 라벨 정직성 게이트)
④ 추적 (매일)        주간 언급 수(쇼츠+뉴스+데이터랩) → 생애주기 판정 (규칙): emerging / rising / peak / steady / declining / dormant
                    · 생애주기별 재검증 주기: emerging 2일 · rising 3일 · peak 7일 · steady/declining 14일 · dormant 60일
                    · 새 근거가 현행 뜻과 어긋나면(LLM 판정 "이 쓰임이 저장된 뜻과 같은가?") → Meaning v(n+1) 초안 → ②③ 재진입
                    · 이전 버전은 valid_to 를 닫고 남긴다 (위키 이력)
⑤ 답변 (질의 시)     정확·별칭 매칭 → 임베딩 매칭 → verified 현행 버전만 인용해 답함 + 생애주기·확산 경로 첨부
                    · candidate/needs_review 면 "아직 검증 중" 이라고 말하고 알려진 것만
                    · 없으면 Term(candidate) 생성 + 리서치 작업 큐잉 → "조사 시작했다" 회신
```

핵심 원칙 (참고 아키텍처 MCTI 에서 검증된 것): **판정은 데이터, LLM 은 서술.** 생애주기·검증 상태·재검증 주기는 코드가 정한다. LLM 은 조사하고, 초안을 쓰고, 결과를 설명한다.
코드: `lifecycle.py`(생애주기·재검증 주기), `verification.py`(게이트), `interpreters/gemini_research.py`(② 2단계 grounding), `schemas.py` 사전 계층.

## 2. 저장소 결정 — Spanner Graph + BigQuery, Neo4j 는 쓰지 않음

| 후보 | 장점 | 단점 | 판정 |
|---|---|---|---|
| **Spanner Graph** | 순수 Google. ISO GQL. 벡터·전문 검색 내장. **90일 무료 체험 인스턴스(10GB)가 Graph 포함** → 파이널(12/4)까지 커버. Google 공식 "GraphRAG 참조 아키텍처(Agent Platform + Spanner Graph + Cloud Run)" 와 ADK Graph RAG 코드랩 존재. MCP Toolbox `spanner` 소스로 ADK 연결. 에뮬레이터가 PROPERTY GRAPH·GQL 지원(그래프 알고리즘만 미지원) | GQL 학습 곡선. 체험 후 유료는 월 ~$65. 스키마 DDL 이 Neo4j 보다 장황 | **채택** |
| Neo4j (AuraDB) | 팀의 기존 아키텍처·교훈 재사용. Cypher 성숙. Google 과 GraphRAG 파트너십 | 비-Google 스택 → "Google 도구 활용" 특별상에서 불리. AuraDB Free 는 20만 노드·백업 없음, Pro 월 $65 | 미채택 (교훈만 이식) |
| Firestore + BigQuery | 가장 단순·저렴. Firebase 네이티브 | 그래프 질의 없음(수동 홉). "지식 그래프" 서사 약함 | **폴백.** Spanner 셋업이 2일 넘게 막히면 같은 논리 스키마로 전환 |
| BigQuery 단독 | ADK 내장 BigQuery 도구. GDELT 공개 데이터셋과 같은 엔진 | 대화형 조회엔 느림(초 단위), 버전 이력 OLTP 부적합 | 시계열·분석 전용으로만 |
| Cloud SQL/AlloyDB + pgvector | 팀이 PG 익숙 | 그래프 확장 없음, AlloyDB 비쌈 | 미채택 |

역할 분담:
- **Spanner Graph** — 사전 그래프(Term·Meaning 버전·Evidence·Segment, 엣지 HAS_MEANING·SUPPORTED_BY·VARIANT_OF·USED_BY), 검수 큐, 임베딩(768d, `gemini-embedding-001` 다국어) 벡터 검색.
- **BigQuery** — 조회수 스냅샷·데이터랩 포인트·뉴스 언급 시계열(생애주기 입력), **GDELT 공개 데이터셋**(국가별 지정학 이슈 톤·테마), eval 표. 에이전트는 ADK BigQuery 도구로 SQL.
- 로컬 개발 — 수집 원본은 SQLite(지속), 사전은 Spanner 에뮬레이터(인메모리, 테스트용). GCP 결제 등록 후 무료 체험 인스턴스로 이전.

논리 스키마는 `schemas.py` 에 저장소와 무관하게 정의했고, Spanner DDL 은 `storage/spanner_graph.ddl.sql`, 어댑터는 `storage/spanner_graph.py`. 폴백 시 어댑터만 바뀐다.

## 3. 다른 프로젝트(MCTI) 데이터 소스 중 가져올 것

| 소스 | 판정 | 이유 |
|---|---|---|
| Google News RSS 검색 | ✅ 이미 구현 | 동일 |
| RSS 매체 31개 (해운·사이버·지정학) | 🔁 **수집기 패턴만** | 피드 목록을 국가별 연예·IT·마케팅·커뮤니티 매체로 교체. 수집·중복제거·번역 백필 구조 재사용 |
| **GDELT** | ✅ 채택 (BigQuery 공개 데이터셋 `gdelt-bq.gdeltv2.gkg`) | "뉴스·지정학 이슈" 카테고리의 국가별 톤·테마 지수. Google 스택 안에서 SQL 로 바로 조인. 15분 갱신 |
| X 키워드 검색 (미러 사이트 브라우저) | ⚪ 내부 신호로만, 후순위 | 유행어 속도 신호로는 최고지만 ToS 회색지대. 제출물·덱에는 넣지 않음 |
| Telegram 공개 채널 | ❌ | 한국·일본 Z세대 밈 유통 경로가 아님 |
| ACLED · UCDP · HAPI · Polymarket | ❌ | 분쟁·인도주의·예측시장 — 테마 밖 |
| AIS · NGA · UKMTO · USNI · JMIC | ❌ | 해양 |
| NVD · KEV · EPSS · ICS · Feodo · MISP · FOFA | ❌ | 사이버 |
| GDACS · ADS-B/GPSJam | ❌ | 재해·항공 |

가져올 것은 소스보다 **패턴**이다: 30분 크론 오케스트레이터(단계별 step 파라미터), never-throw 브릿지(그래프 동기화 실패가 수집을 멈추지 않음), 인덱스 매핑 배치 JSON, 번역·서술 환각 가드(원문에 없는 고유명사 거부), 조용한 0 감시(어느 단계가 소리 없이 0건이 되는 것을 매일 검사), temporal-correlation(쇼츠·데이터랩·뉴스 spike 정렬), community-detection(밈 군집 + LLM 명명).

## 4. 참고 아키텍처(llm-neo4j-architecture-20260914.zip) 평가

TypeScript/Next.js + vLLM(Qwen) + Neo4j + PostgreSQL 스택이라 코드를 그대로 옮기진 않는다(우리는 Python/ADK + Gemini + Spanner). 하지만 **설계 원칙과 실패 교훈은 그대로 유효**하고, 위 §1·§3 에 이미 반영했다. 세부 리뷰는 아래 §5.

## 5. 참고 아키텍처 리뷰 — 무엇을 가져오고 무엇을 버리나

### 5.1 그대로 가져오는 설계 원칙 (README-ARCHITECTURE·CLAUDE.md 직접 확인)

| MCTI 원칙 | 우리 적용 | 상태 |
|---|---|---|
| **판정은 데이터, LLM 은 서술** — 위험도·분류 임계는 결정론 코드, LLM 은 문장만 | 생애주기·검증 상태·재검증 주기는 `lifecycle.py`/`verification.py`. LLM 은 조사·초안·설명 | ✅ 구현·테스트 |
| **라벨 정직성 게이트** — LLM 이 붙인 라벨(ThreatActor 등)을 레지스트리 일치일 때만 인정. 27,344 → 466 으로 정리한 사고 이력 | `verified` 는 게이트만 부여. 모델 자기확신은 입력값일 뿐 | ✅ 구현 |
| **never-throw 브릿지** — 그래프 동기화 실패가 수집 파이프라인을 멈추지 않음 | Spanner 쓰기는 수집 경로와 분리, 실패 시 로그 + 재시도 큐 | ⬜ 에이전트화 때 |
| **조용한 0 감시** — 어느 단계가 소리 없이 0건이 되는 것이 최악. 매일 결정론 카나리 | 수집·해석·발견·검증 각 단계 일일 건수 카나리 → 0 이면 알림 | ⬜ 3주차 |
| **인덱스 매핑 배치 JSON** — 여러 건을 한 요청에 보낼 때 `i` 와 입력 앞 3단어 `s` 를 되돌려 받아 어긋남 검출 | 쇼츠 10개 배치 해석에서 `url` 을 되돌려 받는 것과 같은 사상. 어긋나면 그 배치 폐기 | ✅ 스키마에 url 포함 |
| **환각 가드(후처리)** — 번역·서술에 원문에 없는 조직·국가가 들어오면 저장 안 함 (앵커 대조 + 고유명사 사전) | MeaningDraft 의 유래·풀이에 근거 텍스트에 없는 고유명사가 있으면 needs_review 로 강등 | ⬜ 게이트 확장 |
| **오늘 날짜(KST) 주입** — "오늘/최근" 질의가 과거로 새는 것 방지 | 답변 에이전트 시스템 프롬프트에 날짜 + 생애주기 기준일 주입 | ⬜ 답변 에이전트 |
| **thinking 기본 OFF** — 3.5+ 세대 모델의 장문 thinking 으로 출력 잘림 | Gemma 4 `think=False` 로 이미 같은 현상 재확인(50s → 7s) | ✅ |
| **신뢰도 = 출처 등급 × 내용 등급, 상한 90~95%** ("100% 는 불가능") | Meaning.confidence 를 출처 수·종류로 계산, 상한 0.95 | ⬜ |
| **스키마 검증 + 안전 바닥** — 파싱 실패·이탈 시 재시도 후 보수적 기본값 | Pydantic 검증 실패 → 재시도 1회 → 그래도 실패면 needs_review | ⬜ |

### 5.2 가져오지 않는 것

- 스택 자체(Next.js·vLLM·Qwen·Neo4j·PostgreSQL·QuestDB·SQLite 4중 저장소). 해커톤은 Gemini/Gemma 필수, Google Cloud 배포 필수.
- vLLM guided decoding 금지 규칙 — Gemini `response_schema` 와 Ollama `format` 은 문제없이 동작함(실측). 이 규칙은 vLLM 특정 크래시에서 나온 것.
- 30분 크론 — 우리 수집은 6시간으로 충분. 리서치 재검증은 생애주기별.
- 도메인 모듈 전부(CVE·선박·위협행위자·해양 트렌드).

### 5.3 코드 계층 상세 리뷰

두 리뷰 에이전트가 코드 계층(`lib/neo4j-*`, `lib/orchestration/*`, `lib/ai-quality.ts`, cron·chat 라우트, `docs/notes/*`)을 읽고 낸 결과를 우리 설계 기준으로 정리한다.

#### 지식 계층 (Neo4j 브릿지·위생·글로서리·knowledge-sync)

| 이식 | 우리 반영 |
|---|---|
| MERGE 규약: `first_seen`/`last_seen`/`mention_count`, `confidence` 는 최대값 갱신, `source` 는 ON CREATE 만(최초 출처 보존) | Term 에 `first_seen/last_seen` 있음. `mention_count` 추가 예정. Spanner 는 PK 가 곧 유니크 제약 → "제약 없는 MERGE 로 쌍둥이 3,277키" 사고 원천 차단 |
| 증거는 **속성 있는 관계**로 (`SUPPORTS {confidence, quote}`) — 속성 0 인 MENTIONS 57.6만 개가 근거 추적 불능이었음 | `MeaningSupportedBy.weight` 있음. `quote`(인용 문장) 컬럼 추가 예정 |
| **앵커 가드**: 용어 문자열이 증거 원문에 실재(`anchor_hit`)할 때만 그 증거를 센다 | ✅ `verification.gate` 에 반영 (용어 앵커 + 풀이 앵커) |
| 검증 = 서로 다른 Source 2개 이상 + 전부 anchor_hit + 최근 창 내. 답변 쿼리는 `status='verified'` 를 **다시** 필터(이중 게이트) | ✅ 게이트 + `lookup_verified` 가 `verification IN (...)` 재필터 |
| 강등은 삭제가 아니라 상태 + `gate_reason` 기록 → 되돌릴 수 있게 | 게이트가 사유 목록 반환. Term 에 `gate_reason` 컬럼 추가 예정 |
| 위생 "저장 영구, 무거운 것만 만료" — 노드·관계 삭제 금지, 오래된 임베딩만 제거 | 버전은 `valid_to` 로 닫고 삭제하지 않음(동일 사상) |
| 3층 dedup: 정규화 일치 → 임베딩 밴드(≥0.88 동일, <0.78 별건) → 모호 밴드만 LLM SAME/DIFFERENT, 실패는 신규 | 발견 에이전트 설계로. 임계값은 임베딩 모델이 다르니(gemini-embedding-001) 실데이터로 재보정 |
| 임베딩: 작성·백필이 **같은 텍스트 빌더**를 써야 한 인덱스에 두 분포가 안 생김. 이중언어는 "kr [SEP] en" | Term 임베딩 텍스트 = "표기. 풀이. 뜻" 한 함수로 고정 |
| knowledge-sync: 지식 계층엔 확정본만, 원본 불변 + 파생은 오버레이, 재임베딩 조건 `embedded_at < updated_at` | Meaning 버전이 오버레이 역할. 재임베딩 조건 채택 |
| glossary: 관측된 **오표기**를 등재해 정본으로 치환(정답만 나열하면 못 잡음). 앵커 있을 때만 적용 | `VARIANT_OF` 에 관측 변형을 쌓는 방식과 동일. 리서치 출력 후처리에 변형→대표형 치환 |

건너뜀: UCO 온톨로지 정렬, Louvain 커뮤니티(소비자 0), temporal-correlation(수작업 키워드 점수 → 데이터랩 곡선으로 대체), SAME_AS/MITRE 정본 연결, SQLite+PG+Neo4j 3중 저장, APOC 병합 위생(제약이 처음부터 있으면 불필요).

#### 오케스트레이션 계층 (LLM 클라이언트·쿼리 루프·품질 감시·cron·chat)

| 이식 | 우리 반영 |
|---|---|
| **검증기 주도 재시도** `callLLMValidated`: 스키마 검증 실패 시 "이전 응답이 검증에 실패했습니다: <사유>" 를 붙여 재시도(2회), 타임아웃·5xx 는 지수 백오프, 연결 거부는 즉시 중단. `safetyFloor`: 결과 수가 이전 대비 급감하면 이전 결과 보존 | Pydantic 검증 + 사유 피드백 재시도를 공용 래퍼로. 발견 에이전트 후보 수 급감 시 이전 결과 유지 |
| 큐 분리: 대화형 vs 배치가 같은 한도를 나누지 않게(배치 100건이 채팅을 200초 밀어낸 사고) | Gemini RPM 을 리서치 배치와 답변 에이전트가 따로 예산. Cloud Run Job(배치) / Service(답변) 분리와 맞음 |
| **컬럼 상태머신 증분 처리**: `attempts` 를 SELECT 직후 선제 +1, 3회 후 영구 스킵, 스킵 표식은 원문 보존 | 리서치 작업 큐에 `attempts`, `skip_reason`. 에이전트는 무상태로 "미처리 & attempts<3" 만 집음 |
| 분류 선행 게이트: 저비용 분류로 후보가 아닌 것을 걸러 비싼 grounding 을 아낌 | ✅ 설계에 있음 (Gemma 로컬 분류 → Gemini) |
| **증거 ≠ 분석물**: 에이전트가 생성한 설명을 다음 답변의 근거로 재사용 금지(순환 참조), 라벨 분리 | Meaning(분석물)과 Evidence(1차 근거)를 노드로 분리해 둔 이유. 답변은 Evidence 만 인용 |
| 인용 파이프라인: 도구가 sources 메타데이터 반환 → dedup → 질의 관련성 재정렬 → 상위 N 소스 카드. 관련 소스 0 → 명시적 unknown + 작업 큐잉 | 답변 에이전트(⑤) 스펙 |
| confidence = 소스 티어 × 내용 신뢰, **상한 0.9**, 단일 소스는 "(미확인)" | `Source.tier` 컬럼 추가 예정. `Meaning.confidence` 계산식 채택 |
| 날짜 주입(KST 오늘) + 기간 필터 강제 — "APT" 질의가 로제 노래 'APT.' 에 매칭된 다의어 사고 | 답변 에이전트 시스템 프롬프트. 슬랭은 다의어가 기본이라 세대·국가 필터를 함께 |
| 드리프트 트리거: 인기 = 직전 7일 평균 대비 1.5× + 2소스 확증 / 의미 = "facts 해시 불일치 시 캐시 무효화" | `lifecycle.RISE_RATIO=1.5` 동일. 의미 변화는 Meaning 핵심 필드 해시로 재검증 트리거 |
| **결과 수 기반 상시 감시** + 실제로 깨졌던 유형만 담은 canary(24h). 알림만, 자동 차단 아님 | 3주차 canary: 단계별 일일 건수 0 · 게이트 통과율 급변 · 임베딩 누락 |
| 피드명 ≠ 발행처 — 애그리게이터 하나가 신뢰도 게이트를 무력화 | **YouTube 채널 ≠ 원작자, 리업로드 ≠ 원 게시일.** 유래 판정에 채널·게시일을 그대로 믿지 않음 |

건너뜀: vLLM 특화(guided decoding 금지·tool-calling 프로브·서킷브레이커) — Gemini `response_schema` 는 정상 동작(실측); 정적 한↔영 사전(다국어 임베딩으로 대체, "단어 경계" 교훈만); 도메인 레지스트리 라벨 게이트(슬랭엔 정본이 없다 → 검증이 사전을 키우는 구조); 자체 컨텍스트 압축(ADK 세션 사용).

#### 문서에 기록된 실패 — 우리가 피할 것

1. 모델 교체 후 품질 회귀(한자 혼입 3~5배, 포기율 27배)가 3일간 무감지, 2,200건 오염 → **결과 수 감시를 첫날부터.**
2. 배치 응답의 인덱스만 믿어 다른 항목 결과가 저장(멕시코 기사에 오하이오 번역) → 우리 쇼츠 10개 배치는 `url` 을 되돌려 받아 대조, 불일치 배치는 폐기.
3. 날짜 미주입으로 2018 사고를 "오늘"로 답변 → 날짜 주입 + 기간 필터 + 데이터 없음 가드 세트.
4. 같은 필드를 쓰는 경로 중 하나만 가드해 다른 경로가 되돌림 → 사전 쓰기는 `spanner_graph.add_meaning` 단일 경로로만.
5. LLM 의 정답 `null` 을 실패로 취급해 93,809행을 3회 재추출 → "해당 없음" 은 유효 결과로 저장.
6. 라벨 변경 후 소비자 코드를 안 고쳐 3만 노드가 조용히 사라짐 → `schemas.py` 의 Literal 을 바꾸면 DDL·게이트·쿼리 전수 확인(CLAUDE.md 규칙).
7. 유니크 제약 없는 동시 MERGE 로 쌍둥이 키 → Spanner PK + `insert_or_update` 로 구조적 차단.

#### 에이전트가 제안한 최소 스키마와 우리 DDL 의 차이

제안: `Term{key, display, aliases[], mention_count, status, gate_reason, lifecycle, embedding}`, `Meaning{gloss, origin, version, valid_from/to, status, confidence, created_by}`, `Evidence{url UNIQUE, kind, excerpt, published_at, anchor_hit, series[]}`, `Source{name, tier}`, 관계 `HAS_MEANING{current}`, `SUPERSEDES{reason}`, `SUPPORTS{confidence, quote}`, `MENTIONS{context}`, `USED_BY`, `USED_IN`, `RELATED_TO{kind}`.
우리 DDL 과 대부분 일치. 반영할 차이: Term 에 `aliases`·`mention_count`·`gate_reason`, `Source{tier}` 노드와 `PUBLISHED` 엣지, `MeaningSupportedBy.quote`, Evidence PK 를 URL 해시로. `SUPERSEDES` 는 `version`+`valid_to` 로 이미 표현되므로 생략. `USED_BY`/`USED_IN` 은 `Segment(세대×국가)` 하나로 합친 현재 방식 유지(확산 경로가 세대×국가 조합으로 나와야 하므로).
