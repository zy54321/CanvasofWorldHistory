# M4-2 导入规则与系统行为修正报告

- 执行时间：2026-11-04（Asia/Shanghai）
- 分支：`m4-2-import-rules`（从 M4-1 验收点 `cbada4c` 拉出）
- 上一轮：M4-1 资产恢复与流水线复现（`b856175` + `cbada4c`）
- 结论：**M4-2 — COMPLETED / ACCEPTED**
- 正式库 `canvas_history`：**未触碰**，仍为 Flyway **V5**，九表行数与 M3 封存时逐表相同
- 测试库：`canvas_history_m2check`（既有 M2/M3 夹具 + 全量导入）与 `canvas_history_m4check`（干净库，用于数量基线）
  均为 **V8**

> 本轮做三件事：把许可门禁连同相关字段与文档彻底清出系统；把「来源信息」从准入条件降为可选追溯信息，
> 并修好 M3 遗留的手工地点不上图；在真实数据库上重新确立导入数量基线、重验幂等与人工修改保护。

---

## 零、开工前文档修正（M4-1 报告三处）

按 Owner 指示只改文档，不动 M4-1 已验收的资产与基线：

| # | 位置 | 修正 |
|---|---|---|
| 1 | `M4_1_ASSET_RECOVERY_REPORT.md` §1.3 | 明确 `$ICJY9IU`（整个 `code/p0`）回收站记录为 **135,626,661 字节**；本轮只恢复其中 23 个核心文件共 **511,225 字节**，未恢复的 135,115,436 字节是 `wb-001-maptiler-demo` 的源码、`dist` 与 `node_modules` |
| 2 | 同上 §3.1 | 明确 23 个文件 = **20 个 Python + 2 个 Shell + 1 个 README**；README 是文档、不是运行时依赖，流水线运行时只 import 那 20 个 `.py` |
| 3 | 同上 首部与 §5 | 从 `git rev-parse` 取得完整 Commit ID：恢复提交 `b856175ca5bd7b11678ca1414a958c09fd91fc5f`，报告提交 `cbada4c0b85af4cbb9d93da24f875d8bfd16a17f` |

---

## 一、许可门禁清理清单

| # | 位置 | 改动 | 结果 |
|---|---|---|---|
| 1 | `ops/import_staging.py` 台账派生 | 删除 `if issue_type == 'licence_unconfirmed': continue` 分支，台账**零丢弃** | 12,631 行全部入库 |
| 2 | `ops/import_staging.py` 时间类型断言 A10 | 5 条分布/F17 断言与「分布逐类型比对」全部限定 `created_by='import'`，避免测试库里既有人工行污染判定 | 断言按导入自身输出判定 |
| 3 | `ops/verify_import.py` 常量 | 删除 `LEDGER_DROPPED = 2`；`LEDGER_TARGET` 改为 `暂存 + 合成`（12,833） | 不再有「许可剔除」常量 |
| 4 | `ops/verify_import.py` V2 | 台账期望改为 `暂存行 + 库内 dup + mismatch + manual_conflict` 动态计算；新增「license* 残留必须为 0」等式 | 七项等式 |
| 5 | `ops/verify_import.py` V7 | 删除「licence 必须为 0」这种许可门禁断言，改为「license* 残留 0 + 许可类 2 行已转写为 `attribution_missing`」 | 检查内容是否完整处理 |
| 6 | `ops/verify_import.py` V1 | 非本导入器创建的批次（如测试库 `demo.json`）列为 external 跳过，不再误判 NULL | 批次核对只针对导入批次 |
| 7 | `ops/verify_no_licence_gate.py` | **整文件删除**（`git rm`）。它本身就是一个「许可检查程序」 | 系统内不再存在许可审计工具 |
| 8 | `ops/IMPORT_VALIDATION_RULES.md` | 「与许可相关的两条口径」整节重写：旧版「2 行直接剔除」标注废止 | 现行口径与代码一致 |
| 9 | `ops/README.md` | 删除脚本表与示例中的 `verify_no_licence_gate.py` 两处 | — |
| 10 | `ops/verify_constraints.py` | 注释不再指向已删除的审计脚本 | — |
| 11 | `设计资料/V2.1.1_正式交付/CORE_DATA_MODEL_V2.1.1.md` §5.9 | 原文「2 行直接删除」处加 ⚠️ 标注：已被 M4-2 决策取代，暂存命中数 12,629 → 12,631；其余 19 值域与约束不变 | 旧设计留痕，不篡改历史 |
| 12 | `backend/.../PlaceQueryService.java` 等 | API 字段 `sourceLicenseNote` → `sourceNote`（它取的是 `data_source.notes` 普通备注，不涉许可） | 前后端同步改 |

