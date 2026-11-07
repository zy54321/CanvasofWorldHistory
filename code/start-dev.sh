#!/usr/bin/env bash
# DEV 一键启动：后端 API（8089）+ 前端 dev server（5181）
#
# 与生产完全分离：
#   - 配置只读 .env.dev（不读、不继承生产 .env）；
#   - 后端由 run-dev-api.sh 启动，该脚本强制断言库名必须是 canvas_history_dev；
#   - 前端在 5181，proxy 到 8089，与生产的 5180/8088 互不干扰；
#   - 与 PROD 可以同时运行。
#
# 首次使用需先起 DEV 数据库：
#   docker compose -f docker-compose.dev.yml --env-file .env.dev up -d
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ ! -f .env.dev ]; then
  echo "未找到 .env.dev，无法启动 DEV 环境。" >&2
  exit 2
fi

if [ ! -f backend/target/canvas-history-api.jar ]; then
  echo "[1/2] 构建后端（首次较慢）…"
  ( cd backend && mvn -q -B -DskipTests package )
fi

if [ ! -d frontend/node_modules ]; then
  echo "[2/2] 安装前端依赖…"
  ( cd frontend && npm install --no-audit --no-fund )
fi

# 端口取自 .env.dev，带默认值兜底
WEB_PORT="$(grep -E '^WEB_HOST_PORT=' .env.dev | cut -d= -f2)"
WEB_PORT="${WEB_PORT:-5181}"
API_PORT="$(grep -E '^API_HOST_PORT=' .env.dev | cut -d= -f2)"
API_PORT="${API_PORT:-8089}"

cleanup() { kill "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "启动 DEV：API ${API_PORT} / WEB ${WEB_PORT}（配置来源 .env.dev）"

bash backend/run-dev-api.sh & API_PID=$!
# 显式指定 DEV 环境文件：vite 默认读 .env（生产），只有这里才切到 .env.dev
( cd frontend && VITE_ENV_FILE=../.env.dev npx vite --host 127.0.0.1 --port "$WEB_PORT" ) & WEB_PID=$!

# 等后端就绪后再做一次身份自检，防止「以为连的是 DEV、其实连了别处」
ok=0
for _ in $(seq 1 60); do
  H="$(curl -s -m 2 "http://127.0.0.1:${API_PORT}/api/v1/meta/health" || true)"
  if printf '%s' "$H" | grep -q '"status":"ok"'; then ok=1; break; fi
  if ! kill -0 "$API_PID" 2>/dev/null; then break; fi
  sleep 1
done

echo
if [ "$ok" -eq 1 ]; then
  DB_SEEN="$(printf '%s' "$H" | sed -n 's/.*"database":"\([^"]*\)".*/\1/p')"
  echo "自检：health.database=${DB_SEEN}"
  if [ "$DB_SEEN" != "canvas_history_dev" ]; then
    echo "⚠ 自检未通过：当前连接的不是 canvas_history_dev，已停止 DEV 进程。" >&2
    cleanup
    exit 1
  fi
  echo "DEV 已就绪"
else
  echo "⚠ 后端未在预期时间内就绪，请检查上方日志。" >&2
fi

echo "API : http://127.0.0.1:${API_PORT}/api/v1/meta/health"
echo "WEB : http://127.0.0.1:${WEB_PORT}/"
echo "Ctrl+C 结束"
wait
