# M4-5 前置专项修正报告｜地点级时间包络口径统一

> 施工授权：OWNER APPROVED（M4-5 前置专项）。
> 本轮只做一件事：把 `normalize.py` 与 `import_staging.py` 对"地点级时间"的纳入规则统一，
> 消除 M4-4b / M4-4c 登记在案的 820 条 `derived_value_mismatch`（629 个地点）。
> **完成后停止。未连正式库、未执行 Migration、未向任何验收库写入 Pleiades 数据、未启动 M4-5 正式导入。**

---

## 一、结论

| 项目 | 结果 |
|---|---|
| 规则认定 | 地点级时间 = **仅** 名称 + 位置子行的 TPQ/TAQ 包络；connection 不参与 |
| 依据 | `CORE_DATA_MODEL_V2.1` §5.5.4、`IMPORT_RULES_V2.1` §7.6（既有定义，非本轮新造） |
| 逐条审计 | 820 条 **100%** 由 connection 造成；`driver.value == 暂存值` 820/820；无法解释 **0** |
| 代码改动 | `normalize.py` +19 / −1，仅 `_place_time_bounds` 内一处 `continue` |
| 暂存重建 | `data/staging_m4_5/`（**不覆盖** `staging_m4_3`），两次独立构建逐字节一致 |
| 变更面 | 1,182 个单元格 / 629 个地点；其余六张表与已验收暂存**逐字节相同** |
| 隔离库验证 | `canvas_history_m4_5_verify`（由 `m4_4b` 克隆）；**36/36** 判据通过；820 → **0** |
| 幂等 | 连跑两轮：新增 0 / 更新 0 / 台账不膨胀；行数 Δ0 |
| 既有四源 | 七张表指纹与 M4-4b 交付**完全一致** |
| 测试 | 单元 11/11；API 级回归 61/61（含时间轴 E8/E9） |

**820 条差异全部得到正确解决，没有一条被删除、屏蔽或降低判据。** 那 820 行历史台账原样留在库里（不删、不改），
本轮导入没有再产生任何一条同类记录。

---

## 二、施工前检查

| 项 | 结果 |
|---|---|
| 分支 | `m4-3-pleiades-gis`（沿用，未开新分支） |
| HEAD | `d7eefa5`（M4-4c 报告）；M4-4c 两个提交 `f5182ec` / `d7eefa5` 均存在 |
| 工作区 | 仅 `汇报/` 未跟踪（交付目录），无其他脏文件 |
| 已验收暂存 | `data/staging_m4_3/` 七张表 SHA256 与 `manifest.json` **逐项相符**（7/7 OK，0 处不符） |
| 验收库 | `canvas_history_m4_4b`：Flyway V9；157,220 / 57,967 / 84,554 / 53,792 / 66,311 / 21,447 / 9 |
| 问题现状 | `derived_value_mismatch` **820 行 / 629 个地点**：v4.1 占 623 行 / 499 地点，切片占 197 行 / 130 地点 |

审计与基线证据在 `ops/reports/m4-5/audit_before.{json,csv}`，全程只读，未改动任何已验收产物。

---

## 三、根因认定（源码 + 逐条数据，双重确认）

### 3.1 源码事实

`normalize.py` 第 711 行把三类子记录一起放进 `extra_children`：

```python
elif record.record_kind in ("name", "location", "connection"):
    extra_children[f"{record.source_dataset}:{record.parent_external_id}"].append(record)
```

而 `_place_time_bounds()` 只按 `time_bound_type ∈ {tpq_taq, bounded}` 过滤，**不看 `record_kind`**，
于是 connection 的 TPQ/TAQ 也进了地点包络。

`import_staging.py` 第 1103–1113 行的重算规则写的是另一套：

```python
# +197：地点级时间重算 vs 暂存值（只聚合 name+location，排除 edge）
for r in self.name_rows + self.loc_rows:
```

两处口径不一致，差异被如实记进台账——**这正是 M4-4b 看到的 820 行**。

### 3.2 哪一套才是"对"的：设计文档已有定义

`CORE_DATA_MODEL_V2.1` §5.5.4（地点级时间不入库、改派生视图）给出可执行定义：

> 地点的时间跨度是"**它的名称与位置的时间跨度之并**"，是一句可以随时重算的派生结论。
> 派生视图 `v_place_time_span` 的 SQL 只 `UNION ALL` `historical_place_location` 与 `historical_place_name`。

