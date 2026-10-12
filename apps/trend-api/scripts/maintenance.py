"""PC 없이 도는 유지보수 한 번: 사용자 문장 보존 기간 정리와 마지막 정상 게시 시각 점검(Plan 05·06).

운영에서는 Cloud Run Job 이 예약 실행한다. 개발자 PC 의 파이프라인(collect.retention)이 멈춰도 보존 기간을 지키고,
게시가 멈춘 것은 종료 코드와 로그 이벤트로 알린다.

- 정리: 해석 캐시 7일, 못 답한 질문 30일(ds.prune_user_text), 문구 승인 기록의 본문 30일(approvals.prune) — collect.retention 과 같은 함수.
- 점검: 지도·대시보드 게시(ds.PUBLISH_STAGES)가 모두 성공한 마지막 때가 ds.STALE_AFTER_HOURS(12시간)보다 오래됐나.
  23:15 실행 뒤 다음 날 09:15 실행까지 게시가 10시간 비므로 health_check 의 8시간으로는 밤마다 울린다.
- 연결: 표를 만들거나 마이그레이션하지 않는다(db.connect 를 쓰지 않는다). DB 역할에는 explain_cache·lookups 의 SELECT·DELETE,
  copy_approvals 의 SELECT·UPDATE 와 pipeline_runs 의 SELECT 만 있으면 된다 — 예약 작업이 스키마를 바꾸지 않는다.
- 출력: 이벤트 한 줄(event=maintenance). 지운 건수·게시 시각·오류 종류만 — 사용자 문장과 오류 메시지 원문(연결 정보가 들 수 있다)은
  넣지 않는다. Cloud Run 서비스·Job 에서는 JSON, 로컬 터미널에서는 텍스트(LOG_FORMAT=json 이면 JSON).
- 종료 코드: 0 정상, 1 정리·점검 실패(파이썬이 죽어도 1), 2 게시본이 오래됨(정리는 했다). 0 이 아니면 Job 실행이 실패로 남는다.
  오래됨은 다시 돌려도 풀리지 않으므로 Job 재시도는 0 으로 두고 다음 예약 실행에 맡긴다.

  uv run scripts/maintenance.py
  docker compose exec api python scripts/maintenance.py
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime

import psycopg

from trend_agents.config import DATABASE_URL
from trend_agents.logging_setup import configure, event
from trend_agents.storage import approvals, db
from trend_agents.storage import dictionary_store as ds

log = logging.getLogger("trend.maintenance")
OK, FAILED, STALE = 0, 1, 2


def connect() -> db.Connection:
    return db.Connection(psycopg.connect(DATABASE_URL, application_name="trend-maintenance"))


def run(con: db.Connection) -> tuple[int, dict]:
    """(종료 코드, 이벤트 필드). 정리를 먼저 한다 — 점검이 실패해도 지운 건수는 남긴다."""
    out: dict = {}
    try:
        out["explain_cache_deleted"], out["lookups_deleted"] = ds.prune_user_text(con)
        out["approval_text_cleared"] = approvals.prune(con)
        published = ds.last_published(con)
    except Exception as e:  # 권한·SQL 오류 — 종류만 남긴다
        return FAILED, {"status": "error", "error": type(e).__name__, **out}
    stale = ds.is_stale(published)
    age = round((ds.now() - datetime.fromisoformat(published)).total_seconds() / 3600, 1) if published else None
    return (STALE if stale else OK), {"status": "stale" if stale else "ok", **out, "last_published": published,
                                      "published_age_hours": age, "stale": stale, "stale_after_hours": ds.STALE_AFTER_HOURS}


def main() -> int:
    configure()
    try:
        con = connect()
    except Exception as e:  # 연결 실패 — 메시지에 호스트·사용자가 들어 있어 종류만 남긴다
        code, fields = FAILED, {"status": "error", "error": type(e).__name__}
    else:
        try:
            code, fields = run(con)
        finally:
            con.close()
    event(log, "maintenance", logging.INFO if code == OK else logging.ERROR, **fields)
    return code


if __name__ == "__main__":
    sys.exit(main())
