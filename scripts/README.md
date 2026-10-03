# Script responsibilities

Team members use Docker Compose from the repository root. These files implement specific
operations; they are not a second task-runner interface.
For copyable everyday commands, see the [Korean command reference](../docs/개발환경/개발-명령어.md).
Trend pipeline tools live in `apps/trend-api/scripts/` and are documented in
[the pipeline record](../docs/트렌드/파이프라인.md).

| File | Caller | Responsibility |
| --- | --- | --- |
| `snapshot.py` | Data intake operator | Pin source generations, verify SQLite and checksums, publish immutable copies with the manifest last, fetch only published snapshots |
| `verify_dataset.py` | Team researcher | Verify selected DVC payload SHA-256/CRC32C, row counts and training/evaluation term separation |
| `restore-rehearsal.sh` | Data intake operator | Migrate a verified snapshot into a throwaway PostgreSQL, round-trip it through `pg_dump`/`pg_restore` and fail on any schema or content difference |
| `build-gpu-image.sh` | GPU release operator | Build the prepared GPU boot image and stage one model release with a temporary, prefix-scoped builder VM |
| `verify-gpu-gateway.sh` | GPU release operator | Check an installed gateway from inside its VM over IAP SSH: TLS, credential rejection, readiness, timed inference and GPU memory |
| `probe-gpu-from-cloud-run.sh` | GPU release operator | Run `probe_gpu_gateway.py` once as a temporary Cloud Run job with the API image, identity and VPC egress, then delete the job and its temporary grant |
| `load-cloud-sql.sh` | Data intake operator | Load a verified snapshot into an empty Cloud SQL database through a pinned Cloud SQL Auth Proxy, reading the connection string from Secret Manager |
| `restore_rehearsal.py` | `restore-rehearsal.sh` | Snapshot hash check, user-data-free migration with per-table counts, and schema/content fingerprints of two databases |
| `container-smoke.sh` | CI | Start a throwaway PostgreSQL, the production API and web images, verify API health and the web landing page |
| `alert-relay-smoke.sh` | CI | Verify the production relay image starts and answers health checks |
| `release_scope.py` | `Release GCP` workflow | Classify release changes into shared checks, infrastructure, application and relay |
| `verify_alert_delivery.py` | relay deploy script | Confirm a uniquely identified synthetic alert reached Discord from the new revision |
| `release_summary.py` | release deploy scripts | Record verified image, revision and numbered secret metadata in the Actions summary |
| `release_recovery.py` | `rollback-gcp.sh` | Check a known revision and verify health before and after an explicit traffic switch |
| `bootstrap-gcp.sh` | Deployment operator | Provision GCP infrastructure and configure GitHub deployment variables |
| `deploy-alert-relay.sh` | alert relay release workflow | Deploy the private Discord relay, verify it and publish a synthetic Pub/Sub smoke notification |
| `rollback-gcp.sh` | Deployment operator | Check or restore main/relay traffic to a known revision |

The Trend application deploy script does not exist yet; the release workflow's application job is
disabled until [Plan 05](../docs/plans/05-trend-cloud-run-deployment.md) is implemented.
Do not add parallel Make/just/task wrappers for these commands. Keep service/task definitions
in `compose.yaml`, frontend tool commands in `apps/trend-web/package.json`, and multi-step operational
implementation here. See [operations](../docs/운영/GCP-운영.md) before running cloud scripts.

The root `pyproject.toml` and `uv.lock` isolate DVC, Kaggle and snapshot dependencies from the API runtime.
Use `docker compose run --rm data-tools` for these tools. Data and model payloads are ignored by Git;
only manifests and `.dvc` metadata belong in the repository. The research remote requires ADC and
approved path permissions. Cloud writes and resource provisioning follow the repository's approval
rules. See [snapshot and DVC operations](../docs/개발환경/데이터-스냅숏-DVC.md).
