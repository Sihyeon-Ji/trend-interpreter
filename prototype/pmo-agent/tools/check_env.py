"""Echo PMO environment check — it makes real calls to confirm things actually connect.
Use: python tools/check_env.py          (from prototype/pmo-agent)
Accounts and keys are a person's job; verifying them is this script's."""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # prototype/pmo-agent
OK, NO, WARN = "  OK  ", " MISS ", " WARN "


def load_env():
    p = os.path.join(ROOT, ".env")
    out = {}
    if os.path.exists(p):
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


ENV = {
    **load_env(),
    **{
        k: v
        for k, v in os.environ.items()
        if k.startswith(("GEMINI", "JIRA", "GCP", "KANEO", "SLACK", "WRITE"))
    },
}


def row(s, name, detail=""):
    print(f"[{s}] {name:<32} {detail}")


def have(cmd):
    p = shutil.which(cmd)
    if not p:
        return None
    try:
        return (
            subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=20)
            .stdout.strip()
            .splitlines()[0][:50]
        )
    except Exception:
        return p


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.8)
        return s.connect_ex(("127.0.0.1", port)) == 0


print("=" * 78 + "\nEcho PMO environment check (direct to Gemini)\n" + "=" * 78)

print("\n[runtime]")
for c, need in (
    ("python", True),
    ("node", False),
    ("docker", False),
    ("gcloud", False),
    ("git", False),
):
    v = have(c)
    row(
        OK if v else (NO if need else WARN),
        c,
        v or ("needs installing" if need else "optional (Kaneo / deploy)"),
    )

print("\n[required keys] .env")
for k, hint in (
    ("GEMINI_API_KEY", "SETUP 1-1"),
    ("JIRA_SITE", "SETUP 1-2"),
    ("JIRA_EMAIL", "SETUP 1-2"),
    ("JIRA_API_TOKEN", "SETUP 1-2"),
    ("JIRA_PROJECT_KEY", "e.g. ECHO"),
):
    v = ENV.get(k, "")
    shown = (
        (v[:4] + "…" + v[-3:]) if (v and ("TOKEN" in k or "KEY" in k and "PROJECT" not in k)) else v
    )
    row(OK if v else NO, k, shown or hint)

print("\n[live connection tests]")
key = ENV.get("GEMINI_API_KEY")
if key:
    try:
        u = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        with urllib.request.urlopen(u, timeout=25) as r:
            ms = [m["name"].split("/")[-1] for m in json.load(r).get("models", [])]
        want = ENV.get("GEMINI_MODEL", "gemini-2.5-flash")
        row(
            OK,
            "Gemini key valid",
            f"{len(ms)} models"
            + (f" · {want} available" if any(want in m for m in ms) else f" · ⚠ no {want}"),
        )
        # one function-calling round trip
        body = {
            "contents": [
                {"role": "user", "parts": [{"text": "show me the details of task ECHO-1"}]}
            ],
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "get_task",
                            "description": "read a task",
                            "parameters": {
                                "type": "object",
                                "properties": {"key": {"type": "string"}},
                                "required": ["key"],
                            },
                        }
                    ]
                }
            ],
            "generationConfig": {"temperature": 0},
        }
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{want}:generateContent?key={key}",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.load(r)
        parts = ((j.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        fc = next((p["functionCall"] for p in parts if "functionCall" in p), None)
        row(
            OK if fc else WARN,
            "Gemini function calling",
            f"called: {fc['name']}({fc.get('args')})" if fc else "text only, no function call",
        )
    except Exception as e:
        row(NO, "Gemini check failed", str(e)[:70])
else:
    row(NO, "Gemini check", "no key")

site, email, tok = (
    ENV.get("JIRA_SITE", "").replace("https://", "").rstrip("/"),
    ENV.get("JIRA_EMAIL"),
    ENV.get("JIRA_API_TOKEN"),
)
if site and email and tok:
    try:
        auth = base64.b64encode(f"{email}:{tok}".encode()).decode()
        req = urllib.request.Request(
            f"https://{site}/rest/api/3/myself",
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            me = json.load(r)
        row(OK, "Jira auth", f"{me.get('displayName')} <{me.get('emailAddress')}> @ {site}")
        pk = ENV.get("JIRA_PROJECT_KEY", "ECHO")
        req = urllib.request.Request(
            f"https://{site}/rest/api/3/project/{pk}",
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            p = json.load(r)
        row(OK, "Jira project", f"{p.get('key')} · {p.get('name')} · {p.get('projectTypeKey')}")
    except urllib.error.HTTPError as e:
        row(NO, "Jira auth failed", f"HTTP {e.code} — check the token, email and site")
    except Exception as e:
        row(NO, "Jira connection failed", str(e)[:70])
else:
    row(NO, "Jira check", "JIRA_SITE/EMAIL/API_TOKEN not set")

print("\n[optional services]")
for port, name in ((1337, "Kaneo API"), (5432, "Postgres")):
    row(
        OK if port_open(port) else WARN,
        f"localhost:{port} ({name})",
        "open" if port_open(port) else "not running (stage 2)",
    )

print("\n[safety guards]")
allow = ENV.get("WRITE_ALLOWLIST", "")
row(OK if os.path.exists(os.path.join(ROOT, ".gitignore")) else NO, ".gitignore", "blocks .env")
bad = [d for d in ("cytur.atlassian.net",) if d in (allow + " " + site)]
row(
    NO if bad else OK,
    "sandbox isolation",
    f"live domain detected: {bad}" if bad else f"allowlist: {allow or '(not set)'}",
)

print("\n" + "=" * 78)
print(
    "For each MISS, follow the matching number in SETUP.md. "
    'All OK: run the first loop with python -m pmo_agent.run "...".'
)
