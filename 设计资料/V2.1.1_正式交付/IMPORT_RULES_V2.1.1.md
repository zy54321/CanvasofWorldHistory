# 数据导入与更新规则 V2.1.1

**项目**：《世界历史时空画布》
**版本**：2.1.1（取代 `IMPORT_RULES_V2.1.md` 2.1.0；V2.1 文件保留原样不覆盖）
**性质**：规则文档。**本轮不含任何数据库施工**——无 DDL 执行、无 Migration、无数据导入、不改 `normalize.py`、不改暂存 CSV。
**权威来源**：`V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md`（**V0.2.2**，1,127 行）> `V2.1.1/00_PROBLEM_LIST_AND_PLAN.md`（V0.2.1）> `V2.1/CORE_DATA_MODEL_V2.1.md` / `IMPORT_RULES_V2.1.md`（V2.1）> `CORE_DATA_MODEL_V2.md`（V2）。
**配套**：`CORE_DATA_MODEL_V2.1.1.md`（模型与视图）、`正式交付/_build/SHARED_BASELINE_V2.1.1.md`（共享定义基线，**不参与八份交付物计数**）。

> **效力顺序**：V0.2.2 > V0.2.1 > V2.1 > V2。凡与 V0.2.2 冲突，一律以 V0.2.2 为准。
> **章节编号**沿用 V2.1 的 0–11 便于对照；本版在末尾新增 §12 施工验证清单、§13 两条施工级硬提醒。

---

## 0. 本版修了什么

V2.1 的导入骨架（幂等双键、先算后写、QUARANTINE 不 REJECT、写入阶段划分、`should_write()` 三处共用）**全部保留**。本版只改 V0.2.2 定死的部分：

| # | 项 | V2.1 | V2.1.1 | 出处 |
|---|---|---|---|---|
| R-1 | 业务唯一键 | 四段（含 `occurrence_key`） | **五段**（`parent_external_id` + `duplicate_ordinal`） | C01、C29 |
| R-2 | `parent_external_id` | 可空派生列 | **必需段**，无父级落哨兵 `'-'`；**不得 NULL / 空串** | C29 |
| R-3 | 重复行身份 | `occurrence_key = parent#ordinal` | **`duplicate_ordinal`**，按 `(content_hash ASC, raw_record_index ASC)` 定序 | §3.3 |
| R-4 | 隔离判据 | 未写死 | **同 hash 子组内最小 ordinal 保留，后续相同 hash 隔离** | §5 |
| R-5 | `content_hash` | `sha256(canonical_json(...))` | **`sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))`** 逐字写死 | CIT-2′ |
| R-6 | 建点判据 | `record_scope <> 'place'`（过宽） | **白名单 + `place_grain` 显式声明** | §4 |
| R-7 | 七类操作 | 10 行判定表 | **11 行**，新增**第 0 行：重复检测优先** | §6 |
| R-8 | 自动失效 vs 人工拒绝 | 未区分 | **`rejected_by`（`auto`/`manual`）**；`manual` 永不自动恢复 | §7 |
| R-9 | 回滚统计 | `\|B\| − blocked_count` | `( \|B\| − N_quar ) − N_noop − blocked_count − failed_count` | §7.4 |
| R-10 | canonical | 各表各取 | **统一外层定序（6 键）**；每个地点**恰有一个** canonical；零有效证据时该行仍落定序第一行但**不构成有效证据**（canonical ≠ 有效，两件事）；315 个无子行地点（入库口径）**不补造名称行** | §10 |
| R-11 | 许可 | 有导入前置校验项 | **全部删除**【留痕：已删除校验项说明，保留以便追溯，非现行校验】——`data_dataset` 9 列许可相关列已删，本系统不做授权 / 再分发判断 | §2 |

---

## 1. 幂等

### 1.1 两个键，两个职责

| 键 | 组成 | 回答什么 |
|---|---|---|
| **业务唯一键（五段）** | **`(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)`** | 这是源里的**哪一行** |
| **内容哈希** | **`sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))`** | 这一行的**内容变了没有** |

两者不能互相替代：源改了一个字段，哈希就变而键不变（是"更新"）；源加了一行，键变而哈希可能撞（是"新增"）。

> **V2.1 → V2.1.1（R-1）**：四段键的 `occurrence_key` **已删除**，拆成 `parent_external_id` 与 `duplicate_ordinal` 两个独立段。**V0.2.2 全篇 `occurrence_key` 零命中。**

### 1.2 哈希口径（**逐字实现**）

```
content_hash = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))   -- 规范定义（唯一）
sha256(raw_payload_json 逐字节)                                                        -- 等价形式（当且仅当 normalize.py:306 约定不变时）
```

- **规范化表达式是主规范**。逐字节版的稳定性依赖**上游 `normalize.py:306` 的一个约定**，不是自保证的。
- **可扫描指纹（CIT-2′）**：完整串（带算法外壳）`len == 85`、`sha1 == 9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5`；内层 `json.dumps(...)` `len == 77`、`sha1 == 781f68645c4e2e3af4b18871f2f5b7848c5f3798`。三处（V0.2.2 §2.5.6 / CHANGELOG D-03 / 交付物）**逐字一致**。

**八条沿用规则**（与 `CORE_DATA_MODEL_V2.1.md` §4.4 同一份）+ V2.1 第 7、8 条：

7. `raw_payload` 的键名保持源文件原样（CHGIS 县级层 `ENT_DATE` vs 府级层 `END_DATE`），**不做键名归一**。
8. `raw_payload` **不含导入器补齐的任何字段**（`record_scope`、`parent_external_id`、`duplicate_ordinal`、批次号、时间戳都不进哈希）。

> **必须逐字实现**——任一条不同，同一份文件重导的 `updated` 就不是 0，幂等断言会天天报警，然后被人关掉。

### 1.3 幂等断言（每次导入结束必须自检，失败即整批 `failed`）

```
A1  count(source_record WHERE dataset_id=:ds AND first_batch_id=:b) == len(inserted_ids)
A2  count(source_record WHERE dataset_id=:ds AND is_active)
      + count(source_record WHERE dataset_id=:ds AND NOT is_active) == input_row_count
A3  SELECT 五段业务键 FROM source_record WHERE dataset_id=:ds
      GROUP BY 1 HAVING count(*)>1   →  必须 0 行
A4  同一份输入 + 同一 dataset_version 再导一次：
      inserted = 0 且 updated = 0 且 failed = 0 且 quarantined = 0
A5  batch.failed_count == count(data_quality_issue WHERE batch_id=:b AND issue_type='import_row_error')
A6  batch.quarantined_count == count(source_record WHERE first_batch_id=:b AND NOT is_active)
A7  count(source_record WHERE dataset_id=:ds AND parent_external_id IS NULL)          == 0   -- C29
A8  count(source_record WHERE dataset_id=:ds AND parent_external_id = '')             == 0   -- C29
A9  count(source_record WHERE dataset_id=:ds AND duplicate_ordinal IS NULL)           == 0   -- C01
```

> **A7 / A8 / A9 本版新增**：把"漏了 `parent_external_id` 段"从**静默数据损坏**变成**整批失败**。漏段的后果是 398 组 / 2,335 行被误判为重复（真实 7 组 / 14 行），数百条被误隔离且**不报错**。

**A4 的实测基线**（29,391 行，**暂存原始**口径）：

