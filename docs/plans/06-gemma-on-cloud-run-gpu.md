# Plan 06. Kaggle Gemma 4 편집·미세조정 실험과 운영 데이터 게시

작성일 **2026-09-28** · 변경일 **2026-10-01** · 상태 **실험 위치를 Colab에서 Kaggle로 변경, Kaggle 실행은 아직 검증 전 · 운영 게시 경계·PC 독립 정리/감시·클라우드 전용 /ask·Gemma 평가는 미구현(Plan 05 Cloud SQL 대기) · 그동안 Gemma 편집은 원작자 PC 파이프라인이 하루 4회 대신 돌린다(아래 '현재 상태') · 12B QLoRA는 학습 서버에서 실행했다([Plan 16](16-wiki-meme-catalog-and-tendency.md))** · 선행 [Plan 01](01-import-latest-trend-data.md)의 최신 데이터와 [Plan 05](05-trend-cloud-run-deployment.md)의 Cloud SQL · 목표일 **2026-10-10**

> 파일 경로는 기존 링크를 위해 유지한다. 2026-09-29에 [개발자 PC Gemma 결정](../AI-개발/Gemma-로컬-편집-엔진-결정.md)을 바꿔 실험 위치를 Colab GPU로 옮겼고, **2026-10-01에 다시 Kaggle 노트북으로 옮겼다**(아래 'Colab에서 Kaggle로 옮긴 까닭'). 사용자 요청을 무료 노트북 런타임에 연결하지 않는 경계는 유지한다. 운영에 Gemma 서비스를 둘지는 [Plan 14](14-gemma-visible-in-deployment.md)에서 협의 중이며 아직 정하지 않았다. Kaggle GPU를 쓸 수 없거나 할당이 떨어지면 로컬 PC의 Ollama가 오프라인 배치 편집의 대체 경로다.

[계획 목록](README.md) · [Plan 01 데이터 이관](01-import-latest-trend-data.md) · [Plan 05 배포](05-trend-cloud-run-deployment.md) · [Gemma 리스크 실험 노트북](../../models/kaggle/gemma_risk_labeling.ipynb) · [파이프라인 기록](../트렌드/파이프라인.md)

## 목적

팀원이 자기 Kaggle 계정의 **노트북 GPU**에서 Ollama와 Gemma 4를 실행해 공개 트렌드 근거의 리스크 분류를 실험하고, 검증된 사전 언어판·국가별 해석의 초안을 **오프라인 배치**로 만든다. 근거 대조·규칙 검증·사람 검수를 통과한 결과만 Cloud SQL에 게시한다. SaaS 사용자는 Cloud Run 웹·API에서 마지막 성공 게시본을 읽고, 사용자별 실시간 생성이 필요할 때 Vertex AI Gemini를 사용한다. **Kaggle 노트북이 꺼져도 공개 서비스는 동작해야 한다.**

대회는 Gemini 또는 Gemma 등 Google AI 모델의 활용을 허용한다. Gemma의 역할은 공개 트렌드 자료를 작은 오픈 모델로 가공해 여러 사용자에게 재사용 가능한 지식 자산을 만드는 것이다. 모델 이름보다 원자료·근거·검수·게시 결과를 연결해 보여 준다.

현재 `models/kaggle/gemma_risk_labeling.ipynb`는 **Plan 03 리스크 분류의 프롬프트·모델 비교용**이다. Gemma 가중치를 학습하거나 미세조정하지 않으며, 사전 번역·국가별 해석을 만들거나 Cloud SQL에 게시하지도 않는다. 표본 CSV와 서버 환경 JSON이 없으면 합성 문장으로 작동만 확인하므로 품질 수치로 사용하지 않는다. 이 노트북의 존재만으로 Plan 06이 구현됐다고 기록하지 않는다.

## Colab에서 Kaggle로 옮긴 까닭 (2026-10-01)

