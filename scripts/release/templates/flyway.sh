#!/usr/bin/env bash
# Canvas of World History —— Flyway 迁移入口（Release 包内自带）
#
# 用法：
#   deploy/flyway.sh info       查看迁移状态（只读）
#   deploy/flyway.sh migrate    执行迁移
#
# 特点：
#   - 迁移脚本来自本包内的 db/migration，不依赖开发源码目录；
#   - 凭证经 `docker run -e VAR` 只传变量名，不出现在命令行；
#   - baselineOnMigrate=false、outOfOrder=false，禁止绕过真实迁移；
#   - 只对 canvas_history 生效，库名不符直接拒绝。
set -euo pipefail
cd "$(dirname "$0")/.."

CFG="config/.env"
[ -f "$CFG" ] || { echo "未找到 $CFG" >&2; exit 2; }
set -a; . "./$CFG"; set +a

DB_NAME="${1:-canvas_history}"
SUB="${2:-info}"

if [ "$DB_NAME" != "canvas_history" ]; then
  echo "拒绝执行：本包只允许迁移 canvas_history，收到 '$DB_NAME'" >&2
  exit 2
fi

FLYWAY_IMAGE="${FLYWAY_IMAGE:-flyway/flyway:13.12.0-alpine}"
export FLYWAY_URL="jdbc:postgresql://db:5432/${DB_NAME}"
export FLYWAY_USER="${POSTGRES_USER}"
export FLYWAY_PASSWORD="${POSTGRES_PASSWORD}"
export FLYWAY_LOCATIONS="filesystem:/flyway/sql"
export FLYWAY_BASELINE_ON_MIGRATE="false"
export FLYWAY_OUT_OF_ORDER="false"
export FLYWAY_CONNECT_RETRIES="10"

HOST_DIR="$(pwd -W 2>/dev/null || pwd)"

exec docker run --rm \
  --network canvas-history-net \
  -e FLYWAY_URL -e FLYWAY_USER -e FLYWAY_PASSWORD \
  -e FLYWAY_LOCATIONS -e FLYWAY_BASELINE_ON_MIGRATE \
  -e FLYWAY_OUT_OF_ORDER -e FLYWAY_CONNECT_RETRIES \
  -v "${HOST_DIR}/db/migration:/flyway/sql" \
  "${FLYWAY_IMAGE}" "$SUB"
