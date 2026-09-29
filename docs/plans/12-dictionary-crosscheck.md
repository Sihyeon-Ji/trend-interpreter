# Plan 12. 사전 전수 대조: 확인된 항목을 참고 위키와 맞춰 보기

작성일 **2026-09-29** · 상태 **구현 (전수조사 결과 반영 대기)** · 근거 [ADR 0003](../adr/0003-사전-등재-기준.md) · 목표일 **2026-10-04** (문서 없는 항목의 처리는 사용자 확인 뒤)

## 목표

[ADR 0003](../adr/0003-사전-등재-기준.md) 전에 자동으로 실린 확인 항목(2026-09-29 운영 DB 148개, 이 가운데 위키 근거가 없는 것 54개)을
참고 위키와 한 번 모두 대조합니다. 뜻·유래가 문서와 어긋나면 고칠 안을, 문서가 없으면 그 목록을 사람에게 올립니다.
그 뒤 새로 실리는 말은 파이프라인의 '문서 대조' 단계가 같은 방식으로 봅니다.

[Plan 03](03-term-risk.md)·[Plan 04](04-target-regions-and-keyword-dashboard.md)는 ADR 0003이 바꾼 부분(리스크 이유의 커뮤니티 글 인용, 대시보드·사전 항목의 '주로 보인 곳') 말고는 그대로 유효합니다.

## 1. 참고 문서 모으기 (언어별)

표제어의 말(`Term.lang`)에 따라 아래 순서로 찾습니다. 표제어나 별칭이 문서에 실제로 있는지는 `match.mentions()`로만 봅니다.

| 표제어의 말 | 찾는 곳 (순서대로) |
| --- | --- |
| 한국어(ko) | 나무위키, 한국어 위키백과 |
| 일본어(ja) | 일본어 위키백과, Know Your Meme, 나무위키(한글 별칭이 있을 때) |
| 영어(en) | Know Your Meme, 영어 위키백과 |
| 그 밖(zh·th·vi·id 등) | 그 말의 위키백과, 영어 위키백과, Know Your Meme. 대만·홍콩 표제어는 萌娘百科도 |

- 니코니코 대백과(ニコニコ大百科)는 이 서버의 요청을 막아 쓰지 않습니다. pixiv 백과사전(pixiv百科事典)은 대부분 봇 확인 뒤에 있어 그냥 열리는 문서만 씁니다.
- 본문은 저장하지 않습니다. 짧은 발췌·링크·수정 시각만 `wiki` 근거로 남깁니다(나무위키 CC BY-NC-SA 2.0 KR, 위키백과 CC BY-SA — `collectors/namuwiki.py`와 같은 방식).
- 기존 수집기(`collectors/namuwiki.lookup`, `collectors/wikipedia_search`)를 쓰고, Know Your Meme은 수집기를 새로 둡니다. 요청 사이 간격을 두고 결과는 하루 캐시합니다.
- 실행은 한 번 쓰는 스크립트(`scripts/crosscheck_dictionary.py`, 새로 작성)로 합니다. 기본은 보고만 하고, 검수 큐에 올리는 것은 옵션으로 켭니다.

## 2. 항목마다 판정

| 판정 | 뜻 | 누가 정하나 |
| --- | --- | --- |
| 일치 | 사전의 뜻·유래가 문서와 맞다 | 모델이 제안, 사람이 확인 |
| 고칠 것 | 문서는 있는데 사전의 뜻·유래가 다르거나 빠졌다 | 모델이 고칠 안을 쓰고, 사람이 결정 |
| 위키끼리 다름 | 문서들이 서로 다른 뜻·유래를 적었다 | 두 설명을 나란히 올리고, 사람이 고른다 |
| 문서 없음 | 표제어가 든 참고 문서가 없다 | 규칙 코드 (`verification.reference_doc`) |
| 밈이 아님 | 문서가 인물·작품·상품·일반 낱말을 다룬다 | 모델이 제안, 사람이 결정 |

- '문서 없음'만 규칙이 정합니다. 나머지 넷은 로컬 Gemma가 사전 뜻과 문서 발췌를 나란히 보고 판정 이름과 한두 문장 이유를 제안할 뿐이고,
  모델이 '일치'라고 해도 확인 상태를 바꾸지 않습니다(판정은 데이터, LLM은 서술).
- 사람이 이미 승인한 뜻(`verified_human`)도 대조는 하되, 제안은 사람의 결정을 덮지 않고 검수 큐에만 올립니다.