**무료 Colab에서는 GPU를 사실상 받을 수 없었다.** 2026-09-30 무료 T4 배정이 사용량 제한으로 거절됐고 컴퓨팅 단위는 0이었다. 이후 사용자가 확인한 결과, 무료 계정에 GPU를 쓸 컴퓨팅 자원이 없어 Gemma 4 추론·학습을 진행할 수 없었다. Colab에서 확인한 것은 소유자 Drive의 입력 읽기·결과 쓰기·재마운트 보존과 합성 표본의 입출력뿐이고, **Gemma 추론과 학습은 한 번도 실행하지 못했다.**

Kaggle은 무료 GPU를 **주간 할당량으로 공개**하고 남은 시간을 계정 화면에 보여 준다. 그래서 실험 위치를 Kaggle로 옮긴다. Colab 조사 전문(Drive 공유·마운트 권한·런타임 제한 실측)은 [옮기기 전 Plan 06](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/blob/8725154debe17b729b950f6548bb5c822e755847/docs/plans/06-gemma-on-cloud-run-gpu.md)과 [옛 Colab 노트북](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/blob/8725154debe17b729b950f6548bb5c822e755847/models/colab/gemma_risk_labeling.ipynb)에 남아 있다. 소유자 Drive의 `Builder-Cup-Trend-Colab` 폴더에는 합성 표본과 연결 시험 파일만 있으므로 더 쓰지 않는다. 정리는 소유자가 판단한다.

## Kaggle 무료 자원 (2026-10-01 조사)

아래 값은 2026년 9월 기준 여러 외부 정리에서 서로 일치한 것이다. Kaggle 공식 문서 페이지는 이번 조사에서 본문을 직접 읽지 못했으므로 **실행 담당자가 계정 설정의 할당량 화면으로 확인한 뒤** 이 표를 고친다.

| 항목 | 내용 |
| --- | --- |
| GPU | 주당 약 30시간. **T4 2장(각 16 GB)** 또는 P100 1장(16 GB) 중 선택 |
| TPU | v3-8, 주당 20시간 |
| 한 세션 | GPU 최대 12시간, TPU 최대 9시간 |
| 저장 | `/kaggle/working` 20 GB가 버전 Output으로 남는다. 그 밖의 디스크는 세션이 끝나면 사라진다. 비공개 Dataset은 합계 200 GB |
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
| 가중치 미세조정(QLoRA) | 학습 서버(RTX 4090). Kaggle은 서버 없이 실험할 때의 경로 | 채택 전 보류 평가 세트에서 전후 비교 |
| 뜻의 검증 상태·생애주기·리스크 | 코드 규칙과 사람 검수 | 모델의 단독 판정 금지, 뜻 버전 유지 |
| 지도·사전·리포트 열람 | Cloud Run 웹·API와 Cloud SQL | 마지막 성공 게시본 제공, 갱신 시각 표시 |
| 신규 사진·홍보 문구 이해, 카피·대본 생성 | Cloud Run API가 Vertex AI Gemini 호출 | 요청 시 처리, 호출 예산 적용 |
| 새 메시지 재작성·사전 질문 응답 | 저장된 근거·규칙 우선, 필요 시 Gemini | Kaggle·개발자 PC에 실시간 의존하지 않도록 별도 구현·평가 |

현재 `USE_LOCAL_GEMMA=1` 라우팅은 현행 파이프라인의 Ollama 경로를 뜻한다. **Kaggle에서 노트북을 돌려도 `run_pipeline.py`가 자동으로 Kaggle 모델을 호출하지 않는다.** 운영 API에는 `USE_LOCAL_GEMMA=0`을 기본으로 두고 `/explain`, `/ask`, Plan 07·08의 실시간 경로를 별도 검증한다.

## GitHub·Kaggle 노트북·Kaggle Dataset의 역할

