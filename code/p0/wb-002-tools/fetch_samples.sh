#!/usr/bin/env bash
# WB-002 历史地理数据源小样本获取脚本（可复现）
# 用法： bash code/p0/wb-002-tools/fetch_samples.sh
# 约束： 单文件 < 10MB，总下载 < 50MB，不做全量快照下载。
# 说明： 每一行 manifest 记录 抓取时间(UTC)/来源/URL/HTTP状态/字节数/SHA256/本地路径。
#        MCGD 主文件 30.5MB 超过单文件上限，因此只取 Range 前缀 65536 字节（HTTP 206）。

set -u
ROOT="E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory"
OUT="$ROOT/设计资料/P0验证/WB-002/sample_data"
MAN="$OUT/MANIFEST.tsv"
PROBE="$OUT/PROBES.tsv"
WHG_UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

mkdir -p "$OUT/pleiades/places" "$OUT/pleiades/gis_vocab" "$OUT/pleiades/datasets_docs" \
         "$OUT/whg/api/place" "$OUT/whg/api" "$OUT/chgis/api" "$OUT/mcgd"
printf "fetched_utc\tsource\turl\thttp_status\tbytes\tsha256\tlocal_path\n" > "$MAN"
printf "fetched_utc\tsource\turl\tmethod\trequest_note\thttp_status\tresponse_excerpt\n" > "$PROBE"

now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# fetch <source> <url> <dest> [ua] [range]
fetch() {
  local src="$1" url="$2" dest="$3" ua="${4:-WB-002-research/1.0}" rng="${5:-}"
  local code size try
  for try in 1 2 3; do
    if [ -n "$rng" ]; then
      code=$(curl -sSL -A "$ua" -r "$rng" -o "$dest" -w '%{http_code}' "$url")
    else
      code=$(curl -sSL -A "$ua" -o "$dest" -w '%{http_code}' "$url")
    fi
    case "$code" in 200|206) break ;; esac
    echo "  ! 第 $try 次尝试返回 $code，重试： $url"
  done
  size=$(wc -c < "$dest" | tr -d ' ' 2>/dev/null || echo 0)
  [ -f "$dest" ] || { size=0; code="${code}-NOFILE"; }
  local sha; sha=$(sha256sum "$dest" | cut -d' ' -f1)
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$(now)" "$src" "$url" "$code" "$size" "$sha" "${dest#$OUT/}" >> "$MAN"
  printf "  [%s] %s (%s bytes) -> %s\n" "$code" "$url" "$size" "${dest#$OUT/}"
}

# probe <source> <url> <method> <note>
probe() {
  local src="$1" url="$2" method="${3:-GET}" note="${4:-}" ua="${5:-$WHG_UA}"
  local body="$OUT/.probe.tmp" code
  if [ "$method" = "POST" ]; then
    code=$(curl -sSL -A "$ua" -X POST -H "Content-Type: application/json" \
      -d '{"queries":{"q0":{"query":"Babylon","limit":3}}}' -o "$body" -w '%{http_code}' "$url")
  else
    code=$(curl -sSL -A "$ua" -o "$body" -w '%{http_code}' "$url")
  fi
  local ex; ex=$(head -c 180 "$body" | tr '\t\n' '  ')
  case "$ex" in
    *anubis*|*Anubis*) ex="[反爬挑战页 Anubis] $ex" ;;
  esac
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$(now)" "$src" "$url" "$method" "$note" "$code" "$ex" >> "$PROBE"
  printf "  PROBE [%s] %s %s\n" "$code" "$method" "$url"
}

echo "== Pleiades：4 条真实 place 记录（含点位/区域/多名称/多 connection） =="
fetch pleiades "https://pleiades.stoa.org/places/423025/json" "$OUT/pleiades/places/423025.json"   # Roma
fetch pleiades "https://pleiades.stoa.org/places/579885/json" "$OUT/pleiades/places/579885.json"   # Athenae
fetch pleiades "https://pleiades.stoa.org/places/893951/json" "$OUT/pleiades/places/893951.json"   # Babylon（有点位）
fetch pleiades "https://pleiades.stoa.org/places/912816/json" "$OUT/pleiades/places/912816.json"   # Babylonia（区域/标注线）

echo "== Pleiades：小型词表（字段取值域，非数据快照） =="
for f in name_types.csv association_certainty.csv transcription_accuracy.csv \
         transcription_completeness.csv archaeological_remains.csv place_types.csv; do
  fetch pleiades_vocab "https://raw.githubusercontent.com/isawnyu/pleiades.datasets/main/data/gis/$f" \
        "$OUT/pleiades/gis_vocab/$f"
done

echo "== Pleiades：官方文档与许可原文（引用依据） =="
fetch pleiades_docs "https://raw.githubusercontent.com/isawnyu/pleiades.datasets/main/README.md"        "$OUT/pleiades/datasets_docs/README.md"
fetch pleiades_docs "https://raw.githubusercontent.com/isawnyu/pleiades.datasets/main/LICENSE"          "$OUT/pleiades/datasets_docs/LICENSE_CC-BY-3.0.txt"
fetch pleiades_docs "https://raw.githubusercontent.com/isawnyu/pleiades.datasets/main/data/gis/README.md" "$OUT/pleiades/datasets_docs/gis_README.md"

echo "== WHG：API 文档快照（451 / 配额 / 命名空间依据） =="
fetch whg_docs "https://docs.whgazetteer.org/content/technical/apis.html" "$OUT/whg/whg_apis_docs.html" "$WHG_UA"

