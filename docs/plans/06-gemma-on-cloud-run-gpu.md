# Plan 06. Kaggle Gemma 4 편집·미세조정 실험과 운영 데이터 게시

> **2026-10-01 통합 계획:** [Plan 17](17-hybrid-infrastructure.md)에서 Kaggle QLoRA·DVC/GCS 버전 관리·승인 게시·GCE GPU 운영 서빙을 연결한다. 기존의 '운영 Gemma 위치 미정'은 이 결정으로 갱신된다. 아래 실험 기록과 품질·게시 조건은 입력 근거로 유지한다.

작성일 **2026-09-28** · 변경일 **2026-10-01** · 상태 **실험 위치를 Colab에서 Kaggle로 변경, Kaggle 합성 표본 실행 확인(10-01)·실표본은 대기 · 운영 게시 경계·PC 독립 정리/감시·클라우드 전용 /ask·Gemma 평가는 미구현(Plan 05 Cloud SQL 대기) · 그동안 Gemma 편집은 원작자 PC 파이프라인이 하루 4회 대신 돌린다(아래 '현재 상태') · 12B QLoRA는 학습 서버에서 실행했다([Plan 16](16-wiki-meme-catalog-and-tendency.md))** · 선행 실험은 [Plan 01](01-import-latest-trend-data.md)의 고정 데이터, 운영 게시만 [Plan 05](05-trend-cloud-run-deployment.md)의 Cloud SQL 필요 · 목표일 **2026-10-10**

> 파일 경로는 기존 링크를 위해 유지한다. 2026-09-29에 [개발자 PC Gemma 결정](../AI-개발/Gemma-로컬-편집-엔진-결정.md)을 바꿔 실험 위치를 Colab GPU로 옮겼고, **2026-10-01에 다시 Kaggle 노트북으로 옮겼다**(아래 'Colab에서 Kaggle로 옮긴 까닭'). 사용자 요청을 무료 노트북 런타임에 연결하지 않는 경계는 유지한다. 운영 Gemma는 [Plan 17](17-hybrid-infrastructure.md)의 GCE GPU에 둔다. Kaggle GPU를 쓸 수 없거나 할당이 떨어지면 로컬 PC의 Ollama가 오프라인 배치 편집의 대체 경로다.

[계획 목록](README.md) · [Plan 01 데이터 이관](01-import-latest-trend-data.md) · [Plan 05 배포](05-trend-cloud-run-deployment.md) · [Gemma 리스크 실험 노트북](../../models/kaggle/gemma_risk_labeling.ipynb) · [파이프라인 기록](../트렌드/파이프라인.md)

## 목적

팀원이 자기 Kaggle 계정의 **노트북 GPU**에서 Ollama와 Gemma 4를 실행해 공개 트렌드 근거의 리스크 분류를 실험하고, 검증된 사전 언어판·국가별 해석의 초안을 **오프라인 배치**로 만든다. 근거 대조·규칙 검증·사람 검수를 통과한 결과만 Cloud SQL에 게시한다. SaaS 사용자는 Cloud Run 웹·API에서 마지막 성공 게시본을 읽고, 일반 실시간 생성은 Vertex AI Gemini, 승인된 특화 추론은 Plan 17의 GCE GPU를 사용한다. Kaggle의 첫 학습 목표는 인수한 감사관의 재현이며, 번역·리스크 등 추가 작업은 각각 별도 평가한다. **Kaggle 노트북이 꺼져도 공개 서비스는 동작해야 한다.**

대회는 Gemini 또는 Gemma 등 Google AI 모델의 활용을 허용한다. Gemma의 역할은 공개 트렌드 자료를 작은 오픈 모델로 가공해 여러 사용자에게 재사용 가능한 지식 자산을 만드는 것이다. 모델 이름보다 원자료·근거·검수·게시 결과를 연결해 보여 준다.

현재 `models/kaggle/gemma_risk_labeling.ipynb`는 **Plan 03 리스크 분류의 프롬프트·모델 비교용**이다. Gemma 가중치를 학습하거나 미세조정하지 않으며, 사전 번역·국가별 해석을 만들거나 Cloud SQL에 게시하지도 않는다. 표본 CSV와 서버 환경 JSON이 없으면 합성 문장으로 작동만 확인하므로 품질 수치로 사용하지 않는다. 이 노트북의 존재만으로 Plan 06이 구현됐다고 기록하지 않는다.

## Colab에서 Kaggle로 옮긴 까닭 (2026-10-01)

**무료 Colab에서는 GPU를 사실상 받을 수 없었다.** 2026-09-30 무료 T4 배정이 사용량 제한으로 거절됐고 컴퓨팅 단위는 0이었다. 이후 사용자가 확인한 결과, 무료 계정에 GPU를 쓸 컴퓨팅 자원이 없어 Gemma 4 추론·학습을 진행할 수 없었다. Colab에서 확인한 것은 소유자 Drive의 입력 읽기·결과 쓰기·재마운트 보존과 합성 표본의 입출력뿐이고, **Gemma 추론과 학습은 한 번도 실행하지 못했다.**

Kaggle은 무료 GPU를 **주간 할당량으로 공개**하고 남은 시간을 계정 화면에 보여 준다. 그래서 실험 위치를 Kaggle로 옮긴다. Colab 조사 전문(Drive 공유·마운트 권한·런타임 제한 실측)은 [옮기기 전 Plan 06](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/blob/d7e9a7ff7960497e84043c0847bb91e19e20fcc7/docs/plans/06-gemma-on-cloud-run-gpu.md)과 [옛 Colab 노트북](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/blob/d7e9a7ff7960497e84043c0847bb91e19e20fcc7/models/colab/gemma_risk_labeling.ipynb)에 남아 있다. 소유자 Drive의 `Builder-Cup-Trend-Colab` 폴더에는 합성 표본과 연결 시험 파일만 있으므로 더 쓰지 않는다. 정리는 소유자가 판단한다.

