# M4-1 P0 数据资产恢复与流水线复现报告

- 执行时间：2026-11-04（Asia/Shanghai）
- 分支：`m3-time-map`（HEAD 起点 `c40dcbb`，M4-0 审计报告）
- 恢复提交：**`b856175`** `chore(m4): restore P0 assets and prove the normalisation pipeline still reproduces`
- 报告提交：紧随恢复提交的独立 `docs(m4)` 提交
- 结论：**ASSET RECOVERY：PASS；PIPELINE REPRODUCTION：PASS；DATA INTEGRITY：PASS**

> 本轮只做三件事：把回收站里的 P0 资产复制回来、逐文件核验、在隔离目录重跑归一化流水线。
> 未修改数据库、未执行 Migration、未下载新数据、未改动 P0 算法、未合并任何地点、未触碰 M3 历史提交。

---

## 一、开工前状态

### 1.1 Git

| 项 | 值 |
|---|---|
| 分支 | `m3-time-map` |
| HEAD | `c40dcbb` `docs(m4): read-only audit of data assets, four sources and pipeline state` |
| 工作区 | 干净（`git status --short` 为空） |
| 远程 | 无（未推送） |

### 1.2 现有资产（恢复前）

| 路径 | 文件数 | 说明 |
|---|---:|---|
| `code/data/staging/` | 7 CSV | 导入器输入，与 P0 归一化产物逐字节相同（基线副本） |
| `设计资料/P0收敛/WB-002/normalized/` | 9（7 CSV + `run_manifest.json` + `stats.json`） | 2026-11-03 12:26 回填的唯一 P0 产物 |

恢复前记录的 MD5 见 `code/ops/m4/md5_baseline.txt`（16 项产物），SHA256 见 M4-0 报告 §3.2。

### 1.3 回收站元数据（`$I` 解析）

| 条目 | 原始路径 | 删除时间 | 记录大小 |
|---|---|---|---:|
| `$I4BI1K6` → `$R4BI1K6` | `E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\设计资料\P0验证` | 2026-11-03 12:14:09 | 2,223,550 B |
| `$IXROG9G` → `$RXROG9G` | `…\设计资料\P0收敛` | 2026-11-03 12:14:09 | 107,765,301 B |
| `$ICJY9IU` → `$RCJY9IU` | `…\code\p0` | 2026-11-03 12:14:14 | 135,626,661 B |

> 三个 `$I` 记录的大小与恢复后逐文件字节总和完全一致（2,223,550 / 107,765,301 / 选定的 511,225），说明回收站内容未被截断或替换。

### 1.4 恢复目标与防覆盖策略

- `设计资料/P0验证`：目标不存在 → 全量复制。
- `设计资料/P0收敛`：目标已有 `WB-002/normalized`（9 文件）→ **逐文件先比哈希**；相同则跳过（`existing_same`），不同则记 `conflict_diff` 并停止该文件，绝不覆盖。
- `code/p0`：目标不存在 → 只复制 23 个核心脚本，保持 `wb-002-normalize/` 与 `wb-002-tools/` 两级结构。

---

## 二、资产恢复结果

### 2.1 总览

| 回收站条目 | 恢复目标 | 文件数 | 字节 | 状态 |
|---|---|---:|---:|---|
| `$R4BI1K6` | `设计资料/P0验证/` | 51 | 2,223,550 | 全部 `restored` |
| `$RXROG9G` | `设计资料/P0收敛/` | 182 | 107,765,301 | 173 `restored` + 9 `existing_same` |
| `$RCJY9IU` | `code/p0/`（仅 23 个核心脚本） | 23 | 511,225 | 全部 `restored` |
| **合计** | — | **256** | **110,500,076** | **0 冲突 / 0 缺失 / 0 失败** |

逐文件明细：`code/ops/m4/restore_manifest.csv`（256 行，字段：回收站条目 / 原始路径 / 恢复路径 / 文件名 / 字节 / SHA256 / 状态）。

### 2.2 与指令中数字的差异（如实说明，不做猜测）

| 指令表述 | 实际 | 差异原因 |
|---|---|---|
| `P0验证`：“43 个文件，约 1.90 MB” | 目录内实际 **51 个文件 / 2,223,550 B** | 43 是 `WB-002/` 子集（37 个原始样本 + 6 个报告/映射）；同目录还有 `WB-001/` 6 个地图验证材料与 2 份 P0 总报告。按“完整找回误删目录”原则一并恢复，未丢弃。 |
| `P0收敛`：“182 个文件，约 102.8 MB” | **182 个文件 / 107,765,301 B** | 与指令一致（102.8 MiB = 107.8 MB） |
| `code/p0`：“2,871 个文件，约 129.3 MB” | 只恢复 **23 个脚本 / 511,225 B** | 2,871 中含 `wb-001-maptiler-demo/node_modules` 与 `dist`；按指令“禁止为方便恢复全部”只取核心脚本 |

