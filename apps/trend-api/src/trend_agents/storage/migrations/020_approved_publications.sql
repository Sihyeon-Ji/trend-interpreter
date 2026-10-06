-- Immutable change batches and the last successfully published snapshot.
CREATE TABLE IF NOT EXISTS change_batches (
  batch_id TEXT PRIMARY KEY, payload_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL,
  snapshot_id TEXT NOT NULL, snapshot_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'approved', 'rejected', 'published', 'conflict', 'failed')),
  reviewed_by TEXT, reviewed_at TEXT, failure_code TEXT
);
CREATE TABLE IF NOT EXISTS change_items (
  batch_id TEXT NOT NULL REFERENCES change_batches(batch_id), term_id TEXT NOT NULL,
  item_sha256 TEXT NOT NULL, expected_meaning_id TEXT, baseline_sha256 TEXT NOT NULL, validation_json TEXT NOT NULL,
  PRIMARY KEY(batch_id, term_id)
);
CREATE TABLE IF NOT EXISTS publications (
  publication_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL UNIQUE REFERENCES change_batches(batch_id),
  payload_sha256 TEXT NOT NULL, published_at TEXT NOT NULL, item_count BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS publication_state (
  singleton BIGINT PRIMARY KEY CHECK (singleton = 1), publication_id TEXT REFERENCES publications(publication_id)
);
