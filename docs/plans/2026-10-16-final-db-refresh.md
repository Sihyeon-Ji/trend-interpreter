# 10-16 마지막 운영 DB 갱신

실행일 **2026-10-14(앞당김)** · 담당 **ktwoo**(원래 shji) · 상태 **전환 완료 – 아래 '10-14 실행 기록'** · 선행 [10-15 수집 서버 스냅숏](2026-10-15-collection-server-snapshot.md)(ktwoo) · 다음 [10-17 저장소 공개](2026-10-17-public-repository.md)

[계획 목록](README.md) · [GCP 운영](../운영/GCP-운영.md) · [승인 배치 게시](../개발환경/승인-배치-게시.md) · 경위 [옛 Plan 19](archive/19-production-data-refresh.md)

수집 서버의 마지막 스냅숏으로 운영 DB를 새로 만들고, 운영에서 사람이 정한 것(사전에서 뺀 말·리스크 결정·쓰임 낱말 고정·뜻 수정·승인 게시)을 이어 받는다. 녹화([데모 영상](sng_j-demo-video.md))가 이 갱신본으로 한다.

## 갱신이 지키는 것과 새로 들어오는 것

갱신은 지금 운영 DB를 덮어쓰지 않는다. 스냅숏으로 **새 DB**를 만들고, 운영 DB의 사람 결정을 그 위에 얹은 뒤(`scripts/refresh_production.py overlay`), 검사가 통과하면 API가 새 DB를 보게 바꾼다. 지금 DB(`trend_20261009`)는 그대로 남는다.

| 운영 DB에서 이어 받는 것 | 방법 |
| --- | --- |
| 사람이 손댄 말(검수 결정, 사람 확인 뜻 `verified_human`, 리스크 사람 결정, 게시한 승인 배치의 말) | 그 말의 `terms`·`meanings`·`review_queue`·`translations`·`topic_notes`·`term_fit` 행을 운영 값으로 바꾼다(스냅숏의 자동 값은 버린다) |
| 사람·Gemini가 붙인 쓰임 낱말 | `carry_fits`(`human:`·`gemini-`) |
| 검수 기록·Gemini 호출 기록·이용자 설정·해석 캐시·승인 배치와 게시 기록·문구 승인 기록(`copy_approvals`, 10-12 추가) | 표째로 옮긴다 |
| 사전에서 뺀 말(Know Your Meme 등) | 검수 기록이 있는 retired 말 |

`compare`가 운영의 사람 결정·기록이 새 DB에 하나도 빠지지 않고 같은지 센다. 10-10까지 한 일(리스크 36개, 草·도도독 뜻 수정, 쓰임 낱말 고정, 영어 뜻 60개 게시)은 모두 위 표에 든다.

**새로 들어오는 것은 확인되지 않은 자동 값이다.** 사람이 손대지 않은 말은 스냅숏 값(새 말, 자동 확인 뜻, 생애주기, 근거)을 쓴다. 그래서 바꾸기 전에 아래 '전환 전 확인'을 거치고, 통과하지 못하면 바꾸지 않는다. 지금 DB로 데모를 찍어도 된다 – 갱신의 이득은 6일 더 최근의 유행과 일본 보강분이다.

## 미리 할 일 (10-16 전)

- ~~`fit_backfill.py`에 추천 후보의 로컬 모델(`local:`) 쓰임 낱말을 Gemini로 다시 붙이는 옵션을 더한다.~~ 10-10에 더했다: `fit_backfill.py --gemini gemini-3.5-flash --batch 12 --relabel-local`(2897066). 10-10 운영 사본에서 로컬 값인 추천 후보는 0개다.

