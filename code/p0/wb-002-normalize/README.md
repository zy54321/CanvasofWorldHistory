# WB-002 历史地理数据规范化流水线

把**四个数据源**整理成可追溯的规范化暂存数据集：

| 源 | 内容 | 本轮角色 |
|---|---|---|
| **CHGIS V6** | 时间序列点数据（府级 `time_pref_pts` + 县级 `time_cnty_pts`） | 主源，提供行政层级、纪年规则、治所坐标 |
| **MCGD** | 现代中国地理数据库 960 行样本 | 现代坐标/罗马化对照 |
| **Pleiades** | GIS CSV 导出（data/gis）5 个 1 MB HTTP Range 切片 | 古典世界地名，提供 TPQ/TAQ 纪年 |
| **WHG** | World Historical Gazetteer API 7 个单记录响应 | 跨语料地名，逐记录许可差异 |

- **输入（只读）**：`设计资料/P0验证/WB-002/sample_data/`（CHGIS / MCGD / WHG）
  与 `设计资料/P0收敛/WB-002/sample_data_pleiades/`（Pleiades 切片）
- **输出**：`设计资料/P0收敛/WB-002/normalized/` 与 `设计资料/P0收敛/WB-002/issues/`
- **依赖**：仅 Python 标准库。**不使用** pandas / shapefile / dbfread / pyproj / openpyxl。
- **网络**：不联网。**数据库**：不建库、不导入。

---

## 运行方法

在项目根目录执行一条命令：

```bash
python code/p0/wb-002-normalize/run_all.py
```

### 参数

| 参数 | 说明 |
|---|---|
| `--timestamp ISO8601` | 固定写入每行的 `created_at` / `ingested_at`。等价环境变量 `WB002_RUN_TIMESTAMP`。不传则取当前 UTC 时间。 |
| `--project-root PATH` | 手工指定项目根（默认从脚本位置向上推）。 |
| `--quiet` | 只输出错误与 ground-truth 失败，不打印每步耗时。 |

### 可复现性

```bash
python code/p0/wb-002-normalize/run_all.py --timestamp 2026-11-02T00:00:00Z
python code/p0/wb-002-normalize/run_all.py --timestamp 2026-11-02T00:00:00Z
```

两次运行产出的 **16 个数据产物**（7 张 `normalized` 表 + 8 个 `issues` 产物 +
`stats.json`）**逐字节相同**（已实测：`md5sum -c` 16/16 `OK`）。
`run_manifest.json` 是唯一例外，其中 `run_started_utc` / `run_finished_utc` /
`duration_seconds` 必然不同——它是 provenance，不是测量值。

> 因此 `stats.json` **刻意不含任何 wall-clock 字段**：固定 `--timestamp` 时它必须
> 稳定。运行时刻只出现在 `run_manifest.json` 里。

### 输入完整性自检

流水线在开始与结束时各计算一次**全部 21 个输入文件**的 SHA256
（CHGIS 2 zip + 字典 + README + EULA、MCGD CSV + Zenodo 记录、
Pleiades 5 切片 + FETCH_LOG、WHG 7 响应 + sources.json），
若不一致会**直接以非零码退出**：

```
FATAL: read-only source files changed during the run: ...
```

两次数值写入 `run_manifest.json` 的 `input_integrity` 段。本轮实测 `unchanged`。

---

## 模块结构

| 文件 | 职责 |
|---|---|
| `run_all.py` | 总入口：串起全部阶段，打印耗时，做输入哈希前后校验。 |
| `dbf_reader.py` | 纯标准库 DBF（dBase III/IV）解析器。 |
| `xlsx_reader.py` | 纯标准库 `.xlsx` 读取器（处理 CHGIS 字典用 `inlineStr`、无 `sharedStrings.xml` 的情况）。 |
| `chgis_extract.py` | 从两个 zip 中提取 15,748 条 CHGIS 记录，保留全部 23 个原始字段；另读 `.prj`/`.cpg` 与 Dataverse EULA 里的强制引用串。 |
| `mcgd_extract.py` | 读取 960 行 MCGD 样本与 Zenodo 许可元数据。 |
| `pleiades_extract.py` | 读取 5 个 Pleiades 切片，丢弃截断尾行，按 WKT/命名列两种轴序约定解析坐标。 |
| `whg_extract.py` | 读取 7 个 WHG 响应，区分 JSON-LD 与旧扁平两种 schema，逐记录取许可。 |
| `extra_record.py` | Pleiades/WHG 共用的扁平记录类型与 WKT 点解析。 |
| `datasets.py` | 7 个已导入数据集的许可/引用/取证登记表 —— `data_datasets.csv` 的唯一来源。 |
| `time_semantics.py` | `time_bound_type` / `time_rule_code` 词汇表与 CHGIS 规则码映射。 |
| `quality_checks.py` | 时间异常、坐标簇、同名异地、跨层矛盾、字段名差异检测。 |
| `chgis_migration.py` | 规则化迁治分析：实体分组、相邻对判定、链条组装、审核队列、ground-truth 回归。 |
| `normalize.py` | 构建七张暂存表。 |
| `report_stats.py` | 写出 `issues/*.csv`、`stats.json`、`run_manifest.json`。 |
| `csv_io.py` | 确定性 CSV/JSON 写出（UTF-8 BOM + CRLF）。 |

### 执行阶段与耗时（本轮实测）

```
0.087s  hash inputs (before)                                 [21 files]
0.017s  parse CHGIS date-rule dictionary                     [7 rules]
0.134s  extract CHGIS DBF records                            [cnty=10522, pref=5226]
0.000s  read CHGIS README (license + citation)
0.005s  extract MCGD sample rows                             [rows=960]
0.118s  extract Pleiades GIS slices                          [rows=12665, places=2643, tails=4]
0.002s  extract WHG API samples                              [rows=238, places=7]
0.000s  verify astronomical-year conversion                  [5 assertions]
0.041s  analyse time anomalies                               [beg>end=28]
0.082s  build coordinate clusters                            [clusters=6013]
0.082s  analyse homonyms                                     [2071/8303]
0.000s  detect field-name quirks                             [2]
0.032s  find cross-layer disagreements                       [29]
0.182s  analyse migration chains                             [7223 pairs, 1254 chains, 1866 queued]
0.023s  verify migration ground truth                        [新兴郡=PASS, 中山国=PASS]
1.642s  build seven staging tables
1.015s  write normalized/*.csv                               [7 tables]
0.341s  write issues/*.csv                                   [8 files]
0.096s  write stats.json
0.012s  hash inputs (after)                                  [unchanged]
0.261s  write run_manifest.json
------
4.17s   total
```

---

## 输出文件

### `normalized/`（七张暂存表 + 两个清单）

全部为 **UTF-8 with BOM、CRLF、逗号分隔、双引号转义**，可直接用 Excel 打开。

| 表 | 行数 |
|---|---|
| `historical_places.csv` | 19,039 |
| `historical_place_locations.csv` | 18,103 |
| `historical_place_names.csv` | 47,503 |
| `source_records.csv` | 29,391 |
| `data_quality_issues.csv` | 12,631 |
| `candidate_matches.csv` | 53,137 |
| `data_datasets.csv` | 7 |

#### `historical_places.csv`

一个 distinct `SYS_ID`（CHGIS）/ 一个 `LocID`（MCGD）/ 一个 `places.id`（Pleiades）/
一个 WHG place id = 一行。