## Kaggle 무료 자원 (2026-10-01 조사·계정 확인)

**GPU·TPU 주간 할당과 비공개 저장 한도는 2026-10-01 팀원 계정의 Quotas 화면으로 확인했다**(GPU 30시간·TPU 20시간·비공개 Dataset 214.75 GB·비공개 Model 214.75 GB). 세션 한도·GPU 종류·`/kaggle/working` 크기·휴대폰 인증 조건은 여러 외부 정리에서 서로 일치한 값이며 첫 실행에서 확인한다. 같은 화면의 **AI Models** 한도(하루 $10·한 달 $100)는 Kaggle이 호스팅하는 모델 호출용으로 보이나 무엇을 부를 수 있는지 확인하지 않았다. 이 프로젝트의 Gemini 호출은 `model_client.py`의 Vertex AI 경로만 쓰므로 이 한도에 기대지 않는다.

| 항목 | 내용 |
| --- | --- |
| GPU | 주당 30시간(계정 확인). **T4 2장(각 16 GB)** 또는 P100 1장(16 GB) 중 선택 |
| TPU | v3-8, 주당 20시간(계정 확인) |
| 한 세션 | GPU 최대 12시간, TPU 최대 9시간 |
| 저장 | `/kaggle/working` 20 GB가 버전 Output으로 남는다. 그 밖의 디스크는 세션이 끝나면 사라진다. 비공개 Dataset 합계 214.75 GB(계정 확인) |
| 조건 | **휴대폰 인증**을 해야 GPU·인터넷을 켤 수 있다. 결제 수단은 필요 없다 |
| 대기 | 붐빌 때는 GPU를 기다릴 수 있다 |
| 모델 | Kaggle Models에 Gemma 4 12B·12B IT가 있다(`kagglehub`). 리스크 노트북은 서버와 같은 조건을 위해 Ollama `gemma4:12b`를 받는다 |

**T4와 P100은 bf16을 지원하지 않는다.** 추론은 Ollama 양자화 모델이라 영향이 적지만, `models/lora/audit_qlora.py`처럼 `torch.bfloat16`으로 학습하는 코드는 그대로 돌지 않는다. fp16으로 바꾸면 Gemma가 불안정해질 수 있다는 보고가 있으므로, 학습은 짧은 시험으로 손실이 정상인지 먼저 확인한다(아래 '가중치 미세조정 실험').

