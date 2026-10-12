"""문구 승인 기록 (Plan 20 ⑤, ktwoo-copy-flow A1) — 시장 하나의 초안을 사람이 승인·반려한 기록(copy_approvals, migration 025).

- 한 줄 = 시장 하나: 고른 밈(term_id·표기), 제품 한 줄, 문구들(플랫폼·본문)과 문구마다의 규칙 검사 결과, AI 의견(시장마다 한 번),
  요청한 계정·시각, 결정(승인·반려)·결정한 사람·시각·메모. 검수자가 초안에서 바로 승인하면 요청과 승인을 한 번에 적는다.
- 이용자 문구는 이 표에만 둔다. API 는 검수자·읽기 전용 계정에게만 본문을 보이고 요청한 사람에게는 본문 없는 상태만 준다.
  운영 로그·알림에는 본문을 쓰지 않는다. 본문(제품 한 줄·문구·AI 의견 문장)은 RETENTION_DAYS 가 지나면 지운다(prune) —
  유지보수 Job·수집 retention 단계가 매일, 관리 화면이 목록을 읽을 때마다 부른다.
- 묶음은 규칙 검사 결과와 AI 의견으로 나눈다. AI 점수로 줄 세우지 않고, 막힘은 규칙만으로 정한다(판정은 데이터, LLM 은 서술):
    blocked  쓰지 말라고 한 말(사용 자제·저속한 말투)이나 욕설·선정 표현이 든 문구가 있다 — 승인할 수 없다
    read     규칙 표시(조심·민감한 소재·판단 보류·식는 말·시장 밖·현지 표기)가 있거나, AI 의견이 '뜻과 다름'·'판단 못 함'이거나 받지 못했다
    clean    규칙을 통과했고 AI 의견도 '뜻에 맞다'
  규칙 검사는 부르는 쪽(API)이 pipeline/copycheck 로 한다 — 이 모듈은 문구마다의 코드 목록만 받는다. AI 의견은 초안 화면이 받은 것을
  그대로 적는다(모델을 다시 부르지 않는다) — 의견이라 막힘을 풀지 못하고, '읽어 볼 것' 과 '깨끗함' 사이만 옮긴다.
"""
from __future__ import annotations

import json
import uuid
from datetime import timedelta

from . import dictionary_store as ds
from .db import Connection

RETENTION_DAYS = 30
BLOCKING = ("avoid", "crude", "unsafe")
FLAGS = ("caution", "sensitive", "undecided", "fading", "not_in_region", "no_script")
FIT_FLAG = {"off": "fit_off", "unsure": "fit_unsure"}      # 그 밖(받지 못함)은 fit_none
COLUMNS = ("approval_id", "market", "term_id", "canonical", "lang", "product", "copies_json", "checks_json", "fit", "fit_copy", "fit_note",
           "image_meme", "grp", "reasons_json", "status", "requested_by", "requested_at", "decided_by", "decided_at", "memo", "expired_at")


class ApprovalError(RuntimeError):
    """blocked 막힌 문구는 승인하지 않는다 · decided 이미 결정했다 · expired 본문을 지워 다시 볼 수 없다 · missing 없다."""

    def __init__(self, code: str, reasons: list[str] | None = None):
        super().__init__(code)
        self.code = code
        self.reasons = reasons or []


def copy_issues(codes: list[str], unsafe: bool) -> list[str]:
    """문구 하나의 규칙 코드 — 문구에 든 밈의 문제(CopyIssue.code)와 욕설·선정(unsafe). 막는 것 먼저, 같은 코드는 한 번."""
    found = set(codes) | ({"unsafe"} if unsafe else set())
    return [c for c in (*BLOCKING, *FLAGS) if c in found]


def group(issues: list[list[str]], fit: str | None) -> tuple[str, list[str]]:
    """(묶음, 이유 코드). issues 는 문구마다의 규칙 코드, fit 은 AI 의견(ok·off·unsure·None)."""
    seen = {c for codes in issues for c in codes}
    reasons = [c for c in (*BLOCKING, *FLAGS) if c in seen]
    if fit != "ok":
        reasons.append(FIT_FLAG.get(fit or "", "fit_none"))
    if any(c in BLOCKING for c in reasons):
        return "blocked", reasons
    return ("read", reasons) if reasons else ("clean", [])


def create(con: Connection, *, market: str, term_id: str, canonical: str, lang: str, product: str, copies: list[dict],
           issues: list[list[str]], fit: str | None, fit_copy: int | None, fit_note: str | None, image_meme: bool,
           by: str, approve: bool) -> dict:
    """요청을 적는다. approve 면 요청과 승인을 한 번에(검수자가 초안에서 바로) — 막힌 초안이면 ApprovalError('blocked').
    copies 는 [{platform, text, hashtags}], issues 는 같은 순서의 규칙 코드."""
    grp, reasons = group(issues, fit)
    if approve and grp == "blocked":
        raise ApprovalError("blocked", reasons)
    at = ds.now_s()
    approval_id = f"ap_{uuid.uuid4().hex[:16]}"
    checks = [{"platform": c["platform"], "issues": i} for c, i in zip(copies, issues)]
    con.execute(f"INSERT INTO copy_approvals ({', '.join(COLUMNS[:20])}) VALUES ({', '.join('?' * 20)})",
                (approval_id, market, term_id, canonical, lang, product or None, json.dumps(copies, ensure_ascii=False),
                 json.dumps(checks, ensure_ascii=False), fit, fit_copy, fit_note or None, int(image_meme), grp,
                 json.dumps(reasons), "approved" if approve else "pending", by, at, by if approve else None, at if approve else None, None))
    con.commit()
    return get(con, approval_id)  # type: ignore[return-value]


