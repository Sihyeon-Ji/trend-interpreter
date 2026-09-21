# AI Builder Cup 2026

English | [한국어](README.kr.md) | [First-time setup guide in Korean](docs/setup.md)

A theme-independent foundation for a four-person team: React + TypeScript, FastAPI,
Gemini on Google Cloud, and an optional separate Gemma/vLLM runtime.
Candidate projects in `prototype/` are independent; the team's final theme is not selected.

## Local development

Install Git and Docker with Compose v2. No host Node, Python, uv, Make, model key or GPU is
required for the default workflow. Docker Desktop must be running.

```bash
git clone --branch develop https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup.git
cd 2026-google-ai-builder-cup
docker compose up -d
```

Open **http://localhost:5173**. Compose builds the development images on the first run and
starts PostgreSQL, initializes the lab schema, then starts the API and Vite web server.
The API is available at http://localhost:8000/docs. `db-init` normally exits with code 0 after initialization.
Use `docker compose ps` to check readiness; initial image downloads may take several minutes.

- Changes in `apps/web/src/` update the open browser through Vite HMR.
- Changes in `apps/api/src/` automatically restart the API through Uvicorn reload.
- Both services use source bind mounts, with polling enabled for Docker Desktop/WSL.
- Dependencies stay inside the images, separate from host `.venv` and `node_modules`.
- Node is **24.21.0**; Python is **3.12**. `Dockerfile.dev` prepares both toolchains.
- The stack explicitly uses **mock** and an empty local access code. No `.env` is needed;
  the development services do not load the host `.env` or cloud credentials.

Changing dependency manifests/lockfiles, Dockerfiles or Python tool configuration requires a rebuild:

```bash
docker compose up -d --build
```

New files inside the mounted source directories are picked up automatically. A new top-level
source or asset directory must also be added to the image and Compose mounts.
This development server is exposed only on host loopback; it is not a production deployment.

## Everyday commands

Run these from the repository root. Compose is the single entry point; there is no Makefile
or extra task runner to install.
See the [Korean command reference](docs/commands.md) for commands by task, expected effects and option meanings.

| Command | Purpose |
| --- | --- |
| `docker compose up -d` | Start the development API and web server |
| `docker compose ps` | Check service status |
| `docker compose logs -f` | Follow logs; Ctrl-C stops following, not the services |
| `docker compose down` | Stop and remove the development containers |
| `docker compose up -d --build` | Rebuild after dependency/configuration changes |
| `docker compose run --rm --build check` | Python lint/format/types/tests, mock evaluation, frontend types and build |
| `docker compose run --rm --build db-check` | Create and read a synthetic PostgreSQL lab record through the API |
| `docker compose run --rm --build workflow-check` | Exercise fan-out, join and deterministic routing with synthetic documents |
| `docker compose run --rm --build history-check` | Verify successful/failed workflow history and metadata privacy |
| `docker compose run --rm --build failure-check` | Reproduce Mock timeout, invalid JSON, branch failure and retry recovery |
| `docker compose run --rm --build ollama-check` | Explicitly compare Mock with an installed Mac Ollama model; save local reports |
| `docker compose run --rm --build e2e` | Run Chromium browser tests against the development stack |
| `docker compose run --rm infra-check` | Format-check, initialize and validate Terraform locally |
| `docker compose up -d --build preview` | Run the production-style mock image on port 8080 |
| `docker compose stop preview` | Stop the production preview |

`check`, `db-check`, `workflow-check`, `history-check`, `failure-check`, `ollama-check`, `e2e`, `npm`, `uv`, `infra-check` and `preview` are opt-in services; plain `up -d` starts
`db`, the one-off `db-init`, `api` and `web`. E2E starts its dependent development services if necessary. Its first build
also installs Chromium and system libraries inside the test image.

Mock evaluation checks the output contract and basic term retention, **not** factual correctness
or AI quality. The validation containers are removed after `--rm`; generated test/evaluation
files inside them are temporary. For diagnosis, omit `--rm`, name the container, and copy its
results before removing it. CI retains browser failure artifacts automatically.

## Dependency changes

Use the Compose `npm` and `uv` tools to edit the checkout's manifests and lockfiles together:

```bash
docker compose run --rm --build npm install zod
docker compose run --rm --build uv add httpx
```

Package names above are examples; add only what the feature needs. These tools do not install host
`node_modules` or `.venv`. Rebuild with `docker compose up -d --build`, run `check` and `e2e`, then
commit both `package.json` / `package-lock.json` or `pyproject.toml` / `uv.lock` in the same commit.
See the [Korean command reference](docs/commands.md) for removal and targeted upgrade commands.
Production and development builds reject out-of-date lockfiles.

## PostgreSQL lab

Run `docker compose run --rm db-check` to insert a synthetic record and read it back by ID.
The output includes a read-only replay command and a browser URL. Use that same ID after restarting
the database to verify persistence. See the [lab plan and recorded results](docs/ai-lab-plan.md).