| 字段 | 说明 |
|---|---|
| `place_id` | `hp_` + 6 位序号。按 `source_dataset` 固定顺序（`chgis_pref` → `chgis_cnty` → `mcgd` → `pleiades` → `whg`）再按外部 ID 稳定排序后分配，重跑不变。 |
| `canonical_name` | CHGIS：该 SYS_ID 下"最新时段"的 `NAME_CH`（`BEG_YR` 最大 → `END_YR` 最大 → `record_index` 最小）；`NAME_CH` 空则退回 `NAME_PY`。MCGD：`NameID` 字典序最小的行（任意但稳定，已标注）。Pleiades/WHG：源数据的 `title`。 |
| `canonical_name_lang` | CHGIS `zh` / `zh-Latn`；MCGD `zh-Latn`；Pleiades/WHG `und`（源未声明语言）。 |
| `place_type` | `admin_center_prefecture` / `admin_center_county` / `admin_center_other` / `unknown`。非 CHGIS 源一律 `unknown`：Pleiades GIS 导出没有类型列，WHG 返回 AAT/GeoNames 要素码，映射过来需要源不支持的判断。 |
| `source_id` | `chgis` / `mcgd` / `pleiades` / `whg`。 |
| `source_dataset` | `chgis_pref` / `chgis_cnty` / `mcgd_zenodo_22094815_head960` / `pleiades_gis_4_1_slice` / `whg_api_sample`。 |
| `primary_external_id` | 各源自己的地点键（`SYS_ID` / `LocID` / Pleiades `id` / WHG place id）。 |
| `record_status` / `locked` | `staging` / `false`。 |
| `created_at` | 运行时间戳。 |
| `valid_from_year_astro` / `valid_to_year_astro` | **地点级**区间，从天级记录聚合而来。见 `time_derivation`。 |
| `time_bound_type` | 地点级时间语义，见决策 5。 |
| `time_derivation` | `min_max_of_children`（CHGIS，子记录区间的包络）/ `tpq_taq_of_children`（Pleiades，子记录 TPQ/TAQ 的包络）/ `none`（无可聚合）。实测 `15718 / 1816 / 1505`。 |
| `notes` | 分组依据、`type_py`/`lev_rank`、映射依据、源标记等。 |

#### `historical_place_locations.csv`

一条 CHGIS 记录 = 一行；一个 MCGD `LocID` = 一行；一条 Pleiades `location_points` = 一行；
一个 WHG `geoms[]` 元素 = 一行。

| 字段 | 说明 |
|---|---|
| `lon` / `lat` | 数值化坐标。 |
| `geom_wkt` | `POINT(lon lat)`；坐标缺失时为空。 |
| `representative_lon` / `representative_lat` | 目前与 `lon`/`lat` 相同（单点几何）。 |
| `original_x` / `original_y` | 原文（CHGIS `X_COOR`/`Y_COOR`；MCGD `LONG`/`LAT`；Pleiades WKT 的 X/Y；WHG `geowkt` 的 X/Y），能识别 `**********` 溢出标记。 |
| `original_crs` | CHGIS / Pleiades：`EPSG:4326`。MCGD：**`unknown`**。 |
| `crs_confidence` | CHGIS `confirmed`（`.prj` 原文）；Pleiades `confirmed`（`gis_README.md` 明写 WGS84）；WHG `inferred`（JSON-LD 是 GeoJSON，RFC 7946 强制 WGS84）；MCGD **`unknown`**（无任何 datum 声明）。 |
| `axis_order_verified` | 全部 `true`，依据见决策 6。 |
| `location_precision` | CHGIS/MCGD `point`；Pleiades 保留其自身的 `precise` / `rough`（2,460 条全部 `precise`）。 |
| `uncertainty_m` | 仅 Pleiades 有值：复制其 `accuracy_radius`（米）。其余源为空（源未提供）。 |
| `valid_from_year_astro` / `valid_to_year_astro` | 天文纪年。时间倒挂记录**留空**；`snapshot` 记录两列相同。 |
| `time_bound_type` | 见决策 5。实测分布 `exact 8057 / bounded 400 / exact_or_bounded 812 / snapshot 21 / tpq_taq 3326 / unknown 9315`。 |
| `time_rule_code` | CHGIS 原始 `BEG_RULE|END_RULE`（如 `6|9`、`|9`、`|`）；Pleiades `year_after_which|year_before_which`；其余源空。 |
| `quality_flag` | `beg_gt_end` / `missing_coordinate` / `coordinate_out_of_range` / `coordinate_outside_china_bbox` / `crs_unknown` / `z_ordinate_discarded`，多值时用 `\|` 连接。 |
| `source_record_id` | 指向 `source_records.csv`。 |

> **`snapshot` 与 `exact` 的区别（必读）**
> `exact` 的两列是**有效期**："这个治所在 553 年到 582 年有效"。
> `snapshot` 的两列是**记载时点**："这一行数据取自 582 年这个时间切片"，两列相同。
> 把 `snapshot` 当成有效期会把"最后一次被记载"读成"到 582 年为止还存在"，
> 从而凭空截断实体寿命。原始 `BEG_YR`/`END_YR` 保存在
> `source_records.raw_payload_json` 与 `issues/chgis_all_records.csv`，
> 并在本表 `notes` 里逐条重述，信息没有丢失。

#### `historical_place_names.csv`

每条 CHGIS 记录产生 1–3 行，每条 MCGD 记录 1 行，每条 Pleiades `names` 1 行，
每条 WHG `names[]` 元素 1 行。

| 来源 | `name_lang` | `name_script` | `name_type` | `transliteration_scheme` |
|---|---|---|---|---|
| CHGIS `NAME_CH` | `zh` | `Hani` | `primary` | 空 |
| CHGIS `NAME_PY` | `zh-Latn` | `Latn` | `transliteration` | `pinyin` |
| CHGIS `NAME_FT`（≠`NAME_CH` 时） | `zh` | `Hant` | `alternate` | 空 |
| MCGD `Name` | `zh-Latn` | `Latn` | `primary` | `wade_giles_probable` |
| Pleiades `names` | `language_tag` 或 `und` | 空 | `primary`/`alternate` | 空 |
| WHG `names[]` | `und` | 空 | 第一个 `primary`，其余 `alternate` | 空 |

> **语义提醒**：名称的 `valid_from/to` 是"**该名称在该时段用于该实体**"的证据，
> **不是**地点存在时间。Pleiades 名称行带的是 **TPQ/TAQ**（`time_bound_type='tpq_taq'`），
> 含义是"该名称在两者之间某处被使用"，**不主张**区间内连续。

#### `source_records.csv`

一行 = 一条源记录（15,748 CHGIS + 960 MCGD + 12,445 Pleiades + 238 WHG = 29,391）。
Pleiades 的 220 条 `time_periods` 是**参考词表**，只计数不建行（见 `stats.json → sources`）。

- `dataset_id`：指向 `data_datasets.csv`，7 行无一为空。实测分布
  `chgis_v6_county_points 10522 / chgis_v6_prefecture_points 5226 /
  mcgd_zenodo_22094815_head960 960 / pleiades_gis_4_1_slice 12445 /
  whg_geoname_s_gn_sample 209 / whg_getty_tgn_sample 21 /
  whg_hgis_de_las_indias_sample 8`。
- `raw_file` 为项目根相对路径。
- `raw_payload_json` 存该记录全部原始字段的紧凑 JSON（`sort_keys` 保证确定性）。
  CHGIS/MCGD 实测 **7,188,521 字节**，低于 25 MB 阈值，使用全量模式；
  Pleiades/WHG 始终 `non_empty_only`（实测 6,256,904 字节）——
  Pleiades `places.csv` 11 列里样本能填满的通常不到 5 列，留空会白耗预算。
  两个策略都在 `stats.json → tables.raw_payload` 里标注。
- 许可/引用来自 `data_datasets.csv` 的同一行（`license_status` / `redistributable` /
  `attribution_text` 逐记录复制），因此逐记录与数据集级不可能漂移。

#### `data_datasets.csv`

