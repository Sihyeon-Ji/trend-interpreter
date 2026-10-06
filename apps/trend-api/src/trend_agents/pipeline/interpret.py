"""3단계 쇼츠 해석. 아직 해석하지 않은 집중 국가 인기 쇼츠를 조회수순으로, 요청 하나에 최대 8개. 무료 등급 503 이면 폴백 모델."""
from __future__ import annotations


from google.genai import errors

from ..config import GEMINI_MODEL, REGIONS_FOCUS
from ..interpreters.gemini_video import interpret_shorts
from ..storage import dictionary_store as ds
from ..storage import store as db
from .gemini import affordable, budget_left, charge, note_call, note_quota
from .gemini import models as gemini_models
from .runs import stage
from ..storage.db import Connection

BATCH = 1   # 영상은 하나씩 — 8개를 한 요청에 넣으면 500, 3개는 영상과 해석을 짝짓지 못해 0건(10-06, 무료 등급). 하나씩은 8/8 성공


def pending_urls(con: Connection, limit: int) -> list[str]:
    q = f"""SELECT v.json FROM videos v LEFT JOIN interpretations i ON i.video_id = v.video_id
            WHERE i.video_id IS NULL AND v.duration_sec <= 180 AND v.region IN ({','.join('?' * len(REGIONS_FOCUS))})
            ORDER BY v.view_count DESC LIMIT ?"""
    rows = con.execute(q, (*REGIONS_FOCUS, limit)).fetchall()
    from ..schemas import ShortsVideo

    return [ShortsVideo.model_validate_json(r[0]).url for r in rows]


def run(con: Connection, max_batches: int = 8) -> dict:
    with stage(con, "interpret") as r:
        urls = pending_urls(con, BATCH * max_batches)
        n = 0
        for b in range(0, len(urls), BATCH):
            chunk = urls[b:b + BATCH]
            if budget_left(con) < 2:
                r.note = "예산 부족"
                break
            # 모델 사슬(gemini.models) 차례로 — 3.8 이 한도(429)·용량(503)·서버 오류(500)면 다음 모델. 두 모델만 보고 500 에 멈춰
            # 트윈에서 10-04~10-06 해석이 매번 실패했다. 금액 상한(affordable·charge)은 모델마다 그대로 본다
            res, used, last, capped = None, "", None, False
            for m in gemini_models(con, GEMINI_MODEL):
                if not affordable(con, m):
                    capped = True
                    continue
                try:
                    ds.gemini_spend(con, 1)
                    note_call(con, m)
                    res, used = interpret_shorts(chunk, model=m, charge=lambda mm, resp: charge(con, mm, resp)), m
                    break
                except errors.APIError as e:
                    last = e
                    if e.code not in (429, 500, 503):
                        raise
                    note_quota(con, m, e)
                    if e.code in (500, 503):
                        note_call(con, m, -1)
            if res is None:
                if capped and last is None:
                    r.note = "금액 상한"
                    break
                raise last or RuntimeError("쓸 수 있는 Gemini 모델이 없다")
            n += db.save_interpretations(con, res.items, used)
            r.detail.setdefault("models", []).append(used)
            r.models.add(used)   # 영상 해석은 gemini.py 를 거치지 않는다 — 실행 기록의 모델 ID 는 여기서 적는다
            if res.dropped:  # 영상에 붙일 수 없는 해석 — 그 영상은 다음 실행에서 다시 시도된다
                r.note += f"batch{b // BATCH}: 귀속 불가 {res.dropped}건 버림 "
        r.count = n
        r.detail["pending"] = len(pending_urls(con, 500))
    return {"interpret": r}
