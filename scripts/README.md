# Script responsibilities

Team members use Docker Compose from the repository root. These files implement specific
operations; they are not a second task-runner interface.
For copyable everyday commands, see the [Korean command reference](../docs/개발환경/개발-명령어.md).

| File | Caller | Responsibility |
| --- | --- | --- |
| `evaluate.py` | Compose `check` | Run contract cases against the configured provider; Compose forces mock |
| `doctor.py` | Compose `doctor` | Read-only HTTP probes for Mock readiness and optional Ollama inventory; no inference, dependency startup or DB writes |
| `db_lab.py` | Compose `db-init` / `db-check` | Initialize the local lab schema; create/read a synthetic record through the API |
| `migration_lab.py` | Compose `db-migration-check` | Verify ordered migration replay, checksum drift rejection and failed transaction rollback |
| `db_backup.sh` | Compose `db-backup` | Create a restricted custom-format PostgreSQL backup and SHA-256 file |
| `db_restore.sh` | Compose `db-restore` | Restore a verified backup only into a new explicitly named local database |
| `db_recovery.py` | Compose `db-recovery-check` | Compare source/restore fingerprints and application-role permissions |
| `workflow_lab.py` | Compose `workflow-check` | Exercise synthetic documents through graph validation, parallel branches, join and routing |
| `history_lab.py` | Compose `history-check` | Verify successful/failed run metadata and privacy; read an existing run by UUID |
| `failure_lab.py` | Compose `failure-check` | Reproduce bounded Mock failures/recovery and verify persisted node states |
| `ollama_lab.py` | Compose `ollama-check`, explicit local use only | Compare synthetic inputs using Mock/Ollama; save JSON and Markdown evaluation reports, never run real inference in CI |
| `model_eval.py` | Compose `model-eval` | Validate the versioned suite and manual reviews; compare two reports without calling a model |
| `ollama_history_lab.py` | Compose `ollama-history-check`, explicit local use only | Run one synthetic Gemma 4 workflow and link its report ID to metadata-only PostgreSQL history |
| `container-smoke.sh` | CI | Verify a production image's UI, health and mock analysis |
| `alert-relay-smoke.sh` | CI | Verify the production relay image starts and answers health checks |
| `release_scope.py` | `Release GCP` workflow | Classify release changes into shared checks, infrastructure, application and relay |
| `verify_alert_delivery.py` | relay deploy script | Confirm a uniquely identified synthetic alert reached Discord from the new revision |
| `bootstrap-gcp.sh` | Deployment operator, only after deployment resumes | Provision GCP infrastructure and configure GitHub deployment variables |
| `deploy-gcp.sh` | `release/gcp` workflow | Deploy a candidate, verify it and promote traffic |
| `deploy-alert-relay.sh` | alert relay release workflow | Deploy the private Discord relay, verify it and publish a synthetic Pub/Sub smoke notification |
| `rollback-gcp.sh` | Deployment operator | Restore traffic to a known revision |

Use `docker compose run --rm --build check` for evaluation as part of application validation.
Do not add parallel Make/just/task wrappers for these commands. Keep service/task definitions
in `compose.yaml`, frontend tool commands in `apps/web/package.json`, and multi-step operational
implementation here. See [operations](../docs/운영/GCP-운영.md) before running cloud scripts.