| dataset | 行数 | 首导 inserted | 重导 inserted | 重导 updated | 首导 quarantined |
|---|---:|---:|---:|---:|---:|
| `chgis_v6_prefecture_points` | 5,226 | 5,226 | 0 | 0 | **2** |
| `chgis_v6_county_points` | 10,522 | 10,522 | 0 | 0 | 0 |
| `mcgd_zenodo_22094815_head960` | 960 | 960 | 0 | 0 | 0 |
| `pleiades_gis_4_1_slice` | 12,445 | 12,445 | 0 | 0 | **1** |
| `whg_geoname_s_gn_sample` | 209 | 209 | 0 | 0 | 0 |
| `whg_getty_tgn_sample` | 21 | 21 | 0 | 0 | 0 |
| `whg_hgis_de_las_indias_sample` | 8 | 8 | 0 | 0 | 0 |
| **合计** | **29,391** | **29,391** | **0** | **0** | **3** |

> `quarantined = 3` = `sr_0004941` / `sr_0004942`（CHGIS 桂林郡 `35000`/`35001`）+ `sr_0027175`（Pleiades connection `98909/20469`）。活性 **29,388**。
> V2.1 写的 `quarantined = 2` 已作废——它只算了 CHGIS 两条，漏了 Pleiades edge 那条。

---

## 2. 导入前置校验（写入前必须全部通过）

| # | 校验 | 不通过的后果 | 依据 |
|---|---|---|---|
| 1 | `data_dataset.record_scopes` 非空；源文件表头与声明一致；未出现未声明 scope | 整批拒绝 | CORE §5.2 |
| 2 | `input_sha256` 与 `data_dataset.content_sha256` 的关系符合预期（相同 = 重导，不同 = 新版本） | 不同则要求显式确认 | CORE §5.3 |
| 3 | 每条记录的 `record_scope` **与** `parent_external_id` 可派生；无父级时落哨兵 `'-'` | **整批拒绝**（不允许默认值兜底、不允许 NULL、不允许空串） | CORE §4.2、**C29** |
| 4 | 五段业务键唯一性预检；重复键全部命中"已知重复"清单 | 出现新重复 ⇒ 整批拒绝，人工确认后才可继续 | §3、§5 |
| 5 | 每个 place 能派生出唯一 `created_from_source_record_id` | 整批拒绝 | CORE §5.5.4 |
| 6 | 每个 place 能派生出唯一 `grain_key`（`place_grain` 值域内） | 整批拒绝 | CORE §5.5.3 |
| 7 | 地点级时间重算与暂存值比对，偏差行数写入预期台账 | 偏差数超出预登记阈值 ⇒ 警告 | CORE §5.10.3 |
| 8 | `derivation_version` 已声明 | 整批拒绝 | CORE §5.3 |

**第 3 条为什么这么硬**：漏 `parent_external_id` ⇒ 398 组 / 2,335 行被误判重复（真实 7 组 / 14 行），**数百条被误隔离**。这是**静默数据损坏，不报错**。
**第 1 条为什么这么硬**：`record_scope` 派生失败时若兜底成 `place`，MCGD 的 960 行会变成 960 个地点（而非 643 个），错误会以"看起来正常"的形态进库。

> **R-11**【留痕：明确不做声明，保留以便追溯，非现行功能】——V2.1 §8 的「`data_dataset.redistributable IS NOT NULL` 且 `license_verified_at` 非空」校验项**已删除**；`data_dataset` 的 9 列许可相关列在 V2.1.1 中全部删除，**本系统不做授权 / 再分发判断**。⛔ 不得据此恢复任何许可列或许可校验项。

---

## 3. 派生：必须在写库前算完

### 3.1 为什么必须"先算完再写"

四条派生（`record_scope` / `parent_external_id` / `duplicate_ordinal` / `content_hash`）都是**下游键的组成部分**。写库后再算 ⇒ 无法回滚到一致的中间态；算错一行 ⇒ 该行的键错 ⇒ 下游全部错位，而 `UNIQUE` 不会报错（它只是"看起来唯一"）。

### 3.2 `parent_external_id` 的派生规则（本轮补全）

```
parent_external_id(record) =
    record.raw_payload 顶层含 place_id  ?  raw_payload.place_id
  : record.raw_payload 顶层含 LocID     ?  raw_payload.LocID
  : 哨兵 '-'
```

**权威口径（实测，判据 = `raw_payload_json` 顶层是否含 `place_id` 或 `LocID`）**：

| 类别 | 行数（**暂存原始**） | 明细 |
|---|---:|---|
| **可派生** | **10,765** | Pleiades **9,802**（`pleiades_name_id` 4,579 + `pleiades_connection_id` 2,763 + `pleiades_location_id` 2,460）+ MCGD **960** + **`whg_geom_index` 3** |
| **不可派生（落哨兵 `'-'`）** | **18,626** | `record_scope='place'` 全域 **18,398** + `whg_place_name_index` **223** + `whg_geometry` **5** |
| **合计** | **29,391** ✓ | |

三条硬规则：

1. ⛔ **不得用空串、不得用 NULL**——Postgres 的 `UNIQUE` 对多列 `NULL` **不去重**，会让五段键退化成四段键（C29 ②）。
2. **`record_scope='place'` 的记录一律落哨兵 `'-'`**——它**本身即实体、无父级**（覆盖 18,398 行，与 V0.2.2 §0 N10 的 place 全域一致）。
3. ⛔ **`whg_geom_index` 那 3 行 payload 顶层确实有父键，是【可派生】的，不得计入缺口。**

**「缺口 2,878」的准确口径**（相对 C29 ② 原文，**不是**相对零）：

```
place 全域 18,398 − C29② 原文已覆盖的 CHGIS place 15,748 = 2,650
    （= pleiades_place_id 2,643 + whg_source_id 5 + whg_place_id 2）
+ WHG 子记录缺口 228（whg_place_name_index 223 + whg_geometry 5）
= 2,878   ← 「相对 C29② 原文的缺口」
```

> ⚠️ **18,626 与 2,878 是两个不同口径，都对**：18,626 = **落哨兵总行数**；2,878 = 其中 **C29 ② 原文未覆盖**的部分。**引用时必须写明用的是哪一个。**

### 3.3 `duplicate_ordinal` 的派生

```
对每个五段键的四段前缀 g = (dataset_id, record_scope, parent_external_id, external_id)：
  组内按 (content_hash ASC, raw_record_index ASC) 定序
  |g| == 1  ⇒ 该行 duplicate_ordinal = 0
  |g| >= 2  ⇒ 按定序取 1..n
```

**`raw_record_index` 的使用限制（R-5 配套）**：

- **只能**在 `content_hash` **完全相等**时用于打破并列，**不得**参与常规定序；
- **不保证文件内唯一**：实测 14 个 `raw_file` 中有 **7 个**（全部为 WHG 的 json 抽取）索引不唯一——`gn_1790630_xian.json` n=39/max=37、索引 1 出现 3 次；`gn_1816670_beijing.json` n=91/max=89；`gn_3169070_roma.json` n=47/max=45；`gn_98182_baghdad.json` n=32/max=30；`tgn_7011781_london.json` n=21/max=19；`169687.json` n=3/max=1；`169687-169688.json` n=5/max=2；
- ⇒ **不得**被当作"文件内 1-based 唯一位置"使用，**不得**作为任何定序键或唯一性依据；
- 已验证：**7 个重复组内部均无 `raw_record_index` 并列** ⇒ 本轮 ordinal 结果不受影响。

### 3.4 派生失败即整批失败

