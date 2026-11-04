# M4-4b · Pleiades 4.1 隔离数据库导入与验收报告

日期：2026-11-04
状态：**M4-4b 已完成，等待 Owner 验收。未进入 M4-4c / M4-5，正式库未连接、未写入。**
基线：M4-3 R1.1（`1332214`）+ M4-4a（`01c5ef8` / `3e277c3`）
验收库：`canvas_history_m4_4b`（**保留**，不删除、不清理，M4-4c 可直接使用）

---

## 一、结论速览

| 项 | 结果 |
|---|---|
| 隔离库 | `canvas_history_m4_4b`，由 `canvas_history_m4check`（V1–V8 + 四源基线）克隆，原库未动 |
| V9 | Flyway 执行成功（`installed_rank=9`，`success=t`，42 ms），三处值域全部生效，存量数据零变化 |
| 正式导入 | 一次成功提交，8 个批次全部 `succeeded`，全部断言（批次 / 时间 / 几何）通过 |
| 核心数量 | 地点 +38,928 · 名称 +37,055 · 位置 +35,691 · 源记录 +127,829（总 157,220）· 候选 +13,180（总 66,311） |
| 几何 | Point 26,684 · Polygon 4,112 · MultiPolygon 2 · LineString 4,893；全部 `ST_IsValid`、类型一致、面线有代表点 |
| 精度 | 位置级 31,223 / 4,468；地点级 27,418 / 11,510 |
| 质量台账 | 21,447 = 基线 12,833 + 暂存增量 7,960 + 合成增量 654 |
| 幂等 | 第二轮：新增 0 / 内容变更 0 / 候选 0 / 台账 0 膨胀；`occurrence_count`、`last_batch_id` 按设计推进 |
| 既有数据 | 七张表指纹（扣掉 `last_batch_id`/`updated_at`/`occurrence_count`）导入前后**完全一致** |
| 故障注入 | 整批回滚生效，无残留 `succeeded` 批次，指纹与注入前一致 |
| 人工保护 | 独立副本上验证：locked / created_by=manual / manual_edited_fields 三档全部拒绝覆盖，值未变 |
| 验收判据 | `verify_import_m4_4b.py` 79/79 通过 |

**三个必须知道的技术判定**（详见 §八）：

1. M4-4a 的归一化产物里有 732 行 `action_taken` 用了库内不存在的动词（`repaired` / `null_written`），导入器**映射为 `preserved_and_flagged` 并把原动词写进 `resolution_note`**，未改约束、未改暂存。
2. M4-4a 导入器有一处几何缺陷（`UPDATE … AND geom_type='Point'` 会把 26,684 条点几何写成 NULL），**dry-run 抓到并已修正**；这正是本阶段存在的意义。
3. `derived_value_mismatch` 实测 820 行（629 个地点），根因是"地点级时间包络是否包含 connection 子行"两处口径不同；**该现象在切片时代就已存在**（基线 197 行 / 130 个地点），本轮按"不改已验收暂存"处理，登记为遗留。

---

## 二、施工前检查

### 2.1 Git

| 项 | 值 |
|---|---|
| 分支 | `m4-3-pleiades-gis` |
| HEAD | `3e277c3`（M4-4a 报告） |
| 工作区 | 干净（仅 `汇报/` 未跟踪，属交付目录） |
| M4-4a 提交 | `01c5ef8`（代码）、`3e277c3`（报告）均在 |

### 2.2 数据库现状

| 库 | Flyway | source_record | place | name | location | candidate | issue | dataset |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `canvas_history`（正式） | V5 | 29,391 | 19,039 | 47,499 | 18,101 | 53,131 | 12,831 | 8 |
| `canvas_history_m2check` | V8 | 29,398 | 19,091 | 47,534 | 18,136 | 53,131 | 12,833 | 10 |
| **`canvas_history_m4check`（选定基线）** | **V8** | **29,391** | **19,039** | **47,499** | **18,101** | **53,131** | **12,833** | **8** |

- `m2check` 含人工测试数据（place +52、dataset +2），不宜作干净基线。
- `m4check` 与 M4-2 干净导入结果逐项一致，且已含 V6/V7/V8。
- **正式库全程只读**：只做过 `SELECT`，未执行任何 DDL/DML。

### 2.3 隔离库创建

```sql
CREATE DATABASE canvas_history_m4_4b WITH TEMPLATE canvas_history_m4check OWNER canvas_app;
```

- 名字未被占用，直接使用 `canvas_history_m4_4b`（无需时间戳名）。
- 克隆后复核：`flyway_max=8`、行数与上表 `m4check` 一致、`data_dataset` 8 行（含 `manual_entry:0`）。

