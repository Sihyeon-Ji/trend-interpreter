ALTER TABLE lab.workflow_runs ADD COLUMN IF NOT EXISTS scenario text NOT NULL DEFAULT 'normal'
CHECK (scenario IN ('normal', 'timeout', 'invalid_json', 'branch_failure', 'transient_error'));
