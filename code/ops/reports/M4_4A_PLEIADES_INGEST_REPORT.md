# M4-4a · Pleiades GIS 4.1 数据接入与归一化 施工报告

日期：2026-11-04
状态：**M4-4a 已完成，等待 Owner 验收。未进入 M4-4b，未执行任何 V9 Migration，未写任何数据库。**
基线：M4-3 R1.1（`13322142b661d8bd2683562b17efa5ce0bb30841`）

---

## 一、结论速览

| 项 | 结果 |
|---|---|
| 七张 staging CSV | 已生成到 `code/data/staging_m4_3/`（五源合并，**不覆盖** `code/data/staging/`） |
| `source_record` | 157,220 行 = 存量 29,391 + 本轮 **127,829**（与基线完全一致） |
| 地点 / 名称 / 位置 | 57,967 / 84,558 / 53,794（增量 38,928 / 37,055 / 35,691，与基线一致） |
| 几何 | Point 26,684 · Polygon 4,112 · MultiPolygon 2 · LineString 4,893（合计 35,691） |
| 精度 | 位置级 precise 31,223 / rough 4,468；地点级 precise 27,418 / rough 11,510 |
| 质量台账 | 本轮 **7,960** 行 = 7,200 + 4 + 28 + 728，逐项实测一致 |
| V9 Migration | 已编写，**未执行**（三处值域变更，含一项需 Owner 追认的增补） |
| 自动化测试 | 单元测试 38/38 通过；交付核验 79/79 通过；可重复性三方逐字节一致 |
| 既有四源回归 | 七张表的前 N 行与旧暂存**逐行一致**（仅 `ingested_at`/`created_at` 时间戳不同） |
| 正式库 / 测试库 | 全程未连接写入；未执行 Migration、未执行导入 |

**唯一的数量偏差**：`candidate_match` 净增实测 **13,180**，比基线 13,553 少 373 条。原因见 §八「与 R1.1 的差异」，不是算法改动，是 373 条连接与旧切片快照同有序对、被既有唯一约束收敛。

---

## 二、冻结决策的执行对照

| # | 冻结决策 | 落地方式 | 证据 |
|---|---|---|---|
| 1 | 增量方案 A，不覆盖现有数据 | 2,552 条重叠地点只写 `is_active=false` 源记录，不建新地点；91 个"仅切片有"的地点原样保留 | 台账 S8；`overlap=2,552`，`new=38,928` |
| 2 | A2：合成 3,317 条代表点 | 抽取阶段按 places.csv 原始代表坐标生成独立 Point 位置行，`external_id=<pid>-representative` | S7：3,317 行，坐标与 places.csv 逐条相等（差异 0） |
| 3 | 2,552 条重叠保留 inactive 源记录 | 导入器按 `grain_key` 交集判定，插入时 `is_active=false` + `superseded_by_newer_snapshot` | S8：导入器实测 2,552 |
| 4 | `attested_form` 不额外生成名称行 | 名称行只来自 names.csv 的 `title`/`attested_form` 择优，不按 `attested_form` 补行 | 名称增量 37,055 = names.csv 中父地点属 NEW 的行数 |
| 5 | `place_without_geometry` 不写台账 | 只作为验收指标（7,200），V9 不含该值 | S10 / `ledger_audit.json` C 段 |
| 6 | 不做跨源自动合并 | 只输出候选关系，`candidate_match` 不产生任何 `confirmed` 的跨源合并 | 本轮未新增跨源候选（R1.1 §9 的跨源候选属 M4-4c 决策） |
| 7 | 来源信息不作为准入 | `attribution_text` 只写 provenance，不参与任何判定 | 台账中 `attribution_missing` 仍为 2 条（存量），无新增 |
| 8 | 不增加本轮不需要的业务表 | 只改两个 CHECK 值域（+1 项由决策 3 推导出的必要扩宽） | V9 无 CREATE TABLE |

---

## 三、数量基线实测对照

单位：行。基线取自施工指令 §四；实测取自 `code/data/staging_m4_3/`。

| 项目 | 基线 | 实测 | 差异 |
|---|---:|---:|---:|
| 新增地点 | 38,928 | 38,928 | 0 |
| 新增名称 | 37,055 | 37,055 | 0 |
| 原始位置记录 | 32,374 | 32,374 | 0 |
| A2 合成代表点 | 3,317 | 3,317 | 0 |
| 位置总量 | 35,691 | 35,691 | 0 |
| connections 源记录 | 13,603 | 13,603 | 0 |
| inactive 重叠源记录 | 2,552 | 2,552 | 0 |
| source_record 增量 | 127,829 | 127,829 | 0 |
| source_record 总量 | 157,220 | 157,220 | 0 |
| candidate_match 唯一有序对 | 13,553 | 13,553 | 0 |
| **candidate_match 入库净增** | 13,553 | **13,180** | **−373**（见 §八.1） |

