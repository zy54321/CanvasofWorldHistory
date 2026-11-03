# 阶段三 · 正式数据库首次导入报告

**最终判定：PASS**（数据入库与全部完整性检查通过）；其中 **1 项 UNVERIFIED**：V8「双轮幂等」不适用于单轮正式导入，未伪造第二轮快照。

| 项 | 结果 |
|---|---|
| 导入程序退出码 | **0** |
| 事务提交状态（独立连接确认） | **已提交**（COMMITTED），九表有数据 |
| 九张表数量 | **9/9 与预期完全一致** |
| 七个导入批次 | **7/7 succeeded**，G1 逐批 residual = 0 |
| 外键 / 唯一键 / 派生视图 / 关联 | 全部 **PASS** |
| 六条排除记录 | **6/6 与已验收版本语义一致**，收敛目标在库中落地 |
| `infra.smoke_check` | **原样保留**（1 行，内容与时间戳未变） |
| Flyway | **V1/V2/V3 校验和未变** |
| 幂等（V8） | **UNVERIFIED**（单轮导入无第二轮快照；按纪律未重复执行导入） |

---

## 1. 执行环境与命令

- 执行时间（UTC）：**2026-11-03T08:44:33Z**（本地 16:44）
- 工作目录：`E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code`
- 数据库身份（独立连接实测）：`current_database()=canvas_history`、`current_user=canvas_app`、PostgreSQL 17.11
- 实际执行命令：

```bash
cd E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/code
PYTHONPATH=./ops/.deps python ./ops/import_staging.py \
  --db canvas_history \
  --summary-json ./ops/reports/formal_import_20261103/formal_import_summary.json \
  --excluded-csv ./ops/reports/formal_import_20261103/formal_import_excluded.csv
```

- **退出码：0**；日志：`ops/reports/formal_import_20261103/02_import.log`（末尾 `✓ 事务已提交`）
- 未带 `--dry-run`、未带 `--inject-fault`；未改任何 CSV / Migration / DDL；未重置序列；未覆盖任何历史证据
  （输出目录 `formal_import_20261103/` 为本轮新建，此前不存在）

### 1.1 执行前五项检查（全部通过）

| 检查 | 结果 |
|---|---|
| 七张 CSV SHA256 vs R1.2 基线 | **7/7 逐字节一致** |
| 数据库身份 | `canvas_history` / `canvas_app` ✅ |
| 九张业务表 | 执行前**全部 0 行** ✅ |
| Flyway V1/V2/V3 | 均 Success，校验和 `882334605 / 966227528 / -2058740630` ✅ |
| 输出路径 | 新目录，未占用历史文件 ✅ |

证据：`01_precheck.log`

## 2. 九张表实际行数（独立新连接直查，不读摘要）

| 数据表 | 预期 | 实际 | 判定 |
|---|---:|---:|---|
| source_record | 29,391 | **29,391** | PASS |
| historical_place | 19,039 | **19,039** | PASS |
| historical_place_name | 47,499 | **47,499** | PASS |
| historical_place_location | 18,101 | **18,101** | PASS |
| candidate_match | 53,131 | **53,131** | PASS |
| data_quality_issue | 12,831 | **12,831** | PASS |
| import_batch | 7 | **7** | PASS |
| data_dataset | 7 | **7** | PASS |
| data_source | 4 | **4** | PASS |

摘要（`formal_import_summary.json`）：`dry_run=false, committed=true, exit_code=0, assert_ok=true`；
`counts_before` 九表全 0，`counts_after` 与上表一致。**摘要与独立查询结果逐表相等**。
证据：`03_counts_and_batches.log`

## 3. 七个批次

