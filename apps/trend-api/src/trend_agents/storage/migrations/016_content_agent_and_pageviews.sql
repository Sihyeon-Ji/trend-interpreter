-- 위키 월별 조회수(과거 관심 추이)와 콘텐츠 조사 에이전트의 기록 (2026-10-01).
CREATE TABLE IF NOT EXISTS term_pageviews (term_id TEXT, lang TEXT, title TEXT, month TEXT, views BIGINT, PRIMARY KEY(term_id, lang, month));
CREATE TABLE IF NOT EXISTS pageviews_done (term_id TEXT PRIMARY KEY, at TEXT);
CREATE TABLE IF NOT EXISTS content_index (content_key TEXT PRIMARY KEY, name TEXT, labels_json TEXT, last_run TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS content_findings (run_id TEXT, content_key TEXT, name TEXT, region TEXT, description TEXT, quote TEXT,
  evidence_url TEXT, sentence TEXT, same_as TEXT, verified INTEGER, reason TEXT, term_id TEXT, created_at TEXT, PRIMARY KEY(run_id, name, region));
CREATE TABLE IF NOT EXISTS content_pairs (run_id TEXT, content_key TEXT, a TEXT, a_region TEXT, b TEXT, b_region TEXT, reason TEXT,
  verified INTEGER, why TEXT, PRIMARY KEY(run_id, a, b));
CREATE TABLE IF NOT EXISTS agent_trace (run_id TEXT, step INTEGER, thought TEXT, tool TEXT, args_json TEXT, result TEXT, at TEXT, PRIMARY KEY(run_id, step));
-- 표제어마다 '지금 뜻' 을 찾는 일이 가장 잦다 — 1만 개를 넘자 색인 없이 질문 하나에 225초(트윈 SQLite 실측)
CREATE INDEX IF NOT EXISTS meanings_term ON meanings(term_id, valid_to, version);
CREATE INDEX IF NOT EXISTS evidences_term ON evidences(term_id);