删完再扫：`grep -ri "licen"` 在**现行系统代码**里只剩三类，均属正常——
① `settings` 无；② 设计文档的历史留痕（已标注被取代）；③ 第三方原始资料（`raw_payload` 里 WHG/CHGIS 原始 JSON 自带字段）。
`node_modules`、`ops/.deps` 为第三方依赖，不在清理范围。

## 二、许可相关字段处理结果

### 2.1 数据库

`information_schema` 全库扫描：**没有任何** `license/licence/redistributable/attribution` 列（M2 起即如此，本轮复核确认）。
`data_source`、`data_dataset` 结构未变，无新增迁移。

### 2.2 归一化输出（流水线 1.2.0 → **1.3.0**）

| 产物 | 变化 |
|---|---|
| `data_datasets.csv` | 删除 `license_id` / `license_url` / `redistributable` / `attribution_text` 四列（11 列 → **7 列**） |
| `source_records.csv` | 删除 `license_status` / `redistributable` 两列（14 列 → **12 列**）；保留 `attribution_text`（引用串，属溯源，不是准入条件） |
| `data_quality_issues.csv` | 2 行 `licence_unconfirmed`（blocking / needs_manual_review）→ `attribution_missing`（info / preserved_and_flagged），配对改写 `expected_rule` 与 `notes` |
| `historical_places.csv` | 2 行 WHG 地点的 `notes` 从 `blocking_for_publication_licence_unconfirmed` 改为 `attribution_missing` |
| `stats.json` | 删除 `datasets.license_ids`、`datasets.redistributable`、`sources.mcgd.license_id`、`provenance.chgis_license_statement` |
| 代码 | `DatasetInfo` 删除 3 个许可字段；`PLEIADES_LICENSE_ID`、`CHGIS_CITATION_EULA`、`license_statement_from_readme()`、`zenodo_license_id` 删除；WHG 抽取器的 `licence_unconfirmed` 标记改名 `attribution_missing` |
| — | **11 / 16 项产物 MD5 与 M4-1 完全一致**，变化的 5 项恰好是上表所列（见 §4） |

M4-1 的 16 项 MD5 基线原样保留在 `code/ops/m4/md5_baseline.txt`，未被覆盖；M4-2 的新基线在 `code/ops/m4-2/md5_baseline.txt`。

## 三、来源可选化修改清单

### 3.1 数据库结构：**不需要放宽**

| 对象 | 现状 | 结论 |
|---|---|---|
| `historical_place_name.source_record_id` | **可空**（V2 起） | 无需改 |
| `historical_place_location.source_record_id` | **可空**（V2 起） | 无需改 |
| `historical_place.created_from_source_record_id` | 可空 | 无需改 |
| `ck_historical_place_c05` | `created_by='manual' OR created_from_source_record_id IS NOT NULL` | **保留**：只约束 `created_by='import'` 的导入行（导入行必然来自某条 `source_record`），人工录入一律豁免 |
| 外键 | name/location → `source_record` 为普通外键，NULL 不触发校验 | 无需改 |

本轮唯一的数据库结构改动是 **V8**，与来源无关（见 §4.1）。

### 3.2 后端逻辑