| batch_id | dataset_id | status | input | 新增(活性) | 隔离 | 更新 | 无变化 | 跳过 | 失败 | G1 residual |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 14 | chgis_v6_prefecture_points | succeeded | 5,226 | 5,224 | 2 | 0 | 0 | 0 | 0 | 0 |
| 15 | chgis_v6_county_points | succeeded | 10,522 | 10,522 | 0 | 0 | 0 | 0 | 0 | 0 |
| 16 | mcgd_zenodo_22094815_head960 | succeeded | 960 | 960 | 0 | 0 | 0 | 0 | 0 | 0 |
| 17 | pleiades_gis_4_1_slice | succeeded | 12,445 | 12,444 | 1 | 0 | 0 | 0 | 0 | 0 |
| 18 | whg_geoname_s_gn_sample | succeeded | 209 | 209 | 0 | 0 | 0 | 0 | 0 | 0 |
| 19 | whg_getty_tgn_sample | succeeded | 21 | 21 | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | whg_hgis_de_las_indias_sample | succeeded | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| **合计** | | **7/7 succeeded** | **29,391** | **29,388** | **3** | 0 | 0 | 0 | 0 | **0** |

- `input_sha256` 七批全部等于 `source_records.csv` 的基线值；`rollback_of_batch_id` 全为空；`operator=ops/import_staging.py`
- 程序内断言：`批次断言 ✓ 通过；时间类型断言 ✓ 通过`（A1–A9、G1、A10、F17a/F17a'/F17b=17 与基线一致，nm_0045996 / nm_0046197 逐行 snapshot 复核）
- 观察（非缺陷）：`batch_id` 为 **14–20** 而非 1–7 —— `import_batch` 主键序列在 dry-run 与更早的验证轮中已推进；主键值不影响语义
- 证据：`03_counts_and_batches.log`、`06_batch_counters.log`

## 4. 完整性检查（独立 SQL，逐项）

| 检查 | 结果 | 判定 |
|---|---|---|
| 外键孤儿（25 条 FK 逐条 LEFT JOIN 全表扫描） | 孤儿 **0** | PASS |
| C01 `source_record` 五段键重复 | 0 | PASS |
| C04 `place (dataset_id, grain_key)` 重复 | 0 | PASS |
| C08 `name` 四段键重复 | 0 | PASS |
| C09 `candidate_match` 业务键重复 | 0 | PASS |
| C10 `issue_fingerprint` 重复 | 0 | PASS |
| `v_place_evidence` | 84,958 行 / canonical 19,039 | PASS |
| `v_place_liveness` | 19,039 行 | PASS |
| `v_place_time_span` | 19,039 行（envelope 17,108 / no_evidence 1,570 / single_point 361） | PASS |
| name / location 指向不存在的地点 | 0 / 0 | PASS |
| name / location 的 `source_record_id` 为空 | 0 | PASS |
| 每地点 anchor 恰 1 条（≠1 的地点） | 0 | PASS |
| anchor 的源记录与 `created_from_source_record_id` 不符 | 0 | PASS |
| `created_from_source_record_id` 为空 | 0 | PASS |
| 人工保护位（locked / manual_edited_fields 非空） | 0 / 0（首次导入应为 0） | PASS |
| `created_by` 分布 | `import` 19,039 | PASS |
| 隔离源记录 | 3 条（20469 / 35000 / 35001，`duplicate_quarantine`），保留未删 | PASS |
| 隔离源的 name/location 子行 | 0（隔离行未写子表） | PASS |
| 台账 `manual_edit_conflict` | 0（首次导入应为 0） | PASS |
| 台账 `licence_unconfirmed` | 0 | PASS |
| 台账 issue_type 分布 | 14 种，合计 12,831（unknown_time_bound_type 6,448 / parent_place_not_in_sample 4,810 / unknown_crs 646 / beg_eq_end 341 / missing_coordinate 337 / derived_value_mismatch 197 / beg_gt_end 28 / coordinate_outside_china_bbox 6 / duplicate_external_id 5 / truncated_slice_tail 4 / year_out_of_range 4 / duplicate_sysid 2 / nonstandard_field_name 2 / coordinate_out_of_range 1） | PASS |
| `infra.smoke_check` | 1 行原样保留：`(1, stage1-persistence, 容器重启前写入…, 2026-11-03 12:21:53.295889+08)` | PASS |
| Flyway | `1:882334605 success / 2:966227528 success / 3:-2058740630 success`，与导入前**一致** | PASS |