| 위치 | 담는 것 | 보존·접근 |
| --- | --- | --- |
| GitHub `develop` | `.ipynb` 코드, 배치 입출력 계약, 검증 코드 | 팀이 버전 관리하는 원본이다 |
| 팀원별 Kaggle 노트북 세션 | 실행 중 설치한 Ollama, 받은 `gemma4:12b`, 임시 파일 | 계정마다 별개다. 세션이 끝나면 `/kaggle/working` 밖의 파일과 모델이 사라진다 |
| 비공개 Kaggle Dataset | 수집 서버에서 내보낸 표본 CSV와 `.env.json` | 노트북의 입력(`/kaggle/input`, 읽기 전용)으로 붙인다. 새 표본은 새 버전으로 올린다. 필요한 팀원만 Collaborator로 더한다 |
| 노트북 버전 Output | 실행별 결과·체크포인트·실행 메타데이터(`/kaggle/working/runs/<RUN_ID>`) | Save Version으로 돌린 버전마다 남는다. 다른 노트북이나 다음 버전의 입력으로 붙여 재개·비교한다 |
| 로컬 PostgreSQL·Cloud SQL | 원자료·검수 기록·마지막 승인 게시본 | Kaggle을 운영 DB로 쓰지 않는다. Kaggle에 DB 비밀번호나 전체 DB 덤프를 올리지 않는다 |

**Dataset과 노트북은 Private으로 둔다.** 표본에는 공개 기사·쇼츠·커뮤니티 글의 발췌가 들어 있다. 공개 Dataset·공개 노트북으로 바꾸면 Kaggle 전체에 공개되므로 바꾸지 않는다. Kaggle Secrets에도 운영 자격증명을 넣지 않는다. CSV·모델 파일·자격증명·검수 결과는 Git에 커밋하지 않는다.

## Kaggle·GitHub 코드 동기화

**코드 원본은 GitHub의 `models/kaggle/gemma_risk_labeling.ipynb`, 데이터는 Kaggle Dataset, 실행 결과는 노트북 버전 Output으로 관리한다.** Kaggle 편집기의 `File → Import Notebook`으로 가져온 노트북은 그 시점의 사본이다. 이후 GitHub 원본이 바뀌어도 Kaggle 사본은 따라오지 않고, Kaggle에서 고친 코드도 GitHub에 자동으로 반영되지 않는다.

1. Kaggle에서 바꾼 공통 코드가 있으면 `File → Download Notebook`으로 받아 개발 PC의 공통 노트북과 비교한다. 실행별 입력 경로·`RESUME_FROM` 같은 값은 공통 기본값으로 옮기지 않는다.
2. 모든 코드 셀 출력과 실행 횟수를 지우고, 원문·개인 계정 정보·토큰·CSV·결과·체크포인트·가중치가 들어 있지 않은지 확인한다.
3. 작업 브랜치에서 커밋하고 PR로 검토해 `develop`에 반영한다. Kaggle에서 `develop`이나 `release/gcp`로 바로 저장하지 않는다. `release/gcp` 푸시는 실제 배포를 유발한다. 같은 `.ipynb`를 두 사람이 동시에 고치지 않는다.
4. 팀원은 반영된 GitHub 버전을 새로 가져온다. Git 커밋과 모델·입력 해시를 실행 메타데이터에 연결한다. 진행 중인 실험 노트북을 최신 코드로 덮어쓰지 않는다.

## 팀원별 Kaggle 실행 절차