**第七张表**。一行 = 一个已导入数据集，共 7 行。字段：
`dataset_id, source_id, dataset_name, homepage, license_id, license_url,
redistributable, attribution_text, acquisition_method, evidence, notes`。

| `dataset_id` | `license_id` | `redistributable` |
|---|---|---|
| `chgis_v6_prefecture_points` | `no_spdx_academic_noncommercial` | `no` |
| `chgis_v6_county_points` | `no_spdx_academic_noncommercial` | `no` |
| `mcgd_zenodo_22094815_head960` | `CC-BY-4.0` | `yes_with_attribution` |
| `pleiades_gis_4_1_slice` | `CC-BY-3.0` | `yes_with_attribution` |
| `whg_geoname_s_gn_sample` | `CC-BY-4.0` | `yes_with_attribution` |
| `whg_getty_tgn_sample` | `ODC-By-1.0` | `yes_with_attribution` |
| `whg_hgis_de_las_indias_sample` | `unconfirmed` | `unconfirmed` |

CHGIS 拆两行、WHG 拆三行，因为"一个源"不等于"一个许可单元"：CHGIS 两层字段完整性
不同，WHG 三个上游资料馆的许可不同且**逐记录**声明。

#### `data_quality_issues.csv`

实测 12,631 行（`info 11,605 / warning 658 / blocking 368`）：

| `issue_type` | `severity` | 行数 | `action_taken` |
|---|---|---|---|
| `unknown_time_bound_type` | `info` | 6,448 | `preserved_and_flagged` |
| `parent_place_not_in_sample` | `info` | 4,810 | `preserved_and_flagged` |
| `unknown_crs` | `warning` | 646 | `needs_manual_review` |
| `beg_eq_end` | `info` | 341 | `preserved_and_flagged` |
| `missing_coordinate` | `blocking` | 337 | `preserved_and_flagged` |
| `beg_gt_end` | `blocking` | 28 | `preserved_and_flagged` |
| `coordinate_outside_china_bbox` | `warning` | 6 | `needs_manual_review` |
| `truncated_slice_tail` | `info` | 4 | `discarded` |
| `year_out_of_range` | `warning` | 4 | `preserved_and_flagged` |
| `duplicate_sysid` | `warning` | 2 | `needs_manual_review` |
| `licence_unconfirmed` | `blocking` | 2 | `needs_manual_review` |
| `nonstandard_field_name` | `info` | 2 | `preserved_and_flagged` |
| `coordinate_out_of_range` | `blocking` | 1 | `preserved_and_flagged` |

合计 12,631 行。

`parent_place_not_in_sample` 的 4,810 行是**逐行**写的，不是聚合：
这些 Pleiades/WHG 子行（name / location / connection）的父地点落在 1 MB 切片窗口
之外，因此永远不会进入 `historical_places`；如果不逐行记，它们只存在于
`source_records` 里而无法被检索。逐行写才能和 `source_record_id` 直接 join。

`unknown_time_bound_type` 按**记录**聚合成一行（列出所有空/未记录的规则字段），
否则仅县级层就会产生 12,000+ 行重复条目。

#### `candidate_matches.csv`

只输出候选，**绝不合并**。`reviewer` / `reviewed_at` 全部留空。实测分布：

| `relation_type` | 行数 | 来源 |
|---|---|---|
| `same_coord_diff_entity` | 34,012 | 空间证据：不同地点共用精确同一坐标 |
| `homonym_diff_place` | 14,536 | 名称证据（<200 km 的对）+ 规则推断（>300 km 的相邻对） |
| `same_entity_same_seat` | 2,331 | 规则推断：同名同层相邻年段、坐标完全相同 |
| `location_migration_candidate` | 1,866 | 规则推断：同名同层相邻年段、坐标不同且 ≤300 km |
| `pleiades_connection` | 390 | 源断言：Pleiades `connections.csv` 两端都在切片内 |
| `true_duplicate_suspected` | 2 | 同 SYS_ID + 同坐标 + 同年段，仅物理记录号不同 |

`status`：`candidate` 51,269 / `needs_manual_review` 1,868。

体积控制：坐标簇两两全配对（最大簇 34 条 → 561 对，无爆炸风险，未做截断）；
同名异地按"（地点, 坐标）代表 + 成员"降重后取最近 25,000 对，被截断数量写入
`stats.json → tables.candidate_truncation_notices`（本轮 0 条）。

#### `stats.json`

所有关键计数。**报告里的每个数字都应从这里取值，不得手抄。**
顶层键：`pipeline_version` / `python_version` / `ingested_at` /
`sources` / `chgis` / `time` / `time_bound_type` / `structure` / `clusters` /
`homonyms` / `mcgd` / `cross_layer_disagreements` / `migration` / `review_queue` /
`data_datasets` / `tables` / `provenance` / `astro_assertions` / `issues` /
`output_row_counts`。

（**没有** `run_started_utc`：运行时刻属 provenance，只写 `run_manifest.json`，
这样固定 `--timestamp` 时 `stats.json` 才是逐字节稳定的。）

本轮为任务 A/B/C 显式补上的键：

- `sources` —— 四个源各自的记录数、地点数、切片文件清单
  （如 `sources.pleiades.discarded_tail_row_count`）。
- `time_bound_type.distribution` —— 记录级 `time_bound_type` 分布；
  `time_bound_type.place_level_distribution` / `place_level_derivation` —— 地点级；
  `time_bound_type.denominator` —— 记录级分布的分母构成
  （`chgis_records 15,748 + mcgd_rows 960 + extra_child_rows 5,223 = total 21,931`）。
  这一项是后补的：分布由三个不同循环累加，**总数没法从任何一张输出表反推**，
  不加这个键就只能手算，而手算正是上一版把 MCGD 写成 643、把子记录写成 5,540 的原因。
- `data_datasets.rows` —— `data_datasets.csv` 的行数（7）。

#### `run_manifest.json`

输入/输出 SHA256、行数、字节数、运行时间、Python 版本、`pipeline_version`、
每阶段耗时、天文纪年断言结果、输入完整性前后对比、`migration_ground_truth`。

---

### `issues/`

| 文件 | 内容 |
|---|---|
| `chgis_all_records.csv` | 15,748 条原始记录，全部 23 个 DBF 字段 + `source_dataset` / `record_index` / `raw_zip` / `raw_dbf`。字段顺序为两层并集（首见顺序），所以 `GEOCOMPLR` 与 `GECOMPLR` 各占一列。 |
| `time_inversions.csv` | 28 条 `BEG_YR > END_YR`，含 `delta_years`。**不修复、不交换**。 |
| `coordinate_clusters.csv` | 每个精确坐标一行（6,013 行）：记录数、SYS_ID 数、名称数、四类配对计数、分类标签。 |
| `cluster_members.csv` | 上述簇的成员明细（15,738 行）。 |
| `homonyms.csv` | 出现在 ≥2 个坐标的 `NAME_CH`（2,071 行）：坐标数、SYS_ID 数、包围盒、是否跨省。 |
| `cross_layer_disagreements.csv` | 同名 **且** 同 (BEG_YR,END_YR) 却在府级/县级两层给出不同坐标的实体（29 行）。 |
| `migration_chains.csv` | 规则化迁治链条候选（1,254 行）：`seat_count >= 2` 且至少含 1 条 `location_migration_candidate`。全部 `needs_manual_review=true`。 |
| `migration_review_queue.csv` | **本轮新增**：1,866 条已接受的迁治腿，**按优先级排序（P1 在最前）**。见决策 9。 |

#### `migration_review_queue.csv` 字段