| 位置 | 改动 |
|---|---|
| `PlaceQueryService` 名称检索 `name_hit` | `JOIN source_record` → **`LEFT JOIN`**，条件改为 `(sr.source_record_id IS NULL OR sr.is_active)` |
| `PlaceQueryService` 地图计数 | 同上（`count(distinct l.place_id)`） |
| `PlaceQueryService` 地图要素 `cand` | 同上 |
| `PlaceQueryService` 类注释 | 明确写清「来源不是准入条件；有来源才校验 is_active」 |
| `PlaceAdminService` 位置新增/更新 | **修真实缺陷**：`CASE WHEN :lon IS NULL` 未加类型转换，无坐标保存时 PostgreSQL 报 `could not determine data type of parameter $10` → HTTP 500。已全部改为 `:lon::double precision IS NULL` |

**没有任何服务端把来源做成必填**：`grep "来源"` 在 Java 里只命中注释；创建/修改地点、名称、位置都不校验 `source_record_id`。

### 3.3 前端

管理界面本来就没有「来源」输入框（M2 起如此），因此不存在必填标记、也不会因来源为空禁用保存。
地点详情面板对来源为空的情况显示「来源记录 0」而不是报错；本轮只把 API 字段 `sourceLicenseNote` 改名为 `sourceNote`，并同步 `types.ts` / `DetailPanel.vue`。

### 3.4 M3 遗留「手工地点不上图」——修复结果

根因是 M1 地图查询用 `INNER JOIN source_record`，人工录入的名称/位置 `source_record_id` 为 NULL，被直接过滤掉。

| 证据 | 修复前 | 修复后 |
|---|---|---|
| `bbox=112,34,113,35` 内可见地点（测试库，同一 SQL 只改 JOIN 方式） | **0** | **16** |
| 无来源地点在 `places` 数据源中 | 无 | 有（E2E E04 `hit=true`，`datasetId=manual_entry`） |
| 无来源别名能否搜到 | 不能 | 能（E2E/A06、A07） |
| 图层开关后是否恢复 | — | `none → visible` 且仍有要素（E06） |
| 点击标记开详情 | — | 打开的是它自己的详情，显示「来源 人工录入 / 来源记录 0」（E07） |

同时保留质量门禁：单侧坐标 400、越界 400、`crs_confidence='unknown'` 可保存但**不进地图**（B07）。

## 四、数据库结构变化

### 4.1 V8（仅测试库）

`V8__quality_issue_attribution_type.sql`：把 `attribution_missing` 补进 `ck_data_quality_issue_issue_type` 值域（19 → 20）。
原因：V2 早已把 `licence_unconfirmed` 从值域删除，取消剔除后这 2 行必须有一个合法类型。
不新增表/列/索引，不回填历史数据，不动 V1–V7。

| 库 | 版本 |
|---|---|
| `canvas_history_m2check` | V8 |
| `canvas_history_m4check`（干净验证库） | V8 |
| `canvas_history`（正式） | **V5**（未执行 V6/V7/V8） |

### 4.2 校验和

| 版本 | 说明 | 状态 |
|---|---|---|
| V1–V7 | 未改动一个字节 | Flyway validate 通过（8 migrations validated） |
| V8 | 新增 | 仅在两个测试库执行 |

## 五、导入前后数据数量对照

### 5.1 干净库 `canvas_history_m4check`（权威基线）

| 表 | 导入前 | 导入后 | Δ | 与暂存的关系 |
|---|---:|---:|---:|---|
| `source_record` | 0 | **29,391** | +29,391 | = 暂存 29,391 |
| `historical_place` | 0 | **19,039** | +19,039 | = 暂存 19,039 |
| `historical_place_name` | 0 | **47,499** | +47,499 | 暂存 47,503 − 4（隔离源记录） |
| `historical_place_location` | 0 | **18,101** | +18,101 | 暂存 18,103 − 2（隔离源记录） |
| `candidate_match` | 0 | **53,131** | +53,131 | 暂存 53,137 − 6（自指 2 + C09 收敛 4，逐条留痕） |
| `data_quality_issue` | 0 | **12,833** | +12,833 | 暂存 12,631（零丢弃）+ 5 + 197 + 0 |
| `import_batch` | 0 | 7 | +7 | 每数据集 1 批 |
| `data_dataset` | 1（V5 种子） | 8 | +7 | — |
| `data_source` | 1（V5 种子） | 5 | +4 | — |