1. Kaggle 계정의 휴대폰 인증을 마친다. 한 사람이 여러 계정으로 할당을 우회하지 않는다.
2. 수집 서버가 새 `apps/trend-api` 코드와 PostgreSQL을 쓰는지 확인한다. `apps/trend-api/scripts/export_risk_sample.py`는 그 환경에서만 실표본을 낼 수 있다. Plan 01의 최신 SQLite 수령·이관이 아직이면 표본의 시점과 한계를 기록한다. 사용자 입력 표는 내보내지 않고 필요한 공개 근거 문장만 CSV로 추출한다.
3. CSV와 같은 이름의 `.env.json`을 **비공개 Dataset**으로 올린다. 실행할 팀원을 Collaborator로 더한다.
4. GitHub의 [리스크 노트북](../../models/kaggle/gemma_risk_labeling.ipynb)을 `File → Import Notebook`으로 가져온다. Settings에서 Accelerator를 **GPU T4 x2**로, Internet을 켜고, **Add Input**으로 표본 Dataset을 붙인다.
5. 먼저 `USE_SYNTHETIC_SAMPLE=True`로 합성 5문장의 설치·추론·메모리·시간·결과 저장을 확인한다. 이는 작동 확인이다. 이어서 실표본으로 셀을 순서대로 실행한다. Ollama 버전, `gemma4:12b`의 태그·digest, 프롬프트 해시, 호출 옵션을 서버 기준과 비교한다. 서버는 미분류 문장만 묶고 노트북은 최근 문장을 다시 묶으므로 같은 모델이어도 결과가 달라질 수 있다.
6. 남겨야 하는 실행은 **Save Version(Save & Run All)** 으로 돌린다. 결과는 그 버전의 Output `runs/<RUN_ID>`에 남는다. 중간에 끊겼으면 그 버전의 Output을 입력으로 붙이고 `RESUME_FROM`에 `runs/<RUN_ID>` 경로를 적어 다시 돌린다. 입력 해시·모델 digest·프롬프트·규칙이 같은 정상 완료 항목만 재사용한다.
7. 각자 다른 프롬프트 안을 별도 실행 ID로 비교한다. 서버 모델과의 일치율은 참고치다. CSV의 `human_*` 칸에 **사람이 독립적으로 판정한 값**을 넣어 오탐·누락과 근거를 비교한다. 합성 표본이나 사람 판정이 없는 일치율을 AI 품질 개선의 증거로 사용하지 않는다.

`path_check.json`은 **입출력 확인 단계의 기록**이며 `inference_executed=false`다. 실제 추론이 성공하면 `sentence_labels.csv`, `term_levels.csv`, `calls.csv`, `run.json`과 `checkpoint.json`이 같은 실행 폴더에 저장된다. 입력 검사 기록을 모델 추론 결과로 해석하지 않는다.

## 가중치 미세조정 실험 — 별도 스크립트