## 3. 결과 적용

- 모든 제안은 사람 검수 큐로 갑니다. 자동으로 적용하는 것은 없습니다. 사유에 판정 이름과 문서 링크를 적습니다.
- '고칠 것'은 사람이 승인할 때 새 판(version)으로 싣고 이전 판의 `valid_to`를 닫습니다. 삭제하지 않습니다.
  지금의 검수 큐는 현행 뜻을 제안으로 보여 주므로(`views.review_items`), 현행 뜻을 닫지 않고 고칠 안(`review_queue.draft_json`)을 따로 보여 주고
  승인할 때 새 판을 만드는 길을 먼저 만듭니다. 그렇지 않으면 제안을 올리는 순간 항목이 공개 사전에서 빠집니다.
- '위키끼리 다름'은 두 문서의 설명을 나란히 올리고, 사람이 고른 쪽을 '고칠 것'과 같은 길로 싣습니다.
- '밈이 아님'은 제외 제안으로 올립니다. 제외(`retired`)는 사람만 합니다.
- '문서 없음' 목록은 먼저 사용자에게 보이고, **사용자가 확인한 뒤에만** 검수 대기(`needs_review`)로 돌립니다.
  `scripts/audit_dictionary.py`는 이제 참고 문서 규칙까지 게이트를 다시 돌리므로 보고 모드로 이 목록을 만들 수 있지만(사람이 승인한 뜻은 이 규칙에서 빠진다),
  `--apply`는 확인 전에 쓰지 않습니다(문서 없는 말을 강등한다).
- 판정별 건수와 표본을 이 문서의 결과 절에 기록합니다.

## 4. 이후: '문서 대조' 단계 (새 말)

- 순서는 `research` 다음(collect → … → research → **문서 대조** → track → …)입니다. 새로 실린 말과, 참고 문서가 마지막 대조 뒤 고쳐진 말(나무위키 단계의 '문서가 고쳐지면 다시 조사'와 같은 방식)만 봅니다.
- 판정·적용 규칙은 위 2·3과 같습니다. 게이트는 이미 참고 문서를 요구하므로, 이 단계는 실린 뜻이 문서와 어긋나는 것을 검수 큐로 보내는 일을 합니다.
- Know Your Meme 수집기는 조사 단계의 근거 모으기에도 붙입니다. 지금은 Search grounding이 없는 오프라인 조사에서 위키백과·나무위키만 찾아, 영어·일본어 밈이 문서가 있어도 검수 대기로 가기 쉽습니다.
- 모델이 없는 기본 개발 환경에서는 '문서 없음' 판정만 하고 나머지는 건너뜁니다.

## 구현 (2026-09-29)

계획의 1~4를 코드로 옮겼습니다. 확인된 항목 전부의 전수조사는 파이프라인 밖에서 따로 돌리고, 그 결과를 아래 `import` 로 가져옵니다.
판정별 건수와 표본은 결과를 가져온 뒤 이 문서의 결과 절에 기록합니다.

| 부분 | 위치 |
| --- | --- |
| 검수 큐의 제안 종류 | `storage/dictionary_store.py`(`queue_review(kind=, docs=)`·`pending_review`·`claim_review`·`human_decided`·`publish_fix`), `storage/migrations/007_review_kinds.sql`·`008_review_history.sql`, `pipeline/views.py`(`ReviewItem`·`ReviewDoc`·`ReviewStats`), `api/app.py`(`POST /review/{term_id}`) |
| 문서 대조 | `pipeline/crosscheck.py` — 참고 문서 모으기, '문서 없음' 규칙, 로컬 Gemma 제안, 검수 큐 올리기, 전수조사 결과 가져오기 |
| '문서 대조' 단계 | `crosscheck.run`, `scripts/run_pipeline.py`의 research 다음. 기록 표 `crosscheck_log`(판정·문서 주소·모델만) |
| 전수 대조 스크립트 | `scripts/crosscheck_dictionary.py` (`collect`·`import`·`judge`) |
| Know Your Meme 수집기 | `collectors/knowyourmeme.py` — **기본 꺼짐**(`KNOWYOURMEME_ENABLED`), 아래 참고 |
| 관리 화면 | `apps/trend-web/components/review-table.tsx`, `app/api/review/[termId]/route.ts`(본문 거르개 `lib/review-decision.ts`), `lib/types.ts`, `lib/i18n.ts`, 예시 `lib/sample/dictionary.ts` |
| 시험 | `tests/test_review_kinds.py`, `tests/test_crosscheck.py`, `tests/test_crosscheck_review.py`(검토에서 찾은 것), `e2e/map-admin.spec.ts`(예시 화면에서 고칠 안 승인), `e2e/review-decision.spec.ts`(라우트가 넘기는 본문) |

