# AI Builder Cup 2026

[한국어](README.md) | English | [팀원용 처음 설치 가이드](docs/setup.md)

A theme-independent foundation for a four-person team with one developer.
React + TypeScript, FastAPI, Gemini on Google Cloud, and an optional local Gemma/vLLM service.

Start with the [session handoff and remaining work](docs/session-handoff.md) for the current
project status, operating constraints, and next steps.

## Local development

These steps set up the shared React/FastAPI foundation. Candidate projects under `prototype/`
are independent and are not installed by `make setup`. Cloud deployment remains paused; local
mock development needs no cloud account, billing, API key or GPU.

### 1. Install required tools

Required: Git, Make, uv, Node.js **24.21.0**, and the npm bundled with that Node release.
Python 3.12 is selected by `.python-version`; uv installs it automatically during setup.

On macOS, install [Homebrew](https://brew.sh/) if needed and follow its shell setup instructions,
then install the development tools:

```bash
xcode-select --install  # only if Command Line Tools, including make, are missing
brew install git uv fnm
```

For zsh, add the following line once to `~/.zshrc`, then run it in the current terminal too:

```bash
eval "$(fnm env --use-on-cd --shell zsh)"
```

From the repository root, select the pinned Node version:

```bash
git switch develop
fnm install
fnm use
node --version  # expected v24.21.0
npm --version
uv --version
make --version
```

`fnm install` and `fnm use` read `.nvmrc`. If you already use nvm, use `nvm install` and
`nvm use` instead; a second version manager is unnecessary. See the official
[fnm setup](https://github.com/Schniz/fnm#shell-setup) and
[uv installation](https://docs.astral.sh/uv/getting-started/installation/) instructions for other systems.

Make uses Node from the active shell's `PATH`; it does not force a Homebrew Node installation.
The clone can live anywhere. Matching home-directory paths across Macs do not transfer installed
tools, `.env`, dependencies or credentials.

### 2. Set up the project

```bash
make setup
```

This checks the Node version, installs Python dependencies from `uv.lock` into `.venv`, installs
web dependencies from `apps/web/package-lock.json`, and creates `.env` from `.env.example` only
when `.env` is absent. An existing `.env` is preserved. No global Python installation or manual
virtual-environment activation is needed.

The generated `.env` selects the deterministic **mock** provider. Keep `MODEL_PROVIDER=mock`
for local setup verification. Credentials, dependency directories and generated artifacts stay
outside Git.

### 3. Verify

```bash
make check test build eval
(cd apps/web && npx playwright install chromium)
make e2e
```

The checks cover Python lint/format/types, frontend types, API tests, the frontend build, mock
contract evaluation, and browser flows. Leave port 8000 free for E2E; Playwright starts and stops
its own mock API server. Run these checks before starting the development servers.

Evaluation fixtures in `evaluation-cases/` check the output contract and basic term retention,
**not** factual correctness or domain quality. `make eval` always uses mock, even if `.env`
selects a live provider. Generated results go to ignored `artifacts/evaluation.json`.

Optional checks require additional tools:

| Tool | When needed | Check |
| --- | --- | --- |
| Docker Desktop with its engine running | Container build and local container execution | `docker info`, then `make docker` |
| Terraform >=1.6 and <2.0 (CI uses 1.16.3) | Infrastructure validation | `make infra-check` |
| GitHub CLI (`gh`) | CLI access to PRs, Actions and repository settings | `gh auth status` |
| Google Cloud CLI (`gcloud`) | Future real Gemini access and deployment | See [operations](docs/operations.md) |

`make infra-check` downloads the locked provider and validates locally without applying resources.
Docker and cloud CLIs are not required for the mock application checks above.

### 4. Run

Run each command from the repository root in a separate terminal with Node 24.21.0 selected:

```bash
make api       # terminal 1: http://127.0.0.1:8000
make web       # terminal 2: http://127.0.0.1:5173
```

Open port 5173 for frontend development; Vite proxies `/api` to port 8000. Stop each server with
Ctrl-C. After changing `.env`, restart the API.

For a single process serving the built UI, run `make build`, then `make api` and open port 8000.
For a container, run `make docker` and open http://127.0.0.1:8080. The container demonstration
intentionally uses mock, not host credentials.

## Real Gemini

Resume this only when real-model access is requested; it is not part of local setup.

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
For a real-model smoke evaluation, use `MODEL_PROVIDER=gemini make eval-live` (may incur API charges).

## Repository layout

```text
apps/web/                    React application, browser tests
apps/api/src/builder_cup/     API, validation, workflow, model adapters
models/vllm/                 GPU-host Gemma service, separate dependencies
infra/gcp/                   Terraform infrastructure foundation
.github/workflows/           CI and release/gcp deployment
scripts/                     Bootstrap, deployment, rollback, evaluation
tests/                       API and failure-mode tests
evaluation-cases/            Team-owned evaluation fixtures
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
