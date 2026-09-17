# AI Builder Cup 2026

A theme-independent foundation for a four-person team with one developer.
React + TypeScript, FastAPI, Gemini on Google Cloud, and an optional local Gemma/vLLM service.

## Start locally

Prerequisites: Python 3.12 (managed by uv), uv, Node 22.12+, npm, Git.
On this Mac, Node 22 is installed at `/opt/homebrew/opt/node@22/bin`; `make` includes that path.

```bash
make setup
make api       # terminal 1: http://127.0.0.1:8000
make web       # terminal 2: http://127.0.0.1:5173
```

The default provider is a clearly labeled deterministic **mock**, requiring no account or GPU.
Edit `.env` to change providers, then restart the API.

For a single process serving the built UI: `make build`, then `make api` and open port 8000.
For a container: `make docker`, then open http://127.0.0.1:8080.
The container demonstration intentionally uses mock, not host credentials.

## Real Gemini

```bash
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project stunning-crane-508614-c1
```

Set `MODEL_PROVIDER=gemini` in `.env`. The project must have billing, the Vertex AI API,
model access and quota enabled. Local credentials need Vertex AI permissions.
Cloud Run uses its own runtime service account; no API key or credentials file is embedded in the image.
`GEMINI_MODEL` and `GOOGLE_CLOUD_LOCATION` are configurable.
If access fails, the API reports an error rather than silently returning mock data.

## Verify

```bash
make check test build eval
cd apps/web && npx playwright install chromium && npm run test:e2e
```

Evaluation fixtures in `evals/` check the output contract and basic term retention, **not** factual
correctness or domain quality. `make eval` always uses mock, even if `.env` selects a live provider.
For a real-model smoke evaluation: `MODEL_PROVIDER=gemini make eval-live` (may incur API charges).
Generated results go to ignored `artifacts/evaluation.json`.

## Repository layout

```text
apps/web/                    React application, browser tests
apps/api/src/builder_cup/     API, validation, workflow, model adapters
models/vllm/                 GPU-host Gemma service, separate dependencies
infra/gcp/                   Terraform infrastructure foundation
.github/workflows/           CI and release/gcp deployment
scripts/                     Bootstrap, deployment, rollback, evaluation
tests/                       API and failure-mode tests
evals/                       Team-owned evaluation fixtures
docs/                        Architecture, operations, team workflow
```

## Branches and release

- `develop`: ongoing development; every push runs CI.
- PRs to `develop` and `release/gcp`: CI only, no cloud credentials.
- `release/gcp`: every push runs CI, builds an immutable image, deploys a candidate,
  checks its health and authentication, then promotes it to receive traffic.
- No `main` branch is required. Use `develop` as the GitHub default branch.
- Never merge `develop` into `release/gcp` automatically. Release when the team is ready.

```bash
git switch release/gcp
git merge --ff-only develop
git push origin release/gcp
git switch develop
```

See [GCP setup and operations](docs/operations.md) for the one-time bootstrap.
See [local Gemma](models/vllm/README.md) for GPU requirements and connectivity.
See [architecture](docs/architecture.md) for ownership boundaries and extension points.

Running `make` alone shows help. `make infra-check` validates Terraform locally without creating
cloud resources. `make infra-apply` provisions resources and requires enabled billing; the old
`infra-init` name stops with instructions rather than applying anything.

## Team links


- [Repository](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup)
- [Project board](https://github.com/users/Sihyeon-Ji/projects/1)
- [Google Cloud project](https://console.cloud.google.com/home/dashboard?project=stunning-crane-508614-c1)

These are workspace references, not automatically connected MCP integrations.