### 검수 큐의 제안 종류

`review_queue`에 `kind`와 `docs_json`(제안의 근거 문서 `[{wiki, url, summary, proposal}]`)을 더했습니다. 기존 줄은 마이그레이션에서 모두 `new`입니다.
표제어마다 한 줄이라, 사람이 볼 제안이 이미 있는 말에는 새 제안을 올리지 않습니다.

| 종류 | 화면 이름 | 제안이 올라와 있는 동안 | 승인 | 거절 |
| --- | --- | --- | --- | --- |
| `new` | 새 말 (새 뜻·뜻이 바뀜·추세) | 조사 결과 그대로(지금 판이 제안된 뜻) | 지금 판을 `verified_human` | 제외(`retired`, 뜻 `rejected`) |
| `correction` | 고칠 안 | 지금 뜻이 **공개된 그대로**. `draft_json`이 고칠 안 | 고칠 안을 새 판(`verified_human`)으로 싣고 이전 판의 `valid_to`를 닫는다 | 제안만 닫는다 |
| `conflict` | 위키끼리 다름 | 지금 뜻 그대로. `docs_json`이 문서마다의 설명 | 고른 설명(`choice`)의 고칠 안을 `correction`과 같은 길로. `choice: "keep"`이면 지금 뜻 그대로 두고 닫는다 | 제안만 닫는다 |
| `retire` | 사전에서 뺄지 | 지금 뜻 그대로 | 사람이 제외한다(`retired`, 뜻 `rejected`) | 아무것도 바꾸지 않는다 |

- `views.review_items`는 `correction`·`conflict`·`retire`에서 지금 실린 뜻을 `current`로, 고칠 안을 `draft`로, 문서들을 `docs`로 보입니다.
  예전처럼 지금 뜻을 제안으로 보이지 않으므로 제안을 올려도 항목이 공개 사전에서 빠지지 않습니다.
- `POST /review/{term_id}` 본문은 `{decision: approve|reject, by, meaning_id, kind, token, choice}`입니다. `meaning_id`(검수자가 본 지금 뜻),
  `kind`(제안 종류), `token`(검수자가 본 제안의 표 — 올린 때와 내용으로 만든 값, `ReviewItem.token`) 가운데 하나라도 대기 중인 제안과 다르면 409입니다.
  `new` 밖의 제안에는 셋을 반드시 적습니다(없으면 400) — `retire`의 승인은 제외라서 종류를 모르는 예전 화면이 잘못 승인하지 않게 하고,
  그사이 같은 종류의 다른 제안이 올라왔을 때 오래된 화면이 보지 않은 안을 싣지 않게 합니다.
- 결정은 검수자가 본 그 대기 줄(올린 때가 같음)을 먼저 붙잡은 뒤에만 적용합니다(`claim_review`, 바뀐 줄이 하나일 때만). 두 결정이 동시에 오면 하나만 되고,
  고칠 안 싣기와 한 트랜잭션이라 싣다가 실패하면 붙잡은 것도 풀립니다.
- `conflict`는 고른 문서의 **주소**(`choice`)로 고릅니다. 번호로 고르면 화면이 모양이 틀린 문서를 빼고 보일 때 번호가 밀립니다. `choice`가 없거나
  없는 문서·고칠 안이 없는 문서를 고르면 400입니다.
- 사람의 결정은 결정 기록(`review_history`, 마이그레이션 008)에 남습니다. 검수 큐는 표제어마다 한 줄이라 새 제안이 예전 결정을 덮던 것입니다(게이트가 스스로 닫은 줄은 두지 않는다).
  사람이 이미 결정한(승인·거절·지금 뜻 그대로) 같은 내용의 제안 — 고칠 안은 같은 뜻, 위키끼리 다름은 같은 문서·안, 뺄지는 같은 문서 — 은
  다시 가져오기나 '문서 대조' 재검사가 되살리지 않습니다(`human_decided`).
- 새 말(`new`) 줄은 사람이 보고 있는 다른 종류의 제안을 덮지 않습니다(`queue_review`가 False). 조사·`scripts/audit_dictionary.py`·`scripts/review_dictionary.py`는
  그런 말을 다시 조사하거나 내리지 않고 따로 보고합니다.