`record_scope` / `parent_external_id` / `duplicate_ordinal` / `grain_key` 任一派生失败 ⇒ **整批 `failed`**，不允许默认值兜底。

> **为什么不允许兜底**：兜底会让错误以"看起来正常"的形态进库。MCGD 的 960 行若 `record_scope` 兜底成 `place`，就会变成 960 个地点而不是 643 个，且每个地点只有一条名称——事后极难发现。**宁可整批失败。**

---

## 4. 建点白名单（P1-03）

### 4.1 白名单（写死，逐字）

```
可作为建点依据的源记录 ⇔
   ( sr.record_scope = 'place' )                                    -- ① 逐记录建点
 OR ( sr.record_scope IN ('name','location')                        -- ② 按组建点
      AND sr.dataset_id 对应的 data_dataset.place_grain = 'per_parent_external_id' )
```
（V0.2.2 §2.7.1）

### 4.2 两个分支的处置

| `place_grain` | 该数据集的 name / location 记录 | 依据 |
|---|---|---|
| `per_record` | **不建点**；必须解析到**已存在的地点** | `IMPORT_RULES_V2.1.md:157`、V0.2.2 §2.7.1 |
| `per_parent_external_id` | **按 `parent_external_id` 建点**（MCGD：960 条 name → 643 个地点） | V0.2.2 §2.7.1 |

**其他两种情形**：

- 该 `dataset_id` 在 `data_dataset` 中**不存在** ⇒ **整批 `failed`**（与 A12 同一处置），**不是**"当作未声明"；
- 值域外的值 ⇒ 由 `CHECK (place_grain IN ('per_record','per_parent_external_id'))` 在**建库期**拦截，不进入运行期。

> ⛔ **不得写「未声明 `place_grain` ⇒ 禁止」**——取 NOT NULL + CHECK 2 值后，"未声明"既不可能为 NULL 也不可能落在值域外 ⇒ **该分支永不触发，是死代码**。白名单**只有一个判据**：`per_parent_external_id`（放行 ②） vs `per_record`（不放行）。

### 4.3 明确禁止

- ⛔ `record_scope = 'edge'`——Pleiades connection 的 id 是**被指向的**地点，不是它自己的地点；
- ⛔ 任何**未知** `record_scope` 值（A12：出现第五种 ⇒ 整批 `failed`）；
- ⛔ V0.2.1 的旧判据 `sr.record_scope <> 'place'`——它把 `edge` 与未来任何新类型**默认放行**，已被 §4.1 白名单取代。

### 4.4 白名单断言

```
V3'  count(creator 证据行 WHERE is_anchor) == 19,039          -- 每地点恰好 1 条锚点（入库口径）
V4   count(证据行 WHERE evidence_role='creator' AND source.record_scope='edge') == 0
V5   count(证据行 WHERE evidence_role='creator'
             AND source.record_scope='name'
             AND dataset.place_grain <> 'per_parent_external_id') == 0
```

> `NOT NULL + CHECK(2 值)` ⇒ `<> 'per_parent_external_id'` **等价于 `= 'per_record'`** ⇒ V5 语义不变、仍应恒为 0，且不再可能命中 NULL（旧写法下 NULL 会因 `NULL <> ...` 为 NULL 而被 `count` 漏掉——那才是隐患）。**交付物必须注明这个等价关系。**

### 4.5 写入顺序：数据集内部 place-scope 优先

同一数据集内，先处理 `record_scope='place'` 的记录，再处理 `name` / `location` / `edge`。

> Pleiades 的 `place_grain='per_record'`，只有 place 记录创建地点。名称与位置必须解析到已存在的地点。若先导 `names.csv`，4,579 条名称里凡父地点在切片内的都会变成孤儿。这个顺序错误**不会报错**，只会让 `parent_place_not_in_sample` 从 4,810 暴涨到 9,000 以上，然后被当成"切片太小"解释过去。

### 4.6 地点解析：三种结局，没有第四种

```
place_key(record) =
  dataset.place_grain == 'per_record'
    ? (dataset_id, record.external_id)          # 仅当 record_scope='place'
    : (dataset_id, record.parent_external_id)   # per_parent_external_id
```

| 结局 | 条件 | 动作 |
|---|---|---|
| **命中** | 地点已存在（本批已建或库中已有） | 正常挂子行 |
| **新建** | `place_grain='per_parent_external_id'` 且地点不存在 | 建地点（MCGD：960 条 name → 643 个地点） |
| **孤儿** | `place_grain='per_record'` 且地点不存在 | **不建地点**；落 `parent_place_not_in_sample`（info / preserved_and_flagged）；`source_record` **仍入库且 `is_active=true`** |

**孤儿记录为什么必须留着**：那 4,810 条是**真实的源数据行**，只是父地点不在这批切片里。下一批导入全量时，同一个五段键会命中已有记录，届时地点出现、子行自动补齐。**删了它们，全量导入时会漏掉这 4,810 条。**

---

## 5. 重复隔离算法

### 5.1 隔离判据（写死）

```
对四段前缀 g 的组内每一行 r，按 (content_hash ASC, raw_record_index ASC) 定序后：
  · 同一 hash 子组内【最小 ordinal】保留
  · 该子组内后续相同 hash 的行 ⇒ 隔离（is_active=false, inactive_reason='duplicate_quarantine'）
  · 不同 hash 的行 ⇒ 均保留（不隔离）
```

两条硬性禁止：

> ⛔ **禁止"只比 `ordinal = 1`"**。
> ⛔ **禁止"要求整组内容完全相同才隔离"**。实测 `external_id=20469` 出现在两个父级：`parent_external_id=98909` 的两行属于同一四段前缀组且内容相同，隔离 `sr_0027175`；`parent_external_id=98930` 的另一行属于不同组，必须独立保留。若漏掉 `parent_external_id`，就会把跨父级记录误合并。

### 5.2 四种排列的逐步推演

设 hash 全序 `A < B < C`（定序键是 `content_hash`，**文件物理顺序不参与**）。

#### ① `A,B,B`（3 行：A ×1，B ×2）→ **隔离 1 行**

| ordinal | hash | 所属子组 | 处置 | 依据 |
|---:|---|---|---|---|
| 1 | A | A 子组 {1} | **保留** | 子组内最小 ordinal（且子组只有 1 行） |
| 2 | B | B 子组 {2,3} | **保留** | 与 A **不同 hash** ⇒ 不因跨组而被隔离；且是 B 子组最小 ordinal |
| 3 | B | B 子组 {2,3} | **隔离** | 与 B 子组最小 ordinal 同 hash |

⇒ **隔离 1 行（ordinal 3），保留 2 行（ordinal 1、2）。**

#### ② `B,A,B`（同一组，仅文件顺序不同）→ **隔离 1 行，与 ① 逐位相同**

| 步 | 动作 | 结果 |
|---|---|---|
| 1 | 按 `(hash ASC, raw_record_index ASC)` 定序 | **同 ①**：`A`→1；两个 `B` 按 `raw_record_index` 破并列 → 2、3 |
| 2 | 分组 | A 子组 {1}；B 子组 {2,3} |
| 3 | 各子组内最小保留、后续同 hash 隔离 | 隔离 ordinal 3 |
| 4 | **隔离** | **1 行** |

> **① 与 ② 结果逐位相同** ⇒ 这正是 P1-01 的目标：**ordinal 不受行序影响**。物理顺序只在 `content_hash` 相等时经 `raw_record_index` 破并列，而并列行内容不可区分 ⇒ 无语义影响。

