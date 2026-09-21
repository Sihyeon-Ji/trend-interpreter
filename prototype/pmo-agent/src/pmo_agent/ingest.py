"""메모·필기 이미지 → 일정 변경 제안. Gemini 멀티모달 입력 경로.

설계 원칙(SETUP.md 그대로): 모델은 '읽기'만 한다 — 사진과 문장에서 무엇을 말하는지 뽑아낼 뿐,
태스크가 실존하는지·날짜가 말이 되는지·일정에 어떤 영향인지는 전부 이 파일의 코드와 schedule.py 가
판정한다.
모델이 지어낸 태스크 키나 상대 날짜는 여기서 걸러져 '사람에게 물을 질문'으로 떨어진다.

네트워크 호출은 call() 하나뿐이고 주입 가능하다 — 그래서 API 키 없이 나머지 전부를 단위 테스트할 수
있다.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import sys

from pmo_agent import llm, schedule

MAX_BYTES = 15 * 1024 * 1024  # inline 첨부 상한 (그 이상은 Files API 가 필요하다)
MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".pdf": "application/pdf",
}

EXTRACT_SYSTEM = """너는 회의 메모와 손글씨 노트를 읽어 프로젝트 변경사항을 뽑아내는 추출기다. 규칙:
1) 문서에 적힌 것만 뽑는다. 추측하거나 보충하지 않는다. 안 읽히면 읽히는 대로만 적고 confidence 를
낮춘다.
2) 날짜는 반드시 YYYY-MM-DD 로 적는다. '다음 주 화요일' 같은 표현은
   주어진 오늘 날짜를 기준으로 환산한다. 불확실하면 duedate 를 비우고 question 에 적는다.
3) 태스크는 문서에 적힌 그대로 적는다
   (키 'ECHO-12' 가 있으면 키를, 없으면 제목 문구를). 키를 지어내지 않는다.