### 2.4 staging 哈希复核

`code/data/staging_m4_3/SHA256SUMS.txt` 与 `manifest.json` 逐项一致（导入器日志开头也重新算了一遍）：

| 文件 | sha256（前 16） |
|---|---|
| `historical_places.csv` | `b7a6ab5af4c2771d` |
| `historical_place_names.csv` | `281105066963c5f3` |
| `historical_place_locations.csv` | `7ac7b28b88f94af8` |
| `source_records.csv` | `1a2d8b66e41c3aa4` |
| `data_quality_issues.csv` | `23d37766f568c329` |
| `candidate_matches.csv` | `9abba953096159b1` |
| `data_datasets.csv` | `7cd39277de70132b` |

### 2.5 执行前检查（V9_checks.sql §一）

日志：`ops/reports/m4-4b/01_pre_v9_checks.log`

| 检查 | 结果 |
|---|---|
| 当前库 | `canvas_history_m4_4b` ✅ |
| Flyway V1–V8 | 8 条全 `success=t` ✅ |
| `geom_type` 分布 | `Point` 18,091 / NULL 10（DBF 溢出的 CHGIS 行）✅ |
| `ck_hpl_geom_type` | `Point / Polygon / MultiPolygon` ✅ |
| `ck_data_quality_issue_issue_type` | **允许 20 值**；**实际出现 15 种**；越界 0 ✅ |
| `ck_source_record_c19` | `source_absent / batch_rolled_back / duplicate_quarantine` ✅ |

> 值域 20 vs 实际 15 是**两件事**：没出现过的合法类型不算缺失。V9_checks.sql 已按此改写
> （原来那句"应恰为 20 种"已删掉，改为分别统计"CHECK 内允许值数"和"库内实际类型数"）。

### 2.6 导入前数据指纹

日志：`ops/reports/m4-4b/02_fingerprint_before_v9.log`（`ops/m4-4b/fingerprint.sql`，`cutoff=14`）

| 表 | 行数 | sha256（前 16） |
|---|---:|---|
| source_record | 29,391 | `0035ea6180440d57` |
| historical_place | 19,039 | `9eb3abacfe057c0e` |
| historical_place_name | 47,499 | `002e565d5ad652e6` |
| historical_place_location | 18,101 | `5020dad396bbcbd9` |
| candidate_match | 53,131 | `2bd8b4b51fa8ca43` |
| data_quality_issue | 12,833 | `2df591ce7888515d` |
| data_dataset | 8 | `7b2e5ba36e63606e` |

指纹口径：按行序 `string_agg(row_to_json(...))` 取 `sha256`，**扣除** `last_batch_id` /
`updated_at` / `occurrence_count` 三个"按设计会变"的列；几何用 `ST_AsEWKB` 的十六进制参与。

---

## 三、V9 Migration 执行记录

### 3.1 执行

```
./ops/flyway.sh canvas_history_m4_4b migrate
Flyway OSS Edition 13.12.0
Database: jdbc:postgresql:******** (PostgreSQL 17.11)
Successfully validated 9 migrations
Current version of schema "public": 8
Migrating schema "public" to version "9 - geometry linestring and issue types"
Successfully applied 1 migration to schema "public", now at version v9 (execution time 00:00.042s)
```

日志：`ops/reports/m4-4b/03_v9_migrate.log`

`flyway_schema_history` 记录：

| installed_rank | version | description | script | checksum | success | installed_on | time |
|---:|---|---|---|---|---|---|---:|
| 9 | 9 | geometry linestring and issue types | `V9__geometry_linestring_and_issue_types.sql` | 259549483 | t | 2026-11-04 11:01:10 | 42 ms |

### 3.2 执行后校验

日志：`ops/reports/m4-4b/04_post_v9_checks.log`

| 检查 | 结果 |
|---|---|
| `ck_hpl_geom_type` | 含 `LineString`，共 4 值 ✅ |
| `ck_data_quality_issue_issue_type` | 23 值，含 3 个新值，**不含** `place_without_geometry` ✅ |
| `ck_source_record_c19` | 4 值，含 `superseded_by_newer_snapshot` ✅ |
| 七张表行数 | 与执行前完全一致（19,039 / 47,499 / 18,101 / 29,391 / 53,131 / 12,833 / 8）✅ |
| 数据指纹 | 与 2.6 完全一致（见 `06_fingerprint_after_v9.log`）✅ |

### 3.3 值域探针与负控（全部在事务内，结束即 `ROLLBACK`）

日志：`ops/reports/m4-4b/05_v9_value_probe.log`

