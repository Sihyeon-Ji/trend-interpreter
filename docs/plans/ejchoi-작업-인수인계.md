# ejchoi 작업 인수인계 (10-12 ~ 10-18)

작성일 **2026-10-11** · 보내는 사람 **ejchoi** · 받는 사람 **sng_j** · 함께 볼 사람 **shji(지시현)** · 제출 **10-18**

[계획 목록](README.md) · [ejchoi 확인 요청](ejchoi-확인-요청.md) · [발표 자료](ejchoi-submission-deck.md) · [Gemma 실시간 분류](ejchoi-gemma-live-classify.md) · [제출 양식 문안](../대회/제출/제출-양식-문안.md) · [데모 영상(sng_j)](sng_j-demo-video.md)

10-12부터 제출까지 ejchoi 몫으로 생기는 일을 sng_j가 이어서 한다. 코드·문서는 10-11에 끝났고(`0d4e38a`까지 develop), 남은 것은 결과를 채워 넣는 일과 운영 작업이다. GCP 자원·운영 비밀값·배포는 지시현 확인이 필요하다(표의 '확인').

## 한눈에

| 언제 | 할 일 | 누가 | 절 |
| --- | --- | --- | --- |
| 10-14 코드 동결 전 | 배포: 심사용 계정·Gemma 실행 기록 코드(`f5393fa`, migration 024) | sng_j, 확인 지시현 | [1](#1-배포) |
| 10-15 | 운영 GPU VM 만들기 | 지시현 | [2](#2-gpu와-gemma-실행-기록) |
| 10-16 갱신 뒤 | 사람 결정 누락 확인(Know Your Meme·relatable) | 지시현·sng_j | [3](#3-10-16-갱신-뒤-확인) |
| 10-16 갱신 뒤 | GPU 켜서 Gemma 실행 기록 남기고 끄기 | sng_j | [2](#2-gpu와-gemma-실행-기록) |
| 10-16 재측정 뒤 | 덱·제출 문안·평가 숫자 갱신, 화면 사진 다시 찍기 | sng_j | [4](#4-재측정-숫자와-화면-사진) |
| 10-17까지 | 심사용 계정 만들기 | 지시현, 안내는 sng_j | [5](#5-심사용-계정) |
| 영상 업로드 뒤 | 링크 채우고 제출용 PDF 뽑기 | sng_j | [6](#6-링크와-제출용-pdf) |
| 10-18 | 제출 양식 작성 | sng_j | [7](#7-제출-양식) |

## 1. 배포

develop에는 있지만 운영에 없는 것: 심사용 읽기 전용 계정, Gemma 마지막 실행 기록, `/admin/status`의 '기록된 Gemma 실행'. 운영 데이터 작업(게시·갱신)이 없을 때 배포한다.

```bash
docker compose run --rm --build check
docker compose run --rm --build e2e
git fetch origin
git push origin origin/develop:refs/heads/release/gcp
```

GitHub Actions의 'Release GCP'가 끝나면 운영 웹의 첫 화면·사전 항목이 200인지, 로그인 없이 `/api/live-risk/<term>`에 POST하면 401인지 본다. 배포가 끝났다고 말하기 전에 실제로 확인한다(루트 `AGENTS.md`).

## 2. GPU와 Gemma 실행 기록

10-10 결정: GPU는 데모·녹화 때만 켠다. 심사위원은 꺼진 GPU 대신 마지막 실제 실행 기록을 본다.

1. **VM 만들기(지시현).** 운영 Terraform 설정에 `gpu`(boot image·모델 릴리스·TLS·토큰)를 채워 적용한다. 디스크 250GB가 꺼져 있어도 요금이 나간다(한 달 $25 안팎). 지울 날짜를 함께 정한다. 자세한 것은 [Gemma 실시간 분류 4-2](ejchoi-gemma-live-classify.md#4-2-확인이-필요한-것-10-10)·[4-3](ejchoi-gemma-live-classify.md#4-3-데모녹화-때-gpu-켜고-끄기).
2. **켜기.** `gcloud compute instances start trend-production-gpu --zone <zone> --project stunning-crane-508614-c1`
3. **준비 확인.** 검수자로 로그인해 `/admin/status` 맨 아래 'Gemma 수동 실행'의 GPU 표시가 '준비됨 · gemma4:12b'가 될 때까지 '다시 확인'을 누른다. 켠 시각과 준비된 시각을 적는다.
4. **실행 기록 남기기(10-16 갱신 뒤).** 데모에 나오는 말 3~5개에 대해
   - 사전 항목 `/dictionary/<term_id>`의 '지금 다시 분류해 보기'를 누른다.
   - `/admin/status`의 'Gemma 수동 실행'에 같은 말을 넣고 실행한다.
   - '기록된 Gemma 실행' 목록에 그 말들이 생겼는지 본다. 결과는 공개 사전에 쓰이지 않는다(미리보기).
5. **끄기.** `gcloud compute instances stop trend-production-gpu --zone <zone> --project stunning-crane-508614-c1` 뒤 `gcloud compute instances describe … --format 'value(status)'`가 `TERMINATED`인지 본다.
6. **청구.** 다음 날 Billing에서 GPU·VM·디스크 금액을 [Gemma 실시간 분류](ejchoi-gemma-live-classify.md) 문서에 적는다.
7. **영상에 버튼 장면을 넣을 경우**, 녹화 시간에 맞춰 2~3을 다시 하고 녹화가 끝나면 끈다.

## 3. 10-16 갱신 뒤 확인

- 영어권 둘러보기(`/trends?m=GLOBAL`)·브리핑(Global)·만들기 첫 화면 영어권 칸에 **Know Your Meme·relatable**이 없어야 한다. 10-09에 사람 결정으로 뺐는데 10-09 DB 전환 때 다시 나왔다. 남아 있으면 지시현에게 알린다 – 덱 11쪽('밈 아닌 말을 뺐다')과 어긋나고 영상에도 찍힌다.
- 이 확인은 지시현의 [10-16 운영 DB 갱신](2026-10-16-final-db-refresh.md)과 함께 본다.

## 4. 재측정 숫자와 화면 사진

지시현이 10-16에 같은 12사례를 다시 재면(10차), 그 값으로 아래를 고친다. 숫자는 영상과 같아야 한다.

| 파일 | 고칠 곳 |
| --- | --- |
| `docs/대회/제출/AI-Builder-Cup-제출-초안.pptx` 10쪽 | 큰 숫자 넷(어울림 40% → ?%, 위험한데 '없음', 추천·만들기 응답 시간을 다시 쟀다면), 제목 문장, 회차 그래프(그래프 우클릭 → 데이터 편집에 R10 열 추가, 마지막 막대만 진한 색) |
| 같은 덱 11쪽 | 사례는 그대로 둔다. 10차에 새로 막힌 실패가 있으면 바꿔도 된다 |
| `evals/recommend-rounds.csv` | 10행 추가(같은 열 순서) |
| `EVALUATION.md` 5절 | 요약 표와 'Round 4 / Round 9' 표에 10차를 더한다 |
| `docs/대회/제출/제출-양식-문안.md` | 'Results.' 문단 숫자 |
| `docs/plans/ejchoi-submission-deck.md` | 5절 '숫자 다시 맞추기'를 끝냈다고 적는다 |

**화면 사진**(덱 9쪽, README `docs/images/`). 갱신 뒤 운영에서 다시 찍는다. 운영 주소는 저장소에 적지 않으므로 실행할 때 넘긴다.

```bash
BASE_URL=https://<운영 웹 주소> docker compose run --rm --build --no-deps -e BASE_URL -v "$PWD/docs/images:/out" e2e node scripts/capture-screens.mjs
```

1600×1000 PNG 다섯 장(create, explore-en, entry-en, briefing, map)이 `docs/images/`에 덮어써진다. README는 그대로 이 파일을 쓴다. 덱 9쪽은 PowerPoint에서 사진을 우클릭 → '그림 바꾸기'로 같은 자리에 넣는다(위쪽만 보이게 잘라 넣었으니 '자르기'로 맞춘다). Know Your Meme·relatable이 보이는 화면은 쓰지 않는다.

## 5. 심사용 계정

심사위원이 관리 화면에서 Gemma 실행 기록과 근거를 직접 보게 한다. 읽기 전용이라 승인·결정은 웹과 API가 모두 막는다.

1. 아무 PC에서 해시를 만든다: `cd apps/trend-api && uv run scripts/set_account.py --user judge --readonly` (로컬 `.env`에 계정이 써지고 비밀번호가 한 번 출력된다).
2. 지시현이 그 계정 줄(`{"user":"judge","hash":"…","reviewer":true,"readonly":true}`)을 운영 `ACCOUNTS` 비밀값에 더하고 API를 다시 띄운다.
3. 운영에서 그 계정으로 로그인해 관리 화면 위에 '읽기 전용 계정' 안내가 뜨는지, 리스크 결정이 막히는지 본다.
4. 아이디·비밀번호는 저장소에 적지 않는다. 제출 양식에만 적는다(7절).

## 6. 링크와 제출용 PDF

영상을 올리면:

1. 덱 15쪽 'Demo Video Link'와 `docs/대회/제출/제출-양식-문안.md`·`README.md`·`README.kr.md` 링크 표의 영상 칸을 채운다.
2. 제출용 PDF는 덱을 복사해 15쪽 'Final Product Link'의 `[Cloud Run URL]`에 운영 웹 주소를 넣고 PowerPoint '다른 이름으로 저장 → PDF'로 뽑는다. 이 사본과 PDF는 `artifacts/submission/`에 두고 커밋하지 않는다(운영 주소가 들어 있다). 10-11 초안 `artifacts/submission/COPYBARA-deck-draft-20261011b.pdf`는 ejchoi PC에만 있다.
3. README 링크 표의 배포본 칸에 주소를 넣을지는 팀 결정이다([확인 요청](ejchoi-확인-요청.md) 6번).

## 7. 제출 양식

`docs/대회/제출/제출-양식-문안.md`의 영어 문장을 그대로 붙여 넣는다. 영상·제품 링크와 심사용 계정(아이디·비밀번호, '읽기 전용 – `/admin/status`의 Recorded Gemma runs에서 실제 실행 기록을 볼 수 있음')을 함께 적는다. 문안의 '제출 직전 확인' 표를 따라 본다.

## 참고: 작업 방식

- 커밋 메시지·`docs/` 문서는 한국어, 덱·README·EVALUATION·제출 문안은 영어다. Markdown과 커밋 메시지에는 긴 대시(U+2014) 대신 줄표(U+2013, –)를 쓴다.
- 운영 데이터를 바꾸는 일(게시·갱신)이 돌고 있을 때는 배포하지 않는다.
- 승인 배치를 게시할 때는 Job 제한 시간 때문에 `gcloud run jobs execute trend-production-publication --update-env-vars PUBLICATION_BATCH_ID=<id> --task-timeout=1800s --wait`처럼 시간을 늘려 돌린다([승인 배치 게시](../개발환경/승인-배치-게시.md)).
- 덱은 PowerPoint에서 직접 고쳐도 된다. 디자인 규칙: 글자 #121826, 보조 #566074, 판 #F2F4F7, 파란색 #2448E0은 사람 승인에만, 좌우 여백 0.4인치, 내용은 1.4~5.05인치.
