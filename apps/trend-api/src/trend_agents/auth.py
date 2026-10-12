"""계정과 권한. 로그인한 사람은 자기 설정(세대·나라)을 갖고, 그중 검수자만 사전 승인·제외를 할 수 있다.

계정은 .env 의 ACCOUNTS 하나에 JSON 으로 둔다 — 비밀번호는 PBKDF2-SHA256 해시만 저장한다.
  ACCOUNTS=[{"user":"admin","hash":"pbkdf2$...","reviewer":true},{"user":"demo","hash":"pbkdf2$..."}]
심사용 계정은 "readonly":true 를 더한다 – 관리 화면을 보고 미리보기(Gemma 다시 분류)는 하지만 승인·결정은 못 한다.
나중에 Firebase Auth 로 갈 때는 `check_account` 만 ID 토큰 검증으로 바꾸고, 검수자 여부는 계정 목록 대신
Firebase 커스텀 클레임에서 읽으면 된다. 세션·미들웨어·저장 구조는 그대로다.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass

ITERATIONS = 200_000


@dataclass(frozen=True)
class Account:
    user: str
    reviewer: bool = False
    readonly: bool = False


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """stored 가 형식이 아니거나 비어 있으면 False. 비교는 상수 시간으로."""
    try:
        scheme, iters, salt_hex, want_hex = stored.split("$")
        if scheme != "pbkdf2":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(dk.hex(), want_hex)


def _accounts() -> list[dict]:
    try:
        rows = json.loads(os.getenv("ACCOUNTS", "") or "[]")
        return [r for r in rows if isinstance(r, dict) and r.get("user") and r.get("hash")]
    except (ValueError, TypeError):
        return []


def _same(a: str, b: str) -> bool:
    """상수 시간 비교. 바이트로 비교한다 — compare_digest 는 비ASCII 문자열을 받으면 TypeError 를 던져,
    한글 아이디를 입력한 사람이 401 대신 500 을 보게 된다(2026-09-16 테스트로 발견)."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def check_account(user: str, password: str) -> Account | None:
    """맞으면 계정, 아니면 None. 계정이 하나도 설정돼 있지 않으면 누구도 통과하지 못한다."""
    for row in _accounts():
        if _same(user.strip(), str(row["user"])) and verify_password(password, str(row["hash"])):
            return Account(user=str(row["user"]), reviewer=bool(row.get("reviewer")), readonly=bool(row.get("readonly")))
    return None


def is_account(user: str) -> bool:
    """설정된 계정인가 – 문구 승인 요청처럼 로그인한 사람만 쓰는 API 가 프론트의 세션 검사와 별개로 한 번 더 본다(익명 문구를 쌓지 않는다)."""
    return any(str(r["user"]) == user for r in _accounts())


def is_reviewer(user: str) -> bool:
    return any(str(r["user"]) == user and r.get("reviewer") for r in _accounts())


def is_readonly(user: str) -> bool:
    """심사용 읽기 전용 계정인가 – 결정 API 가 프론트의 검사와 별개로 한 번 더 막는다."""
    return any(str(r["user"]) == user and r.get("readonly") for r in _accounts())


def frontend_token_ok(sent: str | None) -> bool:
    """이 요청이 우리 프론트 서버를 거쳐 왔는가. 토큰이 설정돼 있지 않으면 통과시키지 않는다(기본 잠금)."""
    want = os.getenv("FRONTEND_API_TOKEN", "")
    return bool(want) and bool(sent) and _same(sent, want)
