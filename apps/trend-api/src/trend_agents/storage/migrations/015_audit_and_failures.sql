-- 사전 감사 기록과 일괄 등재 실패 목록 (2026-09-30).
CREATE TABLE IF NOT EXISTS audit_log (term_id TEXT, meaning_id TEXT, checked_at TEXT, verdict TEXT, reasons_json TEXT, model TEXT, action TEXT, PRIMARY KEY(term_id, meaning_id));
CREATE TABLE IF NOT EXISTS catalog_failed (source TEXT, title TEXT, reason TEXT, at TEXT, PRIMARY KEY(source, title));