| 字段 | 说明 |
|---|---|
| `priority` | `P1` 87 / `P2` 161 / `P3` 1618。只表示**审核顺序**，不表示"是否真迁治"。 |
| `name_ch` / `source_dataset` | 分组键。 |
| `leg_distance_m` / `gap_years` | 这一腿的球面距离（米）与 `B.BEG_YR - A.END_YR`。 |
| `confidence` | 原样复制，**只反映年隙紧密度**。 |
| `from_coord` / `to_coord` | `lon\|lat`。 |
| `from_pres_loc` / `to_pres_loc` | 两侧 `PRES_LOC`（今地名），给人读的锚点。 |
| `review_hint` | 该优先级的审核提示。 |

**排序规则（本轮按裁决调整过）**：

```
priority ASC (P1 → P2 → P3)  →  leg_distance_m DESC  →  gap_years ASC
```

**为什么 `priority` 是主键**：这份队列的用途是**让人先看 P1**。原先按
`leg_distance_m DESC` 排，文件头几行是 299 km 但 `confidence=low` 的 P3，
而 87 条 P1 埋在中间——排序把用途废掉了。现在打开文件，**头 87 行就是最该复核的**。

**两种视图都成立**：`leg_distance_m` 降序视图仍可直接对该列排序得到；文件默认顺序
只服务人工复核。`stats.json → review_queue.definition` 里写的是同一个规则。

次键用的是**写出来的那个值**（`round(distance, 1)`），不是原始浮点数。原因：CSV 里
距离只保留 1 位小数，两条相差 6 cm 的腿会写成同一个数，若按原始浮点排序，读者拿
`leg_distance_m` 列重新排序就会看到"逆序"（本轮实测过 1 处：`襄垣县`（772.6 / gap 1）
排在 `韩州`（772.6 / gap 12）之后——两条腿原始距离相差不到 0.1 m，写出来是同一个数）。
改用写出值排序后，按 `priority ASC, leg_distance_m DESC, gap_years ASC` 复核
1,866 行**零逆序**。

---

## 关键设计决策

### 1. 地点身份：一个 distinct SYS_ID = 一个 historical_place

按规格实现。但**必须记录的反证**：CHGIS 数据字典
（`v6_data_dictionary.xlsx`）对 `SYS_ID` 的原文是

> `unique ID for the spatial object [can only occur once in the gisinfo_table]`

即 `SYS_ID` 标识**空间对象**，不是持续的行政实体。实测也支持这一点：
15,748 条记录中 **15,746 个 SYS_ID 只出现一次**（府级 2 个重复 = 完全重复行）。

**推论（重要）**：CHGIS 点层**无法**用"SYS_ID 重复"来证明迁治。
一次迁治在点层体现为**两个不同 SYS_ID、两个不同坐标**。因此
`candidate_matches.csv` 里同-SYS_ID 的 `location_migration` 条数为 0，
不是漏算，而是数据结构使然。

→ 迁治因此另建了一层规则化推断，见 **决策 7/9**。

### 2. 时间倒挂一律不修复

`BEG_YR > END_YR` 的 28 条记录（府 9 + 县 19）：原始年份原样保留在
`source_records.raw_payload_json` 与 `issues/time_inversions.csv`，
`valid_from/to` 留空，`time_bound_type='unknown'`、`quality_flag='beg_gt_end'`。
**不交换、不夹取、不改写**——交换会凭空创造一个史料不支持的历史主张。

判定口径（严格）：`BEG_YR` 与 `END_YR` **都必须是数值**，且 `BEG_YR > END_YR`。
空年份与 `BEG_YR == END_YR`（341 条）分别单列，**不计入** 28。

### 3. `place_type` 映射规则

来源：`LEV_RANK`（CHGIS 数据字典未描述该字段，映射由实测构成推出）。

| `LEV_RANK` | `place_type` | 实测源记录条数 |
|---|---|---|
| `3` | `admin_center_prefecture` | 5,205 |
| `6` | `admin_center_county` | 10,524 |
| `0` / `1` | `admin_center_other` | 18 |
| 空 / 未映射 | `unknown` | 1 |
| MCGD / Pleiades / WHG | `unknown` | 643 + 2,643 + 7 |

`LEV_RANK` 与所属图层不一致的**记录**共 **21** 条，见
`stats.json → tables.lev_rank_vs_layer_disagreements`，并在 `places.notes` 里逐条标注。

### 4. 天文纪年

`astro = year + 1 if year < 0 else year`（CHGIS 无 0 年）。
`run_all.py` 启动时断言 `-221 → -220`、`1 → 1`、`1911 → 1911`、`None → None`、
`0 → ValueError`，结果写入 `run_manifest.json` 与 `stats.json → astro_assertions`。

**Pleiades 用同一套转换**：`gis_README.md` 对 `year_after_which` 的原文是
"a signed integer indicating a year in the **proleptic Julian calendar**.
**There is no year zero**" —— 与 CHGIS 同约定，所以不写第二个转换函数。

### 5. `time_bound_type` 依据（替代 `time_basis`）

旧版只有一个 `time_basis`（`source_attested` / `estimated` / `mixed` / `unknown`）。
它表达不了两件事，因此 1.2.0 版删除它，改为 `time_bound_type` + `time_rule_code`：

1. **TPQ/TAQ**：Pleiades 给的是 `year_after_which`（terminus post quem）与
   `year_before_which`（terminus ante quem）。写成 `source_attested` 等于声称
   "该地名在整个区间内连续存在"，而源只说了"在两者之间某处"。
2. **快照 vs 区间**：规则码 `9` 在字典里的原文是
   "Dated is set to a specific year based on the source materials used,
   **not based on the valid span of time**"。旧版把它归到 `estimated`，
   于是 21 条 `END_RULE=9` 的记录里有 20 条（`BEG_YR != END_YR`）被渲染成
   看起来很确定的多年区间，而且**完全不在** `beg_gt_end` 的检查范围内。

`xtra_date_rules.xlsx` 已用 `zipfile + xml.etree` 成功解析（7 条规则）：

| code | rule_short_name | rule_eng（原文） |
|---|---|---|
| 1 | Pan-Dynastic period | Year is set according to a pan-Dynastic period |
| 2 | Dynastic period | Year is set according to a Dynastic period |
| 3 | Reign period | Year is set according to a Dynastic Title or Reign Period |
| 4 | Specific year | Year is specified |
| 5 | Specific month | Season or Month is specified |
| 6 | Specific date | Date is specified |
| 9 | Time slice | Dated is set to a specific year based on the source materials used, **not based on the valid span of time** [both Begin and End values will be the same] |

**CHGIS 映射（`(BEG_RULE, END_RULE)` → `time_bound_type`）**：

| 顺序 | 条件 | `time_bound_type` |
|---|---|---|
| 1 | 任一端为 `9` | `snapshot` |
| 2 | 两端都在 `{4,5,6}` | `exact` |
| 3 | 两端都在 `{1,2,3}` | `bounded` |
| 4 | 一端在 `{4,5,6}`、另一端在 `{1,2,3}` | `exact_or_bounded` |
| 5 | 其余（空 / `0` / `7` / `8` / 一端为空） | `unknown` |
| — | 28 条时间倒挂 | `unknown` + `quality_flag='beg_gt_end'` + 年份留空（优先级最高） |

规则 1 排在最前是刻意的：`BEG_RULE=6, END_RULE=9` 这类混搭里，片段码是更强的
"这一行怎么产生"的陈述，所以整条记录降级为 `snapshot`，而不是 `exact_or_bounded`。

**`snapshot` 的年份取法**：切片年是**带 9 的那一端**。实测 21 条全部在 `END` 侧
（其中 1 条两端都是 9 且年份不同 —— `赤峰州` 1908/1911），所以取 `END_YR`；
`valid_from_year_astro` 与 `valid_to_year_astro` **都填该切片年**，
原始 `BEG_YR`/`END_YR` 写进 `notes`。取法依据记在
`stats.json → time_bound_type.snapshot_basis_counts`
（`end_rule_9` 20 / `end_rule_9_conflict_with_begin_rule_9` 1）。

