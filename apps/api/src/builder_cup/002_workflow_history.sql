CREATE TABLE IF NOT EXISTS lab.workflow_runs (
    id uuid PRIMARY KEY,
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    duration_ms bigint CHECK (duration_ms >= 0),
    status text NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    outcome text CHECK (outcome IN ('accepted', 'needs_revision')),
    provider text NOT NULL,
    model text NOT NULL,
    prompt_version text NOT NULL,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    input_tokens bigint CHECK (input_tokens >= 0),
    output_tokens bigint CHECK (output_tokens >= 0),
    error_code text,
    reason_codes jsonb NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS workflow_runs_started_idx
ON lab.workflow_runs (started_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS lab.workflow_nodes (
    run_id uuid NOT NULL REFERENCES lab.workflow_runs (id) ON DELETE CASCADE,
    node text NOT NULL CHECK (node IN ('validate_input', 'extract', 'inspect_document', 'join', 'route')),
    position smallint NOT NULL CHECK (position BETWEEN 0 AND 4),
    status text NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'skipped')),
    started_at timestamptz,
    finished_at timestamptz,
    duration_ms bigint CHECK (duration_ms >= 0),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    input_tokens bigint CHECK (input_tokens >= 0),
    output_tokens bigint CHECK (output_tokens >= 0),
    error_code text,
    PRIMARY KEY (run_id, node)
);
