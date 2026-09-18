# Repository instructions

- Work on `develop`; pushing `release/gcp` triggers a real GCP deployment.
- Keep web, API, model runtime and infrastructure responsibilities separate.
- Use `docker compose run --rm --build check` for application checks, tests, builds and mock contract evaluation; add `docker compose run --rm --build e2e` for user flows.
- Mock evaluation results are not evidence of AI quality. The default development stack always uses mock.
- Validate infrastructure with `terraform fmt -check` and `terraform validate` in `infra/gcp`.
- Commit dependency lockfiles. Keep generated state, credentials, `.env` and model weights out of Git.
- Keep code and submission-facing documentation in English.
- Keep `README.kr.md`, the team onboarding guide `docs/setup.md` and the command reference `docs/commands.md` in Korean.
- No raw user text, generated output or credentials in operational logs.
- A health check does not establish real Gemini access or GPU inference readiness.
- GCP is currently validation-only at the user's request. Do not enable billing, provision resources, or push `release/gcp` until the user resumes cloud deployment.
- Notion access for this project is limited to page `project page` and its descendants. Verify ancestry before changes; linked pages outside that subtree are out of scope. Do not search or modify unrelated workspace content.