**其他源**：MCGD → `unknown`（CSV 无任何时间列）；WHG → `unknown`
（只有 2/5 条 JSON-LD 记录带 `when.timespans`，扁平记录只有数据集级 `minmax`，
都不是逐地点的有效期）；Pleiades → 名称/坐标行 `tpq_taq`，
地点行 `unknown` 并由子记录聚合为 `derived_tpq_taq`。

**地点级聚合口径**：CHGIS 取子记录区间的包络（`min_max_of_children`）；
只有当所有子记录的 `time_bound_type` 一致且不含 `snapshot` 时，地点级才沿用该值，
否则降为 `unknown` —— 地点不比它最弱的记录更确定。Pleiades 取
`tpq_taq_of_children`（最早 TPQ、最晚 TAQ）。MCGD/WHG 为 `none`。

**分布**（口径见 `stats.json → time_bound_type.denominator`：记录级合计 21,931 =
CHGIS 15,748 条 + MCGD 960 行 + Pleiades/WHG **挂得上父地点的子记录 5,223** 条；
不计入 Pleiades/WHG 的 place 行（本身不带年份）与 4,810 条孤儿子记录）：
- 记录级：`exact 8,057 / unknown 9,315 / tpq_taq 3,326 /
  exact_or_bounded 812 / bounded 400 / snapshot 21`。
- 地点级：`exact 8,055 / unknown 7,937 / derived_tpq_taq 1,816 /
  exact_or_bounded 812 / bounded 398 / snapshot 21`。

`unknown` 偏高是结构性的：县级 10,522 条里 6,136 条 `BEG_RULE` 为空，
而 Pleiades 2,643 个地点里只有 1,816 个有可用的子记录 TPQ/TAQ。

### 6. 坐标轴序与 CRS 信心：三列各管一件事

三列常被混为一谈，因此把分工写死：

| 列 | 回答的问题 | 取值来源 |
|---|---|---|
| `original_crs` | **源声明**了什么坐标系？ | 源有声明就写，没有就 `unknown` |
| `crs_confidence` | **我们有多确定**这些坐标真的是 EPSG:4326？ | **只能由声明/格式强制推出**，不得由"数值看着合理"推出 |
| `axis_order_verified` | **轴序**核实了吗？ | 与 CRS 信心是**两个独立问题** |

`crs_confidence` 的取值规则：

| 取值 | 判定 | 适用 |
|---|---|---|
| `confirmed` | 源**明确声明** WGS84 | CHGIS（`.prj` = `GEOGCS["GCS_WGS_1984"]`）；Pleiades（`gis_README.md` 明写 WGS84） |
| `inferred` | 源无声明，但**该格式规范强制要求 WGS84，且文件确实符合该规范** | WHG 的 5 条 JSON-LD 记录（符合 RFC 7946 的 GeoJSON 文档，规范本身把 CRS 定为 WGS84） |
| `unknown` | 源无声明且格式不强制 | **MCGD**（9 列表头无任何 crs/datum/srid）；**WHG 的 3 条旧扁平记录**（`169687*.json`） |

> **`inferred` 的适用前提是"该格式规范强制要求 WGS84 且文件确实符合该规范"，
> 仅具备形状不算。**
>
> 这条判据是本轮补上的，起因是一个具体案例：WHG 的 `169687.json` /
> `169687-169688.json` 的 `geoms[]` 元素长这样——
> `{"type":"Point","geowkt":"POINT(-99.27 19.36)","coordinates":[-99.27,19.36]}`——
> 有 `coordinates`、有 `type`，**看着像 GeoJSON**。但整个文件没有 `@context`、
> 没有 `crs` 成员、也没有 `attribution` 块，它只是一段**形状像 GeoJSON 的普通 JSON**，
> 不构成符合 RFC 7946 的文档。给 `inferred` 等于把"长得像"当成"格式强制"，
> 与 MCGD 那次纠正（把"数值看着合理"当 CRS 证据）是同一类错误。
> 所以这 3 条判 `unknown`，`original_crs` 也写 `unknown`，并带上
> `quality_flag='crs_unknown'` 与 `unknown_crs` warning。
>
> **判据必须一以贯之**：MCGD 无声明、无格式强制 → `unknown`；这 3 条同样
> 无声明、无格式强制 → 也必须 `unknown`。否则同一套规则在两个源上给出
> 不同结论，将来没人能解释为什么。
>
> 结果是 `crs_confidence` **按行判定、不按源判定**：WHG 一个源内部
> `inferred 5 / unknown 3`，见下表。

**MCGD 必须是 `unknown`，不是 `inferred`。** 9 列表头里没有任何
crs / datum / srid 声明；坐标数值落在合理范围只是**合理性检验**，不是 CRS 证据。
把它写成 `inferred` 会让下游导入器绕过 CRS 门禁直接发布，
等于把基准面未知、可能偏几百米的坐标放上地图；而且同一行的
`quality_flag` 里已经写着 `crs_unknown`，两列会互相打脸。
（这条是团队在复查时纠正的，最初规格写错了。）

**轴序与 CRS 信心不矛盾。** MCGD 的轴序可由列名 `LAT`/`LONG` 加物理不可能反证
（`LONG` 有一行 = 881.41，若是纬度则不可能）⇒ `axis_order_verified='true'`，
同时 `crs_confidence='unknown'`。两句话说的不是一件事。

> **WHG 一个源内部两种取值，是本轮一处裁决的结果**：那 3 条旧扁平记录
> 判 `unknown` 而不是 `inferred`（理由见上面 `inferred` 前提那段）。它们现在是
> 与 MCGD 一样被 CRS 门禁挡住的 3 条，**在补齐基准面证据前不可发布**。

**WHG 的 `axis_order_verified='true'` 是反证法，不是源声明**：WHG 单记录模板
里没有任何轴序字段，判定依据是 `geoms[].geowkt`（WKT 是 X Y = 经纬）与同一元素
的 `geoms[].coordinates`（`[lon, lat]`）互相印证，以及数值本身落在该地名的
真实经纬度上。

各源实测分布（`stats.json → tables.crs_confidence_counts`）：

| 源 | 条数 | `original_crs` | `crs_confidence` |
|---|---|---|---|
| CHGIS | 15,748 | `EPSG:4326` | `confirmed` |
| Pleiades | 1,704 | `EPSG:4326` | `confirmed` |
| WHG（JSON-LD，5 条） | 5 | `EPSG:4326` | `inferred` |
| WHG（旧扁平，3 条） | 3 | `unknown` | `unknown` |
| MCGD | 643 | `unknown` | `unknown` |

分布（`→ tables.crs_confidence_counts`）：
`chgis:confirmed 15,748 / pleiades:confirmed 1,704 / whg:inferred 5 / whg:unknown 3 /
mcgd:unknown 643`，合计 **18,103**（= `historical_place_locations` 行数）。
**同一个源可以同时出现两种取值**，所以这张表按 schema 拆行、不按源合并。

**轴序判定依据**：

CHGIS：`.prj` = `GEOGCS["GCS_WGS_1984"]`，且 `X_COOR` 出现 `108.937190` 等值——
若当纬度则 > 90 物理不可能 ⇒ `X_COOR`=经度、`Y_COOR`=纬度。

MCGD：列名 `LAT`/`LONG` 已明示轴序；`LAT` 全样本落在 [18.53, 53.33]，
而 `LONG` 有一行 = 881.41 ⇒ 轴序可确认，但 CRS 仍 `unknown`。

Pleiades 有**两种**约定同时存在，这是最容易搞反的地方：
- `places.csv` 用**命名列** `representative_latitude` / `representative_longitude`；
- `location_points.csv` 用 **WKT**，而 WKT 是 X Y。

