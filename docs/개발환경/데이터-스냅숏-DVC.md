# 데이터 스냅숏과 DVC 재현

Plan 17의 인수 도구는 루트 `pyproject.toml`·`uv.lock`에 고정한다. API 이미지에는 DVC를 넣지 않는다. 실제 DB·학습셋·모델은 Git 제외 경로에, `manifests/`와 `.dvc`만 Git에 둔다.

## 인증과 경계

GCS remote는 `gs://copybara-team-shared-bucket/taewoo/trend-interpreter/dvc-cache`다. 개발 환경은 ADC, GCP 실행 환경은 서비스 계정을 사용한다. Kaggle은 비공개 Dataset으로 자료를 전달하며 장기 GCP 키나 운영 DB 인증 정보를 넣지 않는다. DVC의 [GCS 인증 문서](https://doc.dvc.org/user-guide/data-management/remote-storage/google-cloud-storage)를 따른다.

현재 `gcloud` 로그인과 ADC는 서로 다르다. ADC가 없는 환경에서는 사용자가 다음 인증을 완료한다.

```sh
gcloud auth application-default login
```

Compose에서 GCS를 사용하는 명령에는 인증 디렉터리만 읽기 전용으로 연결한다.

```sh
docker compose run --rm --build \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  data-tools python scripts/snapshot.py --help
```

인증 파일은 저장소나 Kaggle로 복사하지 않는다. 공유 버킷의 prefix는 IAM 경계가 아니며, 실제 쓰기 전 managed folder 또는 별도 비공개 운영 버킷 경계를 확정해야 한다.

## SQLite 인수

`capture`는 DB 압축 파일·표별 건수·수집 메타데이터 3개를 generation으로 고정해서 내려받는다. CRC32C·SHA-256·크기, SQLite 무결성, 전체 표 목록과 행 수를 검사한다. `explain_cache`·`lookups`·`reader_prefs`가 존재하면 빈 표도 거부한다. 읽는 동안 원본 generation이 바뀌면 manifest를 만들지 않는다. `--directory`는 새 경로만 허용한다.

```sh
docker compose run --rm \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  data-tools python scripts/snapshot.py capture \
  --snapshot-id 20261001T224511-e56b90d \
  --directory artifacts/snapshots/20261001T224511-e56b90d
```

`latest/`는 생산자가 manifest를 마지막에 게시하는 계약이 아직 없다. 따라서 현재 인수 기록의 `source_consistency=legacy-count-verified`는 행 수와 다운로드 중 generation 안정성 검증이다. 같은 행 수로 내용만 바뀐 서로 다른 업로드까지 동일 수집 실행이라고 보증하지 않는다. 생산자 완료 manifest를 붙이는 자동 업로더 변경과 운영 게시 승인은 별도로 필요하다.

로컬 검증은 인증과 네트워크 없이 실행할 수 있다.

```sh
docker compose run --rm data-tools python scripts/snapshot.py verify \
  --manifest manifests/20261001T224511-e56b90d.json \
  --directory artifacts/snapshots/20261001T224511-e56b90d
```

`publish`는 검증한 로컬 파일을 `snapshots/<snapshot-id>/`에 올린 뒤 `manifests/<snapshot-id>.json`을 마지막에 쓴다. 모든 객체는 `if_generation_match=0`으로 기존 파일 덮어쓰기를 거부한다. 중간 실패에서는 완료 manifest가 생성되지 않으며 남은 객체를 자동 삭제하지 않는다. 새 ID로 재시도하고 실패 사본 정리는 별도로 검토한다.

**아래는 GCS 쓰기 명령이다. 공유 경로 권한·보존 정책과 사용자 확인을 끝낸 뒤 실행한다. 현재 인수 기록은 아직 `captured` 상태다.**

```sh
docker compose run --rm \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  data-tools python scripts/snapshot.py publish \
  --manifest manifests/20261001T224511-e56b90d.json \
  --directory artifacts/snapshots/20261001T224511-e56b90d
```

성공 후 `published-manifest.json`을 Git의 원본 manifest로 반영한다. 다른 환경에서는 Git에 기록된 게시 manifest를 `fetch --manifest ... --directory ...`로 받아 검증한다. `fetch`는 `published` 상태의 고정 snapshot 경로만 허용한다. `captured` 상태의 `db/latest` 참조를 장기 보존 사본으로 취급하지 않는다. generation을 지정해도 삭제된 판이 영구 보존되는 것은 아니므로 운영·연구에서 참조하는 사본은 정리 대상에서 제외해야 한다([GCS precondition](https://docs.cloud.google.com/storage/docs/request-preconditions)).

## 선택 학습셋

기존 감사관 v5의 SFT 371행과 holdout 20행, 약 1.45MB만 DVC에 등록했다. `manifests/audit-v5-baseline.json`에는 원본 generation·SHA-256·행 수와 평가 제한이 있다. 원본 JSONL은 `datasets/audit-v5/`에서 Git 제외한다.

```sh
docker compose run --rm data-tools dvc status
docker compose run --rm data-tools python -m scripts.verify_dataset \
  --manifest manifests/audit-v5-baseline.json --directory datasets/audit-v5
```

공유 경로에 쓰기 전 최소 권한·사용자 확인을 완료한 운영자는 대상 2개만 push한다. **현재 remote push는 실행하지 않았다.**

```sh
docker compose run --rm \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  data-tools dvc push datasets/audit-v5/audit_sft_v5.jsonl.dvc \
  datasets/audit-v5/audit_holdout_sft.jsonl.dvc
```

push 후 팀원은 같은 Git commit을 checkout하고 필요한 `.dvc`만 pull한 뒤 위 SHA-256 검증을 실행한다. Kaggle Dataset에는 그 검증한 파일·manifest·코드·lockfile만 전달한다. Git commit 변경만으로 가중치가 합쳐지지 않는다. `dvc gc`는 사용 중인 release·팀원 브랜치·과거판 보존 범위를 확인하기 전 실행하지 않는다.

현재 자료에는 train 319행·test 32행·test2 20행이 있다. 학습 표제어와 평가 표제어는 겹치지 않지만 holdout 20개와 test2는 모두 같은 표제어다. 정답은 모델 판정이며 독립 사람 정답이라고 표시하지 않는다. 최신 DB snapshot에서 만든 학습셋이라는 계보도 아직 확인하지 않았다.

## Kaggle 연결

사용자가 지정한 Notebook은 [onzlchoi/ai-builder-cup-gemma](https://www.kaggle.com/code/onzlchoi/ai-builder-cup-gemma), 참여 계정은 `jseanj`다. OAuth 연결 후 비공개·GPU T4·인터넷 활성·연결 Dataset 없음을 확인했다. 현재 코드는 CSV 기반 리스크 추론이며 감사관 QLoRA 학습은 아니다. 읽은 설정과 소스 해시는 `manifests/kaggle-context.json`에 있다. 이메일·account number는 저장소에 기록하지 않는다.

CLI는 루트 lockfile의 `kaggle==2.2.4`를 사용한다. 로컬에서 [공식 OAuth 로그인](https://github.com/Kaggle/kaggle-cli/blob/main/docs/README.md#authentication)을 완료한다.

```sh
uv run --locked kaggle auth login
uv run --locked kaggle kernels pull onzlchoi/ai-builder-cup-gemma \
  --metadata --path artifacts/kaggle/ai-builder-cup-gemma
```

다운로드는 읽기 전용이며 Notebook을 게시하거나 실행하지 않는다. private Notebook/Dataset에는 `jseanj` 접근 권한이 필요하다. OAuth 인증은 로컬에 보관하고 Kaggle에는 GCP 운영 자격증명을 전달하지 않는다. GPU 실행·Dataset 업로드·Notebook push는 비용·공개 범위와 실행 대상을 먼저 확인한다.

검증한 SFT 2개와 manifest만 담은 전달용 파일은 `artifacts/kaggle/audit-v5-inputs.zip`이다. 현재 업로드 전이며 비공개로만 전달한다. 기존 Notebook은 다른 입력 형식이므로 별도 감사관 학습 Notebook을 마련한다.

## 검증

`docker compose run --rm --build check`가 snapshot·DVC 재현·이관 테스트를 실행한다. DVC 테스트는 네트워크와 GCP 인증 없이 로컬 remote에서 독립 환경 두 개의 동일 해시·선택 pull·과거판 복원을 확인한다. 이는 실제 팀원 두 명의 Kaggle 실행이나 모델 품질 검증을 대신하지 않는다.
