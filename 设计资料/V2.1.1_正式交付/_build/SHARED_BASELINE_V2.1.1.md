# SHARED_BASELINE_V2.1.1 · 共享定义基线

> **本文件仅作为内部编制时的统一参考，不是独立设计来源，不得凌驾于 V0.2.2-r2。凡本文件与 V0.2.2-r2 冲突，一律以 V0.2.2-r2 为准。本文件不参与八份交付物计数。**

---

## 0. 本文件的性质与用法

| 项 | 说明 |
|---|---|
| 用途 | 把 V0.2.2-r2 散落在各章节的**定式、枚举、计数、约束**抄录到一处，供八份交付物编制时**逐条取用**，避免同一事实在多份文档里出现多个写法 |
| 权威来源 | `V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md`（1,127 行，下称 **V0.2.2**）；`V2.1.1/V0.2.2/V0.2.1_TO_V0.2.2_CHANGELOG.md`（下称 **CHANGELOG**） |
| 判定"是否既有列/既有枚举"的依据 | `架构/CORE_DATA_MODEL_V2.md`（V2 基线）、`架构/V2.1/CORE_DATA_MODEL_V2.1.md`（V2.1 基线）、`架构/V2.1.1/00_PROBLEM_LIST_AND_PLAN.md`（V0.2.1 基线，V0.2.2 未覆盖处以它为准） |
| 效力顺序 | **V0.2.2 > V0.2.1 > V2.1 > V2** |
| 抄录纪律 | 每项均标注出处章节号 + 行号；**逐字抄录**，不改写、不归纳、不推断 |
| 未做的事 | 未写 DDL/Migration、未建库、未导入、未改任何基线文件、未改暂存 CSV、未改 `normalize.py`、未做 Git 操作 |

> **引用纪律（抄自 V0.2.2 §3.4，硬要求）**：八份交付物凡引用 V0.2.1 §2.1.4a / G1-02，必须同时标注 V0.2.2 §2.9 的更正（写明"V0.2.1 该处论证已撤销，理由见 V0.2.2 §2.9.1"），且不得单独转述 V0.2.1 的原文理由。

---

## 1. 业务键（五段自然键）

**出处：V0.2.2 §2.5.0（行 521–572）；§2.1.1 交叉引用（行 80）**

```
自然键 = (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)
```

```
C29  parent_external_id 为必需段：
     ① 任何情况下不得省略、不得以 NULL 兜底、不得用空串代替；
     ② 无父级概念的数据集（CHGIS place）写入哨兵值 '-'（不是 NULL），
        以保证 UNIQUE 仍然生效（Postgres 的 UNIQUE 对多列 NULL 不去重）；
     ③ 派生失败 ⇒ 整批 failed（与 A12 同一处置），不是默认放行；
     ④ 哨兵值约束（r2 新增，team-lead 裁定）：哨兵必须是 parent_external_id 值域之外的保留字，
        且只能在 data_dataset 或一张常量表里声明一次（不得散落在导入逻辑各处）。
        若将来某数据集的 parent 恰为 '-' ⇒ 换哨兵是一次性常量替换，不得牵动五段键逻辑。
```
（V0.2.2 行 527–534）

### 1.1 `parent_external_id` 的取值

| 数据源 | `parent_external_id` 来源 |
|---|---|
| Pleiades | `raw_payload.place_id` |
| MCGD | `raw_payload.LocID` |
| 无父级概念（CHGIS place 等） | 哨兵 `'-'`（**值域外保留字**，在常量表/`data_dataset` 声明一次） |

### 1.2 为什么不能用空串 / NULL

Postgres 的 `UNIQUE` 对多列 `NULL` **不去重** ⇒ 一旦 `parent_external_id` 为 NULL，五段键退化成四段键，重复检测失效。空串同理会与"真实空值"混淆。哨兵必须是值域外保留字（C29 ④）。

### 1.3 漏段的后果（真实数据，已验证）

| 分组口径 | 重复组数 | 涉及行数 | `ordinal=0` |
|---|---:|---:|---:|
| 三段键 `(dataset_id, external_id_type, external_id)`（**漏 parent**） | **398** | **2,335** | 27,056 |
| 五段键（含 `parent_external_id`） | **7** | **14** | **29,377** |

（V0.2.2 行 539–545）

> 差两个数量级。根因：Pleiades 的 `external_id` 在 dataset 内不唯一（connection 用 title 作 id；name 同理）。只有 `parent_external_id` 能区分。⇒ **静默数据损坏，不报错**。

### 1.4 真实数据的 7 组明细

| dataset | `external_id_type` | parent | `external_id` | n | 内容 | 处置 |
|---|---|---|---|---:|---|---|
| chgis_v6_prefecture_points | chgis_sys_id | — | 35000 | 2 | 相同 | 隔离 `sr_0004941`（ordinal **2**） |
| chgis_v6_prefecture_points | chgis_sys_id | — | 35001 | 2 | 相同 | 隔离 `sr_0004942`（ordinal **2**） |
| pleiades_gis_4_1_slice | pleiades_name_id | 92117 | argita | 2 | **不同** | ordinal 1,2 **均入库，不隔离** |
| pleiades_gis_4_1_slice | pleiades_name_id | 92153 | isamnion-akron | 2 | **不同** | 同上 |
| pleiades_gis_4_1_slice | pleiades_name_id | 92175 | ouidoua | 2 | **不同** | 同上 |
| pleiades_gis_4_1_slice | pleiades_name_id | 981506 | arabia | 2 | **不同** | 同上 |
| pleiades_gis_4_1_slice | pleiades_connection_id | 98909 | 20469 | 2 | 相同 | 隔离 `sr_0027175`（ordinal **2**） |

（V0.2.2 行 549–557）

---

## 2. `duplicate_ordinal` 规则

**出处：V0.2.2 §2.5.0（行 562–572）、§2.5.1（行 574–587）**

| 项 | 定式 |
|---|---|
| 单行组 | `duplicate_ordinal = 0` |
| 多行组（n ≥ 2） | 按 **`(content_hash ASC, raw_record_index ASC)`** 定序，取 **1..n** |
| `duplicate_ordinal` 语义 | **内容的函数**，不是身份（§2.5 总原则，行 519）。"ordinal 绑定了哪一行"没有语义；真正需要保护的是"`source_record_id` 绑定了哪份内容" |
| `raw_record_index` 的作用 | **只能**在 `content_hash` 完全相等时用于**打破并列**，不得参与常规定序（§2.5.5，行 619–623）。该字段**不保证文件内唯一**（14 个 `raw_file` 中 7 个不唯一，全为 WHG），不得作为定序键或唯一性依据 |

### 2.1 隔离判据（写死，§2.5.0 实现注意事项，行 562–564）

```
正确规则：组内按 (content_hash ASC, raw_record_index ASC) 定序后，
         同一 hash 子组内【最小 ordinal】保留；
         该子组内【后续相同 hash】的行 ⇒ 隔离；
         【不同 hash】的行 ⇒ 均保留（不隔离）。
```

⛔ **「只比较 `ordinal = 1` 的 hash」是 V0.2.2 §2.5.0 的历史写法，已被 Owner r3 / P0-03 裁定禁用**（此处仅作**【留痕】**）。

**关键约束（不得只比 ordinal = 1）**：

- **同一 hash 子组内最小 ordinal 保留**，后续相同 hash 的行隔离；
- **不同 hash 的行均保留**（不隔离）。

> **禁止"只比 `ordinal = 1`"**：像 `pleiades_connection_id / 20469` 这种**混合组**（3 行里 2 行相同、1 行不同），第一版脚本用"整组内容完全相同才隔离"会直接漏掉 `sr_0027175`。
> **禁止"要求整组内容完全相同"**：判定隔离时**不能**这样要求。

### 2.2 每批必做的比对（导入器第 0 步，先于任何写入）

```
对每个五段键的四段前缀 g（= dataset_id, record_scope, parent_external_id, external_id）：
  old_set = multiset(content_hash)  -- 库中现有行的 content_hash 多重集
  new_set = multiset(content_hash)  -- 本批解析得到的 content_hash 多重集
  比对 old_set 与 new_set → 按 §2.5.1 五表处置
```
（V0.2.2 行 566–572）

---

## 3. `content_hash` 主规范

**出处：V0.2.2 §2.5.6（行 625–643）、§3.4（行 929–936）；CHANGELOG D-03**

### 3.1 两行定式（三处逐字一致，交付物不得改写）

```
content_hash = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))   -- 规范定义（唯一）
sha256(raw_payload_json 逐字节)                                                                        -- 等价形式（当且仅当 normalize.py:306 约定不变时）
```
（V0.2.2 行 931–934）

- **规范化表达式是主规范**（r2 改定），**不是**逐字节版。理由（V0.2.2 行 629）：
  1. 逐字节版的稳定性依赖**上游 `normalize.py:306` 的一个约定**，不是自保证的——该行一旦被改（下一轮明确要动它，V0.2.1 遗留 `normalize.py:666` / `494–509` 污染地点级时间），逐字节版会让 29,391 条 `content_hash` **全部改变** ⇒ ordinal 大规模重排 ⇒ **STOP_AUTO 误触发、整批 SKIP_UPDATE**；
  2. P1-01 的目标是让 ordinal **不受行序影响**，而逐字节版让它**受序列化键序影响**——同一个问题的另一面；
  3. 当前数据上两者**完全等价**，改主规范**不改动任何一个已算出的数**（隔离 3 条、`N06 −4`、`N07 −2`、18,396、7 组 14 行全不变）。
- **等价条件必须标注**：逐字节形式**仅在 `normalize.py:306` 保持 `sort_keys=True, ensure_ascii=False, separators=(",",":")` 时等价**（已验证：暂存 29,391/29,391 行与该表达式输出逐字节相等，0 行不等；R30，V0.2.2 行 993）。**该约定一旦变动，等价性即失效。**

### 3.2 指纹（CIT-2′，可扫描）

| 对象 | 长度 | SHA1 |
|---|---:|---|
| **完整串（带算法外壳）** `sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))` | **85** | **`9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5`** |
| 辅助：内层 `json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':'))` | **77** | `781f68645c4e2e3af4b18871f2f5b7848c5f3798` |

（V0.2.2 行 923、927）

> 指纹取"**带算法外壳**"的完整串——因为 U17 的失败正是"只写表达式不写算法"。
> r1 的旧值 `len 82` / `7c3978b5…` 是 **md5 版**表达式的指纹，**已作废**。

### 3.3 摘要算法差异的影响范围（不得写成断言）

| 变体 | 摘要 | 换绑行数 | 翻转的组 |
|---|---|---:|---|
| 逐字节 | **sha256** | **6** | isamnion-akron / ouidoua / arabia |
| 等价表达式 | md5 | 4 | argita / isamnion-akron |
| 等价表达式 + `ensure_ascii=True` | md5 | 4 | 同 |
| 等价表达式 | sha256 | 6 | 同 |
| 默认分隔符（偏离规范） | md5 | 2 | ouidoua |

（V0.2.2 行 633–639）

- **唯一原因是摘要算法（md5 ↔ sha256）**，不是 `ensure_ascii` / `separators`。架构师先前"根因是 `ensure_ascii`"的猜测**已作废**。
- **不受影响的部分**：五种变体下"内容相同的组数"**都是 3 组** ⇒ 隔离条数 **3**、`N06 −4`、`N07 −2`、18,398 − 2 = **18,396** 全部不变。
- **该换绑行数不得写成断言**（NON-1，V0.2.2 行 1014）。要断言就断言**不变量 INV-1**：① 取值域 ⊆ {0,2,4,6,8}；② 上限 8；③ 新方案恒 0；④ 场景 A 下旧方案恒 0；⑤ 内容相同组数恒 3 ⇒ 隔离条数恒 3。