`IMPORT_RULES_V2.1` §7.6 的重算规则同样只聚合 name+location。
**所以导入器是对的，`normalize.py` 是偏离方。** 本轮修的是偏离方，没有改判据。

语义上也站得住：Pleiades 的 connection 行带 `part_of_admin` / `insula-batavorum` / `sumer` 这类关系类型，
它的 `year_after_which` / `year_before_which` 说的是"**这两个地点之间的关系何时被证实**"，
不是"这个地点何时存在"。把它算进地点包络，等于允许邻接地点的年代改写本地点。

### 3.3 逐条数据：820 条一条不漏地归因

`ops/m4-5/audit_time_envelope.py` 对暂存里 57,967 个地点各算三个口径：

| 口径 | 定义 |
|---|---|
| `E_all` | name + location 全部带数字年份的子行（= 导入器规则） |
| `E_bound` | name + location，且 `time_bound_type ∈ {tpq_taq, bounded}`（= 排除 connection 后的归一化口径） |
| `E_bound_conn` | `E_bound` 再加 connection（= 归一化**当时实际**口径） |

结果：

| 判据 | 数值 |
|---|---|
| 暂存值 ≠ `E_all` 的记录 | **820**（与库里台账逐条相同） |
| 其中 `E_bound_conn` 能完整复现暂存值 | **820 / 820** |
| 驱动记录（给出极值的那条 connection）年份 == 暂存值 | **820 / 820** |
| 需要 `bound_type` 过滤参与的 | 0 |
| 无法解释 | **0** |

样例（`ops/reports/m4-5/mismatch_820_before_after.csv` 全量可查）：

| place | 外部 id | 字段 | 旧暂存值 | 驱动 connection | 关系类型 | 年份 |
|---|---|---|---:|---|---|---:|
| hp_016476 | 98921 | from | −329 | `insula-batavorum` | `in` | −329 |
| hp_016592 | 903002 | from | −539 | `achaemenid-empire` | `part_of_admin` | −539 |
| hp_016743 | 912905 | to | 651 | `sasanian-empire` | `part_of_admin` | 651 |
| hp_016792 | 912985 | from | −6499 | `sumer` | `part_of_regional` | −6499 |

受影响幅度：收窄的 458 个字段里，**中位收窄 1,400 年，最大 10,299 年**。这不是"±1 年的舍入噪声"，
是"一个地点被邻接地点的年代强行拉宽"这种实质性错误。

### 3.4 与历史文档的一处偏差（如实记录，未擅自改文档）

`CORE_DATA_MODEL_V2.1` §5.5.4 在解释当年那 197 条时写的原因是
"有 123 个 names 记录因为 title 为空等原因没有产出名称行，但其时间声明仍被计入地点聚合"。

**在当前暂存里，这条机制贡献为 0。** 判据：若存在"无对应行的记录仍在驱动地点值"，则暂存值必然
既不等于 `E_all`、也无法由任何 connection 解释，审计会落到 `unexplained`。实测 `unexplained = 0`，
且 197 条逐条都由 connection 极值完美复现。

推断：该文档写于 M2 时期的切片归一化版本，本轮 M4-4a 的全量抽取器对每个 name 记录都产出了行
（含空标题，打 `empty_name` 标记），这条旧通路已不存在。**文档未改**（属设计资料，不在本轮授权内），
记录在此供 Owner 决定是否回填勘误。

---

## 四、统一后的规则（一句话）

> **地点级时间 = 该地点 `historical_place_name` 与 `historical_place_location` 子行中，
> `time_bound_type ∈ {tpq_taq, bounded}` 者的最早 TPQ 与最晚 TAQ；connection 记录不参与；
> 若没有任何这类子行，则地点级时间为空、`time_bound_type='unknown'`、`time_derivation='none'`。**

`normalize.py` 与 `import_staging.py` 现在都按这一套算。导入器的规则字符串一字未改（它是判据，不是被改的对象）。

---

## 五、最小代码修正

`code/p0/wb-002-normalize/normalize.py`：+19 / −1，全部在 `_place_time_bounds` 内。

```python
for record in children:
    # M4-5：connection 子记录不进入地点级时间包络。依据 CORE_DATA_MODEL_V2.1 §5.5.4 /
    # IMPORT_RULES_V2.1 §7.6：地点的时间跨度是"它的名称与位置的时间跨度之并"……
    if record.record_kind == "connection":
        continue
    if record.time_bound_type not in ("tpq_taq", "bounded"):
        continue
```