- **10-14 수집 DB 정리(ktwoo 위임, 결정 이름 `ktwoo(위임·Claude 조사 2026-10-14)`)** — 10-13 스냅숏(`20261013T170912-5f2443d`)과 그 빌드는 이 정리 전이라 10-15 밤 스냅숏으로 다시 만든다.
  - 草: 뜻을 출처(일본어 위키백과 「（笑）」, 나무위키 草)대로 고친 새 판(verified_human), 언어 zh → ja. 이전 판은 '지지율 비유'(天草灘 지진 기사에서 뽑힌 틀린 뜻)였다.
  - 게이트 규칙(근거 메모·'밈으로 사용됨' 뿐·짐작·한두 마디)이 생기기 전에 자동으로 실린 뜻 221개를 검수 대기로 내렸다(사람이 보던 제안이 있는 10개는 그대로).
  - 리스크 사람 결정: 무뇌충·정속충·환기충·리얼충 주의(벌레 비하 접미), #BreakTheBias 사용 자제 → 주의. #NiggerNavy·Noah Knigga 는 표제어 규칙(match.unsafe)으로 공개에서 빠진다.
  - 구두점만 다른 표제어 4쌍을 별칭으로 합침(Nice boat. · …Kenny! · This is Sparta! · …Captain Alex? 를 retired).
  - 결정 칸이 빈 문자열이라 큐에 안 보이던 5건(역주행·썬연료·kocak·High key·Hawk tuah)을 다시 보이게.
  - 급증 이유 351개·지구 주제의 나라별 차이에 일본어판(Sonnet), 기존 말 37개의 뜻 번역을 Sonnet 판으로.
  - 정리 전 백업: 수집 서버 `data/backup/trend.db.bak-20261014-before-cleanup`.
- 아직 사람이 볼 것: 검수 대기의 '밈 아님(두 판정 일치)' 1,006건·'빈말' 88건은 한꺼번에 닫을 수 있다(10-14 권한 확인으로 보류), 이미 실린 말의 고칠 안 140건·제외 제안(???, Bob Ross, Bohemian Rhapsody, Blood Sugar).

## 전환 전 확인 (새 DB, API를 바꾸기 전)

1. `compare` 결과 빠진 사람 결정 0.
2. 새로 추천 후보가 된 말 목록을 지금 DB와 견준다. 쓰임 낱말은 `fit_backfill --gemini --relabel-local`, 리스크가 비어 있으면 표로 내 사람 판정.
3. 같은 12사례를 새 DB 사본으로 잰다. 9차(어울림 91%, 위험 누락 0)보다 나쁘면 원인을 고치거나 전환하지 않는다.
4. 화면 점검(10-14): 영어·일본어 화면 첫 화면·둘러보기에 밈 아닌 말(Know Your Meme·relatable·Deepfake)이 없고, 첫 화면 말이 모두 그 화면 언어의 뜻을 갖는다(草 'English explanation not available yet' 이었다). 나라 화면 1초 안.
5. 통과하면 secret 버전 추가와 API·Job 전환. 코드도 함께 배포한다(develop 의 10-14 수정: 첫 방문 언어·나라 화면 brief·빈 뜻 비공개·급증 이유 일본어판).

## 이전 DB로 되돌리기 – 왜 하나

전환 뒤에야 드러나는 문제(얹기에서 빠진 것, 화면 오류, 새 후보의 나쁜 추천)가 있으면 API를 바로 지금 DB로 돌려야 한다. 되돌리기는 secret 버전을 이전 것으로 바꾸고 API·Job revision을 다시 만드는 일이라 release 되돌리기(revision 트래픽만 옮기기)와 다르고, 아직 한 번도 해 보지 않았다. 녹화·제출 직전이라 막히면 시간이 없으므로, **10-16 전환 직후 한 번 이전 DB로 돌렸다가 다시 새 DB로 오는 것**을 실행해 기록한다(따로 날을 잡을 필요는 없다).

## 10-14 실행 기록

사용자 요청으로 10-16 갱신을 10-14 에 했다. 도커를 쓰지 않으므로 `refresh-production-db.sh` 와 같은 순서를 이 서버의 로컬 PostgreSQL(:55432)·`cloud-sql-proxy` 로 손으로 돌렸다. 운영 GCP 를 바꾸는 명령(Cloud SQL 사용자·DB, secret, Cloud Run)은 ktwoo 가 직접 실행했다.