`gis_README.md` 第 13 行直接写明 "Set X = `representative_longitude` and Y =
`representative_latitude`"，因此 WKT 的 X 是经度。搞反会让整个古典世界镜像翻转。
`location_points` 里另有 1 条 `POINT Z`，Z 值被丢弃并在 `quality_flag` 记
`z_ordinate_discarded`（本表二维）。

WHG 两种 schema：JSON-LD 的 `geometry` 是 GeoJSON，序为 `[lon, lat]`；
扁平 schema 的 `geoms[].geowkt` 是 WKT，同样是 X Y = 经纬。两条都用同一批坐标的
`coordinates` 数组交叉验证过。

### 7. 迁治（迁治链条候选）：为什么必须另建一层，怎么建

**为什么"1 个 SYS_ID = 1 个地点"建不出迁治。** 字典原文说 `SYS_ID` 是
"unique ID for the **spatial object**"，实测 15,746/15,748 个 SYS_ID 只出现一次。
所以"同一 SYS_ID 出现在两个坐标"这件事**在数据里不可能发生**。
迁治在点层里表现为**一串坐标不同的独立记录**，必须另起一层规则来推断。

**实体身份改为 `(NAME_CH, source_dataset)`。** 同一名称在同一行政层级内、
年段首尾相接的记录，最可能是同一实体的延续。**跨层级永不合并**。

组内按 `BEG_YR` 升序；`BEG_YR` 为空的记录不参与配对（实测 0 条）。
实测 8,525 组、15,748 条记录全部可定位到时间轴、7,223 个相邻对。

**相邻对判定阶梯**（`gap = B.BEG_YR - A.END_YR`，`dist = haversine(A,B)`）：

| 顺序 | 条件 | `relation_type` | `confidence` |
|---|---|---|---|
| 1 | `dist > 300 km` | `homonym_diff_place` | high |
| 2 | `gap < -2` | `period_overlap`（不出行） | — |
| 3 | `dist == 0` 且 `gap <= 2` | `same_entity_same_seat` | high |
| 4 | `dist == 0` 且 `gap <= 60` | `same_entity_same_seat` | medium |
| 5 | `0 < dist <= 300 km` 且 `gap <= 2` | `location_migration_candidate` | high |
| 6 | `0 < dist <= 300 km` 且 `gap <= 10` | `location_migration_candidate` | medium |
| 7 | `0 < dist <= 300 km` 且 `gap <= 60` | `location_migration_candidate` | low |
| 8 | 其余（`gap > 60`） | `temporal_gap_too_large`（不出行） | — |

实测各支命中数：`homonym_diff_place 1,456 / period_overlap 308 /
same_entity_same_seat 2,331 / location_migration_candidate 1,866 /
temporal_gap_too_large 1,259 / coordinate_missing 3`。

**为什么把 `dist > 300 km` 提到最前面**：顺序 3–7 全都要求 `dist <= 300 km`，
所以提前判断**不改变任何一条的归类**，只在"距离远"与"年段重叠"之间决定优先级。

**为什么 `gap < -2` 不判迁治**：年段重叠意味着这对年份里至少一个不可信。
跨越不可信年份去推"迁治"，等于把坏日期洗成一条看起来很确定的结论。

**所有阈值都是模块常量**（`MIGRATION_MAX_LEG_M`、`GAP_*`），改一行即可重跑不同切法。

#### Ground-truth 回归（每次运行都跑，结果进 `stats.json → migration.ground_truth`）

**`新兴郡` @ `chgis_pref` —— PASS。** 6 条记录、4 个坐标，按 `BEG_YR` 排序后 5 条相邻对：

| A → B | gap | dist | 判定 |
|---|---|---|---|
| 215–295 @ 忻州 → 300–445 @ 忻州 | 5 | 0 m | `same_entity_same_seat` medium |
| 300–445 @ 忻州 → 446–528 @ 定襄 | 1 | 21,266.7 m | `location_migration_candidate` **high** |
| 446–528 @ 定襄 → 581–583 @ 忻州南三十里 | 53 | 31,589.6 m | `location_migration_candidate` low |
| 581–583 @ 忻州南三十里 → 617 @ 忻州 | 34 | 15,217.5 m | `location_migration_candidate` low |
| 617 @ 忻州 → 742–757 @ 广东新兴 | 125 | **1,745,946.6 m** | `homonym_diff_place` high |

链条 = 前 4 条边 → **`seat_count = 3`**，坐标恰为忻州 / 定襄 / 忻州南三十里；
广东新兴因超过 300 km 上限被判 `homonym_diff_place`，**在链外**。
脚本实测：`seats=3`，三个期望坐标全部命中，`foreign_seat_excluded_from_chain=True`。

**`中山国` 反例 —— PASS（未被误判）。** 府级 7 条全在 `114.563995|38.140121`，
县级 7 条全在 `114.975040|38.520060`，年段一一对应。脚本实测：
`cross_layer_edges = 0`、两条链 `seat_count` 均为 **1**、`migration_chains = 0`。

> 需要更正的归因：**不是**"gap 因年段相同而不满足条件" —— 同层内相邻年段的
> gap 分别为 13/7/25(27)/5/11/59 年，全部落在 `<= 60` 的射程内。
> 真正起作用的**第一道**防线是 **`(NAME_CH, source_dataset)` 分组**
> 让跨层对根本无法进入比较；第二道防线是同层内 7 条记录**只有一个坐标**，
> `dist == 0` 使链条塌缩成 `seat_count == 1`，不满足"迁治链"定义。

断言失败时**不改数据、不调阈值迎合**，只在控制台打印 `FAIL` 并把实测值写进
`stats.json → migration.ground_truth` 与 `run_manifest.json`。

### 8. Pleiades / WHG 导入：五个必须显式处理的坑

1. **每个切片末尾有一行被字节截断。** 5 个文件都用固定 Range 取（`bytes=0-1048575`
   或 `0-524287`），最后一个 CSV 记录字段数少于表头。它们是**传输截断**，不是坏数据，
   因此丢弃并计数（`issue_type='truncated_slice_tail'`，实测 4 条：
   `places` 3/11 字段、`names` 12/19、`location_points` 2/16、`connections` 10/13；
   `time_periods.csv` 是完整文件，0 条）。
   有效行数：places 2,643 / names 4,579 / location_points 2,460 /
   connections 2,763 / time_periods 220。
2. **轴序两套约定并存**（见决策 6）。
3. **`places.csv` 没有时间列。** 尽管 `gis_README.md` 把 `year_after_which` /
   `year_before_which` 列为 "Applies to: ... `places.csv`"，实际切片里这两列不存在。
   所以地点级 TPQ/TAQ 只能从 `names.csv` 与 `location_points.csv` 聚合，
   `time_derivation='tpq_taq_of_children'`。这是**文档与数据的矛盾**，记为已知限制。
4. **一对多**：一个 Pleiades place 可有多条 name、多条 location。
   2,460 条 location 里 **756 条**的 `place_id` 不在切片内，
   4,579 条 name 里 **2,505 条**同样。这些行是真数据，父地点只是落在 1 MB 窗口之外，
   所以保留在 `source_records` 并标 `parent_place_not_in_sample`（info），
   **不丢弃、不臆造父行**。
5. **place 级的几何也必须落成 location 行。** `historical_places` 表**没有坐标列**，
   所以只把坐标写在 place 记录上的话，它会在规范化层**静默消失**。
   WHG 的 JSON-LD 就是这种情况：`geometry` 挂在 place 上，第一版只写进了
   place 记录的 `notes`，结果 5 条 gn/tgn 地点在 `historical_place_locations`
   里一条 location 都没有（当时该表 WHG 只有 3 条 WKT 的 location）。
   现已为 JSON-LD 的 `geometry.type=Point` 补发 location 行
   （`external_id='<source_id>#geom1'`），WHG 的 location 由 3 条变为 8 条。
   **教训**：新增任何源时，先确认"坐标最终落在哪张表"，别假设 place 上的坐标会被自动下推。

