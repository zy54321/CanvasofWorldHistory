#!/usr/bin/env bash
# DEV 后端启动器（唯一允许连接 canvas_history_dev 的入口）
#
# 与 run-dev.sh / run-prod.sh 的区别：
#   run-dev.sh   —— 通用启动器，读 ../.env（生产配置），供 run-prod.sh 复用
#   run-prod.sh  —— 生产启动器，只连 canvas_history
#   run-dev-api.sh（本文件）—— DEV 专用，只读 ../.env.dev，只连 canvas_history_dev
#
# 三道断言，任何一条不满足就拒绝启动，不静默降级：
#   1. 配置文件必须是 .env.dev（不存在就退出，绝不回退到生产 .env）；
#   2. 目标库名必须是 canvas_history_dev；
#   3. 写白名单必须且只能包含 canvas_history_dev —— 防止有人顺手把生产库放进来。
set -euo pipefail

cd "$(dirname "$0")"

EXPECTED_DB="canvas_history_dev"
DEV_ENV="../.env.dev"
JAR="target/canvas-history-api.jar"

# ---------------------------------------------------------------- 1. 前置检查
if [ ! -f "$DEV_ENV" ]; then
  echo "拒绝启动：未找到 $DEV_ENV" >&2
  echo "        DEV 启动器不会回退到生产配置 ../.env。" >&2
  exit 2
fi

if [ ! -f "$JAR" ]; then
  echo "未找到 $JAR，请先构建：mvn -DskipTests package" >&2
  exit 1
fi

# ---------------------------------------------------------------- 2. 加载 DEV 配置
# 只加载 .env.dev；外部显式传入的值仍然优先，并且同样要过断言 ——
# 否则「命令行传 canvas_history 当白名单」会被 .env.dev 的值悄悄覆盖，断言形同虚设。
_OVR_DB_NAME="${DB_NAME-}"
_OVR_API_PORT="${API_PORT-}"
_OVR_WRITE="${DB_WRITE_ALLOWED_DATABASES-}"

# shellcheck disable=SC1091
set -a; . "$DEV_ENV"; set +a

if [ -n "$_OVR_DB_NAME" ]; then DB_NAME="$_OVR_DB_NAME"; fi
if [ -n "$_OVR_API_PORT" ]; then API_HOST_PORT="$_OVR_API_PORT"; fi
if [ -n "$_OVR_WRITE" ]; then DB_WRITE_ALLOWED_DATABASES="$_OVR_WRITE"; fi

DB_NAME="${DB_NAME:-${POSTGRES_DB:-}}"

# ---------------------------------------------------------------- 3. 断言一：库名
if [ "$DB_NAME" != "$EXPECTED_DB" ]; then
  echo "拒绝启动：DEV 启动器只允许连接 ${EXPECTED_DB}，收到 '${DB_NAME}'" >&2
  echo "        若要连接其它库，请用 run-dev.sh 并自行承担风险。" >&2
  exit 2
fi

# ---------------------------------------------------------------- 4. 断言二：白名单
ALLOWED="${DB_WRITE_ALLOWED_DATABASES:-}"
if [ "$ALLOWED" != "$EXPECTED_DB" ]; then
  echo "拒绝启动：DEV 写白名单必须是 '${EXPECTED_DB}'，收到 '${ALLOWED}'" >&2
  echo "        DEV 实例不得对任何其它库（尤其 canvas_history）开放写入。" >&2
  exit 2
fi

# ---------------------------------------------------------------- 5. 断言三：容器就绪
# 注意必须精确比较：`unhealthy` / `starting` 都含 "healthy" 子串，grep 会误判。
DB_STATUS="$(docker inspect canvas-history-db-dev --format '{{.State.Health.Status}}' 2>/dev/null || echo missing)"
if [ "$DB_STATUS" != "healthy" ]; then
  echo "拒绝启动：DEV 数据库容器 canvas-history-db-dev 状态为 '${DB_STATUS}'，未就绪。" >&2
  echo "        请先执行：docker compose -f docker-compose.dev.yml --env-file .env.dev up -d" >&2
  exit 2
fi

# ---------------------------------------------------------------- 6. 启动
export DB_NAME
export DB_URL="jdbc:postgresql://127.0.0.1:${DB_HOST_PORT:-15433}/${DB_NAME}"
export DB_USER="${POSTGRES_USER}"
export DB_PASSWORD="${POSTGRES_PASSWORD}"
export API_PORT="${API_HOST_PORT:-8089}"
export DB_WRITE_ALLOWED_DATABASES="$ALLOWED"

# IDE/工具注入的 SERVER__PORT 会让 Spring 松散绑定成 server.port，显式清掉
unset SERVER__PORT SERVER_PORT 2>/dev/null || true

echo "DEV API 启动：http://127.0.0.1:${API_PORT}  db=${DB_NAME}@127.0.0.1:${DB_HOST_PORT:-15433}  可写（白名单：${ALLOWED}）"

exec java -jar "$JAR" --server.port="${API_PORT}"
