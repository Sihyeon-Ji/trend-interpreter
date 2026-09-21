# pmo-agent — 실현 가능한 일정을 계산하는 PMO 에이전트

`prototype/` 의 독립 후보 프로젝트입니다. 저장소 루트의 개발 스택과 분리되어 있고, 자기 의존성만 씁니다.

**일정 숫자는 코드가 계산하고, Gemini 는 읽고 설명하고, 쓰기는 사람이 승인한 것만 나갑니다.**

---

## 무엇이 다른가

### 1. "가능한 일정"과 "실현 가능한 일정"은 다르다

40건짜리 데모 보드에서 의존관계만 보면 **2026-10-20** 완료입니다. 그런데 담당자별 남은 작업은:

| 담당 | 남은 영업일 |
|---|---|
| 오태경 | **38** |
| 민아름 | 28 |
| 유하늘 | 22 |
| 한서준 | 18 |

오태경 혼자 38영업일치를 들고 있습니다. 22영업일 뒤 완료는 **한 사람이 8건을 동시에 한다는 가정** 위에서만 성립합니다. Jira 도, 대부분의 간트 플러그인도 이 가정을 씁니다.

`capacity.py` 는 "한 사람은 동시에 한 건"을 넣고 다시 계산합니다.

```
의존관계만 반영    2026-10-20
사람 용량까지 반영  2026-11-17   (+20영업일)
병목: 오태경 — 가동률 93%, 이 사람이 비는 2026-11-16 이 하한선

재배치 3건 →      2026-10-29   (13영업일 단축)
  ECHO-27 단위 테스트 보강   오태경 → 한서준   10일
  ECHO-38 모니터링 대시보드  오태경 → 유하늘    2일
  ECHO-34 버그 수정 2차     민아름 → 한서준    1일
```

**"언제 끝나나"가 아니라 "누구 때문에 못 끝나고, 무엇을 옮기면 되나"** 에 답합니다.

### 2. 보드만 봐서는 안 보이는 것

보드는 사람이 적은 상태를, GitHub 은 실제로 일어난 일을 담습니다. 맞대야 보입니다.

```
ECHO-12  완료 처리됐는데 PR #111 이 아직 열려 있다
ECHO-5   진행 중인데 마지막 커밋이 20일 전(2026-08-31)이다
ECHO-14  보드는 '할 일'인데 커밋이 1건 있다
ECHO-15  PR #113 이 10일째 리뷰 대기 중이다 (리뷰어 tk-oh)
```

**근거가 없으면 경고하지 않습니다.** 커밋에 태스크 키를 쓰지 않는 저장소에서는 "커밋이 없다"가 아니라 "연결할 근거가 없다"고 말합니다 — 모르는 것을 경고로 내면 전부 잡음이 됩니다.

### 3. 숫자를 모델이 만들지 않는다

- 일정·지연·임계경로·부하는 전부 `schedule.py` / `capacity.py`(표준 라이브러리만)가 계산합니다
- Gemini 는 툴 응답의 값만 인용하도록 시스템 프롬프트가 강제합니다
- 모델이 지어낸 태스크 키(`ECHO-99`)나 상대 날짜("다음 주 화요일")는 `ingest.validate()` 가 걸러 **사람에게 물을 질문**으로 떨어뜨립니다

테스트로 고정돼 있습니다:

```python
def test_툴_레이어에는_approve_True가_없다(self):
    self.assertNotIn("approve=True", inspect.getsource(tools))
```

### 4. 쓰기는 전부 사람 승인 뒤에

- 모델이 부를 수 있는 쓰기 툴은 `propose_*` 뿐이고 전부 `dry_run` 결과만 돌려줍니다
- 실제 반영은 `approve.py` 한 곳에서만 일어납니다. 모델은 이 모듈을 호출할 수 없습니다
- 번호를 고르고 `yes` 를 한 번 더 쳐야 나갑니다. `y` 로는 전체 승인이 안 됩니다
- 반영된 것은 `logs/approvals.jsonl` 에 남습니다
- 샌드박스가 아닌 도메인으로 쓰기가 시도되면 `WriteBlocked` 로 막고 그 시도까지 기록합니다

### 5. 도구를 여러 개 붙이는 이유

"여러 도구를 한 화면에"는 흔합니다. 여기서 도구를 붙이는 목적은 **한 도구만 봐서는 원리적으로 계산할 수 없는 값**을 얻는 것입니다.

| 도구 | 고유 기여 |
|---|---|
| Jira / 로컬 보드 | 태스크·의존관계·마감 (기준 보드) |
| **GitHub** | 커밋·PR 로 본 실제 진척 → 보드와의 불일치 |
| 캘린더 *(예정)* | 회의 점유 → 실가용 시간 → 용량 계산 입력 |
| Notion *(예정)* | 회의록·의사결정 → 메모 입력원 |
| Teams *(예정)* | 승인 요청을 팀이 있는 곳에서 |

---

## 구조

