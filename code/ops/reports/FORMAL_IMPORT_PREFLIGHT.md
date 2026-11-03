# 阶段三 · 正式数据库首次导入前 Dry-run 报告

- 执行时间（UTC）：2026-11-03T08:08:30Z ~ 08:10Z
- 工作目录：`E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code`
- 结论：**预演通过（EXIT 0，全部断言 ✓，九表数量逐项命中，事务已完整回滚，正式库仍全 0 行）**
- 未执行正式导入；未运行任何不带 `--dry-run` 的命令；未改 DDL / 原始 CSV / 设计文件。

## 1. 执行前检查（6 项，全部符合）

| # | 检查项 | 结果 | 证据 |
|---|---|---|---|
| 1 | 工作目录 | `E:/01_Work/.../014-CanvasofWorldHistory/code` | — |
| 2 | 七张 CSV SHA256 与 R1.2 基线 | **7/7 逐字节一致** | `formal_preflight_01_csv_fingerprint.log` |
| 3 | 数据库连接身份 | `db=canvas_history`，`user=canvas_app`（`current_user` 实测），PG 17.11 | `formal_preflight_02_db_state_before.log` |
| 4 | 正式库九张业务表 | **全部 0 行** | 同上 |
| 5 | Flyway V1/V2/V3 | 均 `Success`，校验和 `882334605 / 966227528 / -2058740630`，**无漂移** | `formal_preflight_03_flyway.log` |
| 6 | 执行前行数快照 | 已保存（九表 0 行；`infra.smoke_check` 1 行） | `formal_preflight_02_db_state_before.log` |

### 1.1 七张 CSV 指纹

| 文件 | 行数 | SHA256 |
|---|---:|---|
| `data_datasets.csv` | 7 | `fa44197e54b4da4a8af78b589d10a63a668184397f63dbdf842b5051a2ef636f` |
| `source_records.csv` | 29,391 | `30fed0e40ba124960ba008b030948394398a418a9cc58b333095614469771c5d` |
| `historical_places.csv` | 19,039 | `86db3ce6b94f9e31036a3785a55510d48eb43bd4ce998aaa5cad2f59b068533f` |
| `historical_place_names.csv` | 47,503 | `80674c0ded553241c6f4745db0d6957d4dd6617acdfa7918d503128c1690ebbd` |
| `historical_place_locations.csv` | 18,103 | `9e987ba578e933ed9bdb11564487125783b22623abf348b9201a74d562d637a2` |
| `candidate_matches.csv` | 53,137 | `4e29c2ec64ebe263c325bab5f0eb70dc922116dd737542cf234373d86c98ab12` |
| `data_quality_issues.csv` | 12,631 | `7a8ab3916e00dcb04308d89c816c7c8771c6f71ec598ee3e4188c6b643263602` |

### 1.2 数据库身份与 Flyway

```
db=canvas_history  user=canvas_app  server_pg=17.11 (Debian 17.11-1.pgdg13+2)
server=192.168.16.2:5432  client=192.168.16.1/32   （宿主 127.0.0.1:55432 映射）
flyway_schema_history: 1:882334605 success  |  2:966227528 success  |  3:-2058740630 success
```

### 1.3 执行前九表快照

```
source_record 0 | historical_place 0 | historical_place_name 0 | historical_place_location 0
candidate_match 0 | data_quality_issue 0 | import_batch 0 | data_dataset 0 | data_source 0
infra.smoke_check：1 行（id=1, marker=stage1-persistence, created_at=2026-11-03 12:21:53.295889+08）
```

## 2. Dry-run 执行

实际执行命令（与 Owner 给定参数等价，shell 换为 Git Bash 以便 UTF-8 日志不丢字）：

```bash
cd E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/code
PYTHONPATH=./ops/.deps python ./ops/import_staging.py \
  --db canvas_history \
  --dry-run \
  --summary-json ./ops/reports/formal_preflight_summary.json \
  --excluded-csv ./ops/reports/formal_preflight_excluded.csv
```

- 未使用 `--inject-fault`；已使用 `--dry-run`
- 排除留痕写入 **新文件** `formal_preflight_excluded.csv`，未覆盖 R1 / R1.1 / R1.2 任何历史文件
  （`r1_2/stage3_excluded_rows.csv` 的 SHA256 执行前后均为 `511704865665ea945ad5440283d7e53420676a84e55081b13a5f9ca7cfc701b2`）
