-- 밈 추천(Plan 07): 표제어마다 광고 쓰임 낱말(느낌·쓰임·어울리는 분야·말투). fit 단계가 로컬 Gemma 로 붙이고, 추천 점수는 규칙이 매긴다.
-- meaning_id 가 현재 뜻과 다르면 다시 붙인다.
CREATE TABLE IF NOT EXISTS term_fit (term_id TEXT PRIMARY KEY, meaning_id TEXT, json TEXT, model TEXT, labeled_at TEXT);
