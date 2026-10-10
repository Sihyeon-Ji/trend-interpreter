-- 관리 화면 '수동 실행'(Gemma 실시간 분류 2단계)도 같은 기록 표에 남긴다. kind: live(사전 항목 버튼) · rerun(관리자 수동 실행). 비어 있으면 live.
ALTER TABLE live_risk_runs ADD COLUMN IF NOT EXISTS kind TEXT;