#### ③ `A,A,B,B`（4 行：A ×2，B ×2）→ **隔离 2 行** ⭐

| ordinal | hash | 所属子组 | 处置 | 依据 |
|---:|---|---|---|---|
| 1 | A | A 子组 {1,2} | **保留** | 子组内最小 ordinal |
| 2 | A | A 子组 {1,2} | **隔离** | 与子组最小 ordinal 同 hash |
| 3 | B | B 子组 {3,4} | **保留** | 与 A **不同 hash** ⇒ 不因跨组而被隔离；且是 B 子组最小 ordinal |
| 4 | B | B 子组 {3,4} | **隔离** | 与 B 子组最小 ordinal 同 hash |

⇒ **隔离 2 行（ordinal 2、4），保留 2 行（ordinal 1、3）。**

> ⭐ **易错点（本条经 team-lead 裁定更正，V-9 由"待确认"改为"已裁定"）**：
> 「不同 hash 记录均保留」指的是**跨子组**——B 组不会因为与 A 组 hash 不同而被隔离（这正是旧规则"只比 `ordinal=1` 的 hash"会误伤的地方）。
> 但**子组内部仍要执行"最小保留、后续隔离"**：B 出现两次，第二次**照样要隔离**。否则 `A,A,B,B` 里两个内容相同的 B 会同时入库，**去重就失效了**。
> 裁定依据：Owner r3 任务书 **P0-03**——「每个相同 hash 子组：最小 ordinal 保留，后续相同 hash 记录隔离」「**不得仅比较 `ordinal=1` 的 hash**」。
> 我先前写的"只隔离第二个 A，两个 B 都保留"**是错的**，它等价于被明令禁止的旧规则，已更正。

#### ④ `A,B,C`（3 行：三个不同 hash）→ **隔离 0 行**

三个子组各 1 行 ⇒ 无"后续同 hash"可隔离 ⇒ **3 行全部入库**。

#### ⑤ 真实父级分组核验（Pleiades connection `external_id=20469`）

| 四段前缀（dataset / scope / parent / external_id） | 行数与内容 | 处置 |
|---|---|---|
| `pleiades_gis_4_1_slice / edge / 98909 / 20469` | 2 行，hash 均为 A | ordinal 1 保留；ordinal 2（`sr_0027175`）隔离 |
| `pleiades_gis_4_1_slice / edge / 98930 / 20469` | 1 行，hash 为 B | 独立组，保留 |

⇒ 隔离 **1 行**（`sr_0027175`）。这不是一个 `A,A,B` 三行混合组：第三行属于另一个 `parent_external_id`。本例用于验证 **`parent_external_id` 必须参与四段前缀**，不能跨父级合并。组内 `A,A,B` 的一般规则由上面的排列推演覆盖。

**四种排列汇总（裁定后）**：

| 排列 | 排序后 | 保留 | 隔离 | 隔离数 |
|---|---|---|---|---:|
| `A,B,B` | A,B,B | 1(A)、2(B) | 3(B) | **1** |
| `B,A,B` | A,B,B | 1(A)、2(B) | 3(B) | **1** |
| `A,B,C` | A,B,C | 全部 | — | **0** |
| `A,A,B,B` | A,A,B,B | 1(A)、3(B) | 2(A)、4(B) | **2** |
| `A,A,B`（示意组） | A,A,B | 1(A)、3(B) | 2(A) | **1** |

### 5.3 相同 hash 数量增减的情形

| 变化 | 定序后 | 隔离 | 说明 |
|---|---|---|---|
| `A,A` → `A,A,A`（同 hash +1） | `A`1、`A`2、`A`3 | **2 行**（ordinal 2、3） | 同 hash 子组内只保留最小 ordinal |
| `A,A,A` → `A,A`（同 hash −1） | `A`1、`A`2 | **1 行**（ordinal 2） | 同上 |
| `A,A,B` → `A,A,B,B` | `A`1、`A`2、`B`3、`B`4 | **2 行**（ordinal 2、4） | A、B 两个相同 hash 子组都各自保留最小 ordinal，后续副本隔离 |
| `A,A,B` → `A,B`（一个 `A` 消失） | `A`1、`B`2 | **0 行** | 剩余行 ordinal → 1、2；若已是 `duplicate_quarantine` 保持，否则置 `source_absent`（**不删行**） |
| `A` → `A,A`（组 1 → 2） | `A`1、`A`2 | **1 行** | 原先 `ordinal=0`（唯一组）的两行现在变成 1、2 |

> **跨版本不可稳定的部分**：同 hash 子组**内部**的 ordinal 由 `raw_record_index` 破并列 ⇒ 跨版本可能变化。但**内容不可区分 ⇒ 无语义影响**（V0.2.1 §2.1.5 已证）。

### 5.4 隔离不是删除

```
写入/更新 source_record：
    is_active            = false
    inactive_reason      = 'duplicate_quarantine'
    inactive_at          = now()
    inactive_in_batch_id = :batch_id
落 data_quality_issue(issue_type='duplicate_external_id', severity='warning',
                      action_taken='preserved_and_flagged', ...)
不派生 historical_place / location / name / candidate
```

- **不删行**；`inactive_reason` + `inactive_at` + `inactive_in_batch_id`（C21/C22）完整保留；
- **先于** O1 的普通派生（覆盖 V0.2.1 判定表第 8/9 行的 O1 分支）；
- **不得**通过 O7 解除人工保护恢复——恢复**只能**由下一批 O1 重算自动解除；
- `duplicate_quarantine` 是**每批重算的派生结论**，不是一次性的置位。

### 5.5 每批必做的比对（导入器第 0 步，先于任何写入）

```
对每个五段键的四段前缀 g（= dataset_id, record_scope, parent_external_id, external_id）：
  old_set = multiset(content_hash)  -- 库中现有行的 content_hash 多重集
  new_set = multiset(content_hash)  -- 本批解析得到的 content_hash 多重集
  比对 old_set 与 new_set → 按 §8 五表处置（自动 / STOP_AUTO）
```

> 隔离判据（§5.1）与本节的多重集比对是**同一个机制**：组内 `content_hash` 多重集既决定谁被隔离，也决定谁能自动更新。**一处实现，两处语义**，不新增代码路径。

### 5.6 真实数据落点

- 本轮隔离 **3 条**：`sr_0004941`（CHGIS `35000` 组）、`sr_0004942`（`35001` 组）、`sr_0027175`（Pleiades edge `98909/20469`）；
- 前 2 条**不派生子行** ⇒ 这正是 `47,503 → 47,499`（−4）与 `18,103 → 18,101`（−2）的来源；
- 第 3 条是 `edge`，本就不参与建点与时间聚合；
- 闭合校验：`record_scope='place'` 18,398 − 2 = **18,396** = 19,039 − 643（MCGD 按组创建）✓；
- 内容**不同**的 4 组（8 行）ordinal 分别为 1 和 2、**都不隔离**——这是 §8 ④「内容交换」与 STOP_AUTO 的真实场景，不是假想用例。

---

## 6. 判定表（11 行 × 7 列）+ 七类操作拦截

### 6.1 第 0 行：重复检测优先（**先于其余全部 10 行**）

