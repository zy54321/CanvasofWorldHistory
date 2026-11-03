# 阶段三导入程序必须自行校验的规则（数据库不强制）

本文件只记录一件事：**V2.1.1 在「说明」列写作“必填”、但「约束」列为空**的字段。
按权威模型，这类字段属**导入级校验**，不落数据库 `NOT NULL`——数据库结构以 V2.1.1 约束列为准，
阶段二已据此实施，**不得事后追加 NOT NULL**。

阶段三的导入程序必须自行校验下表；校验失败时的处置（拒绝该行 / 落台账 / 保留并标记）
以 `IMPORT_RULES_V2.1.1.md` 对应条目为准，本文件不重新定义处置策略。

| # | 表 | 列 | 设计原文出处 | 要求 | 实测暂存 | 实装位置（R1 起**强制**） |
|---|---|---|---|---|---|---|
| I-01 | `historical_place_name` | `notes` | `CORE_DATA_MODEL_V2.1.1` §5.7 行 764「**本表必填**。实测**暂存** 47,503 行全部非空」 | 导入时必须非空 | 47,503 / 47,503 非空 | `Importer.check_import_required()`（写库前）+ `write_names()` 写入前复检；空 ⇒ `DerivationError` ⇒ 整批 rollback |
| I-02 | `data_dataset` | `grain_evidence` | `CORE_DATA_MODEL_V2.1.1` §5.2 行 394「该 grain 判定从哪几个数推出来的。**必填**」 | 导入时必须非空（7 个数据集的 grain 判定依据） | 由导入程序按 §5.2.4 落值，7/7 非空 | 同上，`check_import_required()` |

> R1 修订：这两项此前只在文档里写着，代码没有真正拦截。现改为**写库前一次性校验 + 写入处复检**，
> 任一处为空即整批中止（退出码 2），不会出现"数据库允许 NULL 就顺过去"的情况。

| # | 表 | 规则 | 实装位置 |
|---|---|---|---|
| I-03 | `historical_place_name` / `historical_place_location` | `time_bound_type` 三分支映射（见下节） | `derive_time_bound_type()` + `assert_time_types()` |
| I-04 | `candidate_match` | 未入库行必须逐条留痕，并可回指原始 CSV 行号 | `write_candidates()` → `--excluded-csv` 指定路径（R1.1 起可配置，默认 `ops/reports/stage3_excluded_rows.csv`），由 `verify_import.py` V13 校验 |

## 已由数据库强制、无需导入程序重复实现的

| 列 | 设计原文 | 落地方式 |
|---|---|---|
| `historical_place_name.source_record_id` / `historical_place_location.source_record_id` | 「导入创建时必填」 | `CHECK (source_record_id IS NOT NULL OR created_by='manual')`，已落库并已验证 |

## 与许可相关的两条口径（阶段三必须遵守）

1. **`issue_type` 值域为 19 值**，`licence_unconfirmed` 已按 V2.1.1 §5.9 删除。
   暂存原始 12,631 行台账中有 **2 行**该类型：按 Owner 决策 3 **直接剔除、不重新归类**
   （依据：`CORE_DATA_MODEL_V2.1.1` §5.9 / `IMPORT_RULES_V2.1.1` R-11）。
   剔除是**导入程序的数据处置**，不是数据库拒绝——数据库中不存在任何以许可为条件的写入约束。
2. 系统**不做**授权 / 许可 / 再分发判断；`data_source`（2 列）与 `data_dataset`（9 列）
   的许可相关列已在模型中删除，导入程序**不得**为暂存中的 `license_status` / `license_url` 等列寻找落脚点。

> 不存在的门禁已在阶段二收尾用 `ops/verify_no_licence_gate.py` 逐项证明（目录级 0 命中 + 342 条台账写入全通）。

---

## I-03　时间类型三分支映射（`time_bound_type`）

权威依据：`CORE_DATA_MODEL_V2.1.1` §6.1（七值域）+ `V2.1_TO_V2.1.1_CHANGELOG.md` §B.6 决策 6。
**不改原始 CSV**，全部在导入器的映射环节派生。

