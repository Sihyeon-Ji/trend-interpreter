# Evaluation cases

This directory contains sample inputs and expected response checks. It contains data, not executable
code. `cases.jsonl` has one JSON object per line: `id`, `text`, and `required_terms`.

Run `make eval` for deterministic mock checks with no model API calls. Run
`MODEL_PROVIDER=gemini make eval-live` only when real model access and possible API charges are intended.
The runner is `scripts/evaluate.py`; results are written to ignored `artifacts/evaluation.json`.

Current checks validate the output schema and basic term retention. They do not establish factual
accuracy, usefulness, or domain quality. Replace or expand the cases once the team chooses a theme.
