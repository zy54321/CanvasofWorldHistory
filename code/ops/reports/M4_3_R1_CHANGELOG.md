# M4-3 R1 · 变更记录与只读复核

日期：2026-11-04
分支：`m4-3-pleiades-gis`
性质：**文档与核算修订**。未改业务代码、未改数据库、未执行 Migration、未导入、未改原始数据与 staging。

---

## 一、本轮变更清单

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `code/ops/reports/M4_3_IMPORT_COUNT_RECONCILIATION.md` | 数量重算报告（10 节，含与 R0 的差异表） |
| 新增 | `code/ops/reports/M4_3_FILE_BEARING_MATRIX.md` | 19 个文件的承载矩阵（6 入库 / 2 派生 / 3 仅源记录 / 8 归档） |
| 新增 | `code/ops/reports/M4_3_V9_REVISION.md` | V9 设计稿（只设计，不执行） |
| 新增 | `code/ops/reports/M4_3_R1_CHANGELOG.md` | 本文件 |
| 新增 | `code/ops/m4-3/import_counts.py` | 只读核算脚本（可重跑） |
| 新增 | `code/ops/m4-3/import_counts.json` | 核算结果（本报告全部数字的机器可读版本） |
| 重写 | `code/ops/reports/M4_3_IMPORT_PLAN.md` | 修订 R1：两套行数口径、两级精度、代表点方案、验收指标分层 |

**未改动**：`M4_3_PLEIADES_GIS_ACQUISITION_REPORT.md`（R0 的数据事实仍然成立；本次只在其下游修订方案）、
`code/p0/**`、`code/ops/import_staging.py`、`code/ops/verify_import.py`、`code/data/staging/**`、
`code/data/raw/**`、数据库任何对象。

---

## 二、数字更正（R0 → R1）

| 项 | R0 | R1 实测 | 原因 |
|---|---:|---:|---|
| 重叠地点 | 0（脚本 bug） | **2,552** | 用 `new ∩ slice` 求交集恒为 0，应为 `all ∩ slice` |
| source_record 增量 | 121,931 | **124,512** | 补 2,552 条 inactive 记录；连接按全量 13,603 |
| source_record 总量 | 151,322 | **153,903** | 同上 |
| candidate_match 增量 | 13,572 / 13,574 | **13,553** | 按 `uq_candidate_match_c09` 有序对去重 |
| 新增地点精度 | 29,396 / 12,084 | **27,418 / 11,510** | 未按 NEW 集合过滤 |
| 位置级精度 | 未分 | **precise 28,634 / rough 3,740**（A1） | 新算 |
| `-1` 哨兵 | 12,007（整包） | **11,438（NEW）/ 728（实际入账）** | 口径细化 |
| 代表点无 location | 未识别 | **3,317（NEW）** | 本轮新发现 |
| 无几何口径 | 7,509 与 10,974 混用 | **7,200（口径③）** | 定义分层 |

另修正两处口径混淆：

1. **自环/悬空**：R0 写"孤儿 29、自环 2"。实测是 **29 个悬空端点分属 28 条记录**（1 条两端都悬空），
   **自环 1 条**且它本身就落在悬空集合里。全部记录都保留源记录。
2. **`accuracy_radius` 与 `-1` 哨兵不是一回事**：位置表的 `accuracy_radius` 只有"有值/空"（空 3,674 条），
   没有任何 0 或负值；`-1` 出现在 `places_accuracy.max/min_accuracy_meters`。R0 把两者混写了。

---

## 三、只读复核结果

### 3.1 原始数据指纹（未变）

| 项 | 值 |
|---|---|
| `pleiades.datasets-v4.1.zip` 字节 | 286,621,469 |
| MD5 | `ad339c92c6b895f0eb9a52228da498c4` |
| SHA256 | `94c5c337d27a07f1a5fa231b6513e40e6d3cf7d5ad7b8c010f8e8bfd9159cd85` |
| GIS 目录文件数 | 19 |
| GIS 目录总字节 | 128,705,151 |
| `places.csv` SHA256 | `5dd09b1a92c53e50cb9962bab44df12c5f0b7b683d4f228367d843637cfe5a59` |
| `connections.csv` SHA256 | `51e3f71c813b1132d9ef35f7dc2a0b9dea9cb9d5d95068e0b5f50e7e8925f1c3` |
| `places_accuracy.csv` SHA256 | `740849bd213d78993ad754fb316962f6a7cfd9a44cc4cbe7af925c12457709e9` |