`P0收敛` 的 182 个文件构成：

| 子树 | 文件数 | 与流水线的关系 |
|---|---:|---|
| `WB-002/normalized` | 9 | 归一化产物（已存在 9/9，哈希相同） |
| `WB-002/issues` | 8 | 八份质量问题清单（本轮恢复） |
| `WB-002/sample_data_pleiades` | 6 | Pleiades 切片输入（流水线必需） |
| `WB-002/*.md` + `FIELD_MAPPING.csv` | 6 | P0 报告与字段映射 |
| `WB-001/` | 6 | 早期地图验证材料（同目录，非本轮流水线） |
| `架构/` + `架构.zip` | 145 | **历史设计文档快照**（与现行 `设计资料/V2.1.1_正式交付` 内容不同，属旧版本副本），仅按原路径恢复，不作为现行设计依据 |
| 根目录 2 份 P0 收尾报告 | 2 | `P0_CLOSEOUT_REPORT.md`、`QA_VERIFICATION_R2.md` |

> `架构/` 与现行交付包的差异已用 `diff -rq` 确认（`CORE_DATA_MODEL_V2.1.1.md`、`DATA_PROVENANCE_V2.1.1.md` 等均不同），**不参与本轮任何计算**，也不会被导入。

### 2.3 冲突检查

| 场景 | 数量 | 处理 |
|---|---:|---|
| 目标已存在且 SHA256 相同 | 9 | `existing_same`，跳过，不重写（mtime 未变） |
| 目标已存在但 SHA256 不同 | **0** | — |
| 恢复后哈希与源不一致 | **0** | — |
| 源文件缺失 | **0** | — |

### 2.4 独立复核（不依赖恢复脚本的第二次计算）

对恢复后的全部文件重新遍历，与回收站源逐文件比 SHA256：

```
$R4BI1K6 : src_files 51  missing 0  hash_mismatch 0
$RXROG9G : src_files 182 missing 0  hash_mismatch 0
23 个脚本 : problems 0
```

同时复核项目内 16 个基线产物（normalized 7 CSV + stats + issues 8 CSV）与恢复前基线 MD5：**16/16 一致，0 差异**——即恢复过程没有改动任何既有产物。

### 2.5 未恢复项（明确列出，不标记为成功）

| 项 | 数量 | 原因 |
|---|---:|---|
| `code/p0/wb-001-maptiler-demo/`（源码、dist、node_modules） | 2,848 | 属 WB-001 地图 Demo，不在 23 个核心脚本内；按指令不整目录恢复 |
| `code/p0/wb-002-normalize` 下未列入 16 个清单的任何文件 | 0 | 该目录恰好只有这 16 个文件 |
| 回收站本身 | 3 个条目 | **未清空、未移动**，保留为二次备份 |

---

## 三、核心脚本恢复结果

### 3.1 清单（23 个，全部 `restored`）

| 文件 | 字节 | SHA256（前 16 位） |
|---|---:|---|
| `code/p0/wb-002-normalize/run_all.py` | 26,321 | `e3c41ba27252035e…` |
| `code/p0/wb-002-normalize/normalize.py` | 102,275 | `4a0a6fed7f656de5…` |
| `code/p0/wb-002-normalize/chgis_extract.py` | 16,253 | `7fb59934d7b04cc5…` |
| `code/p0/wb-002-normalize/chgis_migration.py` | 32,810 | `c920743a68ec573f…` |
| `code/p0/wb-002-normalize/mcgd_extract.py` | 6,781 | `a9513cbfe8f60149…` |
| `code/p0/wb-002-normalize/pleiades_extract.py` | 23,361 | `e17e39a6df988c28…` |
| `code/p0/wb-002-normalize/whg_extract.py` | 24,412 | `a4bee12d6a4b6887…` |
| `code/p0/wb-002-normalize/quality_checks.py` | 32,927 | `d963ef59a5704280…` |
| `code/p0/wb-002-normalize/report_stats.py` | 30,736 | `0fd2af12a5159675…` |
| `code/p0/wb-002-normalize/time_semantics.py` | 11,414 | `595ca00210e40bc7…` |
| `code/p0/wb-002-normalize/datasets.py` | 13,847 | `4c0166bcb46be36b…` |
| `code/p0/wb-002-normalize/dbf_reader.py` | 10,172 | `1bf91945298fccd7…` |
| `code/p0/wb-002-normalize/xlsx_reader.py` | 6,145 | `41a66ea1f7476e26…` |
| `code/p0/wb-002-normalize/csv_io.py` | 2,655 | `02fed31d051dba46…` |
| `code/p0/wb-002-normalize/extra_record.py` | 8,307 | `8df59dfd4c9cb9df…` |
| `code/p0/wb-002-normalize/README.md` | 54,425 | `b1e794a159280e68…` |
| `code/p0/wb-002-tools/fetch_samples.sh` | 9,080 | `f5f596549fce8df5…` |
| `code/p0/wb-002-tools/r2_fetch_pleiades_gis.sh` | 2,580 | `44ed97067e4a190a…` |
| `code/p0/wb-002-tools/verify_wb002.py` | 10,691 | `07be002b79c308d0…` |
| `code/p0/wb-002-tools/r2_verify_pleiades_fields.py` | 14,383 | `0e5b6ccb2860eba8…` |
| `code/p0/wb-002-tools/r2_verify_whg_mcgd_chgis.py` | 16,089 | `c2a268c8fc6d1fef…` |
| `code/p0/wb-002-tools/r2_build_field_mapping.py` | 52,420 | `f6c78c0c79f4bbc4…` |
| `code/p0/wb-002-tools/derive_mcgd_sample.py` | 3,141 | `16e3fd6322fefb84…` |