| # | 判定 | O1 导入新增 | O2 更新 | O3 源端消失 | O4 批次失效 | O5 回滚 | O6 合并 | O7 解除保护后重导 |
|---|---|---|---|---|---|---|---|---|
| **0** | **本行属于"完全重复副本"**（同**五段键的四段前缀**（含 `parent_external_id`）下，存在另一行 `content_hash` 相同且 `duplicate_ordinal` 更小） | **QUARANTINE**：`is_active=false`, `inactive_reason='duplicate_quarantine'`, **不派生任何子行** | 同左 | SKIP_ROW（已是隔离态） | — | **SKIP_ROW**，不计任何计数 | 不适用 | **重新执行重复检测**；仍重复 ⇒ 保持隔离，**不得复活** |
（V0.2.2 §2.3.1）

**第 0 行的语义**：`duplicate_quarantine` 是**每批重算的派生结论**。因此它：
- **先于** O1 的普通派生（V0.2.1 判定表第 8/9 行被它覆盖）；
- **先于** O7 的 WRITE——**不得**通过解除人工保护恢复。

### 6.2 其余 10 行（V0.2.1 判定表，第 8 行的 O1 分支已被第 0 行改写）

| # | 判定 | 处置要点 |
|---|---|---|
| 1 | 目标行 `locked` | SKIP_ROW + `blocked_count+1`（判定表第 4 行） |
| 2 | 目标行有 `manual_edited_fields` | **KEEP_MANUAL** + 台账 `manual_edit_conflict`（第 5 行） |
| 3 | 目标行是 `merged` 墓碑 | SKIP_ROW（`merged_tombstone`） |
| 4 | 目标行 `created_by='manual'` | SKIP_ROW（`manual_created`） |
| 5 | 身份列（`place_id`/`source_record_id`/`created_at` 等） | KEEP（identity_column） |
| 6 | 键不存在 | INSERT + 派生全部子行 |
| 7 | 键存在，`content_hash` 相同 | 只更新 `last_batch_id` |
| 8 | 键存在，哈希不同 | **若当前 `inactive_reason='duplicate_quarantine'` 且仍重复 ⇒ `SKIP_ROW(quarantine_hold)`**；否则按 `should_write()` 更新 |
| 9 | 键存在，哈希不同，整行冻结 | 不改数据 + 台账，`failed += 1` |
| 10 | 派生失败 | 整批 `failed` |

> **第 8 行是第 0 行的落点**：第 0 行命中时，第 8 行的 O1 分支**不执行**。这正是 Owner 点出的冲突点（"一边规定 INSERT 不派生、一边又被 O1 普通派生规则覆盖"）。

### 6.3 七类操作与第 0 行**不得冲突**

| 操作 | 与第 0 行的关系 |
|---|---|
| **O1 导入新增** | 第 0 行先判；命中 ⇒ QUARANTINE，**不派生任何子行** |
| **O2 更新** | 同左 |
| **O3 源端消失** | 已是隔离态 ⇒ SKIP_ROW |
| **O4 批次失效** | 不适用 |
| **O5 回滚** | **SKIP_ROW，不计任何计数**（隔离行从未派生对象，回滚它没有语义，且会破坏"保留原始记录"） |
| **O6 合并** | 不适用 |
| **O7 解除保护后重导** | **重新执行重复检测**；仍重复 ⇒ 保持隔离 |

七条要求的落点对照（V0.2.2 §2.3.2）：

| # | Owner 要求 | 落点 |
|---|---|---|
| 1 | 完全重复的记录不得派生 place / name / location / candidate | 第 0 行 `不派生任何子行` |
| 2 | `duplicate_quarantine` 不得通过解除人工保护恢复 | O7 第 0 行；恢复只能由下批 O1 重算解除 |
| 3 | O1、O7 必须重新执行重复检测 | 第 0 行对 O1/O7 均标注"重新执行重复检测" |
| 4 | 重复隔离状态不能被普通 upsert 覆盖 | 第 0 行位于第 8 行之前 |
| 5 | 已隔离记录必须保留原始记录和隔离原因 | 不删行；`inactive_reason` + `inactive_at` + `inactive_in_batch_id`（C21/C22）完整保留 |
| 6 | 重新导入后仍满足完全重复条件的记录继续隔离 | 第 0 行 O1：仍重复 ⇒ 继续隔离（保持，不是"重新插入再隔离"） |
| 7 | 重复关系变化时须重新判定 | 隔离状态每批由第 0 行重算；组内 `content_hash` 多重集变化即触发重判 |

---

## 7. 回滚与人工保护

### 7.1 `should_write()`：唯一的写入判定（三处共用）

**被 upsert（§6）、回滚（§7）、人工解除保护后重导三处调用，必须是同一份实现。**

```
def should_write(entity, field, new_value) -> Decision:
    # 1. 墓碑优先于一切
    if entity.merged_into_place_id is not None:
        return SKIP_ROW('merged_tombstone')
    # 2. 整行冻结
    if entity.locked:
        return SKIP_ROW('row_locked')
    # 3. 人工创建的行永不被导入改写
    if entity.created_by == 'manual':
        return SKIP_ROW('manual_created')
    # 4. 字段级冻结
    if field in entity.manual_edited_fields:
        return KEEP_MANUAL('field_edited')
    # 5. 身份列永不被导入器改写
    if field in ('place_id','location_id','name_id','source_record_id','created_at','created_by'):
        return KEEP('identity_column')
    return WRITE(new_value)
```

**第 1 条必须排在最前**：`merged` 的行不一定 `locked`。若把 `merged` 判定放在 `locked` 之后，一个被合并的地点在源更新时会被直接改写墓碑行的字段，而 `merged_into_place_id` 保持不变 ⇒ 行仍是墓碑但内容已变，且读路径 `COALESCE(merged_into_place_id, place_id)` 会把它解析到目标地点 ⇒ **用户看到目标地点的名字配上被改写的内容，没有任何报错**。

### 7.2 判定表第 3 / 4 / 5 行的记账

```
issue_type      = 'manual_edit_conflict'
severity        = 'info'
field_name      = <第一个被挡住的字段名>；整行/墓碑时为 ''
observed_value  = '旧值 → 新值'（截断到 200 字符）
expected_rule   = 'import would have overwritten a manually edited field'
action_taken    = 'needs_manual_review'
```

- **不做静默跳过**——静默跳过会让"源已经修正、我们没跟进"变成不可见状态，台账是唯一的发现渠道；
- **粒度**：一条源记录一次导入最多记一条 `manual_edit_conflict`（唯一索引 `(source_record_id, issue_type, field_name)`）。若一条记录有 3 个字段被挡，记 3 行。

### 7.3 `rejected_by`：自动失效 vs 人工拒绝

| `rejected_by` | 产生 | 源端恢复后 | 导入器可否改 |
|---|---|---|---|
| `'auto'` | 源记录失效（O3/O4）时自动置 | **恢复 `staging`**，`rejected_by` 清 NULL | 可以（自动恢复） |
| `'manual'` | 人工拒绝（判定表第 5 行 / 场景 A） | **保持 `rejected`**，落 1 条 `manual_edit_conflict` 提示人工复核 | ⛔ **永远不可以** |

> ⛔ **明确禁止**：不得"把所有 rejected 子行恢复成 staging"来绕过本条——那会一次性抹掉所有人工拒绝，正是本条要防的。
> 没有 `rejected_by` 就无法区分两者，导入器只能在"恢复所有 rejected 子行"（覆盖人工决定）与"一个都不恢复"（合法数据永久丢失）之间二选一。**这不是"多存一列方便查询"，是规则可执行性的前提。**