- 관리 화면의 '검수 대기' 수는 새 말만 세고, 문서 대조의 제안은 '문서 대조 제안'으로 따로 셉니다(이미 실린 말이라 자동으로 실린 비율에 두 번 세지 않게).
- 유래·뉘앙스만 고친 안도 새 판이 됩니다(`publish_fix`). `add_meaning`의 같은 뜻 판정은 정의·풀이만 봐서 그런 안을 버렸습니다.
- 조사 단계는 문서 대조의 제안을 사람이 보는 동안 그 말을 다시 조사하지 않고(`research.under_review`), 스스로 닫는 줄도 `new`뿐입니다.

### '문서 대조' 단계와 판정

- 대상: 확인된 말 가운데 한 번도 대조하지 않은 것, 로컬 모델이 생긴 뒤의 '판정 안 함', 마지막 대조 뒤 참고 문서가 바뀐 것(그때 보지 못한 참고 문서 근거가
  생겼거나, 나무위키 문서의 수정 시각이 마지막 대조보다 늦음 — 실행마다 20개까지 묻는다). 실행마다 8개까지이며 사람이 볼 제안이 있는 말은 건너뜁니다.
- 참고 문서는 §1의 언어별 순서로 모읍니다(`crosscheck.sources`). 표제어가 든 문서는 짧은 발췌·링크로 wiki 근거에 더합니다(나무위키·위키백과 수집기와 같은 방식).
- '문서 없음'은 규칙입니다: 저장된 근거와 새로 찾은 문서 가운데 표제어가 든 참고 문서(`verification.reference_doc`)가 없을 때. 기록만 하고 아무것도 바꾸지 않습니다.
  새 밈은 나중에 문서가 생기므로 '문서 없음'과 모델의 판정 실패는 7일 뒤 다시 봅니다.
- **'닿지 못함'은 '문서 없음'이 아닙니다.** 수집기는 없다고 확인하면(200·404·410) 빈 목록, 닿지 못하면(429·5xx·네트워크) `None`을 줍니다
  (나무위키·Know Your Meme, 위키백과는 `strict`로 부를 때 `Unreachable`). 닿지 못한 결과는 캐시하지 않습니다. 문서가 하나도 없는데 닿지 못한 곳이 있으면
  판정은 `unreachable`이고 다음 실행에 다시 봅니다(실측: 위키백과 429 로 `推し活`이 '문서 없음'으로 적히던 것).
- 글이 있는 문서가 없고 제목뿐인 문서(Know Your Meme)만 있으면 모델에게 빈 글을 보이지 않고 '판정 안 함(문서 제목뿐)'(`no_text`)으로 둡니다. 글이 있는 문서가 생기면 다시 봅니다.
- 로컬 Gemma가 있으면(`USE_LOCAL_GEMMA=1`과 모델이 떠 있음) `keep`·`fix`·`conflict`·`not_a_meme`와 한두 문장 이유, 고칠 안을 제안받습니다
  (`schemas.CrosscheckJudgement`, 스키마는 프롬프트에). `fix`→`correction`, `conflict`→`conflict`, `not_a_meme`→`retire`로 검수 큐에 올리고, `keep`은 기록만 합니다.
  고칠 안은 지금 뜻 위에 뜻·유래·뉘앙스만 얹습니다(풀이·세대·나라는 그대로).
- 모델이 없는 기본 개발 환경(`MODEL_PROVIDER=mock`, 로컬 모델 없음)에서는 모델을 부르지 않고 '문서 없음'만 판정합니다. 문서가 있는 말은 '판정 안 함'으로 남습니다.
- 검수 화면의 사유는 판정 이름·문서와 다른 점·참고 문서 주소입니다. 예: `문서 대조: 고칠 것`, `유래가 문서와 다름`, `참고 문서: https://…`.

### Know Your Meme — 기본 꺼짐 (사용자 결정 대기)

수집기(`collectors/knowyourmeme.py`)는 만들었지만 `KNOWYOURMEME_ENABLED=false`가 기본입니다. [파이프라인 기록](../트렌드/파이프라인.md)의 '약관 확인 전까지 쓰지 않음' 결정과 같고,
이용 약관(운영사 Cheezburger)을 읽은 결과 제품에 쓸지는 사용자가 정해야 합니다.

