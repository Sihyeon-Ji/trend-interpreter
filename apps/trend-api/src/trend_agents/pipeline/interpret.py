"""3단계 쇼츠 해석. 아직 해석하지 않은 집중 국가 인기 쇼츠를 조회수순으로, 요청 하나에 최대 8개. 무료 등급 503 이면 폴백 모델."""
from __future__ import annotations


from google.genai import errors

from ..config import GEMINI_FALLBACK_MODEL, GEMINI_MODEL, REGIONS_FOCUS
from ..interpreters.gemini_video import interpret_shorts
from ..storage import dictionary_store as ds
from ..storage import store as db
from .gemini import budget_left
from .runs import stage
from ..storage.db import Connection

BATCH = 8


def pending_urls(con: Connection, limit: int) -> list[str]:
    q = f"""SELECT v.json FROM videos v LEFT JOIN interpretations i ON i.video_id = v.video_id
            WHERE i.video_id IS NULL AND v.duration_sec <= 180 AND v.region IN ({','.join('?' * len(REGIONS_FOCUS))})
            ORDER BY v.view_count DESC LIMIT ?"""
    rows = con.execute(q, (*REGIONS_FOCUS, limit)).fetchall()
    from ..schemas import ShortsVideo

    return [ShortsVideo.model_validate_json(r[0]).url for r in rows]


def run(con: Connection, max_batches: int = 2) -> dict:
    with stage(con, "interpret") as r:
        urls = pending_urls(con, BATCH * max_batches)
        n = 0
        for b in range(0, len(urls), BATCH):
            chunk = urls[b:b + BATCH]
            if budget_left(con) < 2:
                r.note = "예산 부족"
                break
            used = GEMINI_MODEL
            try:
                ds.gemini_spend(con, 1)
                res = interpret_shorts(chunk, model=GEMINI_MODEL)
            except errors.APIError as e:
                if e.code not in (429, 503):
                    raise
                ds.gemini_spend(con, 1)
                used = GEMINI_FALLBACK_MODEL
                res = interpret_shorts(chunk, model=GEMINI_FALLBACK_MODEL)
            n += db.save_interpretations(con, res.items, used)
            r.detail.setdefault("models", []).append(used)
            if res.dropped:  # 영상에 붙일 수 없는 해석 — 그 영상은 다음 실행에서 다시 시도된다
                r.note += f"batch{b // BATCH}: 귀속 불가 {res.dropped}건 버림 "
        r.count = n
        r.detail["pending"] = len(pending_urls(con, 500))
    return {"interpret": r}