| 分支 | 触发条件 | 处置 |
|---|---|---|
| ① `mask` | `time_rule_code = 'year_after_which\|year_before_which'` | 两端**相等** ⇒ `snapshot`（区间长度 0，"两端都是界限"不成立）；两端不等 ⇒ 保留暂存值 |
| ② `numeric` | 数字码（CHGIS `'3\|3'` 一类） | 直接沿用暂存值（`chgis_time_bound_type()` 既有 7 值域契约）。`from == to` 是**真实零长区间**，**保持 `bounded`，不得改判** |
| ③ `empty` | `time_rule_code` 为空 | 直接沿用暂存值 |

**唯一改判对象（实测）**：`nm_0045996`「Boxar」、`nm_0046197`「Catife」，两条 `after = before = 1500`
⇒ `bounded → snapshot`。改判后：

| 表 | `bounded` | `snapshot` | `exact_or_bounded` | 说明 |
|---|---:|---:|---:|---|
| `historical_place_name` | **1,164**（暂存 1,166 − 2） | **56**（暂存 54 + 2） | 2,360（不得与 bounded 互换） | 入库 47,499 行（暂存 47,503 − 隔离 4） |
| `historical_place_location` | 398 | 21 | 812 | 本表 mask 分支无两端相等行，不受影响 |

**边界（F17b）**：同表另 **17 行** CHGIS `time_rule_code='3|3'` 也满足 `from == to`，走 `numeric` 分支，
**保持 `bounded`**。17 是期望值，不是缺陷值。`19 = 2 + 17`。

**断言（A10）**：`mask` 分支两端相等却非 `snapshot` 必须为 0；`mask` 分支两端不等却为 `snapshot` 必须为 0；
`numeric` 分支两端相等仍 `bounded` 必须为 17；两表 `time_bound_type` 均不得越出七值域；
分布按「暂存行 − 隔离行」经映射逐类型比对；并对上述两条记录做逐行核验（值 = snapshot、两端 = 1500、`notes` 非空）。

> 台账口径提示：`V2.1_TO_V2.1.1_CHANGELOG.md` §B.6 称「两行已在 `beg_eq_end` 台账 341 行内，不新增台账」。
> **实测不成立**：暂存台账 341 条 `beg_eq_end` 全部是 CHGIS 记录（`chgis_pref` 175 + `chgis_cnty` 166，
> `source_record_id` 均非 `sr_0021392` / `sr_0021146`）。本程序按要求**不新增台账行**（总数仍为 12,831），
> 差异如实登记在此，不改数据。

---


| # | 事项 | 事实 | 处置 | 依据 |
|---|---|---|---|---|
| D-01 | `candidate_match` **自指行** | 暂存 53,137 行中有 **2 行** `place_id_a = place_id_b`（`cm_0052746` / `cm_0052747`，CHGIS 桂林郡 `SYS_ID` 35000/35001 的**同一外部 ID 内部重复**，record_index 4834 vs 4941） | **不入 `candidate_match`**：数据库有 `CHECK (place_id_a <> place_id_b)`，且该事实已由 `duplicate_sysid` 台账（`dq_0007485` / `dq_0007486`）+ `duplicate_ordinal` 隔离完整承载。原行逐字留痕于 `ops/reports/stage3_excluded_rows.csv`（含目标 `place_id`），**未删除、未改写** | `CORE_DATA_MODEL_V2.1.1` §5.8 表级 CHECK；`IMPORT_RULES` §5 重复隔离 |
| D-02 | `candidate_match` **C09 同向收敛** | 同一 `(relation_type, place_id_a, place_id_b)` 在**暂存文件内**重复出现 3 组、多出 **4 行**（`cm_0025046` / `cm_0025047` → `cm_0025045`；`cm_0025180` → `cm_0025179`；`cm_0025182` → `cm_0025181`） | 保留首行、收敛 4 行（`UNIQUE uq_candidate_match_c09` 强制），入库 **53,131 = 53,137 − 2 − 4**。**R1 起逐条留痕**（而非只加计数）：4 行连同自指 2 行共 6 行写入 `stage3_excluded_rows.csv`，字段含 `staging_row_no`（原始 CSV 行序）、`exclusion_reason`、`converged_to_candidate_id`。**未按 U18 过滤**：U18 仍未拍板，程序中不存在任何基于 `status` 的过滤分支 | 同表 C09；`CORE` §9.4 登记项 U18 |
| D-03 | `R1` 的 `N_noop` 取数式 | 设计 §5.2 写作「`inactive_reason` 非空且 `<> duplicate_quarantine`」，但**本次回滚刚写入的 `batch_rolled_back` 行会被算进去**，右式多减，R1 必然破裂（夹具实测：LHS=3 / RHS=0） | 收窄为「**回滚前**已失效」：再加 `NOT (inactive_reason='batch_rolled_back' AND inactive_in_batch_id=:R)`。修正后 LHS=3 / RHS=3。性质与阶段二 `v_place_liveness` 的 FILTER 括号修正相同——**使设计可执行，不改语义** | `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1` §5.2；§3.3 中 `N_noop` 定义「回滚前已失效」 |