---

## 4. `issue_fingerprint`（及与 `content_hash` 的不可互换性）

**出处：V0.2.2 §2.5.7（行 647–657）；V0.2.1 §2.5.5（V2.1.1/00_PROBLEM_LIST_AND_PLAN.md 行 1289–1316）**

### 4.1 表达式

```
指纹 = md5(jsonb_build_array(source_record_id, dataset_id, place_id,
                             issue_type, field_name, observed_value)::text)
```
（V0.2.1 行 1293–1297；V0.2.2 §2.5.7 行 651）

- **六段**，`place_id` 是**必需段**（缺 `place_id` 则 197 条只剩 **45** 个不同指纹，24 组冲突 / 176 行）。
- **编码为 JSON 数组**（不用字符串拼接）：`null` / `""` / 含 `|` 的值三者互不相同。
- **不含 `batch_id`**：含 `batch_id` 会让每导一批新增 197 行（台账自我膨胀）。
- **空值不做 `coalesce` 归一**：`NULL` 与 `''` 必须保持可区分。
- **`observed_value` 口径**：暂存列原始字符串**单值**、空值渲染字面量 `NULL`、**重算值进 `notes`**（重算值进指纹会让每次修正聚合逻辑都新增 197 行）。
- 落库形式（V0.2.2 行 651）：`GENERATED ALWAYS AS md5(jsonb_build_array(...)::text) STORED`，由 **PostgreSQL 内算**。

### 4.2 两种摘要算法并存是**有意设计**，不可互换、不可统一（ALG-1）

```
content_hash       : sha256   -- 内容身份。导入器算。用于 ordinal 定序、跨版本稳定、重复隔离判定
issue_fingerprint  : md5      -- 台账去重键。PostgreSQL 内算
                              -- 用于识别"同一问题重复出现"，承载 first_batch_id / last_batch_id / occurrence_count
```
（V0.2.2 行 649–653）

> **本系统有意并存两种摘要算法，不得因"算法不一致"而擅自统一。**
> 理由：① `issue_fingerprint` 是 **V0.2.1 §2.5.1 已验收**的定义，197 条时间偏差台账的指纹**已按 md5 算好**并进入 V0.2.2 §0 权威数字——改算法会使这 197 条历史指纹**全部对不上**；② 两者**语义不同**（内容身份 / 台账去重）、**计算位置不同**（导入器 / PostgreSQL），算法不同不构成冲突；③ 改的成本（改 SQL、重算 197 条、台账历史断裂）> 收益（算法一致性这个纯审美收益）。
> **后人若提出统一，先问：197 条已算指纹怎么办？** 没有答案就不要动。

---

## 5. `record_scope` 四值

**出处：V0.2.2 §2.7.2（行 752–762）、A12（行 784）**

| 值 | CHGIS | Pleiades | MCGD | WHG | 合计 | 可否建点 |
|---|---:|---:|---:|---:|---:|---|
| `place` | 15,748 | 2,643 | — | 7 | **18,398** | ✅ ① 逐记录建点 |
| `name` | — | 4,579 | 960 | 223 | **5,762** | ✅ ② 仅 MCGD（`place_grain='per_parent_external_id'`） |
| `location` | — | 2,460 | — | 8 | **2,468** | ✅ ②（当前无数据集声明） |
| `edge` | — | 2,763 | — | — | **2,763** | ❌ 禁止 |
| **合计** | 15,748 | 12,445 | 960 | 238 | **29,391** | |

- **全域只有 4 种，无第五种**（R21）。
- **一律用 `edge`**，**不得混用 `connection`**【留痕：源端概念名】。`connection`【留痕：源端概念名】是 Pleiades 的**源端概念**，进入目标模型后统一记作 `edge`。
- **A12**：每个 `source_record` 的 `record_scope ∈ ('place','name','location','edge')`；出现第五种 ⇒ **整批 `failed`**（不默认放行）。

---

## 6. `evidence_role` 三值

**出处：V0.2.2 §2.6.1（行 663–676）**

| 值 | 含义 | 对应实体 | 真实数据规模 |
|---|---|---|---:|
| `creator` | 该源记录**参与创建**了这个地点（1:N，MCGD 就有 N>1） | `source_record`（经 §2.7 白名单） | place-scope 18,398 条；`is_anchor=true` 的行 = 19,039 行（每地点 1 条） |
| `name` | 该源记录派生了一条名称行 | `historical_place_name` | 47,503 条（入库 47,499） |
| `location` | 该源记录派生了一条位置行 | `historical_place_location` | 18,103 条（入库 18,101） |

- **统一为 3 值**：`creator` / `name` / `location`。
- **`place_record` 是禁用词**【留痕：禁用词清单】（与 `citation_text`【留痕】同级，进 QA 扫描）。V0.2.1 G4-01 第 3 点的 `role='place_record'`【留痕】一律改为 `creator`。
- 交付物（ER 图 / `CORE` / `IMPORT_RULES` / `DATA_PROVENANCE` / SQL）**只准出现 `creator`**。
- **为什么是 `creator` 而不是反过来**：`creator` 表达"这条记录做了什么"（参与创建），`place_record`【留痕：禁用词对照】表达"这条记录是什么类型"（易与 `record_scope='place'` 混淆，而 MCGD 的创建者恰恰是 `record_scope='name'` 的记录）。

### 6.1 各数据源对应的角色

| 数据源 | `record_scope` | 产生的 `evidence_role` | 条数 |
|---|---|---|---:|
| CHGIS pref / cnty | `place` | `creator`（并派生 `name` / `location`） | 15,748 |
| Pleiades places | `place` | **`creator`**（不派生子行） | 2,643 |
| Pleiades names | `name` | `name` | 4,579 |
| Pleiades locations | `location` | `location` | 2,460 |
| Pleiades connections | `edge` | **无**（不建点、不进证据） | 2,763 |
| MCGD names | `name` | **`creator`**（按 `grain_key` 成组）+ `name` | 960 → 643 地点 |
| WHG | place 7 / name 223 / location 8 | 对应角色 | 238 |

（V0.2.2 行 680–688）

---

## 7. `liveness` 8 值 × `record_status` 3 值 真值表

**出处：V0.2.2 §2.1.1（行 74–80）、§2.1.2（行 82–99）、§2.1.3（行 101–127）、§2.1.4（行 129–152）**

### 7.1 `historical_place.record_status`（3 值）

`staging` / `rejected` / `merged`。`rejected` 是**派生态**（由证据集合求出，不是人置位的）。

### 7.2 `v_place_liveness.liveness`（**8 值**，V0.2.1 为 7 值）

**派生优先级（自上而下，命中即返回，顺序不可换）**：

| 序 | 判据 | `liveness` | 类别 |
|---:|---|---|---|
| 1 | `record_status = 'merged'` | `merged` | **合并态** |
| 2 | `created_by = 'manual'` | `manual` | **有效态（永不失效）** |
| 3 | ∃ 有效证据（定义见 §2.2.3） | `active` | **有效态** |
| 4 | 证据全失效，且失效原因**唯一** = `source_absent` | `all_sources_absent` | **来源失效态** |
| 5 | 证据全失效，且失效原因**唯一** = `batch_rolled_back` | `all_sources_rolled_back` | **批次回滚态** |
| 6 | 证据全失效，且失效原因**唯一** = `duplicate_quarantine` | `quarantined_only` | **隔离态** |
| 7 | 证据全失效，且失效原因**≥2 种** | **`mixed_inactive`**（V0.2.2 新增） | **混合失效态** |
| 8 | 证据集为空，或存在失效但原因缺失 | `orphaned` | **孤立态（非法终态，断言 = 0）** |

### 7.3 真值表（✅ = 唯一合法组合）

| `liveness` | `staging` | `rejected` | `merged` | 判据 |
|---|---|---|---|---|
| `active` | ✅ | ❌ | ❌ | 有活性证据 ⇒ 不得被拒；合并需先使证据失效并经人操作 |
| `manual` | ✅ | ❌ | ❌ | 人工地点永不失效；**被合并后其 `liveness` 变为 `merged`，不再是 `manual`** |
| `merged` | ❌ | ❌ | ✅ | `record_status='merged'` ⇒ `liveness` 必为 `merged`（第 1 优先级） |
| `all_sources_absent` | ❌ | ✅ | ❌ | 失效态必须落到 `rejected` |
| `all_sources_rolled_back` | ❌ | ✅ | ❌ | 同上 |
| `quarantined_only` | ❌ | ✅ | ❌ | 同上 |
| `mixed_inactive` | ❌ | ✅ | ❌ | 同上 |
| `orphaned` | ❌ | ❌ | ❌ | **非法终态**，断言 = 0（**唯一允许 0 个 ✅ 的行**） |

**`(manual, merged)` 的取舍**：取 **(a) 删掉该 ✅**。
理由：§2.1.2 优先级**第 1 行**是 `record_status='merged' ⇒ liveness='merged'`，它在第 2 行 `created_by='manual'` **之前**命中，因此 `(manual, merged)` 这一格**永远不可达**——一个人工创建的地点被合并后，它的 `liveness` 是 `merged`，不是 `manual`。保留该 ✅ 会让表头"✅ = 唯一合法组合"自相矛盾，并**诱导实现者写出"先判 manual 再判 merged"的代码**（与本设计相反）。
不取 (b)：`rejected_by` 是**子表**列，地点表没有它 ⇒ 该例外在地点一级**无字段可判**，会变成无法实现的判据。
**信息是否丢失**：不丢失。"人工地点可被人工合并"由 `merged` 行表达；`manual` 行的语义退化为"人工创建且未被合并"。

### 7.4 `FAILURE_SET` 与双向等价

**记 `FAILURE_SET = {all_sources_absent, all_sources_rolled_back, quarantined_only, mixed_inactive}`。**

```
rejected ⟺ liveness ∈ FAILURE_SET
```

```sql
-- R4a  被拒必须可解释：rejected ⟹ liveness ∈ FAILURE_SET
R4a  count(historical_place
           WHERE record_status = 'rejected'
             AND liveness NOT IN ('all_sources_absent','all_sources_rolled_back',
                                  'quarantined_only','mixed_inactive'))                == 0

-- R4b  失效必须落到 rejected：liveness ∈ FAILURE_SET ⟹ rejected
R4b  count(historical_place
           WHERE liveness IN ('all_sources_absent','all_sources_rolled_back',
                              'quarantined_only','mixed_inactive')
             AND record_status <> 'rejected')                                           == 0

-- R4c  有活性证据的地点不得被拒
R4c  count(historical_place WHERE liveness = 'active'   AND record_status = 'rejected') == 0
R4d  count(historical_place WHERE liveness = 'manual'   AND record_status = 'rejected') == 0
R4e  count(historical_place WHERE liveness = 'merged'   AND record_status <> 'merged')  == 0
R4f  count(historical_place WHERE liveness = 'orphaned')                                == 0   -- 与 L4 同一条
```
（V0.2.2 行 131–149）

> V0.2.1 的 `R4 count(... AND liveness <> 'orphaned') == 0` **方向反了**，已废除。

### 7.5 "有效证据"的唯一定义（视图、存活、时间三处共用）

```
有效证据(e) ⇔ e.source_is_active                                  -- 源记录活性
            AND e.child_record_status IS DISTINCT FROM 'rejected'  -- 子行未被拒（creator 行为 NULL）
```
**且**：`child_rejected_by = 'manual'` 的行**永远不是有效证据**，且不参与任何自动恢复。
（V0.2.2 §2.2.3，行 222–233）

