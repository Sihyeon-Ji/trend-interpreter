-- 위키 밈 분류(Plan 16): 표제어가 걸린 분류 이름들(종류·연대·나라). 제목·분류만, 본문 없음.
CREATE TABLE IF NOT EXISTS wiki_catalog (term_id TEXT, source TEXT, title TEXT, categories_json TEXT, fetched_at TEXT, PRIMARY KEY(term_id, source, title));