| 探针 | 结果 |
|---|---|
| P1 `LineString` 写入 | 成功，`ST_GeometryType=ST_LineString`，长度 13,860.8 m ✅ |
| P2 三个新台账类型写入 | 三条全部成功 ✅ |
| P3 `superseded_by_newer_snapshot` | `is_active=f` + 原因写入成功，C03/C18/C21/C22 组合成立 ✅ |
| P4a 负控 `GeometryCollection` | 被 `ck_hpl_geom_type` 拒绝 ✅ |
| P4b 负控 `place_without_geometry` | 被值域拒绝 ✅ |
| P4c 负控 未声明 `inactive_reason` | 被 C19 拒绝 ✅ |
| P4d 负控 `action_taken='repaired'` | 被 6 值域拒绝（**这就是 §八.1 的来源**）✅ |
| P5 `ROLLBACK` 后 | `LineString=0`、新台账=0、`superseded=0` ✅ |

---

## 四、导入前检查

### 4.1 导入器版本确认

`ops/import_staging.py` 已是 M4-4a 版本：含 `pleiades_gis_4_1` 数据集、`SCOPE_MAP` 5 组、
重叠地点失效、几何三类型写入、`assert_geometry()`。`--staging-dir` 参数已存在（M4-4a 新增），
默认仍指向 `code/data/staging`，**未改变既有流水线**。

本轮对该文件的三处最小修正见 §八.1–8.3。

### 4.2 dry-run

```
PYTHONPATH=ops/.deps python ops/import_staging.py --db canvas_history_m4_4b \
  --staging-dir data/staging_m4_3 --dry-run \
  --excluded-csv ops/reports/m4-4b/excluded_rows.csv \
  --summary-json ops/reports/m4-4b/dryrun_summary.json
```

日志：`ops/reports/m4-4b/07_dryrun.log`（首轮 exit=3，暴露 §八.2 几何缺陷；修正后 exit=0）

| 检查 | 结果 |
|---|---|
| record_scope | 157,220 行全部命中 4 值 ✅ |
| content_hash 规范化式 = 逐字节式 | 157,220/157,220 ✅ |
| 隔离（重复行） | 7 条（4 条在 4.1）✅ |
| 重叠地点判定 | 2,552 ✅ |
| grain_key | 57,967，与暂存 places 1:1 ✅ |
| 时间改判 | 7 行 = 规则推导集合 ✅ |
| 几何准备 | Point 26,684 / LineString 4,893 / Polygon 4,112 / MultiPolygon 2 ✅ |
| 断言 | 批次 G1 全平衡、时间 ✅、几何 ✅ |

### 4.3 受控故障注入

```
… --inject-fault rollback_check
```

日志：`ops/reports/m4-4b/08_fault_injection.log`、`09_fault_after_counts.log`、`10_fingerprint_after_fault.log`

| 检查 | 结果 |
|---|---|
| 退出码 | 3（`AssertionFailure` → 整批回滚）✅ |
| 业务表行数 | 与注入前完全一致（29,391 / 19,039 / 47,499 / 18,101 / 53,131 / 12,833 / 8）✅ |
| `import_batch` | 仍 14 行，`batch_id > 14` 的批次 **0** 条 ✅ |
| `LineString` / `superseded` 残留 | 0 / 0 ✅ |
| 数据指纹 | 与 2.6 完全一致 ✅ |

---

## 五、正式导入

### 5.1 命令

```
PYTHONPATH=ops/.deps python ops/import_staging.py \
  --db canvas_history_m4_4b \
  --staging-dir data/staging_m4_3 \
  --excluded-csv ops/reports/m4-4b/excluded_rows.csv \
  --summary-json ops/reports/m4-4b/import_summary.json
```

凭证来自 `code/.env`，由 `import_staging.load_env()` 读入，**不出现在命令行、未写入任何日志**。

### 5.2 批次

日志：`ops/reports/m4-4b/11_import_run1.log`

| batch | dataset | status | input_row_count | quarantined | skipped | inserted |
|---:|---|---|---:|---:|---:|---:|
| 72 | chgis_v6_prefecture_points | succeeded | 5,226 | 0 | 5,224 | 0 |
| 73 | chgis_v6_county_points | succeeded | 10,522 | 0 | 10,522 | 0 |
| 74 | mcgd_zenodo_22094815_head960 | succeeded | 960 | 0 | 960 | 0 |
| 75 | pleiades_gis_4_1_slice | succeeded | 12,445 | 0 | 12,444 | 0 |
| **76** | **pleiades_gis_4_1** | **succeeded** | **127,829** | **4** | **0** | **127,829** |
| 77 | whg_geoname_s_gn_sample | succeeded | 209 | 0 | 209 | 0 |
| 78 | whg_getty_tgn_sample | succeeded | 21 | 0 | 21 | 0 |
| 79 | whg_hgis_de_las_indias_sample | succeeded | 8 | 0 | 8 | 0 |