三条细则：
1. 子行存在但源记录失效 ⇒ 该子行不贡献存活。
2. `evidence_role` 只用于**解释**，不用于加权；`creator` / `name` / `location` 任一有有效证据即存活。
3. `merged` 与 `manual` 先于存活判定（§2.1.2 第 1、2 行）。

---

## 8. `rejected_by`（name / location 各 1 列）

**出处：V0.2.2 §2.2.1（行 166–185）**

```sql
ALTER TABLE historical_place_name     ADD COLUMN rejected_by text NULL;
ALTER TABLE historical_place_location ADD COLUMN rejected_by text NULL;

-- C25：rejected 与 rejected_by 同生同灭
ALTER TABLE historical_place_name     ADD CONSTRAINT ck_name_rejected_by
  CHECK ((record_status = 'rejected') = (rejected_by IS NOT NULL));
ALTER TABLE historical_place_location ADD CONSTRAINT ck_loc_rejected_by
  CHECK ((record_status = 'rejected') = (rejected_by IS NOT NULL));

-- C26：只有两种来源
ALTER TABLE historical_place_name     ADD CONSTRAINT ck_name_rejected_by_val
  CHECK (rejected_by IS NULL OR rejected_by IN ('auto','manual'));
ALTER TABLE historical_place_location ADD CONSTRAINT ck_loc_rejected_by_val
  CHECK (rejected_by IS NULL OR rejected_by IN ('auto','manual'));
```

- **值域**：`auto` / `manual`（**2 值**）。这是 **V0.2.2 相对 V0.2.1** 的唯一新增列（+2 = name 1 列 + location 1 列）。
  > ⚠️ **「+2」的口径（留痕，防误读）**：`+2` 是 **V0.2.2 相对 V0.2.1** 的增量，**不是 V2.1.1 相对 V2.1 的增量**。V2.1.1 相对 V2.1 的完整列变更还包含三轮（V0.2 / V0.2.1 / V0.2.2）陆续引入的全部增量，**另含** V0.2.1 §2.7.1 的 `source_time_columns`（location 改名 + **name 新增 1 列**，见 §8.2）。⇒ **不得把 V2.1.1 的新增列写成「+2」**；逐列清单以 `CORE_DATA_MODEL_V2.1.1.md` §5.0 为唯一依据。
- **新列必要性**：没有 `rejected_by` 就无法区分"因源记录消失而自动 rejected"与"人工拒绝"。后果是 P0-02 第 3/4/5 条要求**全部无法实现**——源端重新出现时，导入器只能在"恢复所有 rejected 子行"（覆盖人工决定，被明令禁止）与"一个都不恢复"（人工拒绝之外的合法数据永久丢失）之间二选一。**这不是"多存一列方便查询"，是规则可执行性的前提。**

### 8.2 `source_time_columns`（location **改名** + name **新增**）

**出处：V0.2.1 §2.7.1（行 1449–1451）；§5.6（行 1626）；§5.7（行 1627）**（V0.2.2-r2 全篇未覆盖此点，按效力顺序 **V0.2.1 为准**）

```sql
-- location：改名（不是新增）
ALTER TABLE historical_place_location RENAME COLUMN source_rule_vocabulary TO source_time_columns;

-- name：新增
ALTER TABLE historical_place_name ADD COLUMN source_time_columns text NOT NULL DEFAULT '';
```

| 项 | 定式 |
|---|---|
| 语义（改后） | **「该行来源文件声明了哪些时间列」（列级掩码）**，逐字保留；**不是**本行实际使用的规则（V2.1 的旧语义"非数字规则词元"含糊，已改） |
| 类型 | `text NOT NULL DEFAULT ''`（两表一致） |
| 为什么 name 也要有 | `time_rule_code = 'year_after_which\|year_before_which'` 共 **3,778 行**（name 2,074 + location 1,704）；**V2.1 只有 location 一列能存**，name 侧的 2,074 行 mask 会被丢弃——这是 V2.1 的漏行（`FIELD_MAPPING` 里 name 的 `time_rule_code` 只能落 `(dropped)`） |
| 约束 | **C13 仅落 location**（见 §13 的 C13 行）。⛔ name 表**不得**套用 C13 原式——它没有 `source_beg_rule` / `source_end_rule`，写了就是引用不存在的列 |
| 旧名处置 | `source_rule_vocabulary` **作废**，只在"改名对照"处出现（本条 + `CORE_DATA_MODEL_V2.1.1.md` §5.0 / §5.6） |

> **⛔ 不得据此给「V2.1.1 新增列 N 列」的合计数**：`rejected_by` × 2 表（V0.2.2 增量）、`source_time_columns` on name（V0.2.1 增量）、`import_batch.blocked_count`（V0.2.1 G3-04 行 336）分属三轮不同增量，**合计数是口径陷阱**（沿用裁定 3）。**逐列清单以 `CORE_DATA_MODEL_V2.1.1.md` §5.0 为唯一依据，本文件不再复述、也不给合计。**

### 8.1 四组场景的状态转换（V0.2.2 §2.2.5，行 271–312）

**场景 A｜源记录仍 active，但其名称/位置子行被人工 rejected**

| 实体 | 前 | 后 | 规则 |
|---|---|---|---|
| `source_record` | `is_active=true` | 不变 | 源端未变 |
| 子行 | `record_status='staging'` | `'rejected'`, `rejected_by='manual'` | 人工操作 |
| 该证据 | 有效 | **无效** | 人工拒绝优先 |
| 地点 | `active` / `staging` | 若仍有其他有效证据 ⇒ 不变；否则 ⇒ `liveness∈FAILURE_SET` + `rejected` | 真值表 |
| 时间 | 该子行参与 | 不再参与 | §2.2.6 |
| 台账 | — | **不落**（人工拒绝不是数据质量问题） | §2.4 R2 |

**场景 B｜源记录因 `source_absent` 失效，子行被自动 rejected**

| 实体 | 前 | 后 |
|---|---|---|
| `source_record` | active | `is_active=false`, `inactive_reason='source_absent'`, `inactive_at=now()`, `inactive_in_batch_id=<本批>` |
| 子行 | `staging` | `'rejected'`, **`rejected_by='auto'`** |
| 地点 | `active`/`staging` | 若 ∃ 其他有效证据 ⇒ 保持 `staging`；否则 `liveness='all_sources_absent'` + `record_status='rejected'` |
| 时间 | 参与 | 不参与（`source_is_active=false`） |

**场景 C｜原始源记录重新出现（O1/O7 复活）**

| 实体 | 前 | 后 | 规则 |
|---|---|---|---|
| `source_record` | 失效 | `is_active=true`，三列清 NULL | 复活 |
| 子行 `rejected_by='auto'` | `'rejected'` | **恢复 `'staging'`，`rejected_by` 清 NULL** | **自动恢复** |
| 子行 `rejected_by='manual'` | `'rejected'` | **保持 `'rejected'`** | **人工决定不被自动覆盖**；落 1 条 `manual_edit_conflict` 台账提示人工复核 |
| 地点 | `rejected` | 若 ∃ 有效证据 ⇒ `'staging'`（不新建） | O1/O7 复活规则 |

**场景 D｜子行有人工修改或人工拒绝，源端重新导入**

| 情形 | 处置 | 依据 |
|---|---|---|
| 子行字段 ∈ `manual_edited_fields` | **KEEP_MANUAL** + 台账 `manual_edit_conflict` | V0.2.1 判定表第 5 行 |
| 子行 `rejected_by='manual'` | **保持 rejected**，导入器不得改 | **本轮新增**（C25/C26 + 场景 C） |
| 子行 `locked` | SKIP_ROW + `blocked_count+1` | V0.2.1 判定表第 4 行 |
| 子行 `rejected_by='auto'` 且源仍失效 | 保持 rejected | 场景 B |
| 子行 `rejected_by='auto'` 且源已恢复 | 恢复 staging | 场景 C |

> **明确禁止**：不得"把所有 rejected 子行恢复成 staging"来绕过本条——那会一次性抹掉所有人工拒绝（`rejected_by='manual'`），正是本条要防的。

---

## 9. `time_bound_type` 七值

**出处：`架构/V2.1/CORE_DATA_MODEL_V2.1.md` §6.1（行 674–684）；V0.2.1 §4.2（行 1766，7 值不变）**

| 值 | 语义 | 数据里意味着什么 | 实测（位置 / 名称） |
|---|---|---|---|
| `exact` | 两个端点都是源声明的事实 | "存在于 −214 到 −207 年" | 8,057 / 21,614 |
| `bounded` | 两端都是界限 | "不早于 X，不晚于 Y" | 398 / 1,166 |
| `exact_or_bounded` | 端点混合，源未逐端区分 | — | 812 / 2,360 |
| `tpq_taq` | 两端都是 TPQ/TAQ 界限 | Pleiades 的 `year_after_which`/`year_before_which` | 1,159 / 1,774 |
| `derived_tpq_taq` | 由子行聚合出的 TPQ/TAQ | 只出现在地点级 | 0 / 0 |
| `snapshot` | 单年快照 | CHGIS `BEG_YR = END_YR` 的 21 行 | 21 / 54 |
| `unknown` | 源未声明 | — | 7,656 / 20,535 |

- **七值全序列**：`exact` / `bounded` / `exact_or_bounded` / `tpq_taq` / `derived_tpq_taq` / `snapshot` / `unknown`。
- **`exact_or_bounded` 2,360 与 `bounded` 1,166 不得互换**。
- **`tpq_taq` 与 `bounded` 的区别**：`bounded` 说"这两个端点是界限"，`tpq_taq` 说"这两个端点是**特定类型**的界限，且 Pleiades 用这两个字段名"。本项目取 `tpq_taq` 是因为它保留源词汇。**不要让下游代码依赖这个区分做逻辑分支**——两者在渲染上应当同处理。
- **约束**：`CHECK (time_bound_type <> 'exact' OR (valid_from_year_astro IS NOT NULL AND valid_to_year_astro IS NOT NULL))`（实测违反 0 行）。
- `unknown` 的行**可以**有年份值；`exact` 的行**必须**两端都有值。

---

## 10. `derivation_kind` 三值

**出处：V0.2.1 §2.6.4（`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` 行 1413–1423）；V0.2.1 §4.2（行 1773）；V0.2.2 §0 N15（行 41）**

| 值 | 判据（**必须两端均非 NULL** 才可判 `single_point`） | 期望计数 |
|---|---|---:|
| `no_evidence` | `count(*) FILTER (WHERE (f IS NOT NULL OR t IS NOT NULL) AND record_status <> 'rejected') = 0` | **1,570** |
| `single_point` | `span_from_astro IS NOT NULL AND span_to_astro IS NOT NULL AND span_from_astro = span_to_astro` | **361** |
| `envelope_of_name_and_location_rows` | 其余（含"仅单侧有值"的情形） | **17,108** |

- **不得出现第 4 值**。
- **1,570 + 361 + 17,108 = 19,039（暂存态干跑；加 `sr.is_active` 后待复算）**。
- `single_point` **不得**写成 `MIN(f) = MAX(t)` 而不校验非 NULL——当两端皆 NULL 时该表达式为 NULL（不是 TRUE），会落到 ELSE，把"无证据"误判成"包络"。
- 断言 T4：`derivation_kind` 三值计数 == 1,570 / 361 / 17,108，且 `count(derivation_kind='single_point' AND span_from_astro IS NULL) = 0`。

### 10.1 `no_evidence` 的构成（暂存态干跑，已验证）= 1,570

| 组 | 数量 | 成因 |
|---|---:|---|
| **无子行** | **315**（**入库口径**；暂存/入库同为 315） | 全部 Pleiades（= N11），走 T5 豁免 ① |
| **有子行但有效子行无年份** | **1,255** | 走 T5 豁免 ③；构成 = `none` **1,230** + `tpq_taq_of_children` **25** |