台账构成（M4-2 新基线）：

```
暂存 data_quality_issues.csv        12,631   （许可类 2 行已改判，全部保留）
+ duplicate_external_id                  5
+ derived_value_mismatch               197   （落在 130 个地点）
+ manual_edit_conflict                   0
= 入库                               12,833   ← 旧口径为 12,831
类型数 15 种（暂存 13 种 + 合成 2 种）；license* 残留 0；attribution_missing 2 行
```

### 5.2 测试库 `canvas_history_m2check`（既有夹具 + 全量导入）

| 表 | 导入前 | 导入后 | 说明 |
|---|---:|---:|---|
| `source_record` | 7 | 29,398 | 7 条为 M3 演示数据（`m3_demo_ds`），独立批次 |
| `historical_place` | 39 | 19,078 | 39 条人工地点原样保留 |
| `historical_place_name` | 26 | 47,525 | 26 条人工名称原样保留 |
| `historical_place_location` | 25 | 18,126 | 25 条人工位置原样保留 |
| `candidate_match` | 0 | 53,131 | — |
| `data_quality_issue` | 0 | 12,833 | 与干净库相同 |
| `event` / `historical_polity` | 16 / 8 | 16 / 8 | M3 数据未受影响 |

### 5.3 正式库（只读对照，**未改动**）

```
Flyway V5；source_record 29,391 / historical_place 19,039 / name 47,499 /
location 18,101 / candidate 53,131 / data_quality_issue 12,831 / import_batch 7 /
data_dataset 8 / data_source 5
```

正式库仍是旧台账口径 12,831、仍是 V5——本轮**不向正式库写入**。新基线在正式库生效的时机由 Owner 在后续发布窗口决定。

## 六、两条历史过滤记录的处理结果

| 项 | 内容 |
|---|---|
| issue_id | `dq_0007820` / `dq_0007821` |
| source_record_id | `sr_0029159` / `sr_0029154`（WHG HGIS de las Indias 扁平记录，`169687` / `169687-169688`） |
| 原 issue_type | `licence_unconfirmed`，severity `blocking`，action `needs_manual_review` |
| 真实事实 | 扁平 schema 没有 `attribution` 块；`sources.json` 也没有 SPDX 字段 |
| 是否应进台账 | **应该**。它是「来源元数据缺失」的观察，不是数据缺陷，更不是准入条件 |
| 是否重复计数 | 否。两条分别指向不同 source_record，`issue_fingerprint` 唯一；与 `unknown_crs`（646 条，其中 WHG 3 条）不重叠——后者记的是 CRS，字段不同 |
| 现处理 | `attribution_missing`，severity `info`，action `preserved_and_flagged`；`observed_value` 原文保留，`notes` 只追加不作删改 |
| 落地证据 | 两个测试库里各 2 行，`field_name='attribution'`；许可证类类型计数为 **0**（`strpos(lower(issue_type),'licen') = 0`） |

## 七、人工修改保护测试结果

在干净库 `canvas_history_m4check` 上走**真实 Importer 代码路径**（`verify_rollback_and_protection.py`，事务内执行后 ROLLBACK）：

```
✓ P1  locked / manual_edited_fields / created_by=manual 三种保护位均未被机器覆盖；
      blocked_count=3、manual_edit_conflict=3（1:1 行级记账）
✓ P2  19,039 个地点 = 新增 0 + 更新 0 + 无变化 19,036 + 人工保护跳过 3；
      仅这 3 个被挡且各登记 1 条台账，其余 19,036 个地点重跑均判为无变化，无误挡
```