证据：`05_integrity_checks.log`

## 5. 核验脚本结果（`04_verify_import.log`）

| 项 | 结果 | 说明 |
|---|---|---|
| V1 七张 CSV 指纹 + 批次逐条 SHA256 | **PASS** | 7 个批次全部等于基线 |
| V2 行数链 | **PASS** | 29,391−0 / 47,503−4 隔离 / 18,103−2 隔离 / 53,137−6 留痕 / 12,631−2+5+197=12,831 |
| V3 外键 | **PASS** | 25 条 FK 0 孤儿 |
| V4 唯一键 | **PASS** | 5 组 0 冲突 |
| V5 坐标与 SRID | **PASS** | 18,091 行几何全 4326/Point；单侧 NULL 双向 0；无 geom 10 行 notes 齐备且台账覆盖 100%；越界 1 行 blocking |
| V6 三个派生视图 | **PASS** | 84,958 = 19,358+47,499+18,101；四列双向差集 0；时间跨度 9 列重算 0 不一致 |
| V7 质量台账 | **PASS** | 12,831 / 14 种 / mismatch 197 条 130 地点 / licence 0 |
| **V8 双轮幂等** | **FAIL（不适用）** | 缺 `run2_summary.json` —— **本轮是单轮正式导入**，按纪律不得为凑证据再跑一轮。**不判 PASS，列为 UNVERIFIED** |
| V9 批次推进 | **PASS** | 29,391 行 last_batch_id 均指向本数据集最新批 |
| V9b 内容变更 UPDATE 路径 | **UNVERIFIED** | 单轮 `updated=0`，路径未走到（历史遗留项，同 R1.2） |
| V12 C27/C28 | **PASS** | R4a–R4f 全 0；C28 19,039 行重算 0 不一致 |
| V13 候选表排除追溯 | **PASS** | 53,137 = 53,131 + 6；19 列全保留；行号/ID 无重复；4 条 C09 目标在库中可定位 |

脚本整体退出码为 1，**唯一原因是 V8 找不到第二轮快照**（无数据类 FAIL）。V8 覆盖面（两轮增量、两轮衔接、与库对账）
无法在单轮导入中成立，已改用第 2–4 节的独立 SQL 逐项核对九表数量、批次计数与库内一致性；**没有伪造第二轮快照**。

> `run1_summary.json` / `stage3_excluded_rows.csv` 是 `formal_import_summary.json` / `formal_import_excluded.csv`
> 的**同字节副本**（SHA256 分别相同），仅用于适配核验脚本的文件名约定，非新增证据。见 `00_aliases_note.log`。

## 6. 六条排除记录

- 文件：`formal_import_excluded.csv`，**6 行 / 24 列**（原始 19 列 + `staging_row_no` / `exclusion_reason` / `db_place_id_a` / `db_place_id_b` / `converged_to_candidate_id`）
- 原因分布：`c09_converged` 4 条、`self_reference` 2 条
- 与**已验收版本（R1.2）**逐行比对：**22 个语义字段 0 处差异**
- 与 **Dry-run 版本**逐行比对：22 个语义字段一致；`db_place_id` 两列整体后移 **+19,039**（dry-run 消耗了 19,039 个 place_id，正式导入从下一个值起），与序列账完全对得上
- 收敛目标在**正式库**中逐一落地：