**⚠️ 那 1,255 个是两种不同成因，不得混为一谈（r2 修正）**：

| 组 | 数量 | 成因 | 会不会被误读 |
|---|---:|---|---|
| `none` | **1,230** | **源端本来就没有年份**——子行无年份，地点自身也无年份 | 会（属"源端缺失"，找源数据是对的） |
| `tpq_taq_of_children` | **25** | **年份源是 connection，被 P0-04「排除 connection」切掉了**。**这 25 个地点自身带年份**（实测 25/25 `valid_from/to_year_astro` 非空、`time_bound_type='derived_tpq_taq'`） | **会**——若写成"源端缺失"，下一轮会去源数据里找根本没有的缺失（死路） |

### 10.2 ⚠️ `derivation_kind` / `no_evidence` **不得**直接读暂存 `historical_places.valid_from/to_year_astro`

```
【必须写进交付物】derivation_kind 与 no_evidence 的计数必须基于「只聚合 name + location、排除 connection」的重算结果；
不得直接引用暂存 historical_places.valid_from_year_astro / valid_to_year_astro，
该两列由含 connection 的旧口径生成 ⇒ 会使 no_evidence 系统性偏低 65。
```
（V0.2.2 §2.2.6a，行 362–368）

| 项 | 值 |
|---|---:|
| 暂存列两端皆空（`time_derivation='none'`） | **1,505**（旧口径，含 connection） |
| `tpq_taq_of_children` 中 name/location 子行全无时间值 | **65** |
| **新设计 `no_evidence`** | **1,505 + 65 = 1,570** ✓（**暂存态干跑**） |
| ├ 无子行 | 275 + 40 = **315**（**入库口径**） |
| └ 有子行 | 1,230 + 25 = **1,255** |

---

## 11. `inactive_reason` / `issue_type` / `import_batch.status`

### 11.1 `source_record.inactive_reason`（**3 值**）

**出处：V0.2.1 §4.2（行 1763）；V0.2.1 §4.3 C19（00_PROBLEM_LIST_AND_PLAN.md 行 1785）；V0.2.2 §4.1 K5（行 969）**

```
source_absent / batch_rolled_back / duplicate_quarantine  （+ NULL 表 active）
```

> **`import_error` 已删除**（0 条可达路径，V0.2.1 §0.4-R11）。

### 11.2 `data_quality_issue.issue_type`（**19 值**）

**出处：V0.2.1 §4.2（行 1769）；清单 = `CORE_DATA_MODEL_V2.1.md:642` 的 20 值删 `licence_unconfirmed`**【留痕：删枚举值说明】

```
1  beg_gt_end
2  beg_eq_end
3  missing_coordinate
4  coordinate_out_of_range
5  coordinate_outside_china_bbox
6  year_out_of_range
7  duplicate_external_id
8  duplicate_sysid
9  unknown_crs
10 unknown_time_bound_type
11 nonstandard_field_name
12 empty_name
13 parent_place_not_in_sample
14 truncated_slice_tail
15 cross_layer_coordinate_conflict
16 manual_edit_conflict
17 import_row_error
18 derived_value_mismatch
19 rollback_conflict
```

- **禁止**为凑满 20 值而新增替代类型（Owner 决策 3 / V0.2.1 §2.8-C）。
- **实测值域 12 种**（删 2 行 `licence_unconfirmed`【留痕：删枚举值】后由 13 降为 12）；目标枚举 **19**。
- **回滚阶段**产生的台账类型**只有** `rollback_conflict` 与 `manual_edit_conflict` 两种；`import_row_error` 属**原导入阶段**，不计入 R2，改由 **R2c** 单独校验。

### 11.3 `import_batch.status`（**6 值**）

**出处：`架构/V2.1/CORE_DATA_MODEL_V2.1.md` §5.3（行 235）**

```
running / succeeded / partial / failed / rolled_back / quarantined_only
```

| 状态 | 判据 |
|---|---|
| `succeeded` | `failed_count = 0` |
| `partial` | `failed_count > 0`，且每条失败都有台账 |
| `failed` | 前置校验未通过或整批中断。**此时一行都不许落库** |
| `rolled_back` | 已完整撤销 |
| `quarantined_only` | `inserted = 0` 且 `quarantined = input_row_count`（整套文件都是重复行） |

---

## 12. 台账语义 A（唯一身份）+ 三个伴生列

**出处：V0.2.1 §2.5.5（`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` 行 1289–1324）**

### 12.1 语义

```
语义：A（唯一身份）+ 事件伴生列。全系统只有这一套语义，不混用 B。

指纹 = 一个对象 × 一类问题 × 一个字段 × 一份证据内容  的唯一身份
     = md5(jsonb_build_array(source_record_id, dataset_id, place_id,
                             issue_type, field_name, observed_value)::text)
```

| 决策 | 结论 | 理由 |
|---|---|---|
| 指纹是否含 `batch_id` | **不含** | 197 条派生偏差是"一处持续存在的偏差"，含 `batch_id` 会让每导一批新增 197 行（台账自我膨胀） |
| 重复发现怎么处理 | **UPDATE，不 INSERT** | `last_batch_id = 本批`、`occurrence_count += 1`、`first_batch_id` 不变 |
| 内容不同的多次冲突 | **各占一行** | `observed_value` 是指纹的一段，内容不同 ⇒ 不同问题对象（`manual_edit_conflict` 的"事件性"由此承载，无需引入 B 语义） |
| 语义 B（每次发现独立成行） | **不采用** | 与前两条冲突，且与"重导不产生第二行"的幂等要求矛盾 |

### 12.2 编码规范化（三条）

1. **段值一律用 JSON 数组承载**：`null` / `""` / 含 `|` 的值三者互不相同（实测，V0.2.1 §0.4-R5）；
2. **空值不做 `coalesce` 归一**：`NULL` 与 `''` 必须保持可区分；
3. **`observed_value` 的口径沿用 §2.5.3**：暂存列原始字符串单值、空值渲染字面量 `NULL`、重算值进 `notes`。

### 12.3 三个伴生列

| 列 | 语义 | 约束 |
|---|---|---|
| `first_batch_id` | 首次发现该问题的批次。**重复发现时不变** | `C24 CHECK (first_batch_id IS NULL OR last_batch_id IS NOT NULL)`；断言 F12d `count(*) WHERE first_batch_id IS NULL AND last_batch_id IS NOT NULL = 0` |
| `last_batch_id` | 最近一次发现该问题的批次。重复发现时置为本批 | 同上 |
| `occurrence_count` | 该问题被发现的次数。重复发现时 `+= 1` | `C23 CHECK (occurrence_count >= 1)`；断言 F12c `count(*) WHERE occurrence_count < 1 = 0` |

### 12.4 指纹唯一性验证（真实数据）

| 指纹构成 | 不同指纹数 | 冲突组 | 涉案行 |
|---|---:|---:|---:|
| 六段（含 `place_id`） | **197** | **0** | 0 |
| 五段（不含 `place_id`） | **45** | **24** | **176** |

（V0.2.1 行 1311–1316、行 1262–1269）

> 次大一组：`valid_to_year_astro` / `300` = 21 行；第三：`valid_from_year_astro` / `300` = 17 行。最大一组 26（`valid_from_year_astro` / `-29`）。

---

## 13. 约束全集 C01–C29

**出处：V0.2.2 §4 第 11 项（行 956）、§2.2.1（行 172–182）、§2.1.3（行 114–120）、§2.5.0（行 527–534）、§2.7.3（行 783–791）；V0.2.1 §4.3 约束表（`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` 行 1777–1804）**

### 13.1 逐条落点表与状态

| # | 约束 | 落点 | 状态 |
|---|---|---|---|
| **C01** | `UNIQUE (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` | `source_record` | **保留**（五段键；`parent_external_id` 必需段见 C29） |
| **C02** | `CHECK (is_active OR duplicate_ordinal > 0)`（V0.1） | `source_record` | **废除** → 由 **C20** 取代（理由 G8-01） |
| **C03** | `CHECK ((is_active AND inactive_reason IS NULL) OR (NOT is_active AND inactive_reason IS NOT NULL))` | `source_record`（不变量） | **保留** |
| **C04** | `UNIQUE (dataset_id, grain_key)` | `historical_place` | **保留** |
| **C05** | `CHECK (created_by='manual' OR created_from_source_record_id IS NOT NULL)` | `historical_place` | **保留** |
| **C06** | `CHECK (merged_into_place_id IS NULL OR (record_status='merged' AND merge_review_ref IS NOT NULL AND merged_at IS NOT NULL))` | `historical_place` | **保留** |
| **C07** | `UNIQUE (source_record_id) WHERE source_record_id IS NOT NULL` | `historical_place_location` | **保留**（V0.2.1 新增，实测 0 冲突） |
| **C08** | `UNIQUE (source_record_id, name_type, name_text, name_lang)` | `historical_place_name` | **保留**（**不得**改成 `UNIQUE(source_record_id)`，一个记录最多 3 个名称行） |
| **C09** | `UNIQUE (relation_type, place_id_a, place_id_b)` | `candidate_match` | **保留** |
| **C10** | `UNIQUE (issue_fingerprint)` | `data_quality_issue` | **保留**（替换 2 条部分索引）。指纹 = JSON 数组编码 + **六段含 `place_id`**；缺 `place_id` 则 197 条只剩 45 个不同指纹（24 组 / 176 行） |
| **C11** | `CHECK (dataset_id IS NOT NULL OR place_id IS NOT NULL)` | `data_quality_issue` | **保留** |
| **C12** | `CHECK (dataset_id IS NOT NULL OR source_record_id IS NULL)` | `data_quality_issue` | **保留** |

