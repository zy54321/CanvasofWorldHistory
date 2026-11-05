#!/usr/bin/env bash
# 正式环境启动脚本（V1.0）
#
# 与 run-dev.sh 的区别只有一件事：显式把**唯一正式库**放进写白名单。
# 其它一律不动 —— 连接地址、账号、密码仍从 ../.env 读，脚本里不出现任何凭证。
#
#   bash run-prod.sh                 # 正式环境：db=canvas_history，可写（白名单仅此一库）
#   bash run-dev.sh                  # 开发/只读：白名单为空 → writeAllowed=false，写操作 403
#
# 为什么要有这个脚本：.env 里 DB_WRITE_ALLOWED_DATABASES 留空是"默认只读"的安全默认值，
# 但正式环境必须可写。把"可写"这件事固定在脚本里，比让每个人记住一条环境变量可靠。
#
# 安全约束（任何一条不满足就拒绝启动，不静默降级）：
#   1. 库名只能是 canvas_history；
#   2. 写白名单只能是 canvas_history —— 传入空值以外的其它值一律拒绝，
#      防止有人用这个脚本顺手把测试库也放开；
#   3. 启动后自动核对 health 的 database 与 write-policy 的 writeAllowed，
#      不一致就杀掉子进程并返回非 0（避免"以为起了可写实例，其实起了只读"）。
set -euo pipefail

cd "$(dirname "$0")"

TARGET_DB="canvas_history"
HEALTH_PATH="/api/v1/meta/health"
POLICY_PATH="/api/v1/meta/write-policy"
READY_TIMEOUT="${READY_TIMEOUT:-90}"

# ---------------------------------------------------------------- 1. 参数校验
REQ_DB="${DB_NAME:-$TARGET_DB}"
if [ "$REQ_DB" != "$TARGET_DB" ]; then
  echo "拒绝启动：本脚本只服务正式库 ${TARGET_DB}，收到 DB_NAME=${REQ_DB}" >&2
  echo "        其它库请用 run-dev.sh 显式指定，不要把正式脚本当通用启动器。" >&2
  exit 2
fi

REQ_WRITE="${DB_WRITE_ALLOWED_DATABASES:-$TARGET_DB}"
if [ "$REQ_WRITE" != "$TARGET_DB" ]; then
  echo "拒绝启动：写白名单只能是 ${TARGET_DB}，收到 '${REQ_WRITE}'" >&2
  echo "        本脚本不允许把白名单扩大到任何其它数据库。" >&2
  exit 2
fi

if [ ! -f target/canvas-history-api.jar ]; then
  echo "未找到 target/canvas-history-api.jar，请先构建：mvn -DskipTests package" >&2
  exit 1
fi

# 交给 run-dev.sh 的"外部显式值"：它会优先于 .env 生效
export DB_NAME="$TARGET_DB"
export DB_WRITE_ALLOWED_DATABASES="$TARGET_DB"

# ---------------------------------------------------------------- 2. 启动
# 端口与库名由 run-dev.sh 统一解析（它负责读 .env、拼 DB_URL、清 SERVER__PORT）
API_PORT_RESOLVED="${API_PORT:-$(grep -E '^API_HOST_PORT=' ../.env 2>/dev/null | cut -d= -f2)}"
API_PORT_RESOLVED="${API_PORT_RESOLVED:-8088}"
BASE="http://127.0.0.1:${API_PORT_RESOLVED}"

echo "启动正式环境：db=${TARGET_DB}  写白名单=${TARGET_DB}  端口=${API_PORT_RESOLVED}"

bash run-dev.sh &
CHILD=$!

cleanup() {
  if kill -0 "$CHILD" 2>/dev/null; then
    kill "$CHILD" 2>/dev/null || true
    wait "$CHILD" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- 3. 启动后自检
json_field() { # json_field <文本> <字段名>
  printf '%s' "$1" | sed -n "s/.*\"$2\":\"\([^\"]*\)\".*/\1/p"
}

ok=0
for _ in $(seq 1 "$READY_TIMEOUT"); do
  HEALTH="$(curl -s -m 2 "${BASE}${HEALTH_PATH}" || true)"
  if printf '%s' "$HEALTH" | grep -q '"status":"ok"'; then ok=1; break; fi
  if ! kill -0 "$CHILD" 2>/dev/null; then break; fi
  sleep 1
done

if [ "$ok" -ne 1 ]; then
  echo "启动失败：${READY_TIMEOUT}s 内 health 未就绪" >&2
  exit 1
fi

DB_SEEN="$(json_field "$HEALTH" database)"
POLICY="$(curl -s -m 3 "${BASE}${POLICY_PATH}" || true)"
WRITE_SEEN="$(printf '%s' "$POLICY" | sed -n 's/.*"writeAllowed":\(true\|false\).*/\1/p')"
ALLOWED_SEEN="$(printf '%s' "$POLICY" | sed -n 's/.*"allowedDatabases":\[\([^]]*\)\].*/\1/p')"

echo "自检：health.database=${DB_SEEN}  writeAllowed=${WRITE_SEEN}  allowedDatabases=[${ALLOWED_SEEN}]"

fail=""
[ "$DB_SEEN" = "$TARGET_DB" ] || fail="health.database=${DB_SEEN}，期望 ${TARGET_DB}"
[ "$WRITE_SEEN" = "true" ] || fail="${fail} writeAllowed=${WRITE_SEEN}，期望 true"
case "$ALLOWED_SEEN" in
  "\"${TARGET_DB}\"") : ;;
  *) fail="${fail} allowedDatabases=[${ALLOWED_SEEN}]，期望 [\"${TARGET_DB}\"]" ;;
esac

if [ -n "$fail" ]; then
  echo "自检未通过：${fail}" >&2
  echo "已停止刚启动的进程，避免「以为可写、实际只读」的静默偏差。" >&2
  exit 1
fi

echo "正式环境已就绪：${BASE}"
echo "前端启动：cd frontend && npx vite --host 127.0.0.1   → http://127.0.0.1:5180/"
echo "（Ctrl-C 停止）"

wait "$CHILD"
