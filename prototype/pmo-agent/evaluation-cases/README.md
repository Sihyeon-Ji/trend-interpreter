# 평가 케이스

팀 워크플로 문서가 요구하는 **성공 5 / 실패·엣지 5** 케이스입니다.
`../tools/evaluate.py` 가 실행합니다.

```bash
cd prototype/pmo-agent
python tools/evaluate.py          # 결과 표
python tools/evaluate.py --json   # 기계가 읽을 형태 (실패 시 exit 1)
```

## 정답지가 어디서 오는가

케이스에 답을 하드코딩하지 않습니다. `src/pmo_agent/seeds/world.py` 가 프로젝트를
하루 단위로 시뮬레이션하면서 **무엇이 진짜 원인인지**를 `World.truths` 에 적어 둡니다.
평가는 그 정답지를 실행 시점에 읽어 옵니다.

```
world.simulate()  →  truths (정답지)  →  cases.jsonl 의 truth 필드가 참조
                  →  board / repo / calendar 투영  →  엔진이 계산
                                                        ↓
                                              둘이 맞는가?
```

날짜에 따라 태스크 키가 달라지므로 이 방식이어야 합니다. `ECHO-8` 같은 키를 적어 두면
내일 깨집니다.

## 두 묶음

### detect — 심어 둔 것을 찾아내는가

| id | 무엇을 심었나 |
|---|---|
| `root-cause-visible` | 외부 IdP 스펙 변경으로 인증 구현이 8영업일 막혔다 |
| `stalled-detected` | 착수만 하고 손을 놓은 태스크 (보드는 '진행 중') |
| `undeclared-progress-detected` | 커밋은 있는데 보드는 '할 일' |
| `premature-done-detected` | 보드는 완료인데 PR 이 열려 있다 |
| `meeting-overload-detected` | 앞으로 회의가 가장 많은 사람 |

### restraint — 없는 것을 지어내지 않는가

| id | 무엇을 확인하나 |
|---|---|
| `no-evidence-no-warning` | 커밋에 태스크 키가 없으면 태스크 단위 경고를 내지 않는다 |
| `cycle-is-error-not-crash` | 순환 의존은 예외로 죽지 않고 오류로 돌아온다 |
| `invented-key-becomes-question` | 모델이 지어낸 키는 반영되지 않고 질문이 된다 |
| `no-write-without-approval` | 고르지 않으면 쓰기 호출 자체가 나가지 않는다 |
| `no-calendar-no-meeting-claim` | 캘린더가 없으면 회의를 반영했다고 말하지 않는다 |

**두 번째 묶음이 더 중요합니다.** 못 찾는 것은 아쉬운 정도지만, 없는 것을 있다고 하거나
승인 없이 쓰는 것은 신뢰를 통째로 잃습니다.

## 케이스 형식

```json
{
  "id": "stalled-detected",
  "group": "detect",
  "check": "signals_mismatch",
  "truth": "stalled",
  "ask": "보드 상태와 실제 코드 진척이 어긋난 게 있나",
  "why": "착수만 하고 손을 놓은 태스크가 있다"
}
```

- `check` — `tools/evaluate.py` 의 `CHECKS` 에 등록된 검사 함수
- `truth` — `World.truths` 에서 찾을 정답 종류 (detect 묶음만)
- `ask` — 사람이 에이전트에게 실제로 물을 법한 문장. 모델 경로를 붙일 때 입력으로 쓴다

## 지금 다루지 않는 것

- **모델 출력의 문장 품질** — 숫자는 코드가 계산하고 모델은 인용만 하므로, 여기서는
  계산이 맞는지만 본다. 문장 평가는 별도 과제다
- **실제 손글씨 판독률** — 합성 이미지로만 검증했다 (`tools/make_note.py`)
- **Gemini 호출** — 평가는 네트워크를 타지 않는다. 키 없이 돌아야 CI 에 넣을 수 있다