WHG 的两个 schema 不是外观差异：JSON-LD（5 条）带完整 `attribution` 块，
逐记录声明许可（`gn`→`CC-BY-4.0`、`tgn`→`ODC-By-1.0`）；
旧扁平 schema（2 条，HGIS de las Indias）**完全没有** `attribution` 键，
也没有任何匹配 `licen`/`right`/`attribut` 的键。回退到 `sources.json` 只能确认
`redistributable: true`，不能确认"以什么许可"，所以记 `license_id='unconfirmed'`、
`redistributable='unconfirmed'`，并写 `licence_unconfirmed`（`blocking`）issue。
`169687-169688` 是**复合记录**：WHG 自己的 id 把两个聚落并成一个地点、带两个几何，
因此保留为一个 place + 两条 location。

### 9. 阈值不收紧，改用审核队列（`confidence` 语义冻结）

`confidence` **只**反映年隙紧密度：`gap <= 2` 就是 `high`，无论这一腿走了 4 km 还是 250 km。
所以 1,866 条迁治腿里有 **87 条是 >100 km 且 `high`**。

**决定：不收紧 `MIGRATION_MAX_LEG_M`。** 因为长距离移治在史料里真实存在
（`扬州` 安徽寿县 → 江苏扬州，250 km，`gap=1`），收紧这个上限会把真事件一起拒掉。

**决定：`confidence` 的语义保持不变、不再扩展。** 它编码的是年隙，不是真实性。
真实性必须从 `leg_distance_m` 与 `issues/migration_review_queue.csv` 判断。
`priority`（P1/P2/P3）只是审核排序，定义见上文"`migration_review_queue.csv` 字段"。

**所有阈值都是人设的边界，两个实测证据**：

- **上边界**：`颍阳县`（`chgis_cnty`）的一腿是 **299,597.4 m**，比
  `MIGRATION_MAX_LEG_M = 300,000 m` **只低 402.6 m**，因此被判为
  `location_migration_candidate`；同样一条腿只要长 403 m 就会被判 `homonym_diff_place`。
  同一个名字在 `homonym_diff_place` 里另有 0 m 与 92,070.9 m 两种配对。
- **下边界**：`dist == 0.0` 判同座、`dist > 0.0` 判迁治，所以
  `恒山郡` / `中山郡` 那条 **0.4 m** 的腿被规则当成"迁治"，
  `中牟县` 是 **0.9 m**。这不是地理事实，而是浮点比较的后果。

两条都保留原样：它们说明"阈值"是可复核的人为切点，而不是数据里的自然分界。

---

## 与架构模型 V2 的对齐与差异

`设计资料/P0收敛/架构/CORE_DATA_MODEL_V2.md` 是**入库层**模型，本目录产出的是
**暂存层** CSV。两者有三处刻意不同，都不是疏漏，改动前请先看这里。

### 一致的部分

- `time_bound_type` 的 **7 值域完全一致**：
  `exact / bounded / exact_or_bounded / tpq_taq / derived_tpq_taq / snapshot / unknown`。
  本流水线**不使用 `mixed`** —— 那个词属于已删除的 `time_basis`（旧实测 828 条），
  复用会制造歧义。
- CHGIS 规则映射判据一致：4/5/6→`exact`；1/2/3→`bounded`；9→`snapshot`；
  空/0/7/8→`unknown`；两端类别不同→`exact_or_bounded`；任一端 9→`snapshot`。
- `beg_gt_end` 的 28 条年份留空、不交换不夹取。
- Pleiades 两端相等的 TPQ/TAQ **判 `bounded` 而不是 `exact`**
  （切片内恰 2 条，都是 `1500-1500`：`Boxar`、`Catife`）。判 `exact` 会把
  "TAQ 恰好等于 TPQ"误读成"精确到某一年"。这一条由架构师提出，已按此实现。
- 年份列名 `valid_from_year_astro` / `valid_to_year_astro`（天文纪年）。
- `crs_confidence` 只由 `original_crs`/格式强制派生，不由数值合理性派生。

### 差异 1：原始规则码是**一列 `time_rule_code`**，不是两列 smallint

V2 用 `source_beg_rule` / `source_end_rule` 两列。暂存层用一列
`time_rule_code`，值形如 `6|9`、`|9`、`|`。

信息量等价：每个规则码都是**单字符**，所以单个 `|` 分隔无歧义，两端的原始码
都能无损还原（`6|9` → beg=`6`, end=`9`；`|9` → beg=空, end=`9`）。
选择一列而不是两列，是因为暂存 CSV 的列名与列数是 WB-002 的可复现产物契约，
team-lead 已明确指定 `time_rule_code` 这个名字；**导入层按 `|` split 即可得到两列**，
不需要改暂存产物。

### 差异 2：`historical_places` 上有 4 个时间列，V2 建议改为派生视图

V2 主张 place 表不加时间列、改用 `v_place_time_span` 视图（恒 `derived_tpq_taq`）。
暂存层**保留**了 `valid_from_year_astro` / `valid_to_year_astro` / `time_bound_type` /
`time_derivation`，因为 team-lead 的任务规格明确要求这 4 列。

两者不冲突：暂存列的 `time_derivation` 已经写明来源
（`min_max_of_children` 15,718 / `tpq_taq_of_children` 1,816 / `none` 1,505），
所以导入层可以**只取 `time_derivation='tpq_taq_of_children'` 的行**，
等价于 V2 视图；或者干脆忽略这 4 列重新派生。
需要哪一个由 team-lead 决定，本流水线不擅自删除已被要求的列。

### 差异 3：表名 `data_datasets`（复数），V2 表名 `data_dataset`（单数）

暂存文件名沿用 team-lead 指定的 `data_datasets.csv`；导入层建表时改名即可。
V2 需要的三个附加列**不落在 CSV 里**，因为它们的值对每个数据集都是常量，
是 `dataset_id` 的纯函数，导入层可无损派生：

| V2 列 | 派生方式 |
|---|---|
| `overlay_license_id` | WHG 的 `attribution.whg` = `CC-BY-4.0`，**在来源许可之上另行主张、从不替代**。本轮 7 条样本的扁平和 JSON-LD 记录里**都不含** `attribution.whg` 块，所以该值只有文档依据（`whg_apis_docs.html`），已写进三行 WHG 的 `notes` |
| `place_grain` | `chgis_*`/`mcgd_*` → `per_external_id`；`pleiades_gis_4_1_slice` → `per_record` |
| `location_grain` | `chgis_*`/`mcgd_*` → `per_external_id`；`pleiades_gis_4_1_slice` → `per_parent_external_id`；`whg_*` → `per_parent_external_id` |

另外 `redistributable` 在暂存层是**四态字符串**
（`no` / `yes_with_attribution` / `unconfirmed`，加上 CHGIS 的 `no`），
V2 要的是 `NOT NULL boolean` + `license_id='unknown'` 组合表达"可分发但许可未确认"。
映射：`unconfirmed` → `redistributable=true` + `license_id='unknown'`。
本轮唯一落在这一档的是 `whg_hgis_de_las_indias_sample`（2 条记录）。

### 不在本层处理的 V2 约束

`CHECK (crs_confidence <> 'unknown' OR record_status <> 'published')`、
`CHECK (geom IS NOT NULL OR record_status <> 'published')`、
合并门禁、`place_quality_flag` 入库丢弃、导出禁用 `place_id` ——
这些都在**导入/导出层**，不属于暂存 CSV。暂存层的责任是把它们需要的事实
（`crs_confidence`、`geom` 是否为空、`place_id`、`source_record` 业务键）
**如实写全**，本轮已做到。

