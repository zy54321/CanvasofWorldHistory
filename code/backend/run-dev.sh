#!/usr/bin/env bash
# 通用启动器（凭证从 ../.env 读取，不落源码）
#
# 目标库必须显式指定，没有默认值 —— 见下方 DB_NAME 检查。
#
# 日常请优先使用两个专用入口：
#   DEV ： bash run-dev-api.sh    （只读 .env.dev，强制 canvas_history_dev）
#   PROD： bash run-prod.sh       （强制 canvas_history，可写白名单仅此一库）
#
# 临时连某个库（例如测试库）时才直接用本脚本：
#   DB_NAME=canvas_history_m2check API_PORT=8089 \
#   DB_WRITE_ALLOWED_DATABASES=canvas_history_m2check bash run-dev.sh
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -f target/canvas-history-api.jar ]; then
  echo "未找到 target/canvas-history-api.jar，请先构建：mvn -DskipTests package" >&2
  exit 1
fi

# 外部显式指定的值优先于 .env（否则同一个脚本没法起测试实例）
_OVR_DB_NAME="${DB_NAME-}"
_OVR_WRITE="${DB_WRITE_ALLOWED_DATABASES-}"
_OVR_API_PORT="${API_PORT-}"

# shellcheck disable=SC1091
set -a; . ../.env; set +a

if [ -n "$_OVR_DB_NAME" ]; then DB_NAME="$_OVR_DB_NAME"; fi
if [ -n "$_OVR_WRITE" ]; then DB_WRITE_ALLOWED_DATABASES="$_OVR_WRITE"; fi
if [ -n "$_OVR_API_PORT" ]; then API_HOST_PORT="$_OVR_API_PORT"; fi

# 目标库必须由调用方显式给出。
#
# 历史问题：这里原本是 DB_NAME="${DB_NAME:-${POSTGRES_DB:-canvas_history}}"，
# 三级回退意味着「裸跑本脚本」会静默连上正式库 canvas_history。
# 现在改为：没有显式 DB_NAME 就拒绝启动。
#
# 正常调用方都不受影响：
#   - run-prod.sh 会在调用前 export DB_NAME=canvas_history；
#   - run-dev-api.sh（DEV 专用）不经过本脚本；
#   - 需要临时连某个库时，显式写 DB_NAME=<库名> bash run-dev.sh。
if [ -z "${DB_NAME-}" ]; then
  echo "拒绝启动：未指定 DB_NAME。" >&2
  echo "        本脚本是通用启动器，不再默认连接正式库 canvas_history。" >&2
  echo "" >&2
  echo "        DEV  开发环境：  bash run-dev-api.sh" >&2
  echo "        PROD 正式环境：  bash run-prod.sh" >&2
  echo "        其它临时库：    DB_NAME=<库名> bash run-dev.sh" >&2
  exit 2
fi

export DB_URL="jdbc:postgresql://127.0.0.1:${DB_HOST_PORT:-55432}/${DB_NAME}"
export DB_USER="${POSTGRES_USER}"
export DB_PASSWORD="${POSTGRES_PASSWORD}"
export API_PORT="${API_HOST_PORT:-8088}"
# 写白名单：.env 里留空即为「全库禁写」；只有显式列出的库名才允许写
export DB_WRITE_ALLOWED_DATABASES="${DB_WRITE_ALLOWED_DATABASES:-}"

# 宿主机环境里存在 SERVER__PORT（IDE/工具注入），Spring 松散绑定会把它当成 server.port，
# 这里显式清掉并用命令行参数钉住端口（命令行优先级最高）。
unset SERVER__PORT SERVER_PORT 2>/dev/null || true

if [ -n "$DB_WRITE_ALLOWED_DATABASES" ]; then
  WRITE_STATE="可写（白名单：${DB_WRITE_ALLOWED_DATABASES}）"
else
  WRITE_STATE="只读（写白名单为空）"
fi

echo "API 启动：http://127.0.0.1:${API_PORT}  db=${DB_NAME}  ${WRITE_STATE}"
exec java -jar target/canvas-history-api.jar --server.port="${API_PORT}"