현재 Ollama 리스크 노트북은 `ollama.chat()`으로 답만 생성하므로 학습이 일어나지 않는다. 학습에는 정답이 붙은 입력·출력 쌍, 학습 프레임워크, 손실 계산·역전파, 체크포인트 저장 코드가 필요하다. Google의 [Gemma 텍스트 QLoRA 가이드](https://ai.google.dev/gemma/docs/core/huggingface_text_finetune_qlora)는 기본 모델을 4비트로 읽고 작은 **LoRA 어댑터 가중치**만 학습하는 예를 제공한다.

**12B QLoRA는 이미 학습 서버에서 돌았다.** `models/lora/audit_qlora.py`는 학습 서버의 RTX 4090 한 장에서 사전 감사관을 약 9분, 최대 9.8 GiB로 학습했다([Plan 16](16-wiki-meme-catalog-and-tendency.md)). 실행 환경은 `models/lora/pyproject.toml`과 `uv.lock`이다. 따라서 Kaggle 학습은 서버를 쓸 수 없는 팀원이 실험할 때의 보조 경로다.

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

1. **Kaggle 입력과 첫 실행.** 실행 담당자가 휴대폰 인증과 할당량을 확인하고 위 '무료 자원' 표를 고친다. 합성 표본으로 설치·추론·저장·재개를 확인한 뒤, Plan 01의 데이터 시점·근거 ID를 포함한 제한된 공개 표본을 비공개 Dataset으로 올리고 팀원 한 명의 계정에서도 같은 Dataset으로 실행해 본다. 실표본 실험은 최신 데이터가 준비되는 범위에서 진행하고 Cloud SQL 배포를 기다릴 필요는 없다.
2. **리스크 기준선과 선택적 미세조정 실험.** 현행 `gemma4:12b` 추론의 GPU 메모리·시간과 사람이 판정한 표본의 품질을 측정한다. 미세조정은 학습 서버를 기본으로 하고, Kaggle 학습은 fp16 짧은 시험을 통과한 경우에만 이어 간다. 성공·실패·보류 결정을 기록한다.
3. **Kaggle 편집 배치.** 검증된 뜻과 근거를 받아 사전 언어판·국가별 해석 초안을 만드는 입출력 계약과 배치를 구현한다. 원자료 수집·영상·검색 grounding은 현행 PC 파이프라인에 둔다. 출력에 입력 스냅샷·뜻 버전·모델 ID·프롬프트·검수 상태를 연결하고, 세션이 끊기면 완료된 항목부터 이어서 처리한다. 초안을 Output에 저장하는 것만으로 승인하지 않는다.
4. **검수와 운영 게시.** 스키마·근거·언어별 뜻 보존을 검사하고 사람이 승인한 결과만 별도 게시 도구로 Plan 05의 Cloud SQL에 반영한다. 게시 도구는 관리되는 PC 등에서 최소 쓰기 권한으로 실행하며 Kaggle에는 운영 DB 자격증명을 주지 않는다. 배치 ID와 뜻 버전으로 중복·오래된 결과의 덮어쓰기를 막고, 실패 시 마지막 정상 게시본을 유지한다. Cloud SQL Auth Proxy를 쓰더라도 private IP에는 별도 네트워크 경로가 필요하다. 자격증명·사용자 원문·생성 결과 전문은 운영 로그나 Git에 기록하지 않는다.
5. **서비스 분리와 보존·감시.** Cloud Run 웹·API는 PC와 Kaggle이 꺼져도 게시 자료를 읽어야 한다. 운영 `USE_LOCAL_GEMMA=0`을 기본으로 하고 실시간 자유 서술은 Gemini 또는 사전 기반 규칙으로 구현·검증한다. 해석 캐시 7일·미해결 질문 30일 삭제, 마지막 정상 게시 시각과 오래된 자료 경보는 Plan 05의 독립 예약 작업으로 운영한다.
6. **품질 평가와 시연.** 같은 원자료의 Gemma 초안, 근거 검사, 사람 수정, 게시본을 추적한다. 언어별 뜻 보존·국가별 차이·출처에 없는 주장·처리 시간을 측정해 Plan 09에 넣는다. 미세조정 모델을 실제 채택한 경우에만 해당 어댑터와 전후 평가 결과를 제출 근거로 사용한다.

## 완료 기준

- 실행 담당자가 계정의 실제 GPU 할당량·세션 한도를 확인하고, 합성 표본으로 Kaggle에서 설치·추론·Output 저장·이전 버전 Output으로부터의 재개를 검증한다. 팀원 계정에서 비공개 Dataset에 접근해 같은 실행을 할 수 있음을 확인한다.
- 팀원이 자기 Kaggle 노트북에서 실표본 추론을 실행하고 결과를 버전 Output으로 남기며 다음 실행에서 다시 불러올 수 있다. GPU·모델·입력·프롬프트 버전을 추적할 수 있다.
- Kaggle의 Gemma 편집 배치가 검증된 사전 언어판과 국가별 해석 초안을 만들고, 근거·사람 검수를 거친 결과만 별도 게시 도구로 운영 DB에 반영한다.
- 검증되지 않은 초안은 공개 API에 노출되지 않고, 같은 배치를 다시 실행하거나 오래된 배치를 게시하려 해도 뜻 버전과 게시 데이터가 손상되지 않는다.
- PC와 Kaggle이 꺼져도 공개 지도·사전·게시 결과가 열리고 갱신 시각·오래된 자료 상태가 정확하다. 보존 정리와 운영 건강 점검도 독립적으로 동작한다.
- 실시간 사용자 기능은 Kaggle이나 PC의 Gemma 없이 작동하며, 사용자 원문은 Kaggle·PC로 전달하지 않는다.
- 미세조정은 선택 실험으로 성공·실패·보류 및 실측 제약을 기록한다. 성공이라고 기록하려면 학습 재개와 보류 평가 세트의 전후 비교를 확인한다. 품질이 개선되지 않으면 기본 모델을 유지한다.
- 대표 사례의 근거 일치와 품질을 Plan 09에서 평가해 실제 Gemma 활용 결과를 설명한다. 추론 노트북 실행만으로 가중치를 학습했다고 쓰지 않는다.

## 현재 상태와 남은 일 (2026-09-29 실측)

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
2. **팀 결정 대기:** 게시 경계 — 직접 쓰기인지 단계 게시인지, `needs_review` 초안을 이용자에게 보일지. 결정 뒤 `publications` 표(게시 시각·실행 ID·모델 ID·건수, 새 마이그레이션)와 마지막 정상 게시본을 덮지 않는 게시 단계를 만든다.
3. `/meta` 가 '마지막으로 성공한 편집 단계 시각' 과 오래됨 표시를 돌려주게 한다.
4. `/ask` 의 클라우드 경로: 로컬 모델이 없을 때 같은 읽기 전용 도구 루프를 Gemini 함수 호출(`model_client`, 요청 장부·한 번 시도)로 돌린다. 마지막 턴 무도구·차단기·인자 검증 규칙은 유지한다. 이용자 요청 호출에는 `request=True` 를 붙인다.
5. **팀 결정 대기:** 답하지 못한 질문이 원문 없이 PC 로 가는 방법(클라우드에서 표현 이름만 뽑아 넘기거나, 원문 전달을 받아들이고 문서화).
6. 원작자 서버의 예약 파이프라인(SQLite, Gemini 키)을 팀 코드·PostgreSQL 로 옮기고 Cloud SQL 에 Auth Proxy 로 최소 권한 연결한다. `migrate_sqlite_to_postgres.py` 는 삽입만 하므로(`ON CONFLICT DO NOTHING`) 갱신이 안 전파된다 — 주기적 게시·동기화를 따로 만든다.
7. `local:gpt-oss` 가 만든 주제 해설 6건을 Gemma 로 다시 만들거나 뺀다(이용자에게 보이고 추천의 `local_note` 로 나올 수 있다).
8. 대표 사례의 자동 지표(뜻 표기 보존·근거 ID 존재·처리 시간)와 사람 판정(뉘앙스·나라별 정확도)을 [Plan 09](09-generation-quality-evaluation.md) 로 잰다.

## 제외한 계획

- `builder-cup-gemma` Cloud Run GPU 서비스, vLLM 이미지, GPU IAM·인스턴스 경보는 이 계획에서 만들지 않는다. 운영 Gemma 서비스는 [Plan 14](14-gemma-visible-in-deployment.md)에서 협의 중이다.
- **무료 Colab.** 무료 계정에 GPU 컴퓨팅 자원이 없어 Gemma 추론·학습을 할 수 없었다(2026-09-30·10-01 확인). Drive 입출력 경로는 더 쓰지 않는다. 기록은 위 'Colab에서 Kaggle로 옮긴 까닭'의 링크에 있다.
- Kaggle 노트북을 상시 서버로 쓰거나 Cloud Run API가 Kaggle·개발자 PC의 Ollama에 실시간 접속하는 경로를 만들지 않는다.
- 무료 GPU(16 GB)에서 12B 전체 가중치 학습을 완료하는 것은 목표가 아니다. QLoRA도 실측 전 완료 시간·품질을 보장하지 않는다.
- 팀원이 같은 세션이나 모델 메모리를 공유한다고 가정하지 않는다. 각자 실행하고 승인된 입력·결과·체크포인트만 공유한다.
- 모델 크기·GPU·프롬프트가 다른 실험의 품질·비용·속도를 동일한 결과로 취급하지 않는다.
