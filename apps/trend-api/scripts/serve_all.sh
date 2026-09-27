#!/usr/bin/env bash
# trend-agents 를 내부망에 띄운다 (웹 :3100 · API :8180). 사용: bash scripts/serve_all.sh [start|stop|status]
set -u
ROOT=/home/cytur/trend
IP=$(hostname -I | awk '{print $1}')
LOG=${LOG_DIR:-$ROOT/data}
case "${1:-start}" in
  start)
    pgrep -f 'scripts/serve_api.py' >/dev/null || (cd "$ROOT" && nohup uv run scripts/serve_api.py > "$LOG/api.log" 2>&1 &)
    if ! ss -ltn 2>/dev/null | grep -q ':3100 '; then
      source /home/cytur/.nvm/nvm.sh >/dev/null 2>&1; nvm use 24 >/dev/null 2>&1
      (cd "$ROOT/web" && nohup env NEXT_PUBLIC_DATA_MODE=api NEXT_PUBLIC_API_BASE="http://$IP:8180" pnpm start -p 3100 -H 0.0.0.0 > "$LOG/web.log" 2>&1 &)
    fi
    for _ in $(seq 1 40); do
      [ "$(curl -s -o /dev/null -w '%{http_code}' -m 2 "http://127.0.0.1:3100/")" = "200" ] && break; sleep 1
    done
    echo "웹   http://$IP:3100"
    echo "API  http://$IP:8180/docs"
    ;;
  stop)
    pkill -f 'scripts/serve_api\.py'; pkill -f 'next-server \(v16'
    echo "중지"
    ;;
  status)
    ss -ltn 2>/dev/null | grep -E ':(3100|8180) ' || echo "안 떠 있음"
    curl -s -m 3 "http://127.0.0.1:8180/health" && echo
    ;;
  *) sed -n '2,3p' "$0"; exit 2;;
esac