完整 64 位哈希见 `code/ops/m4/restore_manifest.csv`。

### 3.2 依赖判定

- 16 个 `wb-002-normalize` 文件是**全部必需**：`run_all.py` 直接 `import` 其余 15 个（抽取器 4、读取器 2、语义 2、归一 3、质量 2、统计 1、校验 1，含 `README.md` 作为使用说明）。
- 7 个 `wb-002-tools` 文件是本轮指令要求保留的抓取/核验能力，流水线运行本身不 `import` 它们。
- 额外依赖：**无**。全部 import 为标准库（`argparse/csv/dataclasses/datetime/hashlib/json/math/platform/struct/sys/time/traceback/xml.etree/zipfile`），无 `pyproj`、无 `pandas`、无网络调用；无需配置文件、无需环境变量。
- 目录结构保持原样：`code/p0/wb-002-normalize/`、`code/p0/wb-002-tools/`。

---

## 四、流水线复现结果

### 4.1 执行入口与环境

| 项 | 值 |
|---|---|
| 入口 | `python code/p0/wb-002-normalize/run_all.py`（P0 原规范入口） |
| 固定时间戳 | `--timestamp 2026-11-02T00:00:00Z`（与基线 `run_manifest.ingested_at` 相同） |
| 运行隔离 | `--project-root C:/Users/the_z/AppData/Local/Temp/m4-repro-20261104/root`；输入为恢复资产的**副本**，输出写到该临时根，**未写入项目内 `P0收敛`** |
| Python | 3.13.14（与基线 `run_manifest.python_version` 相同） |
| 平台 | Windows-11-10.0.28000-SP0（与基线相同） |
| 流水线版本 | `wb-002-normalize/1.2.0`（与基线相同） |
| 耗时 | run1 3.643 s / run2 3.576 s（基线 3.803 s） |
| 原始输入 | 21 个文件参与哈希校验，运行前后 `input_integrity.verified = true`、`changed_files = []` |

运行日志：`code/ops/m4/pipeline_run1.txt`；两次运行的清单：`run1_run_manifest.json`、`run2_run_manifest.json`。

### 4.2 运行输出摘要（run1）

```
hash inputs (before)  [21 files] → 未变化
CHGIS  cnty=10,522  pref=5,226
MCGD   960 rows
Pleiades rows=12,665 places=2,643 discarded_tails=4
WHG    rows=238 places=7 (flat 2 / jsonld 5)
astro  5 assertions passed
beg>end 28 (pref 9 / cnty 19)
clusters 6,013 max_size 34
homonyms 2,071 / 8,303
cross-layer 29
migration 1,254 chains / 1,866 legs
ground truth: 新兴郡 PASS / 中山国 PASS
build 7 tables → places 19,039 / locations 18,103 / names 47,503 / sources 29,391
                   issues 12,631 / candidates 53,137 / datasets 7
hash inputs (after) [unchanged]
```

### 4.3 16 项产物 MD5 对比