G1 恒等式（每个批次独立成立）：

```
5,226  = 0 + 0 + 0 + 0 + 5,224 + 2
10,522 = 0 + 0 + 0 + 0 + 10,522 + 0
960    = 0 + 0 + 0 + 0 + 960    + 0
12,445 = 0 + 0 + 0 + 0 + 12,444 + 1
127,829= 0 + 隔离4 + 新增125,273 + 重叠失效2,552 + 0 + 0 + 0
209    = 0 + 0 + 0 + 0 + 209    + 0
21     = 0 + 0 + 0 + 0 + 21     + 0
8      = 0 + 0 + 0 + 0 + 8      + 0
```

### 5.3 行数变化

| 表 | 导入前 | 导入后 | Δ |
|---|---:|---:|---:|
| source_record | 29,391 | **157,220** | +127,829 |
| historical_place | 19,039 | **57,967** | +38,928 |
| historical_place_name | 47,499 | **84,554** | +37,055 |
| historical_place_location | 18,101 | **53,792** | +35,691 |
| candidate_match | 53,131 | **66,311** | +13,180 |
| data_quality_issue | 12,833 | **21,447** | +8,614 |
| data_dataset | 8 | **9** | +1 |
| import_batch | 14 | 22 | +8 |

### 5.4 七张 CSV 与数据库实际落库对照

| 对象 | staging 行数 | 落库行数 | 差异 | 原因 |
|---|---:|---:|---:|---|
| source_record | 157,220 | 157,220 | 0 | — |
| historical_place | 57,967 | 57,967 | 0 | — |
| historical_place_name | 84,558 | 84,554 | −4 | `uq_hpn_c08 (source_record_id, name_type, name_text, name_lang)` 既有去重 |
| historical_place_location | 53,794 | 53,792 | −2 | `uq_hpl_c07 (source_record_id)` 既有去重 |
| candidate_match | 66,711 | 66,311 | −400 | 2 自指 + 398 C09 收敛（见下） |
| data_quality_issue | 20,591 | 20,591（全在库） | 0 | 另有 856 条导入器合成（见 §六.5） |
| data_datasets | 8 | 9 | +1 | V5 的 `manual_entry` 不由暂存提供 |

候选 −400 的构成：2 条 `place_id_a = place_id_b`（`ck_candidate_match_distinct_places` 拒绝）
+ 398 条同 `(relation_type, place_id_a, place_id_b)` 重复。后者再分解为
**4 条既有 CHGIS 内重复 + 21 条 4.1 内重复 + 373 条与切片快照同对**。
逐条留痕：`ops/reports/m4-4b/excluded_rows.csv`（400 行）。

---

## 六、数据库验收（`verify_import_m4_4b.py`，79/79）

日志：`ops/reports/m4-4b/12_verify_after_import.log`；结果：`ops/reports/m4-4b/verify_m4_4b.json`

### 6.1 地点与来源记录

| 项目 | 预期 | 实测 |
|---|---:|---:|
| 新增地点 | 38,928 | 38,928 ✅ |
| 新增名称 | 37,055 | 37,055 ✅ |
| 新增位置 | 35,691 | 35,691 ✅ |
| 新增来源记录 | 127,829 | 127,829 ✅ |
| 来源记录总量 | 157,220 | 157,220 ✅ |
| 重叠失效来源记录 | 2,552 | 2,552 ✅ |

2,552 条逐项核验：

| 检查 | 结果 |
|---|---|
| `is_active=false` | 2,552 ✅ |
| `inactive_reason='superseded_by_newer_snapshot'` | 2,552 ✅ |
| `duplicate_ordinal=0`（不是重复隔离） | 2,552 ✅ |
| `inactive_at` / `inactive_in_batch_id` 非空 | 2,552 ✅ |
| v4.1 侧没有为它们建点（`historical_place` 仅 38,928） | ✅ |
| 这些 `grain_key` 在 v4.1 数据集内无对应 place | 0 冲突 ✅ |

v4.1 `record_scope` 分布：`place 41,480 / name 37,055 / location 35,691 / edge 13,603` ✅

### 6.2 几何

| 类型 | 预期 | 实测 |
|---|---:|---:|
| Point | 26,684 | 26,684 ✅ |
| Polygon | 4,112 | 4,112 ✅ |
| MultiPolygon | 2 | 2 ✅ |
| LineString | 4,893 | 4,893 ✅ |
| 合计 | 35,691 | 35,691 ✅ |

