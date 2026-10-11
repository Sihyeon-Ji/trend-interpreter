-- Gemma 실시간 분류·수동 실행의 마지막 실제 결과(용어·종류마다 하나). GPU 가 꺼져 있을 때 심사용 화면이 이 기록을 보여 준다.
-- 공개 기사 제목과 분류 결과(뉘앙스·위험 유형)·규칙 판정만 담는다. 이용자 문장은 없다. 새로 돌리면 덮어쓴다.
CREATE TABLE IF NOT EXISTS live_risk_snapshots (term_id TEXT, kind TEXT, run_at TEXT, payload TEXT, PRIMARY KEY(term_id, kind));
