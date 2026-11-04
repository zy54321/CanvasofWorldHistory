#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
r2_build_field_mapping.py
WB-002 P0收敛 第二轮：生成修正版 FIELD_MAPPING.csv。
用 csv 模块写出，保证含逗号/引号/中文的 sample_value 被正确转义。

列（固定）:
  source, source_dataset, source_field, sample_value,
  target_table, target_field, transform_rule, time_semantics, confidence, evidence

time_semantics 取值域（本表使用）:
  exact            上下界即精确年份，可直接当起止年
  exact_or_bounded 依随附的 *RULE 字段决定是精确年还是时期边界（CHGIS BEG_RULE/END_RULE）
  tpq_taq          上下界是「不早于/不晚于」的约束，真实值可为区间内任一点
  bounded          来源给的是显式区间/时期边界，粒度即区间本身
  unknown          该字段无时间语义，或来源无任何时间信息
  n/a              非时间字段

用法（项目根目录下）:
  python code/p0/wb-002-tools/r2_build_field_mapping.py
"""
import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
OUT = os.path.join(ROOT, "设计资料", "P0收敛", "WB-002", "FIELD_MAPPING.csv")

COLS = ["source", "source_dataset", "source_field", "sample_value",
        "target_table", "target_field", "transform_rule",
        "time_semantics", "confidence", "evidence"]

R = []


def add(*a):
    assert len(a) == 10, a
    R.append(dict(zip(COLS, a)))


# =====================================================================
# PLEIADES —— 全部使用本轮实测的 CSV 字段名（不是 JSON API 字段名）
# 证据统一指向：sample_data_pleiades/<file>.range-* 的物理行号（表头=第1行）
# =====================================================================
P = "Pleiades"
PS = "pleiades.datasets / data/gis (main branch)"

# ---- places.csv : 11 字段
add(P, PS + " :: places.csv", "id", "993",
    "places", "source_native_id",
    "原样转字符串；与 names/locations/connections 的 place_id 关联；不要与 names.csv 的 slug 型 id 混用",
    "n/a", "verified",
    "places.csv.range-0-1048575 行1 表头 + 行2 id='993'；README.md(gis) L163-170 定义 id 唯一性限于单文件，全局唯一须用 uri")
add(P, PS + " :: places.csv", "uri", "https://pleiades.stoa.org/places/993",
    "places", "uri", "原样保留；作为全局唯一标识", "n/a", "verified",
    "places.csv.range-0-1048575 行2 uri='https://pleiades.stoa.org/places/993'")
add(P, PS + " :: places.csv", "title", "Gallia",
    "places", "title", "原样保留为地点主标题；注意这是编辑者给的标题，不等于任一 name 形式",
    "n/a", "verified",
    "places.csv.range-0-1048575 行2 title='Gallia'")
add(P, PS + " :: places.csv", "description", "An ancient region covering a large part of southwestern Europe ...",
    "places", "description", "去掉首尾空白；纯文本", "n/a", "verified",
    "places.csv.range-0-1048575 行2 description")
add(P, PS + " :: places.csv", "details", "<p>The Barrington Atlas Directory notes: FRA</p>",
    "places", "details_html", "**可能含 HTML 标签**，入库前须 sanitize 再渲染；不要当纯文本直接输出",
    "n/a", "verified",
    "places.csv.range-0-1048575 行2 details；README.md(gis) L148-155 明示 'This field may include HTML tags'")
add(P, PS + " :: places.csv", "provenance", "Barrington Atlas: BAtlas 1 D1 Gallia",
    "places", "provenance", "原样保留，用于溯源；切片内大量为 'Barrington Atlas: BAtlas ...' 与 'Pleiades'",
    "n/a", "verified",
    "places.csv.range-0-1048575 行2 provenance")
add(P, PS + " :: places.csv", "created", "2021-11-14T03:44:08Z",
    "source_records", "source_created_at",
    "解析为 UTC 时间戳（ISO 8601，带 Z）", "n/a", "verified",
    "places.csv.range-0-1048575 行2 created；README.md(gis) L133-140")
add(P, PS + " :: places.csv", "representative_latitude", "46.360953305773286",
    "locations", "lat",
    "**纬度 Y**。WGS84 有符号十进制度。字段名为全称，不是 repr_lat，也不要与 bounding_box_wkt 内的轴序混淆",
    "n/a", "verified",
    "places.csv.range-0-1048575 行2；行3 id=999909607 lat=40.7500099 而 bbox WKT 首点='14.4895058 40.7500099'，证明本列是纬度")
add(P, PS + " :: places.csv", "representative_longitude", "1.6706144893053327",
    "locations", "lon",
    "**经度 X**。WGS84 有符号十进制度。⚠️ gis_README L243 的释义文字误写为 'A latitude coordinate'，以实测取值为准",
    "n/a", "verified",
    "places.csv.range-0-1048575 行2；行1680 id=912816 lon=45.49540677142205（两河流域），与 places/912816.json reprPoint=[45.495,31.628] 的 lon 位一致")
add(P, PS + " :: places.csv", "bounding_box_wkt", "POLYGON ((9.6708805 31.937048, 9.6708805 51.9019, -19.665682 51.9019, -19.665682 31.937048, 9.6708805 31.937048))",
    "places", "bbox_wkt",
    "WKT 内部为 **X Y = 经度 纬度**，与 representative_latitude/longitude 两列顺序相反，解析后须互换再对齐；类型固定为 POLYGON",
    "n/a", "verified",
    "places.csv.range-0-1048575 行2/行3/行1680；README.md(gis) L111-117")
add(P, PS + " :: places.csv", "location_precision", "rough",
    "places", "location_precision",
    "枚举 {precise, rough}；切片内分布 precise=2045 / rough=598，无第三值；'rough' 的 representative point 可能仅为大包围盒质心",
    "n/a", "verified",
    "places.csv.range-0-1048575；README.md(gis) L16-20、L180-188")
add(P, PS + " :: places.csv", "representative_latitude (空值)", "",
    "places", "has_geometry",
    "为空时置 has_geometry=false；切片内 327/2643 为空，且 bounding_box_wkt 同为空的正是同一批 327 行 → 这批地点完全无法上图",
    "n/a", "verified",
    "places.csv.range-0-1048575：representative_latitude 空 327 行、bounding_box_wkt 空 327 行，行集合相同")
add(P, PS + " :: places.csv 【缺失字段】", "feature_type / placeTypes", "",
    "places", "place_type",
    "**places.csv 无此字段**。须 places.csv:id ⋈ places_place_types.csv ⋈ place_types.csv:key。后两文件的字段名本轮未实测",
    "n/a", "documented_only",
    "places.csv.range-0-1048575 行1 表头（11 字段，无 feature_type）；README.md(gis) L40 仅文字描述 join 方式。**places_place_types.csv 未取样本**")
add(P, PS + " :: places.csv 【缺失字段】", "year_after_which / year_before_which", "",
    "places", "(不可用)",
    "**places.csv 没有任何时间字段**。README.md(gis) L305/L313 的 'Applies to: places.csv' 与实测不符。地点级时间必须由 locations + names 派生，并标 time_basis='derived_tpq_taq'",
    "unknown", "verified",
    "places.csv.range-0-1048575 行1 表头 11 字段逐项检查，min_date/max_date/repr_lat/repr_lon/year_after_which/year_before_which 全部不存在")

# ---- names.csv : 19 字段
N = PS + " :: names.csv"
add(P, N, "id", "gallia",
    "names", "source_native_id",
    "**names.csv 的 id 是 slug（切片内 4579/4579 非纯数字）**，不是数字；不可用它 join 到 places，必须用 place_id",
    "n/a", "verified",
    "names.csv.range-0-1048575 行2 id='gallia' uri='https://pleiades.stoa.org/places/993/gallia'")
add(P, N, "place_id", "993",
    "names", "place_id",
    "**外键**：join 到 places.source_native_id。数值字符串", "n/a", "verified",
    "names.csv.range-0-1048575 行2 place_id='993'；README.md(gis) L218-224")
add(P, N, "romanized_form_1", "Gallia",
    "names", "name_text",
    "**这是「名字」的主取值**。切片内空值率 0/4579。JSON API 中对应 names[].romanized —— **CSV 叫 romanized_form_1，不同名**",
    "n/a", "verified",
    "names.csv.range-0-1048575 行2 romanized_form_1='Gallia'；对照 places/912816.json names[0].romanized='Karduniaš'。README.md(gis) L248-255")
add(P, N, "title", "Gallia",
    "names", "name_text（冗余校验）",
    "**切片内 title 与 romanized_form_1 100% 相同（4579/4579）**，属冗余列；可与 romanized_form_1 互为校验，不必单独建列",
    "n/a", "verified",
    "names.csv.range-0-1048575：title==romanized_form_1 计 4579/4579")
add(P, N, "romanized_form_2", "(空)",
    "names", "name_variant_2",
    "备用转写；为空则跳过。切片内多数为空", "n/a", "verified",
    "names.csv.range-0-1048575 行2 romanized_form_2=''；README.md(gis) L256-262")
add(P, N, "romanized_form_3", "(空)",
    "names", "name_variant_3",
    "备用转写；为空则跳过", "n/a", "verified",
    "names.csv.range-0-1048575 行2；README.md(gis) L263-269")
add(P, N, "attested_form", "Ἁρμόδιος καὶ Ἀριστογείτων",
    "names", "name_original_script",
    "原文字形（Unicode）。JSON API 中对应 names[].attested —— CSV 叫 attested_form。可为空，**不可作为显示名**",
    "n/a", "verified",
    "names.csv.range-0-1048575 行24 attested_form='Ἁρμόδιος καὶ Ἀριστογείτων' romanized_form_1='Harmódios kaì Aristogeítōn' lang='grc'；README.md(gis) L104-110")
add(P, N, "language_tag", "grc",
    "names", "language_tag",
    "BCP 47 语言标签，对应 languages_and_scripts.csv。**切片内 2076/4579（45.3%）为空**",
    "n/a", "verified",
    "names.csv.range-0-1048575：空 2076/4579；README.md(gis) L171-179")
add(P, N, "name_type", "geographic",
    "names", "name_type",
    "**存的是词表 key（slug）不是 term**。须 join gis_vocab/name_types.csv:key 取中文/人话。切片内取值域 {geographic 4243, associated_modern 173, ethnic 115, label 40, undefined 5, unknown 3}，全部命中词表无越界",
    "n/a", "verified",
    "names.csv.range-0-1048575 取值分布；对照 gis_vocab/name_types.csv（本地全文，6 行 key/term/definition/same_as/uri）")
add(P, N, "association_certainty", "certain",
    "names", "association_certainty",
    "词表 slug；切片内 {certain 4306, less-certain 263, uncertain 10}。用于'这个名称是否确实指这个地点'",
    "n/a", "verified",
    "names.csv.range-0-1048575；词表 gis_vocab/association_certainty.csv")
add(P, N, "transcription_accuracy", "accurate",
    "names", "transcription_accuracy",
    "词表 slug；切片内 {accurate 4543, inaccurate 36}", "n/a", "verified",
    "names.csv.range-0-1048575；词表 gis_vocab/transcription_accuracy.csv")
add(P, N, "transcription_completeness", "complete",
    "names", "transcription_completeness",
    "词表 slug；切片内 {complete 4530, reconstructable 47, non-reconstructable 2}", "n/a", "verified",
    "names.csv.range-0-1048575；词表 gis_vocab/transcription_completeness.csv")
add(P, N, "year_after_which", "-550",
    "names", "in_use_from_year",
    "**不可直接当「名称启用年」**。这是 TPQ（terminus post quem）：该名称形式被使用的时间**不早于**此年。入库必须同时写 time_bound_type='tpq_taq'。负数=BCE，跨系统换算须 astro_year = year+1 if year<0",
    "tpq_taq", "verified",
    "names.csv.range-0-1048575 行24 yaw='-550'；README.md(gis) L300-307 原文 'terminus post quem'；切片内区间宽度 median=400 年、仅 3/4125 行窄于 50 年")
add(P, N, "year_before_which", "300",
    "names", "in_use_to_year",
    "**不可直接当「名称停用年」**。这是 TAQ（terminus ante quem）：该名称形式被使用的时间**不晚于**此年。入库写 time_bound_type='tpq_taq'",
    "tpq_taq", "verified",
    "names.csv.range-0-1048575 行24 ybw='300'；README.md(gis) L308-314 原文 'terminus ante quem'；宽度 median=400 年")
add(P, N, "year_after_which + year_before_which 【空值】", "",
    "names", "time_bound_type",
    "两列同时为空 → time_bound_type='unknown'，时间窗置 NULL，不得用 0 或当年填充。切片内两者皆空 454/4579（9.9%）",
    "unknown", "verified",
    "names.csv.range-0-1048575：yaw 空 454、ybw 空 454，且为同一批 454 行")
add(P, N, "year_after_which 与 year_before_which 【相等】", "1500 / 1500",
    "names", "time_bound_type",
    "TAQ==TPQ 的退化情形（切片内仅 2 条），应标 time_bound_type='bounded' 而非 'exact'，避免被读成'精确到某一年'",
    "bounded", "verified",
    "names.csv.range-0-1048575 行1796 place_id=932479 'Catife' yaw=ybw=1500；行2042 place_id=922627 'Boxar' yaw=ybw=1500")

# ---- location_points.csv : 16 字段
L = PS + " :: location_points.csv"
add(P, L, "id", "osm-location-casa-dei-ceii",
    "locations", "source_native_id",
    "slug，非数字；唯一性限于本文件", "n/a", "verified",
    "location_points.csv.range-0-1048575 行2 id='osm-location-casa-dei-ceii'")
add(P, L, "place_id", "999909607",
    "locations", "place_id",
    "**外键**：1 place : N locations（切片内 place_id=92147 挂 7 条）。不可假设一对一",
    "n/a", "verified",
    "location_points.csv.range-0-1048575 行2 place_id='999909607'；行1590-1596 均 place_id='92147'")
add(P, L, "geometry_wkt", "POINT (14.4895058 40.7500099)",
    "locations", "lon",
    "**本表唯一坐标载体**。解析 WKT 'POINT (lon lat)'：第 1 个数=经度 X，第 2 个=纬度 Y。**注意存在 'POINT Z (x y z)' 共 1 条，须容忍并丢弃 Z**。表内无 repr_lat/repr_lon/lat/lon 任何一列",
    "n/a", "verified",
    "location_points.csv.range-0-1048575 行1 表头 16 字段（无 lat/lon 列）；行2 geometry_wkt='POINT (14.4895058 40.7500099)'；前缀统计 {POINT:2459, POINT Z:1}")
add(P, L, "geometry_wkt 【纬度位】", "40.7500099",
    "locations", "lat",
    "同上，取 WKT 第 2 个数值为纬度 Y", "n/a", "verified",
    "location_points.csv.range-0-1048575 行2/行3/行4")
add(P, L, "location_precision", "precise",
    "locations", "location_precision",
    "枚举 {precise, rough}。**本表切片内 2460/2460 全为 precise**（点几何按定义即 precise）；判'粗略定位'须回看 places.csv.location_precision 或取 polygons/linestrings",
    "n/a", "verified",
    "location_points.csv.range-0-1048575：Counter({'precise': 2460})")
add(P, L, "accuracy_radius", "20.0",
    "locations", "accuracy_radius_m",
    "单位=**米**。对应 JSON API 的 accuracy_value（**不同名**）。切片内非空 2459/2460",
    "n/a", "verified",
    "location_points.csv.range-0-1048575 行2 accuracy_radius='20.0'；对照 places/912816.json locations[0].accuracy_value=1860.0；README.md(gis) L81-87")
add(P, L, "accuracy_assessment_uri", "https://pleiades.stoa.org/features/metadata/generic-osm-accuracy-assessment",
    "locations", "accuracy_source_uri",
    "原样保留；对应 JSON API 的 accuracy。切片内非空 2459/2460", "n/a", "verified",
    "location_points.csv.range-0-1048575 行2；README.md(gis) L60-66")
add(P, L, "archaeological_remains", "unknown",
    "locations", "archaeological_remains",
    "词表 slug；切片内 {unknown 2019, substantive 204, traces 133, notvisible 50, notapplicable 45, none 6, restored 3}",
    "n/a", "verified",
    "location_points.csv.range-0-1048575；词表 gis_vocab/archaeological_remains.csv")
add(P, L, "association_certainty", "certain",
    "locations", "association_certainty",
    "词表 slug；切片内 {certain 2214, uncertain 153, less-certain 93}。表示'这个坐标确实指这个地点'的把握",
    "n/a", "verified",
    "location_points.csv.range-0-1048575")
add(P, L, "year_after_which", "-30",
    "locations", "valid_from_year",
    "**位置有效期的 TPQ**，不是'地点建于该年'。入库写 time_bound_type='tpq_taq'。切片内非空 1884/2460（76.6%）",
    "tpq_taq", "verified",
    "location_points.csv.range-0-1048575 行2 yaw='-30'；README.md(gis) L300-307；切片内位置区间宽度 median=670 年、0 条窄于 50 年")
add(P, L, "year_before_which", "300",
    "locations", "valid_to_year",
    "**位置有效期的 TAQ**。写 time_bound_type='tpq_taq'。区间可整体落在 BCE（行4: -550 → -30）",
    "tpq_taq", "verified",
    "location_points.csv.range-0-1048575 行2 ybw='300'、行4 yaw='-550' ybw='-30'")
add(P, L, "year_after_which + year_before_which 【空值】", "",
    "locations", "time_bound_type",
    "两列皆空 → 'unknown'。切片内空 576/2460。交叉证据：places/893951.json locations[0].start/end 均为 null 且 attestations=[] → '有坐标但无时间证据'是合法状态",
    "unknown", "verified",
    "location_points.csv.range-0-1048575：yaw 空 576；对照 places/893951.json locations[0]")

# ---- connections.csv
C = PS + " :: connections.csv"
add(P, C, "place_id", "999909607",
    "source_records", "source_native_id",
    "⚠️ **连接边表不在本轮四张目标表(places/locations/names/source_records)内**。建议单独建 connections 表；在此之前把整行以 raw edge 存入 source_records。place_id 是**这条边的起点** place",
    "n/a", "verified",
    "connections.csv.range-0-524287 行2 place_id='999909607' title='Pompeii'；README.md(gis) L218-224 'the place from which the connection originates'")
add(P, C, "connects_to", "https://pleiades.stoa.org/places/433032",
    "source_records", "target_uri",
    "**是 URI 不是裸 id**，须从 URL 尾部提取数字 id 再 join places.uri。切片内 2763 行", "n/a", "verified",
    "connections.csv.range-0-524287 行2/行3 connects_to")
add(P, C, "connection_type", "part_of_analytical",
    "source_records", "relation_type",
    "词表 slug（**值非 term**），须 join connection_types.csv:key。切片内 37 种，top: at 712 / connection 683 / part_of_physical 263 / on 217 / near 166",
    "n/a", "verified_partial",
    "connections.csv.range-0-524287 取值分布；完整词表 connection_types.csv(6429 B) **本轮未取样**，37 种仅为 512KB 切片所见")
add(P, C, "year_after_which / year_before_which", "1700 / 2100",
    "source_records", "valid_from_year / valid_to_year",
    "该关系成立的 TPQ/TAQ。切片内非空仅 809/2763（29.3%），多为空 → 关系普遍无时间证据",
    "tpq_taq", "verified",
    "connections.csv.range-0-524287 行3 yaw='1700' ybw='2100'；非空 809/2763")

# ---- time_periods.csv
T = PS + " :: time_periods.csv"
add(P, T, "key / term / lower_bound / upper_bound / same_as / definition", "archaic | Archaic (Greco-Roman; 750-550 BCE/BC) (750 BC - 550 BC) | 750 BC | 550 BC | http://n2t.net/ark:/99152/p03wskdnwd4",
    "source_records", "ref_vocabulary_row",
    "**作为具名时期词表整表导入，不要试图 join GIS CSV —— 没有任何外键指向它。** lower_bound/upper_bound 是**文本**('750 BC'/'AD 300')，须解析前缀；更可靠的数值在 definition 尾部的 '[[a, b]]'（已是整数），但只覆盖 156/220 行",
    "bounded", "verified",
    "time_periods.csv 全量 220 行；逐字段扫过 places/names/location_points/connections 四表所有单元格，**无一命中任何 period key**（唯一疑似命中是 connections.id='anuradhapura'，为地名与词表 key 偶然同名）")
add(P, T, "（用途）attestations[].timePeriod", "['archaic','classical','hellenistic-republican','roman','late-antique']",
    "source_records", "period_set",
    "**仅 JSON API 可得，GIS CSV 已丢失。** 若要更细的时间粒度，唯一路径是逐条拉 JSON API 的 attestations[].timePeriod，再 join 本词表得到'时期集合'。CSV 侧只剩被压平的两个端点",
    "bounded", "verified",
    "places/912816.json locations[0].attestations 5 个时期 → start=-750 end=640；用 time_periods.csv 复算 archaic.lower=750BC→-750、late-antique.upper=AD640→640，与 JSON 完全吻合")

# ---- Pleiades 派生规则（地点级时间）
add(P, PS + " 【派生规则】", "locations.* + names.* 时间窗的并集", "",
    "places", "valid_from_year / valid_to_year",
    "地点存在时间**没有现成字段**。必须派生：min(该 place 所有 location 的 year_after_which, 所有 name 的 year_after_which) / max(对应 year_before_which)。结果必须标 time_bound_type='derived_tpq_taq' 并保留派生来源（用了哪几条 location/name），**严禁在 UI 上渲染成『建城年/废弃年』**",
    "tpq_taq", "recommended",
    "places.csv 无时间字段（实测）；912816.json 中 place 级亦无任何 year/date/time 字段，而 locations[0].start=-750/end=640、names 各 name 时间窗互不相同（Karduniaš -1600~-330 vs Babylonia -750~640 vs 仅古典期 -550~-330）")

# =====================================================================
# WHG
# =====================================================================
W = "WHG"
WS = "whgazetteer.org /api/place/{id}（JSON-LD 单记录 shape）"
WD = "whgazetteer.org /api/place/{id}（legacy flat shape，169687 系）"

add(W, WS, "properties.source_id", "gn:3169070",
    "source_records", "source_native_id",
    "原样保留 'namespace:id' 复合串；同时拆出 namespace 与裸 id 两列", "n/a", "verified",
    "whg/api/place/gn_3169070_roma.json → properties.source_id='gn:3169070'")
add(W, WS, "attribution.id", "gn",
    "source_records", "source_namespace",
    "命名空间枚举 {gn, tgn, hgis, chgis, kain_par, nl, ...}（sources.json 共 28 个）。**逐记录保存，不要用全局常量**",
    "n/a", "verified",
    "whg/api/place/gn_3169070_roma.json → attribution.id='gn'；tgn_7011781_london.json → 'tgn'")
add(W, WS, "attribution.license__spdx_id", "CC-BY-4.0",
    "source_records", "license_spdx",
    "**必须逐记录落库**。单记录 shape 是扁平结构，许可字段带 `license__` 双下划线前缀（不是 license.spdx_id；后者是 /reconcile 批量 shape 的嵌套写法，两种 shape 不通用）。gn→CC-BY-4.0，tgn→ODC-By-1.0",
    "n/a", "verified",
    "whg/api/place/gn_*.json 4 个文件 attribution.license__spdx_id='CC-BY-4.0'；tgn_7011781_london.json='ODC-By-1.0'。文档 whg_apis_docs.html 明确警告两种 shape 不通用")
add(W, WS, "attribution.license__url", "https://creativecommons.org/licenses/by/4.0/",
    "source_records", "license_url",
    "优先用 license__url；**license_url 与 license__url 二者重复，文档明示 'Prefer license__url'**", "n/a", "verified",
    "whg/api/place/gn_*.json attribution 同时含 license_url 与 license__url，值相同；whg_apis_docs.html 原文 'license_url and license__url are both present and duplicate each other. Prefer license__url'")
add(W, WS, "attribution.citation_text", "GeoNames geographical database, Unxos GmbH.",
    "source_records", "attribution_text",
    "**直接作为署名串展示，不要改写**。gn 与 tgn 的值不同：tgn 为 'Getty Thesaurus of Geographic Names (TGN), J. Paul Getty Trust.'",
    "n/a", "verified",
    "whg/api/place/gn_*.json、tgn_7011781_london.json attribution.citation_text")
add(W, WS, "attribution.rights_holder", "Unxos GmbH",
    "source_records", "rights_holder",
    "原样保留", "n/a", "verified",
    "whg/api/place/gn_*.json attribution.rights_holder；tgn 为 'J. Paul Getty Trust'")
add(W, WS, "attribution.redistributable", "true",
    "source_records", "redistributable",
    "布尔。**这是唯一跨两种 shape 都存在的字段**，语义是『WHG 是否可以把这个源的记录交给你』，**不是**『许可允许你分发』。gn/tgn=true；chgis/kain_par/nl=false（WHG 以 HTTP 451 拒绝）",
    "n/a", "verified",
    "whg/api/place/gn_*.json attribution.redistributable=true；sources.json 中 chgis/kain_par/nl=false；whg_apis_docs.html 原文 'redistributable answers a narrower question than the licence does'")
add(W, WS, "attribution.downloadable + download_blocked_reason", "false + volume-exceeds-cap",
    "source_records", "downloadable / blocked_reason",
    "⚠️ **`downloadable=false` 配 `redistributable=true` 是正常的，不是矛盾**，不要据此判定不可用。它只回答『WHG 是否提供批量下载』",
    "n/a", "verified",
    "whg/api/place/gn_*.json attribution.downloadable=false, download_blocked_reason='volume-exceeds-cap', redistributable=true；whg_apis_docs.html 原文 'downloadable: false alongside redistributable: true is normal and not a contradiction'")
add(W, WS, "attribution.license__attribution_required", "true",
    "source_records", "attribution_required",
    "布尔。**是法律条件不是礼貌请求** —— 文档原文 'records a legal condition, not a courtesy'。为 true 时署名是硬义务",
    "n/a", "verified",
    "whg/api/place/gn_*.json attribution.license__attribution_required=true；whg_apis_docs.html 原文")
add(W, WS, "properties.title", "Roma",
    "places", "title",
    "原样。注意 tgn 样本的 title 是 'Londen'（荷兰语形式）而非 'London'，**不要当作错误，也不要本地化覆盖**",
    "n/a", "verified",
    "whg/api/place/gn_3169070_roma.json properties.title='Roma'；tgn_7011781_london.json properties.title='Londen'")
add(W, WS, "geometry.coordinates", "[12.51133, 41.89193]",
    "locations", "lon / lat",
    "GeoJSON Point 顺序 **lon 在前 lat 在后**（与 Pleiades 两列命名相反，最易出错）。罗马 [12.51, 41.89] 可校验",
    "n/a", "verified",
    "whg/api/place/gn_3169070_roma.json geometry={'type':'Point','coordinates':[12.51133,41.89193]}；tgn london=[-0.093145,51.514248]")
add(W, WS, "geometry.type", "Point",
    "locations", "geom_type",
    "7 个样本全为 Point；未见到 LineString/Polygon 样本", "n/a", "verified_partial",
    "whg/api/place/*.json geometry.type='Point'（7/7）")
add(W, WS, "names[].toponym", "Roma",
    "names", "name_text",
    "多名称按数组顺序落库；与 places.title 可能不同", "n/a", "verified",
    "whg/api/place/169687.json names[0].toponym='Santa Fe'；gn_*.json names 数组中 'Byzantium'/'İstanbul' 等（whg_apis_docs.html 示例）")
add(W, WS, "names[].lang", "en",
    "names", "language_tag",
    "BCP 47；可为空", "n/a", "verified",
    "whg/api/place/169687.json names[].lang 示例值 'en'/'tr'")
add(W, WS, "when.timespans[].start.in / end.in", "{\"start\":{\"in\":\"-200\"},\"end\":{\"in\":\"1000\"}}",
    "places", "valid_from_year / valid_to_year",
    "⚠️ **语义未确认**：WHG 单记录中的 `when` 给的是显式区间端点（可与 `{}` 空对象）。它是『实体存续期』还是『文献见证期』，**样本与文档快照均未定义**。建议原样入库并标 time_semantics='bounded' + confidence='inferred'，**不得当精确起止年用**",
    "bounded", "inferred",
    "whg/api/place/tgn_7011781_london.json when={'timespans':[{'start':{'in':'-200'},'end':{'in':'1000'}}]}；gn_1816670_beijing.json when={'timespans':[{'end':{'in':'1949'}}]}（只有 end）；gn_3169070_roma.json when={}（空）。**LPF 规范原文不在本轮样本内，故语义标 inferred**")
add(W, WS, "[字段缺失] attribution.whg", "",
    "source_records", "overlay_license",
    "**7 个单记录样本中均无 attribution.whg 块**。文档另述 WHG 自身策展层为 CC-BY-4.0 且『叠加于各来源条款之上、永不替代』。若后续响应中出现，须另列一列存，不可覆盖逐来源许可",
    "n/a", "documented_only",
    "whg/api/place/*.json 7 个文件均无 attribution.whg；whg_apis_docs.html 原文 'attribution.whg is WHG’s own licence over its curation ... asserted in addition to each source’s terms and never replaces them'（仅文档依据）")

add(W, WD, "datasets[].id / .title", "{\"id\":14,\"title\":\"HGIS de las Indias (lugares)\"}",
    "source_records", "dataset_label",
    "⚠️ **旧扁平 shape 无 attribution 块、无任何许可字段**。只能靠 dataset id/title 回查 sources.json 得到『可再分发』，**拿不到 SPDX**。此类记录建议默认不入公开包",
    "n/a", "verified",
    "whg/api/place/169687.json 与 169687-169688.json 顶层键无 attribution/licen/right 任一；datasets=[{'id':14,'title':'HGIS de las Indias (lugares)'}]；sources.json namespace='hgis' 仅给出 redistributable=true, downloadable=true,**无 license 字段**")
add(W, WD, "minmax", "[1701, 1808]",
    "places", "valid_from_year / valid_to_year",
    "区间两端均为整数年。**语义未确认**（是数据集覆盖期还是记录存续期不明），标 bounded + inferred", "bounded", "inferred",
    "whg/api/place/169687.json minmax=[1701,1808]；attestation_years=[]（空）。文档未定义 minmax 语义")
add(W, WD, "geoms[].coordinates", "[-99.272349, 19.361932]",
    "locations", "lon / lat",
    "同样 lon 在前。geoms 为数组，一个 place 可多几何", "n/a", "verified",
    "whg/api/place/169687.json geoms[0].coordinates=[-99.272349,19.361932]；169687-169688.json geoms 有 2 条")
add(W, WD, "geoms[].geowkt", "POINT(-99.272349 19.361932)",
    "locations", "geom_wkt_raw",
    "原样保留；可与 coordinates 互为校验（WKT 内 X Y 顺序与 coordinates 一致）", "n/a", "verified",
    "whg/api/place/169687.json geoms[0].geowkt")

# =====================================================================
# CHGIS
# =====================================================================
G = "CHGIS"
GS = "CHGIS v6 / time_pref_pts (v6_time_pref_pts_utf_wgs84.dbf, 5226 记录 / 23 字段)"
GC = "CHGIS v6 / time_cnty_pts (v6_time_cnty_pts_utf_wgs84.dbf, 10522 记录 / 23 字段)"

add(G, GS, "NAME_PY", "Dingqiang Jun",
    "names", "name_text",
    "拼音/罗马化名，作为主显示名。CHGIS 一行 = 一个时间切片下的一个名称，**同一 SYS_ID 跨多行会有不同 NAME_PY**（如 Baode Jun→Baode Zhou→Baode Xian），这正好对应我们的 names 表",
    "n/a", "verified",
    "v6_time_pref_pts_utf_wgs84.zip → .dbf 字段表 + 记录0 'Dingqiang Jun' / 记录1 'Baode Jun' / 记录2 'Baode Zhou'；cnty_pts 中同一 SYS_ID 95002/95003 亦有不同 NAME_PY")
add(G, GS, "NAME_CH", "定羌军",
    "names", "name_text_zh_hans",
    "简体中文字形，原样保留（UTF-8，.cpg='UTF-8'）", "n/a", "verified",
    "v6_time_pref_pts .dbf 记录0 NAME_CH='定羌军'；.cpg 内容 'UTF-8'")
add(G, GS, "NAME_FT", "定羌軍",
    "names", "name_text_zh_hant",
    "繁体中文字形（FT=fan体）。**与 NAME_CH 不等价**（军/軍），是两个独立写法，不要合并", "n/a", "verified",
    "v6_time_pref_pts .dbf 记录0 NAME_FT='定羌軍'；cnty_pts 记录1 NAME_CH='保德县' NAME_FT='保德縣'")
add(G, GS, "X_COOR", "111.076617",
    "locations", "lon",
    "**经度 X**。CRS 有明确声明：同 zip 内 `.prj` = `GEOGCS[\"GCS_WGS_1984\",DATUM[\"D_WGS_1984\",SPHEROID[\"WGS_1984\",6378137,298.257223563]],PRIMEM[\"Greenwich\",0],UNIT[\"Degree\",0.017453292519943295]]` → WGS84 经纬度。**这是本表 confidence 可判 verified 的关键差异（对比 MCGD 无声明）**",
    "n/a", "verified",
    "v6_time_pref_pts_utf_wgs84.zip 内 .prj 原文（见上）；.dbf 记录0 X_COOR='111.076617'")
add(G, GS, "Y_COOR", "39.017872",
    "locations", "lat",
    "**纬度 Y**，WGS84（.prj 已声明）", "n/a", "verified",
    "同上 .prj；.dbf 记录0 Y_COOR='39.017872'（山西保德 ≈ 39.0N, 111.1E，与 PRES_LOC 一致）")
add(G, GS, "BEG_YR", "993",
    "locations", "valid_from_year",
    "**精确/有界取决于 BEG_RULE**，必须与 BEG_RULE 一起读：rule∈{1,2,3} → 时期边界（bounded）；rule=4 → 精确年；rule=5 → 到月；rule=6 → 到日；rule=9 → **时间切片，不代表有效跨度**（begin==end，仅'取材于该年'）。负数年跨系统换算须 astro_year = year+1 if year<0",
    "exact_or_bounded", "verified",
    "v6_time_pref_pts .dbf 记录0 BEG_YR='993' BEG_RULE='4'；记录1 BEG_YR='1005' BEG_RULE='4'；规则表见 CHGIS_data_dictionary.zip → xtra_date_rules.xlsx（rule 1/2/3/4/5/6/9 及英文释义已逐条读出）")
add(G, GS, "END_YR", "1004",
    "locations", "valid_to_year",
    "同上，与 END_RULE 配对读。cnty_pts 记录0 END_RULE='6'（到日精度），END_YR='1911'",
    "exact_or_bounded", "verified",
    "v6_time_pref_pts .dbf 记录0 END_YR='1004' END_RULE='4'；cnty_pts 记录0 END_YR='1911' END_RULE='6'")
add(G, GS, "BEG_RULE", "4",
    "source_records", "beg_time_rule",
    "**必须单独落库，不能丢**。取值域（xtra_date_rules.xlsx 原文）：1=Pan-Dynastic period, 2=Dynastic period, 3=Reign period, 4=Specific year, 5=Specific month, 6=Specific date, 9=Time slice",
    "n/a", "verified",
    "CHGIS_data_dictionary.zip → xtra_date_rules.xlsx 全 7 行原文逐条读出（rule_number/rule_short_name/rule_eng）")
add(G, GS, "END_RULE", "4",
    "source_records", "end_time_rule",
    "同上。**特别注意 rule=9**：原文 'Dated is set to a specific year based on the source materials used, **not based on the valid span of time for the historical place** [both Begin and End values will be the same]' → rule=9 的行不可当有效期使用",
    "n/a", "verified",
    "xtra_date_rules.xlsx rule 9 行原文；cnty_pts 记录0 END_RULE='6'")
add(G, GS, "TYPE_PY / TYPE_CH", "Jun / 军",
    "places", "place_type",
    "行政层级类型；LEV_RANK 为数值等级（切片内 '3'/'6'）。**CHGIS 的 TYPE 与 Pleiades 的 placeTypes 词表不同源**，需自建映射表，不可直接互译",
    "n/a", "verified",
    "v6_time_pref_pts .dbf 记录0 TYPE_PY='Jun' TYPE_CH='军' LEV_RANK='3'；cnty_pts 记录0 TYPE_PY='Zhou' TYPE_CH='州' LEV_RANK='6'")
add(G, GS, "SYS_ID", "210001",
    "places", "source_native_id",
    "**这是 CHGIS 的实体主键**。同一 SYS_ID 可跨多行/多时间切片；同一 NAME_PY 也可对应不同 SYS_ID（保德县 95002/95003 是不同实体）。join 与去重都必须以 SYS_ID 为准",
    "n/a", "verified",
    "v6_time_pref_pts .dbf 记录0 SYS_ID='210001'；cnty_pts 记录1 SYS_ID='95002' 记录2 SYS_ID='95003'（同名 Baode Xian）")
add(G, GS, "PRES_LOC", "今山西保德县城西侧",
    "places", "present_location_note",
    "中文'今地'描述，原样保留为文本，**不要尝试解析成坐标**", "n/a", "verified",
    "v6_time_pref_pts .dbf 记录0 PRES_LOC='今山西保德县城西侧'；cnty_pts 记录0 '山西保德县城西侧'")
add(G, GS, "OBJ_TYPE", "POINT",
    "locations", "geom_type",
    "切片样本全为 POINT（这两个文件本身就是 points 图层）", "n/a", "verified",
    "v6_time_pref_pts/.dbf 记录0 OBJ_TYPE='POINT'")
add(G, GS, "BEG_CHG_TY / END_CHG_TY", "新建 / 更名",
    "source_records", "change_type_beg / change_type_end",
    "变化类型中文词（更名/新建/撤销/数据下限…）。**语义未确认**（词表 xtra_change_types.xlsx 在本轮样本 zip 中，但未逐行解析）",
    "n/a", "inferred",
    "v6_time_pref_pts .dbf 记录0 BEG_CHG_TY='新建' END_CHG_TY='更名'；记录2 END_CHG_TY='撤销'；cnty_pts 记录0 END_CHG_TY='数据下限'。词表未解析")
add(G, GS, "GEO_SRC", "FROM_FD",
    "source_records", "geo_source_code",
    "代码值（FROM_FD / FROM_AC …），对应 xtra_geo_source.xlsx。**本轮未解析该表，代码含义未确认**", "n/a", "inferred",
    "v6_time_pref_pts .dbf 记录0 GEO_SRC='FROM_FD'；cnty_pts GEO_SRC='FROM_AC'。xtra_geo_source.xlsx 在 zip 内但未解析")
add(G, GS, "[许可] attribution / citation 串", "\"CHGIS Version 6.\" (c) Fairbank Center for Chinese Studies and the Institute for Chinese Historical Geography at Fudan University, Dec 2016.",
    "source_records", "attribution_text",
    "⚠️ **官方分发里有两份不一致的强制引用串，须两条都存**：(a) Dataverse EULA termsOfUse 条款(4) 的版本（上文 sample_value）；(b) 数据包内 CHGIS_V6_README.txt 的版本 `\"CHGIS, Version: 6.\" (c) Fairbank Center for Chinese Studies of Harvard University and the Center for Historical Geographical Studies at Fudan University, 2016.\"`。差异：Version: 6 vs Version 6 / Center for Historical Geographical Studies vs Institute for Chinese Historical Geography / 2016 vs Dec 2016。无法判定权威版，建议以 EULA 为主、README 并列",
    "n/a", "verified",
    "chgis/api/dataset_FDLFJ3_EULA.json → data.latestVersion.termsOfUse 条款(4)；chgis/CHGIS_V6_README.txt 第 10 行 Citation 行。两者原文均已逐字比对")
add(G, GS, "[许可] 一句话合规摘要", "free for academic research, no commercial use, resale, or redistribution permitted.",
    "source_records", "license_status",
    "可直接落库为一句话摘要；与 EULA 条款(3)(5) 方向一致。redistributable 必须为 false",
    "n/a", "verified",
    "chgis/CHGIS_V6_README.txt 'License: free for academic research, no commercial use, resale, or redistribution permitted.'")
add(G, GC, "字段差异：GEOCOMPLR vs GECOMPLR；END_DATE vs ENT_DATE", "GEOCOMPLR / END_DATE（pref）  vs  GECOMPLR / ENT_DATE（cnty）",
    "source_records", "(警告)",
    "⚠️ **两个图层字段名不一致且有拼写错误**：pref_pts 为 `GEOCOMPLR`+`END_DATE`，cnty_pts 为 `GECOMPLR`+`ENT_DATE`（少一个 O / 换了词）。导入器必须按图层分别写字段映射，不能用一份 schema 通吃",
    "n/a", "verified",
    "v6_time_pref_pts.dbf 23 字段含 GEOCOMPLR, END_DATE；v6_time_cnty_pts.dbf 23 字段含 GECOMPLR, ENT_DATE（两 zip 内 .dbf 头部逐字段解析）")

# =====================================================================
# MCGD
# =====================================================================
M = "MCGD"
MS = "Modern China Geospatial Database - Main Dataset / MCGD_Data2026_08_25.csv (960 行样本，占全量 31953904 B 的约 0.2%)"

add(M, MS, "LocID", "D3392205",
    "places", "source_native_id",
    "**地点主键**。首字母有语义（Zenodo 描述原文）：`D` = 取自 China Historical GIS (Harvard)；`E` = 取自 GeoNames 或团队从各种地图资料添加。切片内 D=868 / E=92。**注意与 CHGIS 的 SYS_ID 无关，不可互 join**",
    "n/a", "verified",
    "MCGD 样本行2 LocID='D3392205'；行793 LocID='E9613613'；首字母分布 Counter({'D':868,'E':92})；Zenodo record 22094815 metadata.description 原文 'Locations IDs that start with \"D\" are data points extracted from China Historical GIS...'")
add(M, MS, "NameID", "H0380830",
    "names", "source_native_id",
    "**名称主键**。Zenodo 原文 'The Name IDs all start with H followed by seven digits'；实测 960/960 全为 H 开头、长度 8，完全吻合",
    "n/a", "verified",
    "MCGD 样本行2 NameID='H0380830'；长度分布 {8:960}；Zenodo 描述原文")
add(M, MS, "Name", "A-ch'a Kang",
    "names", "name_text",
    "**Wade-Giles 转写为主**（含撇号送气符，切片内 198/960 含撇号）。⚠️ 同一 LocID 可挂多个 Name（切片内 162 个 LocID 多名，最多 D3236772 挂 15 个）→ 1 place : N names，与我们的 names 表结构一致",
    "n/a", "verified",
    "MCGD 样本行3 Name=\"A-ch'a Kang\"、行4 \"A-ch'eng\"、行8 'A-ch'eng-hsien'、行9 'A-ch'i Shan'；含撇号 198/960；LocID 多名统计见 r2_verify_whg_mcgd_chgis.py")
add(M, MS, "Name 【Code 分类】", "P / W / PP / WW / A / C",
    "names", "name_type",
    "Zenodo 描述的取值域：`A`=Canonical Chinese name、`C`=Alternative Chinese name、`P`=Romanized name in pinyin、`W`=Romanized name in another transliteration system；**双写 PP/WW 表示该名未能匹配到数据集内任何已有中文名**。切片内分布 P=408, W=216, PP=198, WW=135。⚠️ 切片内还出现 **`NA`(1) 与 `J`(1)**，**这两个值不在描述记录的取值域内**，属未记载取值",
    "n/a", "verified",
    "MCGD 样本 Code 分布 Counter({'P':408,'W':216,'PP':198,'WW':135,'NA':1,'A':1,'J':1})；Zenodo 描述 UPDATES 段 'MCGD_Data2025_08_06 introduces ... the Code column' 列出 A/C/P/W/PP/WW")
add(M, MS, "Code 【与自建 name_type 的映射】", "P → romanized_pinyin；W → romanized_other_scheme",
    "names", "name_type",
    "**MCGD 的 Code 是我们没有的维度**（转写体系 + 是否已匹配中文名），**不要硬塞进 Pleiades 的 name_type 词表**（那个词表只有 geographic/ethnic/label/associated_modern/unknown/undefined）。建议在 names 表另开 `source_name_code` 列独立保存",
    "n/a", "recommended",
    "对照 gis_vocab/name_types.csv 6 个 key（无 pinyin/transliteration 概念）与 MCGD Zenodo Code 释义，两套分类维度正交")
add(M, MS, "LAT", "33",
    "locations", "lat",
    "⚠️ **CRS 与轴序均无任何声明**，故 confidence=inferred。数值形式上落在 [-90,90]（960/960），且与 LONG 配对后 953/960 落在中国 bbox(18-54N, 73-135E)，与『列名 LABEL 为 Latitude』一致，但**这只是合理性校验，不是 CRS 断言**。入库须标 crs_asserted=false",
    "n/a", "inferred",
    "MCGD 表头 9 字段无任何 crs/coord/datum/srid/proj 字段；LAT 可解析 960/960，min=18.531351 max=53.333333；Zenodo 描述仅写 'LAT: Latitude coordinates'，未声明 CRS")
add(M, MS, "LONG", "88",
    "locations", "lon",
    "⚠️ 同上，CRS 无声明 → inferred。**且存在 1 条越界脏数据**（行793 'Aleitai' LONG=881.41253 > 180），导入时必须做范围校验并隔离，不能静默截断",
    "n/a", "inferred",
    "MCGD 表头无 CRS 字段；LONG 可解析 960/960，min=-84.659684 max=881.41253；行793 Aleitai LONG='881.41253'（疑为 88.141253 误录）")
add(M, MS, "Prov_Zh / Prov_Py / PROVID", "新疆 / Xinjiang / 28",
    "places", "admin_unit_*",
    "三者严格 1:1（切片内 32 个 PROVID ↔ 32 个 (Prov_Zh, Prov_Py) 组合，双向均无一对多）。Prov_Zh 为**繁体**中文省名（新疆/內蒙古/台灣）。**`Prov_*=NA` 是剔除域外地点的官方过滤条件**（Zenodo 原文 'Such place names can easily be removed by selecting all the entries where the Province data is missing'）",
    "n/a", "verified",
    "MCGD 样本：PROVID 唯一值 32、(Prov_Zh,Prov_Py) 唯一组合 32、双向一对多均为 0；映射表完整读出（1=安徽 … 48=台灣, NA=NA）；Zenodo 描述原文")
add(M, MS, "PROVID 【未记载字段】", "1..31, 48, NA",
    "places", "admin_unit_id",
    "⚠️ **`PROVID` 在 Zenodo 描述里完全没有被提及**（描述的『七个变量』列表里没有它，只有 Name/Prov_Zh/Prov_Py/LAT/LONG/LocID/NameID）。其语义（省份 id）是**由 1:1 映射实测推断**，不是文档声明。切片内缺 3 与 32-47 号，含义未确认",
    "n/a", "inferred",
    "Zenodo 描述『The data include seven variables』仅列 7 个，不含 Code 与 PROVID；Code 在 UPDATES 段有记载，PROVID 无任何记载。切片内 PROVID 缺号：3、32-47")
add(M, MS, "[字段缺失] 任何时间字段", "",
    "places", "(不可用)",
    "**MCGD 没有任何时间字段** —— 全量 9 列无一处涉及年代。因此 MCGD 只能提供『名称 + 坐标 + 省籍 + 转写体系』，**不能提供任何时间信息**。导入后这些记录的 valid_from/valid_to 必须为 NULL，time_bound_type='unknown'",
    "unknown", "verified",
    "MCGD 表头 9 字段逐项检查：Name, Prov_Zh, Prov_Py, Code, LAT, LONG, LocID, NameID, PROVID —— 无任何 year/date/time 相关列；Zenodo 描述的 7 变量列表亦无时间项")

# =====================================================================
# 跨源一致性规则（不给具体源，但工程必须处理）
# =====================================================================
add("CROSS-SOURCE", "四源共性（作用于 locations）", "—— 年份跨系统换算", "-550 (Pleiades) / -30 (Pleiades location)",
    "locations", "valid_from_year / valid_to_year",
    "Pleiades 明示**无 0 年**（proleptic Julian，BCE 用负数）；CHGIS 亦有负年。跨系统换算到含 0 年的天文纪年时必须 `astro_year = year + 1 if year < 0 else year`，否则整体错位 1 年。Pleiades 侧已实测无 '0' 值（切片内 0 条）",
    "n/a", "verified",
    "README.md(gis) L304/L314 两处 'There is no year zero'；names.csv 切片内 year_*=='0' 的行数=0；location_points.csv 行2 yaw='-30'、行4 yaw='-550' ybw='-30'；CHGIS BEG_YR/END_YR 为 N 型数值列")
add("CROSS-SOURCE", "四源共性（作用于 names）", "—— 年份跨系统换算", "-550 (Pleiades names 行24)",
    "names", "in_use_from_year / in_use_to_year",
    "同上。注意 Pleiades names 的负年份出现在同一行两端的情况较少但存在（如 -550 → 300 为跨 BCE/CE），换算必须逐端点独立判断符号",
    "n/a", "verified",
    "names.csv.range-0-1048575 行18 yaw='-330'、行24 yaw='-550'、行25 yaw='-30'")
add("CROSS-SOURCE", "四源共性（作用于 locations）", "—— time_bound_type 判别列", "",
    "locations", "time_bound_type",
    "**必须建这一列，否则下游无法区分 TPQ/TAQ 与精确年。** 取值域：exact（上下界即精确年）/ tpq_taq（约束区间）/ bounded（粗粒度时期边界）/ exact_or_bounded（依随附 RULE）/ unknown。按源赋值：Pleiades → 恒为 tpq_taq；CHGIS → exact_or_bounded（依 BEG_RULE/END_RULE）；MCGD → 恒为 unknown（无时间字段）",
    "n/a", "recommended",
    "本表 locations 各行 time_semantics 汇总；Pleiades 位置区间宽度 median=670 年、0 条窄于 50 年 → 不可当精确年；CHGIS xtra_date_rules 7 条规则证明精度由 RULE 决定；MCGD 9 列无任何时间字段")
add("CROSS-SOURCE", "四源共性（作用于 names）", "—— time_bound_type 判别列", "",
    "names", "time_bound_type",
    "同上。Pleiades names → tpq_taq（区间宽度 median=400 年，仅 3/4125 窄于 50 年）；CHGIS names 来自 BEG_YR/END_YR → exact_or_bounded；MCGD names → unknown",
    "n/a", "recommended",
    "names.csv 切片内宽度分布；CHGIS xtra_date_rules.xlsx；MCGD 表头无时间列")
add("CROSS-SOURCE", "四源共性（作用于 places）", "—— time_bound_type 判别列", "",
    "places", "time_bound_type",
    "**places 层只有 Pleiades 需要派生**：places.csv 无时间字段，须由 locations+names 聚合，结果标 `derived_tpq_taq`；CHGIS/WHG/MCGD 的 places 时间直接从各自字段落库，标 exact_or_bounded / bounded / unknown",
    "n/a", "recommended",
    "places.csv 表头 11 字段无时间字段（实测）；912816.json place 级亦无 year/date/time 字段；CHGIS BEG_YR/END_YR 在实体行上；WHG when；MCGD 无")

# =====================================================================
# 与已落地的 normalized/ 表结构对齐（软件工程师已产出，2026-11-02）
# 作用：本表 target_field 用的是语义名；工程侧实际列名见下，二者须一一对应。
# =====================================================================
add("CROSS-SOURCE", "对齐 normalized/ 实表", "target_table=names → historical_place_names.csv", "",
    "names", "name_id / place_id / name / name_lang / name_script / name_type / transliteration_scheme",
    "工程侧已建表（45,206 行）。本表 names 语义字段对应关系：name_text→name；name_original_script→name_script；language_tag→name_lang；name_type→name_type；romanized_form_2/_3→transliteration_scheme（部分）",
    "n/a", "verified",
    "设计资料/P0收敛/WB-002/normalized/historical_place_names.csv 第 1 行表头：name_id,place_id,name,name_lang,name_script,name_type,transliteration_scheme,valid_from_year_astro,valid_to_year_astro,time_basis,source_record_id,notes")
add("CROSS-SOURCE", "对齐 normalized/ 实表", "target_table=locations → historical_place_locations.csv", "",
    "locations", "location_id / place_id / geom_type / lon / lat / geom_wkt / representative_lon / representative_lat / original_x / original_y / original_crs / crs_confidence / axis_order_verified / location_precision / uncertainty_m",
    "工程侧已建表（16,391 行）。本表 locations 语义字段对应：lon/lat→lon/lat；accuracy_radius_m→uncertainty_m；geometry_wkt→geom_wkt；accuracy_source_uri→（无对应列，需新增）。**`axis_order_verified` 与 `crs_confidence` 两列是本次 Pleiades 导入的关键校验位**",
    "n/a", "verified",
    "设计资料/P0收敛/WB-002/normalized/historical_place_locations.csv 第 1 行表头；实测 crs_confidence={confirmed:15748, inferred:643}、axis_order_verified 全为 true、original_crs={EPSG:4326:15748, unknown:643}")
add("CROSS-SOURCE", "对齐 normalized/ 实表", "target_table=places → historical_places.csv", "",
    "places", "place_id / canonical_name / canonical_name_lang / place_type / source_id / source_dataset / primary_external_id",
    "工程侧已建表。本表 places 语义字段对应：title→canonical_name；source_native_id→primary_external_id；place_type→place_type。⚠️ **该表目前没有 valid_from/valid_to 列** —— Pleiades 地点级派生时间无处可放，须新增两列",
    "n/a", "verified",
    "设计资料/P0收敛/WB-002/normalized/historical_places.csv 第 1 行表头（11 列，无时间列）")
add("CROSS-SOURCE", "对齐 normalized/ 实表", "target_table=source_records → source_records.csv", "",
    "source_records", "source_record_id / source_id / source_dataset / external_id / external_id_type / raw_file / raw_record_index / raw_payload_json / license_status / redistributable / attribution_text",
    "工程侧已建表（16,708 行）。本表 source_records 语义字段对应：license_spdx→license_status；redistributable→redistributable；attribution_text→attribution_text；source_namespace→source_id。⚠️ **本表要求的 beg_time_rule / end_time_rule（CHGIS 日期规则）在该表中无对应列，须新增**，否则 CHGIS 的 exact/bounded 判别信息会在落地时丢失",
    "n/a", "verified",
    "设计资料/P0收敛/WB-002/normalized/source_records.csv 第 1 行表头；实测 license_status={restricted_academic_only:15748, cc-by-4.0:960}、redistributable={no:15748, yes_with_attribution:960}")
add("CROSS-SOURCE", "对齐 normalized/ 实表 【冲突预警】", "time_basis 的取值域", "source_attested / unknown / mixed / estimated",
    "names", "time_basis",
    "⚠️ **口径冲突，必须在 Pleiades 入库前解决**：工程侧现用 `time_basis` 4 值（source_attested / unknown / mixed / estimated），**这四个值都无法表达『TPQ/TAQ 约束区间』**。若 Pleiades 的 year_after_which/year_before_which 仍写入 `source_attested`，下游将无法把它与 CHGIS 的精确年区分，UI 会把『公元前 750 年之后到公元 640 年之前』渲染成『公元前 750 年–公元 640 年』的确定起止。建议把 time_basis 扩充（或在 names/locations 增列 `time_bound_type`）为：exact / tpq_taq / bounded / exact_or_bounded / derived_tpq_taq / unknown",
    "n/a", "recommended",
    "normalized/historical_place_names.csv 实测 time_basis={source_attested:21775, unknown:19335, mixed:2400, estimated:1696}；normalized/historical_place_locations.csv time_basis={source_attested:8116, unknown:6867, mixed:828, estimated:580}。Pleiades 与 WHG **尚未入库**（source_records.source_dataset 仅含 chgis_cnty 10522 / chgis_pref 5226 / mcgd 960）")
add("CROSS-SOURCE", "四源共性", "—— 年份写入列", "valid_from_year_astro",
    "names", "valid_from_year_astro / valid_to_year_astro",
    "工程侧已用 `*_year_astro` 列名且已做天文纪年换算（其 stats.json 自检 astro_year(-221)==-220、astro_year(0) raises）。本表所有 time_semantics∈{tpq_taq, bounded, exact_or_bounded} 的年份须**先做 astro 换算再写入该列**，并保留原始年值一列备查",
    "n/a", "verified",
    "normalized/historical_place_names.csv 与 historical_place_locations.csv 列名 *_year_astro；normalized/stats.json astro_assertions 数组 5 条自检")

with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=COLS, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writeheader()
    for r in R:
        w.writerow(r)

print(f"written: {OUT}")
print(f"rows (excl header): {len(R)}")
from collections import Counter
print("by source:", dict(Counter(r["source"] for r in R)))
print("by target_table:", dict(Counter(r["target_table"] for r in R)))
print("by time_semantics:", dict(Counter(r["time_semantics"] for r in R)))
print("by confidence:", dict(Counter(r["confidence"] for r in R)))