| 产物 | 基线 MD5 | 复现 run1 | 复现 run2 | 结果 |
|---|---|---|---|---|
| `normalized/historical_places.csv` | `0281f5b9d475b1045cbd922c6dd66095` | 同 | 同 | PASS |
| `normalized/historical_place_names.csv` | `8a19a7828a541d3a7c674ddda190bf90` | 同 | 同 | PASS |
| `normalized/historical_place_locations.csv` | `0a7ce725cd6e0444e83a51cc5ad84575` | 同 | 同 | PASS |
| `normalized/source_records.csv` | `97c014b3b9570980d60098927c4efaeb` | 同 | 同 | PASS |
| `normalized/candidate_matches.csv` | `c1d9bfa5364137795606bdb7d9bd5ef8` | 同 | 同 | PASS |
| `normalized/data_quality_issues.csv` | `52e561d786505a092305cc20a6489506` | 同 | 同 | PASS |
| `normalized/data_datasets.csv` | `443a9cdf01d95558cc5db191da1868ed` | 同 | 同 | PASS |
| `normalized/stats.json` | `41d814e3afbe0954f3cd276274d7a94f` | 同 | 同 | PASS |
| `issues/chgis_all_records.csv` | `4f02caad6daee3b7548486659f756a24` | 同 | 同 | PASS |
| `issues/cluster_members.csv` | `cfa39d94f56499c0b94aa0a9f207f9c2` | 同 | 同 | PASS |
| `issues/coordinate_clusters.csv` | `a5ca0d8d05ecbc2281c9b2d76d9f6ebe` | 同 | 同 | PASS |
| `issues/cross_layer_disagreements.csv` | `24028e1747a822ca25bea1fbaecd34c7` | 同 | 同 | PASS |
| `issues/homonyms.csv` | `c2b0b72337d1956c3cc306f2e8e0b70a` | 同 | 同 | PASS |
| `issues/migration_chains.csv` | `6ab4fefc9e563b7cccbf7e2aca33e97d` | 同 | 同 | PASS |
| `issues/migration_review_queue.csv` | `e2a1fb3de35a62918dde90ee45e2a316` | 同 | 同 | PASS |
| `issues/time_inversions.csv` | `5915dd3285c303d215f37881498b8320` | 同 | 同 | PASS |

- **16 / 16 与基线一致**（结果列全 PASS，机器可读版：`code/ops/m4/md5_compare.csv`）。
- 两次独立运行之间 **16 / 16 也一致** → 连续重复执行稳定。
- `run_manifest.json` 不作 MD5 比对：它记录运行起止时刻与耗时，两次运行分别为 3.643 s / 3.576 s，属预期差异（P0 报告已说明它是 provenance 而非测量值）。

### 4.4 数据数量对比

| 表 | 基线 | 复现 run1 | 差异 |
|---|---:|---:|---:|
| `historical_places` | 19,039 | 19,039 | 0 |
| `historical_place_names` | 47,503 | 47,503 | 0 |
| `historical_place_locations` | 18,103 | 18,103 | 0 |
| `source_records` | 29,391 | 29,391 | 0 |
| `candidate_matches` | 53,137 | 53,137 | 0 |
| `data_quality_issues` | 12,631 | 12,631 | 0 |
| `data_datasets` | 7 | 7 | 0 |
| 八份问题清单 | 15,748 / 15,738 / 6,013 / 29 / 2,071 / 1,254 / 1,866 / 28 | 完全相同 | 0 |

### 4.5 关键质量检查

| 检查 | 结果 |
|---|---|
| 天文纪年断言 | 5/5 通过：`-221→-220`、`1→1`、`1911→1911`、`None→None`、`0` 抛错 |
| 天文纪年抽样 | `historical_place_names` 中「雁门郡」`valid_from = -220`、`valid_to = 13`、`exact`（CHGIS 原始 `BEG_YR=-221`） |
| 时间值域 | 名称 6 值：`exact` 21,614 / `unknown` 20,535 / `exact_or_bounded` 2,360 / `tpq_taq` 1,774 / `bounded` 1,166 / `snapshot` 54；位置 6 值：8,057 / 7,656 / 812 / 1,159 / 398 / 21；地点级另有 `derived_tpq_taq` 1,816（由子记录派生） |
| 时间倒挂 | 28 条（府 9 / 县 19），原值保留、派生年份留空、`unknown` |
| 迁治 ground truth | 新兴郡 PASS（3 个治所、1 条同名腿、异地治所排除）；中山国 PASS（跨层 0 边、链 1/1） |
| 候选匹配 | 53,137 行；`candidate` 51,269 / `needs_manual_review` 1,868；关系 `same_coord_diff_entity` 34,012 / `homonym_diff_place` 14,536 / `same_entity_same_seat` 2,331 / `location_migration_candidate` 1,866 / `pleiades_connection` 390 / `true_duplicate_suspected` 2；**无任何合并动作** |
| 人工修改保护 | 归一化产物保留 `locked` 列（19,039 行，当前全 `false`）；保护逻辑属**导入层**（`ops/import_staging.py:643-660`：`created_by=manual` / `locked` / `manual_edited_fields` → 记录级 blocked + 台账），历史实测见 `ops/reports/r1_2/08_verify_protection_rollback.log`（19,039 = 0 + 0 + 19,036 + 3，三条夹具未被覆盖）。**本轮未写数据库，故未重跑该写库测试** |
| 输入只读 | 21 个输入文件运行前后 SHA256 一致（`input_integrity.verified=true`，`changed_files=[]`） |

