# 10-16 마지막 운영 DB 갱신

실행일 **2026-10-16** · 담당 **shji(지시현)** · 상태 **준비 중** · 선행 [10-15 수집 서버 스냅숏](2026-10-15-collection-server-snapshot.md)(ktwoo) · 다음 [10-17 저장소 공개](2026-10-17-public-repository.md)

[계획 목록](README.md) · [GCP 운영](../운영/GCP-운영.md) · [승인 배치 게시](../개발환경/승인-배치-게시.md) · 경위 [옛 Plan 19](archive/19-production-data-refresh.md)

수집 서버의 마지막 스냅숏으로 운영 DB를 새로 만들고, 운영에서 사람이 정한 것(사전에서 뺀 말·리스크 결정·쓰임 낱말 고정·뜻 수정·승인 게시)을 이어 받는다. 녹화([데모 영상](sng_j-demo-video.md))가 이 갱신본으로 한다.

## 미리 할 일 (10-16 전)

- `fit_backfill.py`에 추천 후보의 로컬 모델(`local:`) 쓰임 낱말을 Gemini로 다시 붙이는 옵션을 더한다. 지금은 칸이 찬 로컬 값을 건너뛴다.

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