几何：

| 类型 | 基线 | 实测 | 说明 |
|---|---:|---:|---|
| Point | 26,684 | 26,684 | 23,367 真实点 + 3,317 合成点 |
| Polygon | 4,114（Polygon/MultiPolygon 合计） | 4,112 | 2 条修复后成为双片，计入 MultiPolygon |
| MultiPolygon | — | 2 | 由 `ST_MakeValid` 产生，值域本已允许 |
| LineString | 4,893 | 4,893 | — |
| 合计 | 35,691 | 35,691 | — |

精度：

| 级别 | 基线 precise / rough | 实测 | 差异 |
|---|---|---|---|
| 地点级（places.csv，仅 NEW） | 27,418 / 11,510 | 27,418 / 11,510 | 0 |
| 位置级（A2） | 31,223 / 4,468 | 31,223 / 4,468 | 0 |

台账：

| 类型 | 基线 | 实测 | 差异 |
|---|---:|---:|---:|
| `missing_coordinate` | 7,200 | 7,200 | 0 |
| `geometry_invalid_repaired` | 4 | 4 | 0 |
| `connection_endpoint_missing` | 28 | 28 | 0 |
| `accuracy_unknown_sentinel` | 728 | 728 | 0 |
| `unknown_time_bound_type`（Pleiades） | 0 | 0 | 0 |
| `parent_place_not_in_sample`（新增） | 0 | 0 | 0 |
| `coordinate_out_of_range`（新增） | 0 | 0 | 0 |
| **可预测合计** | **7,960** | **7,960** | 0 |

七张表总量（合并后）：

| 表 | 旧暂存 | 新暂存 | 增量 |
|---|---:|---:|---:|
| `historical_places` | 19,039 | 57,967 | 38,928 |
| `historical_place_names` | 47,503 | 84,558 | 37,055 |
| `historical_place_locations` | 18,103 | 53,794 | 35,691 |
| `source_records` | 29,391 | 157,220 | 127,829 |
| `data_quality_issues` | 12,631 | 20,591 | 7,960 |
| `candidate_matches` | 53,137 | 66,711 | 13,574（记录）/ 13,553（唯一对） |
| `data_datasets` | 7 | 8 | 1 |

> 说明：`historical_place_names` / `historical_place_locations` 的**增量**与基线一致；
> 旧暂存 CSV 是 47,503 / 18,103，比库里多 4 / 2 行 —— 那 6 行是导入时被 C08 与 C07 收敛的
> 重复行，属既有行为，本轮未改。

---

## 四、交付物清单

### 4.1 V9 Migration（只编写，未执行）

`code/backend/src/main/resources/db/migration/V9__geometry_linestring_and_issue_types.sql`（129 行）

| # | 变更 | 内容 |
|---|---|---|
| 1 | `ck_hpl_geom_type` | `Point/Polygon/MultiPolygon` → `+ LineString` |
| 2 | `ck_data_quality_issue_issue_type` | 20 → 23：`+ geometry_invalid_repaired`、`connection_endpoint_missing`、`accuracy_unknown_sentinel`；**不含** `place_without_geometry` |
| 3 | `ck_source_record_c19`（**V9-D1，需 Owner 追认**） | `inactive_reason` 3 → 4：`+ superseded_by_newer_snapshot` |

- 三处都用 `DO $$ … IF NOT EXISTS (… pg_get_constraintdef …) THEN` 先判后改，可反复执行审查。
- 不写显式 `BEGIN/COMMIT`：Flyway 在 PostgreSQL 上默认按单 migration 事务执行。
- 不改列类型、不加列、不改索引、不动数据。
- 配套 `code/ops/m4-4a/V9_checks.sql`：执行前校验 4 条、执行后校验 5 条、**完整可执行回滚**（注释态，含回滚前提自检）、验收查询 4 条。

### 4.2 三个流水线脚本

| 文件 | 变更行数 | 改了什么 |
|---|---:|---|
| `p0/wb-002-normalize/pleiades_extract.py` | +860 | 新增 `extract_pleiades_full()` 全量抽取器；切片抽取器一字未改 |
| `p0/wb-002-normalize/normalize.py` | +330 | 新增第五源分支：几何类型、精度直传、A2 时间、台账缓冲、连接别名解析 |
| `ops/import_staging.py` | +270 | 新增数据集/作用域、几何三类型写入、精度直传、重叠失效、G1 与几何断言 |
| `p0/wb-002-normalize/datasets.py` | +25 | 注册 `pleiades_gis_4_1` 数据集（**第 4 个文件，必须说明**，见 §八.6） |