- **退出码：0**，日志：`formal_preflight_04_dryrun.log`

### 2.1 断言结果（全部通过）

```
批次断言 ✓ 通过；时间类型断言 ✓ 通过

A1–A9 + G1（逐数据集，七批全部平衡）
  chgis_v6_prefecture_points      A1  5,226/5,226  G1 5,226 = 失败0 + 隔离2 + 新增5,224 + 更新0 + 无变化0 + 跳过0
  chgis_v6_county_points          A1 10,522/10,522 G1 10,522 = 0 + 0 + 10,522 + 0 + 0 + 0
  mcgd_zenodo_22094815_head960    A1    960/960    G1 960   = 0 + 0 + 960 + 0 + 0 + 0
  pleiades_gis_4_1_slice          A1 12,445/12,445 G1 12,445 = 0 + 1 + 12,444 + 0 + 0 + 0
  whg_geoname_s_gn_sample         A1    209/209    G1 209   = 0 + 0 + 209 + 0 + 0 + 0
  whg_getty_tgn_sample            A1     21/21     G1 21    = 0 + 0 + 21 + 0 + 0 + 0
  whg_hgis_de_las_indias_sample   A1      8/8      G1 8     = 0 + 0 + 8 + 0 + 0 + 0
  合计 source_record 29,391（活性 29,388 / 隔离 3）；duplicate_ordinal=0 29,377

A10 时间类型
  F17a / F17a' / 七值域外 均 0；F17b（数字分支两端相等仍 bounded）17（基线一致）
  name      exact 21,610 / unknown 20,535 / exact_or_bounded 2,360 / tpq_taq 1,774 / bounded 1,164 / snapshot 56  ✓
  location  exact  8,055 / unknown  7,656 / tpq_taq 1,159 / exact_or_bounded 812 / bounded 398 / snapshot 21  ✓
  逐行 nm_0045996、nm_0046197 → snapshot（1500–1500）✓
```

其他关键中间量：`I-01` name.notes 47,503/47,503 ✓、`I-02` grain_evidence 7/7 ✓、`content_hash` 两种规范化 29,391/29,391 相等 ✓、
`record_scope` 全部命中 4 值、`parent_external_id` 可派生 10,765、隔离 3 条、`candidate_match` 恒等式 53,137 − 6 = 53,131、
`data_quality_issue` 12,629 + 5 + 197 = 12,831 且唯一指纹 12,831 ✓。**无任何警告输出**。

### 2.2 预演九表数量（`counts_after`，事务提交前快照）

| 数据表 | 预期 | 预演实测 | 判定 |
|---|---:|---:|---|
| source_record | 29,391 | 29,391 | ✅ |
| historical_place | 19,039 | 19,039 | ✅ |
| historical_place_name | 47,499 | 47,499 | ✅ |
| historical_place_location | 18,101 | 18,101 | ✅ |
| candidate_match | 53,131 | 53,131 | ✅ |
| data_quality_issue | 12,831 | 12,831 | ✅ |
| import_batch | 7 | 7 | ✅ |
| data_dataset | 7 | 7 | ✅ |
| data_source | 4 | 4 | ✅ |

`counts_before` 九表全 0；`summary` 关键字段：`db=canvas_history, dry_run=true, inject_fault=null, exit_code=0,
committed=false, assert_ok=true`。
六张业务数据表数量与 R1.2 完全一致（29,391 / 19,039 / 47,499 / 18,101 / 53,131 / 12,831）。

## 3. 排除记录核对（`formal_preflight_excluded.csv`）

- 6 行，24 列（原始 19 列 + `staging_row_no` / `exclusion_reason` / `db_place_id_a` / `db_place_id_b` / `converged_to_candidate_id`）
- 原因分布：`c09_converged` 4 条 / `self_reference` 2 条
- **22 个语义字段（原始 19 列 + 行号 + 原因 + 收敛目标）与 R1.2 逐行一致，0 处差异**
- 4 条 C09 收敛目标（`cm_0025045` ×2 / `cm_0025179` / `cm_0025181`）均在原始 CSV 中存在且键一致；2 条自指行收敛目标为空
- 唯一差异：`db_place_id_a/b` 两列。它们是**本库内**的自增代理键，两库序列位置不同：
  本库此前序列停在 6 ⇒ 本轮首个 `place_id = 7` ⇒ `hp_001496 = 1,502`；
  r1_2 库的 dry-run 已占用 1..19,039 ⇒ 首轮首个 `place_id = 19,040` ⇒ `hp_001496 = 20,535`；
  差值 `20,535 − 1,502 = 19,033 = 19,040 − 7`，两列完全一致 ⇒ **纯编号差异，非内容差异**。
  留痕内部自洽（自指行 `a==b`：1502==1502、1503==1503）
