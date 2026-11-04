#!/usr/bin/env bash
# r2_fetch_pleiades_gis.sh
# WB-002 P0收敛第二轮：用 HTTP Range 抓取 Pleiades GIS CSV 前段样本（不下载全量）
# 用法: bash code/p0/wb-002-tools/r2_fetch_pleiades_gis.sh
# 输出: 设计资料/P0收敛/WB-002/sample_data_pleiades/
# 同时写 LOG.tsv（每个请求的 URL / Range / HTTP 状态 / 实际字节 / SHA256 / content-range / 抓取时间）

set -u

ROOT="E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory"
OUT="$ROOT/设计资料/P0收敛/WB-002/sample_data_pleiades"
BASE="https://raw.githubusercontent.com/isawnyu/pleiades.datasets/main/data/gis"
LOG="$OUT/FETCH_LOG.tsv"

mkdir -p "$OUT"
: > "$LOG"
printf "file\turl\trange_requested\thttp_status\tbytes_received\trange_returned\tcontent_type\tsha256\tfetched_at_utc\tlocal_path\n" >> "$LOG"

# name|范围（字节区间，闭区间）
ITEMS=(
  "places.csv|0-1048575"
  "names.csv|0-1048575"
  "location_points.csv|0-1048575"
  "time_periods.csv|0-999999"     # 全量仅 40909 B，用足够大的上界即全取
  "connections.csv|0-524287"
)

TOTAL=0
for item in "${ITEMS[@]}"; do
  NAME="${item%%|*}"
  RANGE="${item##*|}"
  LOCAL="$OUT/${NAME}.range-${RANGE}"
  TMP="$LOCAL.part"
  TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  # -sS 静默但报错；-w 输出 http_code；-D 保存响应头以便读 Content-Range
  HDR="$TMP.hdr"
  CODE=$(curl -sS -L --max-time 120 \
        -H "Range: bytes=${RANGE}" \
        -H "Accept-Encoding: identity" \
        -D "$HDR" \
        -o "$TMP" \
        -w '%{http_code}' \
        "$BASE/$NAME" 2>"$TMP.err")
  CURLRC=$?

  if [ $CURLRC -ne 0 ] || [ ! -s "$TMP" ]; then
    echo "FAIL $NAME curl_rc=$CURLRC $(cat "$TMP.err" 2>/dev/null)" >&2
    printf "%s\t%s\t%s\t%s\t0\t\t\t\t%s\tFAILED\n" "$NAME" "$BASE/$NAME" "$RANGE" "${CODE:-ERR}" "$TS" >> "$LOG"
    rm -f "$TMP" "$HDR" "$TMP.err"
    continue
  fi

  BYTES=$(wc -c < "$TMP" | tr -d ' ')
  TOTAL=$((TOTAL + BYTES))
  SHA=$(sha256sum "$TMP" | awk '{print $1}')
  CR=$(grep -i '^content-range:' "$HDR" | tr -d '\r' | sed 's/^[Cc]ontent-[Rr]ange:[[:space:]]*//' | tail -1)
  CT=$(grep -i '^content-type:' "$HDR" | tr -d '\r' | sed 's/^[Cc]ontent-[Tt]ype:[[:space:]]*//' | tail -1)

  mv "$TMP" "$LOCAL"
  rm -f "$HDR" "$TMP.err"

  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
    "$NAME" "$BASE/$NAME" "bytes=$RANGE" "$CODE" "$BYTES" "${CR:-none}" "${CT:-unknown}" "$SHA" "$TS" "sample_data_pleiades/$(basename "$LOCAL")" >> "$LOG"
  echo "OK   $NAME  http=$CODE  bytes=$BYTES  content-range=${CR:-none}"
done

echo "----- total downloaded bytes: $TOTAL -----"
