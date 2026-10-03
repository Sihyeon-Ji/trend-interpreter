#!/usr/bin/env bash
# Build the prepared GPU boot image and stage one model release with a temporary builder VM (no GPU).
# The builder has an ephemeral external IP for package and model downloads, no inbound firewall rules and a
# two-hour stop limit. The image, the staged model files and a report remain; the VM and its network are removed.
set -euo pipefail

release_id=${1:?release id, e.g. gemma4-12b-validation-20261003}
gateway_image=${2:?gateway image pinned by digest}
output=${3:?report path}
project=${PROJECT_ID:-stunning-crane-508614-c1}
region=asia-northeast1
zone=${ZONE:-asia-northeast1-a}
bucket=$project-trend-models
model=${MODEL:-trend-audit-base:gemma4-12b}
model_blob=gemma4@sha256:bb722270d54346adc198f213851dbe0207e87c3ecf2a0aff4d92262726215391
ollama_image=ollama/ollama@sha256:292ee7945dfc3d5840a181f3ab86fedb1e66703e02c8af98b50f4da56b7e278c
base_image=projects/ubuntu-os-accelerator-images/global/images/ubuntu-accelerator-2404-amd64-with-nvidia-580-v20260925
builder=trend-image-builder
account=$builder@$project.iam.gserviceaccount.com
input=builder/$release_id/
release_prefix=validation/$release_id/
image=trend-gpu-$release_id
root=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)

gc() { gcloud --project "$project" --quiet "$@"; }
revoke() {
  gc storage buckets remove-iam-policy-binding "gs://$bucket" --member "serviceAccount:$account" \
    --role roles/storage.objectAdmin --all >/dev/null 2>&1 || true
  gc artifacts repositories remove-iam-policy-binding builder-cup --location "$region" \
    --member "serviceAccount:$account" --role roles/artifactregistry.reader >/dev/null 2>&1 || true
}
cleanup() {
  revoke
  gc compute instances delete "$builder" --zone "$zone" >/dev/null 2>&1 || true
  gc compute networks subnets delete "$builder" --region "$region" >/dev/null 2>&1 || true
  gc compute networks delete "$builder" >/dev/null 2>&1 || true
  rm -rf "$work"
}
trap cleanup EXIT

[[ $gateway_image =~ @sha256:[a-f0-9]{64}$ ]] || { echo "pin the gateway image by digest" >&2; exit 1; }
if gc storage ls "gs://$bucket/$release_prefix" >/dev/null 2>&1; then echo "release prefix already exists" >&2; exit 1; fi

# Builder inputs: the locked gateway dependencies with hashes, the gateway wheel and the Modelfile.
(cd "$root/models/serving" &&
  uv export --frozen --no-dev --no-emit-project --format requirements-txt -o "$work/requirements.txt" -q &&
  uv build --wheel -o "$work" -q)
printf 'FROM /models/model.gguf\nRENDERER gemma4\nPARSER gemma4\nPARAMETER temperature 1\nPARAMETER top_k 64\nPARAMETER top_p 0.95\n' >"$work/Modelfile"
wheel=$(basename "$work"/*.whl)
gc storage cp "$work/requirements.txt" "$work/$wheel" "$work/Modelfile" "gs://$bucket/$input"

gc iam service-accounts describe "$account" >/dev/null 2>&1 ||
  gc iam service-accounts create "$builder" --display-name "Trend GPU image builder"
# The builder downloads third-party packages and model files, so its object access and listing are limited to
# this release's two prefixes and revoked when the script exits.
objects="projects/_/buckets/$bucket/objects"
list_prefix="api.getAttribute('storage.googleapis.com/objectListPrefix', '')"
python3 - "$release_id" "resource.name.startsWith('$objects/$input') || resource.name.startsWith('$objects/$release_prefix') || $list_prefix.startsWith('$input') || $list_prefix.startsWith('$release_prefix')" \
  >"$work/condition.json" <<'PY'
import json, sys
print(json.dumps({"title": "builder-" + sys.argv[1], "expression": sys.argv[2]}))
PY
gc storage buckets add-iam-policy-binding "gs://$bucket" --member "serviceAccount:$account" \
  --role roles/storage.objectAdmin --condition-from-file "$work/condition.json" >/dev/null
gc artifacts repositories add-iam-policy-binding builder-cup --location "$region" \
  --member "serviceAccount:$account" --role roles/artifactregistry.reader >/dev/null
gc compute networks create "$builder" --subnet-mode custom >/dev/null
gc compute networks subnets create "$builder" --network "$builder" --region "$region" --range 10.90.0.0/24 >/dev/null

gc compute instances create "$builder" --zone "$zone" --machine-type e2-standard-4 \
  --image "$base_image" --boot-disk-size 40GB --boot-disk-type pd-balanced \
  --subnet "$builder" --service-account "$account" --scopes cloud-platform \
  --provisioning-model STANDARD --max-run-duration 7200s --instance-termination-action STOP \
  --shielded-vtpm --shielded-integrity-monitoring \
  --metadata-from-file startup-script="$root/models/serving/image/builder-startup.sh" \
  --metadata "trend-bucket=$bucket,trend-input-prefix=$input,trend-release-prefix=$release_prefix,trend-ollama-image=$ollama_image,trend-gateway-image=$gateway_image,trend-model-blob=$model_blob,trend-model=$model,trend-wheel=$wheel" >/dev/null

for attempt in $(seq 1 180); do
  status=$(gc compute instances describe "$builder" --zone "$zone" --format 'value(status)')
  [ "$status" = TERMINATED ] && break
  sleep 30
done
gc storage cat "gs://$bucket/${input}result.json" >"$work/result.json"
python3 - "$work/result.json" <<'PY'
import json, sys
result = json.load(open(sys.argv[1]))
if result.get("status") != "ok" or not result.get("model_digest"):
    raise SystemExit(f"builder failed at step {result.get('step')}")
PY

gc compute images create "$image" --source-disk "$builder" --source-disk-zone "$zone" \
  --storage-location "$region" --guest-os-features UEFI_COMPATIBLE,GVNIC,VIRTIO_SCSI_MULTIQUEUE \
  --labels "app=trend,release=$release_id" >/dev/null

python3 - "$work/result.json" "projects/$project/global/images/$image" "$base_image" "$release_id" >"$output" <<'PY'
import json, sys
result_path, image, base_image, release_id = sys.argv[1:]
result = json.load(open(result_path))
result.pop("status"); result.pop("step")
print(json.dumps({"release_id": release_id, "boot_image": image, "base_image": base_image, **result},
                 ensure_ascii=False, indent=2, sort_keys=True))
PY
