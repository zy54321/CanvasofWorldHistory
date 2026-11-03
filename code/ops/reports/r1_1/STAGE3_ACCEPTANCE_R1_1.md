# 阶段三 · 交付验收修订 R1.1

> 本轮范围：**只**修 Owner 指出的四处 QA 判据不严（V1 / V5 / V6 / V8）。
> 未改 DDL、未改 Migration、未改原始 CSV、未改 V2.1.1 设计文件；未重建架构；未触碰正式库。
> 正式库 `canvas_history` 九张表 **仍全部为 0 行**（本轮实测，见 §6）。

- 修订对象：`ops/verify_import.py`（主要）、`ops/import_staging.py`（仅输出路径参数）
- 新验证库：`canvas_history_stage3_r11`、`canvas_history_stage3_r11_fault`（均为空库新迁 V1–V3）
- 旧库 `canvas_history_stage3`、`canvas_history_stage3_r1` **原样保留**，未做任何写入
- 本轮日志目录：`ops/reports/r1_1/`（00–07 按序）

---

## 1. 四处判据的修订与证据

### 1.1 V1 批次 SHA256 逐批核对

| 项 | R1（旧） | R1.1（新） |
|---|---|---|
| 取数 | `SELECT DISTINCT input_sha256 FROM import_batch` + `fetchone()` | `SELECT batch_id, dataset_id, input_file, input_sha256 … ORDER BY batch_id` 全量遍历 |
| 判定 | 只比第一行；若某批写错，DISTINCT 返回 2 行时 `fetchone()` 可能恰好取到正确的那行 ⇒ 假 PASS | 每一批都必须等于**其 `input_file` 对应的基线值**；`NULL` 判失败；`input_file` 不在基线表判失败 |

实测（本轮 2 轮导入 = 14 个批次）：

```
import_batch 共 14 个批次（逐条核对，不取 DISTINCT 首行）
  batch   8  chgis_v6_prefecture_points      source_records.csv  30fed0e40ba12496…  = 基线 source_records.csv
  …（共 14 行，逐行打印，见 04_verify_import.log）
  指纹集合：1 种；NULL 0 条；无基线 input_file 0 条；与基线不符 0 条
✓ V1 7/7 文件指纹与基线逐字节相等；import_batch 14 个批次逐条核对，全部 input_sha256 = 其 input_file 的基线值
```

七张 CSV 的 SHA256 亦逐文件与 `STAGING_FIELD_BASELINE.md` 基线比对（结果 7/7 相等）。

### 1.2 V5 坐标比较改 NULL 安全 + 无 geom 归因 + 越界台账等级

| 项 | R1（旧） | R1.1（新） |
|---|---|---|
| 坐标比较 | `ST_X(geom) <> representative_lon OR ST_Y(geom) <> …` —— 任一侧为 `NULL` 时结果是 `NULL`（不是 `TRUE`），**该行被静默跳过** | `ST_X(geom) IS DISTINCT FROM representative_lon OR ST_Y(geom) IS DISTINCT FROM …`，单侧 `NULL` 也计入不一致 |
| 无 geom 行 | 只在文案里写「均为 staging」，**未查询** | 现场查 `record_status × crs_confidence` 分布 + `published` 计数 + `notes` 为空计数，`published` 必须为 0 才 PASS |
| 越界坐标 | 只查台账是否存在该 `observed_value` | 逐条取 `issue_type` / `severity` / `action_taken`，要求 `coordinate_out_of_range` + `blocking` + `preserved_and_flagged`，并核 `source_record_id` 归属 |
| 附加 | — | 有 geom 缺坐标 / 有坐标缺 geom / lon-lat 单侧 NULL，三项目前均为 0 |

实测：