```
src/pmo_agent/
  schedule.py   CPM 임계경로, 영업일, 지연 전파, 완료 예측   (표준 라이브러리만)
  capacity.py   자원 제약 일정, 병목, 재배치 탐색            (표준 라이브러리만)
  signals.py    보드 상태와 코드 활동 대조                   (표준 라이브러리만)
  report.py     주간 리포트 (모델 미사용)
  ingest.py     메모·사진 → 검증된 변경 제안                 (Gemini 멀티모달)
  tools.py      Gemini function calling 툴 레이어
  approve.py    승인 게이트 — 유일한 쓰기 경로
  llm.py        Gemini 호출·재시도·대체 모델·Vertex 전환
  run.py        에이전트 루프
  api.py        FastAPI 서비스 + 데모 UI
  ports.py      어댑터 인터페이스 (Protocol — mypy 가 강제)
  adapters/     jira · memory (보드) / github · memory_repo (저장소, 읽기 전용)
  seeds/        board · jira_seed · repo (데모 데이터)
```

계산부에 외부 의존성이 없습니다. 그래서 **API 키도 계정도 없이 단위 테스트가 전부 돕니다.**

`ports.py` 의 `Board` / `Repo` Protocol 이 "두 어댑터는 같은 모양"을 타입 검사로 강제합니다. 실제로 이 Protocol 을 넣자마자 `Jira.search` 의 인자 순서가 로컬 보드와 달라 교체 불가능했던 것이 드러났습니다.

---

## 실행

### 계정 없이 (로컬 보드 + 로컬 저장소)

```bash
cd prototype/pmo-agent
pip install -e ".[dev]"          # 또는  uv sync

python -m pmo_agent.seeds.board   # 보드 데모 데이터 40건
python -m pmo_agent.seeds.repo    # 가상 저장소 (어긋난 상황을 의도적으로 심는다)

PMO_BACKEND=memory REPO_BACKEND=memory python tools/demo.py   # 3분 시연
```

가상 저장소에는 네 종류의 어긋남이 심어져 있고, 테스트가 **그것이 실제로 검출되는지** 확인합니다 (`test_심어둔_어긋남이_전부_검출된다`). 시연 전 사전 점검을 겸합니다.

### 실제 Jira + Gemini

`.env.example` 을 `.env` 로 복사해 채웁니다. `.env` 는 커밋되지 않습니다.

```bash
python tools/check_env.py                    # 실제 호출로 전 항목 검증
python -m pmo_agent.seeds.jira_seed --approve  # 시드 40건을 Jira 에 생성
python -m pmo_agent.run "지금 일정이 현실적으로 가능한지 판단해줘"
```

### 웹 서비스

```bash
uvicorn pmo_agent.api:app --port 8080
```

| 엔드포인트 | 내용 |
|---|---|
| `GET /api/schedule` | 임계경로·지연 위험 |
| `GET /api/capacity` | 실현 가능한 일정·병목 |
| `GET /api/rebalance` | 재배치 제안 |
| `GET /api/signals` | 보드-코드 대조 |
| `POST /api/ingest` | 메모/사진 → 제안 (`applied:false`) |
| `POST /api/approve` | 고른 제안 반영 (`confirm:true` 필수) |
| `GET /api/report` | 주간 리포트 (마크다운) |

컨테이너는 이 디렉터리에서 빌드합니다: `docker build -t pmo-agent prototype/pmo-agent`

---

## 검사

저장소 루트와 같은 기준입니다 (py312, ruff `E/F/I/UP/B`, line-length 100, mypy `check_untyped_defs`).

```bash
cd prototype/pmo-agent
ruff check . && ruff format --check . && mypy && pytest -q
```

현재 **279건 통과, 1초 이내**. 네트워크도 계정도 타지 않습니다 — 외부 호출은 전부 주입 지점에서 갈아끼웁니다.

> 루트 `docker compose run --rm --build check` 는 `apps/api tests scripts` 만 봅니다. `prototype/` 은 각자 검사합니다 (`prototype/disease` 도 같은 방식).

---

## 알려진 한계

- **스토리포인트 1 = 영업일 1** 가정 (`DAYS_PER_POINT`). 팀 속도가 나오면 상수를 바꿉니다
- **동시 처리 1건** 이 기본 가정입니다. 운영 방식이 다르면 `capacity` 인자로 조정합니다
- 재배치 탐색은 **탐욕적**입니다. 최적해가 아니라 사람이 판단할 후보를 줍니다
- 담당자 인계 가능 여부·역량 차이는 반영하지 않습니다
- 태스크-코드 연결은 **커밋·PR 에 태스크 키를 적는 규칙**에 기댑니다
- 커밋 이메일이 GitHub 계정에 연결돼 있지 않으면 한 사람이 둘로 갈립니다 (이메일 기준 병합하지만 완벽하지 않음)
- 필기 인식은 **합성 이미지로만 검증**했습니다 (`tools/make_note.py`). 실제 손글씨 사진 확인이 남았습니다
- Vertex AI 경로는 **구조만 준비**돼 있고 실호출 미검증입니다
- 팀 저장소가 최근 도입한 PostgreSQL 영속성은 아직 쓰지 않습니다. 로컬 보드는 JSON 파일입니다
