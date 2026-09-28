# Script responsibilities

Team members use Docker Compose from the repository root. These files implement specific
operations; they are not a second task-runner interface.
For copyable everyday commands, see the [Korean command reference](../docs/개발환경/개발-명령어.md).
Trend pipeline tools live in `apps/trend-api/scripts/` and are documented in
[the pipeline record](../docs/트렌드/파이프라인.md).

| File | Caller | Responsibility |
| --- | --- | --- |
| `container-smoke.sh` | CI | Start the production API and web images, verify API health and the web landing page |
| `alert-relay-smoke.sh` | CI | Verify the production relay image starts and answers health checks |
| `release_scope.py` | `Release GCP` workflow | Classify release changes into shared checks, infrastructure, application and relay |
| `verify_alert_delivery.py` | relay deploy script | Confirm a uniquely identified synthetic alert reached Discord from the new revision |
| `release_summary.py` | release deploy scripts | Record verified image, revision and numbered secret metadata in the Actions summary |
| `release_recovery.py` | `rollback-gcp.sh` | Check a known revision and verify health before and after an explicit traffic switch |
| `bootstrap-gcp.sh` | Deployment operator | Provision GCP infrastructure and configure GitHub deployment variables |
| `deploy-alert-relay.sh` | alert relay release workflow | Deploy the private Discord relay, verify it and publish a synthetic Pub/Sub smoke notification |
| `rollback-gcp.sh` | Deployment operator | Check or restore main/relay traffic to a known revision |

The Trend application deploy script does not exist yet; the release workflow's application job is
disabled until [Plan 03](../docs/plans/03-trend-cloud-run-deployment.md) is implemented.
Do not add parallel Make/just/task wrappers for these commands. Keep service/task definitions
in `compose.yaml`, frontend tool commands in `apps/trend-web/package.json`, and multi-step operational
implementation here. See [operations](../docs/운영/GCP-운영.md) before running cloud scripts.