与 R0 审计（`audit.json`）逐项一致。

### 3.2 staging 指纹（未变）

```
candidate_matches.csv              4e29c2ec64ebe263c325bab5f0eb70dc922116dd737542cf234373d86c98ab12
data_datasets.csv                  4b530673373005ccb1feaad5edc1c689d457139497a398399373c658bc624ed4
data_quality_issues.csv            7b9020ee41a1ad141dc7dd29529bd7e1202e98409aa3ef55371e5691b5a4a9c5
historical_place_locations.csv     9e987ba578e933ed9bdb11564487125783b22623abf348b9201a74d562d637a2
historical_place_names.csv         80674c0ded553241c6f4745db0d6957d4dd6617acdfa7918d503128c1690ebbd
historical_places.csv              bfddd91c6fb2a502f063e64aa6b4b2c045d454b057bc56bd2a0d23ad7035fb94
source_records.csv                 83bd11626964a21de4becf3a7cfc6ae99f022b48aafd40e1e70462c765d1c93e
```

与 M4-3 开工时记录**逐字节相同**。

### 3.3 数据库（均未变）

| 库 | Flyway | source_record | place | name | location | candidate | issue |
|---|---:|---:|---:|---:|---:|---:|---:|
| `canvas_history`（正式） | **5** | 29,391 | 19,039 | 47,499 | 18,101 | 53,131 | 12,831 |
| `canvas_history_m2check`（测试） | 8 | 29,398 | 19,091 | 47,534 | 18,136 | 53,131 | 12,833 |

**本轮无写入的硬证据**（最近写入时间都早于本轮开始 16:45）：

```
canvas_history        place/name/loc/issue = 2026-11-03 16:44  | batch 2026-11-03 16:44
canvas_history_m2check place 15:04:57 / name 15:05:00 / loc 15:05:03 / issue 11:47  （均为 M4-2 收尾轮）
```

本轮执行的 SQL 全是 `SELECT` / `\d` / `pg_get_constraintdef`；未建库、未删库、未加约束。

### 3.4 Git

| 项 | 值 |
|---|---|
| 分支 | `m4-3-pleiades-gis` |
| HEAD（开工） | `97e04d3024653acb323f0ac0db437fe14d9b030e` |
| 本轮改动 | 1 个文件修改 + 5 个文件新增（见 §一），全部在 `code/ops/` 下 |
| 未跟踪 | `汇报/`（交付目录，按约定保留、不入库） |
| 业务代码 | 0 改动（`git diff --stat` 仅 `M4_3_IMPORT_PLAN.md`） |

---

## 四、待决事项（3 项，需 Owner 决定后才能冻结最终行数）

| # | 事项 | 推荐 | 若不采纳的影响 |
|---|---|---|---|
| 1 | 3,317 个"有代表点但无 location 行"的地点是否合成位置行（A2） | **采纳 A2** | 选 A1 则这 3,317 个地点入库后在图上不可见 |
| 2 | `attested_form`（10,297 条原文）是否补成名称行 | **不补** | 补则名称 +10,297、source_record +10,297 |
| 3 | `place_without_geometry`（7,200）是否写台账 | **不写**，只作验收查询 | 写则与 `missing_coordinate` 重复计数，台账 +7,200 |

---

## 五、本轮明确没做的事

1. 没有写 V9 SQL 文件到 `db/migration/`（只在报告里给设计稿）。
2. 没有在任何库执行 Migration（正式库仍 V5、测试库仍 V8）。
3. 没有导入任何数据，没有建新库。
4. 没有修改 `code/p0/**` 与 `code/ops/import_staging.py`。
5. 没有覆盖 `code/data/staging`，没有改动原始 zip 与提取件。
6. 没有做任何跨源合并。

---

## 六、下一步（等 Owner 决策后）

1. 按 §四 的决策确定 A1/A2，更新 `M4_3_IMPORT_PLAN.md` §5、§7、§13 的数字；
2. 进入 M4-4a：写 V9 + 三处脚本改造 + 归一化到 `staging_m4_3/`；
3. 归一化跑完后，用 `data_quality_issues.csv` 的实际行数**冻结台账指标**（当前只给下界）。
