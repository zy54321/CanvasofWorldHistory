#!/usr/bin/env bash
# 一键本地启动：后端 API（8088）+ 前端 dev server（5180）
# 依赖：code/.env 中的 POSTGRES_* 与端口配置；首次需先构建后端与安装前端依赖。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ ! -f backend/target/canvas-history-api.jar ]; then
  echo "[1/2] 构建后端（首次较慢）…"
  ( cd backend && mvn -q -B -DskipTests package )
fi

if [ ! -d frontend/node_modules ]; then
  echo "[2/2] 安装前端依赖…"
  ( cd frontend && npm install --no-audit --no-fund )
fi

cleanup() { kill "${API_PID:-}" "${WEB_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

bash backend/run-dev.sh & API_PID=$!
( cd frontend && npx vite --host 127.0.0.1 ) & WEB_PID=$!

sleep 6
echo
echo "API : http://127.0.0.1:8088/api/v1/meta/health"
echo "WEB : http://127.0.0.1:5180/"
echo "Ctrl+C 结束"
wait