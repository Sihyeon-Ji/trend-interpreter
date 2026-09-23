CREATE TABLE IF NOT EXISTS lab.records (
    id uuid PRIMARY KEY,
    label text NOT NULL CHECK (length(label) BETWEEN 1 AND 100),
    created_at timestamptz NOT NULL DEFAULT now()
);