echo "== WHG：真实记录与来源注册表（legacy 公开端点，无需 token） =="
fetch whg "https://whgazetteer.org/api/place/169687/"         "$OUT/whg/api/place/169687.json" "$WHG_UA"
fetch whg "https://whgazetteer.org/api/place/169687-169688/"  "$OUT/whg/api/place/169687-169688.json" "$WHG_UA"
fetch whg "https://whgazetteer.org/api/sources/"              "$OUT/whg/api/sources.json" "$WHG_UA"

echo "== WHG：Entity API 的 LPF v1.1 真实记录（gn:/tgn: 命名空间实测无需 token） =="
fetch whg "https://whgazetteer.org/entity/place:gn:3169070/api"  "$OUT/whg/api/place/gn_3169070_roma.json"    "$WHG_UA"
fetch whg "https://whgazetteer.org/entity/place:gn:1790630/api"  "$OUT/whg/api/place/gn_1790630_xian.json"    "$WHG_UA"
fetch whg "https://whgazetteer.org/entity/place:gn:1816670/api"  "$OUT/whg/api/place/gn_1816670_beijing.json" "$WHG_UA"
fetch whg "https://whgazetteer.org/entity/place:gn:98182/api"    "$OUT/whg/api/place/gn_98182_baghdad.json"   "$WHG_UA"
fetch whg "https://whgazetteer.org/entity/place:tgn:7011781/api" "$OUT/whg/api/place/tgn_7011781_london.json" "$WHG_UA"

echo "== CHGIS：Dataverse 元数据与最小样本文件 =="
fetch chgis_meta "https://dataverse.harvard.edu/api/dataverses/chgis_v6/contents"                              "$OUT/chgis/api/dataverse_chgis_v6_contents.json"
fetch chgis_meta "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/FDLFJ3" "$OUT/chgis/api/dataset_FDLFJ3_EULA.json"
fetch chgis_meta "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/WW1PD6" "$OUT/chgis/api/dataset_WW1PD6_pref_pts.json"
fetch chgis_meta "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/Q9VOF5" "$OUT/chgis/api/dataset_Q9VOF5_cnty_pts.json"
fetch chgis_meta "https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/I0Q7SM" "$OUT/chgis/api/dataset_I0Q7SM_pref_pgn.json"

fetch chgis "https://dataverse.harvard.edu/api/access/datafile/2970286" "$OUT/chgis/v6_time_pref_pts_utf_wgs84.zip"
fetch chgis "https://dataverse.harvard.edu/api/access/datafile/3048165" "$OUT/chgis/v6_time_cnty_pts_utf_wgs84.zip"
fetch chgis "https://dataverse.harvard.edu/api/access/datafile/3048161" "$OUT/chgis/CHGIS_V6_README.txt"
fetch chgis "https://dataverse.harvard.edu/api/access/datafile/2966674" "$OUT/chgis/README_DATA_DICTIONARY.txt"
fetch chgis "https://dataverse.harvard.edu/api/access/datafile/2966673" "$OUT/chgis/CHGIS_data_dictionary.zip"

echo "== MCGD：Zenodo 记录元数据 + 主文件 Range 前缀（206，不做全量下载） =="
fetch mcgd_meta "https://zenodo.org/api/records/22094815" "$OUT/mcgd/zenodo_record_22094815.json"
fetch mcgd "https://zenodo.org/api/records/22094815/files/MCGD_Data2026_08_25.csv/content" \
      "$OUT/mcgd/MCGD_Data2026_08_25.csv.range-0-65535.raw" "WB-002-research/1.0" "0-65535"

echo "== MCGD：从原始前缀派生「只含完整行」的干净样本 =="
python "$ROOT/code/p0/wb-002-tools/derive_mcgd_sample.py"

echo "== 访问性与许可探测（只记录 HTTP 状态，不保存正文） =="
probe pleiades "https://pleiades.stoa.org/places/89387/json" GET "基线候选 ID 89387(Babylon) 核验"
probe pleiades "https://pleiades.stoa.org/places/423025"     GET "HTML 页面是否被反爬挑战拦截"
probe pleiades "https://pleiades.stoa.org/search?q=Babylon"  GET "搜索页是否可用"
probe pleiades "https://pleiades.stoa.org/help/license"      GET "许可帮助页是否存在"
probe pleiades "https://pleiades.stoa.org/downloads"         GET "下载说明页"
probe whg "https://whgazetteer.org/suggest/entity?prefix=Babylon"     GET  "建议端点是否需 token"
probe whg "https://whgazetteer.org/entity/place:gn:745044/api"        GET  "gn: 命名空间 Entity API"
probe whg "https://whgazetteer.org/entity/place:169687/api"           GET  "whg 原生 ID 的 Entity API（对照）"
probe whg "https://whgazetteer.org/entity/dataset:14/api"             GET  "数据集实体是否需 token"
probe whg "https://whgazetteer.org/entity/place:chgis:1/api"          GET  "chgis 命名空间实体探测"
probe whg "https://whgazetteer.org/reconcile"                          POST "批量检索是否需 token"
probe whg "https://whgazetteer.org/api/place/search?q=Babylon"        GET  "legacy 搜索端点是否存在"
probe whg "https://whgazetteer.org/atlas/search/?q=Babylon"           GET  "Atlas 搜索是否开放"
probe chgis "https://dataverse.harvard.edu/api/search?q=*&subtree=chgis_v6_time&type=dataset" GET "搜索 API 可用性"

rm -f "$OUT/.probe.tmp"

echo
echo "manifest -> ${MAN#$ROOT/}"
echo "probes   -> ${PROBE#$ROOT/}"
