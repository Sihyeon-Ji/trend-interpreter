#!/usr/bin/env bash
# Keep the Git-ignored Terraform variable files in Secret Manager so another checkout can apply infrastructure.
#
#   save      bundle every ignored *.tfvars.json under infra/gcp into a new version of the secret
#   restore   write the latest bundle back, refusing to overwrite a file that differs
#
# Run save after editing any of those files. The bundle holds pinned image digests, numeric secret versions and an
# alert email address, not credentials.
set -euo pipefail

project_id=${PROJECT_ID:-stunning-crane-508614-c1}
secret=trend-terraform-vars
root=$(cd "$(dirname "$0")/.." && pwd)

case "${1:?usage: terraform-vars.sh save|restore}" in
  save)
    cd "$root"
    files=$(git ls-files --others --ignored --exclude-standard -- 'infra/gcp/*.tfvars.json' 'infra/gcp/hybrid/*.tfvars.json')
    test -n "$files" || { echo "no ignored tfvars files found" >&2; exit 1; }
    if ! gcloud secrets describe "$secret" --project "$project_id" >/dev/null 2>&1; then
      gcloud secrets create "$secret" --project "$project_id" --replication-policy=user-managed \
        --locations=asia-northeast1 >/dev/null
    fi
    printf '%s\n' "$files" | python3 -c '
import json, sys
print(json.dumps({path: open(path).read() for path in sys.stdin.read().split()}, indent=2, sort_keys=True))
' | gcloud secrets versions add "$secret" --project "$project_id" --data-file=- --format='value(name)'
    printf '%s\n' "$files"
    ;;
  restore)
    cd "$root"
    gcloud secrets versions access latest --secret "$secret" --project "$project_id" | python3 -c '
import json, os, sys
for path, text in json.load(sys.stdin).items():
    if not path.startswith("infra/gcp/") or ".." in path:
        sys.exit(f"unexpected path {path}")
    if os.path.exists(path):
        status = "unchanged" if open(path).read() == text else "differs, kept local file"
    else:
        with open(path, "w") as handle:
            handle.write(text)
        status = "restored"
    print(f"{path}: {status}")
'
    ;;
  *)
    echo "usage: terraform-vars.sh save|restore" >&2
    exit 1
    ;;
esac