**四组场景**（CORE §5.6.1）：

| 场景 | 触发 | 子行 `auto` | 子行 `manual` | 地点 |
|---|---|---|---|---|
| **A** | 源仍 active，子行被人工拒 | — | 置 `rejected`+`manual`；该证据**无效** | 若仍有其他有效证据 ⇒ 不变；否则 `liveness∈FAILURE_SET` + `rejected`。**不落台账** |
| **B** | 源 `source_absent` 失效 | 置 `rejected`+`auto` | — | 若 ∃ 其他有效证据 ⇒ 保持；否则 `all_sources_absent` + `rejected` |
| **C** | 源重新出现（O1/O7 复活） | **恢复 `staging`** | **保持 `rejected`** + 台账 | 若 ∃ 有效证据 ⇒ `'staging'`（不新建） |
| **D** | 源端重新导入 | 源已恢复 ⇒ 恢复 | **保持 rejected** | — |

### 7.4 回滚统计口径（R1 / R2 / R2b / R2c）

本节只保留导入规则侧的统计索引；**唯一完整定义、集合边界和判定顺序见 `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md` §3 / §5**，不得在两份文件中维护两套状态机。

记号固定：`:R` = 被回滚批次；`:Rb` = 回滚批次（`rollback_of_batch_id = :R`）。导入期写入失败为 `N_fail_import`；回滚期 UPDATE 失败为 `N_fail_rb`，两者不得混用。

回滚期恒等式：

```text
N_new    = N_quar + N_normal
N_normal = N_rolled_back + N_blocked + N_fail_rb + N_noop
```

断言（`:R` 仅用于被回滚批的源记录；回滚期台账统一记在 `:Rb`）：

```sql
R1   count(source_record
           WHERE inactive_in_batch_id = :R
             AND inactive_reason = 'batch_rolled_back')
     == N_normal - N_noop - N_blocked - N_fail_rb

R2   count(data_quality_issue
           WHERE batch_id = :Rb
             AND issue_type IN ('rollback_conflict','manual_edit_conflict'))
     == N_blocked

R2b  count(data_quality_issue
           WHERE batch_id = :Rb
             AND issue_type NOT IN ('rollback_conflict','manual_edit_conflict')) >= 0

R2c  count(data_quality_issue
           WHERE batch_id = :Rb
             AND issue_type = 'import_row_error') == N_fail_rb
```

`R2c` 为**结构断言 + 未验证**：当前暂存原始 12,631 条台账中 `import_row_error` 为 0 行，且尚无真实回滚批次可代入；必须在施工阶段用影子回滚批验证。R1/R2/R2b/R2c 的完整说明及反例见回滚文件，不得在此另行改写。

---

## 8. STOP_AUTO（ordinal 跨版本变化的工程策略）

**总原则**：`duplicate_ordinal` 是**内容的函数**，不是身份。真正需要保护的是 **"`source_record_id` 绑定了哪份内容"**。

### 8.1 五种变化的表（自动 / 停止二分）

| # | 变化 | 检测 | 可自动？ | 处置 |
|---|---|---|---|---|
| ① | 组内**一条**内容变化 | `\|old\| = \|new\|` 且 `\|old ∩ new\| = \|old\| − 1` | ✅ **自动** | 未变的那一行保持 `source_record_id` 与 ordinal；变的那一行**在同 `source_record_id` 上更新** `content_hash`/`raw_payload`/`last_batch_id`，ordinal 由算法重算 |
| ② | **新增**一条（组 2 → 3） | `new ⊃ old` 且 `\|new\| − \|old\| = 1` | ✅ **自动** | 新行 INSERT。已有行**默认不动**；**仅当**新增行的 `content_hash` 在 `(content_hash ASC, raw_record_index ASC)` 全序中落在两个既有行之间、且该插入导致既有行的 ordinal 不再等于其全序位次 ⇒ **只重排受影响的既有行** |
| ③ | **删除**一条（组 2 → 1） | `old ⊃ new` 且 `\|old\| − \|new\| = 1` | ✅ **自动** | 剩余行 ordinal → 0；消失的那一行：若已是 `duplicate_quarantine` ⇒ 保持；否则置 `source_absent`（**不删行**） |
| ④ | **两条内容交换** | `old_set = new_set`（多重集完全相同） | ✅ **无需处理** | 见 §8.2 |
| ⑤ | **同 hash 数量变化**（3 → 4 条同哈希） | 同哈希行的基数变化 | ✅ **自动** | 按 ② / ③ 处理；同哈希内部 ordinal 由 `raw_record_index` 破并列 ⇒ **跨版本不可稳定，但内容不可区分 ⇒ 无语义影响** |

### 8.2 ④ 的补充：显式接受的不可观测性

多重集不变**不代表绑定未变**——组内两行内容互换时，`source_record_id → content` 的绑定**恰恰翻转了**，只是因为定序键是 `content_hash`，翻转后 ordinal→内容映射与翻转前**逐位相同**，所以**不可观测**。

- 本设计**显式接受**这一不可观测性——内容相同 ⇒ 两条记录的所有语义字段相同 ⇒ 谁绑定到谁不产生任何下游差异；
- 因此 ④ **不构成台账事件**（不落 `duplicate_external_id`，不触发 `STOP_AUTO`）；
- `STOP_AUTO` 判据在**真交换**时**不触发**（交集 = `\|old\|`），这是**有意为之**，不是漏判。

### 8.3 STOP_AUTO 判据与实现（**不加新表、不加新列**）

```
若 |old| = |new| 且 |old ∩ new| < |old| − 1
   ⇒ 有 ≥2 条同时变化，无法把新旧内容一一对应
   ⇒ 停止自动更新（STOP_AUTO）
```
其他无法唯一对应的情形（如 `\|old\|=\|new\|` 但多重集交集更小）同理。

实现：

1. 该组**整组 `SKIP_UPDATE`**：本批不修改任何已有行的 `content_hash` / ordinal；
2. 落 **1 条 `duplicate_external_id`** 台账（**复用既有类型，不新增枚举值**），`observed_value` 写明 `old_multiset` 与 `new_multiset`，`notes` 写明"ordinal 无法唯一对应，等待人工核验"；
3. 每次导入重判；仍无法对应 ⇒ 再次 `SKIP_UPDATE` + 台账（`occurrence_count += 1`）。

### 8.4 三条硬禁止与两条硬保留

**禁止**：
1. ⛔ 不得仅因重排后的 ordinal 不同而静默更新旧 `source_record` 的内容（那会把 A 的内容写到 B 的身份上）；
2. ⛔ 不得把原 `source_record_id` 自动绑定到另一条不同内容的记录；
3. ⛔ 不得删除旧行（③ 也是置 `source_absent`，不是删）。

**保留**：
1. 原始数据：`raw_payload_json` 逐字保留（IDENTITY / 可追溯要求）；
2. 既有身份关系：**`source_record_id`、`created_from_source_record_id`、`duplicate_ordinal` 在 `STOP_AUTO` 期间一律不动**。

---

## 9. MCGD 的按组装配

| 项 | 规则 |
|---|---|
| `place_grain` | **`per_parent_external_id`**（`CORE_DATA_MODEL_V2.1.md:154`） |
| `record_scope` | **`name`**（不是 `place`——MCGD 一行 = 一个 `NameID` + 一个 `LocID`） |
| 建点 | 按 **`parent_external_id`（`LocID`）** 成组 ⇒ **960 条 name 记录 → 643 个地点** |
| canonical | **最小 `NameID`（`external_id` 字典序最小）** 的那条记录 |
| 锚点 | `created_from_source_record_id` = 最小 `NameID` 的那条 `source_record` |
| 证据角色 | 该记录同时是 **`creator`** 与 **`name`**（创建地点靠白名单 ②） |

