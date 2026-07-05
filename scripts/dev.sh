#!/usr/bin/env bash
# ai-07-b-subtitle 本地开发：start | stop | restart | status | dev
# dev/start 默认开启热更：后端 uvicorn --reload，前端 Vite HMR
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8907}"
VITE_PORT="${VITE_PORT:-9177}"
DEV_HOST="${DEV_HOST:-0.0.0.0}"
UVICORN_RELOAD="${UVICORN_RELOAD:-1}"
RUN_DIR="$ROOT/.run"
LOG_DIR="$RUN_DIR/logs"
BACKEND_PID="$RUN_DIR/backend.pid"
FRONTEND_PID="$RUN_DIR/frontend.pid"

mkdir -p "$LOG_DIR"

port_pids() {
  lsof -ti ":$1" 2>/dev/null || true
}

stop_port() {
  local pids
  pids=$(port_pids "$1")
  [ -z "$pids" ] || kill $pids 2>/dev/null || true
}

stop_pid_file() {
  local f="$1"
  [ -f "$f" ] || return 0
  local pid
  pid=$(cat "$f" 2>/dev/null || true)
  [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
  rm -f "$f"
}

do_stop() {
  stop_pid_file "$BACKEND_PID"
  stop_pid_file "$FRONTEND_PID"
  stop_port "$BACKEND_PORT"
  stop_port "$VITE_PORT"
  echo "stopped (ports $BACKEND_PORT, $VITE_PORT)"
}

uvicorn_args() {
  local args=(app.main:app --host "$DEV_HOST" --port "$BACKEND_PORT")
  if [ "$UVICORN_RELOAD" = "1" ]; then
    args+=(--reload --reload-dir "$ROOT/backend/app")
  fi
  printf '%s\n' "${args[@]}"
}

start_backend() {
  cd "$ROOT/backend"
  if [ ! -d .venv ]; then
    echo "error: backend/.venv 不存在，请先 pip install -r requirements.txt" >&2
    exit 1
  fi
  # shellcheck disable=SC2046
  "$ROOT/backend/.venv/bin/uvicorn" $(uvicorn_args) "$@"
}

start_frontend() {
  cd "$ROOT/frontend"
  if [ ! -d node_modules ]; then
    echo "installing frontend deps..."
    npm install --silent
  fi
  ./node_modules/.bin/vite --host "$DEV_HOST" --port "$VITE_PORT" "$@"
}

do_start() {
  do_stop
  sleep 0.5

  # shellcheck disable=SC2046
  nohup "$ROOT/backend/.venv/bin/uvicorn" $(uvicorn_args) >"$LOG_DIR/backend.log" 2>&1 &
  echo $! >"$BACKEND_PID"

  nohup bash -c "cd '$ROOT/frontend' && ./node_modules/.bin/vite --host '$DEV_HOST' --port '$VITE_PORT'" \
    >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$FRONTEND_PID"

  sleep 1.5
  do_status
  echo "hot reload: backend reload=$UVICORN_RELOAD, frontend=Vite HMR"
}

do_dev() {
  do_stop
  sleep 0.3
  trap 'do_stop' INT TERM EXIT

  start_backend &
  echo $! >"$BACKEND_PID"
  start_frontend &
  echo $! >"$FRONTEND_PID"

  echo "dev 模式（热更已开）：backend http://localhost:$BACKEND_PORT  frontend http://localhost:$VITE_PORT"
  echo "后端改 app/ 自动 reload；前端改 src/ 自动 HMR。Ctrl+C 停止。"
  wait
}

do_status() {
  local be fe reload_hint=""
  be=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$BACKEND_PORT/api/health" 2>/dev/null || echo down)
  fe=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:$VITE_PORT/" 2>/dev/null || echo down)
  [ "$UVICORN_RELOAD" = "1" ] && reload_hint=" reload=on"
  echo "backend  http://localhost:$BACKEND_PORT  health=$be$reload_hint  pid=$(cat "$BACKEND_PID" 2>/dev/null || echo -)"
  echo "frontend http://localhost:$VITE_PORT  status=$fe  hmr=on  pid=$(cat "$FRONTEND_PID" 2>/dev/null || echo -)"
  echo "logs: $LOG_DIR/"
}

cmd="${1:-restart}"
case "$cmd" in
  start) do_start ;;
  stop) do_stop ;;
  restart) do_start ;;
  dev) do_dev ;;
  status) do_status ;;
  *)
    echo "用法: $0 {start|stop|restart|status|dev}" >&2
    echo "  dev   前台运行，改代码自动热更（推荐开发时用）" >&2
    exit 1
    ;;
esac
