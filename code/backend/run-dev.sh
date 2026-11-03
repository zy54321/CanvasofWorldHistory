#!/usr/bin/env bash
# 本地启动只读查询 API（凭证从 ../.env 读取，不落源码）
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f target/canvas-history-api.jar ]; then
  echo "未找到 target/canvas-history-api.jar，请先构建：mvn -DskipTests package" >&2
  exit 1
fi

# shellcheck disable=SC1091
set -a; . ../.env; set +a

export DB_URL="jdbc:postgresql://127.0.0.1:${DB_HOST_PORT:-55432}/${POSTGRES_DB:-canvas_history}"
export DB_USER="${POSTGRES_USER}"
export DB_PASSWORD="${POSTGRES_PASSWORD}"
export API_PORT="${API_HOST_PORT:-8088}"

# 宿主机环境里存在 SERVER__PORT（IDE/工具注入），Spring 松散绑定会把它当成 server.port，
# 这里显式清掉并用命令行参数钉住端口（命令行优先级最高）。
unset SERVER__PORT SERVER_PORT 2>/dev/null || true

echo "API 启动：http://127.0.0.1:${API_PORT}  db=${POSTGRES_DB:-canvas_history}"
exec java -jar target/canvas-history-api.jar --server.port="${API_PORT}"
