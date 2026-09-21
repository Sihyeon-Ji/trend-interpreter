"""Echo PMO 환경 점검 — 실제 호출까지 해서 '연결되는지'를 확인한다.
사용: python tools/check_env.py          (D:/echo-pmo 에서)
계정·키 발급은 사람이, 검증은 이 스크립트가."""

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


print("=" * 78 + "\nEcho PMO 환경 점검 (Gemini 직결)\n" + "=" * 78)

print("\n[런타임]")
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
        v or ("설치 필요" if need else "선택 (Kaneo/배포 때)"),
    )

print("\n[필수 키] .env")
for k, hint in (
    ("GEMINI_API_KEY", "SETUP 1-1"),
    ("JIRA_SITE", "SETUP 1-2"),
    ("JIRA_EMAIL", "SETUP 1-2"),
    ("JIRA_API_TOKEN", "SETUP 1-2"),
    ("JIRA_PROJECT_KEY", "예: ECHO"),
):
    v = ENV.get(k, "")
    shown = (
        (v[:4] + "…" + v[-3:]) if (v and ("TOKEN" in k or "KEY" in k and "PROJECT" not in k)) else v
    )
    row(OK if v else NO, k, shown or hint)

print("\n[실제 연결 테스트]")
key = ENV.get("GEMINI_API_KEY")
if key:
    try:
        u = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        with urllib.request.urlopen(u, timeout=25) as r:
            ms = [m["name"].split("/")[-1] for m in json.load(r).get("models", [])]
        want = ENV.get("GEMINI_MODEL", "gemini-2.5-flash")
        row(
            OK,
            "Gemini 키 유효",
            f"모델 {len(ms)}개"
            + (f" · {want} 사용 가능" if any(want in m for m in ms) else f" · ⚠ {want} 없음"),
        )
        # function calling 왕복 1회
        body = {
            "contents": [{"role": "user", "parts": [{"text": "ECHO-1 태스크 상세를 조회해줘"}]}],
            "tools": [
                {
                    "functionDeclarations": [
                        {
                            "name": "get_task",
                            "description": "태스크 조회",
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
            f"호출됨: {fc['name']}({fc.get('args')})" if fc else "함수 호출 없이 텍스트만 반환",
        )
    except Exception as e:
        row(NO, "Gemini 검증 실패", str(e)[:70])
else:
    row(NO, "Gemini 검증", "키 없음")

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
        row(OK, "Jira 인증", f"{me.get('displayName')} <{me.get('emailAddress')}> @ {site}")
        pk = ENV.get("JIRA_PROJECT_KEY", "ECHO")
        req = urllib.request.Request(
            f"https://{site}/rest/api/3/project/{pk}",
            headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            p = json.load(r)
        row(OK, "Jira 프로젝트", f"{p.get('key')} · {p.get('name')} · {p.get('projectTypeKey')}")
    except urllib.error.HTTPError as e:
        row(NO, "Jira 인증 실패", f"HTTP {e.code} — 토큰/이메일/사이트 확인")
    except Exception as e:
        row(NO, "Jira 연결 실패", str(e)[:70])
else:
    row(NO, "Jira 검증", "JIRA_SITE/EMAIL/API_TOKEN 미설정")

print("\n[선택 서비스]")
for port, name in ((1337, "Kaneo API"), (5432, "Postgres")):
    row(
        OK if port_open(port) else WARN,
        f"localhost:{port} ({name})",
        "열림" if port_open(port) else "미기동 (2단계)",
    )

print("\n[안전 가드]")
allow = ENV.get("WRITE_ALLOWLIST", "")
row(OK if os.path.exists(os.path.join(ROOT, ".gitignore")) else NO, ".gitignore", ".env 커밋 차단")
bad = [d for d in ("cytur.atlassian.net",) if d in (allow + " " + site)]
row(
    NO if bad else OK,
    "샌드박스 격리",
    f"실서비스 도메인 감지: {bad}" if bad else f"허용 목록: {allow or '(미설정)'}",
)

print("\n" + "=" * 78)
print(
    "MISS 는 SETUP.md 해당 번호를 보고 발급하세요. "
    '전부 OK 면: python -m pmo_agent.run "..." 로 첫 루프 실행.'
)