| 附加核验 | 结果 |
|---|---|
| 全部几何 `ST_IsValid` | 0 条无效 ✅ |
| `ST_GeometryType` 与 `geom_type` 一致 | 0 条不一致 ✅ |
| 面/线代表点非空 | 0 条缺失 ✅ |
| SRID | 全部 4326 ✅ |
| 4 条修复多边形：几何有效 + 类型为面/多面 + 有台账 | 全部成立 ✅ |
| 3,317 条合成代表点与 `places.csv` 坐标逐条一致（容差 1e-9） | 不一致 0 ✅ |
| 无位置线索的 7,200 个地点：没有位置行、`notes` 标记 `has_representative_point=false` | 7,200 / 7,200 ✅ |

### 6.3 精度

| 级别 | precise | rough |
|---|---:|---:|
| 位置级（v4.1） | 31,223 ✅ | 4,468 ✅ |
| 地点级（v4.1，`places.csv` 原值经 notes 承载） | 27,418 ✅ | 11,510 ✅ |

位置级只出现 `precise` / `rough` 两个值（源值直传，没有再被压成 `unknown`）。

### 6.4 候选关系

| 项目 | 预期 | 实测 |
|---|---:|---:|
| `candidate_match` 总量 | 66,311 | 66,311 ✅ |
| `pleiades_connection` 行数 | 13,570（390 切片 + 13,180 本轮） | 13,570 ✅ |
| 本轮新增 | 13,180 | 13,180 ✅ |
| v4.1 唯一有序对（从 `connections.csv` 重算） | 13,553 | 13,553 ✅ |
| 这些有序对全部在库 | 差集 0 | 0 ✅ |
| 库里连接对没有来源之外的多余项 | 17（切片独有） | 17 ✅ |
| 自环 / 重复三元组 | 0 / 0 | 0 / 0 ✅ |
| `confirmed` 的 `pleiades_connection` 都有 `system:source_attested` | 0 例外 | 0 ✅ |

> 13,553 与 13,570 的关系：库里 13,570 个连接对 = v4.1 的 **13,553** 对 + 切片独有的 **17** 对
> （一端是"仅切片有"的 91 个地点之一）。13,553 中的 **373** 对两端都在重叠集合里，
> 在切片快照导入时就已入库，本轮按 `uq_candidate_match_c09` 收敛 —— 这就是
> "净增 13,180 而不是 13,553"的全部原因。

### 6.5 质量台账

| 类型 | 累计 | 其中本轮新增 | 来源 |
|---|---:|---:|---|
| `missing_coordinate` | 7,537 | 7,200 | 归一化 |
| `geometry_invalid_repaired` | 4 | 4 | 归一化 |
| `connection_endpoint_missing` | 28 | 28 | 归一化 |
| `accuracy_unknown_sentinel` | 728 | 728 | 归一化 |
| **暂存台账增量合计** | — | **7,960** | ✅ |
| `duplicate_external_id` | 36 | 0（36 为既有） | 导入器合成 |
| `derived_value_mismatch` | 820 | +654 | 导入器合成 |
| `manual_edit_conflict` | 0 | 0 | 导入器合成（验收库无保护位） |

台账总量恒等式：

```
21,447 = 基线 12,833 + 暂存增量 7,960 + 合成增量 654
```

| 附加核验 | 结果 |
|---|---|
| `issue_fingerprint` 唯一 | 唯一 21,447 / 21,447 ✅ |
| 台账 `dataset_id` 均非空 | 0 条为空 ✅ |
| `action_taken` 全在 6 值域 | 0 条越界 ✅ |
| 732 行的原动词保留在 `resolution_note` | 732/732 ✅ |

> `derived_value_mismatch` 820 行（629 个地点）**不是本轮引入**：根因是"地点级时间包络
> 是否包含 connection 子行"两处口径不同。基线里 130 个切片地点已产生 166 行同类台账，
> 本轮 499 个 v4.1 地点放大到 654 行。详见 §八.4。

### 6.6 数据完整性

| 检查 | 结果 |
|---|---|
| 名称孤儿 / 位置孤儿 | 0 / 0 ✅ |
| 名称 / 位置的 `source_record_id` 可解析 | 全可解析 ✅ |
| v4.1 地点的锚点源记录指向本数据集 | 0 例外 ✅ |
| `raw_payload` 非空 | 157,220/157,220 ✅ |
| v4.1 源记录 `raw_file` 均是 6 个已知文件之一 | 0 例外 ✅ |
| v4.1 源记录 `raw_record_index` 非空 | 0 例外 ✅ |
| 五段键内 `content_hash` 无重复 | 0 ✅ |
| `pleiades_gis_4_1` 数据集登记（`record_count=127,829`） | ✅ |

