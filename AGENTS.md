# Repository instructions

- Work on `develop`; pushing `release/gcp` triggers a real GCP deployment.
- Keep web, API, model runtime and infrastructure responsibilities separate.
- Use `docker compose run --rm --build check` for application checks, tests, builds and mock contract evaluation; add `docker compose run --rm --build e2e` for user flows.
- Mock evaluation results are not evidence of AI quality. The default development stack always uses mock.
- Validate infrastructure with `terraform fmt -check` and `terraform validate` in `infra/gcp`.
- Commit dependency lockfiles. Keep generated state, credentials, `.env` and model weights out of Git.
- Keep code and root-level submission-facing documentation such as `README.md` in English.
- Keep `README.kr.md` and all documentation under `docs/` in Korean. Preserve commands, identifiers and product names where translating them would reduce accuracy.
- No raw user text, generated output or credentials in operational logs.
- A health check does not establish real Gemini access or GPU inference readiness.
- GCP billing is linked and deployment resumed on 2026-09-21. Deploy through `release/gcp` only after checks pass, and verify the resulting service before reporting success.
- Notion access for this project is limited to page `project page` and its descendants. Verify ancestry before changes; linked pages outside that subtree are out of scope. Do not search or modify unrelated workspace content.