- 没有改 `extra_children` 的装配（它还承担名称/位置/连接三类的分发职责，改这里会波及别处）。
- 没有改导入器、没有改数据库、没有新增 Migration、没有动 CHGIS / MCGD / WHG 分支。
- 函数 docstring 同步补充了这条规则与其依据。

---

## 六、暂存重建

输出目录 `code/data/staging_m4_5/`，**`data/staging_m4_3/` 未做任何写入**（构建前后哈希一次核验，7/7 相符）。

### 6.1 可复现

两次独立构建（一次到目标目录、一次到系统临时目录），七张 CSV **逐字节相同**。

### 6.2 与已验收暂存的差异：只动了该动的

| 文件 | 结果 |
|---|---|
| `historical_places.csv` | 变化（1,182 单元格 / 629 地点） |
| `historical_place_names.csv` | **逐字节相同** |
| `historical_place_locations.csv` | **逐字节相同** |
| `source_records.csv` | **逐字节相同** |
| `data_quality_issues.csv` | **逐字节相同** |
| `candidate_matches.csv` | **逐字节相同** |
| `data_datasets.csv` | **逐字节相同** |

`historical_places.csv` 内部：行数 57,967 → 57,967，主键顺序完全一致，表头一致，
**非时间列变化 0**。

| 变化列 | 数量 |
|---|---:|
| `valid_from_year_astro` | 511 |
| `valid_to_year_astro` | 309 |
| `time_bound_type` | 181（全部 `derived_tpq_taq` → `unknown`） |
| `time_derivation` | 181（全部 `tpq_taq_of_children` → `none`） |

方向核验：**收窄 458 / 清空 362 / 变宽 0**。移除一个只会拉宽包络的证据源，结果只能是变窄或变空——
出现任何"变宽"都说明改错了，实测 0 条。

### 6.3 181 个地点的时间被清空：这是正确的语义结果

这 181 个地点**只有 connection 纪年**，没有任何名称或位置的纪年。旧口径给它们一个"看起来有据"的年代，
实际依据全部来自邻接地点的关系行。按 §5.5.4 的定义，它们本来就该是"源未声明"。

补充事实：`historical_place` 表**没有年份列**（`information_schema` 里 year 相关列为 0 个），
地点级时间从不入库，用户看到的时间范围一直由子行算——所以这 181 个地点的产品可见行为没有变化，
变化的是"暂存里那个不可复算的数字"。

### 6.4 manifest 与哈希

`data/staging_m4_5/manifest.json`（含 40 个输入文件的 SHA256 与前后未变校验）、`SHA256SUMS.txt`：

```
58b4dedf2a2c1e25390a3089849369c5395b4d732821a8e2dd27bb815d107372  historical_places.csv
281105066963c5f32cf7b020c634a7002a45ac7b4affab2fe6f3d8e04d2f34cf  historical_place_names.csv
7ac7b28b88f94af8e105f45d6114d75c33f7684ffc5c3e9c6112f4762bb65cd5  historical_place_locations.csv
1a2d8b66e41c3aa41700630a42e769c4ef652fcf17bbd458212846ead8b1e502  source_records.csv
23d37766f568c329081db90c95bfb30b4ed46823ae896ee80f4a1d8258b194b9  data_quality_issues.csv
9abba953096159b1dd046e9d984dba84f6c7f7921874468c11d7bdb744fcaca7  candidate_matches.csv
7cd39277de70132bfc298bac49b9ada0036dde3901479fe549d576667a70ed81  data_datasets.csv
```

只有第一行与 M4-4a 不同，其余六行与 `staging_m4_3` 完全一致。

---

## 七、隔离库验证

验证库 `canvas_history_m4_5_verify`，由 `canvas_history_m4_4b` **克隆**（Flyway V9、157,220 源记录）。
`m4_4b` 本身、`m4_4b_protect`、`m2check`、`m4check`、正式库 `canvas_history` **均未写入**。

### 7.1 A/B 对照：同一份代码、同一个库，只换暂存

| 输入 | 导入器算出的差异 |
|---|---|
| `data/staging_m4_3`（旧） | `duplicate_external_id 36 + derived_value_mismatch 820（629 个地点）` |
| `data/staging_m4_5`（新） | `duplicate_external_id 36 + derived_value_mismatch 0（0 个地点）` |