> **⭐ C11/C12 的可空性前提（留痕，QA F-12 / CORE A-4）**：`data_quality_issue.dataset_id` **必须可空**（`text`，FK → `data_dataset`，**可空**），依据 **V0.2.1 §2.5.1（行 1233）、§5.9（行 1629）、§6（行 1798–1799）**——V0.2.2-r2 全篇未覆盖该点，按效力顺序 V0.2.1 为准。
> **若 `dataset_id` 定为 NOT NULL**：`dataset_id IS NOT NULL` 恒真 ⇒ **C11/C12 永不可能触发**，是"看起来在守、其实什么都没守"的死约束。改可空后两条 CHECK 恢复为真实的归因兜底：**任何一行台账至少能说清「这是哪个数据集的问题」或「这是哪个地点的问题」**。
> **连带效果**：`data_quality_issue` 中 6 行空 `source_record_id` 的 `dataset_id` 缺口**自然消解**（合法留 NULL，由 C11 要求它们必须带 `place_id`）⇒ 该登记项由"待裁定是否整批 failed"降级为"待复核"。与 `CORE_DATA_MODEL_V2.1.1.md` §5.9 / §5.0 / 附录 B V-6 一致。
| **C13** | `CHECK (source_time_columns = '' OR (source_beg_rule IS NULL AND source_end_rule IS NULL))` | `historical_place_location`（**改名后**：V0.2.1 §2.7.1 行 1449–1451 把 `source_rule_vocabulary` 改名为 `source_time_columns`） | **保留**。⛔ **C13 仅落 location**：`historical_place_name` **没有** `source_beg_rule` / `source_end_rule` 两列（V0.2.1 §5.7 行 1627 只要求 name 表 `+source_time_columns`，其余继承 V2.1，而 V2.1 name 表无数字规则列）⇒ 把 C13 原式写进 name 表会引用**不存在的列、SQL 无法编译**。name 表的 `source_time_columns` 只作掩码留存（收纳 V2.1 会丢弃的 2,074 行 name 侧 mask），**无「数字/词元二选一」冲突面**。与 `CORE_DATA_MODEL_V2.1.1.md` §5.6 / §5.7 / 附录 A 逐字一致 |
| **C14** | `CHECK (crs_confidence <> 'unknown' OR record_status <> 'published')` | `historical_place_location` | **保留**（CRS 门禁） |
| **C15** | `CHECK (geom IS NOT NULL OR record_status <> 'published')` | `historical_place_location` | **保留**（几何门禁） |
| **C16** | `CHECK (time_bound_type <> 'exact' OR (both NOT NULL))` | name / location | **保留** |
| **C17** | `CHECK (direction='none' OR relation_type='location_migration_candidate')` | `candidate_match` | **保留** |
| **C18** | 同上 **C03**，作为 V0.2 正式编号 | `source_record` | **保留**（与 C03 **双编号，去重后不另计**） |
| **C19** | `CHECK (inactive_reason IS NULL OR inactive_reason IN ('source_absent','batch_rolled_back','duplicate_quarantine'))` | `source_record`（3 值） | **保留** |
| **C20** | `CHECK (inactive_reason <> 'duplicate_quarantine' OR duplicate_ordinal > 0)` | `source_record`（**取代 C02**） | **保留** |
| **C21** | `CHECK ((inactive_at IS NULL) = (inactive_reason IS NULL))` | `source_record` | **保留** |
| **C22** | `CHECK ((inactive_in_batch_id IS NULL) = (inactive_reason IS NULL))` | `source_record` | **保留** |
| **C23** | `CHECK (occurrence_count >= 1)` | `data_quality_issue`（伴生列） | **保留** |
| **C24** | `CHECK (first_batch_id IS NULL OR last_batch_id IS NOT NULL)` | `data_quality_issue`（伴生列一致性） | **保留** |
| **C25** | `CHECK ((record_status = 'rejected') = (rejected_by IS NOT NULL))`（name + location 各 1 条） | `historical_place_name` / `historical_place_location` | **新增（V0.2.2）** |
| **C26** | `CHECK (rejected_by IS NULL OR rejected_by IN ('auto','manual'))`（name + location 各 1 条） | `historical_place_name` / `historical_place_location` | **新增（V0.2.2）** |
| **C27** | 真值表除 `orphaned` 行外，每一行 ✅ 恰有 1 个；`orphaned` 行 ✅ 恰有 0 个（即 `count(合法组合) == 7`，且不存在同一 `liveness` 对应两个 `record_status`） | §2.1.3 真值表 | **新增（V0.2.2）**——**断言级**（不落成 SQL CHECK） |
| **C28** | 真值表与 §2.1.2 优先级衔接：∀ 行，`liveness` 由 §2.1.2 自上而下首次命中决定；若某格与本优先级冲突（如 `(manual, merged)`），该格**恒不可达**，必须置 ❌ | §2.1.3 真值表 | **新增（V0.2.2）**——**断言级** |
| **C29** | `parent_external_id` 为必需段：① 不得省略 / NULL 兜底 / 空串代替；② 无父级写哨兵 `'-'`（不是 NULL），保证 UNIQUE 生效（Postgres UNIQUE 对多列 NULL 不去重）；③ 派生失败 ⇒ 整批 failed（同 A12）；④ 哨兵必须是值域外保留字，只能在 `data_dataset` 或一张常量表里声明一次 | §2.5.0 五段自然键 | **新增（V0.2.2）**——**键级硬约束**（写进 `UNIQUE` 与所有去重/隔离实现） |

### 13.2 ⭐ 唯一权威的有效条数计数

> **以下为本文件采用的唯一口径，不得再出现第二个数字。**

| 口径 | 数 | 算法 |
|---|---:|---|
| **C 编号总数** | **29** | C01–C29 |
| 减：废除 | −1 | C02（由 C20 取代） |
| 减：双编号 | −1 | C18 与 C03 同一条，去重后不另计 |
| **⭐ 有效约束条目（唯一权威数）** | **27** | 29 − 1 − 1 |
| ├ 其中**可落库的 SQL 约束**（UNIQUE / CHECK） | **24** | = V0.2.1 的 **22** + 本轮 **C25 / C26** |
| └ 其中**不可落成 SQL CHECK 的断言级/键级硬约束** | **3** | **C27 / C28 / C29** |

**说明**：
- V0.2.2 §4 第 11 项原文"**CHECK 总数 = 24 条**（= V0.2.1 的 **22** 条 + 本轮 C25/C26；C02 已被 C20 取代而**废除**、C03/C18 为双编号**去重后不另计**），编号范围 C01–C26"——该 24 是 **r1 时刻**的计数，彼时 C27/C28/C29 尚未引入。
- V0.2.2 §1 与 §5.2 后续引入 **C27 / C28 / C29**（其中 C29 被 §5.2 列为"✅ 已验证"的断言）。**三个编号均已存在于 V0.2.2-r2 正文且未被废除**，因此计入有效条目。
- ⇒ **"有效约束条目 = 27"** 与 **"可落库 SQL 约束 = 24"** 是**同一全集的两个子集口径**，不是两个矛盾的数：
  - 讨论"**建库后能跑多少条 CHECK/UNIQUE**" ⇒ 用 **24**；
  - 讨论"**C01–C29 里有多少条还有效**" ⇒ 用 **27**。
- **不属于 C 编号集合、但同样是可校验断言的项**（单独列出，不并入上面任一数字）：**R2c**（`import_row_error` 计数 == `N_failed`）、**INV-1**（换绑五条不变量）、**ALG-1**（两种摘要算法并存不可统一）、**CIT-1′ / CIT-2′**（文档级引用纪律）、**T5**（`no_evidence` 可解释）。

### 13.3 关联：本轮架构侧净增量（V0.2.2 §1，行 66）

**新表 0，新列 +2（**仅** `rejected_by` × 2 表），新 CHECK +2（C25/C26），新视图派生列（逐列名见 §14，不给总数），新操作 0，新枚举类型 1（`rejected_by`）、`liveness` 7→8 值、`evidence_role` 收敛 3 值、判定表 +1 行。**

> **`data_dataset.place_grain` 是 V2 既有列**（`CORE_DATA_MODEL_V2.md:208`；V2.1 收敛为 2 值），**不是**本轮新增——暂存 CSV 未导出它（`FIELD_MAPPING_V2.1.csv:19` 标 `(derived)`），但设计里一直有。⇒ 真实性质是「**暂存 CSV 未导出该列**」，**不是设计里没有**。r1 曾记为 +3，**已回退为 +2**（`rejected_by` × 2 表）【留痕：历史计数留痕，QA W-03】。

### 13.4 建点白名单断言（V0.2.2 §2.7.3，行 783–791）

```
A12  每个 source_record 的 record_scope ∈ ('place','name','location','edge')；
     出现第五种 ⇒ 整批 failed（不默认放行）
V3'  count(creator 证据行 WHERE is_anchor) == 19,039          -- 每地点恰好 1 条锚点
V4   count(证据行 WHERE evidence_role='creator' AND source.record_scope='edge') == 0
V5   count(证据行 WHERE evidence_role='creator'
             AND source.record_scope='name'
             AND dataset.place_grain <> 'per_parent_external_id') == 0
```

**白名单（写死）**：
```
可作为建点依据的源记录 ⇔
   ( sr.record_scope = 'place' )                                    -- ① 逐记录建点
 OR ( sr.record_scope IN ('name','location')                        -- ② 按组建点
      AND sr.dataset_id 对应的 data_dataset.place_grain = 'per_parent_external_id' )
```
失败分支：`place_grain = 'per_record'` ⇒ 该数据集的 name/location 记录**不建点**；该 `dataset_id` 在 `data_dataset` 中不存在 ⇒ **整批 failed**（同 A12）；值域外的值 ⇒ 由 CHECK 在建库期拦截。

---

## 14. 三视图清单

### 14.1 `v_place_evidence`

**出处：V0.2.2 §2.2.2（行 187–220）、§2.8.2（行 805–818）**

**列清单（11 列）**：

| # | 列 | 类型 | 说明 |
|---:|---|---|---|
| 1 | `place_id` | bigint | |
| 2 | `source_record_id` | bigint | |
| 3 | `evidence_role` | text | `creator` / `name` / `location`（**3 值，`place_record`【留痕：禁用词】是禁用词**） |
| 4 | `source_is_active` | bool | 派生（V0.2.2 新增） |
| 5 | `source_inactive_reason` | text | 派生（V0.2.2 新增） |
| 6 | `child_table` | text | `'name'` \| `'location'` \| `NULL`（creator 行为 NULL）（V0.2.2 新增） |
| 7 | `child_row_id` | bigint | V0.2.2 新增 |
| 8 | `child_record_status` | text | V0.2.2 新增 |
| 9 | `child_rejected_by` | text | `'auto'` \| `'manual'` \| NULL（V0.2.2 新增） |
| 10 | `is_anchor` | bool | `sr.source_record_id = p.created_from_source_record_id` |
| 11 | `is_canonical_row` | bool | 视图派生列（§2.8）。⛔ **不是写死常量、不是占位符**：三个分支统一由**外层窗口函数**计算，见下方「`is_canonical_row` 定序」 |

**三个分支**：① 创建证据（1:N，白名单见 §2.7）→ `evidence_role='creator'`；② 名称行 → `'name'`；③ 位置行 → `'location'`。

**`is_canonical_row` 定序（写死，已落地为可执行 SQL）**：
```
is_canonical_row ⇔ 该行是本地点证据集中定序第一的行
实现：UNION ALL 三支下沉为子查询 u，外层
      row_number() OVER (PARTITION BY u.place_id ORDER BY ...) = 1
      并回连 LEFT JOIN source_record sr ON sr.source_record_id = u.source_record_id

排序键（顺序不可换）：
  ⓿ (source_is_active AND child_record_status IS DISTINCT FROM 'rejected') DESC  -- 有效证据优先
  ① (evidence_role = 'creator') DESC            -- 创建记录优先
  ② sr.duplicate_ordinal ASC NULLS LAST         -- 与 §2 同源（回连 source_record 取值）
  ③ sr.external_id       ASC NULLS LAST         -- MCGD 即"NameID 最小"（回连 source_record 取值）
  ④ source_record_id     ASC                    -- 破并列（可复现）
  ⑤ coalesce(child_row_id, 0) ASC               -- 同记录多行 name 的行级破并列（可复现）
```

> **⭐⭐ 与 V0.2.2 原文的差异（留痕，QA F-11）**：V0.2.2 §2.2.2（行 201）把 creator 分支写死 `FALSE AS is_canonical_row`，而 §2.8.2（行 816）要求「315 个（入库口径）无子行地点的 `is_canonical_row=true` 落在 creator 行」⇒ **原文自相矛盾**，且 ② 分支的 `<canonical 定序 §2.8>` 是**不可执行占位符**。
> **本版按「外层窗口定序」解决**（与 `CORE_DATA_MODEL_V2.1.1.md` §5.10.1 / §5.10.4 / §5.10.5 逐字一致），须写入 CHANGELOG。
> **⛔ ②③ 必须回连 `source_record`**：`duplicate_ordinal` / `external_id` **不是** `v_place_evidence` 的列；"在视图内直接 ORDER BY 这两列"不可执行。
> **⛔ ⓿ 不可省略**：定义句写的是"**有效证据**中定序第一的行"；缺 ⓿ 则一条 rejected 子行或失效源行可能成为 canonical ⇒ 定义句与 SQL 不自洽。
> **⛔ ⑤ 不可省略**：C08 允许一条 `source_record` 派生最多 3 行 name（`name_type` 不同），其 ②③④ 键**全同**；缺 ⑤ 则 `row_number()` 并列取值**不可复现**，与 §2「ordinal 必须可复现」冲突。
> ⓿ 与 ⑤ 两键为**补全项**（V0.2.2 四键未含），登记 CORE 附录 B **V-8** 待 QA 复算。