```
共 18,101 行坐标行：有 geom 18,091 / 有 lon+lat 18,091
SRID=4326 18,091 / ST_Point 18,091 / geom_type='Point' 18,091  ✓
geom 与 representative_lon/lat 不一致（IS DISTINCT FROM，含单侧 NULL）0  ✓
有 geom 但缺坐标 0；有坐标但无 geom 0
坐标越界 1；lon/lat 单侧为 NULL 0

无 geom 行的状态分布（record_status / crs_confidence / 行数 / notes 为空的行数）：
  staging      confirmed     10 行   notes 空 0
其中 published 0（C14/C15 拦截口径）；crs_confidence='unknown' 0
C14/C15 违例（published 且 geom 空或 CRS 未知）0

越界坐标逐条核对：
  location 34487  place 35425「Aleitai」(mcgd_zenodo_22094815_head960)  lon=881.41253 lat=47.844924
    → 台账 [(20309, 'coordinate_out_of_range', 'blocking', 'LONG', 'preserved_and_flagged')]  ✓ 类型/等级/处置相符
    → 台账 place_id=None（暂存台账未回填地点，可经 source_record_id=45931 反查得 place 35425，与坐标行归属一致）
```

那 10 行无 geom 的确切原因（原样保留，不修补）：CHGIS 县治点位中 `X_COOR`/`Y_COOR` 为 DBF 字段溢出标记 `**********`，
坐标在源文件层即已丢失；`notes` 逐行写明 `coordinate lost to DBF field-overflow marker`。它们全部为 `staging`，
不触发 C15（C15 只拦 `published`），也不需要伪造坐标。

### 1.3 V6 证据视图完整性与时间跨度实际派生结果

R1 的判据只有「列数 + 一个行数 + `valid_child_rows > 0`」。R1.1 拆成 8 组，全部进判定：

| 组 | 判据 | 实测 |
|---|---|---|
| 6.1 | 列数 11 / 7 / 10 | 11 / 7 / 10 ✓ |
| 6.2 | 两地点级视图行数 = 地点数；证据视图行数 ≥ 地点数 | 19,039 / 19,039 / 84,958 ✓ |
| 6.3 | canonical **每地点恰 1 行**（`GROUP BY place_id HAVING count(*) FILTER (is_canonical_row) <> 1`） | canonical≠1 的地点 **0**；canonical 行 19,039 = 地点数；覆盖 19,039/19,039；无证据行地点 0 |
| 6.4 | 证据行与子表**双向** `EXCEPT` 恒等 + `child_record_status`/`child_rejected_by` 与子表一致 | name 47,499↔47,499、location 18,101↔18,101，**两向差集均 0**；状态不一致 0 |
| 6.5 | creator 行 `child_row_id/table/status` 必须为空；`is_anchor` 每地点恰 1 且等于 `created_from_source_record_id` | 19,358 creator 行；违规 **0 / 0 / 0 / 0** |
| 6.6 | `source_is_active` / `source_inactive_reason` 忠实于 `source_record`；不得有无源证据行 | 不一致 0；孤儿 0 |
| 6.7 | 时间跨度**独立重算 9 个派生列** + `derivation_kind` 三值 + `all_children_rejected` | 不一致地点 **0** |
| 6.8 | `no_evidence` 必须两列全 NULL；`single_point` 必须两端相等且非空 | 违规 0 |

6.7 的重算式（日志中逐项可比对）：从 `historical_place_name` ∪ `historical_place_location` 出发，
过滤 `record_status <> 'rejected' AND sr.is_active`，再 `min(f)/max(t)/count(...)` 聚合，与视图
`span_from_astro / span_to_astro / from_evidence_rows / to_evidence_rows / staging_evidence_rows /
valid_child_rows / child_rows_total` 逐列 `IS DISTINCT FROM` 比对。

实测派生结果分布（不再只看 `> 0`）：

```
envelope_of_name_and_location_rows  17,108   span_from NULL 0      两端相等 0
no_evidence                          1,570   span_from NULL 1,570  两端相等 0
single_point                           361   span_from NULL 0      两端相等 361
有实际派生结果（span_from 非空且 valid_child_rows>0）17,469 行
```

`no_evidence 1,570` 与 `span_from IS NULL` 的 1,570 完全对齐；`single_point 361` 全部两端相等——
两者都是语义自洽的强证据，而不是「行数大于 0 就 PASS」。

