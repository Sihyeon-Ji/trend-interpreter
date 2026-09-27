-- 사전 지식 그래프. 노드 = 일반 테이블, 엣지 = 소스 노드에 INTERLEAVE 된 테이블, 그 위에 PROPERTY GRAPH.
CREATE TABLE Term (
  term_id STRING(64) NOT NULL,
  canonical STRING(MAX) NOT NULL,
  lang STRING(8),
  status STRING(32),
  lifecycle STRING(32),
  first_seen TIMESTAMP,
  last_seen TIMESTAMP,
  embedding ARRAY<FLOAT32>(vector_length=>768)
) PRIMARY KEY (term_id);

CREATE TABLE Meaning (
  meaning_id STRING(64) NOT NULL,
  term_id STRING(64) NOT NULL,
  version INT64 NOT NULL,
  definition STRING(MAX),
  expansion STRING(MAX),
  origin STRING(MAX),
  nuance STRING(MAX),
  is_expression BOOL,
  confidence FLOAT64,
  verification STRING(32),
  valid_from TIMESTAMP,
  valid_to TIMESTAMP,
  created_by STRING(64),
  citations ARRAY<STRING(MAX)>
) PRIMARY KEY (meaning_id);

CREATE TABLE Evidence (
  evidence_id STRING(64) NOT NULL,
  kind STRING(32),
  url STRING(MAX),
  title STRING(MAX),
  source_domain STRING(MAX),
  observed_at TIMESTAMP,
  excerpt STRING(MAX)
) PRIMARY KEY (evidence_id);

CREATE TABLE Segment (
  segment_id STRING(64) NOT NULL,
  generation STRING(16),
  region STRING(8)
) PRIMARY KEY (segment_id);

CREATE TABLE TermHasMeaning (
  term_id STRING(64) NOT NULL,
  meaning_id STRING(64) NOT NULL,
  FOREIGN KEY (meaning_id) REFERENCES Meaning (meaning_id)
) PRIMARY KEY (term_id, meaning_id), INTERLEAVE IN PARENT Term ON DELETE CASCADE;

CREATE TABLE MeaningSupportedBy (
  meaning_id STRING(64) NOT NULL,
  evidence_id STRING(64) NOT NULL,
  weight FLOAT64,
  FOREIGN KEY (evidence_id) REFERENCES Evidence (evidence_id)
) PRIMARY KEY (meaning_id, evidence_id), INTERLEAVE IN PARENT Meaning ON DELETE CASCADE;

CREATE TABLE TermVariantOf (
  term_id STRING(64) NOT NULL,
  canonical_term_id STRING(64) NOT NULL,
  FOREIGN KEY (canonical_term_id) REFERENCES Term (term_id)
) PRIMARY KEY (term_id, canonical_term_id), INTERLEAVE IN PARENT Term ON DELETE CASCADE;

CREATE TABLE TermUsedBy (
  term_id STRING(64) NOT NULL,
  segment_id STRING(64) NOT NULL,
  first_seen TIMESTAMP,
  share FLOAT64,
  FOREIGN KEY (segment_id) REFERENCES Segment (segment_id)
) PRIMARY KEY (term_id, segment_id), INTERLEAVE IN PARENT Term ON DELETE CASCADE;

CREATE PROPERTY GRAPH TrendGraph
  NODE TABLES (Term, Meaning, Evidence, Segment)
  EDGE TABLES (
    TermHasMeaning
      SOURCE KEY (term_id) REFERENCES Term (term_id)
      DESTINATION KEY (meaning_id) REFERENCES Meaning (meaning_id)
      LABEL HAS_MEANING,
    MeaningSupportedBy
      SOURCE KEY (meaning_id) REFERENCES Meaning (meaning_id)
      DESTINATION KEY (evidence_id) REFERENCES Evidence (evidence_id)
      LABEL SUPPORTED_BY,
    TermVariantOf
      SOURCE KEY (term_id) REFERENCES Term (term_id)
      DESTINATION KEY (canonical_term_id) REFERENCES Term (term_id)
      LABEL VARIANT_OF,
    TermUsedBy
      SOURCE KEY (term_id) REFERENCES Term (term_id)
      DESTINATION KEY (segment_id) REFERENCES Segment (segment_id)
      LABEL USED_BY
  );
