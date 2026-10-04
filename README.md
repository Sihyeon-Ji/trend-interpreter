# AI Builder Cup 2026

English | [한국어](README.kr.md) | [First-time setup guide in Korean](docs/개발환경/처음-설치.md)

**Trend Interpreter**: a cross-generation, cross-culture trend interpretation service for the
AI Builder Cup 2026. The repository holds the Next.js web app, the FastAPI API with its collection
and dictionary pipeline, the Discord alert relay, and the GCP infrastructure.
Other candidate projects under `prototype/` are kept for reference only.

## What it does

Brand marketers and creators ask one question about a meme: can we use it now, here, without trouble?
Trend Interpreter answers it per market (ten Asia-Pacific markets plus a global group) from collected public data.

| Feature | What the user gets |
| --- | --- |
| Trend dashboard | Memes in use now, fading and needing care, with lifecycle stage, risk, 12-week mentions and an at-a-glance summary of what is safe to use |
| Meme dictionary | Versioned meanings with cited sources, regions, per-country variants and history |
| Trend briefing | One-page market report to save as PDF or share, with a summary written only from the listed facts |
| Campaign kit | Meme picks for a product photo or copy, then SNS copy, a short-form script and a thumbnail plan, checked against the dictionary |
| Copy check | Flags memes in your own copy that are risky, fading or foreign to the market, and gives an AI opinion on whether each is used in the right sense |
| Message explain and dictionary chat | Rewrites a pasted message in plain words; a read-only tool-calling chat answers only from the dictionary |
| World map and recent changes | Where a meme is used and what changed lately |
| Reviewer console | Human approval queue for new meanings, corrections and risk decisions |

## How AI is used

Rules decide, models write. Listing, lifecycle, verification status, risk level, list filtering and
recommendation ranking are deterministic code; a model never sets a status.

- **Gemini on Vertex AI** (runtime service account, no API key, monthly spend cap): researches new terms with
  grounding, reads trending short videos, turns a product photo or copy into a product brief, writes campaign
  copy, summarises the briefing and judges whether copy uses a meme in the right sense.
- **Gemma 4** (local or on a GPU VM): drafts dictionary translations, classifies evidence sentences for risk and
  audits dictionary meanings against their sources. The auditor is being fine-tuned with QLoRA on Kaggle and is
  compared with the base model on a sealed human-labelled set before use.
- Every model output is checked by rules before it is shown: a meaning needs a matching reference document,
  generated copy is re-checked for the chosen meme, profanity and length, and empty or note-like meanings are
  held back.

## Google Cloud services

| Service | Use |
| --- | --- |
| Cloud Run | Web app, private API and alert relay; new revisions are tested before traffic moves |
| Cloud SQL for PostgreSQL | Published dictionary, evidence and dashboard data |
| Vertex AI (Gemini) | Request-time research, generation and summaries |
| Compute Engine GPU (L4) | Gemma auditor gateway, started only when needed |
| Cloud Storage | Fixed data snapshots handed from the collection server |
| Cloud Logging, Monitoring, Pub/Sub | Alerts relayed to the team's Discord channel |
| Secret Manager | Runtime secrets |

Collection runs on a separate team server; only verified snapshots are published to Cloud SQL.
Details are in the [architecture document](docs/운영/시스템-아키텍처.md) (Korean).

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