### 4.3 staging 七张 CSV

`code/data/staging_m4_3/`（合计 250,982,312 B，另有 `manifest.json`、`SHA256SUMS.txt`）

| 文件 | 行数 | 字节 | SHA256 |
|---|---:|---:|---|
| `historical_places.csv` | 57,967 | 21,028,530 | `b7a6ab5af4c2771d74097cb54e2df71560d488b3489f0eed49c2f9e096852645` |
| `historical_place_names.csv` | 84,558 | 21,426,671 | `281105066963c5f32cf7b020c634a7002a45ac7b4affab2fe6f3d8e04d2f34cf` |
| `historical_place_locations.csv` | 53,794 | 33,093,285 | `7ac7b28b88f94af8e105f45d6114d75c33f7684ffc5c3e9c6112f4762bb65cd5` |
| `source_records.csv` | 157,220 | 144,578,156 | `1a2d8b66e41c3aa41700630a42e769c4ef652fcf17bbd458212846ead8b1e502` |
| `data_quality_issues.csv` | 20,591 | 8,285,862 | `23d37766f568c329081db90c95bfb30b4ed46823ae896ee80f4a1d8258b194b9` |
| `candidate_matches.csv` | 66,711 | 21,407,181 | `9abba953096159b1dd046e9d984dba84f6c7f7921874468c11d7bdb744fcaca7` |
| `data_datasets.csv` | 8 | 5,647 | `7cd39277de70132bfc298bac49b9ada0036dde3901479fe549d576667a70ed81` |

为什么是"合并后的总量"而不是"只有增量"：基线写的 `source_record 预计总量 157,220` 只有
在暂存里真的存在 157,220 行时才成立；而且导入器要求「源记录派生的地点键 ≡ 暂存 places 行」，
增量式暂存会让 373 条指向旧切片地点的连接无处解析。因此七张表是五源的**完整重建**，
旧四源部分逐行不变（§九 S11）。

### 4.4 新增的运维脚本

| 文件 | 作用 |
|---|---|
| `ops/m4-4a/build_staging_m4_3.py` | 归一化入口：五源 → `staging_m4_3`；不修改 `run_all.py` |
| `ops/m4-4a/verify_staging_m4_3.py` | 79 条判据的交付核验（S1–S11），输出 `verify_report.json` |
| `ops/m4-4a/test_m4_4a.py` | 38 个单元测试（几何 / 修复 / URI / 精度 / V9 值域 / 作用域） |
| `ops/m4-4a/check_reproducibility.py` | 两次独立构建 + 与交付目录三方 SHA256 比对 |
| `ops/m4-4a/ledger_audit.py` | 台账逐类型实测 + 逐条 ID，分「归一化 / 导入器合成 / 不开票」三段 |
| `ops/m4-4a/V9_checks.sql` | 执行前后校验与完整回滚 SQL |

### 4.5 证据文件

- `code/data/staging_m4_3/manifest.json`：40 个只读输入的 sha256（运行前后一致）、七个输出的
  sha256/行数、五源抽取统计、`v4.1` 每文件 sha256、重叠/新增集合的摘要哈希、环境版本。
- `code/data/staging_m4_3/SHA256SUMS.txt`：七行 `sha256sum` 格式。
- `code/ops/m4-4a/verify_report.json`：79 条判据的逐条结果。
- `code/ops/m4-4a/ledger_audit.json`：台账逐类型与逐条 ID。
- `code/ops/reports/m4-4a/*.log`：核验、单元测试、可重复性、台账四份运行日志。

---

## 五、三个脚本的关键改造点

### 5.1 `pleiades_extract.py`：并列新增，不动切片

`extract_pleiades()`（切片）**一行未改**，其输出仍逐字节进入新暂存（S11 已验证）。
新增 `extract_pleiades_full(gis_dir, new_place_ids, superseded_place_ids)`：

1. 读 8 个文件（places / names / 三个 location / connections / places_accuracy / places_place_types），
   每个文件记 sha256、字节、行数、短记录数（实测 0）。
2. **子行只导 NEW 集合**：names / locations 只保留父地点 ∈ 38,928 的行；place 记录 41,480 条全留。
3. **几何三类型**：Point 走 `parse_wkt_point`；LineString / Polygon 走 shapely（GEOS），
   `force_2d` 降 Z、`make_valid` + 只取面片修复、`representative_point()` 与
   `interpolate(0.5, normalized=True)` 算代表点。