### 1.4 V8 从两轮快照独立计算 + 摘要完整性

| 项 | R1（旧） | R1.1（新） |
|---|---|---|
| 缺字段 | `d.get(t, 0)` / `s.get(...)` —— 缺失即当 0，缺表会被算成「净增 0」而恰好满足幂等判据 | `_load_summary()` 先做完整性校验：11 个必备键、`counts_before`/`counts_after`/`table_delta_inserted` 必须覆盖 **9 张表且值为 int**，缺一项直接 FAIL 并打印缺什么 |
| 增量 | 直接读程序自报的 `table_delta_inserted` | **独立复算** `Δ = counts_after − counts_before`，再与自报值交叉核对（不一致即 FAIL） |
| 链条 | 无 | `run1.counts_after` 必须逐表等于 `run2.counts_before` |
| 第三方校验 | 无 | 用**当前库实际行数**逐表比对 `run2.counts_after` |

实测：

```
两轮快照字段完整（11 个必备键 + 9 表逐表计数齐备）
run1: Δ+29391 Δ+19039 Δ+47499 Δ+18101 Δ+53131 Δ+12831 Δ+7 Δ+7 Δ+4
run2: Δ+0 Δ+0 Δ+0 Δ+0 Δ+0 Δ+0 Δ+7 Δ+0 Δ+0
首轮数据表净增为 0 或负的表：无
次轮数据表净增非 0 的表：无
次轮 import_batch 净增 +7（每轮新建 7 批，属预期）
两轮衔接（run1.after == run2.before）不一致的表：无
当前库实际行数 vs run2.counts_after 不一致的表：无
次轮 source_stat：{inserted: 0, updated: 0, touched: 29388, held: 3}
```

注：`import_batch` 每轮 +7 是设计行为（每数据集 1 批），故「净增为 0」的判据只施加于六张业务表，
但 `import_batch` 的增量仍被独立复算并打印，不做静默忽略。

**负向对照（证明新判据不空转）**：把 `run2_summary.json` 故意删掉 `counts_after.data_quality_issue`
与顶层 `table_delta_inserted` 后重跑：

```
      ✗ run2 快照缺字段 ['table_delta_inserted']
      ✗ run2.counts_after 缺表字段 ['data_quality_issue']
      ✗ run2.table_delta_inserted 不是对象
  ✗ [V8] 执行快照不完整，幂等性无可靠证据
EXIT=1
```

R1 的实现会把这两个缺失读成 0，从而**恰好满足**「净增 0」的判据；现在直接 FAIL 并列出缺什么。

---

## 2. 执行记录（`ops/reports/r1_1/`，全部为本次真实执行）

| # | 动作 | 命令要点 | 退出码 | 日志 |
|---:|---|---|---:|---|
| 0 | 空库试运行并回滚 | `--dry-run` | 0 | `00_dryrun.log` |
| 1 | 首轮完整导入并提交 | `--summary-json run1_summary.json` | 0 | `01_run1_import.log` |
| 2 | 重复导入（幂等） | `--summary-json run2_summary.json` | 0 | `02_run2_idempotent.log` |
| 3 | 断言失败回滚（空库 + 注入） | `--inject-fault g1` | **3** | `03_fault_before_state.log` / `03_fault_injection.log` / `03_fault_after_state.log` / `fault_injection_summary.json` |
| 4 | 全量核验 | `verify_import.py --run-dir ops/reports/r1_1` | 0 | `04_verify_import.log` |
| 5 | 人工保护 + 回滚四道闸 + 真值表 | `verify_rollback_and_protection.py` | 0 | `05_verify_rollback.log` |
| 6 | 夹具回滚后复检 | 同 4 | 0 | `06_post_fixture_recheck.log`（结论行与 04 逐行 `diff` **IDENTICAL**） |
| 7 | 时间类型逐行核验（SQL 独立取证） | `psql` | 0 | `07_time_type_rowcheck.log` |
| 8 | **负向对照**：故意改残 run2 摘要再核验 | `--run-dir ops/reports/r1_1_negctl` | **1** | `08_negative_control.log`（夹具说明见 `r1_1_negctl/README.txt`） |

