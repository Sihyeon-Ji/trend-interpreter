"""계정을 만든다/바꾼다. 비밀번호는 해시만 .env 에 남고, 평문은 이 명령의 출력에 한 번만 보여 준다(파일에 쓰지 않는다).

  uv run scripts/set_account.py --user admin --reviewer   # 검수자 (사전 승인·제외 가능)
  uv run scripts/set_account.py --user demo               # 일반 이용자 (설정만)
  uv run scripts/set_account.py --user demo --password …  # 비밀번호 직접 지정
  uv run scripts/set_account.py --list
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from trend_agents.auth import hash_password  # noqa: E402
from trend_agents.config import ROOT  # noqa: E402


def put(env: str, key: str, value: str) -> str:
    line = f"{key}={value}"
    if re.search(rf"^{key}=.*$", env, flags=re.M):
        return re.sub(rf"^{key}=.*$", lambda _: line, env, flags=re.M)
    return env.rstrip("\n") + "\n" + line + "\n"


def read(env: str, key: str) -> str:
    m = re.search(rf"^{key}=(.*)$", env, flags=re.M)
    return m.group(1) if m else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="")
    ap.add_argument("--password", default="")
    ap.add_argument("--reviewer", action="store_true", help="사전 승인·제외 권한 (/admin 접근)")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    env_path = ROOT / ".env"
    env = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    try:
        accounts = json.loads(read(env, "ACCOUNTS") or "[]")
    except ValueError:
        accounts = []

    if a.list or not a.user:
        print("계정:")
        for r in accounts:
            print(f"  {r['user']:12} {'검수자' if r.get('reviewer') else '이용자'}")
        if not accounts:
            print("  (없음)")
        return

    accounts = [r for r in accounts if r.get("user") != a.user]
    if a.remove:
        env = put(env, "ACCOUNTS", json.dumps(accounts, ensure_ascii=False))
        env_path.write_text(env, encoding="utf-8")
        print(f"계정 '{a.user}' 제거")
        return

    password = a.password or secrets.token_urlsafe(12)
    accounts.append({"user": a.user, "hash": hash_password(password), **({"reviewer": True} if a.reviewer else {})})
    env = put(env, "ACCOUNTS", json.dumps(accounts, ensure_ascii=False))
    if not read(env, "FRONTEND_API_TOKEN"):
        env = put(env, "FRONTEND_API_TOKEN", secrets.token_urlsafe(32))
    env_path.write_text(env, encoding="utf-8")

    web_env = ROOT.parent / "trend-web" / ".env.local"   # 프론트 서버만 읽는 값 (NEXT_PUBLIC_ 아님 → 브라우저에 안 나감)
    we = web_env.read_text(encoding="utf-8") if web_env.exists() else ""
    we = put(we, "FRONTEND_API_TOKEN", read(env, "FRONTEND_API_TOKEN"))
    if not read(we, "SESSION_SECRET"):
        we = put(we, "SESSION_SECRET", secrets.token_urlsafe(32))
    web_env.write_text(we, encoding="utf-8")

    print(f"계정 '{a.user}' ({'검수자' if a.reviewer else '이용자'}) 설정 완료")
    print(f"  비밀번호: {password}   ← 지금 안전한 경로로 전달하고 이 출력은 남기지 않는다 (.env 에는 해시만)")
    print("  프론트를 다시 시작해야 토큰이 반영된다")


if __name__ == "__main__":
    main()