4. **A2 合成**：对"有代表点、无任何 location 行"的 NEW 地点，生成独立 location 记录；
   payload 是 places.csv 原行 + `place_id` + `_synthetic` + `_derived_from` 三个派生键
   （`place_id` 是必需的：导入器靠 `raw_payload.place_id` 派生 `parent_external_id`）。
5. **连接全量 13,603 行**：`connects_to` 归一为裸 id；悬空的打
   `connection_endpoint_missing`，自环的留痕，都不丢弃。

### 5.2 `normalize.py`：第五源分支

1. `EXTRA_SOURCE_DATASETS`、`DATASET_ORDER` 追加 `pleiades_gis_4_1`（**排在最后**，使既有
   `hp_` / `nm_` / `loc_` / `sr_` 编号一位都不动）。
2. 跳过多重叠地点：`extraction.stats["superseded_place_ids"]` → 不进 `PlaceGroup`。
3. 位置行：`geom_type` 由 WKT 首词推断；`original_x/y` 只对点写入；`location_precision` 直传。
4. 地点行：`place_type` 取 `settlement`/`unknown`（唯一有数据依据的映射），
   类型汇总与"有无代表点"写进 `notes`。
5. 台账：四类新票**缓冲后追加在最后**，因此既有 12,631 条 `dq_` 编号零位移。
6. 候选：新增别名解析（重叠地点的连接另一端映射到旧切片 `place_id`），
   并区分 `resolved_through_alias` / `self_loop_after_alias` / `unresolvable`。

### 5.3 `import_staging.py`：几何与失效语义

1. `DATASETS` 增 `pleiades_gis_4_1`；`SCOPE_MAP` 增 5 组（含 `pleiades_representative_point`）。
2. `build()` 里先用**切片 place 集合 ∩ 4.1 place 集合**算出重叠集合，排除出 `place_keys`；
   实测 2,552，且地点键 57,967 与 `historical_places.csv` 1:1。
3. 写源记录时重叠集合 `is_active=false` + `inactive_reason=superseded_by_newer_snapshot`
   （常量 `SUPERSEDED_INACTIVE_REASON`，需 V9-D1）。
4. 写位置：点仍走 `ST_MakePoint`（既有路径不动）；面/线在 INSERT 内
   `ST_GeomFromText(wkt,4326)`，并用 `ST_IsValid` / `ST_MakeValid` + `ST_CollectionExtract(...,3)`
   兜底。
5. 精度：新增 `normalize_location_precision()`，源值直传；`'point'`（CHGIS/MCGD 把几何类型词写在
   精度列）继续映射 `unknown`，与既有 18,103 行完全一致。
6. 断言：G1 增加「重叠失效」一项（否则恒等式差 2,552）；新增 `assert_geometry()` 四条
   （值域 / 几何-类型一致 / 面线有代表点 / `ST_IsValid`）。
7. 删除一条写死的断言：时间类型改判原来要求"恰 2 行（nm_0045996 / nm_0046197）"，
   改为**从暂存独立复算期望集合**——数据集变大后改判变成 7 行，规则一个字没改。

---

## 六、几何修复专项结果

整包 5 条 `ST_IsValid=false`，NEW 集合 4 条（第 95 行属重叠地点，不入本轮）：

| `location_polygons.csv` 行 | location id | place_id | 无效原因 | 修复后 |
|---:|---|---|---|---|
| 418 | `total-station-coordinates` | 747016480 | Ring Self-intersection | **Polygon**（GEOS 返回 GeometryCollection，只取面片） |
| 1556 | `plan-location-south` | 15685985 | Ring Self-intersection | **MultiPolygon**（2 片） |
| 1799 | `location-of-balochistan` | 84624811 | Self-intersection（蝴蝶结） | **MultiPolygon**（2 片，各 20 deg²） |
| 3441 | `total-station-coordinates` | 288390870 | Ring Self-intersection | **Polygon** |

- 修复规则与 PostGIS `ST_MakeValid` + `ST_CollectionExtract(...,3)` 等价（同一 GEOS）。
- 修复后的 WKT 进入 `historical_place_locations.geom_wkt`；**原始 WKT 保留在 `raw_payload`**。
- 4 条各开一条 `geometry_invalid_repaired` 台账（`action_taken=repaired`）。
- 详细 ID 见 `code/ops/m4-4a/ledger_audit.json` 的 `A_normalization.types[geometry_invalid_repaired].all_keys`。
- 单元测试 T-04 逐条断言：行号集合 = `{95,418,1556,1799,3441}`、修复后 `is_valid=True`、
  面积 > 0、类型与上表一致。