---

## 已知限制

1. **无第三方 GIS 库**：`.shp` 几何未被读取，CHGIS 坐标全部取自 DBF 的
   `X_COOR`/`Y_COOR` 属性列，**未做几何-属性一致性校验**。Pleiades/WHG
   的几何是 CSV/JSON 里的 WKT/GeoJSON，只解析 POINT。
2. **`SYS_ID` 语义**：见决策 1/7。`place_id` 不是历史实体 ID。
   实测 `NOTE_ID` **不**像实体 ID：15,748 条记录只有 12,975 个唯一值，
   其中 `'0'` 出现 2,739 次；填充规则未确认。
3. **迁治规则会产假阳性，最可能是"长腿 + 紧年段"**。见决策 9：
   未做后处理剔除，而是把 1,866 条腿全部放进审核队列并标优先级。
4. **迁治链条依赖"同名 = 同一实体"这一假设**。改名会断链（例如
   `保德军`→`保德州` 在数据里是两条独立同名组），本流水线**不做**跨名称拼接，
   所以真实迁治链数量**只少不多**。
5. **`temporal_gap_too_large` 的 60 年上限是硬切**：断代超过 60 年的同名记录不再连链，
   即使它们可能确属同一实体（中间史料缺失）。本轮被排除 1,259 条。
6. **MCGD `Code` 语义未确认**（实测 `P`=408, `W`=216, `PP`=198, `WW`=135,
   `NA`/`A`/`J` 各 1），因此 MCGD 的 `place_type` 一律 `unknown`。
7. **MCGD 罗马化方案未确认**：`Name` 列同时出现 `A-ch'eng Hsien` 与 `Aikou`
   这类无标记形式，记 `wade_giles_probable` 而非断言。
8. **MCGD 仅 960 行样本**（head slice），**Pleiades 仅 1 MB 头切片**，
   **WHG 仅 7 条记录**。任何基于它们的比例都不能外推到全库。
9. **`uncertainty_m` 只有 Pleiades 有值**（源给 `accuracy_radius`）；
   CHGIS/MCGD 全空，因为源未提供定位精度。
10. **`END_DATE` / `ENT_DATE` 未解释**：府级是 `END_DATE`、县级是 `ENT_DATE`，
    字典里都查不到，原样保留在 `chgis_all_records.csv` 与 `raw_payload_json`。
11. **跨层矛盾只做同名 + 同年段的严格匹配**（29 对），不做模糊名称对齐，
    所以真实矛盾数量**只多不少**。
12. **不存在"正式数据"层**：所有输出都在 `staging`，`locked=false`，
    迁治链条一律 `needs_manual_review=true`。
13. **迁治分析只覆盖 CHGIS point 层**：`v6_time_pref_pgn`（府级面）本轮未纳入,
    面层的"辖域迁移"与点层的"治所迁移"是两回事。
14. **Pleiades 文档与数据不一致**：`gis_README.md` 说
    `year_after_which`/`year_before_which` 适用于 `places.csv`，但切片里没有这两列。
    本流水线按**数据**处理（地点级靠子记录聚合），并把矛盾记在这里。
15. **Pleiades 年份跨度极大**：`names.csv` 的 TPQ 最小到 **-2,600,000**
    （旧石器时代地名），远超 `sources.json` 声明的时间范围 [-10000, 2100]。
    这些值原样保留，未做范围裁剪，也**未**套用 CHGIS 的中国年份合理性阈值。
16. **WHG HGIS 许可未确认**，是**阻塞发布**的问题，不是可以靠推断解决的：
    2 条记录可再分发但不能确认以何许可再分发。
17. **Pleiades `connections.csv` 只导入了 390/2,763 条**为候选对：其余 2,373 条
    目标端不在切片内，无法组成两个 `place_id` 的候选行。它们仍在 `source_records`。
18. **`time_bound_type='snapshot'` 会丢掉 BEG_YR 侧的已记载起始年**：
    21 条里有 20 条的 `BEG_RULE` 是 4/5/6（真实纪年），按快照语义两列都写切片年，
    原来的起始年只留在 `notes` 与原始字段里。这是按规格执行的结果，
    但下游若要"有效期"就必须回到原始字段重算。
19. **`overlay_license_id`（V2）只有文档依据，没有样本依据**：WHG 的
    `attribution.whg` = `CC-BY-4.0` 来自 `whg_apis_docs.html` 原文，
    本轮 7 条样本里**没有任何一条**带 `attribution.whg` 块。因此这一项只能
    作为"文档声明"引用，不能声称"逐记录验证过"。
20. **`crs_confidence` 本轮做过一次纠正**：MCGD 643 条从 `inferred` 改为
    `unknown`（Pleiades 从 `documented` 改为 `confirmed`，WHG 从 `documented`
    改为 `inferred`）。若下游此前已按旧值导入，需要重跑导入。

---

## 许可

| 源 | 许可 | `redistributable` | 依据 |
|---|---|---|---|
| **CHGIS V6** | 无 SPDX，学术非商业限定 | `no` | `CHGIS_V6_README.txt`："free for academic research, no commercial use, resale, or redistribution permitted."；EULA 条款 (3) 禁止再分发，(4) 强制引用 |
| **MCGD**（Zenodo 22094815） | `cc-by-4.0` | `yes_with_attribution` | `zenodo_record_22094815.json → metadata.license.id` |
| **Pleiades** | `CC-BY-3.0` | `yes_with_attribution` | `pleiades/datasets_docs/LICENSE_CC-BY-3.0.txt`（Attribution 3.0 Unported）+ `datasets_docs/README.md` "All content is distributed under the terms of a Creative Commons Attribution license (cc-by)" |
| **WHG / GeoNames (`gn`)** | `CC-BY-4.0` | `yes_with_attribution` | 逐记录 `attribution.license__spdx_id`（4 条样本一致），须署名 Unxos GmbH |
| **WHG / Getty TGN (`tgn`)** | `ODC-By-1.0` | `yes_with_attribution` | 逐记录 `attribution.license__spdx_id`，须署名 J. Paul Getty Trust |
| **WHG / HGIS de las Indias (`hgis`)** | **未确认** | `unconfirmed` | 记录内无 `attribution` 块；`sources.json` 只说 `redistributable: true`，28 个命名空间全无 SPDX 字段 |

### CHGIS 有两份互相矛盾的官方引用串

两份都是"官方"的，都原样记录，不擅自择一：

- **README 版**（`CHGIS_V6_README.txt` 的 `Citation:` 行，本流水线写入
  `source_records.attribution_text`）：
  > `CHGIS, Version: 6. (c) Fairbank Center for Chinese Studies of Harvard University and the Center for Historical Geographical Studies at Fudan University, 2016.`
- **EULA 版**（`api/dataset_FDLFJ3_EULA.json → termsOfUse` 第 4 条
  "Mandatory Citation"，由 `chgis_extract.mandatory_citation_from_eula()` 读取）：
  > `"CHGIS Version 6." (c) Fairbank Center for Chinese Studies and the Institute for Chinese Historical Geography at Fudan University, Dec 2016.`

差异有三处：`Version: 6` vs `Version 6`；
`Center for Historical Geographical Studies` vs `Institute for Chinese Historical Geography`；
`2016` vs `Dec 2016`。以哪份对外署名需由项目方与 CHGIS 确认，
`data_datasets.csv` 的 `notes` 里明确写了这个冲突。

---

## 配套报告

- `设计资料/P0收敛/WB-002/DATA_NORMALIZATION_REPORT.md` —— 规范化做了什么、怎么做的。
- `设计资料/P0收敛/WB-002/DATA_QUALITY_REPORT.md` —— 数据本身的质量与已知"异常"。

两份报告的所有数字都从 `normalized/stats.json` 取值，并在文中标注键路径。
