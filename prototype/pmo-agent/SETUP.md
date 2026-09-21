# Echo PMO — 환경 준비 체크리스트 (공모전 환경: Gemini 직결)

목표: **업무 도구를 연결해 프로젝트를 관리하는 에이전트**. 대회 제출 환경 그대로 구성한다.

```
사용자/이벤트 → [우리 에이전트 서비스 · FastAPI]
                   ├─ Gemini (function calling) : 무엇을 할지 판단·설명
                   └─ 툴 어댑터 (우리 코드)
                        ├─ Jira Cloud REST v3   (API 토큰, 샌드박스 사이트)
                        ├─ Kaneo (자체 호스팅)   (선택, 2단계)
                        └─ 스케줄 엔진 (순수 파이썬: CPM·지연 예측)
```

원칙 두 가지:
1. **숫자·일정 계산은 코드가, Gemini는 읽기·판단·설명만** (CRQ에서 검증된 설계)
2. **쓰기는 샌드박스에만.** 회사 실 Jira는 읽기조차 이 프로젝트에서 쓰지 않는다

---

## 0. 현재 상태 (2026-09-20 갱신)

| 항목 | 상태 | 비고 |
|---|---|---|
| Node.js / npm | ✅ v24.11.1 / 11.11.1 | |
| Python | ✅ 3.12 | |
| Docker | ✅ 29.8.0 | 설치 완료 |
| gcloud CLI | ❌ 미설치 | Cloud Run 배포 때 필요 |
| `GEMINI_API_KEY` | ✅ 발급 · 검증 완료 | 모델은 `gemini-3.6-flash` |
| Jira 샌드박스 + API 토큰 | ✅ `dmswisl1017.atlassian.net` / `ECHO` | 시드 40건 생성 완료 |
| ⚠️ 참고 | 이 PC 의 Claude 에 `cytur.atlassian.net`(실서비스) 커넥터가 붙어 있음 | **이 프로젝트에서는 사용하지 않음.** 코드에 도메인 차단 가드 있음 |

### 구현 현황

| 단계 | 내용 | 상태 |
|---|---|---|
| 2-1 | 환경 검증 (`tools/check_env.py`) | ✅ 전 항목 OK |
| 2-2 | 데모 시드 40건 (`seeds/board.py`, `seeds/jira_seed.py`) | ✅ Jira 에 생성됨 |
| 2-3 | 스케줄 엔진 (`schedule.py`) | ✅ 테스트 통과 |
| 2-3+ | **자원 제약 스케줄링 (`capacity.py`)** | ✅ 차별점 |
| 2-4 | Gemini 툴 레이어 (`tools.py`) | ✅ 읽기 6 + 쓰기 제안 3 |
| 2-5 | PMO 루프 + 주간 리포트 | ✅ 1회 완주 |
| 2-5+ | 멀티모달 입력 (`ingest.py`) | ✅ 실검증 (합성 이미지) |
| 2-5+ | 승인 게이트 (`approve.py`) | ✅ 감사 로그 포함 |
| 2-5+ | 웹 서비스 + 데모 UI (`api.py`) | ✅ Dockerfile 포함 |
| 2-6 | Cloud Run 배포 + Vertex AI 전환 | ⏳ GCP 프로젝트 필요 |

전체 사용법은 [README.md](README.md) 를 본다.

> 이 프로젝트는 팀 저장소의 `prototype/pmo-agent/` 로 이식됐다.
> 아래 경로는 전부 그 디렉터리 기준이다.

---

## 1. 직접 만들어야 하는 것 (계정·키는 사람이 발급)

### 1-1. Gemini API 키 ⭐ 필수 · 2분
- [ ] https://aistudio.google.com/apikey → **Create API key**
- [ ] `prototype/pmo-agent/.env` 에 `GEMINI_API_KEY=...` 저장 (`.env.example` 복사해서 사용)
- [ ] 무료 티어로 개발 가능 (`gemini-2.5-flash` 권장, 판단 품질 필요한 곳만 `-pro`)

### 1-2. Jira 샌드박스 사이트 + API 토큰 ⭐ 필수 · 10분
- [ ] https://www.atlassian.com/software/jira/free 에서 **새 사이트** 생성
      - 사이트 이름 예: `echo-pmo-demo` → `echo-pmo-demo.atlassian.net`
      - **회사 계정(ejchoi@cytur.net)이 아닌 별도 이메일 권장** — 조직 정책·실데이터와 분리
      - 무료 플랜(10명)