Z 序：8 `POINT Z` / 11 `LINESTRING Z` / 91 `POLYGON Z` 显式降维，行上留 `z_ordinate_discarded`，
**不**入台账（表示层处理，不是数据缺陷）。

---

## 七、质量台账实测（任务 5）

`code/ops/m4-4a/ledger_audit.json` 把台账分三段，避免"把没跑的东西说成验证过"。

### 7.1 A 段：归一化阶段真实生成（已实测）

| 类型 | 本轮新增 | 累计 | 来源 | 生成规则 |
|---|---:|---:|---|---|
| `missing_coordinate` | 7,200 | 7,537 | 4.1 place 行 | 无代表点 → place 级 flag → 1 place 1 行 |
| `geometry_invalid_repaired` | 4 | 4 | 4.1 面 | GEOS 判无效且修复出面片才开票 |
| `connection_endpoint_missing` | 28 | 28 | 4.1 连接 | 任一端不在 places.csv（24 不存在 + 3 `/errata/` + 1 整行空） |
| `accuracy_unknown_sentinel` | 728 | 728 | 4.1 合成行 | `min_accuracy_meters = -1` → `uncertainty_m` 写 NULL |
| **合计** | **7,960** | — | — | — |

其它类型本轮**零新增**：`unknown_time_bound_type`（Pleiades 恒 0，有代码依据）、
`parent_place_not_in_sample`（全量包无孤儿）、`coordinate_out_of_range`（全包 0 越界）、
`truncated_slice_tail`（无字节切片）。

### 7.2 B 段：导入器合成（**未验证，不得当成果**）

| 类型 | 本阶段状态 | 静态预判 |
|---|---|---|
| `duplicate_external_id` | 未执行导入 | 暂存 38 个多行组 / 76 行，其中 2 组已有 `duplicate_sysid` ⇒ 预计 36 行；以运行期分组为准 |
| `derived_value_mismatch` | 未执行导入 | 取决于地点级时间包络与暂存值逐地点比对 |
| `manual_edit_conflict` | 未执行导入 | 取决于目标库哪些地点带人工保护位 |

### 7.3 C 段：明确不开票，以及为什么

| 事实 | 不开票的理由 |
|---|---|
| `place_without_geometry` 7,200 | OWNER 决策：已有 7,200 条 `missing_coordinate`，重复登记同一事实无意义；改为验收 SQL |
| `z_ordinate_discarded` 110 行 | 表示层降维，非源缺陷；值留在 `raw_payload` + `quality_flag` |
| `place_type=unknown` 26,383（NEW） | 192 键词表无法映射 5 值域，强行映射等于编造 |
| `name_lang` 非 BCP-47 42 行 | 导入器统一写 `und`，原值在 `raw_payload`（既有降级路径） |
| `attested_form` 10,297 条 | OWNER 决策：不补名称行 |

---

## 八、与 R1.1 基线的差异说明

### 8.1 `candidate_match` 净增 13,553 → **13,180**（−373）

- 4.1 自身的可解析非自环记录 13,574 条，去重后 **13,553 个有序对**（与基线一致，S9 已核）。
- 其中 **373 个有序对的两端都在重叠集合内**（2,552 个地点里），对应的连接在切片快照导入时
  已入库；本轮按 `uq_candidate_match_c09 (relation_type, place_id_a, place_id_b)` 收敛。
- 因此入库净增 = 13,553 − 373 = **13,180**；`candidate_match` 预计总量 53,131 + 13,180 = **66,311**，
  而不是 R1.1 写的 66,684。
- 这 373 条在各表里都能点名：`verify_staging_m4_3.py` 的 S9 判据会把它们算出来并打印。
- **没有为了让数字对上而改算法**：算法是"源断言如实落库 + 既有唯一约束去重"，两条都没动。

### 8.2 位置/名称/台账：交付的是合并总量，不是增量

基线里的 38,928 / 37,055 / 35,691 / 7,960 是**增量**。交付的 CSV 是五源合并后的**总量**
（57,967 / 84,558 / 53,794 / 20,591），增量在 §三 逐项对齐。
理由见 §4.3：否则 `source_record 预计总量 157,220` 与导入器的地点键一致性都无法成立。

### 8.3 V9 多了一项：`inactive_reason` 值域（V9-D1，需追认）

