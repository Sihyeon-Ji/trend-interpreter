-- 검수 결정 기록(Plan 12 검토). 검수 큐는 표제어마다 한 줄이라 새 제안이 올라오면 예전 결정이 덮였다 — 사람이 결정한 줄은
-- 결정할 때(와 덮기 전에) 여기에 남긴다. 사람이 이미 결정한 같은 내용의 제안을 다시 올리지 않는 데에도 쓴다. 게이트가 스스로 닫은 줄은 두지 않는다.
CREATE TABLE IF NOT EXISTS review_history (
  term_id TEXT, kind TEXT, draft_json TEXT, reasons_json TEXT, docs_json TEXT, queued_at TEXT, decision TEXT, decided_at TEXT, decided_by TEXT,
  PRIMARY KEY(term_id, queued_at, decided_at));
INSERT INTO review_history (term_id, kind, draft_json, reasons_json, docs_json, queued_at, decision, decided_at, decided_by)
SELECT term_id, COALESCE(kind, 'new'), draft_json, reasons_json, docs_json, queued_at, decision, decided_at, decided_by
FROM review_queue
WHERE decision IS NOT NULL AND COALESCE(decided_by, '') != 'gate' AND queued_at IS NOT NULL AND decided_at IS NOT NULL
ON CONFLICT DO NOTHING;
