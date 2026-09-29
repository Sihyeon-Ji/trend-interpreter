-- 검수 큐의 제안 종류(Plan 12 사전 전수 대조). 지금까지의 줄은 모두 조사 결과(new)다.
--   new        조사 결과 — 지금 판(확인 전)이 제안된 뜻
--   correction 고칠 안 — draft_json 이 고칠 안이고 지금 뜻은 그대로 실려 있다. 승인하면 새 판(verified_human)
--   conflict   위키끼리 다름 — docs_json 의 문서 설명 가운데 사람이 고른 것이 고칠 안과 같은 길로 간다
--   retire     사전에서 뺄지 — 승인하면 사람이 제외한다
-- docs_json 은 제안의 근거가 된 참고 문서 [{wiki, url, summary, proposal}] (본문은 두지 않는다).
ALTER TABLE review_queue ADD COLUMN IF NOT EXISTS kind TEXT;
ALTER TABLE review_queue ADD COLUMN IF NOT EXISTS docs_json TEXT;
UPDATE review_queue SET kind = 'new' WHERE kind IS NULL;
-- 문서 대조 기록. 판정·문서 주소·모델만.
CREATE TABLE IF NOT EXISTS crosscheck_log (term_id TEXT, checked_at TEXT, verdict TEXT, doc_urls_json TEXT, model TEXT);