冻结决策 3 要求写 `is_active=false` 的源记录，但 V2 的 `ck_source_record_c19` 只允许
`source_absent` / `batch_rolled_back` / `duplicate_quarantine`，且 C20 要求
`duplicate_quarantine` 必须 `duplicate_ordinal > 0`。三个既有值没有一个能表达
"同 `grain_key` 已由既有快照承载"：
- `source_absent` = 源端消失（这里没有消失）；
- `duplicate_quarantine` = 组内重复行（这里是不同快照的同名地点）；
- `batch_rolled_back` = 批次回滚（没有回滚）。

因此 V9 做了**最小枚举扩宽**（+1 个值，不改任何既有语义）。这**超出了 R1.1 "只改两个 CHECK" 的范围**，
在此显式登记，请 Owner 追认。若不追认，回退方案是改用 `source_absent`
（改 `import_staging.SUPERSEDED_INACTIVE_REASON` 一行 + 删掉 V9 第 3 段），语义会不准确但可运行。

### 8.4 时间类型改判 2 行 → 7 行

导入器的 mask 分支规则"两端相等 ⇒ snapshot"不变，但 4.1 里另有 5 条名称行（`Yafā`、`Bidlīs`、
`Mazaquete`、`Ādīnapūr`、`Adīnapūr`，均 1500–1500）满足同一条件，因此改判 7 行。
这条断言原来是写死的"恰 nm_0045996 / nm_0046197"，已改成从暂存独立复算期望集合
（与 M4-2 收尾时对验证器做的同类修正一致）。

### 8.5 代表点计算放在抽取阶段，不是导入阶段

R1.1 §5.2 / §6 写的是入库时用 `ST_PointOnSurface` / `ST_LineInterpolatePoint` 算代表点。
实现改为在抽取阶段用 shapely（同一 GEOS 内核）算好写进 CSV：
- staging 自包含，可离线核验（S7 逐条比对坐标）；
- 可重复生成（同输入 ⇒ 同字节）；
- 导入器仍然做 `ST_IsValid` 兜底与几何类型断言，没有把责任推给流水线。

### 8.6 改了第四个文件 `datasets.py`

数据集注册表是 `data_datasets.csv` 的唯一来源，`get_dataset()` 对新 `dataset_id` 会抛
`KeyError`。只加了 1 个 `DatasetInfo` 块（25 行，纯数据），无逻辑改动。
**这是超出"只改三个脚本"的唯一一处，明确登记。**

### 8.7 `is_preferred` 保持 `false`

R1.1 §6 说"每地点第一条点行置 true"。V2 的列注释写的是「导入器永不置 true」，且
`PlaceQueryService.PREFERRED_LOCATION` 用 `ORDER BY location_id LIMIT 1`，不看这一列。
为不改动一条写进 schema 注释的既有约定，**不置 true**；插入顺序已保证点 → 线 → 面。

### 8.8 Polygon 4,114 → 4,112 + 2 MultiPolygon

基线表写的是"Polygon / MultiPolygon 合计 4,114"，合计相符；修复把 2 条双片多边形落到
`MultiPolygon`（值域本已允许），因此单看 `Polygon` 是 4,112。

### 8.9 42 行 `name_lang` 落到 `und`

Pleiades 的 `asyr` / `osar` / `cana` / `arbd` / `etruscan-in-latin-characters` 等不是 BCP-47 形态，
导入器统一写 `und`，原值留在 `raw_payload`。这是既有的 `sanitize_lang` 路径，不是新增缺陷。

### 8.10 地点级时间：2,467（不是 R1.1 §7.2 的 2,583）

R1.1 §7.2 写"NEW 无时间：名称 2,986 · 位置 1,977 · 地点 2,583"，那是**按子行空单元格**数的。
本轮交付的 `historical_places.time_bound_type` 是**按子行包络推导**的结果：

| 口径 | 数值 |
|---|---|
| v4.1 地点 `derived_tpq_taq`（子行包络推得出上下界） | 36,461 |
| v4.1 地点 `unknown`（子行全无可用时间） | 2,467 |

两者不是同一件事，差值 116 来自"有子行但子行时间类型为 unknown"的地点。规则本身没改
（`_place_time_bounds` 一字未动），也未据此开任何台账（Pleiades 恒 0 条
`unknown_time_bound_type`）。子行侧的 2,986 / 1,977 与本轮实测一致；
另外 3,317 条合成代表点没有时间列，也计入 `unknown`（2,986 + 1,977 + 3,317 = 8,280，
与本轮 v4.1 子行 `unknown` 合计相符）。

---

## 九、自动化测试结果

