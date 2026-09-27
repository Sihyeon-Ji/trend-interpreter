#!/usr/bin/env bash
# cron 이 부르는 파이프라인 한 바퀴. 겹쳐 돌지 않게 잠금을 걸고, 로그는 길이를 제한한다.
#
# MCTI 와 GPU·Ollama 를 함께 쓰므로 MCTI cron 이 몰리는 새벽 2~8시는 피해서 등록한다.
# 등록: crontab -e  →  15 9,14,19,23 * * * /home/cytur/trend/scripts/cron_pipeline.sh
set -uo pipefail
cd /home/cytur/trend || exit 1
export PATH="/home/cytur/.local/bin:$PATH"
LOG=/home/cytur/trend/logs/pipeline.log
LOCK=/tmp/trend-pipeline.lock
mkdir -p "$(dirname "$LOG")"

exec 9>"$LOCK"
if ! flock -n 9; then
  echo "[$(date '+%F %T')] 이전 실행이 아직 돌고 있다 — 건너뜀" >> "$LOG"
  exit 0
fi

echo "[$(date '+%F %T')] 시작" >> "$LOG"
timeout 3600 uv run scripts/run_pipeline.py >> "$LOG" 2>&1
echo "[$(date '+%F %T')] 끝 (코드 $?)" >> "$LOG"

# 로그가 무한히 자라지 않게 뒤 4000줄만 남긴다
tail -n 4000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