**锚点 vs 当前最佳证据（§2.8.3）**：

| 概念 | 列 | 语义 | 是否随导入变 |
|---|---|---|---|
| **锚点** | `created_from_source_record_id` | 首次导入时的身份记录（IDENTITY，永不改写） | 否 |
| **当前最佳证据** | `v_place_evidence.is_canonical_row` | 每次导入重算 | 是 |

二者指向不同记录 **不是错误**，不落台账；`DATA_PROVENANCE` 必须写明这是设计选择。

### 14.2 `v_place_liveness`

**出处：V0.2.2 §2.2.4（行 235–269）；列骨架补自 V0.2.1 §2.3.4（`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` 行 1044–1080）**

> **注**：V0.2.2 §2.2.4 的 `SELECT p.place_id, ..., CASE … END AS liveness, ...` 中 `...` 未逐列枚举。下表 = V0.2.1 §2.3.4 已枚举的列 + V0.2.2 §2.2.4 明确新增/替换的列。
>
> **⚠️ 本表为【补全项、非新设计】**：依据 V0.2.2 §2.1.2（八值 `liveness` 与派生优先级）/ §2.2.3（有效证据定义）/ §2.2.5（四场景 A–D）与 V0.2.1 §2.3.4 的已枚举列补全，**待 QA 复算**（对应 CORE 附录 B **V-1**；QA **W-09**）。V0.2.2-r2 原文以 `...` 省略，**不得**把本表当成 V0.2.2 的逐字原文。

**对外列清单（7 列）**：

| # | 列 | 说明 |
|---:|---|---|
| 1 | `place_id` | |
| 2 | `dataset_id` | 来自 `historical_place`（V0.2.1 §2.3.4） |
| 3 | `grain_key` | 来自 `historical_place`（V0.2.1 §2.3.4） |
| 4 | `record_status` | 来自 `historical_place`（3 值） |
| 5 | `manual_rejected_rows` | 对外新增：`count(*) FILTER (WHERE e.child_rejected_by = 'manual')`，供场景 D 与台账使用 |
| 6 | `distinct_inactive_reasons` | 对外新增：`count(DISTINCT e.source_inactive_reason) FILTER (WHERE NOT e.source_is_active)`，用于判 `mixed_inactive` |
| 7 | `liveness` | **8 值**（见 §7.2） |

**CTE 中间量（2 列，不在对外 `SELECT` 中）**：

| 列 | 说明 |
|---|---|
| `has_valid` | **CTE 中间量，不对外**。V0.2.2 新增（替换 V0.2.1 的 `has_active`）：`bool_or(e.source_is_active AND e.child_record_status IS DISTINCT FROM 'rejected')`，仅供 `CASE` 判 `'active'` |
| `reasons` | **CTE 中间量，不对外**。V0.2.2 新增（替换 V0.2.1 的 `last_inactive_reason` 标量）：失效原因数组，按 `inactive_at DESC NULLS LAST, inactive_in_batch_id DESC NULLS LAST, CASE reason WHEN 'batch_rolled_back' THEN 1 WHEN 'duplicate_quarantine' THEN 2 WHEN 'source_absent' THEN 3 END` 定序，仅供 `CASE` 取 `reasons[1]` |

> **⭐ 对外列数口径（留痕，QA F-04）**：本视图**对外 7 列**（上表 1–7），`has_valid` / `reasons` 是 CTE 中间量**不计入对外列**。旧稿曾标「9 列」并把两中间量算作对外列 ⇒ **与 CORE §5.10.2 的 SQL 互斥**（CORE 的 `SELECT` 只输出 7 列）。本版按 **QA F-04 方案 A**（SQL 不动、改文档）统一为 **7 列**，与 `CORE_DATA_MODEL_V2.1.1.md` §5.10.2 / §5.10.5 逐字一致。
> **算术核对**：V0.2.1 的 8 列 − 3 列被取代（`active_creator_rows` / `active_child_rows` 不再对外 + `last_inactive_reason` 被 `reasons` 取代）+ 2 列对外新增（`distinct_inactive_reasons` / `manual_rejected_rows`）= **7** ✓。「对外新增 2」与「对外总列数 7」是两个口径，**不矛盾**。

**派生逻辑（CASE，V0.2.2 §2.2.4）**：
```
WHEN p.record_status = 'merged'                          THEN 'merged'
WHEN p.created_by    = 'manual'                          THEN 'manual'
WHEN coalesce(ev.has_valid,false)                        THEN 'active'
WHEN coalesce(ev.distinct_inactive_reasons,0) > 1        THEN 'mixed_inactive'
WHEN coalesce(ev.distinct_inactive_reasons,0) = 1        THEN
     CASE ev.reasons[1] WHEN 'source_absent'        THEN 'all_sources_absent'
                        WHEN 'batch_rolled_back'    THEN 'all_sources_rolled_back'
                        WHEN 'duplicate_quarantine' THEN 'quarantined_only' END
ELSE 'orphaned'
```

> **V0.2.1 → V0.2.2**：`bool_or(sr.is_active)` → 加 `child_record_status <> 'rejected'`；新增 `distinct_inactive_reasons` 判 `mixed_inactive`；`manual_rejected_rows` 供场景 D 与台账使用。

> **⭐⭐ CTE 必须回连 `source_record`（留痕，QA F-03 / CORE A-1）**：`reasons` 的定序键 `inactive_at` / `inactive_in_batch_id` **不在 `v_place_evidence` 的 11 列里**（该视图固定 11 列，见 §14.1）。CTE 必须写：
> ```sql
> FROM v_place_evidence e
> JOIN source_record sr ON sr.source_record_id = e.source_record_id
> ```
> 并用 `sr.inactive_at` / `sr.inactive_in_batch_id` 定序。
> **根因留痕**：V0.2.2-r2 §2.2.4（行 246–247）把 CTE 里的 `JOIN source_record sr` 去掉、把 `sr.` 全改成 `e.`，**却未给 `v_place_evidence` 补这两列** ⇒ 原样照抄则 **SQL 无法编译**。⛔ **不采用**「给视图加两列变 13 列」的解法（那会破坏 §14.1 的 11 列定式）。与 `CORE_DATA_MODEL_V2.1.1.md` §5.10.2 逐字一致。

### 14.3 `v_place_time_span`

**出处：V0.2.1 §2.6.1（`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` 行 1332–1368）；V0.2.2 §2.2.6（行 314–360）**

**列清单**：

| # | 列 | 说明 |
|---:|---|---|
| 1 | `place_id` | |
| 2 | `span_from_astro` | `MIN(c.f) FILTER (WHERE 有效)` |
| 3 | `span_to_astro` | `MAX(c.t) FILTER (WHERE 有效)` |
| 4 | `from_evidence_rows` | `count(*) FILTER (WHERE c.f IS NOT NULL AND 有效)` |
| 5 | `to_evidence_rows` | `count(*) FILTER (WHERE c.t IS NOT NULL AND 有效)` |
| 6 | `staging_evidence_rows` | `count(*) FILTER (WHERE c.record_status = 'staging')` |
| 7 | `derivation_kind` | **3 值**（见 §10） |
| 8 | `child_rows_total` | **V0.2.2 新增**：该地点全部 name+location 行数 |
| 9 | `valid_child_rows` | **V0.2.2 新增**：有效子行数。⛔ **必须写 `count(e.place_id)`，不得写裸 `count(*)`**（见下方留痕） |
| 10 | `all_children_rejected` | **V0.2.2 新增**：`child_rows_total > 0 AND valid_child_rows = 0` |

> **⭐⭐ `valid_child_rows` 必须用 `count(e.place_id)`（留痕，QA F-05 / CORE A-2）**：主查询是 `historical_place p LEFT JOIN eff e`，**LEFT JOIN 无匹配时仍产生 1 行全 NULL** ⇒ 裸 `count(*)` 得 **1**（不是 0）⇒ `valid_child_rows` 对"无有效子行"的地点**恒 ≥1** ⇒ `all_children_rejected`（`child_rows_total > 0 AND valid_child_rows = 0`）**永不可能为真** ⇒ T5 豁免 ② 完全失效。
> 改用 `count(e.place_id)`：`e.place_id` 在无匹配行为 NULL，`count(列)` **不计 NULL** ⇒ 无有效子行时得 **0**，语义恢复。
> **其余 `count(*) FILTER (...)` 保持不动**：`FILTER` 子句在无匹配行时该行被排除（`e.f IS NOT NULL` 为 NULL ⇒ 不计数），语义已安全；只有**无 FILTER 的裸 `count(*)`** 有问题。
> **这也是一个回归**：V2.1 §5.5.4 用 `COUNT(c.*) FILTER(...)`、V0.2.1 §2.6.1 用 `count(*) FILTER(...)`，都未出现"裸 `count(*)` 当有效行数"的写法。与 `CORE_DATA_MODEL_V2.1.1.md` §5.10.3 逐字一致。

**⭐ 过滤条件（V0.2.2 §2.2.6，行 316–322）**：
```sql
-- V0.2.1: WHERE c.record_status <> 'rejected'
-- V0.2.2: 与 §2.2.3 "有效证据" 同一判据
JOIN source_record sr ON sr.source_record_id = c.source_record_id
WHERE c.record_status <> 'rejected'
  AND sr.is_active
```

> **过滤是 `record_status <> 'rejected'`，**不是** `'published'`。**
> V0.2.1 §2.6.1 原文（行 1364–1366）："过滤条件（V0.2 定稿）：`c.record_status <> 'rejected'`。**V0.2 变更**：V0.1 继承 V2.1 的 `record_status = 'published'`，实测使 **0/19,039** 个地点有跨度（视图整体空转）——因为子表 CSV 根本没有 `record_status` 列，且 V2.1 全文无发布动作。改为 `<> 'rejected'` 后 **17,469/19,039** 有跨度。
> **禁止**用"默认 published"绕过：那会让 646 条未知 CRS + 10 条无几何直接越过两道门禁。

**聚合源（刻意排除 connection/edge）**【留痕：排除告警必需表述】：
```sql
WITH child AS (
    SELECT place_id, valid_from_year_astro AS f, valid_to_year_astro AS t, record_status
      FROM historical_place_name
    UNION ALL
    SELECT place_id, valid_from_year_astro, valid_to_year_astro, record_status
      FROM historical_place_location
    -- 刻意不 UNION 任何 edge/connection 来源【留痕：排除告警必需表述】
)
```
**必须排除 connection/edge 的四条证据链**【留痕：排除告警必需表述】（V0.2.1 §2.6.2）：① 实测 1,816/1,816 个有地点级时间的 Pleiades 地点，其值 == "全部 name+location+**connection** 源记录的年值包络"，0 例外；② 65/65 个"有地点级时间、但全部子行无时间"的地点，全部由 connection 的时间解释；③ 代码：`normalize.py:666` 把 `connection` 放进 `extra_children`，`normalize.py:494–509` 对全部 children 求包络；④ 语义：connection 的年份描述"两个地点之间关系的存续期"，不是"该地点存在到 X 年"——把边的时间写进点的存在期是**量纲错误**。

