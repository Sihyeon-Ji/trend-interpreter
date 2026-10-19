# 10-27 ~ 10-28 실제 청구 확인

실행일 **2026-10-27 ~ 10-28** · 담당 **shji(지시현)** · 상태 **대기** · 선행 [10-20 Cloud SQL 전환](2026-10-20-cloud-sql-transition.md)

[계획 목록](README.md) · [GCP 운영](../운영/GCP-운영.md) · [옛 Plan 13](archive/13-cloud-sql-trial-to-paid-transition.md)

## 할 일

- Billing 보고서에서 Cloud SQL·Cloud Run·Vertex AI(Gemini)·GCS·Artifact Registry·GPU(쓴 경우, [Gemma 실시간 분류](archive/ejchoi-gemma-live-classify.md))의 실제 청구와 SKU를 확인한다.
- 전환 때 정한 월 비용 상한·예상치와 비교하고, 넘은 항목은 원인과 조치를 적는다.
- 새 인스턴스의 운영 서비스·백업·유지보수·게시 Job 검증 기록을 확인한 뒤 옛 체험 인스턴스를 정리한다.

## 완료 기준

- 항목별 실제 청구와 예상치의 차이를 기록했다.
- 새 인스턴스 검증 후 옛 체험 인스턴스 정리 결과를 기록했다.