这是最干净的一组证据：**判据没动、代码没动、库没动，只有归一化产物变了，差异归零。**

### 7.2 导入结果

| 表 | 导入前 | 导入后 |
|---|---:|---:|
| `source_record` | 157,220 | 157,220 (Δ0) |
| `historical_place` | 57,967 | 57,967 (Δ0) |
| `historical_place_name` | 84,554 | 84,554 (Δ0) |
| `historical_place_location` | 53,792 | 53,792 (Δ0) |
| `candidate_match` | 66,311 | 66,311 (Δ0) |
| `data_quality_issue` | 21,447 | 21,447 (Δ0) |
| `import_batch` | 30 | 38 (Δ+8) |

8 个批次全部 `succeeded`，G1 逐批平衡，几何/时间/幂等三组断言全通过。
唯一的行数变化是批次表本身——因为新暂存与库内已导入内容**逐条相同**，没有任何东西需要重写。

### 7.3 七组判据（36/36）

| 组 | 内容 | 结果 |
|---|---|---|
| V1 | 七张表行数与 M4-4b 验收值逐项相等 | 7/7 |
| V2 | **57,967 个地点**的地点级时间 == 库里 name+location 子行包络 | 57,967/57,967，差异 **0** |
| V3 | 629 个受影响地点逐个核对；变化数 629；其中仍不符 0；变宽 0 | 5/5 |
| V4 | 181 个"只有 connection 纪年"的地点：双空 + `unknown/none` + 库内确无子行纪年 | 4/4 |
| V5 | 820 条历史台账原样保留；本轮没有新增一条同类记录 | 5/5 |
| V6 | 既有四源七张表指纹与 M4-4b 交付逐项一致 | 7/7 |
| V7 | 时间轴：10 样本有效年命中 / 有效年外不命中 / 覆盖 BCE / 子行年份未变 | 6/6 |

> V2 用的是 `(dataset_id, grain_key)` 装配键（不是 `hp_` 编号——v4.1 的库内 `place_id` 从 135,875 起）。
> 7 个地点无法按该键映射，全部是 MCGD 的 `primary_external_id` 填 LocID 的既有问题
> （`CORE_DATA_MODEL_V2.1` §5.5.3 已登记），它们没有任何地点级时间，比对因此仍成立。

### 7.4 幂等

同一份新暂存在同一库连跑两轮：第二轮 `新增 0（其中重叠地点失效 0）/ 内容变更 0 / 仅触 last_batch_id 157,213`，
地点 `新增 0 / 无变化 57,967`，台账 `derived_value_mismatch 0`，全部表 Δ0。
`occurrence_count` 按设计从 4 推进到 6，`last_batch_id` 全部前移——这是设计要的副作用，不是膨胀。

### 7.5 既有四源没有非预期变化

`ops/m4-4b/fingerprint.sql`（cutoff=14，即 V9 之前创建的行）在导入前后各取一次，七个指纹逐项相等：

```
source_record 29,391 · historical_place 19,039 · historical_place_name 47,499
historical_place_location 18,101 · candidate_match 53,131
data_quality_issue 12,833 · data_dataset 8
```

---

## 八、820 条差异逐条对照

`ops/reports/m4-5/mismatch_820_before_after.csv`（19 列，820 行）每条给出：

`place_id / 外部 id / 名称 / 字段 / 修复前值 / 修复后值 / 规则重算值 / 变化方向 /
驱动 connection（id、关系类型、对端地点、年份、原始文件与行号）/ 修复前后 time_bound_type / 结论`

结论列统计：**fixed 820，still_broken 0**。按数据集 v4.1 623 / 切片 197；按字段 from 511 / to 309。

`ops/reports/m4-5/place_time_cell_diff.json` 则是 1,182 个单元格的完整新旧值（含 181 组类型降级）。

---

## 九、629 个地点的核验结果

| 分组 | 地点数 | 说明 |
|---|---:|---|
| 上下界收窄但仍有值 | 448 | 时间主张仍成立，只是不再被邻接关系拉宽（458 个字段） |
| 上下界双空 + 类型降级 | 181 | 自身无任何名称/位置纪年，只有 connection 纪年 ⇒ 依规则应为"未声明" |
| 合计 | 629 | 全部与库内子行包络一致（V2/V3 双路核到同一数） |