### 9.1 单元测试：38/38 通过

`code/ops/m4-4a/test_m4_4a.py`（日志 `ops/reports/m4-4a/unit_tests.log`）

| 组 | 覆盖 |
|---|---|
| T-01 | 三脚本 + 构建脚本可导入；`PIPELINE_VERSION` 未变；切片抽取器仍在 |
| T-02 | Point / LineString（线长中点）/ Polygon（面内点）/ 空 WKT / 不可解析 WKT / 跨文件类型混入 |
| T-03 | POINT Z / LINESTRING Z / POLYGON Z 降维且降维后无 Z |
| T-04 | 整包 5 条无效面、行号集合、修复后类型与有效性、原始 WKT 留存 |
| T-05 | `connects_to` 绝对 URI / 尾斜杠 / `/errata/` / 空值 |
| T-06 | WKT 首词 → `geom_type`（含 MultiPolygon） |
| T-07 | 精度源值直传；`point`→`unknown`；空值与脏值 |
| T-08 | V9 两个值域：23 值、3 个新值、无 `place_without_geometry`、原有 20 值全在、`LineString`、`superseded_by_newer_snapshot`、3 个 DO 块、无破坏性语句 |
| T-09 | 暂存里每个 `(dataset_id, external_id_type)` 都在 `SCOPE_MAP`；数据集 8 个 |
| T-10 | 合成代表点载荷能派生 `parent_external_id` |
| T-11 | CHGIS 时间规则字典仍可加载（7 条） |

### 9.2 交付核验：79/79 通过

`code/ops/m4-4a/verify_staging_m4_3.py`（日志 `ops/reports/m4-4a/verify_staging.log`，
结果 `ops/m4-4a/verify_report.json`）

| 组 | 内容 | 结果 |
|---|---|---|
| S1 | 表头与旧暂存一致、行数与增量、source_record 总量 | 10/10 |
| S2 | 主键唯一、外键可解析（名称/位置/候选/台账）、地点键 1:1 | 10/10 |
| S3 | 几何分布、空 WKT、面线代表点、无效面重判与修复 | 11/11 |
| S4 | 精度源值直传（位置级 + 地点级） | 5/5 |
| S5 | 七值域、`from > to`、v4.1 时间类型分布 | 4/4 |
| S6 | 经纬度范围（v4.1 零越界；既有 10 行缺坐标 / 1 行越界已点名） | 4/4 |
| S7 | 3,317 条合成点：坐标逐条对齐 places.csv、精度、`uncertainty_m`、payload | 6/6 |
| S8 | 41,480 / 2,643 / 2,552 / 38,928 + 导入器侧实测 | 6/6 |
| S9 | 13,603 源记录 / 13,574 记录 / 13,553 唯一对 / 373 条重复 | 5/5 |
| S10 | 台账四类净增、合计 7,960、追加位置 | 8/8 |
| S11 | 七张表既有部分与旧暂存逐行一致（忽略时间戳列） | 7/7 |

### 9.3 可重复性：三方逐字节一致

`code/ops/m4-4a/check_reproducibility.py`（日志 `ops/reports/m4-4a/reproducibility.log`）
两次独立构建到临时目录，七个 CSV 的 sha256 与交付目录完全一致。

### 9.4 既有流水线回归

S11 的七条判据即回归本体：CHGIS / MCGD / Pleiades 切片 / WHG 的行内容、编号、排序全部未变，
差异只有 `ingested_at` / `created_at` 两列（本轮时间戳 2026-11-04 vs 旧 2026-11-02）。

### 9.5 施工指令 §五 十项要求对照

| # | 要求 | 落点 | 结果 |
|---:|---|---|---|
| 1 | 脚本语法与基本功能 | T-01、T-11；四个脚本均可导入 | ✅ |
| 2 | Point / Polygon / LineString 几何 | T-02、S3 | ✅ |
| 3 | 4 条无效多边形真实修复 | T-04、§六 | ✅ |
| 4 | 3,317 条代表点合成核验 | S7（逐条坐标比对） | ✅ |
| 5 | 2,552 条 inactive 核验 | S8（暂存 + 导入器两路） | ✅ |
| 6 | 连接解析与 13,553 候选 | T-05、S9（含 373 条重复的成因） | ✅ |
| 7 | 七张 CSV 行数/字段/外键/唯一性 | S1、S2 | ✅ |
| 8 | 时间、精度、坐标边界 | S4、S5、S6 | ✅ |
| 9 | 重复生成哈希一致性 | §9.3 | ✅ |
| 10 | 既有四源流水线回归 | S11 | ✅ |

