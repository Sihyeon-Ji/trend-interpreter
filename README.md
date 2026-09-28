# AI Builder Cup 2026

English | [한국어](README.kr.md) | [First-time setup guide in Korean](docs/개발환경/처음-설치.md)

**Trend Interpreter**: a cross-generation, cross-culture trend interpretation service for the
AI Builder Cup 2026. The repository holds the Next.js web app, the FastAPI API with its collection
and dictionary pipeline, the Discord alert relay, and the GCP infrastructure.
Other candidate projects under `prototype/` are kept for reference only.

## Local development

Install Git and Docker with Compose v2. No host Node, Python, uv, model key or GPU is required
for the default workflow. Docker Desktop must be running.

```bash
git clone --branch develop https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup.git
cd 2026-google-ai-builder-cup
docker compose up -d
```

Open **http://localhost:3000**. Compose builds the development images on the first run, starts
PostgreSQL, the API and then the Next.js dev server. The API is available at http://localhost:8000/docs.
Use `docker compose ps` to check readiness; initial image downloads may take several minutes.

- The web starts in **sample mode** with built-in example data. `DATA_MODE=api docker compose up -d`
  switches it to the local API, which reads the PostgreSQL database in the `postgres_data` volume.
- All relational data lives in PostgreSQL (`DATABASE_URL`). The development database is loopback-only
  with fixed local credentials and no published port.
- Changes in `apps/trend-web/` (app, components, lib, public) reload through Next.js Fast Refresh.
- Changes in `apps/trend-api/src/` restart the API through Uvicorn reload.
- Dependencies stay inside the images, separate from host `.venv` and `node_modules`.
- Node is **24.21.0** with pnpm through Corepack; Python is **3.12** with uv.
- The API runs with `MODEL_PROVIDER=mock` and `MODEL_REQUESTS_ENABLED=false`. It never calls a paid
  model, and the development services do not load the host `.env` or cloud credentials.

Changing dependency manifests, lockfiles, Dockerfiles or Compose settings requires a rebuild:

```bash
docker compose up -d --build
```

The development servers are exposed only on host loopback; this is not a production deployment.

## Everyday commands

Run these from the repository root. Compose is the single entry point; there is no Makefile or
extra task runner to install. See the [Korean command reference](docs/개발환경/개발-명령어.md).

| Command | Purpose |
| --- | --- |
| `docker compose up -d` | Start the API and the web dev server |
| `docker compose ps` | Check service status |
| `docker compose logs -f` | Follow logs; Ctrl-C stops following, not the services |
| `docker compose down` | Stop and remove the development containers; the database volume stays |
| `docker compose up -d --build` | Rebuild after dependency or configuration changes |
| `docker compose run --rm --build check` | API tests, release and relay tests, web lint and production build |
| `docker compose run --rm security-check` | Scan the three service lockfiles with OSV-Scanner |
| `docker compose run --rm --build e2e` | Run Chromium browser tests against the development stack |
| `docker compose run --rm infra-check` | Format-check, initialize and validate Terraform locally |
| `docker compose run --rm --build uv add httpx` | Edit `apps/trend-api` dependencies and lockfile |
| `docker compose run --rm --build pnpm add zod` | Edit `apps/trend-web` dependencies and lockfile |

`check`, `security-check`, `e2e`, `infra-check`, `uv` and `pnpm` are opt-in services; plain `up -d`
starts only `db`, `api` and `web`. `check` starts `db` for the API tests, which isolate themselves in
temporary schemas. E2E starts its dependent development services if necessary. Its first
build also installs Chromium inside the test image.

Passing checks confirm the code contract and the build, **not** AI quality. Real Gemini access,
collector keys and GPU inference are never exercised by the default stack or by CI.

## Dependency changes

Use the Compose `uv` and `pnpm` tools so the manifest and lockfile change together on the host:

```bash
docker compose run --rm --build uv add httpx
docker compose run --rm --build pnpm add zod
```

Package names above are examples. Rebuild with `docker compose up -d --build`, run `check` and
`e2e`, then commit `pyproject.toml` / `uv.lock` or `package.json` / `pnpm-lock.yaml` in the same commit.
Production and development builds reject out-of-date lockfiles.

## Model access

| Setting | Local default | Production intent |
| --- | --- | --- |
| `MODEL_PROVIDER` | `mock` | `vertex` |
| `MODEL_REQUESTS_ENABLED` | `false` | `true` only while the service is meant to spend |
| `GCP_PROJECT_ID`, `GOOGLE_CLOUD_LOCATION` | empty | Vertex AI project and location |
| `GEMINI_DAILY_BUDGET` | `36` | daily call cap recorded in the database |

Gemini clients are created only in `apps/trend-api/src/trend_agents/model_client.py`, through Vertex AI
with the Cloud Run runtime service account. There is no Gemini API key anywhere in the codebase.
Local Gemma runs through Ollama or an OpenAI-compatible server (`LOCAL_LLM_BASE_URL`); see
[Gemma/vLLM](models/vllm/README.md). Collector keys (YouTube, Naver) belong only in
`apps/trend-api/.env`; see `apps/trend-api/.env.example`.

## Repository layout

```text
compose.yaml                 Development services and opt-in validation tools
Dockerfile.dev               Development toolchain and browser-test image
apps/trend-web/              Next.js web app, browser tests, production Dockerfile
apps/trend-api/              FastAPI API, collection and dictionary pipeline on PostgreSQL, production Dockerfile
apps/alert-relay/            Private Cloud Run relay from Pub/Sub alerts to Discord
models/vllm/                 Separate GPU-host Gemma runtime
infra/gcp/                   Terraform infrastructure
.github/workflows/           CI and release/gcp deployment
scripts/                     Release, smoke-test and cloud operation implementation
tests/                       Release routing and recovery tests
prototype/                   Earlier candidate projects, not built or scanned
docs/                        Korean documentation: setup, operations, Trend design records, plans
```

## Release and deployment

Develop on `develop`; pushes there do not start GitHub Actions. Pushing `release/gcp` classifies the
change, runs the full checks once, and deploys the alert relay when it changed.

The **Trend application deployment job is intentionally disabled** until the Cloud SQL PostgreSQL
instance and a private API path are provisioned; see [Plan 05](docs/plans/05-trend-cloud-run-deployment.md). The
previously deployed `builder-cup` Cloud Run service keeps serving until the Trend release replaces it.
Never commit credentials, `.env`, model weights, Terraform state or collected data.

## Team and documentation

- [Documentation index in Korean](docs/README.md)
- [Trend direction, pipeline and research records in Korean](docs/트렌드/방향.md)
- [Current plans in Korean](docs/plans/README.md)
- [First-time setup in Korean](docs/개발환경/처음-설치.md)
- [Architecture](docs/운영/시스템-아키텍처.md)
- [Operations](docs/운영/GCP-운영.md)
- [Team workflow](docs/개발환경/팀-작업-방식.md)

- [Repository](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup)
- [Project board](https://github.com/users/Sihyeon-Ji/projects/1)

External workspace links do not automatically authenticate a clone or connect an MCP integration.