1. 자동 접근은 사람과 비슷한 요청 속도로만 허락합니다.
2. 내용은 정보·개인적 이용만 되며, 사전 서면 동의 없이 내려받기·복제·재생산·배포·게시할 수 없습니다.
3. 사전 서면 허락 없이 상업적으로 이용하지 않는다는 데 동의해야 합니다.

- 꺼져 있으면 조사·문서 대조·스크립트가 수집기를 부르지 않고(요청 0건), 전수조사 결과의 Know Your Meme 발췌도 근거로 받지 않습니다.
  그동안 나무위키·위키백과 문서가 없는 영어·일본어 밈은 사람 검수로 갑니다([ADR 0003](../adr/0003-사전-등재-기준.md)의 예외 길).
- 켜면 흔적을 최소로 둡니다. `/memes/<slug>` 문서만 열고(robots.txt가 `/search`를 막는다) 표제어·로마자 별칭으로 최대 세 번, 요청 사이 2초 넘게,
  정직한 User-Agent. 제목과 'About' 절에 표제어가 있는지 그 자리에서 `mentions()`로만 보고, 근거에는 **문서 주소와 제목만** 남깁니다(발췌 없음).
  하루 캐시에도 찾았나·주소·제목만 둡니다.

### 실행

`apps/trend-api`에서 `uv run`으로 돌립니다(Compose 개발 스택이면 `docker compose exec api python scripts/crosscheck_dictionary.py …`).
어느 모드도 확인 상태·뜻을 바꾸지 않습니다. 모든 제안은 검수 큐로 갑니다.

```bash
uv run scripts/crosscheck_dictionary.py                                   # collect: 확인된 말마다 찾은 참고 문서를 보고만
uv run scripts/crosscheck_dictionary.py collect --store                   # 찾은 문서(짧은 발췌·링크)를 wiki 근거로 더한다
uv run scripts/crosscheck_dictionary.py collect --terms "럭키비키|aura farming" --limit 20
uv run scripts/crosscheck_dictionary.py import --from audit.json          # 전수조사 결과: 판정별 건수와 올릴 제안만 보고
uv run scripts/crosscheck_dictionary.py import --from audit.json --queue  # fix·conflict·not_a_meme → 검수 큐 (+ 대조 기록)
uv run scripts/crosscheck_dictionary.py import --from audit.json --store-evidence   # 발췌를 wiki 근거로
uv run scripts/crosscheck_dictionary.py judge                             # 같은 판정을 로컬 Gemma 로 — 보고만
uv run scripts/crosscheck_dictionary.py judge --queue [--store]           # 제안을 검수 큐에 (+ 대조 기록)
uv run scripts/run_pipeline.py --stages crosscheck                        # '문서 대조' 단계만
```

- `import`는 판정 목록(JSON 배열)을 받습니다. 한 줄의 모양:

  ```json
  {"term_id": "t_…", "verdict": "keep | fix | conflict | no_doc | not_a_meme",
   "problems": ["사전과 문서가 다른 점"], "sources": ["https://…"],
   "proposal": {"definition": "…", "origin": "…", "nuance": "…"},
   "alternatives": [{"wiki": "…", "url": "https://…", "summary": "…", "proposal": {"definition": "…"}}],
   "excerpt": {"url": "https://…", "title": "…", "text": "…"}}
  ```

  `proposal`(fix)·`alternatives[].proposal`(conflict)의 빈 칸은 지금 뜻 그대로이고, `proposal`·`excerpt`는 `null`이어도 됩니다.
  fix인데 고칠 안이 없거나 지금 뜻과 같으면 올리지 않고 보고합니다. 형식이 틀린 줄은 건너뛰고 보고합니다.
- 파일은 엄격히 봅니다. 모르는 키(오타 포함)가 있는 줄은 형식 오류로 건너뛰고 보고합니다. `sources`·`alternatives[].url`은 참고 문서의 문서 주소
  (http·https, 참고 문서 도메인, 루트가 아닌 경로, 커뮤니티·SNS 글이 아님 — `crosscheck.reference_url`)만 남기고 나머지는 '뺀 주소'로 보고합니다.
  남은 주소는 한 꼴로 고칩니다(퍼센트 인코딩, 위키백과 문서 이름의 띄어쓰기는 밑줄) — 같은 문서가 근거·문서 목록에 두 번 들어가지 않게.
  fix·conflict·not_a_meme는 참고 문서 주소가 하나는 있어야 올라가고, conflict는 고를 문서 설명이 하나는 있어야 합니다.
