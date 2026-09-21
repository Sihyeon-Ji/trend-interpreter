# Session handoff — 2026-09-18

## Goal and decisions

Prepare a reusable development foundation before selecting the AI Builder Cup theme. The team has
four members and one developer, who also owns infrastructure. Use one repository with separate web,
API, model-runtime and infrastructure directories. Keep operations small enough for one person.

- Repository: [Sihyeon-Ji/2026-google-ai-builder-cup](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup).
- Development and default branch: `develop`. Pushes do not run CI automatically.
- Deployment branch: `release/gcp`. Pushes trigger CI, image build and GCP deployment.
- GCP project: `stunning-crane-508614-c1` (number `266542883304`).
- Billing was linked and cloud deployment resumed on 2026-09-21. The deployment target is Tokyo
  (`asia-northeast1`) for Cloud Run Tier 1 pricing and direct custom-domain mapping support.
- Notion work is restricted to [the contest page](https://www.notion.so/)
  and its descendants. Linked pages outside that subtree are not in scope.

## How the work progressed

| Stage | Result |
| --- | --- |
| Scope review | Chose React/Vite, FastAPI, Gemini, Docker, Cloud Run, GitHub Actions and basic observability. Deferred databases, queues, Kubernetes and a full monitoring stack until requirements justify them. |
| Initial foundation (`41b306e`) | Created the application, model adapters, tests, container, Terraform, CI/CD and operations documentation. |
| CI maintenance (`63b59fa`) | Updated GitHub Actions and pinned them to official release commit SHAs. |
| Validation-only workflow (`2167858`) | Made plain `make` show help, forced `make eval` to mock, separated `eval-live` and `infra-apply`, added a billing preflight, and recorded Notion/GCP restrictions. |
| This handoff | Renamed the sample directory to `evaluation-cases`, updated its runner and documentation, and recorded remaining work. |
| First cloud release (`07ef775`) | Applied the Tokyo foundation, fixed first-service deployment handling, deployed Cloud Run and verified a real Gemini request. |

## Completed and verified

- React + TypeScript playground and FastAPI endpoint, served together in a release container.
- Mock, Gemini/Vertex AI and OpenAI-compatible vLLM adapters. No CUDA/vLLM dependency in the API.
- Input/output validation, bounded retries and timeouts, request IDs, structured logs and usage metadata.
- Shared team access-code gate for deployed model requests; credentials are not bundled into the UI.
- Seven Python tests, two browser tests, mock evaluation, frontend build and Terraform validation passed.
- Docker builds and container smoke checks passed locally, including the GCP-targeted `linux/amd64` image.
- Desktop/mobile UI was inspected. GitHub CI passed through commit `2167858`; later results are available
  in [Actions](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions).
- GitHub CLI access and `develop` pushes work. The GitHub Project board is accessible through the CLI.
- GCP CLI login, ADC refresh, project Owner role, active API inventory and local Terraform validation
  were verified. ADC now has this project configured as its quota project; that does not enable billing.
- Docker Desktop originally referenced the old `/Users/sihyeon` disk path after the Mac account was
  renamed to `sean`. The existing disk was found under the current home directory, and the engine later
  started successfully. Container checks confirmed it was operational.
- Terraform applied 25 foundation resources in Tokyo. GitHub Workload Identity authentication and the
  release workflow succeeded without a stored service-account key.
- Cloud Run revision `builder-cup-00003-nec` serves 100% of traffic at
  `https://builder-cup-7jftqxfz3q-an.a.run.app`. Static UI, health, anonymous rejection and authenticated
  `gemini-3.5-flash` inference all passed. The real call returned HTTP 200 with token usage metadata.
  The release-only workflow also passed on [run 35587198212](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup/actions/runs/35587198212).

## Remaining work

| Area | Current state | Next step |
| --- | --- | --- |
| Local Gemma/vLLM | Separate Linux/NVIDIA Compose profile and connection guide prepared. | Obtain GPU model, VRAM and driver details; validate model/image compatibility and run inference. |
| GitHub and Notion plugins | Installed, but latest MCP calls returned `USER_NOT_LOGGED_IN`. CLI authentication does not authenticate the GitHub plugin. | Complete OAuth in each installed plugin, then verify reads of the specified repository/page only. |
| Budget and alerts | Monitoring dashboard is deployed. An optional Terraform billing budget is not configured. | Choose a KRW budget and recipients; budget alerts do not stop spending. |
| Theme and evaluation quality | Theme remains undecided; current evaluation is a contract smoke check. | Collect user scenarios, representative data and domain-specific success/failure cases. |

Tokens were pasted in the conversation. They were not copied into this repository or MCP configuration.
Their revocation/replacement has not been verified. Do not reproduce them in documentation or logs.

## Continue local development

The earlier Make-based setup above is historical and has been replaced. Follow the maintained
[local development guide](../README.md#local-development) or [Korean onboarding guide](setup.md).
Install Git and Docker, clone `develop`, then run `docker compose up -d`. The web and API reload
when their mounted source files change. Node 24.21.0 and Python 3.12 are installed in the image;
no host language tools or `.env` are required for the mock stack.

Run `docker compose run --rm --build check` for checks, tests, frontend build and mock contract
verification. Run `docker compose run --rm --build e2e` for browser tests, and
`docker compose run --rm infra-check` for local Terraform validation. No cloud resources are created.
Use `docker compose up -d --build preview` for the production-style mock app on port 8080.
The Makefile was removed; `scripts/` now documents its internal evaluation and operator responsibilities.

The earlier Docker account-path repair is historical, not a prerequisite for another Mac.
Even when both Macs use the same home path, installed tools and credentials are machine-local.
Mock verification does not establish real Gemini access or AI quality.

## Deploy to GCP

1. Confirm the selected region and budget before creating resources. Tokyo (`asia-northeast1`) is
   selected for the Cloud Run application and Artifact Registry. See [operations](operations.md).
2. Confirm the active billing account, permissions, API and model availability. Do not commit
   credentials, Terraform state or secret values.
3. Run `bash scripts/bootstrap-gcp.sh`. This provisions infrastructure and configures GitHub deployment variables.
4. Promote the current code, then return to development:

   ```bash
   git switch release/gcp             # use git switch -c release/gcp develop if absent
   git merge --ff-only develop
   git push -u origin release/gcp
   git switch develop
   ```

5. Watch GitHub Actions. Verify the deployed URL and a real Gemini request using the team code from
   Secret Manager. A health check alone does not validate model access. Use the rollback instructions
   in [operations](operations.md) if needed.

## Where to look next

- [README](../README.md): everyday commands and repository layout.
- [Architecture](architecture.md): ownership boundaries and deferred components.
- [Operations](operations.md): bootstrap, costs, access, logs and rollback.
- [Gemma/vLLM](../models/vllm/README.md): GPU-host setup and SSH tunnel.
- [Team workflow](team-workflow.md): research, acceptance criteria and team roles.
- [GitHub Project](https://github.com/users/Sihyeon-Ji/projects/1): team board.

All source and documentation are intended for `develop`. Local credentials, `.env`, model weights,
dependency caches, screenshots, generated evaluation results and repair tools remain outside Git.