---

## 七、幂等与数据保护

### 7.1 幂等复跑

日志：`ops/reports/m4-4b/14_import_run2_idempotent.log`

| 检查 | 结果 |
|---|---|
| 业务表行数 | 全部 Δ0（57,967 / 84,554 / 53,792 / 157,220 / 66,311 / 21,447 / 9）✅ |
| 批次新增源记录 | 0 ✅ |
| 批次内容变更（`updated_source_record_ids`） | 0 ✅ |
| 候选入库 | 0（仍 66,311）✅ |
| 台账行数 | 0 膨胀（仍 21,447），`issue_fingerprint` 冲突走 `ON CONFLICT` ✅ |
| G1 恒等式 | 8 个批次全部平衡 ✅ |
| `occurrence_count` | 8,614 行 = 2（首轮插入 + 复跑命中）✅ |
| `last_batch_id` | 全部 157,220 行指向复跑批次（84–87 等）✅ |
| 断言 | 批次 / 时间 / 几何全部通过 ✅ |

### 7.2 人工保护（独立副本）

验收库无任何保护位（`protected_places = 0`），因此**不在验收库上造数据**，
而是克隆出 `canvas_history_m4_4b_protect` 做受控验证。

日志：`ops/reports/m4-4b/16_protect_setup.log`、`17_protect_run.log`

| 地点 | 保护位 | 人工改名 | 重跑后名称 | 冲突台账 |
|---|---|---|---|---|
| 135875 | `locked=true` | 人工改名-A | **仍是 人工改名-A** ✅ | 1 条（原因 `locked`） |
| 135876 | `created_by='manual'` | 人工改名-B | **仍是 人工改名-B** ✅ | 1 条（原因 `created_by=manual`） |
| 135877 | `manual_edited_fields={canonical_name}` | 人工改名-C | **仍是 人工改名-C** ✅ | 1 条（原因 `manual_edited_fields=canonical_name`） |

- 概览行：`新增 0 / 内容变更 0 / 无变化 57,964 / 人工保护跳过 3（其中名称冲突登记台账 3）`
- 三个地点 `updated_at` 保持 `2026-11-04 12:00:00+08`，未被导入器改写 ✅
- `manual_edit_conflict` 台账 `observed_value` / `resolution_note` 同时记录"库中现值"与"导入值"，可逐条复核 ✅
- 验证后**验收库 `canvas_history_m4_4b` 未被触碰**（仍无 manual_edit_conflict、仍 21,447 条台账）✅

### 7.3 既有四源数据保护

| 表 | 导入前 sha256（前 16） | 导入后 | 结论 |
|---|---|---|---|
| source_record | `0035ea6180440d57` | 同 | 一致 ✅ |
| historical_place | `9eb3abacfe057c0e` | 同 | 一致 ✅ |
| historical_place_name | `002e565d5ad652e6` | 同 | 一致 ✅ |
| historical_place_location | `5020dad396bbcbd9` | 同 | 一致 ✅ |
| candidate_match | `2bd8b4b51fa8ca43` | 同 | 一致 ✅ |
| data_quality_issue | `2df591ce7888515d` | 同 | 一致 ✅ |
| data_dataset | `7b2e5ba36e63606e` | 同 | 一致 ✅ |

日志：`ops/reports/m4-4b/13_fingerprint_after_import.log`

---

## 八、与预期的差异（含两个 M4-4a 缺陷）

### 8.1 `action_taken` 两个动词不在库内值域（M4-4a 产物缺陷，已兜住）

`data_quality_issue.action_taken` 的 V2 值域只有 6 个：`preserved_and_flagged` /
`needs_manual_review` / `rejected` / `fixed_manually` / `ignored` / `discarded`。
M4-4a 的归一化产物写了 `repaired`（4 行）与 `null_written`（728 行），共 **732 行**
落不进库（V9 探针 P4d 专门证明了这一点）。

处理：**不改约束（禁止 V10）、不改已验收暂存**，在导入器里做显式映射：

| 原动词 | 落库值 | 理由 |
|---|---|---|
| `repaired` | `preserved_and_flagged` | 几何已修好，但库内没有"自动修复"这个动词；原始 WKT 原样保留在 `raw_payload` |
| `null_written` | `preserved_and_flagged` | 哨兵 -1 写成 NULL，源值同样保留在 `raw_payload` |

