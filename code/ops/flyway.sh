#!/usr/bin/env bash
# Flyway 执行包装（Docker，固定版本，凭证不进命令行）
#
# 用法：
#   ops/flyway.sh <数据库名> <flyway 子命令> [参数...]
#
# 例：
#   ops/flyway.sh canvas_history_migrationcheck migrate
#   ops/flyway.sh canvas_history info
#
# 说明：
#   - 迁移脚本目录固定为 backend/src/main/resources/db/migration（Spring Boot 复用同一套）。
#   - 凭证从 code/.env 读出后经 `docker run -e VAR`（只传变量名）注入容器，
#     不出现在命令行、不写进镜像、不落日志。
#   - 显式 baselineOnMigrate=false：禁止用基线方式绕过真实迁移。
set -euo pipefail

cd "$(dirname "$0")/.."

if [ $# -lt 2 ]; then
  echo "用法: $0 <数据库名> <flyway 子命令> [参数...]" >&2
  exit 2
fi

# shellcheck disable=SC1091
set -a; . ./.env; set +a

DB_NAME="$1"; shift

FLYWAY_IMAGE="${FLYWAY_IMAGE:-flyway/flyway:13.12.0-alpine}"

export FLYWAY_URL="jdbc:postgresql://db:5432/${DB_NAME}"
export FLYWAY_USER="${POSTGRES_USER}"
export FLYWAY_PASSWORD="${POSTGRES_PASSWORD}"
export FLYWAY_LOCATIONS="filesystem:/flyway/sql"
export FLYWAY_BASELINE_ON_MIGRATE="false"
export FLYWAY_CONNECT_RETRIES="10"
export FLYWAY_OUT_OF_ORDER="false"

# Git Bash 下 pwd -W 给出 E:/... 形式，Docker Desktop 可直接挂载
HOST_DIR="$(pwd -W 2>/dev/null || pwd)"

exec docker run --rm \
  --network canvas-history-net \
  -e FLYWAY_URL -e FLYWAY_USER -e FLYWAY_PASSWORD \
  -e FLYWAY_LOCATIONS -e FLYWAY_BASELINE_ON_MIGRATE \
  -e FLYWAY_CONNECT_RETRIES -e FLYWAY_OUT_OF_ORDER \
  -v "${HOST_DIR}/backend/src/main/resources/db/migration:/flyway/sql" \
  "${FLYWAY_IMAGE}" "$@"