def get(con: Connection, approval_id: str) -> dict | None:
    row = con.execute(f"SELECT {', '.join(COLUMNS)} FROM copy_approvals WHERE approval_id=?", (approval_id,)).fetchone()
    return dict(zip(COLUMNS, row)) if row else None


def stored_copies(row: dict) -> list[dict]:
    """다시 검사할 본문 [{platform, text, hashtags}] — 지운 뒤면 빈 목록."""
    return json.loads(row["copies_json"]) if row["copies_json"] else []


def decide(con: Connection, approval_id: str, approve: bool, by: str, memo: str = "", issues: list[list[str]] | None = None) -> dict:
    """결정을 적는다. 기다리는 요청에만 한 번 — 그사이 다른 결정이 먼저 들어왔으면 ApprovalError('decided').
    승인이면 부르는 쪽이 지금 사전으로 다시 검사한 규칙 코드(issues)를 넘긴다: 그사이 막힌 말이 됐으면 묶음을 고쳐 적고 승인하지 않는다."""
    row = get(con, approval_id)
    if row is None:
        raise ApprovalError("missing")
    if row["status"] != "pending":
        raise ApprovalError("decided")
    if approve:
        if row["expired_at"] or not row["copies_json"]:
            raise ApprovalError("expired")
        if issues is None and row["grp"] == "blocked":          # 다시 검사하지 않았으면 적어 둔 묶음대로 막는다
            raise ApprovalError("blocked", json.loads(row["reasons_json"]))
        if issues is not None:
            grp, reasons = group(issues, row["fit"])
            checks = [{"platform": c["platform"], "issues": i} for c, i in zip(stored_copies(row), issues)]
            con.execute("UPDATE copy_approvals SET grp=?, reasons_json=?, checks_json=? WHERE approval_id=? AND status='pending'",
                        (grp, json.dumps(reasons), json.dumps(checks, ensure_ascii=False), approval_id))
            con.commit()
            if grp == "blocked":
                raise ApprovalError("blocked", reasons)
    done = con.execute("UPDATE copy_approvals SET status=?, decided_by=?, decided_at=?, memo=? WHERE approval_id=? AND status='pending'",
                       ("approved" if approve else "rejected", by, ds.now_s(), memo.strip() or None, approval_id)).rowcount
    con.commit()
    if not done:
        raise ApprovalError("decided")
    return get(con, approval_id)  # type: ignore[return-value]


def item(row: dict) -> dict:
    """관리 화면의 한 줄(views.ApprovalItem 모양) — 본문을 지웠으면 본문 칸은 비고 검사 코드만 남는다."""
    checks = json.loads(row["checks_json"])
    texts = stored_copies(row)
    copies = [{"platform": c["platform"], "issues": c["issues"],
               "text": texts[i]["text"] if i < len(texts) else None, "hashtags": texts[i].get("hashtags", []) if i < len(texts) else []}
              for i, c in enumerate(checks)]
    return {**state(row), "term_id": row["term_id"], "canonical": row["canonical"], "lang": row["lang"], "product": row["product"],
            "copies": copies, "fit": row["fit"], "fit_copy": row["fit_copy"], "fit_note": row["fit_note"], "expired": bool(row["expired_at"])}


def state(row: dict) -> dict:
    """요청한 사람이 보는 상태(views.ApprovalState 모양) — 본문 없이."""
    return {"approval_id": row["approval_id"], "market": row["market"], "status": row["status"], "group": row["grp"],
            "reasons": json.loads(row["reasons_json"]), "image_meme": bool(row["image_meme"]), "requested_by": row["requested_by"],
            "requested_at": row["requested_at"], "decided_by": row["decided_by"], "decided_at": row["decided_at"], "memo": row["memo"]}


def listing(con: Connection, history: int = 50, pending: int = 300) -> dict:
    """{pending: 기다리는 것 최신순, history: 결정한 것 결정한 때 최신순}(views.ApprovalList 모양)."""
    cols = ", ".join(COLUMNS)
    waiting = con.execute(f"SELECT {cols} FROM copy_approvals WHERE status='pending' ORDER BY requested_at DESC LIMIT ?", (pending,)).fetchall()
    done = con.execute(f"SELECT {cols} FROM copy_approvals WHERE status<>'pending' ORDER BY decided_at DESC LIMIT ?", (history,)).fetchall()
    return {"pending": [item(dict(zip(COLUMNS, r))) for r in waiting], "history": [item(dict(zip(COLUMNS, r))) for r in done]}


def prune(con: Connection, days: int = RETENTION_DAYS) -> int:
    """보존 기간이 지난 요청의 본문(제품 한 줄·문구·AI 의견 문장)을 지운다. 지운 줄 수. 시장·밈·검사 코드·결정 기록은 남긴다.
    표가 아직 없는 DB(마이그레이션 전)에서는 0 — 유지보수 Job 은 마이그레이션을 하지 않는다."""
    if not con.execute("SELECT to_regclass('copy_approvals')").fetchone()[0]:
        return 0
    cutoff = (ds.now() - timedelta(days=days)).isoformat()
    n = con.execute("UPDATE copy_approvals SET product=NULL, copies_json=NULL, fit_note=NULL, expired_at=? "
                    "WHERE expired_at IS NULL AND requested_at < ?", (ds.now_s(), cutoff)).rowcount
    con.commit()
    return n
