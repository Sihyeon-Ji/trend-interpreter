# Session handoff — 2026-09-18

## Goal and decisions

Prepare a reusable development foundation before selecting the AI Builder Cup theme. The team has
four members and one developer, who also owns infrastructure. Use one repository with separate web,
API, model-runtime and infrastructure directories. Keep operations small enough for one person.

- Repository: [Sihyeon-Ji/2026-google-ai-builder-cup](https://github.com/Sihyeon-Ji/2026-google-ai-builder-cup).
- Development and default branch: `develop`. Pushes run CI.
- Future deployment branch: `release/gcp`. Pushes trigger CI, image build and GCP deployment.
- GCP project: `stunning-crane-508614-c1` (number `266542883304`).
- **Current preference: validation only. Do not enable billing, provision cloud resources, or push
  `release/gcp` until the user explicitly resumes cloud deployment.**
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

## Prepared but not verified live

| Area | Current state | Next step |
| --- | --- | --- |
| GCP infrastructure | Terraform and bootstrap script prepared; no cloud resources applied. Project billing is disabled; the visible billing account was closed. | Keep validating locally. Resume provisioning only when the user wants cloud deployment. |
| Release deployment | Workflow and local `release/gcp` branch prepared; release branch has not been pushed remotely. | After infrastructure exists, fast-forward the branch from `develop`, push it, and watch deployment. |
| Real Gemini | Adapter tested with mocked HTTP responses, not an actual model request. | Once billing/API/model access and quota are ready, run a real evaluation and a deployed UI request. |
| Local Gemma/vLLM | Separate Linux/NVIDIA Compose profile and connection guide prepared. | Obtain GPU model, VRAM and driver details; validate model/image compatibility and run inference. |
| GitHub and Notion plugins | Installed, but latest MCP calls returned `USER_NOT_LOGGED_IN`. CLI authentication does not authenticate the GitHub plugin. | Complete OAuth in each installed plugin, then verify reads of the specified repository/page only. |
| Budget and alerts | Optional Terraform budget and monitoring dashboard definitions exist, not deployed. | Choose budget/currency/recipients when deployment resumes; budget alerts do not stop spending. |
| Theme and evaluation quality | Theme remains undecided; current evaluation is a contract smoke check. | Collect user scenarios, representative data and domain-specific success/failure cases. |

Tokens were pasted in the conversation. They were not copied into this repository or MCP configuration.
Their revocation/replacement has not been verified. Do not reproduce them in documentation or logs.

## Continue development without GCP billing

Follow the maintained [local development guide](../README.en.md#local-development) in order:
install required tools, run `make setup`, verify, then start the API and web servers.
Node is pinned to **24.21.0** in `.nvmrc`, read by CI, and matched by the Docker images and app
engine declarations. Make uses the active shell's Node rather than a machine-specific Homebrew path.

The earlier Docker account-path repair above is historical, not a prerequisite for another Mac.
Even when both Macs use the same `/Users/sean` home path, install tools and recreate ignored local
environments independently. Previous CLI authentication and validation results describe the earlier
session, not the state of every clone.

`evaluation-cases/` contains JSON test data, not executable code. `make eval` always uses mock.
`make eval-live` uses the configured provider and can incur API charges. Results under `artifacts/`
are ignored by Git and may contain generated output; use synthetic data for shared examples.

## Resume cloud deployment later

1. Obtain the user's instruction to resume. Decide the region and budget before creating resources.
   Seoul (`asia-northeast3`) remains in the code. Tokyo (`asia-northeast1`) is a lower-tier Cloud Run
   pricing candidate; it has **not** been selected or applied. See [operations](operations.md).
2. Connect an active billing account and confirm permissions/API/model availability. Do not commit
   credentials, Terraform state or secret values.
3. Run `make infra-apply`. This provisions infrastructure and configures GitHub deployment variables.
   The old `make infra-init` command now stops with guidance rather than applying resources.
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
