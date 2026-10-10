-- 사전 항목의 '지금 다시 분류해 보기'(Gemma 실시간 분류, ejchoi 계획 1단계) 실행 기록. 문장·모델 출력 원문은 남기지 않는다.
CREATE TABLE IF NOT EXISTS live_risk_runs (run_at TEXT, term_id TEXT, status TEXT, sentences INTEGER, seconds REAL, level TEXT, model TEXT, PRIMARY KEY(run_at, term_id));