| 단계 | 결과 |
| --- | --- |
| 스냅숏 | `20261014T134313-8887867`(13:43 업로드, 표제어 11,723) – 10-14 수집 DB 정리 뒤 |
| 적재·얹기 | 로컬 `trend_build_1014`. 사람 손댄 말 196개를 운영 값으로. 얹기가 그 말들의 번역을 운영의 옛 판으로 되돌려, 뜻이 같은 230개(영어 102·일본어 128)는 Sonnet 판을, 지구 메모 70개는 일본어판을 다시 넣었다. 운영 사람 판 뜻에 번역이 없던 草·도도독은 Sonnet 으로 번역, 草 언어 zh → ja |
| 재계산 | track 11,642 · risk 6,509 · dashboard 6,206 · board 81 (14분) |
| 쓰임 낱말 | 추천 후보 117/122 를 Gemma 4 12B 로(어제와 같은 relabel) |
| 대조 | 빌드·새 클라우드 DB 모두 빠진 사람 결정 0 – 그사이 결정이 없어 전환 직전 다시 얹기는 하지 않았다(다시 얹으면 위 번역이 또 옛 판으로 돌아간다) |
| 새 DB | Cloud SQL `trend_20261014`(소유 trend_app, 표 59), 게시 역할(읽기 40·쓰기 14), 임시 관리자 삭제 |
| 전환 전 백업 | `trend-production-backup-m4zdp` 성공 |
| secret | `trend-production-database-url` **v4**, `trend-production-publisher-database` **v2** (계정 `trend-production-accounts` v2 는 같은 날 심사용 계정) |
| API | 새 리비전 `trend-production-api-db20261014`(Cloud Run v2 REST, 트래픽 100%). 되돌리기: `--to-revisions=trend-production-api-judge2=100`(이전 DB `trend_20261009`) |
| Job | backup·maintenance → database-url v4, publication → publisher-database v2 (REST) |
| 확인 | 운영 자료 시각 2026.10.14 09:17, 草 웃음 뜻, 일본어 화면 급증 이유 22/22 일본어, 표제어 읽기(럭키비키 'Lucky Vicky') |

Terraform 변수는 아직 옛 버전이다. 다음 apply 전에 `services.database_secret_version` → `…/trend-production-database-url/versions/4`, `services.accounts_secret_version` → `…/trend-production-accounts/versions/2`, `publisher.database_secret_version` → `…/trend-production-publisher-database/versions/2` 로 맞춘다. 이 서버의 gcloud 584 는 `--update-secrets` 가 Terraform 의 secret 경로를 못 읽어, secret 버전은 REST 로 바꿨다. 이전 DB `trend_20261009` 는 지우지 않는다.

**10-15 이어서(데모 시나리오 v4 점검).** 운영 DB 에 검수 위임 결정(`ktwoo(위임·Claude 조사 2026-10-15)`): 밈이 아닌 말 14개 제외(Summer·먹고 – 여름·한국어 문구마다 카피 검사 오탐, 해시태그·구글 번역·Emoji·ChatGPT·고지라·포켓몬·Barbie·Newport·Diddy parties·Meme coin·Just the Way You Are·Sunshine), 리스크 사람 판정 2개(원영적 사고 주의 – 실존 아이돌 이름, 오히려 좋아 없음). 프록시 너머로 `refresh_caches` 를 돌리면 한 시간 넘게 걸려, 같은 데이터의 로컬 빌드에서 만든 보드·대시보드 캐시를 옮기고 사전 색인은 지워 첫 요청이 다시 만들게 했다. 요청 제한을 웹 60→**180초**, API 90→**150초**로(504, 모델 요청 22건 중 4건), 쓰기 가능 검수자 계정 `reviewer` 를 더했다(accounts **v3**). API 리비전 `trend-production-api-rev-acc3`, 웹 `trend-production-web-t180`. Terraform 에 맞출 값이 늘었다: `services.tf` 의 웹 timeout 180s·API 150s, `accounts_secret_version` v3. **주의:** 이 REST 수정들이 `update_mask` 없이 서비스 전체를 PATCH 해 API 의 `customAudiences`(trend-production-api)가 지워졌고, 그 뒤 GitHub 배포의 신분 토큰 health 검사가 실패했다(10-15 11:13, 후보 `00100-sox` 가 트래픽을 받지 못함). `?update_mask=customAudiences` 로 되돌린 뒤 배포를 다시 돌린다. 앞으로 REST 로 바꿀 때는 바꿀 칸만 `update_mask` 로 지정한다.

이날 이후 수집 서버에 쌓이는 새 말은 운영에 없다 – 녹화 전에 한 번 더 갱신할지는 따로 정한다.

