# 05. 주제 선정과 제출 준비 기준선

상태 **선정 절차·공식 요건 기준선 구현 완료, 팀 주제 결정 대기** · 우선순위 **현재** · [전체 계획](README.md)

## 해결할 문제와 목표

Plan 01~04로 개발·평가·이력·DB 복구 기반은 준비됐지만 팀의 최종 주제는 정해지지 않았습니다.
새로 모은 일정·심사·제출 문서에는 서로 다른 날짜와 category·영상 길이가 섞여 있어 그대로 사용하면
실격 요건이나 내부 일정을 잘못 잡을 수 있습니다.

목표는 **공식 정보와 내부 참고 자료를 구분하고, 모든 후보를 같은 hard gate·심사 배점·delivery risk로
평가해 팀이 한 가지 주제를 결정할 수 있게 하는 것**입니다. 이 계획에서 주제를 임의로 선택하지 않습니다.

## 구현 결과

- [공식 일정 기준선](../schedule/official-timeline.md)에 현재 Overview 일정과 FAQ 충돌을 분리했습니다.
- [공식 참가·제출 요건](../submission-requirements/official-requirements-baseline.md)에 자격·fresh project·Google AI·Cloud 배포·제출물을 정리했습니다.
- [제출 준비 체크리스트](../submission-requirements/submission-readiness-checklist.md)에 자격·제품·평가·제출 증거 상태를 기록하도록 했습니다.
- [후보 등록부](../topic-discovery/candidate-register.md)에 기존 아이디어와 Clearance 조사를 12개 후보로 정규화했습니다.
- [후보 점수표](../topic-discovery/candidate-scorecard-template.md)는 공식 40/25/25/10 배점과 별도 delivery risk를 사용합니다.
- [주제 선정 절차](../topic-discovery/topic-selection-process.md)에 hard gate → evidence pack → 독립 채점 → 상위 3개 spike → 팀 결정 순서를 정의했습니다.
- [문서 색인](../README.md)에서 새 문서와 기존 개발 문서의 위치를 찾을 수 있습니다.

## 공식 확인 결과 — 2026-09-23

| 항목 | 확인 결과 |
| --- | --- |
| 참가자 | working professional·entrepreneur·startup, 21+, JAPAC, 학생 불가 |
| 팀 | 2~4명, 한 사람은 한 팀, 한 팀은 한 솔루션·테마 |
| 프로젝트 | 행사 기간에 시작한 fresh project만 가능 |
| AI·Cloud | Gemini·Gemma 또는 지정 agent platform, Cloud Run/GCP/Firebase 배포 |
| 공식 테마 | BFSI, Retail, Manufacturing, Media, Future of Work, Sustainability 총 6개 |
| 제출물 | 작동 링크, 3분 미만 공개 영상, 공개 GitHub, 상세 deck/PDF |
| 언어 | 코드·문서·발표 자료를 포함한 제출 자료는 영어 |
| 평가 | Technical 40, Alignment 25, Innovation 25, UX 10 |
| 일정 | 팀 구성 10월 11일, 제출 10월 18일, 발표 11월 7일, 결선 12월 4일 |

공식 FAQ에는 팀원 교체 가능 기간이 10월 4일까지라고 적혀 Overview의 10월 11일과 충돌합니다.
Themes 페이지의 category 예시는 공식 여섯 테마와 다른 목록을 사용합니다. 영상 길이도 로컬 템플릿의
3~4분보다 FAQ의 3분 미만이 더 엄격합니다. 이 세 항목은 보수적인 기준을 사용하고 실제 form 또는
운영사 답변으로 최종 확인하도록 표시했습니다.

## 완료 기준 점검

| 기준 | 상태 |
| --- | --- |
| 모든 `docs/` 경로를 영어 파일·디렉터리명으로 통일 | 완료 |
| 공식 정보와 내부 이미지·메모 구분 | 완료 |
| 실격 가능 hard gate 정의 | 완료 |
| 공식 심사 배점 기반 점수표 | 완료 |
| 데이터·권리·비용·demo delivery risk 분리 | 완료 |
| 기존 후보를 누락 없이 등록 | 완료, 후보별 증거 보강 필요 |
| 최종 주제 한 가지 선택 | 팀 결정 대기 |

## 팀이 다음으로 할 일

1. 후보 소유자는 점수표와 최소 evidence pack을 작성합니다.
2. 데이터 없음·fresh project 불명·Google AI 핵심성 부족 후보를 먼저 보류합니다.
3. 독립 채점 후 상위 3개에만 2일 이내 기술 spike와 3분 demo storyboard를 만듭니다.
4. 결과를 다시 채점해 한 후보를 선택하고 결정 기록을 채웁니다.
5. 선택 직후 제출 체크리스트의 담당자·내부 마감·증거 링크를 확정합니다.

이 계획의 문서·프로세스 구현은 완료됐지만 제품 주제는 아직 정해지지 않았습니다.
주제 선택 이후에는 해당 사용자·데이터·품질 합격선에 맞춘 제품 구현 계획을 새로 작성해야 합니다.