**四条不变式（施工后逐条验，必须 0 违反）**：
```
T1  from_evidence_rows = 0 ⇒ span_from_astro IS NULL
T2  to_evidence_rows   = 0 ⇒ span_to_astro   IS NULL
T3  span_from_astro > span_to_astro 的行数 == 0（倒挂的 28 条在子行上已留空）
T4  derivation_kind 三值计数 == 1,570 / 361 / 17,108（合计 19,039）
    且 count(derivation_kind='single_point' AND span_from_astro IS NULL) = 0
```

**新增断言 T5（三项豁免）**：
```
T5  count(place WHERE liveness='active'
                 AND derivation_kind='no_evidence'
                 AND NOT ( child_rows_total = 0
                        OR all_children_rejected
                        OR ( valid_child_rows > 0
                             AND 全部有效子行的 valid_from_year_astro 与 valid_to_year_astro 皆为 NULL ))) == 0
```
豁免三选一：① **本来就没有子行**（`child_rows_total = 0`）；② **子行全被拒**（`all_children_rejected`）；③ **有有效子行，但那些子行本来就没有年份值**。
（V0.2.2 行 327–336；干跑 **T5 = 0** ✓ 已验证）

> **T5 的有效命中率（写进交付物，避免高估断言价值）**：暂存数据中"被过滤"情形 **0 例**，T5 抓到的 1,255 个**全是**"本来没有"。**T5 在真实数据上 0% 有效命中**——它是**防未来回归的护栏**，不是当前的缺陷探测器。

---

## 15. STOP_AUTO 规则与 `duplicate_external_id` 台账复用

**出处：V0.2.2 §2.5.2（行 589–602）；§2.5.1（行 574–587）；§2.5.3（行 604–613）；§2.5.4（行 615–617）**

### 15.1 判据（写死）

```
若 |old| = |new| 且 |old ∩ new| < |old| − 1
   ⇒ 有 ≥2 条同时变化，无法把新旧内容一一对应
   ⇒ 停止自动更新（STOP_AUTO）
```
其他无法唯一对应的情形（如 `|old|=|new|` 但多重集交集更小）同理。

### 15.2 待核验状态的实现（**不加新表、不加新列**）

1. 该组**整组 `SKIP_UPDATE`**：本批不修改任何已有行的 `content_hash` / ordinal。
2. 落 **1 条 `duplicate_external_id`** 台账（**复用既有类型，不新增枚举值**），`observed_value` 写明 `old_multiset` 与 `new_multiset`，`notes` 写明"ordinal 无法唯一对应，等待人工核验"。
3. 每次导入重判；若仍无法唯一对应 ⇒ 再次 `SKIP_UPDATE` + 台账（`occurrence_count += 1`，V0.2.1 §2.5 的伴生列正好承载这个）。

### 15.3 五种变化的自动/停止二分表

| # | 变化 | 检测 | 可自动？ | 处置 |
|---|---|---|---|---|
| ① | 组内**一条**内容变化 | `\|old\| = \|new\|` 且 `\|old ∩ new\| = \|old\| − 1` | ✅ **自动** | 未变的那一行保持 `source_record_id` 与 ordinal；变的那一行**在同 `source_record_id` 上更新** `content_hash` / `raw_payload` / `last_batch_id`，ordinal 由算法重算 |
| ② | **新增**一条（组 2 → 3） | `new ⊃ old` 且 `\|new\| − \|old\| = 1` | ✅ **自动** | 新行 INSERT，ordinal 由算法给。已有行**默认不动**；**仅当**新增行的 `content_hash` 在 `(content_hash ASC, raw_record_index ASC)` 全序中落在两个既有行之间，且该插入导致既有行的 ordinal 不再等于其全序位次 ⇒ **只重排受影响的既有行**，其余一律不动 |
| ③ | **删除**一条（组 2 → 1） | `old ⊃ new` 且 `\|old\| − \|new\| = 1` | ✅ **自动** | 剩余行 ordinal → 0（不再属重复组）；消失的那一行：若已是 `duplicate_quarantine` ⇒ 保持；否则置 `source_absent`（**不删行**） |
| ④ | **两条内容交换** | `old_set = new_set`（多重集完全相同） | ✅ **无需处理** | 见下方「④ 的补充」 |
| ⑤ | **内容相同的记录数量变化**（3 → 4 条同哈希） | 同哈希行的基数变化 | ✅ **自动** | 按 ② / ③ 处理；同哈希内部的 ordinal 由 `raw_record_index` 破并列 ⇒ **跨版本不可稳定，但内容不可区分 ⇒ 无语义影响** |

**④ 的补充（r1 新增）**：多重集不变**不代表绑定未变**——组内两行内容互换时，`source_record_id → content` 的绑定**恰恰翻转了**，只是因为定序键是 `content_hash`，翻转后 ordinal→内容映射与翻转前**逐位相同**，所以**不可观测**。
- 本设计**显式接受**这一不可观测性——内容相同 ⇒ 两条记录的所有语义字段相同 ⇒ 谁绑定到谁不产生任何下游差异。
- 因此 ④ **不构成台账事件**（不落 `duplicate_external_id`，不触发 `STOP_AUTO`）。
- `STOP_AUTO` 判据在**真交换**时**不触发**（交集 = `|old|`），这是**有意为之**，不是漏判。

### 15.4 三条硬禁止与两条硬保留

**禁止**：
1. **不得仅因重新排序后的 ordinal 不同而静默更新旧 `source_record` 的内容**（那会把 A 的内容写到 B 的身份上）。
2. **不得把原 `source_record_id` 自动绑定到另一条不同内容的记录**。
3. **不得删除旧行**（③ 也是置 `source_absent`，不是删）。

**保留**：
1. 原始数据：`raw_payload_json` 逐字保留（IDENTITY / 可追溯要求）。
2. 既有身份关系：`source_record_id`、`created_from_source_record_id`、`duplicate_ordinal` 在 `STOP_AUTO` 期间**一律不动**。

### 15.5 与 P0-03 的统一

第 0 行的"重复检测"（§2.3.1）与本节的多重集比对是**同一个机制**：组内 `content_hash` 多重集既决定谁被隔离，也决定谁能自动更新。**一处实现，两处语义**，不新增代码路径。

---

## 16. V0.2.2-r2 权威数字速查（N01–N18，逐字抄录）

**出处：V0.2.2 §0（行 21–46）**

> **口径纪律**：`暂存原始` = 七张暂存 CSV 的实测行数；`入库` = 执行 V2.1.1 隔离规则后进入目标表的行数。二者**不得混用**，凡出现必须带口径词。

| # | 项 | 暂存原始 | 入库 | 差 | 说明 |
|---|---|---:|---:|---:|---|
| N01 | `source_record` | 29,391 | 29,391 | 0 | 隔离不删行，只置 `is_active=false` |
| N02 | 其中 `is_active=false` | 0 | **3** | +3 | 2 CHGIS（`sr_0004941`/`sr_0004942`）+ 1 Pleiades edge |
| N03 | 活性源记录 | 29,391 | **29,388** | −3 | |
| N04 | `duplicate_ordinal=0` | **29,377** | 29,377 | 0 | 另 7 组 × 2 行 = 14 行，ordinal 1/2 各 7 行 |
| N05 | `historical_place` | 19,039 | **19,039** | 0 | CHGIS 15,746 + Pleiades 2,643 + MCGD 643 + WHG 7 |
| N06 | `historical_place_name` | **47,503** | **47,499** | −4 | 被隔离的 2 条 CHGIS 各派生 2 条名称 |
| N07 | `historical_place_location` | **18,103** | **18,101** | −2 | 被隔离的 2 条 CHGIS 各派生 1 条位置 |
| N08 | `data_quality_issue` | 12,631 | **12,831** | +200 | = 12,631 − 2（删 `licence_unconfirmed`【留痕：删枚举值】）+ 5 + 197 |
| N09 | `record_scope='place'` 记录 | **18,398** | **18,396** | −2 | **本轮新闭合**：18,398 − 2 隔离 = 18,396 = 19,039 − 643 ✓ |
| N10 | `record_scope` 全域 | place 18,398 / name 5,762 / location 2,468 / edge 2,763 | 同 | 0 | **仅 4 种，无第五种**（P1-03 白名单依据） |
| N11 | 无子行地点 | **315** | 315 | 0 | 全部 Pleiades，`canonical_name` 315/315 非空 |
| N12 | 无子行的源记录 | **8,682**（**口径 A**） | 8,682 | 0 | place 2,650（Pl 2,643 + WHG 7）/ name 2,513 / location 756 / edge 2,763。**口径 B**（子行含 `candidate_match` 两侧引用）= **8,218**；差 464 = place 74 + edge 390。**本文钉死口径 A**（R23） |
| N13 | name 表 `time_bound_type` | exact 21,614 / exact_or_bounded **2,360** / unknown 20,535 / **bounded 1,166** / snapshot 54 / tpq_taq 1,774 | 同 | 0 | 2,360 与 1,166 **不得互换** |
| N14 | 时间视图有跨度地点 | **17,469** / 19,039 | 见 §2.2.6 | 待复算 | 过滤改为"有效证据"后需重算（**未验证**） |
| N15 | 时间三值（**新设计口径**：只聚合 name+location） | `no_evidence` **1,570** / `single_point` 361 / `envelope…` 17,108 | 同 | 0 | 合计 19,039。**⚠️ 暂存 `historical_places` 列算出的 1,505 是旧口径（含 connection），偏低 65**（§2.2.6a） |
| **N16**（r1） | `no_evidence` 的构成（**暂存态干跑**） | 1,570 = **315** 无子行 + **1,255** 有子行但子行无年份（`time_derivation`: `none` 1,230 + `tpq_taq_of_children` 25） | 见 §2.2.6 | 0 | **T5 三项豁免后干跑 = 0**（§2.2.6） |
| **N17**（r1） | 重复组口径对照 | **漏 `parent_external_id`**：398 组 / 2,335 行；**五段键**：**7 组 / 14 行** | 同 | 0 | 差两个数量级；`ordinal=0` = **29,377**（§2.5.0） |
| **N18**（r1） | 被隔离的 3 条 | `sr_0004941` / `sr_0004942`（CHGIS）+ **`sr_0027175`**（Pleiades connection 20469） | 同 | 0 | 活性 **29,388**（§2.5.0） |

### 16.1 补充复算（R21–R32，V0.2.2 §5.1，行 978–995）