首轮事务内前后快照（非事后估算）：

```
source_record            0 →  29,391     historical_place_location  0 →  18,101
historical_place         0 →  19,039     candidate_match            0 →  53,131
historical_place_name    0 →  47,499     data_quality_issue         0 →  12,831
```

### 2.1 断言失败确实回滚，数据库无残留

```
BEFORE  sr=0 place=0 name=0 loc=0 cand=0 ledger=0 batch=0 dataset=0 source=0
FAULT_EXIT=3
AFTER   sr=0 place=0 name=0 loc=0 cand=0 ledger=0 batch=0 dataset=0 source=0 succeeded=0
  批次断言 ✗ 失败；时间类型断言 ✓ 通过
✗ 断言失败，整批回滚（import_batch 未残留 succeeded）：断言未全部通过（批次=False, 时间类型=True）⇒ 整批回滚，不得提交
```

九张表前后全 0、`import_batch` 无任何行、`succeeded` 计数 0 —— 断言失败时**没有**任何残留写入。

`fault_injection_summary.json` 里 `counts_after = null` 是**如实留白**而非缺字段：断言在 `run()` 中途抛出，
事务从未走到「提交前快照」那一步，程序不伪造这个值；「回滚后状态」由 `03_fault_after_state.log` 用 psql 独立取数。

---

## 3. 核验结果（`r1_1/04_verify_import.log` 汇总）

| 编号 | 结论 | 关键取证 |
|---|---|---|
| V1 | PASS | 7/7 文件 SHA256 = 基线；**14 个批次逐条**核对，NULL 0 / 不符 0 |
| V2 | PASS | 29,391 / 19,039 / 47,499=47,503−4 / 18,101=18,103−2 / 53,131=53,137−6 / 12,831=12,631−2+5+197 |
| V3 | PASS | 25 条外键全表扫描 0 孤儿 |
| V4 | PASS | C01/C04/C08/C09/C10 五组唯一键 0 冲突 |
| V5 | PASS | 18,091 行几何 SRID=4326/Point；`IS DISTINCT FROM` 比较 0 不一致；无 geom 10 行全非 published（`notes` 均载明坐标丢失）；1 行越界由 `coordinate_out_of_range(blocking, preserved_and_flagged)` 登记 |
| V6 | PASS | 列 11/7/10；canonical 每地点恰 1；证据行 84,958 = creator 19,358 + name 47,499 + location 18,101，双向差集 0；时间跨度 9 列重算 0 不一致，实际派生 17,469 行 |
| V7 | PASS | 12,831 行（目标 12,831）/ 14 种类型 / 偏差 197 条落在 130 地点 / `duplicate_external_id` 5 / licence 0 |
| V8 | PASS | 快照字段完整；独立复算首轮全净增、次轮全 0；两轮衔接无断点；与当前库逐表相等 |
| V9 | PASS | 29,391 行 `last_batch_id` 均指本数据集最新批；`first_batch_id` 未被重跑改写 |
| V9b | **UNVERIFIED** | content_hash 变化的更新路径本次未走到（`updated=0`） |
| V12 | PASS | R4a–R4f 全 0；19,039 行按优先级重算 liveness 0 不一致 |
| V12b | INFO | 本库仅出现 1 个合法格；穷尽性由 T 夹具证明（7/7） |
| V13 | PASS | 53,137 = 53,131 + 6，逐条可回指原始行且字段逐字相符 |

合计 13 项：**PASS 11 / FAIL 0 / UNVERIFIED 1**。

`r1_1/05_verify_rollback.log`（9 项，PASS 8）：