4) 일정 계산은 하지 않는다. 며칠 밀리는지, 무엇이 임계경로인지는 네 일이 아니다.
5) 담당자 확인이 필요한 것은 question 으로 남긴다."""

SCHEMA = {
    "type": "object",
    "properties": {
        "updates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "태스크 키 또는 제목 문구"},
                    "duedate": {"type": "string", "description": "YYYY-MM-DD, 없으면 빈 문자열"},
                    "status": {
                        "type": "string",
                        "description": "예: Done, In Progress. 없으면 빈 문자열",
                    },
                    "note": {"type": "string", "description": "코멘트로 남길 특이사항"},
                    "confidence": {"type": "number", "description": "0.0~1.0 판독 확신도"},
                },
                "required": ["task"],
            },
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "태스크에 매달리지 않는 일반 특이사항",
        },
        "questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "사람에게 확인할 질문",
        },
    },
    "required": ["updates"],
}


# ---------- 입력 만들기 (키 불필요) ----------
def mime_of(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext not in MIME:
        raise ValueError(f"지원하지 않는 형식: {ext or path} (지원: {', '.join(sorted(MIME))})")
    return MIME[ext]


def attach(path: str) -> dict:
    """파일 → Gemini inline_data 파트. 크기 상한을 넘으면 거부한다."""
    size = os.path.getsize(path)
    if size > MAX_BYTES:
        raise ValueError(
            f"{os.path.basename(path)} 가 너무 크다 ({size / 1048576:.1f}MB > 15MB). 줄여서 다시 "
            f"넣어라."
        )
    with open(path, "rb") as f:
        return {
            "inline_data": {"mime_type": mime_of(path), "data": base64.b64encode(f.read()).decode()}
        }


def build_parts(text: str = "", images=(), today: dt.date | None = None, keys=()) -> list:
    """모델에 보낼 parts. 실존 태스크 키 목록을 같이 줘서 헛다리를 줄인다."""
    today = today or dt.date.today()
    head = [f"오늘은 {today.isoformat()} 이다."]
    if keys:
        head.append("이 프로젝트에 실제로 존재하는 태스크 키: " + ", ".join(sorted(keys)[:200]))
    if text:
        head.append("메모:\n" + text)
    if images:
        head.append(f"첨부한 이미지 {len(images)}장에서 읽히는 내용도 함께 반영하라.")
    return [{"text": "\n\n".join(head)}] + [attach(p) for p in images]


# ---------- 모델 호출 (여기만 키가 필요) ----------
def call(parts: list) -> dict:
    """Gemini 멀티모달 호출. JSON 스키마를 강제해 자유 문장이 섞이지 않게 한다.
    재시도·오류 본문·백엔드 전환은 llm.py 가 맡는다."""
    return llm.generate(
        {
            "contents": [{"role": "user", "parts": parts}],
            "systemInstruction": {"parts": [{"text": EXTRACT_SYSTEM}]},
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": SCHEMA,
            },
        }
    )


def parse(resp: dict) -> dict:
    """Gemini 응답 → {updates, notes, questions}.

    깨진 응답은 예외 대신 빈 결과 + 질문으로 돌려준다.
    """
    parts = ((resp.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    raw = "".join(p.get("text", "") for p in parts).strip()
    if not raw:
        return {
            "updates": [],
            "notes": [],
            "questions": ["모델이 아무것도 읽어내지 못했다. 사진이 흐리지 않은지 확인 필요."],
        }
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {
            "updates": [],
            "notes": [],
            "questions": ["모델 응답을 해석하지 못했다. 다시 시도 필요."],
            "raw": raw[:500],
        }
    return {
        "updates": list(data.get("updates") or []),
        "notes": list(data.get("notes") or []),
        "questions": list(data.get("questions") or []),
    }


# ---------- 검증 (키 불필요) ----------
def resolve(name: str, tasks: dict) -> tuple:
    """모델이 말한 태스크 → 실제 키. 반환 (키 or None, 사유).
    키 일치 우선, 없으면 제목 부분일치. 여러 개에 걸리면 사람이 고르게 한다."""
    if not name:
        return None, "태스크가 비어 있다"
    s = name.strip()
    for k in tasks:
        if k.lower() == s.lower():
            return k, ""
    hits = [k for k, t in tasks.items() if s.lower() in (t.summary or "").lower()]
    if len(hits) == 1:
        return hits[0], ""
    if len(hits) > 1:
        return None, f"'{s}' 가 여러 태스크에 걸린다: {', '.join(sorted(hits))}"
    return None, f"'{s}' 에 해당하는 태스크가 없다"


def validate(extraction: dict, tasks: dict, today: dt.date, max_ahead_days: int = 400) -> dict:
    """모델 출력 → 적용 가능한 변경(resolved) / 사람에게 물을 것(unresolved).
    태스크가 실존하고, 날짜가 ISO 이고, 상식적인 범위일 때만 통과시킨다."""
    resolved, unresolved = [], []
    questions = list(extraction.get("questions") or [])
    for u in extraction.get("updates") or []:
        key, why = resolve(str(u.get("task") or ""), tasks)
        if not key:
            unresolved.append({"said": u.get("task"), "reason": why, "raw": u})
            continue
        item = {
            "key": key,
            "summary": tasks[key].summary,
            "assignee": tasks[key].assignee,
            "confidence": float(u.get("confidence") or 0.0),
        }
        due = (u.get("duedate") or "").strip()
        if due:
            try:
                d = schedule.parse_date(due)
            except ValueError:
                unresolved.append(
                    {"said": u.get("task"), "reason": f"날짜를 해석할 수 없다: '{due}'", "raw": u}
                )
                continue
            if abs((d - today).days) > max_ahead_days:
                unresolved.append(
                    {"said": u.get("task"), "reason": f"날짜가 비상식적이다: {d}", "raw": u}
                )
                continue
            item["duedate"] = d.isoformat()
            item["duedate_was"] = tasks[key].duedate.isoformat() if tasks[key].duedate else None
        if (u.get("status") or "").strip():
            item["status"] = u["status"].strip()
        if (u.get("note") or "").strip():
            item["note"] = u["note"].strip()
        if len(item) <= 4:  # key/summary/assignee/confidence 뿐 = 바뀌는 게 없다
            unresolved.append({"said": u.get("task"), "reason": "바꿀 내용이 없다", "raw": u})
            continue
        resolved.append(item)
    for r in unresolved:
        questions.append(f"{r['reason']} — 원문: '{r['said']}'. 어느 태스크를 말하는지 확인 필요.")
    return {
        "resolved": resolved,
        "unresolved": unresolved,
        "notes": list(extraction.get("notes") or []),
        "questions": questions,
    }


def impact(resolved: list, tasks: dict, today: dt.date) -> dict:
    """변경을 적용하면 일정이 어떻게 되는지. 숫자는 전부 schedule.py 가 낸다."""
    after = {k: schedule.Task(**dict(t.__dict__)) for k, t in tasks.items()}
    for r in resolved:
        t = after[r["key"]]
        if r.get("duedate"):
            t.duedate = schedule.parse_date(r["duedate"])
        if r.get("status"):
            t.status = r["status"]
    before_s, after_s = schedule.summary(tasks, today), schedule.summary(after, today)
    was = {x["key"] for x in before_s["risks"]}
    return {
        "predicted_finish_before": before_s["predicted_finish"],
        "predicted_finish_after": after_s["predicted_finish"],
        "risks_before": len(before_s["risks"]),
        "risks_after": len(after_s["risks"]),
        "newly_at_risk": [x for x in after_s["risks"] if x["key"] not in was],
    }


def to_proposals(v: dict) -> list:
    """검증 통과분 → 승인 게이트에 올릴 propose_* 호출 목록. 여기서 실행하지 않는다."""
    out = []
    for r in v.get("resolved") or []:
        if r.get("duedate"):
            out.append(
                {"tool": "propose_field_update", "args": {"key": r["key"], "duedate": r["duedate"]}}
            )
        if r.get("status"):
            out.append(
                {"tool": "propose_transition", "args": {"key": r["key"], "to_status": r["status"]}}
            )
        if r.get("note"):
            out.append({"tool": "propose_comment", "args": {"key": r["key"], "text": r["note"]}})
    for n in v.get("notes") or []:
        out.append(
            {"tool": "note", "args": {"text": n}}
        )  # 태스크에 안 붙는 특이사항 — 리포트에만 남는다
    return out


# ---------- 조합 ----------
def ingest(
    text: str = "", images=(), tasks: dict | None = None, today: dt.date | None = None, caller=call
) -> dict:
    """메모/이미지 → 검증된 변경 제안 + 일정 영향 + 사람에게 물을 질문.
    caller 를 바꿔 끼우면 네트워크 없이 돌릴 수 있다 (테스트가 그렇게 한다)."""
    tasks = tasks or {}
    today = today or dt.date.today()
    if not text and not images:
        return {"error": "메모 텍스트나 이미지 중 하나는 있어야 한다."}
    parts = build_parts(text, images, today, keys=tasks.keys())
    v = validate(parse(caller(parts)), tasks, today)
    v["proposals"] = to_proposals(v)
    v["impact"] = impact(v["resolved"], tasks, today) if v["resolved"] else None
    v["applied"] = False  # 승인 전에는 아무것도 반영되지 않았다
    return schedule.iso(v)


if __name__ == "__main__":
    from pmo_agent.tools import _fetch

    args = [a for a in sys.argv[1:]]
    imgs = [a for a in args if os.path.splitext(a)[1].lower() in MIME]
    memo = " ".join(a for a in args if a not in imgs)
    print(json.dumps(ingest(memo, imgs, _fetch()), ensure_ascii=False, indent=1))