출처: [Kaggle 무료 등급 정리](https://agentdeals.dev/vendor/kaggle), [Colab 대안 비교(2026-09)](https://www.thundercompute.com/blog/colab-alternatives-for-cheap-deep-learning-in-2025), [무료 클라우드 GPU 조건](https://aimultiple.com/free-cloud-gpu), [휴대폰 인증 안내](https://neuroai.neuromatch.io/tutorial-kaggle), [T4의 bf16 문제](https://discuss.vllm.ai/t/gemma3-on-a-t4-gpu/643), [Kaggle의 Gemma 4 12B IT](https://www.llmreference.com/provider/kaggle/gemma-4-12b-it).

## 범위와 역할

| 작업 | 실행 위치·방법 | 게시·요청 경계 |
| --- | --- | --- |
| 공개 자료 수집·검색어·밈 후보 선정 | 개발자 PC의 현행 파이프라인 | 최신 원자료·근거 ID를 유지하고 필요한 배치만 추출 |
| 근거 문장 리스크 분류 실험 | 팀원별 Kaggle 노트북의 Ollama + Gemma 4 | 현재 노트북은 표본 재분류·비교만 수행, 운영 DB에 기록하지 않음 |
| 쇼츠 직접 해석, Google Search grounding | 개발자 PC 파이프라인이 Vertex AI Gemini 호출 | 모델 호출 예산·근거 기록 유지 |
| 검증된 뜻의 ko·en 언어판, 국가별 해석 초안 | Kaggle 노트북의 Gemma 4 오프라인 배치, 미구현. GPU를 쓸 수 없으면 개발자 PC의 Ollama | 원어 표제어·근거·스키마·사람 검증 후 별도 게시 단계에서 반영 |
| 가중치 미세조정(QLoRA) | 팀원별 Kaggle을 재현 경로로 구축. 기존 RTX 4090 실행은 기준선 | 채택 전 보류 평가 세트에서 전후 비교 |
| 뜻의 검증 상태·생애주기·리스크 | 코드 규칙과 사람 검수 | 모델의 단독 판정 금지, 뜻 버전 유지 |
| 지도·사전·리포트 열람 | Cloud Run 웹·API와 Cloud SQL | 마지막 성공 게시본 제공, 갱신 시각 표시 |
| 신규 사진·홍보 문구 이해, 카피·대본 생성 | Cloud Run API가 Vertex AI Gemini 호출 | 요청 시 처리, 호출 예산 적용 |
| 새 메시지 재작성·사전 질문 응답 | 저장된 근거·규칙 우선, 필요 시 Gemini | Kaggle·개발자 PC에 실시간 의존하지 않도록 별도 구현·평가 |

현재 `USE_LOCAL_GEMMA=1` 라우팅은 현행 파이프라인의 Ollama 경로를 뜻한다. **Kaggle에서 노트북을 돌려도 `run_pipeline.py`가 자동으로 Kaggle 모델을 호출하지 않는다.** 운영 API에는 `USE_LOCAL_GEMMA=0`을 기본으로 두고 `/explain`, `/ask`, Plan 07·08의 실시간 경로를 별도 검증한다.

## GitHub·DVC/GCS·Kaggle의 역할

| 위치 | 담는 것 | 보존·접근 |
| --- | --- | --- |
| GitHub `develop` | `.ipynb` 코드, 배치 입출력 계약, 검증 코드 | 팀이 버전 관리하는 원본이다 |
| DVC + 비공개 GCS | 고정 원본 manifest, 선택한 전처리셋·평가셋·채택 모델, 실행 결과 계보 | Git에는 DVC 메타데이터만 저장. 개발 환경에서 ADC로 pull/push하고 Kaggle 전달용 Dataset을 만든다 |
| 팀원별 Kaggle 노트북 세션 | 실행 중 설치한 Ollama, 받은 `gemma4:12b`, 임시 파일 | 계정마다 별개다. 세션이 끝나면 `/kaggle/working` 밖의 파일과 모델이 사라진다 |
| 비공개 Kaggle Dataset | 수집 서버에서 내보낸 표본 CSV와 `.env.json` | 노트북의 입력(`/kaggle/input`, 읽기 전용)으로 붙인다. 새 표본은 새 버전으로 올린다. 필요한 팀원만 Collaborator로 더한다 |
| 노트북 버전 Output | 실행별 결과·체크포인트·실행 메타데이터(`/kaggle/working/runs/<RUN_ID>`) | Save Version으로 돌린 버전마다 남는다. 다른 노트북이나 다음 버전의 입력으로 붙여 재개·비교한다 |
| 로컬 PostgreSQL·Cloud SQL | 원자료·검수 기록·마지막 승인 게시본 | Kaggle을 운영 DB로 쓰지 않는다. Kaggle에 DB 비밀번호나 전체 DB 덤프를 올리지 않는다 |

**Dataset과 노트북은 Private으로 둔다.** 표본에는 공개 기사·쇼츠·커뮤니티 글의 발췌가 들어 있다. 공개 Dataset·공개 노트북으로 바꾸면 Kaggle 전체에 공개되므로 바꾸지 않는다. Kaggle Secrets에도 운영 자격증명을 넣지 않는다. CSV·모델 파일·자격증명·검수 결과는 Git에 커밋하지 않는다.

## Kaggle 계정·CLI 준비

1. kaggle.com에 가입하고 **Settings → Phone verification**으로 휴대폰 인증을 한다. 인증 전에는 GPU·인터넷을 켤 수 없다. 한 사람이 여러 계정으로 할당을 우회하지 않는다.
2. **Settings → API → Create New Token**으로 API 토큰을 받는다. Kaggle CLI 2.x는 `~/.kaggle/access_token`(권한 600)을 쓴다. 토큰은 저장소·Kaggle Secrets·메신저에 올리지 않는다.
3. 개발 PC에 CLI를 설치하고 연결을 확인한다. 2026-10-01 `Kaggle CLI 2.2.4`로 인증을 확인했다.

   ```bash
   uv tool install kaggle
   kaggle datasets list -m   # 인증이 맞으면 오류 없이 목록(처음에는 "No datasets found")
   ```

## Kaggle·GitHub 코드 동기화

**코드 원본은 GitHub의 `models/kaggle/gemma_risk_labeling.ipynb`, 데이터는 비공개 Kaggle Dataset, 실행 결과는 노트북 버전 Output으로 관리한다. 개발 PC의 Kaggle CLI로 올리고 받는다.** Kaggle 편집기의 GitHub 연결(`File → Link to GitHub`)은 쓰지 않는다. Save Version마다 셀 출력까지 커밋될 수 있어 표본 문장이 GitHub에 남고, 검토 없이 `develop`·`release/gcp`에 저장될 수 있다.

**한 저장소, 계정별 노트북.** Kaggle 노트북·GPU 할당(주 30시간)·Output은 계정에 묶인다. 그래서 코드는 저장소의 노트북 하나를 같이 쓰고, 실행은 각자 자기 계정에 같은 이름의 비공개 노트북(`<아이디>/gemma-risk-labeling`)을 만들어 돌린다. 표본 Dataset은 올린 사람 계정에 하나 두고 팀원을 Collaborator로 더해 같이 읽는다. 한 노트북을 여럿이 번갈아 push하면 서로의 설정과 Output 버전이 섞이므로 그렇게 하지 않는다.

`models/kaggle/run_kaggle.py`가 이 흐름을 한 번에 한다. 자기 토큰의 아이디로 노트북 ID를 정하고, 저장소 노트북의 **임시 사본**에 실행 설정(`USE_SYNTHETIC_SAMPLE`·`MAX_TERMS`·`VARIANTS`)을 적어 `kernel-metadata.json`(비공개, GPU T4 x2, 인터넷, Dataset)과 함께 push한다. 끝날 때까지 상태를 보다가 Output을 `artifacts/kaggle/<노트북 이름>/`(커밋하지 않음)으로 받고 GPU·모델 digest·호출 시간을 출력한다. 저장소의 노트북 파일은 바꾸지 않는다.

```bash
python3 models/kaggle/run_kaggle.py --synthetic                                   # 데이터 없이 작동 확인
python3 models/kaggle/run_kaggle.py --dataset builder-cup-risk-sample --max-terms 5
python3 models/kaggle/run_kaggle.py --dataset builder-cup-risk-sample --variants baseline v2_term_vs_tone
python3 models/kaggle/run_kaggle.py --dataset <owner>/builder-cup-risk-sample      # 팀원 Dataset
python3 models/kaggle/run_kaggle.py --synthetic --dry-run                         # push 하지 않고 만들 파일만 확인
```

| 하는 일 | 명령 |
| --- | --- |
| 표본 Dataset 만들기·새 버전 | `kaggle datasets init -p <폴더>` 뒤 `dataset-metadata.json`의 `title`·`id`를 채우고 `kaggle datasets create -p <폴더>`. 새 표본은 `kaggle datasets version -p <폴더> -m "<메모>"`. 기본이 비공개이며 `--public`은 붙이지 않는다 |
| 노트북 올리고 실행·결과 받기 | `python3 models/kaggle/run_kaggle.py ...` (위) |
| 상태만 보기 | `kaggle kernels status <아이디>/gemma-risk-labeling` |
| Kaggle 편집기에서 고친 코드 받기 | `kaggle kernels pull <아이디>/gemma-risk-labeling -p <임시 폴더>` 뒤 공통 노트북과 비교한다 |

1. 실행별 값은 스크립트 인자로만 바꾼다. 실행별 값을 공통 기본값으로 커밋하지 않는다.
2. 공통 코드를 바꿨으면 모든 코드 셀 출력과 실행 횟수를 지우고, 원문·개인 계정 정보·토큰·CSV·결과·체크포인트·가중치가 들어 있지 않은지 확인한다.
3. 작업 브랜치에서 커밋하고 PR로 검토해 `develop`에 반영한다. `release/gcp` 푸시는 실제 배포를 유발한다. 같은 `.ipynb`를 두 사람이 동시에 고치지 않는다.
4. Git 커밋과 모델·입력 해시를 실행 메타데이터에 연결한다. 진행 중인 실험을 최신 코드로 덮어쓰지 않는다.

GPU 종류는 `machine_shape`(`kaggle kernels push --accelerator`)로 정하며 스크립트 기본값은 `NvidiaTeslaT4`(T4 x2)다([kernel-metadata 필드](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md), CLI 2.2.4). 문서에는 `NvidiaL4`·`TpuV5E8`도 있으나 무료 계정에서 고를 수 있는지는 확인하지 않았다. CLI push는 노트북 전체를 비대화형으로 돌리므로 셀별 확인은 웹 편집기에서 한다. `RESUME_FROM` 재개(이전 Output을 입력으로 붙이기)는 스크립트에 아직 없다.

### 첫 실행 기록 (2026-10-01, 합성 표본)

웹 편집기의 Save Version으로 합성 표본(용어 2개·문장 10개)을 돌렸다. **GPU T4 x2, Ollama 0.35.0, `gemma4:12b` digest `6114515d63c1`**. 전체 292초 중 설치 약 30초, 모델 7.4 GB 받기 약 80초, 첫 호출 141.7초(GPU에 모델 올리는 시간 포함), 두 번째 호출 3.9초였다. 두 호출 모두 재질문 없이 `ok`이고 10문장 모두 분류됐으며, Output을 `kaggle kernels output`으로 받았다. 두 번째 호출 속도로 보아 설치 로그의 `Unable to detect NVIDIA/AMD GPU` 경고와 달리 GPU에서 돌았다. **합성 문장이므로 품질 수치가 아니다.** 재개·실표본·팀원 계정 실행은 아직 확인하지 않았다.

## 팀원별 Kaggle 실행 절차

1. 위 '계정·CLI 준비'를 마친다.
2. Plan 01의 GCS 고정 SQLite 스냅숏을 별도 PostgreSQL로 이관하고 `apps/trend-api/scripts/export_risk_sample.py`로 실표본을 추출한다. 수집 서버 자체의 PostgreSQL 전환은 요구하지 않는다. DVC 입력 해시·snapshot ID를 기록하고, 최신본 이관 전에는 표본의 시점과 한계를 기록한다. 사용자 입력 표는 내보내지 않고 필요한 공개 근거 문장만 CSV로 추출한다.
3. CSV와 같은 이름의 `.env.json` 두 파일만 빈 폴더에 모아 **비공개 Dataset**으로 올린다. 실행할 팀원을 Dataset 화면의 **Share**에서 Collaborator로 더한다. GPU 할당은 실행한 계정에서 빠진다.
4. `python3 models/kaggle/run_kaggle.py --dataset <Dataset>`으로 돌린다. 웹 편집기로 셀을 하나씩 확인할 때는 `File → Import Notebook`으로 가져오고 Settings에서 **GPU T4 x2**, Internet, **Add Input**(표본 Dataset)을 정한다. 거기서 고친 코드는 `kaggle kernels pull`로 받아 PR로 반영한다.
5. 처음에는 `--synthetic`으로 합성 문장의 설치·추론·메모리·시간·결과 저장을 확인한다. 이는 작동 확인이다. 이어서 실표본으로 셀을 순서대로 실행한다. Ollama 버전, `gemma4:12b`의 태그·digest, 프롬프트 해시, 호출 옵션을 서버 기준과 비교한다. 서버는 미분류 문장만 묶고 노트북은 최근 문장을 다시 묶으므로 같은 모델이어도 결과가 달라질 수 있다.
6. 남겨야 하는 실행은 CLI push 또는 **Save Version(Save & Run All)** 으로 돌린다. 결과는 그 버전의 Output `runs/<RUN_ID>`에 남는다. 중간에 끊겼으면 그 버전의 Output을 입력으로 붙이고 `RESUME_FROM`에 `runs/<RUN_ID>` 경로를 적어 다시 돌린다. 입력 해시·모델 digest·프롬프트·규칙이 같은 정상 완료 항목만 재사용한다.
7. 각자 다른 프롬프트 안을 별도 실행 ID로 비교한다. 서버 모델과의 일치율은 참고치다. CSV의 `human_*` 칸에 **사람이 독립적으로 판정한 값**을 넣어 오탐·누락과 근거를 비교한다. 합성 표본이나 사람 판정이 없는 일치율을 AI 품질 개선의 증거로 사용하지 않는다.

`path_check.json`은 **입출력 확인 단계의 기록**이며 `inference_executed=false`다. 실제 추론이 성공하면 `sentence_labels.csv`, `term_levels.csv`, `calls.csv`, `run.json`과 `checkpoint.json`이 같은 실행 폴더에 저장된다. 입력 검사 기록을 모델 추론 결과로 해석하지 않는다.

## 가중치 미세조정 실험 – 별도 스크립트

현재 Ollama 리스크 노트북은 `ollama.chat()`으로 답만 생성하므로 학습이 일어나지 않는다. 학습에는 정답이 붙은 입력·출력 쌍, 학습 프레임워크, 손실 계산·역전파, 체크포인트 저장 코드가 필요하다. Google의 [Gemma 텍스트 QLoRA 가이드](https://ai.google.dev/gemma/docs/core/huggingface_text_finetune_qlora)는 기본 모델을 4비트로 읽고 작은 **LoRA 어댑터 가중치**만 학습하는 예를 제공한다.

**12B QLoRA는 이미 학습 서버에서 돌았다.** `models/lora/audit_qlora.py`는 학습 서버의 RTX 4090 한 장에서 사전 감사관을 약 9분, 최대 9.8 GiB로 학습했다([Plan 16](16-wiki-meme-catalog-and-tendency.md)). 실행 환경은 `models/lora/pyproject.toml`과 `uv.lock`이다. 이 실행은 기준선으로 보존하고, Plan 17에 따라 팀원별 Kaggle에서 같은 입력과 설정으로 재현하는 경로를 구축한다. 기존 스크립트의 `save_strategy="no"`를 중간 체크포인트 저장과 `resume_from_checkpoint`로 보완해야 한다.

1. 먼저 한 작업을 고른다. 사람이 판정·수정한 입력과 정답을 모으고 용어·출처 단위로 학습/검증/최종 평가 세트를 분리한다. 모델이 만든 기존 분류를 정답으로 그대로 재사용하거나 같은 문장의 변형을 학습과 평가 양쪽에 넣지 않는다. 학습 데이터(`audit_sft.jsonl` 등)는 비공개 Dataset으로 올리고 Git에는 넣지 않는다.
2. Kaggle T4에서는 `bf16` 대신 `fp16`으로 바꿔 **20~50 학습 단계만** 먼저 돌린다. 손실이 정상으로 줄어드는지, 최대 GPU 메모리, 단계당 시간, 설치·다운로드·저장 시간을 잰다. 손실이 `nan`이 되거나 빈 답을 내면 T4 학습을 멈추고 bf16을 지원하는 TPU v3-8(JAX/Keras 경로), 더 작은 모델, 또는 학습 서버를 쓴다. 이 단계는 실행 가능성 점검이며 품질 개선의 증거가 아니다.
3. 기본 모델의 정확한 ID·revision, 데이터 해시, 코드 커밋, QLoRA 설정, 학습 단계·손실·평가 점수, GPU를 기록한다. 추론용 어댑터와 **학습 재개용 체크포인트**(optimizer·scheduler·단계·난수 상태 포함)를 구분해 `/kaggle/working`에 주기적으로 저장한다. 끊긴 학습은 이전 버전 Output을 입력으로 붙여 마지막 정상 체크포인트부터 재개한다. 12시간 세션과 20 GB Output 한도 안에 들어가도록 저장 간격과 보관 개수를 정한다.
4. **미세조정 전 기본 모델+프롬프트**와 **미세조정 후 기본 모델+어댑터**를 같은 보류 평가 세트에서 비교한다. 근거 일치·리스크 오탐/누락·한국어·영어 표현·국가별 주장·처리 시간과 실패율을 기록한다. 개선이 불분명하면 어댑터를 운영 편집에 사용하지 않는다.
5. 개선이 입증되더라도 어댑터를 Ollama `gemma4:12b`에 자동 적용할 수 있다고 가정하지 않는다. **학습 모델과 실제 편집에 쓰는 모델의 ID·형식·로딩 방법을 맞춘 뒤** 작은 배치로 재현·검증한다. 학습 완료만으로 공개 API나 Cloud SQL의 모델 경로가 바뀌지 않는다.

- **12B 전체 가중치 학습:** 목표로 잡지 않는다. 16비트 가중치만으로 약 24 GB가 필요하고, 학습에는 기울기·optimizer 상태·중간 계산 메모리가 추가된다. 양자화된 Ollama 추론 파일 크기를 학습 메모리로 계산하지 않는다.
- 10월 10일까지 유효한 정답 데이터와 GPU가 준비되지 않으면 학습을 완료했다고 쓰지 않고 실험 결과와 제약을 기록한다.

## 세션 종료와 백그라운드 실행

| 방법 | 효과와 한계 |
| --- | --- |
| 대화형 세션 | 셀을 하나씩 실행해 확인할 때 쓴다. 브라우저를 닫거나 유휴로 두면 세션이 끝나고 `/kaggle/working`도 버전으로 남지 않는다 |
| Save Version(Save & Run All) | 노트북 전체를 처음부터 끝까지 백그라운드로 실행하고 결과를 버전 Output으로 남긴다. 브라우저를 닫아도 계속 돈다. 한 세션 최대 12시간과 주간 할당은 그대로다 |
| 버전 Output을 입력으로 붙이기 | 끊긴 추론·학습을 다음 실행에서 이어 간다. 마지막 정상 저장 이후의 작업은 잃을 수 있다 |

Save Version은 중간에 사람이 값을 바꿀 수 없으므로, 설정 셀의 값을 정한 뒤 실행한다. 추론은 완료 항목과 결과를, 미세조정은 학습 재개용 체크포인트를 주기적으로 저장한다. 저장 간격은 실제 저장 시간과 중단 시 허용할 재작업량을 재서 정한다. 주간 할당이 모자라면 학습 서버를 먼저 쓰고, 유료 GPU는 비용·필요 메모리·실행 시간을 비교한 뒤 따로 결정한다. 이 계획 변경만으로 유료 구독이나 GPU VM을 만들지 않는다.

## 구현 순서

1. **Kaggle 입력과 첫 실행.** 할당량은 확인했다(10-01). 실행 담당자가 휴대폰 인증을 마치고 세션 한도·GPU 종류를 첫 실행에서 확인한다. 합성 표본으로 설치·추론·저장·재개를 확인한 뒤, Plan 01의 데이터 시점·근거 ID를 포함한 제한된 공개 표본을 비공개 Dataset으로 올리고 팀원 한 명의 계정에서도 같은 Dataset으로 실행해 본다. 실표본 실험은 최신 데이터가 준비되는 범위에서 진행하고 Cloud SQL 배포를 기다릴 필요는 없다.
2. **리스크 기준선과 선택적 미세조정 실험.** 현행 `gemma4:12b` 추론의 GPU 메모리·시간과 사람이 판정한 표본의 품질을 측정한다. 기존 감사관을 Kaggle에서 재현하되 fp16 짧은 시험을 통과한 경우에만 이어 간다. 학습 서버 결과는 기준선이며, Kaggle에서 실패하면 원인과 대체 실험 경로를 기록한다. 성공·실패·보류 결정을 기록한다.
3. **Kaggle 편집 배치.** 검증된 뜻과 근거를 받아 사전 언어판·국가별 해석 초안을 만드는 입출력 계약과 배치를 구현한다. 원자료 수집·영상·검색 grounding은 현행 PC 파이프라인에 둔다. 출력에 입력 스냅샷·뜻 버전·모델 ID·프롬프트·검수 상태를 연결하고, 세션이 끊기면 완료된 항목부터 이어서 처리한다. 초안을 Output에 저장하는 것만으로 승인하지 않는다.
4. **검수와 운영 게시.** 스키마·근거·언어별 뜻 보존을 검사하고 사람이 승인한 결과만 별도 게시 도구로 Plan 05의 Cloud SQL에 반영한다. 게시 도구는 Plan 17의 Cloud Run 게시 Job으로 구현하고 관리되는 개발 환경에서 검증하며 Kaggle에는 운영 DB 자격증명을 주지 않는다. 배치 ID와 뜻 버전으로 중복·오래된 결과의 덮어쓰기를 막고, 실패 시 마지막 정상 게시본을 유지한다. Cloud SQL Auth Proxy를 쓰더라도 private IP에는 별도 네트워크 경로가 필요하다. 자격증명·사용자 원문·생성 결과 전문은 운영 로그나 Git에 기록하지 않는다.
   현재 `/meta`와 유지보수 작업은 `pipeline_runs`의 `board`·`dashboard` 성공 행으로 게시 시각을 판단한다(`ds.PUBLISH_STAGES`). Plan 17에서는 게시 트랜잭션의 활성 `publication_id`와 성공 시각을 기준으로 바꾸고, 두 소비자를 함께 수정한다. 전환 전 검증에서는 현행 신호를 유지하며, 완료되지 않은 게시를 성공 행으로 꾸미지 않는다.
5. **서비스 분리와 보존·감시.** Cloud Run 웹·API는 PC와 Kaggle이 꺼져도 게시 자료를 읽어야 한다. 운영에서 PC의 localhost 모델 폴백을 제거한다. 일반 생성은 Vertex AI Gemini·규칙으로 처리하고, 승인된 특화 작업만 Plan 17의 GCE 내부 gateway로 호출한다. 감사관 어댑터를 리스크·번역 등 다른 작업에 품질 검증 없이 적용하지 않는다. 해석 캐시 7일·미해결 질문 30일 삭제, 마지막 정상 게시 시각과 오래된 자료 경보는 Plan 05의 독립 예약 작업으로 운영한다.
   2026-09-29 코드 구현: `scripts/maintenance.py`, `/meta`의 `last_run`(마지막 정상 게시)·`stale`. 예약 실행과 경보 연결은 남았다([Plan 05 구현 기록](05-trend-cloud-run-deployment.md#구현-기록)).
   `stale`은 게시가 멈춘 것만 뜻한다. 지도·대시보드는 저장된 행으로 다시 만들어 수집원이 모두 실패해도 성공하므로, 수집원 실패는 관리 화면 '수집 현황'과 `health_check.py`가 본다.
6. **품질 평가와 시연.** 같은 원자료의 Gemma 초안, 근거 검사, 사람 수정, 게시본을 추적한다. 언어별 뜻 보존·국가별 차이·출처에 없는 주장·처리 시간을 측정해 Plan 09에 넣는다. 미세조정 모델을 실제 채택한 경우에만 해당 어댑터와 전후 평가 결과를 제출 근거로 사용한다.

## 완료 기준

- 실행 담당자가 세션 한도·실제 배정 GPU를 확인하고, 합성 표본으로 Kaggle에서 설치·추론·Output 저장·이전 버전 Output으로부터의 재개를 검증한다. 팀원 계정에서 비공개 Dataset에 접근해 같은 실행을 할 수 있음을 확인한다.
- 팀원 두 명이 같은 Git/DVC 버전에서 입력 해시를 재현하고 Kaggle 실표본 추론·감사관 학습/재개를 실행한다. Output을 회수·검증해 GCS/DVC에 등록하고 GPU·모델·입력·프롬프트·기본 모델 revision을 추적한다.
- Kaggle의 Gemma 편집 배치가 검증된 사전 언어판과 국가별 해석 초안을 만들고, 근거·사람 검수를 거친 결과만 별도 게시 도구로 운영 DB에 반영한다.
- 검증되지 않은 초안은 공개 API에 노출되지 않고, 같은 배치를 다시 실행하거나 오래된 배치를 게시하려 해도 뜻 버전과 게시 데이터가 손상되지 않는다.
- PC와 Kaggle이 꺼져도 공개 지도·사전·게시 결과가 열리고 갱신 시각·오래된 자료 상태가 정확하다. 보존 정리와 운영 건강 점검도 독립적으로 동작한다.
- 실시간 사용자 기능은 Kaggle이나 PC의 Gemma 없이 작동하며, 사용자 원문은 Kaggle·PC로 전달하지 않는다.
- 미세조정은 선택 실험으로 성공·실패·보류 및 실측 제약을 기록한다. 성공이라고 기록하려면 학습 재개와 보류 평가 세트의 전후 비교를 확인한다. 품질이 개선되지 않으면 기본 모델을 유지한다.
- 대표 사례의 근거 일치와 품질을 Plan 09에서 평가해 실제 Gemma 활용 결과를 설명한다. 추론 노트북 실행만으로 가중치를 학습했다고 쓰지 않는다.

## 과거 상태와 당시 남은 일 (2026-09-29 실측)

아래는 당시 구현 상태의 기록이다. 현재 진척도는 [10-01 실측 점검](구현-완료도-실측-점검-2026-10-01.md), 최신 실행 순서와 게시 경계는 Plan 17을 따른다. 초안 공개·사용자 원문 전달·수집 서버 PostgreSQL 전환을 선택하는 실행 지시로 사용하지 않는다.

**지금 실제로 도는 Gemma 편집은 클라우드 노트북이 아니라 원작자 PC 다.** 원작자 서버 파이프라인(cron 9·14·19·23시 :15)이 로컬 Ollama 의 `gemma4:e4b`(그 서버 `.env` 의 `GEMMA_LOCAL_MODEL`; 코드 기본값은 `gemma4:12b`, 공유 Ollama 에는 12b 가 설치돼 있지 않다)로 번역·국가별 해석·추천 낱말·근거 라벨을 만든다. 09-29 기준 번역 표에는 `gemma-local` 276행과 `team` 96행이 있고 주제별 국가 해설(`topic_notes`)은 88건이 `local:gem…` 로 표시돼 있다. 6건은 `local:gpt-oss` 가 만들었다.

| 완료 기준 | 상태 | 근거 |
| --- | --- | --- |
| Gemma 초안을 만들고 모델 ID·시각·근거·검수 상태 추적 | 일부 | 위 PC 파이프라인이 만들지만, 번역에 모델 ID 를 `local:{GEMMA_LOCAL_MODEL}` 로 남기지 않고 실행마다 모델도 기록하지 않는다 |
| 검증 안 된 초안은 공개 API 에 안 나가고 재실행에도 안전 | **팀 결정 대기** | `GET /terms/{id}` 는 제외되지 않은 모든 용어를 돌려주고(`api/app.py`) `needs_review` 도 200 이다. `/explain` 도 그렇다. 게시 경계(직접 쓰기 또는 단계 게시)와 표시된 `needs_review` 초안을 이용자에게 보일지 정해야 한다 |
| PC 가 꺼져도 지도·사전·게시본이 열리고 갱신 시각이 정확 | 미충족 | 클라우드에 배포된 것이 없다([Plan 05](05-trend-cloud-run-deployment.md)). `/meta` 의 마지막 실행 시각은 어느 단계든 끝난 시각(`dictionary_store.py`)이라 수집기만 돌았어도 신선해 보인다 |
| 실시간 기능이 PC·Gemma 없이 작동, 원문은 PC 로 안 감 | 미충족 | `/ask`·`/ask/stream` 의 도구 호출 루프는 로컬 모델(`local_chat.chat_with_tools`)로만 돈다. 로컬 모델이 없으면 규칙 폴백뿐이다 |
| 정리·건강 점검이 PC 배치와 독립 | 미충족 | Plan 05 의 같은 항목(정리는 `collect.retention` 안에만, `health_check.py` 는 출력만) |
| Gemma 사용의 품질 평가 | 미충족 | `docs/트렌드/평가.md`(09-15 자동 생성)에 Gemma 초안 대 게시본 비교가 없다. [Plan 09](09-generation-quality-evaluation.md) 는 '1차 측정 · 사람 판정 전' |

남은 일:

1. 번역 모델 ID 를 `local:{GEMMA_LOCAL_MODEL}`(`gemini.generate` 와 같은 꼴)로 남기고 실행마다 모델을 기록한다. 문서의 '12b' 서술을 실제 엔진(e4b)에 맞춘다.
2. **팀 결정 대기:** 게시 경계 – 직접 쓰기인지 단계 게시인지, `needs_review` 초안을 이용자에게 보일지. 결정 뒤 `publications` 표(게시 시각·실행 ID·모델 ID·건수, 새 마이그레이션)와 마지막 정상 게시본을 덮지 않는 게시 단계를 만든다.
3. `/meta` 가 '마지막으로 성공한 편집 단계 시각' 과 오래됨 표시를 돌려주게 한다.
4. `/ask` 의 클라우드 경로: 로컬 모델이 없을 때 같은 읽기 전용 도구 루프를 Gemini 함수 호출(`model_client`, 요청 장부·한 번 시도)로 돌린다. 마지막 턴 무도구·차단기·인자 검증 규칙은 유지한다. 이용자 요청 호출에는 `request=True` 를 붙인다.
5. **팀 결정 대기:** 답하지 못한 질문이 원문 없이 PC 로 가는 방법(클라우드에서 표현 이름만 뽑아 넘기거나, 원문 전달을 받아들이고 문서화).
6. 원작자 서버의 예약 파이프라인(SQLite, Gemini 키)을 팀 코드·PostgreSQL 로 옮기고 Cloud SQL 에 Auth Proxy 로 최소 권한 연결한다. `migrate_sqlite_to_postgres.py` 는 삽입만 하므로(`ON CONFLICT DO NOTHING`) 갱신이 안 전파된다 – 주기적 게시·동기화를 따로 만든다.
7. `local:gpt-oss` 가 만든 주제 해설 6건을 Gemma 로 다시 만들거나 뺀다(이용자에게 보이고 추천의 `local_note` 로 나올 수 있다).
8. 대표 사례의 자동 지표(뜻 표기 보존·근거 ID 존재·처리 시간)와 사람 판정(뉘앙스·나라별 정확도)을 [Plan 09](09-generation-quality-evaluation.md) 로 잰다.

## 제외한 계획

- 종전 `builder-cup-gemma` Cloud Run GPU 배포안은 대체됐다. GCE GPU·내부 gateway·IAM·경보는 Plan 17에서 구축한다. Ollama로 기존 GGUF를 재현하고 vLLM은 모델·어댑터 지원과 품질을 검증한 뒤 선택한다.
- **무료 Colab.** 무료 계정에 GPU 컴퓨팅 자원이 없어 Gemma 추론·학습을 할 수 없었다(2026-09-30·10-01 확인). Drive 입출력 경로는 더 쓰지 않는다. 기록은 위 'Colab에서 Kaggle로 옮긴 까닭'의 링크에 있다.
- **Kaggle에서 장기 GCP 키·운영 DB 자격증명을 사용하는 직접 연동, Drive·BigQuery 신규 연동.** GCS 자체는 제외하지 않는다. Plan 17의 비공개 GCS·DVC가 데이터/모델 버전 원본이며, Kaggle은 필요한 파일만 비공개 Dataset으로 전달받는다. 버전 Output은 개발 환경에서 회수·검증한 뒤 GCS/DVC에 등록한다. 단기 인증 직접 접근은 별도 검증 뒤 추가한다.
- Kaggle 노트북을 상시 서버로 쓰거나 Cloud Run API가 Kaggle·개발자 PC의 Ollama에 실시간 접속하는 경로를 만들지 않는다.
- 무료 GPU(16 GB)에서 12B 전체 가중치 학습을 완료하는 것은 목표가 아니다. QLoRA도 실측 전 완료 시간·품질을 보장하지 않는다.
- 팀원이 같은 세션이나 모델 메모리를 공유한다고 가정하지 않는다. 각자 실행하고 승인된 입력·결과·체크포인트만 공유한다.
- 모델 크기·GPU·프롬프트가 다른 실험의 품질·비용·속도를 동일한 결과로 취급하지 않는다.

## 구현 기록

### 완료 기준 1 – 모델 ID 추적 (2026-09-29)

- 로컬 번역(`pipeline/translate.py`)이 `gemma-local` 대신 실제 ID `local:<GEMMA_LOCAL_MODEL>`(`gemini.generate`와 같은 꼴)을 `translations.model`에 남긴다.
  국가별 해석(`topic_notes`)·쓰임 낱말(`term_fit`)·근거 분류(`evidence_labels`)·조사 초안(`research_log`)은 이미 `local:<모델>`을 남기고 있었다.
- 단계 실행마다 부른 모델을 `pipeline_runs.models`에 남긴다(마이그레이션 011, 쉼표로 이음, 부르지 않은 실행은 NULL). `pipeline/gemini.py`가 호출이 성공할 때
  `runs.record_model`로 적고, `gemini.py`를 거치지 않는 영상 해석·검색 grounding 조사·로컬 번역은 그 자리에서 적는다. `run_pipeline.py` 로그 줄에도 `models=`로 보인다.
  테스트 `tests/test_model_ids.py`.
- 원작자 서버 사본(2026-09-29 23:58) 기준: 번역 382건 중 `gemma-local` 286건(09-15~09-29)·`team` 96건(팀이 쓴 시드). `gemma-local`은 모델이 남지 않았고,
  같은 시기 다른 표에 `local:gemma4:12b`(09-15 01~04시 UTC)·`local:gpt-oss`(09-15 06시)·`local:gemma4:e4b`(09-15 05시부터)가 섞여 있어 추정으로 채우지 않았다.
  국가별 해석 114건은 e4b 90·12b 18·gpt-oss 6, 쓰임 낱말 158건과 근거 분류 1,258건은 모두 e4b다.
- 문서의 모델 이름을 바로잡았다. 원작자 PC는 12B가 아니라 `gemma4:e4b`로 돈다(Plan 03의 234초 분류도 E4B).

### 완료 기준 6 – 편집 품질 규칙 지표 (2026-09-29)

`apps/trend-api/scripts/eval_editing.py`가 저장된 편집 결과를 모델 없이 산출물·모델별로 잰다(표제어 원문 보존·현지 밈 앵커·근거 id·건당 처리 시간·사람 수정률).
결과 표와 읽는 법은 [평가표](../트렌드/평가.md)의 '로컬 Gemma 편집 품질'. 원작자 서버 사본(09-29 23:58) 기준 요약:

| 산출물 (e4b) | 규칙 지표 |
| --- | --- |
| 번역 286건(모델 미기록) | 원래 뜻(번역한 때의 판)에 표제어가 있던 것 중 한국어판 32/34·영어판 27/34 유지. 빠진 9건 중 5건은 옮겨 적기·번역(훼손 – 한국어판 2·영어판 예문 속 3), 영어판 4건은 되풀이하지 않음. 24건은 옛 뜻을 옮긴 번역(09-16). 건당 2.3초 |
| 국가별 해석 90건 | 현지 밈 212개 중 인용한 보이는 근거에 있는 것 38%, 인용 밖 그 말의 다른 보이는 근거 5%, 커뮤니티 글에만 53%, 없음 3%, 표제어 되풀이 23%. 건당 10.1초(수집 포함) |
| 근거 분류 1,258문장 | 표제어가 든 문장 90%, 딴 이야기 21%. 문장당 0.27초 |
| 뜻 초안 690개 | 게이트 통과 22%. 사람이 정한 12개는 모두 제외·교체(검토 스크립트 10·시드 교체 2) – 검수 화면에서 정한 기록은 아직 없음. 사람이 안 보고 지금 실린 판 108개 |

남은 일: 표본 36건(`-judge.csv`)에 사람이 '근거에 없는 주장'·'국가별 차이 오류'를 채운다. 커뮤니티 글에만 앵커된 현지 밈은 `topics`가 옛 해석을 다시 쓰지 않아
지도에 그대로 나가므로(확신 0.5 이상 e4b 85건), 옛 해석을 다시 만들지 읽을 때 걸러 낼지 정해야 한다.
