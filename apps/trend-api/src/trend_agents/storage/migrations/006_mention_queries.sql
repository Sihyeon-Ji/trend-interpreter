-- 용어마다 뉴스 검색으로 언급을 마지막으로 잰 때. collect.mentions 가 한 번도 안 잰 것·오래된 것부터 돌아가며 잰다
-- (재검증 주기로만 줄 세우면 같은 30개만 매번 재서 나머지의 언급이 늘 0 이었다, 2026-09-29 검토 2차).
CREATE TABLE IF NOT EXISTS mention_queries (term_id TEXT PRIMARY KEY, last_at TEXT);
