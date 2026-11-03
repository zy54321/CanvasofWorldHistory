# V2.1.1 正式交付物 · 冻结快照表

> **本表是八份交付物的唯一身份基准。**
> 哈希口径：`sha256(文件原始字节)`（`sha256(open(path,'rb').read())`）前 16 位十六进制。
> 行数口径：**LF 计数**（`bytes.count(b'\n')`），文件末尾有换行符。
> **以 `sha256[:16]` 为唯一身份，行数与字节数仅作参考**——同一字节流在不同计数口径下会差 1，不得据此判"文件被改过"。

冻结时刻：**2026-11-03 11:29:52**（GMT+8，**第三次冻结——最终版**）
冻结范围：`设计资料/P0收敛/架构/V2.1.1/正式交付/` 根目录

> **冻结判定方式**：`IMPORT_RULES_V2.1.1.md` 于 11:29:33 / 11:29:39 / 11:29:46 / 11:29:52 **连读四次**，字节数 53,361、LF 773、`sha256[:16]=4d36a9e884c6273f`、mtime 11:26:43 **四次完全一致**；架构师侧亦独立连读三次一致 ⇒ 确认停笔。
> **前两次冻结作废原因**（留痕）：首次 11:15 宣布时该文件仍在写（51,887→52,575→52,887→52,925，四版）；二次 11:22 冻结后又被改至 53,361（架构师补完 B-3 全部三项）。QA 两次按纪律拒绝判定，均正确。
> **教训**：宣布冻结前必须"连读多次哈希一致"，不能只测一次。

---

## 八份交付物

| # | 文件 | 字节 | LF 行 | mtime | `sha256[:16]` |
|---|---|---:|---:|---|---|
| 1 | `CORE_DATA_MODEL_V2.1.1.md` | 149,607 | 1,720 | 11-03 11:04:59 | `34ff192009a5d2dd` |
| 2 | `ER_DIAGRAM_V2.1.1.svg` | 60,681 | 458 | 11-03 11:01:27 | `0fafbee24fbf720b` |
| 3 | `IMPORT_RULES_V2.1.1.md` | **53,361** | **773** | 11-03 **11:26:43** | **`4d36a9e884c6273f`** |
| 4 | `FIELD_MAPPING_V2.1.1.csv` | 44,248 | 222 | 11-03 11:05:15 | `d06e7d47dc37b6e5` |
| 5 | `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md` | 74,963 | 1,060 | 11-03 11:14:47 | `15089fb35715b4b9` |
| 6 | `DATA_PROVENANCE_V2.1.1.md` | 41,084 | 561 | 11-03 11:02:45 | `05164fc50c8e1385` |
| 7 | `V2.1_TO_V2.1.1_CHANGELOG.md` | 150,397 | 1,294 | 11-03 11:06:59 | `5c80f224876983de` |
| 8 | `V2.1.1_QA_REPORT.md` | — | — | — | **待 QA 终检后产出**（第 8 份由 QA 出具） |

---

## 编制辅助件（`_build/`，**不参与交付物计数**）

| 文件 | 用途 |
|---|---|
| `_build/ACCEPTANCE_CRITERIA_V2.1.1.md` | 验收判据 60 条（含 V1 修订） |
| `_build/SHARED_BASELINE_V2.1.1.md` | 共享定义（内部参考，不得凌驾 V0.2.2-r2） |
| `_build/STAGING_FIELD_BASELINE.md` | 七张暂存 CSV 实测字段基线（105 字段） |
| `_build/staging_field_inventory.csv` | 同上，机器可读 |
| `_build/QA_CROSSCHECK_BATCH1.md` / `BATCH2.md` / `QA_FINAL_CHECK.md` | QA 三轮检查报告 |
| `_build/CHANGELOG_CORE_DIFF.md` | CHANGELOG ↔ CORE 逐字一致性复核 |
| `_build/qa_scripts/`、`_build/*.py` | 全部只读脚本，可重跑 |

---

## 三轮 QA 与修复轨迹（供验收参考）

### 第 1 轮（CORE + SHARED_BASELINE）：PASS 27 / FAIL 5 / 未验证 22
5 条 FAIL 全部关闭（F-02 `occurrence_key`、F-03 `ev` CTE 缺 JOIN、F-04 对外列 9→7、F-05 裸 `count(*)`、F-06 C13 列名、F-07 `blocked_count`、F-08 引用错、F-09 口径词、F-10 旧隔离规则、F-11 `is_canonical_row`、F-12 `dataset_id` 可空）。

