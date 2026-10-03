"""Runs inside the trend-api image as a temporary Cloud Run job; see probe-gpu-from-cloud-run.sh.

It goes through the same code path as the audit pipeline (local_chat with the gateway configured) using a
synthetic public entry, and checks that the gateway rejects calls without the right token from the API subnet.
It prints one JSON line with statuses, timings and schema results only, never prompts or model output.
"""
import json
import ssl
import time

import httpx

from trend_agents import config
from trend_agents.interpreters import local_chat
from trend_agents.pipeline.audit import PROMPT, AuditCheck

ATTEMPTS = 3
DOCS = (
    "1. [Wikipedia] Touch grass\n"
    "Touch grass is an internet slang phrase used to tell someone that they spend too much time "
    "online and should go outside. It became common on social media around 2020."
)
prompt = PROMPT.format(
    term="touch grass",
    definition="A phrase telling someone to go outside and take a break from the internet.",
    origin="Internet slang that spread on social media around 2020.",
    nuance="Mildly mocking; implies the person is too absorbed in online arguments.",
    docs=DOCS,
)


def timed(call):
    start = time.monotonic()
    try:
        result = {"ok": True, "value": call()}
    except Exception as error:  # noqa: BLE001 – Report the failure type only.
        result = {"ok": False, "error": type(error).__name__}
    result["seconds"] = round(time.monotonic() - start, 2)
    return result


def audit_check():
    checked = local_chat.structured(prompt, AuditCheck, temperature=0.1, model=config.AUDIT_MODEL)
    return {"schema_valid": isinstance(checked, AuditCheck)}


report = {
    "ready": timed(lambda: local_chat.available(config.AUDIT_MODEL)),
    "other_model_available": local_chat.available("other:model"),
    "audit_checks": [timed(audit_check) for _ in range(ATTEMPTS)],
}
context = ssl.create_default_context(cafile=config.GPU_GATEWAY_CA_FILE)
with httpx.Client(verify=context, trust_env=False, follow_redirects=False, timeout=10) as client:
    report["ready_without_token"] = client.get(config.GPU_GATEWAY_URL + "/ready").status_code
    report["generate_wrong_token"] = client.post(
        config.GPU_GATEWAY_URL + "/v1/generate",
        json={"prompt": "synthetic"},
        headers={"authorization": "Bearer " + "x" * 48},
    ).status_code
print(json.dumps({"gpu_gateway_probe": report}, sort_keys=True))