- **P1** locked / `manual_edited_fields` / `created_by=manual` 三种保护位均未被覆盖，`blocked_count=3` 与 `manual_edit_conflict=3` 1:1
- **P2** 全库仅这 3 个地点被挡，其余 19,036 个地点重跑判为 no_change（无误挡）
- **Q1** R1：回滚成功 3 == (|B|11 − N_quar 2) − N_noop 1 − blocked 4 − failed 1 = 3
- **Q2** 判定顺序反证：若先判 `is_active=false`，R1 右式变 **−2**（差 5）⇒ 顺序不可换
- **Q3** R2：回滚期台账 4 == N_blocked 4（1:1 行级）
- **Q4** R2c：`import_row_error` 1 == N_fail_rb 1（受控注入；设计 §11 U5 保留仍成立）
- **Q5** 3 行软撤后 liveness 变 `all_sources_rolled_back`，被挡 4 行仍 `active`
- **T1** 真值表 7 个合法格 7/7 命中；`R4a–R4e` 全 0，`R4f` 对故意造的 orphaned 反例返回 1（证明断言不空转）

### 3.1 时间类型逐行核验（`07_time_type_rowcheck.log`，SQL 侧独立取证）

```
 name_id | name_text | from_yr | to_yr | time_bound_type |        source_time_columns         | notes_ok
   93491 | Boxar     |    1500 |  1500 | snapshot        | year_after_which|year_before_which | t
   93692 | Catife    |    1500 |  1500 | snapshot        | year_after_which|year_before_which | t

name:     exact 21,610 / unknown 20,535 / exact_or_bounded 2,360 / tpq_taq 1,774 / bounded 1,164 / snapshot 56
location: exact  8,055 / unknown  7,656 / exact_or_bounded   812 / tpq_taq 1,159 / bounded   398 / snapshot 21
```

导入器的 A10 断言同时校验：mask 分支两端相等却非 snapshot = 0；mask 分支两端不等却是 snapshot = 0；
数字分支两端相等仍 bounded = **17**（CHGIS `'3|3'`，期望值）；两表越出七值域 = 0；逐类型分布与库内实查相等。

---

## 4. R1 → R1.1 差异说明

### 4.1 `ops/verify_import.py`（本轮主要修订）

| 位置 | R1 | R1.1 |
|---|---|---|
| V1 | `DISTINCT` + `fetchone()` 只验首行 | 遍历全部批次，逐行与其 `input_file` 基线比对；NULL / 无基线 / 不符分别计数并列入 FAIL 原因 |
| V5 | `<>` 比较（吞 NULL）；文案断言「均 staging」 | `IS DISTINCT FROM`；无 geom 行现场分组统计 + `published` 计数入判定；越界坐标逐条核 `issue_type`/`severity`/`action_taken`/`source_record_id`；新增「有 geom 缺坐标 / 有坐标缺 geom / 单侧 NULL」三项 |
| V6 | 列数 + 一个行数 + `valid_child_rows > 0` | 8 组判据：canonical 每地点唯一、双向 `EXCEPT` 恒等、子行状态一致、creator/anchor 规则、源状态忠实、时间跨度 9 列独立重算、`derivation_kind` 语义自洽 |
| V8 | `d.get(t, 0)` 默认 0，缺字段/缺表即当「净增 0」；只读自报的 `table_delta_inserted` | 摘要完整性前置校验（11 键 + 9 表 int）；`Δ = after − before` **独立复算**再与自报值交叉核对；新增两轮链条比对与「当前库 vs run2.counts_after」第三方校验 |
| 全局 | 硬编码路径 `ops/reports/r1/` | 新增 `--run-dir`（默认 `ops/reports/r1_1`）；台账口径提为常量 `LEDGER_STAGED/DROPPED/SYNTH_DUP/SYNTH_MIS/TARGET`、`MISMATCH_PLACES`，V2/V7 共用同一组数字 |

### 4.2 `ops/import_staging.py`

**导入语义零变更**，仅增加输出路径参数，避免本轮覆盖 R1 的证据文件：

| 位置 | 变更 |
|---|---|
| `Importer.__init__` | 新增 `excluded_csv` 参数（默认仍是 `ops/reports/stage3_excluded_rows.csv`） |
| `write_exclusion_trace()` | 输出路径由常量改为 `self.excluded_csv` |
| `main()` | 新增 `--excluded-csv`；快照 JSON 增记 `excluded_csv`（供 V13 定位本轮留痕文件） |