PostgreSQL 18.6 data and generated administrator/application passwords live in separate named volumes.
Normal `docker compose down` preserves them; deleting volumes removes the corresponding data or credentials.
The database has no published host port. The application role has schema usage, record SELECT/INSERT,
and SELECT/INSERT/UPDATE on workflow history tables;
the administrator credential is mounted only into the DB and initializer. The lab API is disabled by default
and cannot be enabled in Cloud Run or with a non-mock provider. The production preview does not require a DB.

## Workflow lab

The independent workflow lab is available through `docker compose run --rm workflow-check`.
It checks three synthetic meeting notes and prints the mock result, routing decision and node events.
`accepted` means the required document sections are present and nonempty, not that the content is factual.
With both local labs enabled, workflow run and node metadata are persisted in PostgreSQL.
Open **Workflow history** at http://localhost:5173 to run a sample, browse the latest 20 runs and inspect
status, timing, model, reported tokens and safe error codes. Source text and generated output are not stored.
Node snapshots are saved when execution ends; this is not live progress or automatic crash recovery.
Run `docker compose run --rm --build history-check` for API and persistence checks.

Choose **Practice scenario** in Workflow history to simulate a model timeout, invalid JSON, parallel
branch failure or a transient connection error followed by recovery. Expectations are shown before running;
the chosen scenario is stored with each run. `failure-check` verifies all scenarios, including a normal run.
Expected HTTP errors are successful failure exercises, not AI quality results. Simulations are local Mock only.

## Local model comparison

The optional `ollama-check` service calls native Ollama on the Mac host via `host.docker.internal:11434`.
Install Ollama and pull `qwen3.5:4b` first; see the [Korean lab instructions](docs/commands.md#실제-로컬-모델-비교).
It runs the same graph and synthetic inputs with Mock and Ollama, then saves timestamped JSON and readable
Markdown reports under ignored `artifacts/`. Reports include synthetic source/output, model digest, usage and
load/generation timing; they are evaluation artifacts, not operational logs or PostgreSQL history.
The default UI/API remains Mock. Real inference is opt-in and never runs in CI. There is no Mock fallback
on model failure. Schema success is separate from factual quality; the [recorded review](docs/ai-lab-plan.md)
includes observed omissions and unsupported generalizations.

## Production preview

```bash
docker compose up -d --build preview
```

Open **http://localhost:8080**. This uses the original production `Dockerfile`: one container
serves the compiled web app and API. It does not mount source or reload after edits. Re-run the
command to build updated code. Development on 5173 and preview on 8080 can run together.
Use `docker compose --profile preview down` to stop both development and preview services.

## Commands and scripts

- `compose.yaml` defines the commands team members and CI run.
- `apps/web/package.json` contains the native frontend commands used inside those containers.
- `scripts/` contains implementation for evaluation, container smoke checks and cloud operations.
  It is not a second everyday command menu. See [script responsibilities](scripts/README.md).
- Cloud operations remain explicit operator actions, outside the development Compose stack.

## Repository layout

```text
compose.yaml                 Development services and opt-in validation/preview tools
Dockerfile.dev               Development toolchain and browser-test image
Dockerfile                   Production application image
apps/web/                    React application and browser tests
apps/api/src/builder_cup/     API, validation, workflow and model adapters
models/vllm/                 Separate GPU-host Gemma runtime
infra/gcp/                   Terraform infrastructure
.github/workflows/           CI and release/gcp deployment
scripts/                     Evaluation and operational implementation
tests/                       API and failure-mode tests
evaluation-cases/            Team-owned evaluation fixtures
prototype/                   Independent candidate projects
docs/                        Setup, architecture, operations and team workflow
```

## Real Gemini and release

**GCP deployment and billing activation remain paused.** The development stack always uses mock.
A future real-model configuration needs deliberate credential injection, project permissions,
model access, quota and billing; successful mock tests do not establish these.
See [operations](docs/operations.md) and [Gemma/vLLM](models/vllm/README.md).

Develop on `develop`; code/configuration pushes run CI. Markdown-only pushes are skipped.
PRs always run CI, and superseded development/PR runs are canceled. CI can also be started manually. A push to `release/gcp` triggers real image publishing
and deployment. Do not push that branch or run `scripts/bootstrap-gcp.sh` until deployment resumes.
Never commit credentials, `.env`, model weights, Terraform state or generated evaluation data.

## Team and documentation

- [AI lab completion report, capabilities and next steps in Korean](docs/ai-lab-report.md)
- [Theme-independent development preparation plans in Korean](docs/plans/README.md)
- [Local LLM, graph workflow and database guide in Korean](docs/ai-development-guide.md)
- [AI development lab plan and prerequisites in Korean](docs/ai-lab-plan.md)
- [First-time setup in Korean](docs/setup.md)
- [Session history and remaining work](docs/session-handoff.md)
- [Architecture](docs/architecture.md)
- [Operations](docs/operations.md)
- [Team workflow](docs/team-workflow.md)

- [Repository](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup)
- [Project board](https://github.com/users/Sihyeon-Ji/projects/1)

External workspace links do not automatically authenticate a clone or connect an MCP integration.