| 留痕行 | 关系 | 库中保留行 | 判定 |
|---|---|---|---|
| cm_0025046 | ⇒ cm_0025045 | `same_coord_diff_entity` + (20541, 20542) 唯一 1 条 | PASS |
| cm_0025047 | ⇒ cm_0025045 | 同上 | PASS |
| cm_0025180 | ⇒ cm_0025179 | (27816, 20541) 唯一 1 条 | PASS |
| cm_0025182 | ⇒ cm_0025181 | (27816, 20542) 唯一 1 条 | PASS |
| cm_0052746 | 自指，无目标 | 同键行 0（`CHECK(place_id_a<>place_id_b)`） | PASS |
| cm_0052747 | 自指，无目标 | 同键行 0 | PASS |

- 恒等式：**入库 53,131 + 留痕 6 = 53,137（原始）**
- 证据：`05_integrity_checks.log` §6、`07_excluded_vs_dryrun.log`

## 7. Flyway 与 schema

```
1:882334605 success | 2:966227528 success | 3:-2058740630 success
```

与导入前、与 R1.2、与其余五座验证库完全一致 ⇒ **无 DDL 漂移、无结构变更**。

## 8. 异常与未验证事项

**无异常**（程序 EXIT 0，无警告，无 Traceback）。

需要登记的事项：

1. **V8 双轮幂等 = UNVERIFIED**：单轮正式导入没有第二轮快照。要补齐需再执行一次导入（会产生 7 个新批次并改写 `last_batch_id`），本轮**未获授权**，按要求不做。数据层面的"无重复入库"由 V4 唯一键 0 冲突、V9 批次指向、九表数量精确命中共同支撑，但这**不等于**已实测幂等。
2. **V9b（内容变更 → UPDATE 路径）= UNVERIFIED**：与 R1.2 相同的历史遗留项。
3. **主键区间因 dry-run 前移**（非缺陷，已在 Dry-run 报告中预告）：`import_batch` 为 **14–20**；
   `historical_place.place_id` 为 **19,046–38,084**；`historical_place_name.name_id` 为 **47,500–94,998**。
   均为库内自增代理键，编号不影响任何业务语义与校验结果。
4. 首次导入不存在人工保护与人工编辑，故 `locked` / `manual_edited_fields` / `manual_edit_conflict` 均为 0 属**预期**；保护机制本身已由 R1.2 的事务内夹具（P1/P2 PASS）验证，本轮未重复。

## 9. 交付物路径

| 文件 | 内容 |
|---|---|
| `ops/reports/formal_import_20261103/01_precheck.log` | 执行前五项检查 |
| `ops/reports/formal_import_20261103/02_import.log` | **正式导入完整日志（EXIT 0，事务已提交）** |
| `ops/reports/formal_import_20261103/formal_import_summary.json` | 正式导入摘要 |
| `ops/reports/formal_import_20261103/formal_import_excluded.csv` | 6 条排除留痕 |
| `ops/reports/formal_import_20261103/00_aliases_note.log` | 同字节别名说明与哈希 |
| `ops/reports/formal_import_20261103/03_counts_and_batches.log` | 独立行数 + 七批次状态 |
| `ops/reports/formal_import_20261103/04_verify_import.log` | V1–V13 核验脚本输出 |
| `ops/reports/formal_import_20261103/05_integrity_checks.log` | 八组独立 SQL 完整性核验 |
| `ops/reports/formal_import_20261103/06_batch_counters.log` | 批次六列计数与 G1 平衡 |
| `ops/reports/formal_import_20261103/07_excluded_vs_dryrun.log` | 留痕 vs Dry-run 比对 |
| `ops/reports/formal_import_20261103/08_final_recheck.log` | 收尾复核（九表算术、主键区间、批次状态、历史证据未被覆盖） |
| `ops/reports/formal_import_20261103/run1_summary.json`、`stage3_excluded_rows.csv` | 上述两份文件的同字节副本（供核验脚本按名读取） |

## 10. 停止声明

正式导入与独立验收已完成。**未**继续开发前端/后端功能，**未**新增表或功能，**未**重复执行导入，**未**清库或重置序列。
按指令在此停止，等待 Owner 验收后再进入下一施工阶段。