在测试库 `canvas_history_m2check` 上做「全量导入前后指纹比对」（人工地点/名称/位置的 id、名称、坐标、
`locked`、`manual_edited_fields`、`updated_at` 全量 MD5）：

```
导入前 c089111a87723cdb29fe955aba95fa21
导入后 c089111a87723cdb29fe955aba95fa21   ← 完全一致，0 行被覆盖
```

重复执行：连续两轮导入，六张数据表 Δ 全为 0（`import_batch` +7 属每轮新建批次，设计如此）。

## 八、完整导入测试结果

| 项 | 结果 |
|---|---|
| 干净库首轮导入 | EXIT 0，一次提交成功，断言全通过 |
| 干净库次轮导入 | EXIT 0，六表 Δ=0（幂等） |
| 测试库两轮导入 | EXIT 0，六表 Δ=0（在 39 条人工地点共存的情况下仍幂等） |
| 导入器自检 | `verify_import.py` 13 项：**PASS 11 / FAIL 0 / UNVERIFIED 1**（V9b「内容变更→UPDATE」路径两轮输入相同未触发，与阶段三结论一致，不冒充通过） |
| 回滚保护 | 9 项：**PASS 8 / FAIL 0**（1 项 INFO） |
| 台账 | 12,833 行 / 15 类型 / license* 0 / attribution_missing 2 |
| 候选留痕 | 53,137 = 入库 53,131 + 留痕 6；19 列逐字保留 |

V9b 诚实标注：本轮没有构造 `content_hash` 变化的第三轮输入，因此「内容变更走 UPDATE 而非 INSERT」的路径
**本轮未实测**，不做 PASS 判定。

## 九、M0～M3 相关回归

| 套件 | 结果 |
|---|---|
| M4-2 来源可选化 API（新） | **19 / 19** |
| M4-2 无来源地点上图 E2E（新） | **9 / 9** |
| M3 接口 | **51 / 51** |
| M3 写保护（正式库） | **4 / 4**（含 PATCH 403） |
| M3 浏览器 E2E | **56 / 56** |
| M3 政权关联界面 | **13 / 13** |
| M2-A 接口 | **43 / 43** |
| M2 完整业务 | **36 / 36** |
| M2 管理界面 E2E | **14 / 14** |
| M0/M1 浏览器 E2E | **15 / 15**（首跑 13/15：MapTiler 首屏样式瓦片未就绪导致 raster 层计数为 0；复跑 15/15，属环境预热，非代码回退） |
| M3 前置加固 | 写保护 11/11、可写 7/7、排序 4/4、选项 7/7 |
| 前端类型检查 `vue-tsc` | 0 错误 |

## 十、归一化流水线复现

| 项 | 值 |
|---|---|
| 入口 | `python code/p0/wb-002-normalize/run_all.py --project-root <tmp> --timestamp 2026-11-02T00:00:00Z` |
| 版本 | `wb-002-normalize/1.3.0` |
| 环境 | Python 3.13.14 / Windows-11-10.0.28000-SP0 |
| 耗时 | 3.75 s / 3.50 s（两次） |
| 输入 | 21 个原始文件，运行前后 SHA256 未变 |
| 16 项产物 | 两次运行之间 **16/16 MD5 一致**；与 M4-1 基线 **11 项相同**、5 项按预期变化 |
| 行数 | 19,039 / 47,503 / 18,103 / 29,391 / 53,137 / 12,631 / 7 —— 与 M4-1 完全相同 |

变化的 5 项：`data_datasets.csv`、`source_records.csv`、`data_quality_issues.csv`、`historical_places.csv`、`stats.json`
（全部由「删许可字段 / 改判 2 行」引起）。`historical_place_names`、`historical_place_locations`、
`candidate_matches` 与 8 份 issues 清单 **逐字节未变**——证明本次改动没有波及坐标、名称与候选匹配。

## 十一、Git