## 절차

절차는 [GCP 운영의 운영 DB 갱신](../운영/GCP-운영.md)을 따른다(capture → build → create → upload → overlay → secret → Terraform·API 전환). 10-09 두 번째 전환에서 바뀐 점을 지킨다.

- Terraform은 `infra/gcp/hybrid`에서 `TF_DATA_DIR=.terraform/production`으로 실행한다. 기본 `.terraform`은 staging 상태다.
- API는 배포 스크립트가 revision 이름을 정해 Terraform이 409로 실패한다. Cloud Run v2 API로 template의 secret 버전과 revision 이름만 바꾼다.
- 백업·유지보수 Job도 새 secret version으로 옮긴다. 10-09에는 유지보수 Job을 빠뜨렸다.
- 게시 역할을 새 DB로 옮긴다. `GRANT CONNECT … TO trend_publisher`, `configure_publisher_role.py --role trend_publisher`를 실행하고, 새 DB 이름으로 `trend-production-publisher-database` version을 추가한다.
- 덮어 얹기(overlay)는 secret 추가 전에 끝낸다. 운영 DB에 일괄 갱신이 도는 동안 승인 배치를 준비하지 않는다.

10-16 갱신에 더할 일(10-10)

- **스냅숏:** ktwoo가 10-15 밤까지 `db/latest`를 올린다([10-15 수집 서버 스냅숏](2026-10-15-collection-server-snapshot.md)). 받은 업로드 시각의 스냅숏으로 capture한다.
- **쓰임 낱말:** 사람(`human:`)·Gemini(`gemini-`) 값은 `carry_fits`가 운영에서 이어 받는다. 새로 추천 후보가 된 말 가운데 쓰임 낱말이 없거나 로컬 모델(`local:`) 값인 것은 Gemini로 다시 붙인다. 지금 `fit_backfill.py`는 칸이 찬 로컬 값을 건너뛰므로, 추천 후보의 `local:` 값을 다시 붙이는 옵션을 갱신 전에 더한다.
- **리스크:** 새로 추천 후보가 된 말 가운데 리스크가 비어 있는 것은 표로 내 사람 판정을 받는다(10-10의 36개와 같은 방법).
- **재측정:** 갱신본으로 같은 12사례를 다시 잰다([밈 추천 남은 일](ktwoo-meme-recommendation-remaining.md)의 완료 기준).
- **이전 DB로 되돌리기:** 위 완료 기준의 되돌리기 명령을 이번 전환 때 한 번 실행해 기록한다(release 되돌리기는 10-10에 실행했다).
- **표제어 읽기(10-13):** 스냅숏에 `term_readings`(마이그레이션 026)가 새로 들고 영어·일본어 뜻이 Sonnet 판으로 바뀐다([10-15 수집 서버 스냅숏](2026-10-15-collection-server-snapshot.md)). 이관은 코드의 표 목록으로 옮기므로 026 이 든 코드로 돌린다. 게시 역할은 마이그레이션 027 이 이미 등록된 역할에 이 표 읽기 권한을 주고, 새 DB 에서 `configure_publisher_role.py` 를 돌릴 때도 받는다.
- **나라별 이름(10-13):** 외국에서 온 한글 표제어(규동·고블린 모드)는 원어 이름(`term_names`, 마이그레이션 028)을 가지고, 그 화면 언어에서는 이 이름이 크게 보인다(일본어 화면 牛丼, 사전 항목에만 '韓国語の見出し語 규동'). 수집 서버가 문서에 글자 그대로 있고 표제어 바로 뒤 괄호 안이거나 소리가 맞는 것만 넣었다(111개). 028 도 게시 역할에 읽기 권한을 준다.

완료 기준(옛 Plan 19)

- 새 snapshot 반영 뒤에도 `review_history`·`verified_human` 뜻·사람 리스크·`gemini_calls`가 전환 전과 같다.
- 전환 전 백업과 그 복원 검증 보고서가 있고, 이전 DB로 되돌리는 명령을 한 번 실행해 본 기록이 있다. **되돌리기 실행은 아직 하지 않았다.**
- 운영 웹의 사전·지도·해석이 새 snapshot 시각으로 열리고, 오류 경보가 없다.