**为什么 canonical 必须指定"NameID 最小"而不是"任取一条"**：若两处各取各的，会出现"地点名来自 A 行、证据来自 B 行"——B 行换了数据集时，名称与证据就脱钩了。**同一地点的一条记录必须同时承担名称与证据两个职责，否则它们可以不一致。**

> **真实断点**：暂存 `historical_places.csv` 的 `primary_external_id`，MCGD 的 643 行填的是 `LocID`（`D` 前缀），而 `source_records.csv` 的 `external_id` 是 `NameID` ⇒ **643 个地点（3.4%）用 `primary_external_id` 完全 join 不上任何源记录**。`primary_external_id` 判定为"装配辅助列"，**不做归属依据**；归属一律走 `created_from_source_record_id`。

---

## 10. canonical 计算（`is_canonical_row`）

### 10.1 统一外层定序（写死，**6 键**，与 CORE §5.10.4 逐字一致）

```
is_canonical_row ⇔ 该行是本地点证据集中定序第一的行
实现位置：CORE §5.10.1 / `DATA_PROVENANCE_V2.1.1` §7.1 视图的外层窗口函数
          row_number() OVER (PARTITION BY place_id ORDER BY …) = 1

排序键（写死，顺序不可换）：
   ⓿ (source_is_active IS TRUE AND child_record_status IS DISTINCT FROM 'rejected') DESC
                                                  -- 有效证据优先；NULL 源活性不算有效（§10.1 下文定义）
  ① (evidence_role = 'creator') DESC             -- 创建记录优先
  ② sr.duplicate_ordinal ASC NULLS LAST          -- 与 §3.3（= CORE §4.3）同源（回连 source_record 取值）
  ③ sr.external_id       ASC NULLS LAST          -- MCGD 即"NameID 最小"（回连 source_record 取值）
  ④ source_record_id     ASC                     -- 破并列（可复现）
  ⑤ coalesce(child_row_id, 0) ASC                -- 同记录多行 name 的行级破并列（可复现）
```

> ⛔ **②③ 必须回连 `source_record`**：`duplicate_ordinal` / `external_id` **不是** `v_place_evidence` 的列（该视图只有 11 列）。任何"在视图内直接 `ORDER BY` 这两列"的写法都**不可执行**。键表达式与 CORE §5.10.4 **逐字相同**，仅 ② 的节号指针本地化为 `§3.3`（CORE 对应节为 §4.3）。
> ⛔ **⓿ 不可省略**：定义句是"**证据集**中定序第一的行"，而 ⓿ 把「有效证据」整体提到最前，使其在**存在有效证据时**必然落在有效证据内——这是 CORE §5.10.4 对定义句的落地方式。缺 ⓿ 时，一条 `rejected` 子行或失效源行可能排到有效证据之前成为 canonical ⇒ 定序与定义句自相矛盾。
> ⛔ **⑤ 不可省略**：C08 允许一条 `source_record` 派生最多 **3** 行 name（`name_type` 不同），其 ②③④ 键**全同**；缺 ⑤ 时并列行的 `row_number()` 取值**不可复现**（同输入两次查询结果可以不同）。

**有效证据**的唯一定义（视图、存活、时间三处共用）：
```
有效证据(e) ⇔ e.source_is_active IS TRUE
            AND e.child_record_status IS DISTINCT FROM 'rejected'
```
且 `child_rejected_by = 'manual'` 的行**永远不是有效证据**。

### 10.2 四条硬规则

1. **每个地点恰有一个 canonical**。定序 6 键整体唯一：①②③④ 可以全同（C08 允许一条 `source_record` 派生最多 3 行 name），此时由 ⑤ `coalesce(child_row_id,0)` 破并列；⑤ 是行级键，同一 `child_table` 内 `child_row_id` 唯一 ⇒ **不存在无解的并列**。又因每个地点的证据集**非空**（V3' 断言每地点恰有 1 条锚点 `creator` 行，见 §4.4）⇒ `row_number()=1` **必选出且只选出一行**，故"恰有一个"而非"至多一个"。
2. **「是否 canonical」与「是否有有效证据」是两件事，不得混为一谈**。零有效证据的地点（证据集里所有行都失效：`child_rejected_by='manual'` / 源失效），`row_number()=1` **仍会选出一行**（SQL 事实，不是可选行为）：该行 `is_canonical_row=true`，但它**不构成"有效证据"**——`is_canonical_row` 只回答"本地点最佳可得记录是哪条"（追溯用），「该地点是否还有有效证据」由本节上文的有效证据定义**单独回答**，二者可以一个为真、一个为假。此时该地点的 `liveness` 必属 `FAILURE_SET` 或 `orphaned`（CORE §5.10.2），与"存在 canonical 行"**不冲突**。⛔ **不得**表述为"全为 FALSE，不得回退任取一行"——那是与 SQL 事实相反的旧写法，已删除；⛔ 也**不得**把该 canonical 行当作"有效证据"用于任何存活 / 时间聚合判断。
3. **315 个无子行地点（入库口径）经 `creator` 证据追溯，不补造名称行**。其唯一有效证据就是 `creator` 行 ⇒ `is_canonical_row=true` 落在它身上，追溯通路为
   `place → v_place_evidence(creator, is_canonical_row) → source_record → raw_file + raw_record_index`，其值为 `raw_payload.title`。
   ⛔ **不需要也不允许制造名称子行**——新增 canonical 角色会与 `name`/`creator` 重复计数，直接破坏 `V2 = 315（入库口径）` 与 `V3' = 19,039（入库口径）` 的基数。
4. **锚点 ≠ 当前最佳证据**。二者指向不同记录**不是错误**，不落台账；`DATA_PROVENANCE` 必须写明这是设计选择。

| 概念 | 列 | 语义 | 是否随导入变 |
|---|---|---|---|
| **锚点** | `created_from_source_record_id` | 首次导入时的身份记录（IDENTITY，永不改写） | 否 |
| **当前最佳证据** | `v_place_evidence.is_canonical_row` | 每次导入重算 | 是 |

### 10.3 人工修改的保护

- `canonical_name` 被人工修改 ⇒ 该字段进入 `manual_edited_fields` ⇒ 导入器 **KEEP_MANUAL**，不覆盖；
- 此时 `is_canonical_row` **仍然指向源行**（用于追溯"这个地点本该叫什么、来自哪里"），显示值取人工值；
- UI / 文档必须能同时展示：显示名（可能人工）+ 源名（`is_canonical_row` 行的 `raw_payload`）+ 来源位置（`raw_file:raw_record_index`）。

### 10.4 各类地点的落点

| 地点类 | 数量（**入库口径**） | `is_canonical_row` 落在 |
|---|---:|---|
| 无子行（全部 Pleiades） | **315** | 唯一有效证据 = `creator` 行 |
| MCGD 按组建点 | **643** | 全部证据 `evidence_role='name'` ⇒ 定序落到 `external_id` = 最小 `NameID` ✓ |
| CHGIS | 15,746 | `creator` 优先 ⇒ 与 `places.csv` 的 `title` 同源 ✓ |

