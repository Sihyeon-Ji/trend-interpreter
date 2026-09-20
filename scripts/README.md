# Script responsibilities

Team members use Docker Compose from the repository root. These files implement specific
operations; they are not a second task-runner interface.
For copyable everyday commands, see the [Korean command reference](../docs/commands.md).

| File | Caller | Responsibility |
| --- | --- | --- |
| `evaluate.py` | Compose `check` | Run contract cases against the configured provider; Compose forces mock |
| `db_lab.py` | Compose `db-init` / `db-check` | Initialize the local lab schema; create/read a synthetic record through the API |
| `workflow_lab.py` | Compose `workflow-check` | Exercise synthetic documents through graph validation, parallel branches, join and routing |
| `history_lab.py` | Compose `history-check` | Verify successful/failed run metadata and privacy; read an existing run by UUID |
| `failure_lab.py` | Compose `failure-check` | Reproduce bounded Mock failures/recovery and verify persisted node states |
| `container-smoke.sh` | CI | Verify a production image's UI, health and mock analysis |
| `bootstrap-gcp.sh` | Deployment operator, only after deployment resumes | Provision GCP infrastructure and configure GitHub deployment variables |
| `deploy-gcp.sh` | `release/gcp` workflow | Deploy a candidate, verify it and promote traffic |
| `rollback-gcp.sh` | Deployment operator | Restore traffic to a known revision |

Use `docker compose run --rm --build check` for evaluation as part of application validation.
Do not add parallel Make/just/task wrappers for these commands. Keep service/task definitions
in `compose.yaml`, frontend tool commands in `apps/web/package.json`, and multi-step operational
implementation here. See [operations](../docs/operations.md) before running cloud scripts.