明细见 `mismatch_820_before_after.csv`（按 `place_id` 去重即 629 个）。

---

## 十、测试与回归

| 套件 | 结果 | 说明 |
|---|---|---|
| `ops/m4-5/test_time_envelope.py` | **11/11** | connection 排除（宽/窄/多条/仅有）、name+location 并集、`bound` 过滤、年份 0 拒绝、MCGD / WHG / CHGIS 分支未变 |
| `ops/m4-5/audit_time_envelope.py` | 820 → **0** | 同一脚本对新旧暂存各跑一次 |
| `ops/m4-5/build_and_verify.py` | **7/7** | 双构建一致 / 表头 / 行序 / 仅时间列 / 六表逐字节 / 无变宽 / 差异归零 |
| `ops/m4-5/verify_db_m4_5.py` | **36/36** | 七组数据库判据 |
| `ops/m4-4c/api_e2e.py`（回归） | **61/61** | 含 E8 时间轴（BCE 7 / CE 3）与 E9 地图-时间轴联动 |

只跑了与本次修改相关的测试与时间轴回归；**没有修改任何既有测试断言**。

---

## 十一、已知遗留与非目标差异（单独列明，未处理）

| # | 事项 | 状态 |
|---|---|---|
| 1 | 181 个地点的时间从有值变空——语义正确，但属"用户可见信息减少"的取舍 | 已在上文说明，等 Owner 确认 |
| 2 | §5.5.4 对 197 条根因的描述（"123 个 name 记录无对应行"）在当前暂存不成立（实测 0） | 记录，未改设计资料 |
| 3 | 管理界面编辑不写 `locked` / `manual_edited_fields`（M4-4c 发现） | **未动**（明确禁止） |
| 4 | `action_taken` 732 行动词映射 | **未动**（明确禁止） |
| 5 | `place_type` 多值关联表 | **未动**（明确禁止） |
| 6 | `is_preferred` 全 false | **未动**（明确禁止） |
| 7 | 42 行 `name_lang` 落到 `und` 的保真问题 | **未动**（明确禁止） |
| 8 | 地图面/线真实形状渲染 | **未动**（明确禁止） |
| 9 | 7 个 MCGD 地点按 `primary_external_id` 无法 join（§5.5.3 既有） | 未动，本轮 V2 已用"无地点级时间"兜住 |
| 10 | `derived_value_mismatch` 的 820 条历史台账仍留在库里 | 按规则不删；它们对应的是修复前的暂存版本 |

---

## 十二、交付物

| 类型 | 路径 |
|---|---|
| 源码修正 | `code/p0/wb-002-normalize/normalize.py` |
| 新暂存 | `code/data/staging_m4_5/`（七张 CSV + `manifest.json` + `SHA256SUMS.txt`） |
| 审计与构建 | `code/ops/m4-5/audit_time_envelope.py`、`build_and_verify.py` |
| 验证 | `code/ops/m4-5/verify_db_m4_5.py`、`make_comparison.py` |
| 测试 | `code/ops/m4-5/test_time_envelope.py` |
| 对照 | `ops/reports/m4-5/mismatch_820_before_after.{csv,json}`、`place_time_cell_diff.json` |
| 日志 | `ops/reports/m4-5/00…10_*.log`（10 份） |
| 结果 | `ops/reports/m4-5/{audit_before,audit_after,build_verify,verify_db,verify_db_after_run2}.json` |

数据库：`canvas_history_m4_5_verify` 保留（不删），供复核。
`canvas_history_m4_4b` / `canvas_history_m4_4b_protect` / `m2check` / `m4check` / 正式库**均未写入**。

---

## 十三、Git

| 项 | 值 |
|---|---|
| 分支 | `m4-3-pleiades-gis`（沿用，未推送） |
| 代码提交 | 见 `git log`（`fix(m4-5): …`） |
| 报告提交 | 见 `git log`（`docs(m4-5): …`） |
| 不入库 | `code/data/staging_m4_5/*.csv`（约 250 MB，按 `data/staging*` 同一约定忽略，只提交 manifest 与 SHA256SUMS）、`ops/reports/m4-5/*.log` |

---

## 十四、停止声明

**M4-5 前置专项 STOP / WAITING FOR OWNER ACCEPTANCE.**

未执行：正式库 Migration、向正式库或 `m4_4b` 导入 Pleiades、M4-5 正式导入、M4-6。