- 只映射这两个已知值；**出现第三个未知动词即整批中止**（`DerivationError`），不猜。
- 原动词写入 `resolution_note`：`…；action_taken 原值=repaired（库内 6 值域无此动词，落库按 preserved_and_flagged 记，原动词在此保留）`
- 可核验：`resolution_note LIKE '%action_taken 原值=%'` = 732 行 ✅
- 运行时会打一条 warning，不会静默。

**建议**（不阻塞）：下一轮把 `normalize.py` 的两个动词改成库内值，或在 V10 里扩宽
`action_taken`；本轮不动，避免改已验收的暂存哈希。

### 8.2 点几何写入缺陷（M4-4a 导入器，dry-run 抓到）

M4-4a 在 `write_locations` 的 `UPDATE` 里加了一句 `AND geom_type='Point'`，
想保护面/线行。但点行插入时 `geom_type` 还是 NULL（`geom` 与 `geom_type` 都由这条
`UPDATE` 补），条件导致 **26,684 条点几何保持 `geom IS NULL`** —— 地图上等于全不可见。

- dry-run 的 `3.9c 几何断言` 立刻显示 `几何分布 {None: 26694, 'Point': 18091, …}`；
- 修正：删掉该条件（面/线行 `geom` 已非空，`geom IS NULL` 本身就足够排除它们）；
- 修正后：`{'Point': 44775, 'LineString': 4893, 'Polygon': 4112, None: 10, 'MultiPolygon': 2}`
  （`None` 的 10 条是 CHGIS DBF 溢出行的既有状态）；
- 正式导入后 `全部几何 ST_IsValid`、`geom_type 与真实类型一致`、`SRID 全 4326` 全部为 0 例外 ✅

### 8.3 G1 恒等式把重叠失效重复计入（M4-4a 导入器）

`import_batch.quarantined_count` 原来按 `NOT is_active` 统计，M4-4a 起 `is_active=false`
还包含 2,552 条"重叠失效"，导致 G1 多算 2,552（10 万级差异，dry-run 直接判失败）。

修正：`quarantined_count` 只统计 `inactive_reason='duplicate_quarantine'`，
"重叠失效"作为 G1 的独立一项单列。修正后 8 个批次全部平衡 ✅

### 8.4 `derived_value_mismatch` 820 行（629 个地点）

| 口径 | 谁 | 规则 |
|---|---|---|
| 归一化 | `normalize._place_time_bounds` | 地点级包络 = **全部子行**（name + location + **connection**）的 TPQ/TAQ 包络 |
| 导入器 | `write_ledger` | 地点级包络 = **仅 name + location**（明确排除 edge/connection） |

两处不一致时，导入器按冻结规则重算并把差异记入台账（`preserved_and_flagged`，库内保留暂存值）。

| 数据集 | 受影响地点 |
|---|---:|
| `pleiades_gis_4_1` | 499 |
| `pleiades_gis_4_1_slice` | 130（**基线里就有**，对应基线 166 行） |
| 合计 | 629（820 个字段级差异） |

结论：**不是 M4-4b 引入的**，是归一化与导入器对"edge 子行是否参与地点包络"的口径分歧；
数据集变大后被放大。本轮按"不改已验收暂存"处理，**登记为遗留**（见 §十一）。
没有为此修改任何算法，也没有把台账数字压掉。

### 8.5 落库比暂存少的 6 行（名称 4 / 位置 2）

`uq_hpn_c08` 与 `uq_hpl_c07` 是 V2 就有的去重约束，与 M4-2 干净导入的表现完全一致
（当时 47,503→47,499、18,103→18,101）。不是本轮新增行为。

### 8.6 时间类型改判 7 行（其中 5 行是本轮的）

mask 分支"两端相等 ⇒ snapshot"的规则不变；4.1 里另有 5 条名称行（`Yafā`、`Bidlīs`、
`Mazaquete`、`Ādīnapūr`、`Adīnapūr`，均 1500–1500）满足同一条件。
断言已改为"改判集合 = 规则推导集合"，不再写死 2 行。

---

## 九、交付物与打包

### 9.1 本轮代码变更

| 文件 | 变更 | 说明 |
|---|---|---|
| `code/ops/import_staging.py` | +30 / −4 | §8.1 动词映射、§8.2 几何修正、§8.3 G1 修正 |
| `code/ops/m4-4a/V9_checks.sql` | 改写 §1.2 | 区分"CHECK 允许值数"与"库内实际类型数" |
| `code/ops/m4-4b/fingerprint.sql` | 新增 | 可重复的关键数据指纹 |
| `code/ops/m4-4b/verify_import_m4_4b.py` | 新增 | 79 条数据库验收判据 |
| `code/ops/reports/m4-4b/*.json` / `*.csv` | 新增 | 取证快照与 400 行未入库留痕 |
| `code/ops/reports/m4-4b/*.log` | 新增 18 份 | 执行日志。**注意**：`code/.gitignore` 忽略 `*.log`，因此这些日志只在磁盘与本交付包里，不在 Git 里 |
| `code/ops/reports/M4_4B_IMPORT_REPORT.md` | 新增 | 本报告 |

