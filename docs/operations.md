# GCP setup and operations

## One-time bootstrap

Project: `stunning-crane-508614-c1`. Cloud Run/Artifact Registry region: `asia-northeast3` (Seoul).
Gemini location: `global`; this is not a Korea-only data residency promise.

1. Authenticate `gh auth login`, `gcloud auth login`, and `gcloud auth application-default login`.
2. The GitHub account needs repository administration to configure variables and environments.
   The Google account needs project permissions for API enablement, IAM/service accounts,
   federation, secrets, storage, Artifact Registry and monitoring.
3. Install Terraform >=1.6 (the local setup uses `.tools/terraform` 1.16.3).
4. When cloud deployment is desired and billing is enabled, run `make infra-apply`. It prints a Terraform plan before applying the prepared infrastructure.
   It does not change the active gcloud project or account.
5. Set GitHub's default branch to `develop` after pushing it.
6. Push `release/gcp` to run CI and deploy.

The bootstrap can be rerun: it preserves the existing demo secret version and uses remote state.
Before enabling any API or creating resources, it checks that project billing is enabled.
It writes only public repository IDs to ignored `infra/gcp/github.auto.tfvars.json`.
The GitHub environment is named `gcp`; no approval gate is configured, so branch pushes deploy automatically.
For future collaborators, protect release pushes and require successful CI on release PRs.

Required repository variables (bootstrap sets these):

| Variable | Source |
| --- | --- |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Terraform `workload_identity_provider` output |
| `GCP_DEPLOY_SERVICE_ACCOUNT` | Terraform `deploy_service_account` output |
| `GEMINI_MODEL` | Optional, defaults to `gemini-3.5-flash` |

## Team access

Open the Cloud Run service URL. Retrieve `builder-cup-demo-key` from Secret Manager privately and
share it with teammates using an appropriate private channel. Enter it in the UI access-code field.
It stays in React memory and is never baked into the frontend or written to localStorage.

The release smoke test checks static UI, application health and anonymous-call rejection.
It does **not** prove Gemini project access or quota. After the first release, submit a real text
with the team code and inspect the returned model, tokens and result. Also run a real-provider
evaluation locally. A failed candidate smoke test is not promoted; previous traffic stays in place.
On the very first deployment, there is no previous serving revision to preserve.

If the organization disallows `allUsers`, the public-invoker step fails visibly. Use an approved
private access architecture rather than removing authentication. Do not claim the deployment is ready.

## Budget

Current project preference: keep billing disabled and perform validation only. CLI login, ADC
token refresh, project/IAM/API inventory reads, application tests, Docker builds and `make infra-check`
can be verified now. Actual Cloud Run deployment and Vertex AI inference remain unverified until
the user resumes deployment. Authentication alone does not enable billing.

Cloud Run Tokyo (`asia-northeast1`) and Osaka (`asia-northeast2`) use Tier 1 pricing; Seoul
(`asia-northeast3`) uses Tier 2. Tokyo is a cost-oriented candidate for the future CPU application.
The current configuration remains Seoul; no regional migration has been performed. These tiers
are specific to Cloud Run pricing and do not establish the price of Gemini or every GCP service.
Keep regional application dependencies together when selecting the final region.
See [Cloud Run locations](https://docs.cloud.google.com/run/docs/locations) and
[pricing](https://cloud.google.com/run/pricing).

No billing budget is silently assumed. Set `billing_account`, `monthly_budget`, and `budget_currency`
in an ignored `infra/gcp/terraform.tfvars`, matching the billing account's currency; then plan/apply.
This enables 50%, 90% and 100% notifications to the account's default billing recipients.
Budget creation needs billing-account permissions. **Budget alerts do not stop spending.**
Model quota and access, budgets, notification recipients and real-model pricing must be verified
in the actual billing account. Image storage persists even when Cloud Run scales to zero.

## Logs and monitoring

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="builder-cup"' \
  --project=stunning-crane-508614-c1 --limit=30 --format=json
```

Search by `jsonPayload.request_id` to join request/retry/completion records.
The `Builder Cup operations` dashboard shows request rates and application errors.
Existing Cloud Run metrics include latency and instance counts; token usage and estimated cost
are recorded in structured completion logs. Set pricing values deliberately to enable estimates.
No paging/notification channel is created until the team's recipient is known.

## Roll back

```bash
gcloud run revisions list --service=builder-cup --region=asia-northeast3 \
  --project=stunning-crane-508614-c1
bash scripts/rollback-gcp.sh KNOWN_GOOD_REVISION
```

Rollback only moves traffic; the bad image and logs remain available for investigation.
Revert the bad commit on `develop` and promote a fixed commit to `release/gcp` before the next release.
Do not use `--to-latest` for rollback.

## Secret rotation

Add a new Secret Manager version, then trigger a new release so instances reload it.
Deployments currently reference `latest`; rollback to an old revision is not a secret rollback.
Keep old versions until all old instances have drained. Do not paste secret values in issues or CI logs.

## Docker on this Mac

Docker Desktop is installed. Its engine must be running before `make docker` or local image tests.
The initial context pointed to `/Users/sihyeon`; starting Docker Desktop changed it to `/Users/sean`.
If the engine does not start, complete Docker Desktop's local onboarding and check `docker info`.
Do not delete existing Docker data to repair a context.
