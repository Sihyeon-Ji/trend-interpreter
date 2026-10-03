# Private model gateway

A single-owner, authenticated Ollama gateway with bounded inference and GPU readiness checks.
It accepts a fixed model and digest, keeps Ollama on loopback, and does not expose model management.
The runtime image requires TLS files and a shared host lock directory. There is no default model or secret.

Run `docker compose run --rm --build gateway-check` from the repository root.
See [runtime and infrastructure setup](../../docs/개발환경/GPU-gateway-인프라-기반.md) for deployment requirements and unverified scope.
