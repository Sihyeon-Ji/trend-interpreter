#!/bin/bash
# Runs once on a temporary builder VM (no GPU) started by scripts/build-gpu-image.sh. It prepares the boot disk
# that becomes the GPU image: Docker with the NVIDIA runtime, the digest-pinned Ollama and gateway images, and
# /opt/trend-gateway with the locked gateway package. It also stages the model files in the release prefix and
# records the Ollama manifest digest that `ollama create` produces for them. The VM powers off when done.
set -euo pipefail
export PATH="$PATH:/snap/bin"
# Access is scoped to object prefixes, so avoid bucket-level checks (listing, composite uploads).
export CLOUDSDK_STORAGE_PARALLEL_COMPOSITE_UPLOAD_ENABLED=False

attribute() {
  curl -sf -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"
}
bucket=$(attribute trend-bucket)
input=$(attribute trend-input-prefix)
release_prefix=$(attribute trend-release-prefix)
ollama_image=$(attribute trend-ollama-image)
gateway_image=$(attribute trend-gateway-image)
model_blob=$(attribute trend-model-blob)
model=$(attribute trend-model)
wheel=$(attribute trend-wheel)
work=/var/tmp/trend-build
step=start

finish() {
  status=$?
  result=$(python3 - "$status" "$step" <<'PY'
import json, os, sys
status, step = sys.argv[1:]
data = {"status": "ok" if status == "0" else "failed", "step": step}
path = "/var/tmp/trend-build/result.json"
if status == "0" and os.path.exists(path):
    data.update(json.load(open(path)))
print(json.dumps(data, sort_keys=True))
PY
)
  printf '%s\n' "$result" | gcloud storage cp - "gs://$bucket/${input}result.json" || true
  docker rm -f trend-builder-ollama >/dev/null 2>&1 || true
  rm -rf "$work" /root/.docker /root/.config/gcloud
  apt-get clean
  journalctl --vacuum-time=1s >/dev/null 2>&1 || true
  shutdown -h now
}
trap finish EXIT
mkdir -p "$work"

step=packages
export DEBIAN_FRONTEND=noninteractive
command -v gcloud >/dev/null || snap install google-cloud-cli --classic
apt-get update -q
apt-get install -y -q docker.io python3.12-venv curl gnupg
if ! command -v nvidia-ctk >/dev/null; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |
    gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' \
      >/etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -q
  apt-get install -y -q nvidia-container-toolkit
fi
nvidia-ctk runtime configure --runtime=docker >/dev/null
systemctl enable docker
systemctl restart docker

step=images
docker pull -q "$ollama_image"
gcloud auth print-access-token | docker login -u oauth2accesstoken --password-stdin "${gateway_image%%/*}" >/dev/null
docker pull -q "$gateway_image"
docker logout "${gateway_image%%/*}" >/dev/null

step=gateway-package
for name in requirements.txt "$wheel"; do
  gcloud storage cp "gs://$bucket/$input$name" "$work/$name"
done
python3.12 -m venv /opt/trend-gateway
/opt/trend-gateway/bin/pip install -q --no-cache-dir --require-hashes --no-deps -r "$work/requirements.txt"
/opt/trend-gateway/bin/pip install -q --no-cache-dir --no-deps "$work/$wheel"
/opt/trend-gateway/bin/python -c 'import model_gateway.install, model_gateway.app'

step=model
mkdir -p "$work/models" "$work/ollama"
curl -fsSL "https://registry.ollama.ai/v2/library/${model_blob%@*}/blobs/${model_blob#*@}" -o "$work/models/model.gguf"
echo "${model_blob#*@sha256:}  $work/models/model.gguf" | sha256sum -c --quiet
gcloud storage cp "gs://$bucket/${input}Modelfile" "$work/models/Modelfile"
for name in model.gguf Modelfile; do
  gcloud storage cp "$work/models/$name" "gs://$bucket/$release_prefix$name"
done

step=model-digest
docker run -d --name trend-builder-ollama --network=host -e OLLAMA_HOST=127.0.0.1:11434 \
  --mount "type=bind,src=$work/models,dst=/models,readonly" \
  --mount "type=bind,src=$work/ollama,dst=/root/.ollama" "$ollama_image" >/dev/null
for attempt in $(seq 1 60); do
  curl -sf http://127.0.0.1:11434/api/version >/dev/null && break
  sleep 1
done
docker exec trend-builder-ollama ollama create "$model" -f /models/Modelfile >/dev/null

step=report
python3 - "$bucket" "$release_prefix" "$model" "$ollama_image" "$gateway_image" <<'PY'
import hashlib, json, subprocess, sys, urllib.request
bucket, prefix, model, ollama_image, gateway_image = sys.argv[1:]
tags = json.load(urllib.request.urlopen("http://127.0.0.1:11434/api/tags"))["models"]
digest = [item["digest"] for item in tags if item["name"] in (model, model + ":latest")]
files = {}
for name in ("model.gguf", "Modelfile"):
    described = json.loads(subprocess.check_output(
        ["gcloud", "storage", "objects", "describe", f"gs://{bucket}/{prefix}{name}", "--format=json"]))
    sha = hashlib.sha256()
    with open(f"/var/tmp/trend-build/models/{name}", "rb") as source:
        while chunk := source.read(1 << 20):
            sha.update(chunk)
    files[name] = {"uri": f"gs://{bucket}/{prefix}{name}", "generation": str(described["generation"]),
                   "sha256": sha.hexdigest(), "size": int(described["size"])}
def output(*args):
    return subprocess.check_output(args, text=True).strip()
json.dump({
    "model": model,
    "model_digest": digest[0] if len(digest) == 1 else None,
    "files": files,
    "ollama_image": ollama_image,
    "gateway_image": gateway_image,
    "docker": output("docker", "version", "--format", "{{.Server.Version}}"),
    "nvidia_container_toolkit": output("nvidia-ctk", "--version").splitlines()[0],
    "nvidia_driver_packages": output("sh", "-c", "dpkg-query -W -f '${Package} ${Version}\\n' 'nvidia-driver-*' 'libnvidia-compute-*' 2>/dev/null | head -3"),
    "python": output("/opt/trend-gateway/bin/python", "--version"),
}, open("/var/tmp/trend-build/result.json", "w"), sort_keys=True)
PY
step=done
