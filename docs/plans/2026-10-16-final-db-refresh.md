# 10-16 마지막 운영 DB 갱신

실행일 **2026-10-16** · 담당 **shji(지시현)** · 상태 **준비 중** · 선행 [10-15 수집 서버 스냅숏](2026-10-15-collection-server-snapshot.md)(ktwoo) · 다음 [10-17 저장소 공개](2026-10-17-public-repository.md)

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

## 전환 전 확인 (새 DB, API를 바꾸기 전)

1. `compare` 결과 빠진 사람 결정 0.
2. 새로 추천 후보가 된 말 목록을 지금 DB와 견준다. 쓰임 낱말은 `fit_backfill --gemini --relabel-local`, 리스크가 비어 있으면 표로 내 사람 판정.
3. 같은 12사례를 새 DB 사본으로 잰다. 9차(어울림 91%, 위험 누락 0)보다 나쁘면 원인을 고치거나 전환하지 않는다.
4. 통과하면 secret 버전 추가와 API·Job 전환.

## 이전 DB로 되돌리기 – 왜 하나

전환 뒤에야 드러나는 문제(얹기에서 빠진 것, 화면 오류, 새 후보의 나쁜 추천)가 있으면 API를 바로 지금 DB로 돌려야 한다. 되돌리기는 secret 버전을 이전 것으로 바꾸고 API·Job revision을 다시 만드는 일이라 release 되돌리기(revision 트래픽만 옮기기)와 다르고, 아직 한 번도 해 보지 않았다. 녹화·제출 직전이라 막히면 시간이 없으므로, **10-16 전환 직후 한 번 이전 DB로 돌렸다가 다시 새 DB로 오는 것**을 실행해 기록한다(따로 날을 잡을 필요는 없다).

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

완료 기준(옛 Plan 19)

- 새 snapshot 반영 뒤에도 `review_history`·`verified_human` 뜻·사람 리스크·`gemini_calls`가 전환 전과 같다.
- 전환 전 백업과 그 복원 검증 보고서가 있고, 이전 DB로 되돌리는 명령을 한 번 실행해 본 기록이 있다. **되돌리기 실행은 아직 하지 않았다.**
- 운영 웹의 사전·지도·해석이 새 snapshot 시각으로 열리고, 오류 경보가 없다.
