# Repository instructions

- Work on `develop`; pushing `release/gcp` triggers a real GCP deployment.
- Keep web, API, model runtime and infrastructure responsibilities separate.
- The main application is the Trend Interpreter in `apps/trend-api` and `apps/trend-web`; `apps/trend-api/AGENTS.md` holds its domain rules. `prototype/` holds earlier candidates only.
- Use `docker compose run --rm --build check` for application checks, tests and builds; add `docker compose run --rm --build e2e` for user flows.
- Passing checks are not evidence of AI quality. The default development stack never calls a paid model (`MODEL_PROVIDER=mock`, `MODEL_REQUESTS_ENABLED=false`); Gemini clients are created only in `model_client.py` through Vertex AI.
- The Trend application deploy job stays disabled until `docs/plans/05-trend-cloud-run-deployment.md` is implemented; the earlier `builder-cup` Cloud Run service keeps running until then.
- Validate infrastructure with `terraform fmt -check` and `terraform validate` in `infra/gcp`.
- Commit dependency lockfiles. Keep generated state, credentials, `.env` and model weights out of Git.
- Keep code and root-level submission-facing documentation such as `README.md` in English.
- Keep `README.kr.md` and all documentation under `docs/` in Korean. Preserve commands, identifiers and product names where translating them would reduce accuracy.
- No raw user text, generated output or credentials in operational logs.
- A health check does not establish real Gemini access or GPU inference readiness.
- GCP billing is linked and deployment resumed on 2026-09-21. Deploy through `release/gcp` only after checks pass, and verify the resulting service before reporting success.
- Notion access for this project is limited to its project page and descendants. Verify ancestry before changes; linked pages outside that subtree are out of scope. Do not search or modify unrelated workspace content.