- [ ] 프로젝트 생성: **Team-managed / Software / Scrum**, 키 `ECHO`
- [ ] API 토큰 발급: https://id.atlassian.com/manage-profile/security/api-tokens → **Create API token**
- [ ] `.env` 에 저장:
      ```
      JIRA_SITE=echo-pmo-demo.atlassian.net
      JIRA_EMAIL=<사이트 가입 이메일>
      JIRA_API_TOKEN=<발급 토큰>
      JIRA_PROJECT_KEY=ECHO
      ```

> 여기까지면 핵심 루프(감지→원인→제안→승인→티켓 갱신→리포트)를 전부 검증할 수 있습니다.

### 1-3. Google Cloud 프로젝트 — 대회 요건 · 20분 (제출 2주 전까지)
- [ ] https://console.cloud.google.com → 프로젝트 생성 (예: `echo-pmo-2026`)
- [ ] 결제 계정 연결 (무료 크레딧 $300)
- [ ] API 활성화: **Cloud Run, Artifact Registry, Vertex AI, Secret Manager**
- [ ] `gcloud` CLI 설치 → `gcloud auth login` (본인 로그인)
- [ ] `.env`: `GCP_PROJECT_ID=`, `GCP_REGION=asia-northeast3`
- [ ] 심사 가점용: Vertex AI 경유 Gemini 호출로 전환(키 → ADC), Agent Engine/Agent Platform 배선은 데모 완성 후

### 1-4. Docker Desktop — Kaneo 자체 호스팅 (2단계, 선택)
- [ ] https://www.docker.com/products/docker-desktop/ 설치
- [ ] Jira만으로 데모가 성립하면 생략 가능. "PM 도구 종속되지 않는다"를 보여줄 때만 필요

### 1-5. 선택 — Slack 무료 워크스페이스
- [ ] 에이전트 보고·승인을 채팅으로 받고 싶을 때. 데모가 웹 UI면 생략

---

## 2. 키가 준비되면 자동으로 진행되는 것 (에이전트 담당)

| 순서 | 작업 | 검증 방법 |
|---|---|---|
| 2-1 | `python tools/check_env.py` (prototype/pmo-agent 에서) — 키 유효성·Jira 인증·Gemini 함수호출까지 실제 호출로 확인 | 전 항목 OK |
| 2-2 | 데모 프로젝트 시드: 태스크 40개, 담당자 4명, 의존관계·스토리포인트·일부 지연 | Jira 보드에 실제 생성 |
| 2-3 | 스케줄 엔진(순수 파이썬): CPM 임계경로·지연 전파·완료 예측 | 단위 테스트 |
| 2-4 | Gemini 툴 레이어: `list_tasks` `get_task` `propose_update` `post_comment` `create_task` — **쓰기 툴은 전부 승인 게이트 뒤** | 툴 호출 로그 |
| 2-5 | PMO 루프: 지연 위험 감지 → 원인 추적 → 담당자 확인 질문 → 승인 → 티켓 갱신 → 주간 리포트 | 데모 시나리오 1회 완주 |
| 2-6 | Cloud Run 배포 + Vertex AI 전환 | 데모 URL |

---

## 3. 안전 가드 (코드에 이미 반영)

- [x] `src/pmo_agent/adapters/jira.py` 에 **도메인 화이트리스트** — `cytur.atlassian.net` 등 실서비스 도메인이면 예외 발생
- [x] 쓰기 함수는 `dry_run=True` 가 기본. 승인 토큰 없이 실행 불가
- [x] `.gitignore` 로 `.env` 커밋 차단
- [ ] 데모 데이터에 실명·실제 고객 정보 사용 금지 (시드 스크립트는 가상 인물 사용)

---

## 4. 남은 일

1-1(Gemini), 1-2(Jira)는 끝났다. 남은 것은 배포 쪽이다.

1. **1-3 Google Cloud 프로젝트** — 제출 요건. `gcloud` 설치 → 프로젝트 생성 → Cloud Run/Vertex AI/Secret Manager 활성화
2. `LLM_BACKEND=vertex` 로 전환해 실호출 검증 (지금은 구조만 준비됨)
3. `docker build` → Artifact Registry → Cloud Run 배포 → 데모 URL 확보
4. 실제 손글씨 사진으로 멀티모달 판독력 재확인 (지금은 합성 이미지로만 검증)

`.env` 에 키를 넣을 때 값 자체를 채팅에 붙여넣지 않는다. 파일에만 저장한다.