| 项 | 值 |
|---|---|
| 分支 | `m4-2-import-rules` |
| 起点 | `cbada4c0b85af4cbb9d93da24f875d8bfd16a17f`（M4-1 报告） |
| 实现提交 | 见文末（本报告与其同轮提交） |
| 远程 | 无，未推送 |
| 工作区 | 提交后干净 |

纳入版本管理：`V8` 迁移、`import_staging.py`、`verify_import.py`、`PlaceQueryService`、`PlaceAdminService`、
`Dtos`、`types.ts`、`DetailPanel.vue`、`p0/wb-002-normalize/*`、`ops/m4-2/*`（基线 + 日志 + 快照 + 新测试脚本）、
`tests/e2e-m4/m4-place-no-source.cjs`、`IMPORT_VALIDATION_RULES.md`、`ops/README.md`、`CORE_DATA_MODEL_V2.1.1.md`（标注）。
删除：`ops/verify_no_licence_gate.py`。

`design/P0验证`、`P0收敛`、`code/data/staging/*.csv` 仍按既有策略不入库（大体积数据快照）。

## 十二、正式库数据保护验证

```
版本：V5（V6/V7/V8 均未执行）
source_record 29,391  historical_place 19,039  historical_place_name 47,499
historical_place_location 18,101  candidate_match 53,131  data_quality_issue 12,831
import_batch 7  data_dataset 8  data_source 5
```

与 M3 封存时逐表比较：**全部相同**。正式库的写保护仍然生效（G01/G01b 403）。

## 十三、未解决问题

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 1 | 正式库仍是 V5 + 旧台账 12,831 | 5180 上矩阵为降级态、台账少 2 行 | 发布窗口内由 Owner 授权 `flyway migrate` 到 V8 并重跑导入 |
| 2 | 写接口仍无鉴权 | 本机工具可接受 | 对外部署前必须补（M2 起遗留） |
| 3 | `source_records.attribution_text` 保留 | 属引用串，不是准入条件 | 若 Owner 要求「零 attribution 字段」，可再删一列，需同步重跑导入 |
| 4 | `issue_type` 值域现为 20 值 | 与设计文档 19 值不一致 | 本轮已在 `CORE_DATA_MODEL_V2.1.1.md` 旁注说明；若后续新增类型应合并为一次值域修订 |
| 5 | V9b「内容变更走 UPDATE」未实测 | 无 | 需要专门构造 content_hash 变化的第三轮，属独立测试项目 |
| 6 | 测试库 `canvas_history_m2check` 已有全量数据 | M2/M3 用例的绝对计数含义变化 | 现有用例均按名称/关联断言，实测全部通过；后续新增用例不要写死总量 |

---

## 附：交付物清单

| 路径 | 内容 |
|---|---|
| `code/backend/src/main/resources/db/migration/V8__quality_issue_attribution_type.sql` | 值域扩展 |
| `code/ops/m4-2/md5_baseline.txt` | M4-2 16 项产物 MD5 基线 |
| `code/ops/m4-2/run_manifest.json` | 1.3.0 运行清单 |
| `code/ops/m4-2/run1_summary.json` / `run2_summary.json` | 干净库两轮导入快照 |
| `code/ops/m4-2/import_run1.json` / `import_run2.json` | 测试库两轮导入快照 |
| `code/ops/m4-2/verify_import.log` | 13 项核验输出 |
| `code/ops/m4-2/protection.log` | 人工保护与回滚实测输出 |
| `code/ops/m4-2/stage3_excluded_rows.csv` | 候选排除留痕（6 行） |
| `code/ops/m4-2/api_m4_2_test.py` | 来源可选化 API 测试（19 项） |
| `code/tests/e2e-m4/m4-place-no-source.cjs` | 无来源地点上图 E2E（9 项） |
| `code/ops/reports/m4-2/shots/` | `40_/41_` 无来源地点截图 + 回归截图 |

**M4-2 — COMPLETED / ACCEPTED**