### 4.3 `verify_rollback_and_protection.py`

**本轮无代码变更**（Owner 未指出该脚本问题）。作为交付物一并提交，并在新库 `canvas_history_stage3_r11` 上重跑，结果见 §3。

---

## 5. 必须报告的事实（不写成 PASS）

1. **10 行无坐标是源数据层丢失，不是导入丢失**：CHGIS 县治中 `X_COOR`/`Y_COOR` 为 `**********`（DBF 字段溢出标记）。
   它们保留为 `staging` 且 `notes` 逐行载明原因，不修补、不伪造坐标，也不触发 C15。
2. **越界坐标 1 行（lon=881.41253）已原样保留**并由 `coordinate_out_of_range`（`blocking` / `preserved_and_flagged`）
   登记；其台账 `place_id` 为空（暂存台账未回填），但 `source_record_id=45931` 可反查到 place 35425，与坐标行归属一致。
3. **V7 的类型数是 14 不是 13**：暂存 13 种 − `licence_unconfirmed` 1 种 + 导入器合成 2 种。数字在日志里带算式。
4. **`CHANGELOG §B.6` 称两条改判行「已在 `beg_eq_end` 台账 341 行内」不成立**：341 条全是 CHGIS，
   `sr_0021392` / `sr_0021146` 在暂存台账中查无记录。按要求不新增台账（总数仍 12,831），差异登记在
   `IMPORT_VALIDATION_RULES.md` I-03 节末尾。
5. **R1.1 未触碰旧证据**：`ops/reports/stage3_excluded_rows.csv`（R1 留痕，6 行，mtime 14:36）与
   `ops/reports/r1/` 全部文件均未改写；本轮留痕写入 `ops/reports/r1_1/stage3_excluded_rows.csv`。

---

## 6. 库状态

| 库 | 状态 | 核对 |
|---|---|---|
| `canvas_history`（正式） | **九张表全部 0 行** | `sr=0 place=0 name=0 loc=0 cand=0 ledger=0 batch=0 dataset=0 source=0` |
| `canvas_history_stage3`（R1 前缺陷现场） | 未触碰 | `snapshot=54 / bounded=1,166` |
| `canvas_history_stage3_r1`（R1 验证库） | 未触碰 | 首轮 + 幂等轮 |
| `canvas_history_stage3_r11`（本轮） | 首轮 + 幂等轮 + 夹具（已回滚） | 见 §3 |
| `canvas_history_stage3_r11_fault` | 故障注入专用 | 九表 0 行、`succeeded` 0 |

四库 Flyway 校验和一致，**无任何 DDL 漂移**：

```
canvas_history             1=882334605 2=966227528 3=-2058740630
canvas_history_stage3      1=882334605 2=966227528 3=-2058740630
canvas_history_stage3_r1   1=882334605 2=966227528 3=-2058740630
canvas_history_stage3_r11  1=882334605 2=966227528 3=-2058740630
```

---

## 7. 仍未验证 / 待裁定

- **V9b 内容变更 ⇒ UPDATE 路径**：需构造 `content_hash` 变化的第三轮才能实测，本轮不做（Owner 未要求）。
- **R2c 失败路径 / R1·R2 在真实回滚批次上**：暂存三类台账全 0，只能受控注入让等式可测（1==1）；
  `ROLLBACK` §11 U5 的保留依然成立。
- `data_dataset.content_sha256` 留 NULL（无按数据集切分的原始文件）。
- 待裁定：4 源 + 7 数据集的种子数据归属；`canvas_history_migrationcheck` / `canvas_history_stage3` / `canvas_history_stage3_r1` 是否清理。

---

**正式库导入命令（等你验收放行后再执行）**：

```bash
PYTHONPATH=./ops/.deps python ops/import_staging.py --db canvas_history \
    --summary-json ops/reports/formal_run_summary.json
```