- 证据：`formal_preflight_06_excluded_check.log`

> 该文件是**每库各自**的留痕：正式导入时会再生成一份带当时 place_id 的留痕，届时它的代理键才与正式库对应。

## 4. 回滚后的数据库实际状态（独立新连接查询）

`formal_preflight_05_db_state_after.log`

```
连接：db=canvas_history user=canvas_app（新连接，非 dry-run 会话）
source_record 0 | historical_place 0 | historical_place_name 0 | historical_place_location 0
candidate_match 0 | data_quality_issue 0 | import_batch 0 | data_dataset 0 | data_source 0
九表合计 0 行 ⇒ 全部为 0（已回滚，无残留）

infra.smoke_check：1 行，内容与执行前完全一致
  (1, 'stage1-persistence', '容器重启前写入，用于验证 named volume 持久化', 2026-11-03 12:21:53.295889+08)
```

日志中亦有明确回滚声明：`!! --dry-run：已回滚，未落库`；`summary.committed=false`。

## 5. 异常与警告

**无异常，无警告**（导入器 `warnings` 为空，日志无 `✗`）。

需要 Owner 知晓的两点**非缺陷观察**：

1. **序列位置前移**：`historical_place_place_id_seq.last_value = 19045, is_called = true`。
   可精确拆账：本次预演插入 19,039 行，而留痕里 `hp_001496`（在 `historical_places.csv` 中第 1,496 行）
   拿到 `place_id = 1502` ⇒ 本轮第一条地点 id = 7，即**本轮开始前序列已停在 6**，本轮占用 7..19,045 共 19,039 个。
   这 6 次消耗发生在本轮之前（阶段一曾对业务表做过写入探测，本库已无从追溯具体来源），**不是本轮造成的**。
   PostgreSQL 的 `nextval` 不随事务回滚，因此：

   - 本轮 dry-run **确实**把序列推进了 19,039（7..19,045 已用掉）；
   - **正式导入时 place_id 不会从 1 开始，而会从 19,046 起**，其余表同理。

   数据正确性不受影响（主键是代理键，行数与内容不受编号影响），但正式库的主键区间会与"从未写过库的空库"不同。
   本轮不允许改结构/写库，故未做 `ALTER SEQUENCE ... RESTART`；如需主键从 1 起，须由 Owner 明确授权后单独处理。
2. **排除留痕的代理键跨库不可比**（见 §3）：只影响 `db_place_id_*` 两列，语义字段逐行一致。

## 6. 交付物

| 文件 | 内容 |
|---|---|
| `ops/reports/FORMAL_IMPORT_PREFLIGHT.md` | 本报告 |
| `ops/reports/formal_preflight_summary.json` | Dry-run 执行快照（九表 before/after、G1 计数、留痕路径） |
| `ops/reports/formal_preflight_excluded.csv` | 本次预演的 6 条排除留痕 |
| `ops/reports/formal_preflight_01_csv_fingerprint.log` | 七张 CSV 指纹与行数 |
| `ops/reports/formal_preflight_02_db_state_before.log` | 数据库身份 + 执行前九表 + smoke_check |
| `ops/reports/formal_preflight_03_flyway.log` | Flyway 状态与校验和 |
| `ops/reports/formal_preflight_04_dryrun.log` | Dry-run 完整输出（EXIT 0） |
| `ops/reports/formal_preflight_05_db_state_after.log` | 回滚后九表 + smoke_check + 序列 |
| `ops/reports/formal_preflight_06_excluded_check.log` | 排除留痕逐字段核对 |

## 7. 停止声明

以上为**预演**结果。未执行正式导入，未运行不带 `--dry-run` 的导入命令，未修改数据库结构、原始 CSV、设计文件，
未覆盖任何历史证据。按指令在此停止，等待 Owner 验收。
