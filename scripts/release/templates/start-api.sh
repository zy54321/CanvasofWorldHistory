#!/usr/bin/env bash
# Canvas of World History —— 启动 API（单 Jar，同时提供页面与接口）
#
# 读取 config/.env（不入库、不进包）。目标库不是 canvas_history 时拒绝启动。
set -euo pipefail
cd "$(dirname "$0")/.."

CFG="config/.env"
[ -f "$CFG" ] || { echo "未找到 $CFG，请先复制 config/.env.example" >&2; exit 2; }
[ -f "api/canvas-history-api.jar" ] || { echo "未找到 api/canvas-history-api.jar" >&2; exit 2; }

set -a; . "./$CFG"; set +a

if [ "${POSTGRES_DB:-}" != "canvas_history" ]; then
  echo "拒绝启动：POSTGRES_DB=${POSTGRES_DB:-}，本包只服务 canvas_history" >&2
  exit 2
fi

export DB_URL="jdbc:postgresql://127.0.0.1:${DB_HOST_PORT:-15432}/${POSTGRES_DB}"
export DB_USER="${POSTGRES_USER}"
export DB_PASSWORD="${POSTGRES_PASSWORD}"
export API_PORT="${API_PORT:-5180}"
unset SERVER__PORT SERVER_PORT 2>/dev/null || true

echo "启动 Canvas of World History"
echo "  db   = ${POSTGRES_DB} @ 127.0.0.1:${DB_HOST_PORT:-15432}"
echo "  port = ${API_PORT}"
echo "  web  = http://127.0.0.1:${API_PORT}/"

# 外部静态目录 web/ 优先于 jar 内置资源：
# 部署时把 config.js（含 MapTiler key）放进 web/ 即可注入，无需重新打包。
exec java -jar api/canvas-history-api.jar --server.port="${API_PORT}" \
  --spring.web.resources.static-locations=file:./web/,classpath:/static/
