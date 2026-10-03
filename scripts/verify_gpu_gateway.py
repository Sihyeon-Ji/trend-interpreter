"""Runs on the GPU VM as root; see verify-gpu-gateway.sh."""
import json, ssl, statistics, subprocess, sys, time, urllib.error, urllib.request

address = sys.argv[1]
env = dict(line.split("=", 1) for line in open("/run/trend-gateway/gateway.env").read().splitlines() if "=" in line)
token = env["GATEWAY_TOKEN"]
context = ssl.create_default_context(cafile="/tmp/trend-ca.pem")
base = f"https://{address}:8443"
PROMPT = ("You check a slang dictionary entry. Entry: 'touch grass' means to go outside and take a break from "
          "the internet. Evidence: 'Touch grass is an internet slang telling someone to go outside.' "
          'Answer only with JSON {"verdict": "ok"} or {"verdict": "fix"}.')


def call(path, credential=None, body=None, timeout=180):
    request = urllib.request.Request(base + path, data=json.dumps(body).encode() if body else None,
                                     method="POST" if body else "GET")
    if credential:
        request.add_header("Authorization", "Bearer " + credential)
    if body:
        request.add_header("Content-Type", "application/json")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, context=context, timeout=timeout) as response:
            status, data = response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        status, data = error.code, None
    return status, data, round(time.monotonic() - start, 2)


report = {"install_log": subprocess.run(
    "journalctl -u google-startup-scripts --no-pager | grep -o '{\"installed\".*}' | tail -1",
    shell=True, capture_output=True, text=True).stdout.strip()}
report["health"] = call("/health")[0]
report["ready_without_token"] = call("/ready")[0]
report["ready_wrong_token"] = call("/ready", "x" * 48)[0]
attempts = []
for _ in range(8):
    status, data, seconds = call("/ready", token)
    attempts.append({"status": status, "seconds": seconds})
    if status == 200:
        report["ready_model"] = {"model": data["model"], "model_digest": data["model_digest"]}
        break
    time.sleep(15)
report["ready_attempts"] = attempts
runs = []
for _ in range(3):
    status, data, seconds = call("/v1/generate", token, {"prompt": PROMPT, "max_tokens": 32})
    text = (data or {}).get("text", "")
    runs.append({"status": status, "seconds": seconds,
                 "verdict_parsed": '"ok"' in text or '"fix"' in text, "chars": len(text)})
report["generate"] = runs
report["generate_median_seconds"] = statistics.median(run["seconds"] for run in runs)
report["generate_wrong_token"] = call("/v1/generate", "x" * 48, {"prompt": PROMPT})[0]
report["gpu"] = subprocess.run(
    ["nvidia-smi", "--query-gpu=name,memory.used,memory.total,driver_version", "--format=csv,noheader"],
    capture_output=True, text=True).stdout.strip()
report["containers"] = subprocess.run(["docker", "ps", "--format", "{{.Names}} {{.Status}}"],
                                      capture_output=True, text=True).stdout.strip().splitlines()
print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