### 4.6 失败与差异

| 项 | 说明 |
|---|---|
| 运行失败 | **无**。两次运行均 EXIT 0，无异常栈 |
| 产物差异 | **无**（16/16 一致） |
| 预期差异 | `run_manifest.json` 的 `run_started_utc` / `run_finished_utc` / `duration_seconds`；`stats.json` 与产物本身不含墙钟，故 MD5 稳定 |
| 未执行项 | 导入层的人工保护/幂等测试需要写数据库，按 M4-1 边界未执行；其能力已在阶段三 R1.2 验收（`ops/reports/r1_2/`） |

---

## 五、Git 结果

| 项 | 值 |
|---|---|
| 分支 | `m3-time-map` |
| 恢复提交 | **`b856175`** `chore(m4): restore P0 assets and prove the normalisation pipeline still reproduces` |
| 报告提交 | 本文件的独立 `docs(m4)` 提交 |
| 远程 | 无，未推送 |
| 工作区 | 提交后干净 |

纳入版本管理（32 个文件）：

- `code/p0/wb-002-normalize/`：16 个（全部脚本 + README）
- `code/p0/wb-002-tools/`：7 个
- `code/ops/m4/`：8 个证据文件（`restore_manifest.csv`、`pipeline_run1.txt`、`md5_baseline.txt`、`md5_run1.txt`、`md5_compare.csv`、`key_metrics.json`、`run1_run_manifest.json`、`run2_run_manifest.json`）
- `.gitignore`：新增 `设计资料/P0验证/`（原始样本按既有“第三方数据快照不入库”策略处理）

**未纳入版本管理（按策略）**：

| 路径 | 理由 |
|---|---|
| `设计资料/P0验证/`（51 文件，2.2 MB） | 第三方原始样本，已有 `.gitignore` 对 `P0收敛` 的同类策略；文件级 SHA256 清单已入库 |
| `设计资料/P0收敛/`（182 文件，102.8 MB） | 大体积归一化产物，原有策略即忽略 |
| `code/data/staging/`（7 CSV，72 MB） | 导入输入副本，原有策略即忽略 |

> 因此“工作区干净”是在上述策略下的干净；`git status` 无未跟踪的恢复残留。

---

## 六、最终结论

| 判定项 | 结果 | 依据 |
|---|---|---|
| **ASSET RECOVERY** | **PASS** | 256 个文件全部按原路径恢复；独立复核 51+182+23 文件 SHA256 与回收站源 0 差异；0 冲突、0 缺失；回收站未清空 |
| **PIPELINE REPRODUCTION** | **PASS** | 原入口原样运行两次；16 项产物与基线 16/16 MD5 一致，两次之间也 16/16 一致；输入前后哈希未变；无报错 |
| **DATA INTEGRITY** | **PASS** | 行数 7 张表 + 8 份清单全部与基线相同；天文纪年 5 断言 + 抽样通过；时间值域完整；候选表零合并；项目内既有 16 个产物在恢复过程中未被改写 |

### 遗留与提醒（不阻断本轮结论）

1. `P0验证` 实际 51 文件（指令写 43），差额为同目录的 `WB-001/` 与 2 份 P0 总报告；已完整恢复并单独说明，未混入“43 个原始样本”的口径。
2. `P0收敛/架构/` 是**旧版设计文档快照**（与现行 `设计资料/V2.1.1_正式交付` 有差异），恢复后仅存档，不参与计算；后续若引用设计口径，仍以 `V2.1.1_正式交付` 为准。
3. 人工修改保护属导入层，M4-1 不写库，未重跑；其能力证据在 `ops/reports/r1_2/`，建议 M4-2 重跑导入时一并复验。
4. 回收站三个条目仍在原位（未清空）。确认本轮验收后，是否清理由 Owner 决定——**在确认前请勿清空回收站**。
5. 本轮未恢复 `code/p0/wb-001-maptiler-demo`（2,848 个文件），它属 M0 地图 Demo，不影响 P0 数据流水线。
