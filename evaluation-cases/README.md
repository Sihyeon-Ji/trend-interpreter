# Evaluation cases

This directory contains sample inputs and expected response checks. It contains data, not executable
code. `cases.jsonl` has one JSON object per line: `id`, `text`, and `required_terms`.

Run `docker compose run --rm --build check` for deterministic mock checks with no model API calls.
The runner is `scripts/evaluate.py`; results are written to `artifacts/evaluation.json` inside the
validation container and removed with that container. Omit `--rm` and use `docker cp` if results
must be retained locally. Generated results belong in ignored `artifacts/`, never in Git.
Real-model evaluation requires explicit provider and credential configuration; do not treat mock
results as live verification. GCP billing and deployment remain paused.

Current checks validate the output schema and basic term retention. They do not establish factual
accuracy, usefulness, or domain quality. Replace or expand the cases once the team chooses a theme.