> **待验项**：`is_canonical_row` 与暂存 `canonical_name` **是否逐行相等**尚未验证 ⇒ 见 §12 V-2。

---

## 11. 一页速查：一次导入的完整流程

```
P0  前置校验 §2（8 项，任一不过 ⇒ 整批拒绝/失败）
P1  逐行派生 §3：record_scope / parent_external_id / duplicate_ordinal / content_hash
      ⛔ 派生失败 ⇒ 整批 failed，不兜底
P2  重复检测 §5（导入器第 0 步，先于任何写入）
      对四段前缀比对 old/new 的 content_hash 多重集
      ⇒ 按 §8 五表处置；无法一一对应 ⇒ STOP_AUTO
P3  写 source_record（含 QUARANTINE 行，不删行）
P4  建点 §4（白名单 + place_grain；place-scope 优先）
P5  派生 historical_place_name / location
P6  派生 candidate_match（隔离行不派生任何候选）
P7  计算 is_canonical_row §10
P8  upsert §6（第 0 行优先，should_write() 三处共用）
P9  落 data_quality_issue + 断言 A1–A9 + 收尾 batch.status
```

---

## 12. 施工验证清单（**不得写成 PASS**）

> **本附录每一项状态都是「未验证 / 未解决」。本文件不宣布通过，也不为任何一项预置通过结论。**
> QA 阶段二累计计数（V0.2.2_QA_VERIFICATION.md 行 704）：**PASS 35 / FAIL 1 / WARN 12 / 未验证 13 —— 存在 FAIL，不宣布通过。**

### 12.1 V0.2.2 §5.3 未解决 / 未验证清单（如实保留）

| # | 项 | 何时解决 |
|---|---|---|
| **U3** | `v_place_evidence` 的 V1–V3 | 建库后首次导入 |
| **U4** | `v_place_time_span` 的 V1–V3、T1–T5 | 同上 |
| **U5** | **七类操作（含判定表第 0 行）能否真正拦住** | 施工后造 7 个测试批次 |
| **U12** | `v_place_time_span` 加 `sr.is_active` 后 17,469 的变化 | 建视图后复算 |
| **U13** | `rejected_by` 两列是否误伤既有写入路径 | 建库后空跑导入 |
| **U14** | 四场景 A–D 的端到端行为（暂存 0 条 rejected/merged/locked，无数据可验） | 施工后造影子批 |
| **U15** | `STOP_AUTO` 的真实触发率（当前 0 例，需内容变更的源版本） | 下一次源更新 |
| **U16** | `raw_record_index` 的真实语义（是"每文件计数器重新计数"，还是 WHG 抽取时的多文件合并残留？）实测**不是**文件内 1-based 唯一编号 | 下一轮；本轮只做"使用限制" |
| **U18** | `candidate_match` 总数（暂存 53,137 / 隔离后 53,103 vs V0.2.1 的 53,133） | **需 Owner / team-lead 裁定** |
| **U19** | `issue_fingerprint` 是否同步改为 sha256 | **已裁定：保持 md5**（ALG-1） |

### 12.2 本文件新增待验项

| # | 项 | 说明 |
|---|---|---|
| **V-1** | `v_place_liveness` 的 SELECT 补全是否正确 | V0.2.2-r2 §2.2.4 用 `...` 省略；CORE §5.10.2 的对外列清单属**补全项**，待 QA 复算 |
| **V-2** | `is_canonical_row` 与暂存 `canonical_name` 是否逐行相等 | 315 无子行（入库口径）/ MCGD 643 / CHGIS 三类落点需逐行核对。**本轮 §10.1 已把定序补全为 6 键**（与 CORE §5.10.4 逐字一致，新增 ⓿ 有效证据优先 + ⑤ `coalesce(child_row_id,0)`），补全后需按 6 键复算：① 315 无子行地点的 canonical 是否全落在 `creator` 行；② MCGD 643 是否落到最小 `NameID`；③ 同记录多行 name 时 `row_number()` 取值是否**确定性唯一**（同输入两次查询结果必须相同）。对应 CORE 附录 B **V-8**，**均未验证** |
| **V-5** | `parent_external_id` 按新哨兵规则复算 | 可派生 **10,765**／落哨兵 **18,626**／相对 C29② 缺口 **2,878**；⛔ `whg_geom_index` 3 行**可派生，不得计入缺口**。属补全项，待 QA 复算 |
| **V-6** | `data_quality_issue` 中 6 行空 `source_record_id` 的 `dataset_id` 来源 | 暂存无 `raw_file`/`dataset_id` 列；这 6 行无回溯通路。裁定"标 `derived` 推断"还是"整批 failed" |
| **V-7** | `external_id_type` 实测 **11 种** vs V2.1 notes 的 16 种 | 16 是**映射行数**不是类型数；需 QA 扫交付物确认无残留 |
| **V-10** | **`import_batch.quarantined_count` 的期望值断言** | 本版 §1.3 A4 基线表已把 V2.1 的 `quarantined = 2` 更正为 **3**（补 Pleiades edge `sr_0027175`）。连带影响：`A6 batch.quarantined_count == count(source_record WHERE first_batch_id=:b AND NOT is_active)` 的期望值必须是 **3**，且 CORE §9.2 N02「`is_active=false` = 3」必须与之一致 ⇒ **单列本条，防止静默错位** |
| **V-8** | 第 0 行与七类操作的实际拦截效果 | §6.3 的对照表是**结构推演**；U5 造 7 个测试批次后才能验 |
| ~~**V-9**~~ | §5.2 四种排列推演 | **已裁定**（team-lead）：**每个相同 hash 子组内**最小 ordinal 保留、后续同 hash 隔离；「不同 hash 均保留」仅指**跨子组**不互相隔离。⇒ `A,B,B` 隔离 **1**、`B,A,B` 隔离 **1**、`A,B,C` 隔离 **0**、`A,A,B,B` 隔离 **2**（不是 1）。我先前写的「`A,A,B,B` 只隔离第二个 A」**是错的**（等价于被明令禁止的旧规则：只比 `ordinal=1` 的 hash），已更正。依据：Owner r3 任务书 P0-03。**仍建议施工后实跑确认**（属结构推演，非真实数据复算） |

---

## 13. 两条施工级硬提醒（写进交付物正文）

### H1｜`normalize.py:306` 一旦改动必须回归 `content_hash`

```
normalize.py:306 是本系统 content_hash 等价性的唯一支点。
该行保持 sort_keys=True, ensure_ascii=False, separators=(",",":") 时，
  逐字节形式 与 规范化表达式 等价（实测 29,391/29,391 逐字节相等，R30）。
该行一旦被改动而不同步回归：
  ⇒ 29,391 条 content_hash 全部改变
  ⇒ duplicate_ordinal 大规模重排
  ⇒ STOP_AUTO 误触发 ⇒ 整批 SKIP_UPDATE
  ⇒ 【静默，不报错】
```

### H2｜`derivation_kind` / `no_evidence` 不得直读暂存 `valid_from/to_year_astro`

```
计数必须基于「只聚合 name + location、排除 connection」的重算结果。
暂存 historical_places.valid_from_year_astro / valid_to_year_astro 由含 connection 的
旧口径生成 ⇒ 直接引用会使 no_evidence 系统性偏低 65（1,505 vs 1,570）。
```

---

> **V2.1.1 到此结束。本版只出导入规则，不含任何数据库施工。架构师不代替独立复核员与 QA 宣布通过——§12 的每一项需在施工阶段逐条关闭。**
