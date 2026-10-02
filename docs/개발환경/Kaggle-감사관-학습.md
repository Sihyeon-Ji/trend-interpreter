# Kaggle 감사관 학습과 재개

Plan 17의 첫 학습 작업은 사전 감사관이다. 기존 [리스크 추론 Notebook](https://www.kaggle.com/code/onzlchoi/ai-builder-cup-gemma)은 그대로 두며, 감사관 작업은 `models/kaggle/audit/`에서 별도로 관리한다. 코드·환경·재개 검증은 이 경로에, 실제 입력·어댑터·실행 결과는 비공개 Dataset과 Git 제외 `artifacts/`에 둔다.

## 고정한 계약

- 기본 모델 `google/gemma-4-12B-it`, revision `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`. 10-02에 공개 모델 메타데이터·토크나이저를 확인한 새 기준선이다. 과거 v5 어댑터의 `revision=null`을 이 값으로 소급해 채우지 않는다.
- Transformers 5.18.0, PEFT 0.21.2, PyTorch 2.14.1, Accelerate 1.15.0, Datasets 5.0.1, bitsandbytes 0.50.2와 전이 의존성을 별도 `uv.lock`에 고정한다. Kaggle T4는 CUDA 12.6 wheel, CPU 검증은 별도 CPU wheel을 사용한다. API 이미지에는 넣지 않는다.
- 4bit NF4, LoRA rank/alpha 16, 학습률 0.0001, 누적 4, batch 1, seed 42, 최대 길이 3,072. 실제 train 319행은 모두 한도 안에 들어오며 최대 2,249토큰이었다. 한도를 넘으면 정답을 잘라 학습하지 않고 중단한다.
- T4의 BF16은 에뮬레이션을 포함해 지원 여부를 확인한다. Gemma BF16 가중치의 FP16 실행에서는 gradient overflow와 optimizer 업데이트 누락을 실제 확인했으므로 BF16을 사용한다. 한 GPU만 노출해 의도한 batch 1을 유지한다.
- 추론과 학습 모두 `enable_thinking=False`의 동일 접두부를 사용한다. 학습은 접두부를 loss에서 제외하고 정답과 `<turn|>`를 학습한다. 학습 손실은 정답 토큰에 필요한 logits만 계산해 긴 입력 전체의 vocabulary 행렬을 FP32로 복사하지 않는다. 기존 masked loss와 같은 손실·gradient인지 CPU에서 대조했다. 채점은 greedy 생성이며 형식 실패도 정확도·fix 누락에 반영한다.
- smoke는 train 8행, 기존 test 2행, 총 4 optimizer step이다. 첫 Notebook은 2단계에서 중단하고 다음 Notebook이 4단계까지 이어간다. smoke 결과는 품질 평가나 운영 승격 근거가 아니다.

기존 test2·holdout의 중복과 모델 판정 정답 문제는 그대로 남는다. 독립 사람 평가·출처 겹침 검사를 완료하기 전 `promotion_eligible=false`다. 모델 구현과 template는 [공식 모델 카드](https://huggingface.co/google/gemma-4-12B-it), 4bit 준비는 [PEFT 양자화 문서](https://huggingface.co/docs/peft/developer_guides/quantization)를 기준으로 확인했다.

## 로컬 검증

```sh
docker compose run --rm --build audit-check
docker compose run --rm --build check
```

`audit-check`는 인터넷 모델이나 학습 데이터를 받지 않는다. 난수로 만든 작은 CPU 언어 모델에 LoRA를 붙여 4단계 연속 실행과 2단계 중단→4단계 재개를 비교한다. 최종 어댑터·optimizer tensor와 scheduler 상태가 정확히 일치해야 한다. 비유한 gradient에서 체크포인트를 남기지 않는 검사, 체크포인트 필수 파일·입력/계보 충돌·분할 누수·정답 절단 거부·형식 실패 처리·비공개 패키지 범위도 검사한다.

Kaggle 실제 Gemma 학습·VRAM·다운로드·CUDA 호환성은 별도 확인이다. CPU 검증을 GPU 완료로 표시하지 않는다.

## 전달 패키지

`prepare.py`는 업로드하거나 실행하지 않고 새 폴더에 검토할 패키지만 만든다.

```sh
uv run --locked python models/kaggle/audit/prepare.py \
  --input-dir artifacts/kaggle/audit-inputs \
  --destination artifacts/kaggle/audit-prepared \
  --owner jseanj
```

입력 폴더에는 앞 단계에서 SHA-256을 검증한 JSONL 2개와 `audit-v5-baseline.json`이 있어야 한다. 출력은 Dataset 폴더와 `trend-audit-qlora-smoke`·`trend-audit-qlora-resume` Notebook 폴더다. 기존 경로는 덮어쓰지 않는다.

Dataset에는 입력 2개·manifest·학습 코드/lockfile을 담은 `runtime.zip`만 올린다. 저장소 `.env`, 인증, DB, 기존 모델 가중치는 포함하지 않는다. 원자료의 통합 라이선스가 확인되지 않아 Dataset metadata는 `unknown`이며, 공개 재사용 권한을 새로 부여하지 않는다. **Private로 유지한다.**

Kaggle은 `runtime.zip`을 입력의 `runtime/`로 자동 해제한다. Notebook은 bundle manifest와 파일별 해시를 검사한 뒤 `/tmp`로 복사한다. uv 0.12.15 bootstrap wheel도 SHA-256으로 고정한다. 가상 환경·패키지 캐시·기본 모델은 `/tmp`에 두어 Notebook Output에 가중치 전체가 섞이지 않게 한다.

새 실행은 기존 GCS v5를 변경하지 않는다. 생성한 Dataset은 [jseanj/trend-audit-v5-baseline](https://www.kaggle.com/datasets/jseanj/trend-audit-v5-baseline), 첫 smoke는 [jseanj/trend-audit-qlora-smoke](https://www.kaggle.com/code/jseanj/trend-audit-qlora-smoke)다. 생성과 실행 상태는 Plan 17 실행 기록을 따른다.

## 실행과 이어가기

아래 명령은 비공개 업로드 또는 GPU quota를 사용하는 실행이다. 이미 만든 Dataset에 `create`를 반복하지 않고, 변경 패키지는 `datasets version`으로 새 버전을 만든다. Notebook이 기대하는 입력·bundle 해시도 함께 갱신한다.

```sh
uv run --locked kaggle datasets create \
  -p artifacts/kaggle/audit-prepared/dataset --keep-tabular --dir-mode skip
uv run --locked kaggle kernels push \
  -p artifacts/kaggle/audit-prepared/trend-audit-qlora-smoke \
  --accelerator NvidiaTeslaT4 --timeout 1800
uv run --locked kaggle kernels status jseanj/trend-audit-qlora-smoke
uv run --locked kaggle kernels output jseanj/trend-audit-qlora-smoke \
  -p artifacts/kaggle/audit-stop-output
```

처음 2단계 실행이 성공하면 `result.json`과 `checkpoint-2`를 확인한다. `save_only_model=false`로 저장한 adapter·optimizer·scheduler·RNG·FP16 scaler·trainer state와 `run-contract.json`이 모두 있어야 한다([Trainer 저장 옵션](https://huggingface.co/docs/transformers/main_classes/trainer)). 어댑터 폴더만으로는 재개하지 않는다.

```sh
uv run --locked kaggle kernels push \
  -p artifacts/kaggle/audit-prepared/trend-audit-qlora-resume \
  --accelerator NvidiaTeslaT4 --timeout 1800
uv run --locked kaggle kernels output jseanj/trend-audit-qlora-resume \
  -p artifacts/kaggle/audit-resumed-output
```

재개 Notebook은 이전 smoke Output을 `kernel_sources`로 붙이고 `checkpoint-2`를 읽는다. 입력·기본 모델 revision·template·학습 설정·코드/lockfile 해시·실제 라이브러리·dtype이 다르면 재개하지 않는다. 다른 output 폴더에 기록하고 이전 실험 결과는 덮어쓰지 않는다.

성공 기준은 `global_step=4`, `optimizer_updates=4`, `resumed_from_step=2`, 유한 gradient·optimizer 상태, 필수 상태 파일 존재와 실제 Gemma 첫 추론·학습·형식/VRAM 기록이다. 다음으로 전체 학습과 독립 사람 평가를 설계하고, 승인된 후보만 모델 release로 등록한다. 팀원 두 명의 실제 같은 입력 재현·공유 권한과 DVC remote push는 별도로 마무리한다.

10-02 실제 smoke 9판·재개 1판에서 위 조건을 통과했다. 실행 수치와 가중치 해시는 `manifests/gemma-audit-training-smoke.json`과 Plan 17 실행 기록에 있다. 전체 학습과 독립 품질 평가는 이 결과와 별도로 진행한다.

GPU smoke 실측 당시에는 verdict 정규식 추출로 형식을 셌다. 커밋 전 검토에서 JSON 객체·ok/fix 필드를 검증하도록 보완했다. 실측 manifest의 기존 수치는 당시 방식으로 보존하며, 이후 전체 평가에는 강화한 JSON 검증을 사용한다. 강화한 평가 코드는 CPU 회귀 테스트로 확인했으며 기존 GPU smoke 수치를 새 방식으로 재측정한 것은 아니다.