- `--store-evidence`는 발췌의 주소가 참고 문서의 문서 주소이고 발췌에 표제어가 있으며(`match.mentions`) **그 문서에 실제로 있는 문장일 때만** 200자 안으로 잘라
  wiki 근거로 더합니다. 나무위키·위키백과는 수집기로 그 문서를 그 자리에서 읽어 확인하고(본문은 저장하지 않는다), 확인할 수집기가 없는 문서(pixiv 백과사전·萌娘百科)는
  받지 않습니다. Know Your Meme 발췌는 꺼져 있으면 받지 않고, 켜져 있으면 수집기 규칙대로 주소·제목만 남깁니다.
- `no_doc`은 어느 모드도 아무것도 바꾸지 않고 목록만 보입니다. **사용자가 확인한 이름만** `scripts/audit_dictionary.py --downgrade "이름|이름"`으로
  검수 대기로 돌립니다(§3). `--apply`는 쓰지 않습니다 — 확인하지 않은 말까지 한꺼번에 내립니다. 닿지 못한 말은 '닿지 못함'으로 따로 보이며 이 목록에 넣지 않습니다.
- 사람이 승인한 뜻(`verified_human`)도 제안은 받지만 큐로만 갑니다. 다시 돌려도 근거·대기 제안·대조 기록이 겹치지 않습니다 — 대기 중인 제안이 있는 말은 건너뛰고 보고합니다.
  확인된 항목(`verified`)이 아닌 말에는 올리지 않습니다.
- `judge`는 로컬 모델이 없으면(`USE_LOCAL_GEMMA=1`과 로컬 서버의 `GEMMA_LOCAL_MODEL`이 필요) 안내만 하고 아무것도 하지 않고 끝납니다. Gemini는 쓰지 않습니다.

### SQLite 쪽으로 옮길 때

코드의 SQL은 `storage/db.py`를 거치는 모양(`?`, 열 이름을 적은 `INSERT OR REPLACE`, `COALESCE(kind, 'new')`)이라 그대로 옮길 수 있습니다.
마이그레이션 007의 `ALTER TABLE … ADD COLUMN IF NOT EXISTS`는 PostgreSQL 문법이라, SQLite에서는 열이 있는지 확인한 뒤 `ADD COLUMN`으로 쓰고
`UPDATE review_queue SET kind='new' WHERE kind IS NULL`을 함께 돌립니다. 마이그레이션 008의 `INSERT … SELECT … ON CONFLICT DO NOTHING`은
SQLite에서 `INSERT OR IGNORE INTO review_history (…) SELECT …`로 씁니다. 결정 기록의 기본키는 `(term_id, queued_at, decided_at)`입니다.

### 남은 일

- 전수조사 결과를 `import`로 가져와 판정별 건수와 표본 10개를 결과 절에 기록하고, '문서 없음' 목록을 사용자가 확인합니다.
- Know Your Meme 사용 여부(위 약관 세 가지)는 사용자가 정합니다. Search grounding을 쓰는 조사(`research.web_evidence`)도 같은 설정을 따릅니다 —
  넘겨주기를 한 칸씩 따라가며 Know Your Meme 으로 가면 꺼져 있을 때는 열지 않고, 켜져 있을 때는 수집기(`knowyourmeme.from_url`)로 넘겨 주소·제목만 남깁니다.
- 萌娘百科·pixiv 백과사전 수집기는 없습니다. 대만·홍콩 표제어는 위키백과만 찾습니다.

## 완료 기준

- 실행 시점의 확인 항목 전부에 판정이 붙고, 판정별 건수와 표본 10개를 이 문서에 기록합니다.
- 사람의 확인 없이 바뀐 상태·뜻이 0건입니다. 모든 제안이 검수 큐를 거칩니다.
- '문서 없음' 목록을 사용자가 확인한 기록이 있습니다.
- '문서 대조' 단계에 테스트가 있습니다: '문서 없음'은 규칙으로 정해지고, 모델의 제안은 상태를 바꾸지 않으며, 기본 개발 환경에서는 모델을 부르지 않습니다.

## 하지 않는 것

- 참고 문서 본문 저장, 니코니코 대백과 수집, pixiv 백과사전의 봇 확인 우회.
- 모델 판정만으로 확인 상태를 바꾸거나 항목을 강등·제외하는 것.
- 커뮤니티·SNS 글을 대조 근거로 쓰는 것. 커뮤니티 글은 쓰임 지표일 뿐입니다([ADR 0003](../adr/0003-사전-등재-기준.md)).
