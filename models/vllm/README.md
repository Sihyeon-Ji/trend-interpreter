# Local Gemma with vLLM

This is an optional inference service, independent of the Python API environment.
The initial profile targets **Linux + one NVIDIA GPU + NVIDIA Container Toolkit**.
Apple Silicon Docker does not provide this NVIDIA runtime; run the service on a GPU host and
connect the Mac through SSH. No GPU machine is provisioned by the GCP foundation.

Starting model: `google/gemma-4-E2B-it`, vLLM `v0.19.1`. This is a configurable starting point,
not a hardware fit guarantee. The upstream recipe describes effective 2B with additional model
parameters and a 24 GB+ GPU deployment. Hardware, driver compatibility, actual memory use,
throughput, and quantized variants must be validated on the target host.

```bash
cd models/vllm
cp .env.example .env
# Accept the Google Gemma license on Hugging Face. Set HF_TOKEN and a private VLLM_API_KEY.
docker compose --env-file .env config --quiet
docker compose --env-file .env up -d
docker compose logs -f vllm
```

Do not print expanded Compose configuration containing credentials. The model port is bound to
GPU-host loopback, not the public network. The model cache persists in a Docker volume.
This profile limits context to 4096, concurrency to two, and disables media inputs for the text-only
application contract. It does not enable automatic tool execution.

From the Mac, if the GPU host is remote:

```bash
ssh -N -L 8001:127.0.0.1:8001 USER@GPU_HOST
```

The default development Compose stack stays on mock and does not load the root `.env`.
After verifying the GPU service, set the private `VLLM_API_KEY` in the host shell through your
secret-handling workflow. On Docker Desktop for Mac, explicitly run a one-off evaluation from
the repository root; `host.docker.internal` reaches the host's forwarded port from the container:

```bash
docker compose run --rm -e MODEL_PROVIDER=vllm \
  -e VLLM_BASE_URL=http://host.docker.internal:8001/v1 \
  -e VLLM_MODEL=google/gemma-4-E2B-it -e VLLM_API_KEY \
  api python scripts/evaluate.py
```

This does not change the running UI/API provider. An interactive live-model UI needs a deliberate
Compose override for provider, connectivity and credentials. Linux hosts need their own host-network
connectivity setup; container `localhost` is not the GPU host or SSH tunnel.
The application uses the OpenAI-compatible chat-completions protocol directly through httpx;
this does not require an OpenAI account. JSON output is constrained server-side and validated again
by the API. If the model/image combination does not support the schema, failure is surfaced.

GPU model, VRAM and driver are still required to choose a final image/quantization profile.
Do not download large weights or claim inference is verified before checking that hardware.

References:
- [Official vLLM Gemma 4 E2B recipe](https://recipes.vllm.ai/Google/gemma-4-E2B-it)
- [Google Gemma model overview](https://ai.google.dev/gemma/docs/core)