未执行（按边界）：数据库导入、V9 执行、E2E。这些属 M4-4b / M4-4c。

---

## 十、运行清单（manifest）摘要

`code/data/staging_m4_3/manifest.json`

| 项 | 值 |
|---|---|
| 流水线版本 | `wb-002-normalize/1.3.0`（未变） |
| `ingested_at` | `2026-11-04T00:00:00Z`（固定值，保证可重复） |
| 只读输入 | 40 个文件 / 133,422,184 B，运行前后 sha256 **全部一致** |
| 输出 | 7 CSV + manifest + SHA256SUMS |
| Python / shapely | 3.13.14 / 2.2.0（GEOS 3.14.1） |
| 集合划分 | v4.1 41,480 · 切片 2,643 · 重叠 2,552 · NEW 38,928 |
| 集合摘要哈希 | 重叠 `70d0c876…daf81`；NEW `7b8ac462…51de2` |
| 构建耗时 | 约 8 秒 |

v4.1 八文件实测（与 M4-3 审计逐字节一致）：

| 文件 | 字节 | 行数 |
|---|---:|---:|
| `places.csv` | 16,048,687 | 41,480 |
| `names.csv` | 8,481,492 | 38,862 |
| `location_points.csv` | 9,408,267 | 25,038 |
| `location_linestrings.csv` | 9,227,776 | 5,265 |
| `location_polygons.csv` | 1,373,849 | 4,385 |
| `connections.csv` | 2,535,616 | 13,603 |
| `places_accuracy.csv` | 80,605,903 | 41,480 |
| `places_place_types.csv` | 922,188 | 51,009 |

---

## 十一、边界确认（本轮没有做的事）

| 禁止项 | 是否发生 |
|---|---|
| 修改正式数据库 `canvas_history` | 否（未建立任何连接） |
| 修改测试数据库 `canvas_history_m2check` | 否 |
| 执行 V9 Migration | 否（只在文件里） |
| 执行正式导入 | 否（只做了导入器的**无库前置派生**，`build()` 不执行 SQL） |
| 覆盖 `code/data/staging/` | 否（旧目录 sha256 未变，S11 作为证据） |
| 修改原始 Pleiades 数据 | 否（40 个输入文件运行前后 sha256 一致） |
| 修改 V1–V8 | 否 |
| 启动 M4-4b / M4-4c | 否 |

V1–V8 未改动可由 `git status` 证明：迁移目录下只有新增的 V9 一个文件。

---

## 十二、需 Owner 决策 / 遗留

| # | 事项 | 影响 | 建议 |
|---|---|---|---|
| 1 | **V9-D1**：`inactive_reason` 增加 `superseded_by_newer_snapshot` | 不追认则 2,552 条源记录无法合法失效 | 请在 M4-4b 前追认；否则改 `source_absent` 并删 V9 第 3 段 |
| 2 | `candidate_match` 净增 13,180（非 13,553） | 验收指标需按 13,180 卡 | 接受：373 条已由切片快照入库，去重是正确行为 |
| 3 | `place_type` 只映射 `settlement`/`unknown` | 无法按类型筛选（26,383 个 NEW 地点为 unknown） | M4-5 之后视需要建 `place_type_link` |
| 4 | `is_preferred` 全 false | 当前查询不依赖 | 需要"优先位置"语义时再改 schema 注释与导入器 |
| 5 | 42 行 `name_lang` → `und` | 少数语言的标签丢失 | 如需保真，改 `ck_hpn_name_lang` 或加 `raw_language_tag` 列 |

**不阻塞 M4-4b。**

---

## 十三、Git

| 项 | 值 |
|---|---|
| 分支 | `m4-3-pleiades-gis`（M4-3 R1.1 同一分支，未开新分支） |
| 代码提交 | `01c5ef8` feat(m4-4a): ingest Pleiades GIS 4.1 into a dedicated staging set |
| 报告提交 | 本文件所在提交（`docs(m4-4a): …`），见 `git log` |
| 变更规模 | 5 个已有文件 +1,444/−46 行；新增 V9 与 6 个 m4-4a 文件（2,047 行） |
| 未入库 | `code/data/staging_m4_3/*.csv`（约 250 MB，按 `data/staging/*` 同一约定忽略，只保留 manifest 与 SHA256SUMS） |
| 未改动 | V1–V8、`.env`、`data/raw/**`、`data/staging/**`、`ops/.deps/**` |

---

**M4-4a — STAGING READY / WAITING FOR OWNER SIGN-OFF（未启动 M4-4b）**
