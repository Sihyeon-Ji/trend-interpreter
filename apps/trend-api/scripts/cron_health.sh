#!/usr/bin/env bash
# 하루 한 번 사전 건강 점검. 사람이 읽는 표와 기계가 읽는 한 줄을 함께 남긴다.
set -uo pipefail
cd /home/cytur/trend || exit 1
export PATH="/home/cytur/.local/bin:$PATH"
mkdir -p /home/cytur/trend/logs
uv run scripts/health_check.py >> /home/cytur/trend/logs/health.log 2>&1
uv run scripts/health_check.py --json >> /home/cytur/trend/logs/health.jsonl 2>&1
tail -n 2000 /home/cytur/trend/logs/health.log > /tmp/h.$$ && mv /tmp/h.$$ /home/cytur/trend/logs/health.log
tail -n 400 /home/cytur/trend/logs/health.jsonl > /tmp/hj.$$ && mv /tmp/hj.$$ /home/cytur/trend/logs/health.jsonl