### 第 2 轮（其余 5 份）：PASS 30 / FAIL 3
3 条 FAIL 全部关闭（F-01/F-02/F-03 `source_time_columns` 三文件同步、F-04 留痕）；并查出 **W-02**：`data_source` 仍有 2 列许可列（V2.1 §5.1「无变化」继承了 V2 的 `default_license_id`/`default_redistributable`）—— 已删除，这是本轮最易漏的一处。

### 第 3 轮（终检，60 条判据）：PASS 54 / FAIL 5 / PARTIAL 1
4 个阻断项全部关闭：
- **B-1** `DATA_PROVENANCE` 视图 SQL 不可编译（占位符 + 缺 JOIN）→ 现 `grep '<canonical'`=0、`grep 'JOIN source_record'`=6
- **B-2** ER 图四处陈旧（9 列/许可默认值/无变化/裸时间戳）→ 四项 grep 全 0
- **B-3** `is_canonical_row` 定序四套并存 → IMPORT 补全 6 键
- **B-4** 6 行空 `source_record_id` 台账 → 核实为 2 条 CHGIS 层字段名 + 4 条 Pleiades 切片尾，经 `source_dataset → dataset_id` 映射派生，C11 不违反

---

## 关键定式速查（八份必须一致）

| 项 | 定式 |
|---|---|
| 业务键 | `UNIQUE(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` 五段 |
| `parent_external_id` | 必需段，无父级写哨兵 `'-'`（不得 NULL/空串） |
| `record_scope` | 4 值 `place`/`name`/`location`/`edge` |
| `evidence_role` | 3 值 `creator`/`name`/`location` |
| `liveness` | 8 值；`rejected ⟺ liveness ∈ FAILURE_SET` |
| `record_status` | 地点表 3 值（staging/rejected/merged）与子表 3 值（staging/published/rejected）**值域不同** |
| `content_hash` | `sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))`（`len=85`，`sha1=9b0414f5…`） |
| `issue_fingerprint` | `md5(jsonb_build_array(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value))`，**算法恒 md5，不改 sha256**（ALG-1） |
| 隔离判据 | 同一 hash 子组内最小 ordinal 保留、后续相同 hash 隔离、不同 hash 均保留（**不得只比 ordinal=1**） |
| 四排列隔离数 | `A,B,B`→1 / `B,A,B`→1 / `A,B,C`→0 / `A,A,B,B`→**2** |
| `v_place_evidence` | 11 列；`is_canonical_row` 由**外层窗口定序**（6 键）计算 |
| `v_place_liveness` | 8 值 `liveness`；对外 **7 列**；`ev` CTE 须 `JOIN source_record` |
| `v_place_time_span` | 10 列；过滤 `record_status <> 'rejected'` + `sr.is_active`（**不是 `'published'`**）；`count(e.place_id)`（**不是裸 `count(*)`**） |
| 约束 | C01–C29，有效 **27** = 可落库 SQL **24** + 断言级/键级 **3** |
| 许可列 | `data_dataset` 删 9 列 + `data_source` 删 2 列，**两张表分别列明、无合计数** |

---

## 未验证事项（**不得预置通过结论**）

- **13 项** V0.2.2 未验证：U3/U4（视图首导）、U5（七类操作拦截）、U12（加 `sr.is_active` 后 17,469 变化）、U13、U14、U15、U16、U18（`candidate_match` 53,103 待 Owner 拍板）、`is_canonical_row` 与暂存 `canonical_name` 是否逐行相等
- **12 项 WARN** 全部保留未关闭
- **V-1…V-10** 待建视图后复算
- **B-1 残留**：CORE 附录 A 的 C19 仍写 `IN (3 值)` 占位（CHANGELOG 侧已用展开式），下轮解冻 CORE 时改

## 两条施工级硬提醒

1. **`normalize.py:306` 一旦被改**，`content_hash` 必须回归——逐字节形式会失效、规范化形式不会。不回归 ⇒ 29,391 条 hash 全变 ⇒ STOP_AUTO 误触发整批 SKIP_UPDATE。
2. **`derivation_kind`/`no_evidence` 不得直读暂存 `historical_places.valid_from/to_year_astro`**（旧口径含 connection ⇒ 偏低 65）。

## 工程边界（收尾须复核）

`架构/V2/`、`架构/V2.1/`、`架构/V2.1.1/V0.2.2/`、`架构/V2.1.1/00_PROBLEM_LIST_AND_PLAN.md`、七张暂存 CSV、`normalize.py` **全部未改动**。
未执行任何 DDL / Migration / 建库 / 数据导入 / 产品代码修改 / Git 操作。