| # | 项 | 结果 |
|---|---|---|
| **R21** | `record_scope` 全域 | 仅 4 种：place 18,398 / name 5,762 / location 2,468 / edge 2,763 = 29,391 |
| **R22** | place 记录与地点数的闭合 | 18,398 − 2（隔离）= **18,396** = 19,039 − 643 ✓ |
| **R23** | 无子行的源记录 | **8,682**（**口径 A**：子行 = 名称行 + 位置行；`candidate_match` 是**待人工审核的候选**，不是已确认的派生子行，故不计入）。**口径 B** = **8,218**，差 **464** = `pleiades_connection_id` 390 + `pleiades_place_id` 74 |
| **R24** | 暂存是否已有失效状态 | `historical_place_names.csv`（13 列）、`historical_place_locations.csv`（22 列）**均无 `record_status` 列**；`historical_places.csv` 的 `record_status` 全为 `staging`（19,039/19,039）、`locked` 全为 false；**0 条 rejected / merged / locked** |
| **R25** | 0 子行源记录的构成 | CHGIS place 15,748 条**全部**派生子行；**Pleiades place 2,643 条全部不派生 name/location 子行**（实测 2,643/2,643 = 0 条有子行），其中 **74 条被 `candidate_match` 引用** |
| **R25b** | 8,682 的两种分组口径 | 按 `external_id_type`：`pleiades_connection_id` 2,763 / `pleiades_place_id` 2,643 / `pleiades_name_id` 2,505 / `pleiades_location_id` 756 / `whg_place_name_index` 8 / `whg_source_id` 5 / `whg_place_id` 2 = 8,682 ✓。按 `record_scope`：place 2,650 / name 2,513 / location 756 / edge 2,763 = 8,682 ✓ |
| **R26** | 换绑口径复核 | 三种实现三种逐次值（4.00 / 3.80 / 4.20），**均值收敛于 3.8–4.2，逐次值依赖实现**。⇒ "3.6 数学上不可能"的论证不成立 |
| **R26-不变量（INV-1）** | **只准断言这五条** | ① 取值域 ⊆ {0,2,4,6,8}；② 上限 8；③ 新方案恒 0；④ 场景 A 下旧方案恒 0；⑤ 内容相同组数恒 3 ⇒ 隔离条数恒 3 |
| **R27** | `raw_record_index` 文件内唯一性 | 14 个 `raw_file` 中 **7 个**（全为 WHG）索引不唯一；**7 个重复组内部均无并列** ⇒ 本轮 ordinal 不受影响 |
| **R28** | 原始顺序下旧/新方案的 ordinal 差异 | 根因是**摘要算法（md5 ↔ sha256）**，不是 `ensure_ascii` 也不是 `separators`。sha256 → 6 行 / md5 → 4 行 / md5+默认分隔符 → 2 行 |
| **R29** | data-auditor 三项复核的独立确认 | ① `whg_place_id` = 2 条（`sr_0029154` / `sr_0029159`），WHG 7 = 5 + 2 ✓；② 8,682（口径 A）/ 8,218（口径 B）/ 差 464 ✓；③ 与 2 条隔离记录相关的 `candidate_match` = **34 行 / 33 个键** |
| **R30** | `raw_payload_json` 是否已规范化 | 29,391 / 29,391 行与 `json.dumps(p, sort_keys=True, ensure_ascii=False, separators=(',',':'))` **逐字节相等**（0 行不等） |
| **R31** | T5 干跑（暂存态） | `no_evidence` 1,570 = 315 + 1,255（1,230 + 25）。三项豁免后 **T5 = 0** ✓ |
| **R32** | 五段键 vs 漏 `parent_external_id` | 漏 parent：398 组 / 2,335 行；五段键：7 组 / 14 行，`ordinal=0` = 29,377。隔离 3 条 = `sr_0004941` / `sr_0004942` / `sr_0027175` |

### 16.2 ⭐ `candidate_match` **不得进权威表**

```
candidate_match 暂存 53,137 / 隔离后 53,103  —— 是登记项 U18，待 Owner 拍板，不得写入权威数字表。
```

**出处：V0.2.2 §5.3 U18（行 1039）**，逐字抄录：
> `candidate_match` 总数：V0.2.1 写 **53,133**。实测**暂存原始 53,137 / 隔离后 53,103**；与 2 条隔离记录相关的候选行共 **34 行 / 33 个键**，按 Owner 决策 4（隔离记录不参与派生）应扣 34 ⇒ **53,103**；V0.2.1 只扣了 C09 同向收敛的 4 行。**以 data-auditor 审计报告为准，架构侧只登记、不自行改数**（该数不在本文 §0 权威表内）。

⇒ **本文件 §16 的 N01–N18 表中不含 `candidate_match` 任何数字**。53,137 / 53,103 只在 §16.2 作为**待裁定登记项**出现，编制交付物时**不得**把它并进权威数字表。

---

## 17. 抄录过程中发现的 V0.2.2-r2 内部不一致（及本文件的处理方式）

> 以下均为**抄录时逐项核对发现**，已在上方各节按"以更具体 / 更晚的定式为准"处理。**本文件不修改 V0.2.2-r2 任何内容，也不宣布这些不一致已解决。**

| # | 位置 | 不一致 | 处理方式 |
|---:|---|---|---|
| **I-1** | §13 约束条数 | V0.2.2 §4 第 11 项（行 956）写"**CHECK 总数 = 24 条**…编号范围 **C01–C26**"；但 §2.1.3（行 114–120）与 §2.5.0（行 527）后续又引入 **C27 / C28 / C29**，且 §5.2（行 1010–1011）把它们列为有效断言 ⇒ "编号范围 C01–C26"已过期 | §13.2 给**唯一数 27**（有效条目）= 24（可落库 SQL）+ 3（C27/C28/C29 断言级）。并写明"24"是**可落库 SQL 子集**的口径，两者不是矛盾而是子集关系。**建议提请 team-lead / Owner 在下一轮把 §4 第 11 项的"编号范围 C01–C26"改为 C01–C29** |
| **I-2** | `v_place_evidence` 列数 | §2.2.2（行 190–217）的 SELECT 列表实为 **11 列**（`place_id` / `source_record_id` / `evidence_role` / `source_is_active` / `source_inactive_reason` / `child_table` / `child_row_id` / `child_record_status` / `child_rejected_by` / `is_anchor` / `is_canonical_row`），但 §6 第 3 行（行 1052）写"**10 列**" | §14.1 **按 SELECT 列表逐列给出 11 列**，不采用"10 列"这个总数。**建议提请核对 §6 第 3 行** |
| **I-3** | 视图派生列总数 | §1（行 66）写"新视图派生列 **+8**"；§2.2.2 末尾（行 220）写"视图新增 **6 个派生列**"并逐个列出；§2.8 又加 `is_canonical_row`（1）；§2.2.6（行 325）又加 `child_rows_total` / `valid_child_rows` / `all_children_rejected`（3）。6 / 7 / 8 / 10 四个口径并存 | §13.3 **只写"新视图派生列（逐列名见 §14，不给总数）"**；§14 按视图逐列列出，**不给合计**。总数待裁定 |
| **I-4** | 时间视图过滤 | V2.1 基线（`CORE_DATA_MODEL_V2.1.md` 行 413–427）的 `v_place_time_span` 用 `c.record_status = 'published'`；V0.2.1 §2.6.1（行 1364）改为 `<> 'rejected'`；V0.2.2 §2.2.6（行 316–322）再加 `sr.is_active` | §14.3 按 **V0.2.2**（`<> 'rejected'` **AND** `sr.is_active`）抄录，并**显式标注"不是 `'published'`"** |
| **I-5** | `record_status` 值数 | V0.2.1 §4.2 枚举表（`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` 行 1767）写"`record_status`（place）| **4** | 不变"；V0.2.2 §2.1.1（行 76）与 §4.1 K5（行 969）写 **3 值**（`staging` / `rejected` / `merged`） | 按 **V0.2.2 的 3 值**抄录（§7.1）。注：子表（`historical_place_name` / `location`）的 `record_status` 在 V2.1 基线中是 `staging`/`published`/`rejected` 三值——**地点与子表的 `record_status` 值域不同，编制交付物时必须分别写明，不得合并成一套** |
| **I-6** | 业务键写法 | V2.1 基线（`CORE_DATA_MODEL_V2.1.md` 行 74/276）写 `UNIQUE (dataset_id, record_scope, external_id, occurrence_key)`（**四段**，用 `occurrence_key` 承载父级+序号）；V0.2.2 C01（行 525）写**五段**（`parent_external_id` + `duplicate_ordinal` 各自独立成段） | §1 按 **V0.2.2 五段**抄录。若交付物需引用 V2.1 的四段写法，**必须同时标注 V0.2.2 §2.5.0 已改为五段** |
| **I-7** | 未编号约束 | `CORE_DATA_MODEL_V2.1.md` 行 279 有一条**未编号**的 `CHECK (is_active OR occurrence_key <> '')`，不在 C01–C29 之列 | §13 **不计入** 27 / 24 任一数字，仅在 I-7 登记。其意图已被 **C20 + C29** 覆盖 |
| **I-8** | `import_batch.status` | V0.2.1 §4.2（行 1771）写"6 值，不变"，但**未列值域**；值域只在 `CORE_DATA_MODEL_V2.1.md` 行 235 出现 | §11.3 从 V2.1 基线抄录 6 值并**标注出处行号**，便于交付物引用 |
| **I-9** | `issue_type` 19 值清单 | V0.2.1 §4.2（行 1769）只写"19"与"删 `licence_unconfirmed`"【留痕：删枚举值】，**未给 19 值清单**；清单需从 `CORE_DATA_MODEL_V2.1.md` 行 642 的 20 值反推 | §11.2 给出**反推后的 19 值清单并标注推导方式**，供交付物直接取用 |
| **I-10** | `derivation_kind` 出处 | V0.2.2 §0 N15（行 41）给出三值计数，但**三值定义本身不在 V0.2.2 正文**，在 V0.2.1 §2.6.4 | §10 从 V0.2.1 §2.6.4 抄录定义 + 判据 + 计数，并**标注 V0.2.2 未覆盖、以 V0.2.1 为准** |

> **以上 10 项均为"登记 + 按效力顺序取用"，本文件未对 V0.2.2-r2 做任何修改，也未宣布任何一项已关闭。**

---

## 18. 编制交付物时的硬约束提示（抄自 V0.2.2，便于取用）

| 项 | 定式 |
|---|---|
| **禁用词扫描（K3）** | 交付物不得出现 `place_record` / `attribution_text` / `citation_text`【留痕：禁用词清单】；`DATA_PROVENANCE` 不得出现 `license` / `redistributable` / `SPDX` / `可发布` / `attribution`（§2.6.1、§3.3）。**⭐ 豁免规则**：凡因「已删除列逐列清单 / 明确不做 / 禁用词清单 / 删枚举值说明」四类语境而引用旧名并逐处标注【留痕】者，**不计入命中**（与 CORE 附录 B 的留痕豁免规则一致） |
| **口径词（K4 / F18）** | 47,503/47,499、18,103/18,101、315、29,391 必须带"暂存 / 入库"口径词；只写一个数即判缺陷 |
| **引用纪律（CIT-1′）** | 引 V0.2.1 §2.1.4a / G1-02 必带 V0.2.2 §2.9 更正，且不得单独转述旧理由。判定式：CIT-1a′（正则 `平均\s*3\.6\|3\.6\s*行\|3\.6\s*数学`，邻行须含更正标注）/ CIT-1b′（`数学上不可能` 在八份交付物中出现次数 == 0，豁免集写在单元格内）/ CIT-1c′（含 `ordinal 不稳定` 或 `行序一换就换绑` 的段落同段必须含 `场景 B`） |
| **表达式逐字一致（CIT-2′）** | `content_hash` 规范化表达式三处（V0.2.2 §2.5.6 / CHANGELOG D-03 / 交付物）逐字一致；完整串 `len == 85`、`sha1 == 9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5` |
| **`mask` 措辞更正（B4）** | V0.2.1 §2.7.2a 写"含词元 3,778"。**交付物一律改写为 `year_after_which\|year_before_which` 3,778**（另一支 710 同理需写明具体词元）。理由：全部 `has_token` 是 38,510，"含词元"会被读成这个总数，与 3,778 差一个量级 |
| **来源追溯六项正当用途（B-01）** | ① 原始数据定位；② 数据更新；③ 数据纠错；④ 记录身份；⑤ 数据转换过程；⑥ 数据质量问题排查。**不得**写成"能不能用这批数据"的判据 |
| **不得写成断言（NON-1）** | "未打乱基线换绑行数 = 6（sha256）/ 4（md5）/ 2（md5+默认分隔符）"、以及各实现的**逐次值** |
| **未验证项不得预置通过结论** | §5.3 全部条目 + C27/C28/C29 的**建库后**行为 + `place_grain` 落库后的白名单实际命中（V3'/V4/V5） |

---

> **本文件到此结束。它是 V0.2.2-r2 的抄录件，不是新增设计；凡有疑问，一律回到 V0.2.2-r2 原文。**