## 导入期六集合计数（G1）的落地

`IMPORT_RULES` §3.2 的 G1 恒等式已逐数据集自检，七批全部平衡：

```
input_row_count = N_fail_import + N_quar + N_inserted + N_updated + N_noop + N_blocked
```

- `N_blocked` 的四种成因全部实装：`created_by='manual'` / `locked` / `manual_edited_fields` 非空
  ⇒ 记录级跳过 + `blocked_count+1` + **一行** `manual_edit_conflict` 台账；
  第四种 `quarantine_hold`（已隔离行再次出现）⇒ 只 `blocked_count+1`，**不落台账**（其台账在产生隔离结论的批次已记）。
- 首轮：29,391 = 0 + 3 + 29,388 + 0 + 0 + 0
- 重导：29,391 = 0 + 0 + 0 + 0 + 29,388 + 3（3 行隔离保持，计入 blocked）

---

## R1.1 复核记录（在新空库 `canvas_history_stage3_r11` 上重跑，逐项实测）

本文件所列规则在新库重跑时全部再次实测，结果如下（日志：`ops/reports/r1_1/01_run1_import.log`、
`04_verify_import.log`、`07_time_type_rowcheck.log`）：

| 规则 | 本轮实测 | 结论 |
|---|---|---|
| I-01 `name.notes` 非空 | 47,503 / 47,503 | 通过，写库前拦截生效 |
| I-02 `dataset.grain_evidence` 非空 | 7 / 7 | 通过 |
| I-03 `time_bound_type` 三分支 | 改判行恰为 `nm_0045996` / `nm_0046197`（1500–1500 → `snapshot`）；name `bounded 1,164 / snapshot 56`；location `bounded 398 / snapshot 21`；F17b 边界 17 行仍 `bounded` | 通过；`07_time_type_rowcheck.log` 为 SQL 侧独立取证 |
| I-04 候选表逐条留痕 | 留痕 6 行（自指 2 + C09 4），`53,131 + 6 = 53,137`，`staging_row_no` 逐行回指原始行且字段逐字相符 | 通过（V13） |
| D-01 自指 2 行 | 仍不入库，逐字留痕 | 通过 |
| D-02 C09 收敛 4 行 | 仍逐条留痕，未按 U18 过滤 | 通过 |
| D-03 `N_noop` 取数口径 | R1 等式 3 == 3；错误顺序反证 RHS = −2 | 通过 |

**未变**：本轮没有新增、废止或修改任何一条导入级规则；`--excluded-csv` 只是把留痕写到哪里做成参数，
避免新一轮覆盖上一轮证据（R1 的 `ops/reports/stage3_excluded_rows.csv` 未被改写）。
