-- 리스크(Plan 03): 근거 문장마다 로컬 Gemma 가 붙인 뉘앙스·위험 유형. 수준은 risk 단계의 규칙이 이 표로 정하고 용어 JSON 에 둔다.
-- polarity 가 'offtopic' 이면 글자만 같은 딴 이야기라 판정에서 뺀다.
CREATE TABLE IF NOT EXISTS evidence_labels (evidence_id TEXT, term_id TEXT, polarity TEXT, risk TEXT, model TEXT, labeled_at TEXT,
  PRIMARY KEY(evidence_id, term_id));