未改：V1–V8、所有前端代码、`normalize.py` / `pleiades_extract.py` / `datasets.py`、原始数据、既有 staging。

### 9.2 打包

`汇报/2026-11-04/<HHMMSS>/`：

| 文件 | 内容 |
|---|---|
| `M4-4b_施工与验收报告.md` | 本报告 |
| `M4-4b_源码包.zip` | 本轮改动的源码 + V9 + 验收脚本 + 报告 + 交付说明（**不含** `.env`、原始 ZIP、staging CSV、`ops/.deps`） |
| `SHA256SUMS.txt` | 上述两件 + 全部日志的 sha256 |
| `交付说明.md` | 目录导读与复核命令 |
| `logs/` | 18 份执行日志（V9、导入、验收、幂等、保护、指纹） |
| `verify_m4_4b.json` | 79 条判据的机器可读结果 |

### 9.3 数据库结论记录

| 项 | 值 |
|---|---|
| 库名 | `canvas_history_m4_4b`（**保留**） |
| PostgreSQL / PostGIS | 17.11 / 3.6（GEOS 3.14.1） |
| Flyway 版本 | V9 |
| 库大小 | 630 MB |
| 结构指纹（`pg_dump -s \| sha256`） | `f72cc74bef872cced0eb74f878b09a62012207ffeb287b4d878020380d263283` |
| V9 checksum | 259549483 |
| 受控副本 | `canvas_history_m4_4b_protect`（保留了 3 个受保护地点，仅供审阅） |

---

## 十、Git

| 项 | 值 |
|---|---|
| 分支 | `m4-3-pleiades-gis`（沿用，未开新分支、未推送远程） |
| 历史 | 未覆盖：`01c5ef8` / `3e277c3` 仍在 |
| 代码提交 | `4459b63` fix(m4-4b): apply V9, import five sources and fix three importer defects |
| 报告提交 | 本文件所在提交（`docs(m4-4b): …`），见 `git log` |
| 未入库 | `code/ops/reports/m4-4b/*.log`（被 `code/.gitignore` 的 `*.log` 忽略）、`汇报/`（交付目录） |

---

## 十一、遗留（不阻塞 M4-4c，均已在报告中量化）

| # | 事项 | 影响 | 建议 |
|---|---|---|---|
| 1 | 地点级时间包络是否含 connection：归一化与导入器口径不同 | 629 个地点的 `valid_from/valid_to` 比导入器口径更宽；820 条 warning 台账 | M4-5 前统一口径（改 `normalize._place_time_bounds` 排除 connection，并重建暂存） |
| 2 | 暂存 `action_taken` 用了 2 个库外动词 | 732 行靠导入器映射，原值留在 `resolution_note` | 下一轮改归一化产物或扩宽值域 |
| 3 | `place_type` 仅 `settlement`/`unknown` | 26,383 个 NEW 地点无类型粒度 | 视需要建 `place_type_link` |
| 4 | `is_preferred` 全 `false` | 当前查询按 `location_id` 取首行 | 需要"优先位置"语义时再改 |
| 5 | 42 行 `name_lang` 落到 `und` | 少数语言标签丢失 | 需要保真时加 `raw_language_tag` 列 |

---

## 十二、边界确认

| 禁止项 | 是否发生 |
|---|---|
| 连接正式库 `canvas_history` 执行写操作 | **否**（仅只读 SELECT） |
| 修改 `canvas_history_m2check` / `canvas_history_m4check` | **否**（只作为克隆模板读取） |
| 覆盖原有 staging | **否**（`code/data/staging/` 未动） |
| 修改 V1–V8 | **否**（迁移目录只有 V9） |
| 新增 V10 或业务表 | **否** |
| 修改 Pleiades 已冻结的数据语义 | **否**（13,603 连接、3,317 代表点、2,552 重叠全部按冻结口径） |
| 修改前端 | **否** |
| 启动 M4-4c / M4-5 | **否** |

本轮唯一"计划外但必要"的三处改动，全部是导入器的最小修正（§8.1–8.3），
且都在 dry-run 阶段被数据本身暴露，没有绕过任何约束。

---

**M4-4b — IMPORT + VERIFICATION COMPLETE / WAITING FOR OWNER SIGN-OFF（未启动 M4-4c）**
