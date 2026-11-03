# 核心数据模型 V2.1.1

**项目**：《世界历史时空画布》
**版本**：2.1.1（取代 `CORE_DATA_MODEL_V2.1.md` 2.1.0；V2 / V2.1 文件保留原样不覆盖）
**性质**：设计文档。**本轮不含任何数据库施工**——无 DDL 执行、无 Migration、无数据导入。
**事实基线**：`设计资料/P0收敛/WB-002/normalized/` 七张暂存 CSV 的逐行复算。
**权威来源**：`V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md`（下称 **V0.2.2**，1,127 行）；`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md`（V0.2.1，V0.2.2 未覆盖处以它为准）；`V2.1/CORE_DATA_MODEL_V2.1.md`（V2.1）；`CORE_DATA_MODEL_V2.md`（V2）。
**共享定义基线**：`V2.1.1/正式交付/_build/SHARED_BASELINE_V2.1.1.md`（内部编制参考，**不参与八份交付物计数**，与 V0.2.2 冲突以 V0.2.2 为准）。

> **效力顺序**：**V0.2.2 > V0.2.1 > V2.1 > V2**。
> **章节编号**：沿用 V2.1 的 11 节编号（0–11）以便逐节对照；本版在 §5 下**新增 §5.10「派生视图」**（V2.1 的 §5 只有表定义）。

---

## 0. 本文件回答什么

V2.1 的模型骨架是对的：九张表、业务键、候选与合并分离、地点无时间列、位置与名称各有时间。V2.1.1 **不推翻这些**，只做一件事：

> **把 V0.2.2-r2 已经定下的定式，落成一份可直接施工的模型定义——逐表逐列、三视图**可执行** SQL（无占位符）、约束全集、实测基线，以及一张不许被写成 PASS 的验证清单。**

本版相对 V2.1 的实质变化只有四组：

| 组 | 变化 | 权威出处 |
|---|---|---|
| ① 业务键 | 四段 → **五段**（`parent_external_id` 升为必需段 + `duplicate_ordinal` 独立成段） | V0.2.2 §2.5.0（行 521–572） |
| ② 新增列 | name/location 各加 `rejected_by`；`data_quality_issue` 加 `first_batch_id`/`last_batch_id`/`occurrence_count`；`historical_place` 加 `dataset_id`/`grain_key` | V0.2.2 §2.2.1、§2.4.2；V0.2.1 §2.5.5 |
| ③ 三视图 | `v_place_evidence` 重写为 **11 列**（`is_canonical_row` 由**外层窗口定序**计算，见 §5.10.1）；`v_place_liveness` 改为 **8 值** `liveness`；`v_place_time_span` 过滤由 `'published'` 改为 **`<> 'rejected'` + `sr.is_active`** | V0.2.2 §2.2.2 / §2.2.4 / §2.2.6 |
| ④ 许可相关 | `data_dataset` 的 **9 列许可相关列全部删除**；许可门禁**废除** | V0.2.1 §4.2（行 1775）、§3.3 |

**本版的一条硬原则（沿用 V2.1 并收紧）**：模型里每一个 `CHECK` 枚举值，必须在暂存数据里有对应取值或明确的空集说明；每一个暂存列，必须能说出它落到哪一列、或被丢弃的理由。**说不出来的，就是设计缺口，不是数据脏。**

---

## 1. 修订清单（相对 V2.1）

| # | 项 | V2.1 | V2.1.1 | 权威出处 |
|---|---|---|---|---|
| **B1** | 业务唯一键 | 四段 `(dataset_id, record_scope, external_id, occurrence_key)` | **五段** `(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` | V0.2.2 §2.5.0 / C01 |
| **B2** | `parent_external_id` | 可为 NULL（CHGIS/WHG 无父级 ⇒ NULL） | **必需段**。无父级写哨兵 `'-'`；不得 NULL 兜底、不得空串 | V0.2.2 C29（行 527–534） |
| **B3** | 重复行身份 | `occurrence_key = parent#ordinal` | `duplicate_ordinal`（0 = 唯一组；≥1 = 组内名次，按 `(content_hash ASC, raw_record_index ASC)` 定序） | V0.2.2 §2.5.0 |
| **B4** | `content_hash` | `sha256(canonical_json(raw_payload))`（未写死表达式） | **`sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))`**，逐字写死 | V0.2.2 §2.5.6（行 625–643） |
| **B5** | 台账指纹 | 无单一唯一键（两条部分索引） | `UNIQUE(issue_fingerprint)`，**md5 + JSON 数组六段含 `place_id`** | V0.2.1 §2.5.5；V0.2.2 §2.5.7 |
| **B6** | 台账语义 | 未声明 | **语义 A（唯一身份）+ 事件伴生列**：重复发现 `UPDATE` 不 `INSERT` | V0.2.1 §2.5.5（行 1289–1304） |
| **B7** | 子行 reject 来源 | 无 | 新增 **`rejected_by`**（name/location 各 1 列，值域 `auto`/`manual`）+ C25/C26 | V0.2.2 §2.2.1 |
| **B8** | `liveness` | 7 值 | **8 值**（新增 `mixed_inactive`） | V0.2.2 §2.1.2 |
| **B9** | `evidence_role` | `place_record`（G4-01）与 `creator`（SQL）并存 | **统一 3 值** `creator`/`name`/`location`；`place_record` 为**禁用词** | V0.2.2 §2.6 |
| **B10** | 建点判据 | `record_scope <> 'place'`（过宽，默认放行 `edge`） | **白名单 + `place_grain` 显式声明**；未知类型整批 `failed` | V0.2.2 §2.7 |
| **B11** | 时间视图过滤 | `record_status = 'published'` | **`record_status <> 'rejected'` AND `sr.is_active`** | V0.2.2 §2.2.6 |
| **B12** | `historical_place` | 无 dataset 列 | **新增 `dataset_id` + `grain_key`** + `UNIQUE(dataset_id, grain_key)` | V0.2.1 §2.4.2 |
| **B13** | `record_status`（地点） | 4 值 | **3 值** `staging`/`rejected`/`merged` | V0.2.2 §2.1.1 |
| **B14** | 许可模型 | `data_dataset` 9 列许可相关 + 许可门禁 | **9 列全部删除 + 门禁废除**；不做授权/再分发判断 | V0.2.1 §4.2（行 1775）、§3.3 |
| **B15** | `issue_type` | 20 值 | **19 值**（删 `licence_unconfirmed`）**【留痕】** | V0.2.1 §4.2（行 1769） |
| **B16** | `canonical_name` 追溯 | 提法有，视图无列 | 视图派生列 **`is_canonical_row`** + 定序式（由外层窗口函数**实际计算**）；**315 个（入库口径）**无子行地点**不制造名称子行** | V0.2.2 §2.8 |

> **⚠️ 关于"新增列 +2"的常见误读（重要）**：
> V0.2.2 §1 写的"新列 **+2**（`rejected_by` × 2 表）"是 **V0.2.2 相对 V0.2.1** 的增量，**不是 V2.1.1 相对 V2.1 的增量**。
> V2.1 的 `CORE_DATA_MODEL_V2.1.md` 里**没有** `inactive_reason` / `inactive_at` / `inactive_in_batch_id` / `duplicate_ordinal` / `dataset_id` / `grain_key` / `first_batch_id` / `last_batch_id` / `occurrence_count` / `issue_fingerprint`——这些是 V0.2 / V0.2.1 / V0.2.2 三轮设计陆续引入的，**在 V2.1 交付物里根本还不存在**。
> 八份正式交付物是 **V2.1.1 相对 V2.1**，必须把三轮的全部增量编进去。**写"＋2"等于只编了 V0.2.2 那一轮。**
> ⇒ **完整的列变更清单见 §5.0**（逐列标 增 / 删 / 改名 / 约束变化 + 出处章节号，**不给任何合计数**）。

---

## 2. 通用约定

| 项 | 约定 |
|---|---|
| 时间纪年 | 一律**天文纪年整数**：公元前 1 年 = 0，公元前 750 年 = −749。转换 `astro = year + 1 if year < 0 else year` |
| 坐标 | 一律 EPSG:4326，经纬度顺序（lon, lat）。源轴序不在此层处理，由 `axis_order_verified` 单独记录 |
| 文本 | `text` 不做 Unicode 归一化。繁体/异体字是数据不是噪声 |
| 空值 | `''`（源里是空串）与 `NULL`（源里没有这个字段）语义不同，**不得互相替代**。**空值不做 `coalesce` 归一** |
| 主键 | 全部 `bigint identity`。**例外（2 个自然键样本）**：① `data_dataset.dataset_id` 为 V2 既有的 `text` 自然主键（§5.2）；② `data_source.source_id` 亦为 `text` 自然主键（§5.1）。其余表为 `bigint identity`。暂存物的 `hp_*` / `sr_*` / `loc_*` / `nm_*` / `cm_*` / `ds_*` **是交付物标识，不是主键**，见 §3 |
| 布尔 | 暂存 CSV 用 `true`/`false` 字符串，入库转 `boolean`。**禁止把 `''` 当 `false`** |
| 哨兵 | 无父级概念的 `parent_external_id` 写 **`'-'`**（不是 NULL、不是空串）。该哨兵是**值域外保留字**，只能在 `data_dataset` 或一张常量表里**声明一次**（C29 ④） |
| 迁移 | 版本化 Migration，禁止 `latest` tag。本轮不产出 SQL |

---

## 3. 标识策略：三层，互不混用

| 层 | 用途 | 形态 | 可变性 |
|---|---|---|---|
| **数据库主键** | 表内引用、外键、回滚定位 | `bigint` | 永不改（唯一例外：无） |

> **主键例外（2 个自然键样本）**：① `data_dataset.dataset_id` 是 V2 既有的 `text` **自然主键**（§5.2）；② `data_source.source_id` 同为 `text` **自然主键**（§5.1，CHECK IN `chgis`/`pleiades`/`whg`/`mcgd`，行数 4）。二者承载的都是"业务代号"（数据集代号 / 数据源代码），改成代理键只会让全库多一次 join 且失掉可读性。**除这两张表外，其余表的主键一律 `bigint identity`。**（沿用 V2 / V2.1 基线，非本版新引入）
| **业务键** | 跨部署重放、增量比对、追溯 | **五段** `(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` | 随源变；源变了就是新键 |
| **交付物标识** | 暂存 CSV 内部互相引用、报告里指名道姓 | `hp_001496` / `sr_0004834` | 仅本批有效，**不得离开暂存包** |

**为什么暂存 `hp_*` 不能当主键**：它是有序流水号，重跑一次流水线就可能整体位移。V2 已规定"任何离开数据库的产物不得用 `place_id` 表达地点"，V2.1.1 补一句：**暂存包的 `hp_*` 也一样，不得进任何持久化结构**。导入器读入后立刻建立 `hp_* → place_id` 的内存映射，用完即弃。

> **V2.1 → V2.1.1**：业务键由四段改为五段（B1）。凡引用 V2.1 四段写法处，**必须同时标注「已被 V0.2.2 §2.5.0 改为五段」**。

---

## 4. 键策略

### 4.1 业务唯一键（**五段**，C01）

```sql
UNIQUE (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)
```

| 段 | 解决的问题 | 缺了会怎样 |
|---|---|---|
| `dataset_id` | 不同数据集的 ID 空间独立（CHGIS `SYS_ID` 与 Pleiades `id` 都是数字） | 跨数据集误判为同一记录 |
| `record_scope` | 同一数据集内 place / name / location / edge 各有自己的 ID 空间（Pleiades 的 `981524` 既是 place id 又是 connection id） | 同名不同物 |
| **`parent_external_id`** | **同一 `external_id` 在不同父记录下重复出现**（Pleiades `names.csv` 的 `id` 是 slug：`argita` / `isamnion-akron` / `ouidoua` / `arabia` 各有 2 条不同父级；connection 用 title 作 id：`urartu` 11 条、`untitled` 12 条、`via-appia` 7 条） | **398 组 / 2,335 行**被误判为重复（真实只有 **7 组 / 14 行**）⇒ 数百条被误隔离 |
| `external_id` | 源声明的 ID | — |
| `duplicate_ordinal` | 同一四段前缀下的第几行 | 7 组 × 2 行无法区分 |

### 4.2 `parent_external_id` 是**必需段**（C29）

```
C29  parent_external_id 为必需段：
     ① 任何情况下不得省略、不得以 NULL 兜底、不得用空串代替；
     ② 无父级概念的数据集（CHGIS place）写入哨兵值 '-'（不是 NULL），
        以保证 UNIQUE 仍然生效（Postgres 的 UNIQUE 对多列 NULL 不去重）；
     ③ 派生失败 ⇒ 整批 failed（与 A12 同一处置），不是默认放行；
     ④ 哨兵值约束：哨兵必须是 parent_external_id 值域之外的保留字，
        且只能在 data_dataset 或一张常量表里声明一次（不得散落在导入逻辑各处）。
        若将来某数据集的 parent 恰为 '-' ⇒ 换哨兵是一次性常量替换，不得牵动五段键逻辑。
```
（V0.2.2 行 527–534）

**为什么不能是 NULL / 空串**：Postgres 的 `UNIQUE` 对多列 `NULL` **不去重** ⇒ 五段键会退化成四段键，重复检测**静默失效**（不报错）。空串会与"真实空值"混淆。

**漏段的真实后果（已验证，V0.2.2 行 539–545）**：

| 分组口径 | 重复组数 | 涉及行数 | `ordinal=0` |
|---|---:|---:|---:|
| 三段键 `(dataset_id, external_id_type, external_id)`（**漏 parent**） | **398** | **2,335** | 27,056 |
| 五段键（含 `parent_external_id`） | **7** | **14** | **29,377** |

> 差两个数量级。**这是静默数据损坏，不是报错。**

**`parent_external_id` 的取值来源（含 D-5 补全规则）**：

| 情形 | 取值 | 覆盖行数（**暂存原始**口径） |
|---|---|---:|
| Pleiades name / location / connection（`raw_payload.place_id` 存在） | `raw_payload.place_id` | 9,802 |
| MCGD（`raw_payload.LocID` 存在） | `raw_payload.LocID` | 960 |
| WHG `whg_geom_index`（payload 顶层**有**父键） | 父键 | **3** |
| **`record_scope = 'place'`**（该记录**本身即实体、无父级**） | **哨兵 `'-'`** | **18,398** |
| payload 顶层**取不到** `place_id` / `LocID` 者（`whg_place_name_index` / `whg_geometry`） | **哨兵 `'-'`** | **228** |
| **合计** | | **29,391** ✓ |

> **⚠️ D-5 补全规则（本版新增，属补全项不是新设计，待 QA 复算 → 附录 B V-5）**：
> C29 ② 原文只规定了「无父级概念的数据集（CHGIS place）写入哨兵 `'-'`」，覆盖 15,748 行；**仍有行无规则可依**。
> 本版补全为：**凡 `record_scope='place'` 的记录——它本身即实体、无父级——一律落哨兵 `'-'`**（覆盖 **18,398** 行，与 V0.2.2 §0 N10 的 place 全域一致）；payload 顶层确无 `place_id`/`LocID` 的 WHG 子记录同样落 `'-'`（228 行）。
>
> **权威口径（实测，判据 = `raw_payload_json` 顶层是否含 `place_id` 或 `LocID`）**：
>
> | 项 | 行数 |
> |---|---:|
> | **可派生** | **10,765** = Pleiades 9,802（name 4,579 + connection 2,763 + location 2,460）+ MCGD 960 + **`whg_geom_index` 3** |
> | **不可派生（落哨兵）** | **18,626** = place 全域 18,398 + `whg_place_name_index` 223 + `whg_geometry` 5 |
> | 合计 | **29,391** ✓ |
>
> ⛔ **`whg_geom_index` 那 3 行 payload 顶层确实有父键，是【可派生】的，不得计入缺口。**
>
> **「缺口 2,878」的准确口径（相对 C29 ② 原文，不是相对零）**：
> ```
> place 全域 18,398 − C29② 原文已覆盖的 CHGIS place 15,748 = 2,650
>     （= pleiades_place_id 2,643 + whg_source_id 5 + whg_place_id 2）
> + WHG 子记录缺口 228（whg_place_name_index 223 + whg_geometry 5）
> = 2,878   ← 「相对 C29② 原文的缺口」
> ```
> ⇒ **18,626 与 2,878 是两个不同口径，都对**：18,626 = 落哨兵总行数；2,878 = 其中 C29 ② 原文未覆盖的部分。**交付物引用时必须写明用的是哪一个。**
> ⇒ 我先前报的「可派生 10,762 / 缺口 231」**不成立**（误把可派生的 `whg_geom_index` 3 行挪进了缺口），**已按实测更正**。列为附录 B **V-5** 待 QA 复算。

**真实数据的 7 组明细**（V0.2.2 行 549–557）：

| dataset | `external_id_type` | parent | `external_id` | n | 内容 | 处置 |
|---|---|---|---|---:|---|---|
| chgis_v6_prefecture_points | chgis_sys_id | — | 35000 | 2 | 相同 | 隔离 `sr_0004941`（ordinal **2**） |
| chgis_v6_prefecture_points | chgis_sys_id | — | 35001 | 2 | 相同 | 隔离 `sr_0004942`（ordinal **2**） |
| pleiades_gis_4_1_slice | pleiades_name_id | 92117 | argita | 2 | **不同** | ordinal 1,2 **均入库，不隔离** |
| pleiades_gis_4_1_slice | pleiades_name_id | 92153 | isamnion-akron | 2 | **不同** | 同上 |
| pleiades_gis_4_1_slice | pleiades_name_id | 92175 | ouidoua | 2 | **不同** | 同上 |
| pleiades_gis_4_1_slice | pleiades_name_id | 981506 | arabia | 2 | **不同** | 同上 |
| pleiades_gis_4_1_slice | pleiades_connection_id | 98909 | 20469 | 2 | 相同 | 隔离 `sr_0027175`（ordinal **2**） |

### 4.3 `duplicate_ordinal` 的生成与隔离判据

| 项 | 定式 |
|---|---|
| 单行组 | `duplicate_ordinal = 0` |
| 多行组（n ≥ 2） | 按 **`(content_hash ASC, raw_record_index ASC)`** 定序，取 **1..n** |
| 语义 | **内容的函数**，不是身份。"ordinal 绑定了哪一行"没有语义；真正需要保护的是"`source_record_id` 绑定了哪份内容" |
| `raw_record_index` 的作用 | **只能**在 `content_hash` 完全相等时打破并列，**不得**参与常规定序；**不保证文件内唯一**（14 个 `raw_file` 中 7 个不唯一，全为 WHG）⇒ 不得作为定序键或唯一性依据（V0.2.2 §2.5.5） |

**隔离判据（写死）**：

```
组内按 (content_hash ASC, raw_record_index ASC) 定序后：
  · 同一 hash 子组内【最小 ordinal】保留
  · 该子组内后续相同 hash 的行 ⇒ 隔离
  · 不同 hash 的行 ⇒ 均保留（不隔离）
```

> ⛔ **禁止"只比 `ordinal = 1`"**。
> ⛔ **禁止"要求整组内容完全相同才隔离"**。实测 `external_id=20469` 出现在两个父级：`parent_external_id=98909` 的两行属于同一四段前缀组且内容相同，隔离 `sr_0027175`；`parent_external_id=98930` 的另一行属于不同组，必须独立保留。若漏掉 `parent_external_id`，就会把跨父级记录误合并。（V0.2.2 行 562–564 的重复隔离原则；分组事实以本轮 QA 复算为准）

**隔离不是删除**：`is_active=false` + `inactive_reason='duplicate_quarantine'`，**不派生任何子行**，原始行与原因完整保留（C21/C22）。它先于 O1 的普通派生，也**不得**通过 O7 解除人工保护恢复（V0.2.2 §2.3.1 第 0 行）。

### 4.4 `content_hash`（逐字写死）

```
content_hash = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))   -- 规范定义（唯一）
sha256(raw_payload_json 逐字节)                                                        -- 等价形式（当且仅当 normalize.py:306 约定不变时）
```
（V0.2.2 行 931–934）

- **规范化表达式是主规范**，逐字节版降为等价形式。理由：逐字节版的稳定性依赖**上游 `normalize.py:306` 的一个约定**，不是自保证的；该行一旦被改，29,391 条 `content_hash` **全部改变** ⇒ ordinal 大规模重排 ⇒ **STOP_AUTO 误触发、整批 SKIP_UPDATE**。
- **等价条件必须标注**：仅当 `normalize.py:306` 保持 `sort_keys=True, ensure_ascii=False, separators=(",",":")` 时等价。实测暂存 29,391/29,391 行与该表达式输出**逐字节相等**（0 行不等，R30）。
- **可扫描指纹（CIT-2′）**：完整串（带算法外壳）`len == 85`、`sha1 == 9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5`；内层 `json.dumps(...)` `len == 77`、`sha1 == 781f68645c4e2e3af4b18871f2f5b7848c5f3798`。

**六条沿用规则**（`DATA_IMPORT_UPDATE_RULES` §1.2）+ V2.1 补充的第 7、8 条：

7. **`raw_payload` 的键名保持源文件原样**（CHGIS 县级层是 `ENT_DATE`，府级层是 `END_DATE`）。**不做键名归一**——归一会让哈希无法回答"字段名变了没有"。
8. **`raw_payload` 不含导入器补齐的任何字段**（`record_scope`、`parent_external_id`、`duplicate_ordinal`、批次号、时间戳都不进哈希），否则同一份文件重导哈希必变。

> **⚠️ 施工级硬提醒 H1**：`normalize.py:306` 一旦改动，**必须回归 `content_hash`**。该行是本系统 `content_hash` 等价性的唯一支点；改动而不同步回归 ⇒ 29,391 条哈希全变 ⇒ ordinal 大规模重排 ⇒ **STOP_AUTO 误触发、整批 SKIP_UPDATE**（静默，不报错）。

### 4.5 `issue_fingerprint` 与两种摘要算法并存（ALG-1）

```sql
-- data_quality_issue.issue_fingerprint（PostgreSQL 内算）
GENERATED ALWAYS AS
  md5(jsonb_build_array(source_record_id, dataset_id, place_id,
                        issue_type, field_name, observed_value)::text) STORED
```

| 项 | 定式 |
|---|---|
| 段数 | **六段**，`place_id` 是**必需段** |
| 编码 | **JSON 数组**（不用字符串拼接）：`null` / `""` / 含 `\|` 的值三者互不相同 |
| 含 `batch_id`？ | **不含**（含了每导一批新增 197 行，台账自我膨胀） |
| 空值归一 | **不做 `coalesce`**：`NULL` 与 `''` 必须可区分 |
| `observed_value` 口径 | 暂存列原始字符串**单值**；空值渲染字面量 `NULL`；**重算值进 `notes`** |
| 唯一性验证 | 六段（含 `place_id`）⇒ **197** 个不同指纹 / 0 冲突；去掉 `place_id` ⇒ **45** 个 / 24 冲突组 / 176 行 |

**两种摘要算法并存是【有意设计】，不可互换、不可统一**（ALG-1，V0.2.2 §2.5.7）：

```
content_hash       : sha256   -- 内容身份。导入器算。用于 ordinal 定序、跨版本稳定、重复隔离判定
issue_fingerprint  : md5      -- 台账去重键。PostgreSQL 内算
```

> ① `issue_fingerprint` 是 V0.2.1 §2.5.1 **已验收**的定义，197 条历史指纹已按 md5 算好 ⇒ 改算法会使这 197 条**全部对不上**；② 两者语义不同（内容身份 / 台账去重）、计算位置不同（导入器 / PostgreSQL）；③ 改的成本 > 收益。
> **后人若提出统一，先问：197 条已算指纹怎么办？没有答案就不要动。**

### 4.6 重复外部 ID 的处置（`QUARANTINE`，不是 `REJECT`）

```
写入 source_record(..., duplicate_ordinal=2, is_active=false,
                   inactive_reason='duplicate_quarantine',
                   inactive_at=now(), inactive_in_batch_id=:batch_id)
写 data_quality_issue(issue_type='duplicate_external_id', severity='warning',
                      action_taken='preserved_and_flagged', ...)
不派生 historical_place / location / name / candidate
```

**为什么不是 REJECT**：`source_record` 是"所有规范化行的追溯终点"。拒收 ⇒ 这条源记录在库里不存在，`raw_payload` 这份原始证据一起消失。`is_active=false` 已达成本效果（不参与派生、不参与导出、不参与计数），同时保留"源端确实有重复"这一事实。**`is_active=false` 与"不存在"在下游行为上等价，在审计上不等价。**

### 4.7 STOP_AUTO 与 `duplicate_external_id` 台账复用

```
判据（写死）：
  若 |old| = |new| 且 |old ∩ new| < |old| − 1
     ⇒ 有 ≥2 条同时变化，无法把新旧内容一一对应 ⇒ 停止自动更新（STOP_AUTO）
```

实现（**不加新表、不加新列**）：
1. 该组**整组 `SKIP_UPDATE`**；
2. 落 **1 条 `duplicate_external_id`** 台账（**复用既有类型，不新增枚举值**），`observed_value` 写 `old_multiset` / `new_multiset`，`notes` 写"ordinal 无法唯一对应，等待人工核验"；
3. 每次导入重判；仍无法对应 ⇒ 再 `SKIP_UPDATE` + `occurrence_count += 1`。

**三条硬禁止**：① 不得仅因重排后 ordinal 不同而静默更新旧行内容；② 不得把原 `source_record_id` 自动绑定到另一条不同内容的记录；③ 不得删除旧行。
**两条硬保留**：① `raw_payload_json` 逐字保留；② `STOP_AUTO` 期间 `source_record_id` / `created_from_source_record_id` / `duplicate_ordinal` **一律不动**。

---

## 5. 表定义

九张表 + 三张派生视图（§5.10）。**逐表列出全部列**，未提及的列与 V2.1 相同、以 V2.1 为准。

### 5.0 ⭐ V2.1 → V2.1.1 列变更清单（逐列，**不给合计数**）

> 本表是八份交付物编制列定义的**唯一依据**。逐列标注 增 / 删 / 改名 / 约束变化 + 出处。**不写"新增 N 列"这类合计数**（沿用裁定 3：合计数是口径陷阱）。

| 表 | 列 | 变更 | V2.1 状态 | V2.1.1 状态 | 出处 |
|---|---|---|---|---|---|
| `import_batch` | `blocked_count` | **新增** | 无 | `integer NOT NULL DEFAULT 0`；记录级跳过（`locked` / `manual_edited_fields` / `last_batch_id` 不符）时 +1 | V0.2.1 G3-04（行 336）；V0.2.2 §2.4.3（行 509） |
| `source_record` | `parent_external_id` | **约束变化** ⭐ | 可空派生列（`CORE_DATA_MODEL_V2.1.md:265`） | **五段键必需段**；无父级落哨兵 `'-'`；**NOT NULL**；不得空串 | V0.2.2 §2.5.0 / **C29** |
| `source_record` | `duplicate_ordinal` | **新增** | 无 | `integer NOT NULL DEFAULT 0`；五段键必需段 | V0.2.2 §2.5.0 / C01 / C20 |
| `source_record` | `inactive_reason` | **新增** | 无 | `text` 可空，CHECK IN 3 值 | V0.2.1 §4.3 **C19** |
| `source_record` | `inactive_at` | **新增** | 无 | `timestamptz` 可空 | V0.2.1 §4.3 **C21** |
| `source_record` | `inactive_in_batch_id` | **新增** | 无 | `bigint` FK → `import_batch`，可空 | V0.2.1 §4.3 **C22** |
| `source_record` | `occurrence_key` | **删除** ⭐ | `text NOT NULL DEFAULT ''`（`CORE_DATA_MODEL_V2.1.md:263`） | **删除**。被 `parent_external_id` + `duplicate_ordinal` 取代（**V0.2.2 全篇 `occurrence_key` 零命中**） | V0.2.2 §2.5.0 / C01；取代关系须写入 CHANGELOG |
| `source_record` | 业务唯一键 UNIQUE | **约束变化** | 四段 `(dataset_id, record_scope, external_id, occurrence_key)` | **五段** `(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` | V0.2.2 **C01** |
| `historical_place` | `dataset_id` | **新增** ⭐ | **无**（V2.1 §5.2.1 规则 1 明令"不带 dataset 列"） | `text` FK → `data_dataset`，**NOT NULL** | Owner 决策 5；V0.2.1 §2.4.2 |
| `historical_place` | `grain_key` | **新增** ⭐ | **无**（grep 零命中） | `text NOT NULL`；与 `dataset_id` 组成 `UNIQUE`（C04） | V0.2.1 §2.4.2 |
| `historical_place` | `record_status` | **约束变化** | 4 值（含 `published`） | **3 值** `staging`/`rejected`/`merged` | V0.2.2 §2.1.1 |
| `historical_place_name` | `rejected_by` | **新增** | 无 | `text` 可空，CHECK IN (`auto`,`manual`) | V0.2.2 §2.2.1 / **C25/C26** |
| `historical_place_location` | `rejected_by` | **新增** | 无 | 同上 | 同上 |
| `historical_place_location` | `source_rule_vocabulary` → `source_time_columns` | **改名** | `source_rule_vocabulary`（`CORE_DATA_MODEL_V2.1.md:475`） | **改名**为 `source_time_columns`；语义改为「该行来源文件声明了哪些时间列（列级掩码），逐字保留；**不是**本行实际使用的规则」 | V0.2.1 §2.7.1（行 1449–1451）/ §5.6（行 1626） |
| `historical_place_name` | `source_time_columns` | **新增** | 无（V2.1 name 表无任何时间规则列） | `text NOT NULL DEFAULT ''`；同类型同语义。收纳 V2.1 会丢弃的 **2,074 行** name 侧 `time_rule_code` 掩码 | V0.2.1 §2.7.1（行 1449–1451）/ §5.7（行 1627） |
| `data_quality_issue` | `dataset_id` | **约束变化** | `text` FK → `data_dataset`，**NOT NULL**（`CORE_DATA_MODEL_V2.1.md` §5.9） | **改为可空**（`text`，FK → `data_dataset`，可空）。数据集级问题直接填；地点级问题可空，由 C11/C12 保证可归因；人工创建、无 `dataset_id`、无 `source_record_id` 的地点台账靠 C11/C12 兜底 | V0.2.1 §2.5.1（行 1233）、§5.9（行 1629）、§6（行 1798–1799） |
| `data_quality_issue` | `issue_fingerprint` | **新增** | 无（V2.1 用两条部分索引） | `text NOT NULL`，`GENERATED ALWAYS AS md5(jsonb_build_array(...)::text) STORED`；`UNIQUE`（C10） | V0.2.1 §2.5.5；V0.2.2 §2.5.7 |
| `data_quality_issue` | `first_batch_id` | **新增** | 无 | `bigint` FK → `import_batch` | V0.2.1 §2.5.5 / **C24** |
| `data_quality_issue` | `last_batch_id` | **新增** | 无 | `bigint` FK → `import_batch` | V0.2.1 §2.5.5 / **C24** |
| `data_quality_issue` | `occurrence_count` | **新增** | 无 | `integer NOT NULL DEFAULT 1` | V0.2.1 §2.5.5 / **C23** |
| `data_quality_issue` | `issue_type` | **约束变化** | 20 值 | **19 值**（删 `licence_unconfirmed`）**【留痕】** | V0.2.1 §4.2（行 1769） |
| `data_dataset` | 9 列许可相关 | **删除** ⭐ | `license_id` / `license_url` / `attribution_text` / `attribution_required` / `modification_note_required` / `overlay_license_id` / `redistributable` / `license_evidence` / `license_verified_at`（`CORE_DATA_MODEL_V2.1.md:144–152`）**【留痕：已删除列逐列清单，保留以便追溯】** | **全部删除** | V0.2.1 §4.2（行 1775）；V0.2.2 §3.3 |
| `data_dataset` | `place_grain` | **不变**（⛔ 非新增） | V2 既有列（`CORE_DATA_MODEL_V2.md:208`），V2.1 收敛 2 值（`:136/154`） | 同 V2.1 | V0.2.2 §2.7.1 |
| `data_dataset` | `location_grain` | **不变** | V2 既有列 | 同 V2.1 | V0.2.2 §2.7.1 |
| `data_source` | `default_license_id` | **删除** ⭐ | V2 既有列（`CORE_DATA_MODEL_V2.md` **行 165**）；V2.1 §5.1 写「无变化」⇒ **继承**【留痕：已删除列来源说明，保留以便追溯，非现行模型】 | **删除**（许可相关） | Owner 决策 3；验收判据 D1-5；见 §5.1 |
| `data_source` | `default_redistributable` | **删除** ⭐ | V2 既有列（`CORE_DATA_MODEL_V2.md` **行 166**）；V2.1 §5.1 写「无变化」⇒ **继承**【留痕：已删除列来源说明，保留以便追溯，非现行模型】 | **删除**（许可相关） | Owner 决策 3；验收判据 D1-5；见 §5.1 |

> **约束变化（单独一行登记，避免被读成表内注释）**：`data_quality_issue.dataset_id` **NOT NULL → 可空**（V0.2.1 §5.9 行 1629 权威；V0.2.2-r2 全篇未覆盖该点，按效力顺序 V0.2.1 为准）。连带效果：C11/C12 从「NOT NULL 下恒真的死约束」恢复为真实可触发的归因兜底。**注意**：可空性**不是** Sheets D-6 那 6 行的解法（旧稿如此断言，已更正）——那 6 行**既无 `source_record_id` 也无 `place_id`**，靠 §5.9.1 的两条派生链取 `dataset_id`，**B-4 已关闭**；V-6 只剩 `whg_api_sample` 多对一未验证。

> **⭐ 许可列清零的第二张表（易漏）**【留痕：已删除列说明，保留以便追溯，非现行模型】：除 `data_dataset` 的 9 列许可相关列外，**`data_source` 还有 2 列许可相关列**（`default_license_id` / `default_redistributable`）。它们**曾被 V2.1 以「无变化」三字继承**（V2.1 §5.1 全文只有「无变化。」）⇒ 按列名 grep **必然零命中**，但那**不等于设计里没有**。本版一并删除，**CHANGELOG 需记**。⛔ 这是「grep 零命中 ≠ 不存在」的第二次同类陷阱（第一次是 §5.2.2 `place_grain`：暂存未导出 ≠ 设计没有）。

**三处必须同时写进交付物的"推翻/作废"关系**（否则下轮会被按 V2.1 旧规则改回去）：

1. **V2.1 §5.2.1 规则 1（"地点不带 dataset 列"）已被 Owner 决策 5 推翻。** V2.1.1 的 `historical_place` **带** `dataset_id` + `grain_key`；这是 §5.5.5 建点白名单与 `v_place_evidence` 的 `ON sr.dataset_id = p.dataset_id` 能成立的唯一前提。
2. **`grain_key` 的"列"与"旧用法"是两件事，都要写明**：① `grain_key` **列**——V2.1 没有，V2.1.1 **要新增**；② 它在 `v_place_evidence` join 条件里的**旧用法** `p.grain_key = sr.parent_external_id AND sr.record_scope <> 'place'`——**该谓词已作废**，被 V0.2.2 §2.7 白名单取代。见 §5.10.1。
3. **`occurrence_key` 已被 `duplicate_ordinal` 取代**，`UNIQUE` 由四段改五段。V0.2.2 全篇 `occurrence_key` **零命中**。

### 5.1 `data_source`

**变化：删除 2 列许可相关列**（`default_license_id` / `default_redistributable`）【留痕：已删除列说明，保留以便追溯，非现行模型】。

> **为什么这不是「无变化」**【留痕：已删除列来源说明，保留以便追溯，非现行模型】：V2.1 §5.1 原文只有「无变化。」三个字，意为**相对 V2 无变化**——而 **V2 §5.1（`CORE_DATA_MODEL_V2.md` 行 160–166）确实含这两列**（`default_license_id` `text`、`default_redistributable` `boolean`，V2 原文说明「仅作新建 dataset 时的默认值；判定不看它」）⇒ V2.1 **继承**了它们。
> 按 **Owner 决策 3「取消全部数据授权、许可管理设计」** + 验收判据 **D1-5（结构层不得有许可列）**，V2.1.1 必须删除。
> ⚠️ **这是 V2.1 → V2.1.1 的真实列变更，不是"无变化"。** 先前判「V2.1 零命中 ⇒ 不登记」是**grep 假阴性**：V2.1 用「无变化」四个字继承了 V2 的全部列，**列名没写出来 ⇒ 按列名 grep 必然零命中**。⛔ **不得再用"grep 零命中"论证"设计里没有"**（与 §5.2.2 `place_grain` 的「暂存没有 ≠ 设计没有」是同一类陷阱）。

**保留列（6 列，逐列列出——本表今后不再用"无变化"三字）**：

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `source_id` | `text` | **PK**，CHECK IN (`chgis`,`pleiades`,`whg`,`mcgd`) | 可读文本主键：行数 4，可读性收益 > 存储成本。**注意**：这是 `data_source` 的**自然主键**，与 `data_dataset.dataset_id` 同理，不是 `bigint identity`（§2 主键例外的第 2 个样本） |
| `display_name` | `text` | NOT NULL | "China Historical GIS" 等 |
| `homepage_url` | `text` | | ⚠️ **是 `homepage_url`，不是 `homepage`**。`homepage` 是 `data_datasets.csv` 的**暂存列名**，已判 `dropped`（见 `FIELD_MAPPING`），不得把两层名字混用 |
| `display_priority` | `smallint` | NOT NULL DEFAULT 0 | 同一地点多来源冲突、且用户显式开启"必须选一个"时的展示排序；默认 0 = 全部等权 = 不启用（V2 §6.3.5） |
| `notes` | `text` | | |
| `created_at` | `timestamptz` | NOT NULL DEFAULT now() | |

**⛔ 已删除的 2 列**【留痕：已删除列逐列清单，保留以便追溯，非现行模型】：

| # | 删除的列 | 原 V2 落点 | 删除理由 |
|---:|---|---|---|
| 1 | `default_license_id` 【留痕】 | V2 §5.1 行 165 | Owner 决策 3：取消全部许可管理。它只作"新建 dataset 时的默认值"，判定从不看它 ⇒ 删后无行为损失 |
| 2 | `default_redistributable` 【留痕】 | V2 §5.1 行 166 | 同上。它是 V2 许可三态拆分（`unconfirmed⇒true` + `license_id='unknown'`）的入口，随 `data_dataset` 9 列许可列一并删除 |

> **⛔ 不加 `updated_at`**：V2 §5.1 的 `data_source` **只有 `created_at`，没有 `updated_at`**。`FIELD_MAPPING` 里若有 `data_source.updated_at` 行，那是 V2.1 映射表遗留的**幽灵行**，已改判 `(dropped)`（见 P1-2）。
> **⚠️ CHANGELOG 需记**【留痕：已删除列说明，保留以便追溯，非现行模型】：`data_source.default_license_id` / `default_redistributable` 这两列**曾被 V2.1 以「无变化」方式继承**，本轮一并删除；记法是「V2.1 §5.1「无变化」≠ V2.1.1 §5.1「无变化」」。
> **与 §5.2 `data_dataset` 的关系**：`data_dataset` 删 **9** 列许可相关列（§5.2 逐列列明），`data_source` 删 **2** 列（上表逐列列明）——**两张表各自逐列列明，不给跨表合计数**（沿用裁定 3：合计数是口径陷阱）。

### 5.2 `data_dataset`

**变化**：**删除 9 列许可相关列**（B14）；其余列沿用 V2.1。

**⛔ 已删除的 9 列【留痕：已删除列逐列清单，保留以便追溯，非现行模型】 **（V0.2.1 §4.2 行 1775「`data_dataset` 许可列 = 0，全部删除，含 `attribution_text`，**无 `citation_text`**」；V0.2.2 §3.3）：

| # | 删除的列 | 原 V2.1 落点 |
|---:|---|---|
| 1 | `license_id` | V2.1 §5.2 行 144 【留痕】 |
| 2 | `license_url` | 行 145 【留痕】 |
| 3 | `attribution_text` | 行 146 【留痕】 |
| 4 | `attribution_required` | 行 147 【留痕】 |
| 5 | `modification_note_required` | 行 148 【留痕】 |
| 6 | `overlay_license_id` | 行 149 【留痕】 |
| 7 | `redistributable` | 行 150 【留痕】 |
| 8 | `license_evidence` | 行 151 【留痕】 |
| 9 | `license_verified_at` | 行 152 【留痕】 |

> **本表整体标【留痕】**：这 9 行是**已删除列的追溯清单**，不是现行模型的一部分。逐列列明是 V0.2.2 / V0.2.1 的硬要求（删掉会制造追溯断点，下轮无法确认"曾经有这些列、为何删"）。**K3 禁用词扫描遇到本表应跳过**（豁免判据：凡「已删除列清单 / 明确不做 / 禁用词清单 / 删枚举值说明」语境且带【留痕】标记者不计命中）。

> **明确不做的事**【留痕】（V0.2.2 §3.3）：不设计授权、许可、再分发管理；**不重新引入 `attribution_text`、`citation_text` 或任何替代字段**。
> **随之废除**：V2.1 §7 的**许可门禁**（行 715、§7.1、§7.2）在 V2.1.1 **不存在**。见 §8。

**保留的列**：

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `dataset_id` | `text` | **PK** | 自然键。7 个实测值见 §9.3 |
| `source_id` | `text` | **FK** → `data_source`，NOT NULL | |
| `display_name` | `text` | NOT NULL | |
| `dataset_version` | `text` | | `v6` / `2026_08_25` / `4.1` |
| `record_scopes` | `text[]` | **NOT NULL** | 该数据集实际产出哪些记录形态，取值 ⊆ `{place,name,location,edge}`。导入前校验：出现未声明 scope ⇒ 整批失败 |
| **`place_grain`** | `text` | **NOT NULL**，CHECK IN (`per_record`,`per_parent_external_id`) | ⭐ **V2 既有列**，见 §5.2.2 |
| `location_grain` | `text` | NOT NULL，CHECK IN (`per_record`,`per_parent_external_id`) | **V2 既有列**，V2.1 收敛 2 值 |
| `grain_evidence` | `text` | | 该 grain 判定从哪几个数推出来的。**必填** |
| `occurrence_key_rule` | `text` | NOT NULL，CHECK IN (`none`,`parent_ordinal`) | V2.1 新增。**⭐ 裁定：保留该列**——但其服务对象 `occurrence_key` 已被 `duplicate_ordinal` 取代（V0.2.2 全篇零命中）⇒ **本列在 V2.1.1 中不再参与键生成**；去留待施工验证后由下轮决定。见 §5.2.3 |
| `external_id_nature` | `text` | NOT NULL，CHECK IN (`source_declared`,`pipeline_composed`) | V2.1 新增 |
| `content_sha256` | `text` | | 本版本输入文件哈希 |
| `local_path` | `text` | | 原始文件位置 |
| `record_count` | `integer` | | 缓存，供核对 |
| `is_active` | `boolean` | NOT NULL DEFAULT true | |
| `notes` | `text` | | 已知限制 |
| `created_at` / `updated_at` | `timestamptz` | NOT NULL | |

**约束**：`array_length(record_scopes,1) >= 1`；`CHECK (external_id_nature <> 'pipeline_composed' OR occurrence_key_rule = 'none')`。

#### 5.2.1 dataset 身份三规则（V2.1 §5.2.1 的收敛版）

1. **dataset 归属的唯一权威字段是 `source_record.dataset_id`。**
2. **`historical_place` 必须能回溯到唯一一条 `source_record`**——`created_from_source_record_id` NOT NULL（人工创建除外）不是可选项；派生失败即整批失败。
3. **任何出现在导出或暂存物里的 dataset 标识，值域必须 ⊆ `data_dataset.dataset_id`。** `chgis_pref`/`chgis_cnty` 是**图层键**不是 dataset id；`whg_api_sample` **作废**。

#### 5.2.2 ⭐ `place_grain` 是 **V2 既有列**，不是 V2.1.1 新增

| 项 | 定式 |
|---|---|
| 归属 | `data_dataset` 表 **V2 既有列**：`CORE_DATA_MODEL_V2.md:208` 明文定义（`text NOT NULL`） |
| 类型 / 值域 | `text NOT NULL`，`CHECK (place_grain IN ('per_record','per_parent_external_id'))` |
| 枚举演进 | V2 = **3 值**（`per_record` / `per_external_id` / `per_parent_external_id`）→ V2.1 收敛为 **2 值**（`CORE_DATA_MODEL_V2.1.md:136/154`），`per_external_id` 作废 |
| 为什么收敛 | `per_external_id` 与 `per_record` 的**计算式完全相同**（都取 `external_id`），唯一区别是"允不允许同 ID 多行"；实测允许同 ID 多行只有桂林郡一例，且它是**缺陷**（走 `QUARANTINE`）⇒ 一个只能描述缺陷的枚举值不应占据枚举位 |
| 暂存为何看不到 | `FIELD_MAPPING_V2.1.csv:19` 标为 **`(derived)`**；暂存 `data_datasets.csv` 的 11 列**未导出**它 ⇒ **"暂存没有" ≠ "设计没有"** |
| 当前取值 | MCGD = `per_parent_external_id`（960 条 name 记录 → 643 地点）；Pleiades / CHGIS = `per_record` |
| 本版是否加列 | **否**。`place_grain` 是 **V2 既有列**，不出现在 §5.0 列变更清单的"新增"行里（该清单只列 V2.1 → V2.1.1 的真实增量） |

> ⛔ **不得把 `place_grain` 写成 V2.1.1 新增列。** V0.2.2-r1 曾记为 +3，**已回退为 +2**（`rejected_by` × 2 表）。

#### 5.2.3 ⛔ `occurrence_key` **已删除**（被 `duplicate_ordinal` 取代）

V2.1 §4.2 / §5.4 的 `occurrence_key`（`parent#ordinal`，`text NOT NULL DEFAULT ''`，`CORE_DATA_MODEL_V2.1.md:263`）在 V2.1.1 中**删除**：

- 五段业务键（C01）用 `parent_external_id` + `duplicate_ordinal` **各自独立成段**，不再用 `occurrence_key` 复合承载"父级 + 序号"两重语义；
- **V0.2.2 全篇 `occurrence_key` 零命中**（grep 核对）⇒ 该列在 V0.2.2 的设计里已不存在；
- V2.1 的 `UNIQUE (dataset_id, record_scope, external_id, occurrence_key)` 由 **C01 五段键**取代；
- V2.1 的 `CHECK (is_active OR occurrence_key <> '')`（`CORE_DATA_MODEL_V2.1.md:279`，**未编号**）随之失效，其意图（"隔离动作必须伴随可解释的键"）由 **C20 + C29** 覆盖；
- `data_dataset.occurrence_key_rule` 列（V2.1 §5.2 新增）**失去服务对象** ⇒ 是否保留列入附录 B **V-3** 待裁定。

> ⛔ **取代关系必须写入 CHANGELOG**：`occurrence_key` ⇒ `parent_external_id` + `duplicate_ordinal`。

#### 5.2.4 七个数据集的 grain / scope 落地值（V2.1 §5.2.3，删许可列后）

| dataset_id | source | scopes | place_grain | location_grain | occ_key_rule | external_id 性质 | 记录数 |
|---|---|---|---|---|---|---|---|
| `chgis_v6_prefecture_points` | chgis | `{place}` | `per_record` | `per_record` | `none` | `source_declared` | 5,226 |
| `chgis_v6_county_points` | chgis | `{place}` | `per_record` | `per_record` | `none` | `source_declared` | 10,522 |
| `mcgd_zenodo_22094815_head960` | mcgd | `{name}` | `per_parent_external_id` | `per_parent_external_id` | `parent_ordinal` | `source_declared` | 960 |
| `pleiades_gis_4_1_slice` | pleiades | `{place,name,location,edge}` | `per_record` | `per_record` | `parent_ordinal` | `source_declared` | 12,445 |
| `whg_geoname_s_gn_sample` | whg | `{place,name,location}` | `per_record` | `per_record` | `none` | `pipeline_composed` | 209 |
| `whg_getty_tgn_sample` | whg | `{place,name,location}` | `per_record` | `per_record` | `none` | `pipeline_composed` | 21 |
| `whg_hgis_de_las_indias_sample` | whg | `{place,name,location}` | `per_record` | `per_record` | `none` | `pipeline_composed` | 8 |

### 5.3 `import_batch`

沿用 V2.1 §5.3（新增 `derivation_version`、`quarantined_count`；`status` 6 值）。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `batch_id` | `bigint` | **PK** | |
| `dataset_id` | `text` | **FK** → `data_dataset`，NOT NULL | |
| `dataset_version` | `text` | | |
| `derivation_version` | `text` | **NOT NULL** | 本次导入使用的派生规则版本（如 `v2.1.1`）。`record_scope`/`parent_external_id`/`duplicate_ordinal`/`created_from_source_record_id` 全是派生的，规则变了结果就变 ⇒ 必须记下"用哪版规则算的" |
| `status` | `text` | NOT NULL，CHECK IN (`running`,`succeeded`,`partial`,`failed`,`rolled_back`,`quarantined_only`) | **6 值**（`CORE_DATA_MODEL_V2.1.md:235`） |
| `input_file` / `input_sha256` / `input_row_count` | | | |
| `inserted_source_record_ids` | `bigint[]` | | 本批新增 |
| `updated_source_record_ids` | `bigint[]` | | 本批更新 |
| `quarantined_count` | `integer` | NOT NULL DEFAULT 0 | 本批隔离的记录数（`is_active=false`）。**既不是 inserted 也不是 failed** |
| `skipped_count` / `failed_count` | `integer` | | |
| `blocked_count` | `integer` | **NOT NULL DEFAULT 0** | 记录级跳过（`locked` / `manual_edited_fields` / `last_batch_id` 不符）时 +1。**新增列**（V2.1 无）；出处 V0.2.1 G3-04（行 336）/ V0.2.2 §2.4.3（行 509），已登记 §5.0 |
| `rollback_of_batch_id` | `bigint` | **FK** → `import_batch`，可空 | |
| `started_at` / `finished_at` / `operator` / `notes` | | | |

**状态判据**：

| 状态 | 判据 |
|---|---|
| `succeeded` | `failed_count = 0` |
| `partial` | `failed_count > 0`，且每条失败都有台账 |
| `failed` | 前置校验未通过或整批中断。**此时一行都不许落库** |
| `rolled_back` | 已完整撤销 |
| `quarantined_only` | `inserted = 0` 且 `quarantined = input_row_count`（整套文件都是重复行） |

### 5.4 `source_record`

**变化**：业务键改五段；`parent_external_id` 升为必需段（C29）；新增 `duplicate_ordinal` / `inactive_reason` / `inactive_at` / `inactive_in_batch_id`。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `source_record_id` | `bigint` | **PK** | |
| `dataset_id` | `text` | **FK** → `data_dataset`，NOT NULL | 唯一权威 |
| `record_scope` | `text` | NOT NULL，CHECK IN (`place`,`name`,`location`,`edge`) | 派生，规则见 §5.4.2。**一律用 `edge`，不得混用 `connection`** |
| `external_id` | `text` | NOT NULL | 源声明 ID，或拼装 ID（见 `external_id_nature`） |
| **`parent_external_id`** | `text` | **NOT NULL** | ⭐ **五段键必需段**。Pleiades `raw_payload.place_id`；MCGD `raw_payload.LocID`；无父级 ⇒ 哨兵 `'-'`。**不得 NULL、不得空串**（C29） |
| **`duplicate_ordinal`** | `integer` | NOT NULL DEFAULT 0 | ⭐ **五段键必需段**。0 = 唯一组；≥1 = 组内名次，按 `(content_hash ASC, raw_record_index ASC)` 定序 |
| ~~`occurrence_key`~~ | — | **已删除**（V2.1 列） | 被 `parent_external_id` + `duplicate_ordinal` 取代，见 §5.2.3；V0.2.2 全篇零命中。**本行保留仅为逐列对照，模型中没有该列** |
| `raw_file` | `text` | NOT NULL | 项目根相对路径 |
| `raw_record_index` | `integer` | | 文件内第几条（1-based）。**不保证文件内唯一**；**只能**在 `content_hash` 相等时破并列 |
| `raw_payload` | `jsonb` | NOT NULL | 该行全部原始字段 |
| `content_hash` | `bytea` | NOT NULL | 派生，规则见 §4.4 |
| `first_batch_id` | `bigint` | **FK** → `import_batch`，NOT NULL | |
| `last_batch_id` | `bigint` | **FK** → `import_batch` | |
| `is_active` | `boolean` | NOT NULL DEFAULT true | 源端消失 / 批次回滚 / 重复隔离 ⇒ false，**不 DELETE** |
| **`inactive_reason`** | `text` | 可空，CHECK IN (`source_absent`,`batch_rolled_back`,`duplicate_quarantine`) | **3 值**（+NULL 表 active）。`import_error` 已删除（0 条可达路径） |
| **`inactive_at`** | `timestamptz` | 可空 | 失效时间戳 |
| **`inactive_in_batch_id`** | `bigint` | **FK** → `import_batch`，可空 | 失效批次 |
| `ingested_at` | `timestamptz` | NOT NULL | |

**约束**（编号引自 V0.2.1 §4.3 / V0.2.2）

| # | 约束 |
|---|---|
| **C01** | `UNIQUE (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` |
| **C03 / C18** | `CHECK ((is_active AND inactive_reason IS NULL) OR (NOT is_active AND inactive_reason IS NOT NULL))`（C18 是 C03 的 V0.2 正式编号，**双编号去重后不另计**） |
| **C19** | `CHECK (inactive_reason IS NULL OR inactive_reason IN ('source_absent','batch_rolled_back','duplicate_quarantine'))` |
| **C20** | `CHECK (inactive_reason <> 'duplicate_quarantine' OR duplicate_ordinal > 0)`（**取代已废除的 C02**） |
| **C21** | `CHECK ((inactive_at IS NULL) = (inactive_reason IS NULL))` |
| **C22** | `CHECK ((inactive_in_batch_id IS NULL) = (inactive_reason IS NULL))` |
| **C29** | §4.2 的 `parent_external_id` 必需段硬约束（键级，不落成 SQL CHECK） |
| — | 索引 `(dataset_id, external_id)`、`(content_hash)`、`(dataset_id, record_scope) WHERE is_active` |
| — | **不**存 `license_status` / `redistributable` / `attribution_text`【留痕：禁用列名清单】 |

> **V0.1 的 `CHECK (is_active OR duplicate_ordinal > 0)`（C02）已废除**，由 **C20** 精确表达：只有 `duplicate_quarantine` 需要 ordinal，`source_absent` / `batch_rolled_back` 下的唯一记录（`ordinal=0`）可以合法失效。

#### 5.4.1 V2.1 CORE 行 279 的未编号约束（登记，不计入计数）

`CORE_DATA_MODEL_V2.1.md:279` 有一条**未编号**的 `CHECK (is_active OR occurrence_key <> '')`。它**不在 C01–C29 之列**，不计入附录 A 的 27 / 24 任一数字；其意图（"隔离动作必须伴随可解释的键"）已被 **C20 + C29** 覆盖。

#### 5.4.2 四个派生列的生成规则（导入器必须照此执行）

| 派生列 | 规则 | 复算结果 |
|---|---|---|
| `record_scope` | 按 `dataset_id` + `external_id_type` 查表（下表），**不猜** | 29,391 行全部落到 4 个值之一，0 未知 |
| `parent_external_id` | Pleiades：`raw_payload.place_id`；MCGD：`raw_payload.LocID`；CHGIS / WHG：`'-'`（哨兵） | Pleiades 9,802 行全有；MCGD 960 行全有 |
| `duplicate_ordinal` | §4.3 | `ordinal=0` **29,377**；另 7 组 × 2 行 = 14 行 |
| `content_hash` | §4.4 | 29,391/29,391 与规范化表达式逐字节相等 |

**`record_scope` 判定表**（V2.1 §5.4.2）：

| dataset_id | `external_id_type` | 实测行数 | → `record_scope` |
|---|---|---:|---|
| `chgis_v6_prefecture_points` | `chgis_sys_id` | 5,226 | `place` |
| `chgis_v6_county_points` | `chgis_sys_id` | 10,522 | `place` |
| `mcgd_zenodo_22094815_head960` | `mcgd_nameid` | 960 | `name` |
| `pleiades_gis_4_1_slice` | `pleiades_place_id` | 2,643 | `place` |
| `pleiades_gis_4_1_slice` | `pleiades_name_id` | 4,579 | `name` |
| `pleiades_gis_4_1_slice` | `pleiades_location_id` | 2,460 | `location` |
| `pleiades_gis_4_1_slice` | `pleiades_connection_id` | 2,763 | **`edge`** |
| `whg_geoname_s_gn_sample` | `whg_source_id` | 4 | `place` |
| `whg_geoname_s_gn_sample` | `whg_place_name_index` | 201 | `name` |
| `whg_geoname_s_gn_sample` | `whg_geometry` | 4 | `location` |
| `whg_getty_tgn_sample` | `whg_source_id` | 1 | `place` |
| `whg_getty_tgn_sample` | `whg_place_name_index` | 19 | `name` |
| `whg_getty_tgn_sample` | `whg_geometry` | 1 | `location` |
| `whg_hgis_de_las_indias_sample` | `whg_place_id` | 2 | `place` |
| `whg_hgis_de_las_indias_sample` | `whg_place_name_index` | 3 | `name` |
| `whg_hgis_de_las_indias_sample` | `whg_geom_index` | 3 | `location` |

**A12**：`record_scope` 出现第五种 ⇒ **整批 `failed`**（不默认放行）。派生失败同样整批 `failed`——若兜底成 `place`，MCGD 的 960 行会变成 960 个地点（而非 643 个），错误会以"看起来正常"的形态进库。

> **⚠️ D-3 更正**：上表的 `(dataset_id, external_id_type)` 组合是 **16 行**，但**实测 `external_id_type` 只有 11 种**（`chgis_sys_id` / `mcgd_nameid` / `pleiades_place_id` / `pleiades_name_id` / `pleiades_location_id` / `pleiades_connection_id` / `whg_source_id` / `whg_place_name_index` / `whg_geometry` / `whg_place_id` / `whg_geom_index`）。
> V2.1 映射 L35 notes 写的「**16 种**」**已作废**——16 是**映射行数**，不是类型数。**交付物一律用实测 11 种 + 权威 11→4 查表**。

### 5.5 `historical_place`

**变化**：新增 `dataset_id` + `grain_key`（B12）；`record_status` **3 值**（B13）。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `place_id` | `bigint` | **PK** | |
| **`dataset_id`** | `text` | **FK** → `data_dataset`，**NOT NULL** | ⭐ 新增。与 `grain_key` 组成装配唯一键 |
| **`grain_key`** | `text` | **NOT NULL** | ⭐ 新增。派生规则见 §5.5.3 |
| `canonical_name` | `text` | NOT NULL | 无唯一约束。派生规则沿用 WB-002：CHGIS 取"最新时段"的 `NAME_CH`；`NAME_CH` 空退回 `NAME_PY`；MCGD 取 `NameID` 字典序最小行；Pleiades 取 `places.csv.title`；WHG 取 `toponym` |
| `canonical_name_lang` | `text` | | BCP-47。实测：CHGIS `zh` 15,746 / Pleiades `und` 2,643 / MCGD `zh-Latn` 643 / WHG `und` 7 |
| `place_type` | `text` | NOT NULL DEFAULT 'unknown'，CHECK IN (`admin_center_prefecture`,`admin_center_county`,`admin_center_other`,`settlement`,`unknown`) | 实测：10,524 / 5,203 / 18 / 0 / 3,294 |
| `place_type_source` | `text` | NOT NULL，CHECK IN (`lev_rank`,`lev_rank_unmapped`,`source_code_unconfirmed`,`unknown`,`manual`) | 实测：15,745 / 1 / 643 / 2,650 / 0 |
| `place_type_basis_note` | `text` | | 依据的原文细节 |
| `description` | `text` | | 本阶段留空 |
| **`record_status`** | `text` | NOT NULL DEFAULT 'staging'，CHECK IN (`staging`,`rejected`,`merged`) | ⭐ **3 值**（V2.1 的 4 值含 `published` **已作废**）。`rejected` 是**派生态**（由证据集合求出，不是人置位的） |
| `merged_into_place_id` | `bigint` | **FK** → `historical_place`，可空 | 合并墓碑 |
| `merge_review_ref` | `bigint` | **FK** → `candidate_match`，可空 | |
| `merged_at` | `timestamptz` | | |
| `created_from_source_record_id` | `bigint` | **FK** → `source_record`，可空 | **锚点**（IDENTITY，永不改写）。派生规则见 §5.5.4 |
| `created_by` | `text` | NOT NULL DEFAULT 'import'，CHECK IN (`import`,`manual`) | |
| `locked` | `boolean` | NOT NULL DEFAULT false | |
| `manual_edited_fields` | `text[]` | NOT NULL DEFAULT '{}' | |
| `notes` | `text` | | |
| `created_at` / `updated_at` | `timestamptz` | NOT NULL | |

**约束**

| # | 约束 |
|---|---|
| **C04** | `UNIQUE (dataset_id, grain_key)` |
| **C05** | `CHECK (created_by='manual' OR created_from_source_record_id IS NOT NULL)` |
| **C06** | `CHECK (merged_into_place_id IS NULL OR (record_status='merged' AND merge_review_ref IS NOT NULL AND merged_at IS NOT NULL))` |
| — | `CHECK (merged_into_place_id IS NULL OR merged_into_place_id <> place_id)` |
| — | `CHECK (place_type_source <> 'manual' OR created_by='manual')` |
| — | `CHECK (place_type_source <> 'lev_rank' OR place_type <> 'unknown')` |
| — | 部分索引 `WHERE merged_into_place_id IS NOT NULL` |

#### 5.5.1 三条硬规则

1. **地点行不带时间列。** 时间在子表，视图聚合（§5.10.3）。
2. **地点行不带几何列。** 几何在 `historical_place_location`。
3. **地点的失效原因不入库。** 完全由证据集合决定，只由 `v_place_liveness` 求出（存两遍必然漂移）。

三条合起来的意思是：`historical_place` 只是一句断言——"存在这样一个地点，它叫这个名字，是这类东西"。所有可争议的信息（它在哪、它什么时候在）都在子表上，各有自己的证据行。

#### 5.5.0 ⛔ V2.1 §5.2.1 规则 1「地点不带 dataset 列」已被推翻

```
【推翻声明】V2.1 §5.2.1 规则 1（"historical_place 不带 dataset 列"，CORE_DATA_MODEL_V2.1.md:176）
            已被 Owner 决策 5 推翻。
V2.1.1 的 historical_place 【带】 dataset_id + grain_key（NOT NULL），并加 UNIQUE(dataset_id, grain_key)（C04）。
原因：这是 §5.5.5 建点白名单与 §5.10.1 v_place_evidence 的 ON sr.dataset_id = p.dataset_id
      能成立的唯一前提；没有这两列，MCGD 按组建点（960 → 643）无法表达。
⛔ 下轮不得按 V2.1 旧规则把这两列删回去。
```

> **D-2 的裁定口径**：视图 `ON sr.dataset_id = p.dataset_id` 依赖 V2.1 中不存在的列，**不是缺陷**，是 Owner 决策 5 的预期变更——V2.1.1 加了 `historical_place.dataset_id` 后视图即可编译。

#### 5.5.2 `record_status` 的 3 值（地点）与子表的 3 值**值域不同，不得合并**

| 表 | `record_status` 值域 | 出处 |
|---|---|---|
| `historical_place`（**地点**） | **`staging` / `rejected` / `merged`** | V0.2.2 §2.1.1（行 76）、§4.1 K5（行 969） |
| `historical_place_name` / `historical_place_location`（**子表**） | `staging` / `published` / `rejected` | V2.1 §5.6 **行 479** / 本文件 §5.7、§5.6 的 `record_status` 行（子表 3 值；`published` 是子表专有，V2.1 行 535 只是合并行、未给值域） |

> ⛔ **两套值域不同（地点有 `merged` 无 `published`；子表有 `published` 无 `merged`），交付物必须分别写明，不得合并成一套。**
> V0.2.1 §4.2（行 1767）写的地点 `record_status` = 4 值 **已作废**（I-5）。

#### 5.5.3 `grain_key` 的派生（唯一实现）

```
grain_key(record) =
    dataset.place_grain = 'per_record'               ? record.external_id
  : dataset.place_grain = 'per_parent_external_id'   ? record.parent_external_id
  : CAST(NULL AS text)   -- 不可能发生（NOT NULL + CHECK 2 值已封死）；发生即整批 failed
```

#### 5.5.4 `created_from_source_record_id` 的派生规则

| 数据集 | 地点的"创建记录" | 复算 |
|---|---|---|
| CHGIS 两层 | `external_id = SYS_ID` 的那条 `record_scope='place'` 记录；若该 SYS_ID 有 2 行，取**活性行**（`is_active=true`） | 15,746 / 15,746 |
| Pleiades | `external_id = place id` 的那条 `record_scope='place'` 记录 | 2,643 / 2,643 |
| MCGD | `parent_external_id = LocID` 的若干 `record_scope='name'` 记录中，**`external_id`（`NameID`）字典序最小的那条**——与 `canonical_name` 同源 | 643 / 643 |
| WHG | `external_id = place ref` 的那条 `record_scope='place'` 记录 | 7 / 7 |

**为什么 MCGD 要指定"NameID 最小"**：`canonical_name` 已用这条规则。若两处各取各的，会出现"地点名来自 A 行、证据来自 B 行"——B 行换了数据集时，名称与证据就脱钩了。

> **真实断点（V2.1 §5.5.3）**：暂存 `historical_places.csv` 的 `primary_external_id`，MCGD 的 643 行填的是 `LocID`（`D` 前缀），而 `source_records.csv` 的 `external_id` 是 `NameID` ⇒ **643 个地点（3.4%）用 `primary_external_id` 完全 join 不上任何源记录**。`primary_external_id` 判定为"装配辅助列"，**不做归属依据**；归属一律走 `created_from_source_record_id`。

#### 5.5.5 建点证据白名单（写死）

```sql
可作为建点依据的源记录 ⇔
   ( sr.record_scope = 'place' )                                    -- ① 逐记录建点
 OR ( sr.record_scope IN ('name','location')                        -- ② 按组建点
      AND sr.dataset_id 对应的 data_dataset.place_grain = 'per_parent_external_id' )
```

**失败分支**（`place_grain` 为 NOT NULL ⇒ "未声明"不存在）：

- `place_grain = 'per_record'` ⇒ 该数据集的 name/location 记录**不建点**，必须解析到已存在的地点；
- 该 `dataset_id` 在 `data_dataset` 中不存在 ⇒ **整批 `failed`**（同 A12），**不是**"当作未声明"；
- 值域外的值 ⇒ 由 CHECK 在**建库期**拦截，不进入运行期。

**⛔ 明确禁止**：`record_scope = 'edge'`（Pleiades connection 的 id 是**被指向的**地点，不是它自己的地点）；任何**未知** `record_scope` 值。

**白名单断言**（V0.2.2 §2.7.3）：

```
V3'  count(creator 证据行 WHERE is_anchor) == 19,039          -- 每地点恰好 1 条锚点（入库口径）
V4   count(证据行 WHERE evidence_role='creator' AND source.record_scope='edge') == 0
V5   count(证据行 WHERE evidence_role='creator'
             AND source.record_scope='name'
             AND dataset.place_grain <> 'per_parent_external_id') == 0
```

> **`NOT NULL + CHECK(2 值)` ⇒ `<> 'per_parent_external_id'` 等价于 `= 'per_record'`** ⇒ V5 语义不变、仍应恒为 0，且不再可能命中 NULL（旧写法下 NULL 会因 `NULL <> ...` 为 NULL 而被 `count` 漏掉——那才是隐患）。**交付物必须注明这个等价关系。**

### 5.6 `historical_place_location`

**变化**：新增 `rejected_by`（B7）；`source_rule_vocabulary` **改名为** `source_time_columns`（V0.2.1 §2.7.1 行 1449–1451 / §5.6 行 1626）；其余沿用 V2.1 §5.6。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `location_id` | `bigint` | **PK** | |
| `place_id` | `bigint` | **FK** → `historical_place`，NOT NULL | |
| `source_record_id` | `bigint` | **FK** → `source_record`，可空 | 导入创建时必填 |
| `geom` | `geometry(Geometry,4326)` | 可空 | 10 条 CHGIS 坐标为 `**********`（DBF 溢出标记）⇒ NULL |
| `geom_type` | `text` | CHECK IN (`Point`,`Polygon`,`MultiPolygon`) | 实测全为 `Point`（**入库** 18,101） |
| `representative_lon` / `representative_lat` | `double precision` | | 面几何取 `ST_PointOnSurface` |
| `original_x` / `original_y` | `text` | | **必须 text**：`**********` 转 numeric 就丢 |
| `original_crs` | `text` | | `EPSG:4326` 17,457 / `unknown` 646 |
| `crs_confidence` | `text` | NOT NULL，CHECK IN (`confirmed`,`inferred`,`unknown`) | **只能由 `original_crs` 派生**：`EPSG:4326`→`confirmed`；`unknown`→`unknown`；`NULL`→`unknown`。人工可上调为 `inferred` |
| `axis_order_verified` | `boolean` | NOT NULL DEFAULT false | 与 CRS 判定**无关**。实测全 `true` |
| `crs_transform_meta` | `jsonb` | | 转换审计 |
| `location_precision` | `text` | NOT NULL DEFAULT 'unknown'，CHECK IN (`precise`,`approximate`,`rough`,`unknown`) | Pleiades `precise`→`precise`（1,704）；其余 `point`→`unknown`（16,397） |
| `uncertainty_m` | `integer` | 可空 | 源未提供 ⇒ NULL。实测全空 |
| `uncertainty_source` | `text` | | |
| `valid_from_year_astro` / `valid_to_year_astro` | `integer` | 可空 | 倒挂的 28 条**留空**，不交换不夹取 |
| `time_bound_type` | `text` | NOT NULL DEFAULT 'unknown' | **7 值域**，见 §6.1 |
| `source_beg_rule` / `source_end_rule` | `smallint` | 可空 | 数字规则码。**非数字词元不写这里** |
| **`source_time_columns`** | `text` | NOT NULL DEFAULT '' | ⭐ **改名**（V2.1 名 `source_rule_vocabulary`）。语义：**该行来源文件声明了哪些时间列（列级掩码）**，逐字保留，如 `year_after_which\|year_before_which`（**入库** 3,778 行 = name 2,074 + location 1,704）；**不是本行实际使用的规则**。出处 V0.2.1 §2.7.1（行 1449–1451）/ §5.6（行 1626） |
| `time_note` | `text` | | 人写说明 |
| `conflict_status` | `text` | NOT NULL DEFAULT 'none'，CHECK IN (`none`,`disputed`,`arbitrated`) | |
| `is_preferred` | `boolean` | NOT NULL DEFAULT false | **导入器永不置 true** |
| `record_status` | `text` | NOT NULL DEFAULT 'staging'，CHECK IN (`staging`,**`published`**,`rejected`) | ⭐ **子表 3 值**，与地点表值域**不同**（§5.5.2） |
| **`rejected_by`** | `text` | 可空，CHECK IN (`auto`,`manual`) | ⭐ **新增**。见 §5.6.1 |
| `locked` / `manual_edited_fields` / `created_by` / `notes` / **`created_at` + `updated_at`**（`timestamptz` NOT NULL） | | | |

> **⭐ 「时间戳」二字的准确所指（P1-2 核实，防幽灵行）**：本行 V2.1 原文写「`locked` / `manual_edited_fields` / `created_by` / `notes` / **时间戳**」，其中的「时间戳」= **`created_at` + `updated_at` 两列**（见 `CORE_DATA_MODEL_V2.md` **行 387**，V2 §5.7 明列 `created_at` / `updated_at`）。⇒ **本表确实有 `updated_at`**，`FIELD_MAPPING` 的第 145 行（`historical_place_names.csv → updated_at`）是**真实映射，不是幽灵行**。

**约束**

| # | 约束 |
|---|---|
| **C07** | `UNIQUE (source_record_id) WHERE source_record_id IS NOT NULL`（实测 0 冲突） |
| **C13** | `CHECK (source_time_columns = '' OR (source_beg_rule IS NULL AND source_end_rule IS NULL))`（**改名后**；实测交集 0） |
| **C14** | CRS 门禁 `CHECK (crs_confidence <> 'unknown' OR record_status <> 'published')` |
| **C15** | 几何门禁 `CHECK (geom IS NOT NULL OR record_status <> 'published')` |
| **C16** | `CHECK (time_bound_type <> 'exact' OR (valid_from_year_astro IS NOT NULL AND valid_to_year_astro IS NOT NULL))` |
| **C25** | `CHECK ((record_status = 'rejected') = (rejected_by IS NOT NULL))` |
| **C26** | `CHECK (rejected_by IS NULL OR rejected_by IN ('auto','manual'))` |
| — | `CHECK (NOT is_preferred OR conflict_status <> 'disputed')` |
| — | `CHECK (source_record_id IS NOT NULL OR created_by='manual')` |
| — | `CHECK (geom IS NULL OR ST_GeometryType(geom) = 'ST_' \|\| geom_type)` |

#### 5.6.1 `rejected_by`：为什么必须新增这两列

没有 `rejected_by` 就无法区分"因源记录消失而**自动** rejected"与"**人工**拒绝"。后果是 P0-02 的第 3/4/5 条要求**全部无法实现**——源端重新出现时，导入器只能在"恢复所有 rejected 子行"（覆盖人工决定，被明令禁止）与"一个都不恢复"（人工拒绝之外的合法数据永久丢失）之间二选一。

**这不是"多存一列方便查询"，是规则可执行性的前提。**

**四组场景的状态转换**

| 场景 | 触发 | 子行 `rejected_by='auto'` | 子行 `rejected_by='manual'` | 地点 |
|---|---|---|---|---|
| **A** 源仍 active，子行被人工拒 | 人工操作 | — | 置 `rejected` + `manual`；该证据**无效** | 若仍有其他有效证据 ⇒ 不变；否则 `liveness∈FAILURE_SET` + `rejected`。**不落台账**（人工拒绝不是数据质量问题） |
| **B** 源 `source_absent` 失效 | O3 | 置 `rejected` + `auto` | — | 若 ∃ 其他有效证据 ⇒ 保持；否则 `all_sources_absent` + `rejected` |
| **C** 源重新出现（O1/O7 复活） | 复活 | **恢复 `staging`**，`rejected_by` 清 NULL | **保持 `rejected`**；落 1 条 `manual_edit_conflict` 提示人工复核 | 若 ∃ 有效证据 ⇒ `'staging'`（不新建） |
| **D** 源端重新导入 | — | 源已恢复 ⇒ 恢复 staging | **保持 rejected**，导入器不得改 | — |

> ⛔ **明确禁止**：不得"把所有 rejected 子行恢复成 staging"来绕过本条——那会一次性抹掉所有人工拒绝，正是本条要防的。

### 5.7 `historical_place_name`

**变化**：新增 `rejected_by`（B7）；**新增 `source_time_columns`**（V0.2.1 §2.7.1 行 1449–1451 / §5.7 行 1627）；其余沿用 V2.1 §5.7。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `name_id` | `bigint` | **PK** | |
| `place_id` | `bigint` | **FK** → `historical_place`，NOT NULL | |
| `source_record_id` | `bigint` | **FK** → `source_record`，可空 | |
| `name_text` | `text` | NOT NULL | 原样，不做归一化 |
| `name_lang` | `text` | | BCP-47。实测 48 种；含 `und` 1,043 行、**字面量 `'None'` 4 行** |
| `name_script` | `text` | | ISO 15924。`Latn` 16,708 / `Hani` 15,748 / `Hant` 12,750 / **空 2,297** |
| `name_type` | `text` | NOT NULL，CHECK IN (`primary`,`alternate`,`transliteration`,`historical`,`colloquial`) | 实测：`primary` 18,621 / `transliteration` 15,748 / `alternate` 13,134 |
| `transliteration_scheme` | `text` | | `pinyin` 15,748 / `wade_giles_probable` 960 / 空 |
| `association_certainty` | `text` | CHECK IN (`certain`,`less-certain`,`uncertain`) | Pleiades 直接映射 |
| `valid_from_year_astro` / `valid_to_year_astro` | `integer` | 可空 | **该名称用于该实体的时间窗，不是地名存在时间** |
| `time_bound_type` | `text` | NOT NULL DEFAULT 'unknown' | **7 值域**，见 §6.1 |
| **`source_time_columns`** | `text` | NOT NULL DEFAULT '' | ⭐ **新增列**（V2.1 name 表无任何时间规则列）。同 `historical_place_location.source_time_columns` 类型与语义：该行来源文件声明了哪些时间列（列级掩码），逐字保留。**收纳 V2.1 会丢弃的 2,074 行 name 侧掩码**（V2.1 只有 location 一列能存，name 侧 `time_rule_code` 只能落 `(dropped)`）。出处 V0.2.1 §2.7.1（行 1449–1451）/ §5.7（行 1627） |
| `time_note` | `text` | | 人写的说明 |
| `notes` | `text` | | **本表必填**。实测**暂存** 47,503 行全部非空 |
| `record_status` | `text` | NOT NULL DEFAULT 'staging'，CHECK IN (`staging`,**`published`**,`rejected`) | ⭐ **子表 3 值**，与地点表值域**不同**（§5.5.2） |
| **`rejected_by`** | `text` | 可空，CHECK IN (`auto`,`manual`) | ⭐ **新增**。同 §5.6.1 |
| `locked` / `manual_edited_fields` / `created_by` / **`created_at` + `updated_at`**（`timestamptz` NOT NULL） | | | |

> **⭐ 「时间戳」二字的准确所指（P1-2 核实，防幽灵行）**：本行 V2.1 原文写「`locked` / `manual_edited_fields` / `created_by` / **时间戳**」，其中的「时间戳」= **`created_at` + `updated_at` 两列**（见 `CORE_DATA_MODEL_V2.md` **行 350**，V2 §5.6 明列 `created_at` / `updated_at`）。⇒ **本表确实有 `updated_at`**，`FIELD_MAPPING` 的第 121 行（`historical_place_locations.csv → updated_at`）是**真实映射，不是幽灵行**。

**约束**

| # | 约束 |
|---|---|
| **C08** | `UNIQUE (source_record_id, name_type, name_text, name_lang)`（**不得**改成 `UNIQUE(source_record_id)`，一个记录最多 3 个名称行） |
| **C16** | `CHECK (time_bound_type <> 'exact' OR (两端均 NOT NULL))` |
| **C25** | `CHECK ((record_status = 'rejected') = (rejected_by IS NOT NULL))` |
| **C26** | `CHECK (rejected_by IS NULL OR rejected_by IN ('auto','manual'))` |
| — | `CHECK (source_record_id IS NOT NULL OR created_by='manual')` |
| — | `CHECK (name_lang IS NULL OR name_lang ~ '^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$' OR name_lang = 'und')` |
| — | **C13 在本表【不适用】**：本表**没有** `source_beg_rule` / `source_end_rule` 两列（V0.2.1 §5.7 只要求 `+source_time_columns`，其余继承 V2.1，而 V2.1 name 表无数字规则列）⇒ 若把 C13 原式写在本表将引用**不存在的列**、SQL 无法编译。本表的 `source_time_columns` 只作掩码留存，无"数字/词元二选一"的冲突面。**C13 仅落在 `historical_place_location`。** |

**两处必须清洗的取值**（V2.1 §5.7.1）：`name_lang` 字面量 `'None'`（4 行）入库写 `NULL` 并记 `nonstandard_field_name`；`name_script` 空（2,297 行）**保持空串，不填 `Zyyy`**（空串 = "源未声明"，`Zyyy` = "已判定为未编码"，是两件事）。

### 5.8 `candidate_match`

沿用 V2.1 §5.8（`relation_type` 7 值、`confidence` 4 值 + 2 条互斥 CHECK、`status` 哨兵规则），无结构变化。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `candidate_id` | `bigint` | **PK** | |
| `relation_type` | `text` | NOT NULL，CHECK IN (`same_coord_diff_entity`,`homonym_diff_place`,`same_entity_same_seat`,`location_migration_candidate`,`pleiades_connection`,`true_duplicate_suspected`,`cross_layer_disagreement`) | 7 值，与数据 6 类一一对应 + 1 个预留 |
| `place_id_a` / `place_id_b` | `bigint` | **FK** → `historical_place`，NOT NULL | |
| `source_record_id_a` / `source_record_id_b` | `bigint` | **FK** → `source_record`，可空 | |
| `distance_m` | `double precision` | 可空 | |
| `direction` | `text` | NOT NULL DEFAULT 'none'，CHECK IN (`none`,`a_to_b`,`b_to_a`) | 仅 `location_migration_candidate` 用 |
| `evidence` | `jsonb` | | 结构随类型变 |
| `confidence` | `text` | NOT NULL，CHECK IN (`high`,`medium`,`low`,`source_asserted`) | 第 4 值 `source_asserted` 仅第 5 类 |
| `status` | `text` | NOT NULL DEFAULT 'candidate'，CHECK IN (`candidate`,`needs_manual_review`,`confirmed`,`rejected`,`superseded`) | |
| `reviewer` | `text` | | 人工名，或哨兵 `system:source_attested` |
| `reviewed_at` / `review_note` | | | |
| `created_at` / `updated_at` | `timestamptz` | NOT NULL | |

**约束**

| # | 约束 |
|---|---|
| **C09** | `UNIQUE (relation_type, place_id_a, place_id_b)` |
| **C17** | `CHECK (direction = 'none' OR relation_type = 'location_migration_candidate')` |
| — | `CHECK (place_id_a <> place_id_b)` |
| — | `CHECK (status <> 'confirmed' OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL))` |
| — | `CHECK (status <> 'confirmed' OR relation_type <> 'pleiades_connection' OR reviewer = 'system:source_attested')` |
| — | `CHECK (status <> 'confirmed' OR relation_type = 'pleiades_connection' OR reviewer NOT LIKE 'system:%')` |

> **⭐ `candidate_match` 的行数不得进权威数字表。** 暂存 **53,137** / 隔离后 **53,103** 是**登记项 U18，待 Owner 拍板**（V0.2.2 §5.3 行 1039）。V0.2.1 写 53,133，实测暂存 53,137；与 2 条隔离记录相关的候选行 34 行 / 33 个键，按 Owner 决策 4 应扣 34 ⇒ 53,103。**以 data-auditor 审计报告为准，架构侧只登记、不自行改数。**

### 5.9 `data_quality_issue`

**变化**：新增 `first_batch_id` / `last_batch_id` / `occurrence_count`（B6）；`issue_type` **19 值**（B15）；新增 `issue_fingerprint` 与 `UNIQUE`；**`dataset_id` 由 NOT NULL 改为可空**（A-4，V0.2.1 §5.9 权威）。

| 列 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `issue_id` | `bigint` | **PK** | |
| `dataset_id` | `text` | **FK** → `data_dataset`，**可空** | ⭐ **约束变化：NOT NULL → 可空**（V0.2.1 §5.9 行 1629 权威）。来源两条链（§5.9.1）：① 有 `source_record_id` ⇒ `source_record.dataset_id`；② 无 `source_record_id` ⇒ 由 `source_dataset` 图层键映射（`chgis_pref`→`chgis_v6_prefecture_points`、`chgis_cnty`→`chgis_v6_county_points`、`mcgd_*`／`pleiades_gis_4_1_slice`→同名；`whg_api_sample` 一对多须走①）。列为可空是为了让"数据集级不可归因"这一语义合法存在，**不是**为了给某几行留 NULL |
| `source_record_id` | `bigint` | **FK** → `source_record`，可空 | |
| `place_id` | `bigint` | **FK** → `historical_place`，可空 | **指纹必需段**。跨层矛盾、派生值不一致等地点级问题用 |
| `batch_id` | `bigint` | **FK** → `import_batch`，可空 | **不进指纹** |
| **`issue_fingerprint`** | `text` | **NOT NULL**，GENERATED ALWAYS AS … STORED | ⭐ md5 + JSON 数组六段，见 §4.5 |
| `issue_type` | `text` | NOT NULL，CHECK IN (**19 值**，见下) | |
| `severity` | `text` | NOT NULL，CHECK IN (`blocking`,`warning`,`info`) | |
| `field_name` | `text` | NOT NULL DEFAULT '' | |
| `observed_value` / `expected_rule` | `text` | | `observed_value` 只放**暂存原值单值**；重算值进 `notes` |
| `action_taken` | `text` | NOT NULL，CHECK IN (`preserved_and_flagged`,`needs_manual_review`,`rejected`,`fixed_manually`,`ignored`,`discarded`) | 6 值 |
| **`first_batch_id`** | `bigint` | **FK** → `import_batch` | ⭐ **新增**。首次发现该问题的批次，重复发现时**不变** |
| **`last_batch_id`** | `bigint` | **FK** → `import_batch` | ⭐ **新增**。最近一次发现的批次，重复发现时置为本批 |
| **`occurrence_count`** | `integer` | NOT NULL DEFAULT 1 | ⭐ **新增**。重复发现时 `+= 1` |
| `resolved` / `resolved_at` / `resolver` / `resolution_note` | | | |
| `created_at` | `timestamptz` | NOT NULL | |

**`issue_type` 完整 19 值**【留痕：删枚举值说明语境】（V0.2.1 §4.2 行 1769「删 `licence_unconfirmed`」；由 `CORE_DATA_MODEL_V2.1.md:642` 的 20 值反推）

| `issue_type` | 暂存原始命中数 | 说明 |
|---|---:|---|
| `beg_gt_end` | 28 | 暂存实测 |
| `beg_eq_end` | 341 | 暂存实测 |
| `missing_coordinate` | 337 | 暂存实测 |
| `coordinate_out_of_range` | 1 | 暂存实测 |
| `coordinate_outside_china_bbox` | 6 | 暂存实测 |
| `year_out_of_range` | 4 | 暂存实测 |
| `duplicate_external_id` | 0 | 导入重复检测产生；当前暂存台账无此类型 |
| `duplicate_sysid` | 2 | 暂存实测 |
| `unknown_crs` | 646 | 暂存实测 |
| `unknown_time_bound_type` | 6,448 | 暂存实测 |
| `nonstandard_field_name` | 2 | 暂存实测 |
| `empty_name` | 0 | 导入校验类型；当前暂存台账无此类型 |
| `parent_place_not_in_sample` | 4,810 | 暂存实测 |
| `truncated_slice_tail` | 4 | 暂存实测 |
| `cross_layer_coordinate_conflict` | 0 | 当前 `data_quality_issues.csv` 无此类型；独立文件中的 29 对 `cross_layer_disagreement` 尚未并入本表 |
| `manual_edit_conflict` | 0 | 人工修改保护运行期产生 |
| `import_row_error` | 0 | 导入写入失败运行期产生 |
| `derived_value_mismatch` | 0 | 导入派生复核运行期产生 |
| `rollback_conflict` | 0 | 回滚运行期产生 |

> 暂存原始 12,631 行中有 2 行 `licence_unconfirmed`，按 Owner 决策 3 直接删除、不重新归类；因此上表 19 值的暂存命中数合计 **12,629**。7 个零命中值均明确保留其运行期/后续处理用途，不代表当前暂存中存在对应行。
> ⛔ **禁止为凑满 20 值而新增替代类型**（Owner 决策 3 / V0.2.1 §2.8-C）。
> **回滚阶段**产生的台账类型**只有** `rollback_conflict` 与 `manual_edit_conflict`；**`import_row_error` 属原导入阶段**，不计入 R2，改由 **R2c** 单独校验。

**约束**

| # | 约束 |
|---|---|
| **C10** | `UNIQUE (issue_fingerprint)`（替换 V2.1 的两条部分索引） |
| **C23** | `CHECK (occurrence_count >= 1)` |
| **C24** | `CHECK (first_batch_id IS NULL OR last_batch_id IS NOT NULL)` |
| **C11** | `CHECK (dataset_id IS NOT NULL OR place_id IS NOT NULL)` |
| **C12** | `CHECK (dataset_id IS NOT NULL OR source_record_id IS NULL)` |

> **C11/C12 之所以现在才真正生效**：在 `dataset_id` 定为 NOT NULL 的版本里，`dataset_id IS NOT NULL` 恒真 ⇒ 两条 CHECK **永不可能触发**，是"看起来在守、其实什么都没守"的死约束。改为可空后，C11/C12 恢复为真实的归因兜底：**任何一行台账至少能说清"这是哪个数据集的问题"，或"这是哪个地点的问题"**。反过来，若有人把 `dataset_id` 改回 NOT NULL，C11/C12 会同时退化为死约束——两者的可空性是**同一件事**，不得只改一处。

**台账语义 A（唯一身份）+ 事件伴生列**（全系统只有这一套语义，不混用 B）：

| 决策 | 结论 | 理由 |
|---|---|---|
| 指纹含 `batch_id`？ | **不含** | 197 条派生偏差是"一处持续存在的偏差"，含了每导一批新增 197 行（台账自我膨胀） |
| 重复发现怎么处理 | **UPDATE，不 INSERT** | `last_batch_id = 本批`、`occurrence_count += 1`、`first_batch_id` 不变 |
| 内容不同的多次冲突 | **各占一行** | `observed_value` 是指纹的一段，内容不同 ⇒ 不同问题对象 |
| 语义 B（每次发现独立成行） | **不采用** | 与前两条冲突，且与"重导不产生第二行"的幂等要求矛盾 |

#### 5.9.1 D-6：`dataset_id` 的来源与 6 行空 `source_record_id` 的派生链（**已核实，B-4 关闭**）

实测暂存 `data_quality_issues.csv` 共 **12,631 行 × 11 列**（`暂存原始`口径），其中**没有 `raw_file`、没有 `dataset_id`、没有 `place_id`**；`source_record_id` 有 **6 行空**。

**两条派生链（写死，按序取第一条可用的）**：

```
① 有 source_record_id   ⇒ dataset_id := source_record.dataset_id
                          （source_record_id → source_record，唯一、一对一）
② 无 source_record_id   ⇒ dataset_id := map(source_dataset)（source_dataset 是"图层键"）
     chgis_pref                       → chgis_v6_prefecture_points
     chgis_cnty                       → chgis_v6_county_points
     mcgd_zenodo_22094815_head960     → mcgd_zenodo_22094815_head960（同名）
     pleiades_gis_4_1_slice           → pleiades_gis_4_1_slice（同名）
     whg_api_sample                   → ⚠️ 一对多（3 个 whg dataset：gn / tgn / hgis）
                                         ⇒ **无法由 source_dataset 一对一派生**，
                                            必须靠 source_record_id 追溯（走①）
```

> **② 的合法性依据**：`source_dataset` 在暂存里确实是**图层键**（值域 5 个：`chgis_pref` 463 / `chgis_cnty` 6,372 / `pleiades_gis_4_1_slice` 5,141 / `mcgd_zenodo_22094815_head960` 650 / `whg_api_sample` 5），而 `normalize.py:94-97` 的 `CHGIS_DATASET_IDS` 与 `whg_extract.py:66-68` 的命名空间映射就是**同一张表**——派生规则不是新发明的，是上游 `normalize.py` 已在用的规则。⛔ 但 `source_dataset` **列本身**仍判 `dropped`（值域含 3 个非法值，见 `FIELD_MAPPING`）：**它的值可以当映射键用，它的列不入库**——两件事，不冲突。

**⛔ 原表述错误，此处更正**：旧稿写"这 6 行合法地留 `dataset_id` 为 NULL，由 C11 要求它们必须带 `place_id`（它们正是地点级台账）"——**该结论不成立**。经逐行核实：

| `issue_id` | `source_dataset` | `issue_type` | `action_taken` | 真实性质 | `place_id` |
|---|---|---|---|---|---|
| `dq_0007487` | `chgis_pref` | `nonstandard_field_name` | `preserved_and_flagged` | 图层字段名与姊妹层不一致（`END_DATE` vs `chgis_cnty` 的 `ENT_DATE`）——**层元数据问题** | 无 |
| `dq_0007488` | `chgis_pref` | `nonstandard_field_name` | `preserved_and_flagged` | 同上（`GEOCOMPLR` vs `GECOMPLR`）——**层元数据问题** | 无 |
| `dq_0007489`~`dq_0007492`（**4 行**） | `pleiades_gis_4_1_slice` | `truncated_slice_tail` | `discarded` | Pleiades HTTP Range 切片**尾截断**（传输残片，非缺陷行） | 无 |

**这 6 行没有 `place_id`、也没有 `source_record_id`，一行都不是地点级台账**；暂存 11 列里**根本没有 `place_id` 列**，`source_dataset` 也已被判 `dropped` ⇒ 旧稿"由 C11 要求带 `place_id`"**不成立**（C11 是 `CHECK (dataset_id IS NOT NULL OR place_id IS NOT NULL)`，两列都为 NULL 时 C11 会**触发失败**，不会"消解缺口"）。

**实测结论**：这 6 行 = **2 条 `chgis_pref`（`nonstandard_field_name`）+ 4 条 `pleiades_gis_4_1_slice`（`truncated_slice_tail`）**，`source_dataset` 全部落在 ② 的可一对一映射集合内 ⇒ **全部可经 ② 派生 `dataset_id`**，落值分别为 `chgis_v6_prefecture_points`（2 行）与 `pleiades_gis_4_1_slice`（4 行）。**C11 不违反**（`dataset_id` 非空即满足），也**不需要** `place_id`。

> ⛔ **不得静默填默认值**：派生必须走上面写死的两条链，**不得**填一个"兜底 dataset"或全表默认值——那会让 `dataset_id` 的 NULL 语义（"数据集级不可归因"）被假值污染。
> ⛔ **`whg_api_sample` 的一对多是本规则唯一的未验证项**：抽样的 5 行 `whg_api_sample` 台账若要派生，只能靠 `source_record_id` 走 ①；若出现"`whg_api_sample` 且 `source_record_id` 为空"的行，**② 无法派生** ⇒ 该情形**本轮未出现，未验证**（登记附录 B V-6）。

**本版处置（B-4 关闭，不再是阻断项；`dataset_id` 仍为可空列，A-4 不变）**：

| 项 | 处置 |
|---|---|
| 6 行空 `source_record_id` 的 `dataset_id` | **经 ② 派生**：2 行 → `chgis_v6_prefecture_points`，4 行 → `pleiades_gis_4_1_slice`。`FIELD_MAPPING` 标 `derived` 并写明两条派生链 |
| `dataset_id` 列的可空性 | **保持可空**（A-4，V0.2.1 §5.9 权威）。可空的理由是"地点级台账可只带 `place_id`"，**与这 6 行无关**（这 6 行都不带 `place_id`，它们靠 ② 填 `dataset_id`） |
| 暂存 11 列中的 `raw_file` / `dataset_id` | **不入库**（暂存无此列）；定位时经 `source_record_id → source_record.raw_file` 回溯；无 `source_record_id` 的行**无物理行级通路**（它们本就是层元数据/传输残片，不是某一行数据的缺陷） |
| 状态 | **B-4 关闭**：派生规则已给出并经逐行核实。残留**未验证项**只剩 `whg_api_sample` 的多对一（附录 B **V-6**） |

---

### 5.10 派生视图（本版新增；V2.1 的 §5 只有表定义）

三张视图是**唯一的派生语义落点**。视图列**不占表列**，每次查询与证据集合同源。

#### 5.10.1 `v_place_evidence`（**11 列**）

```sql
CREATE VIEW v_place_evidence AS
-- ⭐ V2.1.1 修正：把 ①②③ 三支 UNION ALL 整体包进子查询 u，由【外层窗口函数】统一算 canonical 定序。
--   原因：canonical 定序键里的 duplicate_ordinal / external_id 不在本视图的 11 列里（它们是 source_record 的列），
--         单靠分支内的常量无法表达 ⇒ 必须在外层回连 source_record。见本节末尾「修正说明」。
SELECT u.place_id,
       u.source_record_id,
       u.evidence_role,
       u.source_is_active,
       u.source_inactive_reason,
       u.child_table,
       u.child_row_id,
       u.child_record_status,
       u.child_rejected_by,
       u.is_anchor,
       (row_number() OVER (
          PARTITION BY u.place_id
          ORDER BY (u.source_is_active IS TRUE
                    AND u.child_record_status IS DISTINCT FROM 'rejected') DESC,  -- ⓿ 有效证据优先；NULL 源活性不算有效
                   (u.evidence_role = 'creator') DESC,                            -- ① 创建记录优先
                   sr.duplicate_ordinal ASC NULLS LAST,                           -- ② 与 §4.3 同源
                   sr.external_id       ASC NULLS LAST,                           -- ③ MCGD 即"NameID 最小"
                   u.source_record_id   ASC,                                      -- ④ 末位破并列（可复现）
                   coalesce(u.child_row_id, 0) ASC                                -- ⑤ 同记录内行级破并列
        ) = 1) AS is_canonical_row
FROM (
    -- ① 创建证据（1:N，MCGD 就有 N>1；白名单见 §5.5.5）
    SELECT p.place_id,
           sr.source_record_id,
           'creator'::text              AS evidence_role,
           sr.is_active                 AS source_is_active,
           sr.inactive_reason           AS source_inactive_reason,
           NULL::text                   AS child_table,
           NULL::bigint                 AS child_row_id,
           NULL::text                   AS child_record_status,
           NULL::text                   AS child_rejected_by,
           (sr.source_record_id = p.created_from_source_record_id) AS is_anchor
    FROM historical_place p
    JOIN source_record sr
      ON sr.dataset_id = p.dataset_id
     AND (   (p.grain_key = sr.external_id        AND sr.record_scope = 'place')
          OR (p.grain_key = sr.parent_external_id
              AND sr.record_scope IN ('name','location')
              AND sr.dataset_id IN (SELECT dataset_id FROM data_dataset
                                    WHERE place_grain = 'per_parent_external_id')) )
    UNION ALL
    -- ② 名称行
    SELECT n.place_id, n.source_record_id, 'name',
           sr.is_active, sr.inactive_reason,
           'name', n.name_id, n.record_status, n.rejected_by,
           FALSE
    FROM historical_place_name n LEFT JOIN source_record sr USING (source_record_id)
    UNION ALL
    -- ③ 位置行
    SELECT l.place_id, l.source_record_id, 'location',
           sr.is_active, sr.inactive_reason,
           'location', l.location_id, l.record_status, l.rejected_by,
           FALSE
    FROM historical_place_location l LEFT JOIN source_record sr USING (source_record_id)
) u
-- 外层回连取 duplicate_ordinal / external_id；LEFT JOIN 保证 source_record_id 为 NULL 的人工子行不被丢掉
LEFT JOIN source_record sr ON sr.source_record_id = u.source_record_id;
```

> **⭐ 修正说明（A-3 / QA F-11，本版留痕）**
>
> **原缺陷**：旧写法把 creator 分支写死 `FALSE AS is_canonical_row`，② 分支写 `<canonical 定序 §5.10.4>`（**不可执行占位符**），却又在 §5.10.4 要求「315 个（入库口径）无子行地点的 `is_canonical_row=true` 落在 creator 行」⇒ **直接矛盾**；且定序键 `duplicate_ordinal` / `external_id` 在 `v_place_evidence` 里并不存在（它们是 `source_record` 的列）。
>
> **本版解法（方案①：外层窗口定序）**：UNION ALL 整体下沉为子查询 `u`，外层用 `row_number() OVER (PARTITION BY place_id ORDER BY …) = 1` 计算 `is_canonical_row`；涉及 `duplicate_ordinal` / `external_id` 的定序键一律**回连 `source_record`** 取值。**占位符与写死常量全部消除，共 3 处**：creator 分支 `FALSE AS is_canonical_row`（1 处）、location 分支 `FALSE`（1 处）、name 分支 `<canonical 定序 §5.10.4>` 占位符（1 处）——全部替换为统一窗口计算，全视图为**可执行 SQL**。
>
> **两个补全项（不是新设计，登记 V-8 待 QA 复算）**：
> - **⓿ 有效证据优先**是 §5.10.4「该行是本地点**有效证据**中定序第一的行」的字面落地——若不加此键，一条失效源或 rejected 子行可能排到有效证据之前成为 canonical。该键是**必要补全**，否则定序与定义句不自洽。
> - **⑤ `child_row_id` 破并列**：同一 `source_record` 可派生多行 name（`name_type` 最多 3 行，C08），其 ②③④ 键全同 ⇒ 必须有行级末位键，否则 `row_number()` 在并列上的取值**不可复现**。
>
> **零有效证据的地点**：`is_canonical_row` 落在定序第一行（"最佳可得"），仅用于追溯，**不代表该行有效**；此时地点的 `liveness` 必属 `FAILURE_SET` 或 `orphaned`（§5.10.2），二者不会冲突。
>
> **权威设计的同类矛盾（留痕，不改 V0.2.2 原文）**：V0.2.2 §2.2.2（行 201）写死 `FALSE AS is_canonical_row` 与 §2.8.2（行 816）要求「315 个（入库口径）无子行地点的 `is_canonical_row=true` 落在 creator 行」互相冲突；本节按外层窗口定序解决，须写入 CHANGELOG。

**列清单（11 列，逐列）**：

| # | 列 | 类型 | 说明 |
|---:|---|---|---|
| 1 | `place_id` | bigint | |
| 2 | `source_record_id` | bigint | |
| 3 | `evidence_role` | text | **3 值** `creator` / `name` / `location`。⛔ `place_record` 是**禁用词** |
| 4 | `source_is_active` | boolean | 新增派生 |
| 5 | `source_inactive_reason` | text | 新增派生 |
| 6 | `child_table` | text | `'name'` \| `'location'` \| NULL（creator 行为 NULL） |
| 7 | `child_row_id` | bigint | 新增派生 |
| 8 | `child_record_status` | text | 新增派生 |
| 9 | `child_rejected_by` | text | 新增派生（`auto`/`manual`/NULL） |
| 10 | `is_anchor` | boolean | `sr.source_record_id = p.created_from_source_record_id` |
| 11 | `is_canonical_row` | boolean | **新增派生**，**三个分支统一由外层 `row_number()` 计算**，见 §5.10.4。⛔ 不再是写死常量、也不是占位符 |

> ⛔ **V0.2.2 §6 第 3 项（行 1052）写的「10 列」已作废**——漏数了 `is_canonical_row`（它在 §2.8 才定义）。**交付物一律写 11 列并逐列列出列名。**

**join 条件的构成与"旧用法作废"声明**：

| 组成 | 来源 | 状态 |
|---|---|---|
| `ON sr.dataset_id = p.dataset_id` | V0.2.2 §2.2.2（依赖 Owner 决策 5 新增的 `historical_place.dataset_id`） | ✅ 现行 |
| 键等值 `p.grain_key = sr.external_id`（place 场景）/ `p.grain_key = sr.parent_external_id`（按组场景） | V0.2.1 §2.4.2 | ✅ 现行（`grain_key` 列本版新增） |
| 白名单判据 `sr.record_scope='place'` OR (`sr.record_scope IN ('name','location')` AND `dataset.place_grain='per_parent_external_id'`) | V0.2.2 §2.7.1（逐字） | ✅ 现行 |
| ⛔ `AND sr.record_scope <> 'place'` | V0.2.1 §2.4.2 原写法 | **已作废**——它把 `edge` 与未来任何新类型**默认放行**，被 §2.7 白名单取代 |

> **两件事必须分别写明**（不得混淆）：① `grain_key` **列**——V2.1 没有，V2.1.1 **新增**；② `grain_key` 在 join 里的**旧用法** `<> 'place'`——**已作废**。

**"有效证据"的唯一定义（视图、存活、时间三处共用）**：

```
有效证据(e) ⇔ e.source_is_active IS TRUE                      -- 源记录必须明确为活性；NULL（无源的人工子行）不算有效
            AND e.child_record_status IS DISTINCT FROM 'rejected'  -- 子行未被拒（creator 行为 NULL）
```
**且**：`child_rejected_by = 'manual'` 的行**永远不是有效证据**，且不参与任何自动恢复。

三条细则：① 子行存在但源记录失效 ⇒ 该子行不贡献存活；② `evidence_role` 只用于**解释**，不用于加权，`creator`/`name`/`location` 任一有有效证据即存活；③ `merged` 与 `manual` 先于存活判定。

#### 5.10.2 `v_place_liveness`（`liveness` 取 **8 值**；本视图**对外 7 列**）

> **⚠️ 两个数不是一回事（W-04 澄清）**：标题里的「8 值」指 **`liveness` 列取 8 个枚举值**（`merged`/`manual`/`active`/`mixed_inactive`/`all_sources_absent`/`all_sources_rolled_back`/`quarantined_only`/`orphaned`）；「7 列」指**本视图对外输出的列数**（`place_id`/`dataset_id`/`grain_key`/`record_status`/`manual_rejected_rows`/`distinct_inactive_reasons`/`liveness`）。**枚举值个数 ≠ 列数，两者不矛盾。**

```sql
CREATE VIEW v_place_liveness AS
WITH ev AS (
  SELECT e.place_id,
         bool_or(e.source_is_active IS TRUE
                 AND e.child_record_status IS DISTINCT FROM 'rejected')          AS has_valid,
         count(*) FILTER (WHERE e.child_rejected_by = 'manual')                  AS manual_rejected_rows,
         count(DISTINCT e.source_inactive_reason)
           FILTER (WHERE NOT e.source_is_active)                                 AS distinct_inactive_reasons,
         (array_agg(e.source_inactive_reason ORDER BY
              sr.inactive_at DESC NULLS LAST, sr.inactive_in_batch_id DESC NULLS LAST,
              CASE e.source_inactive_reason WHEN 'batch_rolled_back'    THEN 1
                                            WHEN 'duplicate_quarantine' THEN 2
                                            WHEN 'source_absent'        THEN 3 END)
          ) FILTER (WHERE NOT e.source_is_active)                                 AS reasons
  FROM v_place_evidence e
   -- ⭐ 修正（A-1）：LEFT JOIN source_record。既取 inactive_at / inactive_in_batch_id，
   --    又保留 source_record_id 为 NULL 的人工子行，供 manual_rejected_rows 等统计使用。
   LEFT JOIN source_record sr ON sr.source_record_id = e.source_record_id
  GROUP BY e.place_id
)
SELECT p.place_id, p.dataset_id, p.grain_key, p.record_status,
       coalesce(ev.manual_rejected_rows,0)       AS manual_rejected_rows,
       coalesce(ev.distinct_inactive_reasons,0)  AS distinct_inactive_reasons,
       CASE
         WHEN p.record_status = 'merged'                     THEN 'merged'
         WHEN p.created_by    = 'manual'                     THEN 'manual'
         WHEN coalesce(ev.has_valid,false)                   THEN 'active'
         WHEN coalesce(ev.distinct_inactive_reasons,0) > 1   THEN 'mixed_inactive'
         WHEN coalesce(ev.distinct_inactive_reasons,0) = 1   THEN
              CASE ev.reasons[1] WHEN 'source_absent'        THEN 'all_sources_absent'
                                 WHEN 'batch_rolled_back'    THEN 'all_sources_rolled_back'
                                 WHEN 'duplicate_quarantine' THEN 'quarantined_only' END
         ELSE 'orphaned'
       END AS liveness
FROM historical_place p LEFT JOIN ev ON ev.place_id = p.place_id;
```

> **⭐ 修正说明（A-1 / QA F-03，本版留痕）**：`ev` CTE 原写 `FROM v_place_evidence e` 却在 `ORDER BY` 里引用 `e.inactive_at` / `e.inactive_in_batch_id`——**该视图固定 11 列，没有这两列**（见 §5.10.1 列清单），SQL **无法编译**。
> 本版使用 `LEFT JOIN source_record sr ON sr.source_record_id = e.source_record_id`：既从源记录取 `sr.inactive_at` / `sr.inactive_in_batch_id`，又不丢弃 `source_record_id IS NULL` 的人工子行；与 V0.2.1 §2.3.4 的来源字段一致。
> **根因留痕**：V0.2.2-r2 §2.2.4 把 CTE 里的 `JOIN source_record sr` 去掉、把 `sr.` 全部改成 `e.`，却**未给 `v_place_evidence` 补这两列** ⇒ 权威设计自身的笔误。本版按 V0.2.1 补回 JOIN，**不采用"给视图加两列变 13 列"的解法**（那会破坏 §5.10.1 的 11 列定式与 §5.10.5 的逐列清单）。
> **GROUP BY 不变**：`sr.inactive_at` / `sr.inactive_in_batch_id` 只出现在聚合函数内部（`array_agg(... ORDER BY ...)`），`source_record_id` 是 `source_record` 的主键 ⇒ 功能上依赖 `e.place_id`，`GROUP BY e.place_id` 仍充分。

> **⚠️ 补全项声明（非新设计）**：V0.2.2-r2 §2.2.4（行 254–265）的 `SELECT` 写作 `SELECT p.place_id, ..., CASE … END AS liveness, ...`，**省略号未补全**。上表的对外列清单是**本文件依据 V0.2.2 §2.1.2（八值 `liveness` 与派生优先级）、§2.2.3（有效证据定义）、§2.2.5（四场景 A–D）以及 V0.2.1 §2.3.4 的已枚举列补全的**，属**补全项、不是新设计**。列入附录 B 施工验证清单 **B-4-1**，待 QA 复算确认。

**对外列清单（补全，**7 列**）**【留痕：口径修正，QA F-04】：

| # | 列 | 说明 |
|---:|---|---|
| 1 | `place_id` | |
| 2 | `dataset_id` | 来自 `historical_place` |
| 3 | `grain_key` | 来自 `historical_place` |
| 4 | `record_status` | 来自 `historical_place`（3 值） |
| 5 | `manual_rejected_rows` | **对外新增**：`child_rejected_by='manual'` 的行数，供场景 D 与台账使用 |
| 6 | `distinct_inactive_reasons` | **对外新增**：不同失效原因数，用于判 `mixed_inactive` |
| 7 | `liveness` | **8 值**，见下 |
| — | `has_valid` / `reasons` | **CTE 中间量，不计入对外列**（与 SQL 一致：`ev` 的两个 CTE 局部列不出现在外层 `SELECT`） |
| — | `last_inactive_reason` | V0.2.1 的标量列，**本版已被 `reasons` 数组取代，不对外** |

> **⭐ 口径修正（QA F-04，非 team-lead 清单项，由架构师判定为同族施工级矛盾一并修正）**：本节旧稿标题写「**9 列**」，但表内只编号 **1–7**、SQL `SELECT` 也只输出 **7 列** ⇒ **标题与实体自相矛盾**（与 F-03/F-05/F-11 同属"视图定义自相矛盾"一族，属施工级）。
> 本版按 **QA 建议的方案 A**（SQL 不动）统一为 **7 列**：`coalesce()` 包裹的对外列共 7 个；`has_valid` / `reasons` 明确为 CTE 中间量。
> **§5.10.5 的「对外新增 2」不变**（`distinct_inactive_reasons` / `manual_rejected_rows` 是本版相对 V0.2.1 **新增**的对外列，与"总列数 7"是两个不同口径，不冲突）。
> **⛔ 与 `SHARED_BASELINE_V2.1.1.md` §14.2 的冲突**：该文件把 `has_valid` / `reasons` 列为对外列 ⇒ **须由 team-lead 同步改为"CTE 中间量，不对外"**，否则两文件互斥（QA F-04 要求两文件同步，本次只修 CORE）。

**`liveness` 8 值的派生优先级（自上而下，命中即返回，顺序不可换）**：

| 序 | 判据 | `liveness` | 类别 |
|---:|---|---|---|
| 1 | `record_status = 'merged'` | `merged` | 合并态 |
| 2 | `created_by = 'manual'` | `manual` | 有效态（永不失效） |
| 3 | ∃ 有效证据 | `active` | 有效态 |
| 4 | 证据全失效，原因**唯一** = `source_absent` | `all_sources_absent` | 来源失效态 |
| 5 | 证据全失效，原因**唯一** = `batch_rolled_back` | `all_sources_rolled_back` | 批次回滚态 |
| 6 | 证据全失效，原因**唯一** = `duplicate_quarantine` | `quarantined_only` | 隔离态 |
| 7 | 证据全失效，原因 **≥2 种** | **`mixed_inactive`**（本版新增） | 混合失效态 |
| 8 | 证据集为空，或有失效但原因缺失 | `orphaned` | 孤立态（非法终态，断言 = 0） |

**真值表（`liveness` × `record_status`，✅ = 唯一合法组合）**：

| `liveness` | `staging` | `rejected` | `merged` |
|---|---|---|---|
| `active` | ✅ | ❌ | ❌ |
| `manual` | ✅ | ❌ | ❌ |
| `merged` | ❌ | ❌ | ✅ |
| `all_sources_absent` | ❌ | ✅ | ❌ |
| `all_sources_rolled_back` | ❌ | ✅ | ❌ |
| `quarantined_only` | ❌ | ✅ | ❌ |
| `mixed_inactive` | ❌ | ✅ | ❌ |
| `orphaned` | ❌ | ❌ | ❌（**唯一允许 0 个 ✅ 的行**） |

**记 `FAILURE_SET = {all_sources_absent, all_sources_rolled_back, quarantined_only, mixed_inactive}`。**

```
rejected ⟺ liveness ∈ FAILURE_SET
```

```sql
-- C27  本表除 orphaned 行外，每一行 ✅ 恰有 1 个；orphaned 行 ✅ 恰有 0 个
--      （即 count(合法组合) == 7，且不存在同一 liveness 对应两个 record_status）
-- C28  本表与派生优先级衔接：∀ 行，liveness 由优先级自上而下首次命中决定；
--      若某格与优先级冲突（如 (manual, merged)），该格恒不可达，必须置 ❌

R4a  count(historical_place WHERE record_status='rejected'
             AND liveness NOT IN ('all_sources_absent','all_sources_rolled_back',
                                  'quarantined_only','mixed_inactive'))          == 0
R4b  count(historical_place WHERE liveness IN ('all_sources_absent','all_sources_rolled_back',
                                               'quarantined_only','mixed_inactive')
             AND record_status <> 'rejected')                                     == 0
R4c  count(historical_place WHERE liveness='active' AND record_status='rejected') == 0
R4d  count(historical_place WHERE liveness='manual' AND record_status='rejected') == 0
R4e  count(historical_place WHERE liveness='merged' AND record_status<>'merged')  == 0
R4f  count(historical_place WHERE liveness='orphaned')                            == 0
```

> **`(manual, merged)` 取 ❌ 的理由**：优先级第 1 行（`record_status='merged' ⇒ liveness='merged'`）在第 2 行（`created_by='manual'`）**之前**命中 ⇒ 该格**永远不可达**。保留 ✅ 会让表头自相矛盾，并诱导实现者写出"先判 manual 再判 merged"的代码（与本设计相反）。信息不丢失——"人工地点可被人工合并"由 `merged` 行表达；`manual` 行语义退化为"人工创建且未被合并"。

#### 5.10.3 `v_place_time_span`

```sql
CREATE VIEW v_place_time_span AS
WITH child AS (
    SELECT place_id, source_record_id,
           valid_from_year_astro AS f, valid_to_year_astro AS t, record_status
      FROM historical_place_name
    UNION ALL
    SELECT place_id, source_record_id,
           valid_from_year_astro,     valid_to_year_astro,      record_status
      FROM historical_place_location
    -- 刻意不 UNION 任何 edge/connection 来源：见 §6.3
), eff AS (
    SELECT c.*, sr.is_active
      FROM child c
      JOIN source_record sr ON sr.source_record_id = c.source_record_id
     WHERE c.record_status <> 'rejected'
       AND sr.is_active
)
SELECT p.place_id,
       MIN(e.f) FILTER (WHERE e.f IS NOT NULL)                    AS span_from_astro,
       MAX(e.t) FILTER (WHERE e.t IS NOT NULL)                    AS span_to_astro,
       count(*) FILTER (WHERE e.f IS NOT NULL)                    AS from_evidence_rows,
       count(*) FILTER (WHERE e.t IS NOT NULL)                    AS to_evidence_rows,
       count(*) FILTER (WHERE e.record_status = 'staging')        AS staging_evidence_rows,
       count(e.place_id)                                          AS valid_child_rows,   -- ⭐ A-2 修正：不用裸 count(*)
       (SELECT count(*) FROM child c2 WHERE c2.place_id = p.place_id)
                                                                  AS child_rows_total,
       CASE
         WHEN count(*) FILTER (WHERE (e.f IS NOT NULL OR e.t IS NOT NULL)) = 0
              THEN 'no_evidence'
         WHEN MIN(e.f) IS NOT NULL AND MAX(e.t) IS NOT NULL AND MIN(e.f) = MAX(e.t)
              THEN 'single_point'
         ELSE 'envelope_of_name_and_location_rows'
       END                                                        AS derivation_kind,
       (   (SELECT count(*) FROM child c3 WHERE c3.place_id = p.place_id) > 0
       AND count(e.place_id) = 0 )                                AS all_children_rejected -- ⭐ A-2 修正
FROM historical_place p
LEFT JOIN eff e ON e.place_id = p.place_id
GROUP BY p.place_id;
```

> **⭐ 修正说明（A-2 / QA F-05，本版留痕）**：原写 `count(*) AS valid_child_rows` 与 `AND count(*) = 0`。因为主查询是 `historical_place p LEFT JOIN eff e`，**LEFT JOIN 无匹配时仍产生 1 行全 NULL** ⇒ `count(*)` = **1**（不是 0）⇒ `valid_child_rows` 对"无有效子行"的地点恒 ≥1 ⇒ `all_children_rejected`（定义 `child_rows_total > 0 AND valid_child_rows = 0`）**永不可能为真** ⇒ T5 豁免 ② 完全失效。
> 改用 `count(e.place_id)`：`e.place_id` 在无匹配行为 NULL，`count(列)` **不计 NULL** ⇒ 无有效子行时得 **0**，语义恢复。
> **其余 `count(*) FILTER (...)` 保持不动**：`FILTER` 子句在无匹配行时该行被排除（`e.f IS NOT NULL` 为 NULL ⇒ 不计数），语义已安全；只有**无 FILTER 的裸 `count(*)`** 有问题。
> **这也是一个回归**：V2.1 §5.5.4 用 `COUNT(c.*) FILTER(...)`、V0.2.1 §2.6.1 用 `count(*) FILTER(...)`，都未出现"裸 `count(*)` 当有效行数"的写法。

**⭐ 过滤条件（写死）**：

```sql
WHERE c.record_status <> 'rejected'
  AND sr.is_active
```

> ⛔ **过滤是 `record_status <> 'rejected'`，不是 `'published'`。**
> V2.1 §5.5.4（行 413–427）用的是 `record_status = 'published'`——实测使 **0/19,039（入库口径）** 个地点有跨度（视图整体空转），因为子表 CSV 根本没有 `record_status` 列，且 V2.1 全文无发布动作。改为 `<> 'rejected'` 后 **17,469/19,039** 有跨度（**暂存态干跑**；加 `sr.is_active` 后待复算）。
> ⛔ **禁止用"默认 published"绕过**：那会让 646 条未知 CRS + 10 条无几何直接越过两道门禁。

**列清单（10 列）**：

| # | 列 | 说明 |
|---:|---|---|
| 1 | `place_id` | |
| 2 | `span_from_astro` | 有效子行 `MIN(f)` |
| 3 | `span_to_astro` | 有效子行 `MAX(t)` |
| 4 | `from_evidence_rows` | 有效子行中 `f IS NOT NULL` 的行数 |
| 5 | `to_evidence_rows` | 有效子行中 `t IS NOT NULL` 的行数 |
| 6 | `staging_evidence_rows` | 有效子行中仍为 `staging` 的行数 |
| 7 | `valid_child_rows` | **本版新增** |
| 8 | `child_rows_total` | **本版新增**：该地点全部 name+location 行数（**不过滤**） |
| 9 | `derivation_kind` | **3 值**，见 §6.3 |
| 10 | `all_children_rejected` | **本版新增**：`child_rows_total > 0 AND valid_child_rows = 0` |

**四条不变式（施工后逐条验，必须 0 违反）**：

```
T1  from_evidence_rows = 0 ⇒ span_from_astro IS NULL
T2  to_evidence_rows   = 0 ⇒ span_to_astro   IS NULL
T3  span_from_astro > span_to_astro 的行数 == 0（倒挂的 28 条在子行上已留空）
T4  derivation_kind 三值计数 == 1,570 / 361 / 17,108（合计 19,039，暂存态干跑）
    且 count(derivation_kind='single_point' AND span_from_astro IS NULL) = 0
```

**新增断言 T5（三项豁免）**：

```
T5  count(place WHERE liveness='active'
                 AND derivation_kind='no_evidence'
                 AND NOT ( child_rows_total = 0
                        OR all_children_rejected
                        OR ( valid_child_rows > 0
                             AND 全部有效子行的 f 与 t 皆为 NULL ))) == 0
```

豁免三选一：① **本来就没有子行**；② **子行全被拒**；③ **有有效子行，但那些子行本来就没有年份值**。

> **T5 的有效命中率（写进交付物，避免高估断言价值）**：暂存态干跑中"被过滤"情形 **0 例**，T5 抓到的 1,255 个**全是**"本来没有"。**T5 在真实数据上 0% 有效命中**——它是**防未来回归的护栏**，不是当前的缺陷探测器。三项豁免后干跑 **T5 = 0** ✓。

#### 5.10.4 `is_canonical_row` 的定序（写死，**已落地为可执行 SQL**）

```
is_canonical_row ⇔ 该行是本地点证据集中定序第一的行
实现位置：§5.10.1 视图的外层窗口函数 row_number() OVER (PARTITION BY place_id ORDER BY …) = 1

排序键（写死，顺序不可换）：
  ⓿ (source_is_active AND child_record_status IS DISTINCT FROM 'rejected') DESC
                                                 -- 有效证据优先（§5.10.1「有效证据」定义的落地）
  ① (evidence_role = 'creator') DESC             -- 创建记录优先
  ② sr.duplicate_ordinal ASC NULLS LAST          -- 与 §4.3 同源（回连 source_record 取值）
  ③ sr.external_id       ASC NULLS LAST          -- MCGD 即"NameID 最小"（回连 source_record 取值）
  ④ source_record_id     ASC                     -- 破并列（可复现）
  ⑤ coalesce(child_row_id, 0) ASC                -- 同记录多行 name 的行级破并列（可复现）
```

> ⛔ **②③ 必须回连 `source_record`**：`duplicate_ordinal` / `external_id` **不是** `v_place_evidence` 的列。任何"在视图内直接 ORDER BY 这两列"的写法都不可执行——这是 F-11 的原缺陷之一。
> ⛔ **⑤ 不可省略**：C08 允许一条 `source_record` 派生最多 3 行 name（`name_type` 不同），其 ②③④ 键**全同**；缺 ⑤ 则并列行的 `row_number()` 取值**不可复现**，315 个（入库口径）无子行地点之外的追溯结果会随机漂移。
> ⛔ **⓿ 不可省略**：定义句写的是"**有效证据**中定序第一的行"。缺 ⓿ 时，一条 `rejected` 子行或失效源行可能排到有效证据之前成为 canonical ⇒ 视图语义与定义句自相矛盾。
> ⛔ **零有效证据的地点**：`is_canonical_row` 仍会落在一行（"最佳可得"），仅用于追溯；该地点的 `liveness` 必属 `FAILURE_SET` 或 `orphaned`（§5.10.2）。**这不是缺陷**，但 `DATA_PROVENANCE` 必须写明"canonical ≠ 有效"。

- **315 个无子行地点（入库口径）**：唯一证据是 `creator` 行 ⇒ `is_canonical_row=true` 落在它身上，追溯通路为 `place → v_place_evidence(creator, is_canonical_row) → source_record → raw_file + raw_record_index`，其值为 `raw_payload.title`。**不需要也不允许制造名称子行。**（**方案①落地后本条已可实现**；旧稿 creator 分支写死 `FALSE` 时本条为**空断言**——见 F-11）
- **MCGD 643 个地点**：全部证据 `evidence_role='name'`，定序落到 ③ `external_id` ⇒ 最小 `NameID` ✓。
- **CHGIS**：`creator` 优先（①）⇒ 与 `places.csv` 的 `title` 同源 ✓。

**锚点 vs 当前最佳证据**：

| 概念 | 列 | 语义 | 是否随导入变 |
|---|---|---|---|
| **锚点** | `created_from_source_record_id` | 首次导入时的身份记录（IDENTITY，永不改写） | 否 |
| **当前最佳证据** | `v_place_evidence.is_canonical_row` | 每次导入重算 | 是 |

二者指向不同记录 **不是错误**，不落台账；`DATA_PROVENANCE` 必须写明这是设计选择。
`canonical_name` 被人工修改 ⇒ 该字段进 `manual_edited_fields` ⇒ 导入器 **KEEP_MANUAL**；此时 `is_canonical_row` **仍指向源行**（用于追溯"这个地点本该叫什么、来自哪里"），显示值取人工值。

#### 5.10.5 视图派生列：逐视图逐列名清单（**不给单一合计数**）

| 视图 | V0.2.1 | V0.2.2 / V2.1.1 | 新增派生列（逐列名） |
|---|---|---|---|
| `v_place_evidence` | 4 列 | **11 列** | **7**：`source_is_active` / `source_inactive_reason` / `child_table` / `child_row_id` / `child_record_status` / `child_rejected_by` / `is_canonical_row`（最后一个由外层窗口定序**实际计算**，非占位符） |
| `v_place_time_span` | 6 列 | **10 列** | **3**：`child_rows_total` / `valid_child_rows` / `all_children_rejected` |
| `v_place_liveness` | 8 列 | **7 列**（对外）【留痕：口径修正，QA F-04】 | **对外新增 2**：`distinct_inactive_reasons` / `manual_rejected_rows`；CTE 内 `has_valid` / `reasons` 为**中间量，不计入对外列** |

> **`v_place_liveness` 的算术核对**（防止下轮又被读成两个数打架）：V0.2.1 的 8 列中，`active_creator_rows` / `active_child_rows` / `last_inactive_reason` **3 列被取代**（前两者不再对外，后者被 `reasons` 数组取代），新增 `distinct_inactive_reasons` / `manual_rejected_rows` **2 列** ⇒ 8 − 3 + 2 = **7** ✓。**"对外新增 2" 与 "对外总列数 7" 是两个口径，不矛盾。**

**作废口径对照表**（三个旧数全部标明作废原因）：

| 旧表述 | 出处 | 作废原因 |
|---|---|---|
| 新视图派生列 **+8** | V0.2.2 §1（行 66） | **分母不明**（未说明含哪些视图、是否含 liveness 的 CTE 中间量） |
| 新增 **6** 个派生列 | V0.2.2 §2.2.2（行 220） | 只数了 6 个状态列，**漏 `is_canonical_row`** |
| `v_place_evidence` **10 列** | V0.2.2 §6-3（行 1052） | **漏 `is_canonical_row`** |
| `v_place_evidence` 的 creator 分支 **`FALSE AS is_canonical_row`** | V0.2.2 §2.2.2（行 201） | **与 §2.8.2（行 816）「315 个无子行地点的 canonical 落在 creator 行」直接矛盾**；本版按外层窗口定序解决（§5.10.1 / §5.10.4），CHANGELOG 留痕 |
| ② 分支 `<canonical 定序 §5.10.4>` **占位符** | V0.2.2 §2.2.2（行 209） | **不是可执行 SQL**；本版已替换为实际 `row_number()` 计算，全文**无占位符** |

> ⛔ **交付物一律不再出现任何"新增派生列合计数"**，改用上表逐视图逐列名清单 + 作废口径对照。
> 根因：`v_place_liveness` 的 `SELECT` 在 V0.2.2-r2 中以 `...` 省略，**"新增派生列总数"无法从 V0.2.2-r2 精确算出**；强行给一个数等于制造第四个口径。

#### 5.10.6 ⛔ `架构/V2.1/ER_DIAGRAM_V2.1.svg` 已作废

```
【作废声明】架构/V2.1/ER_DIAGRAM_V2.1.svg 自本版起作废，不得作为施工依据。
作废理由：该图的 v_place_time_span 图注仍写「只聚合 record_status='published' 子行」。
照图施工 ⇒ **19,039 个（入库口径）**地点的时间跨度全部为 NULL（视图整体空转，实测 0/19,039 有跨度）。
替代：一律以本文件 §5.10.3 的 SQL 为准（过滤 record_status <> 'rejected' AND sr.is_active）。
```
（V0.2.1 `V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` 行 1639 记「保留 9 表 + 2 视图的布局骨架与配色」——**本版仅保留该图的"骨架与配色"参考价值，其图注中的过滤条件一律作废**。）

---

## 6. 时间模型

### 6.1 `time_bound_type`（**7 值**）

| 值 | 语义 | 数据里意味着什么 | 实测（位置 / 名称） |
|---|---|---|---|
| `exact` | 两个端点都是源声明的事实 | "存在于 −214 到 −207 年" | 8,057 / 21,614 |
| `bounded` | 两端都是界限 | "不早于 X，不晚于 Y" | 398 / **1,166** |
| `exact_or_bounded` | 端点混合，源未逐端区分 | — | 812 / **2,360** |
| `tpq_taq` | 两端都是 TPQ/TAQ 界限 | Pleiades 的 `year_after_which`/`year_before_which` | 1,159 / 1,774 |
| `derived_tpq_taq` | 由子行聚合出的 TPQ/TAQ | 只出现在地点级 | 0 / 0 |
| `snapshot` | 单年快照 | CHGIS `BEG_YR = END_YR` 的 21 行 | 21 / 54 |
| `unknown` | 源未声明 | — | 7,656 / 20,535 |

- **七值全序列**：`exact` / `bounded` / `exact_or_bounded` / `tpq_taq` / `derived_tpq_taq` / `snapshot` / `unknown`。
- ⛔ **`exact_or_bounded` 2,360 与 `bounded` 1,166 不得互换**。
- `tpq_taq` 与 `bounded` 的区别：`bounded` 说"这两个端点是界限"，`tpq_taq` 说"这两个端点是**特定类型**的界限，且 Pleiades 用这两个字段名"。本项目取 `tpq_taq` 是保留源词汇。**不要让下游代码依赖这个区分做逻辑分支**——两者在渲染上应当同处理。
- `unknown` 的行**可以**有年份值（Pleiades 单侧 TPQ）；`exact` 的行**必须**两端都有值（C16）。

### 6.2 `time_derivation`（**仅暂存，不入库**）

| 值 | 地点数 | 语义 |
|---|---:|---|
| `min_max_of_children` | 15,718 | CHGIS：子记录年份的包络 |
| `tpq_taq_of_children` | 1,816 | Pleiades：子记录 TPQ/TAQ 的包络 |
| `none` | 1,505 | 无子行有时值 ⇒ 两端皆 NULL、`time_bound_type='unknown'` |

> ⚠️ 该列是**暂存列**，不入库。它的 1,505 是**旧口径**（含 connection），**不得**与 §6.3 的 `no_evidence` 1,570 混用。

### 6.3 `derivation_kind`（**3 值**，不得出现第 4 值）

| 值 | 判据（**必须两端均非 NULL** 才可判 `single_point`） | 期望计数（**暂存态干跑**） |
|---|---|---:|
| `no_evidence` | `count(*) FILTER (WHERE (f IS NOT NULL OR t IS NOT NULL) AND 有效) = 0` | **1,570** |
| `single_point` | `span_from_astro IS NOT NULL AND span_to_astro IS NOT NULL AND span_from_astro = span_to_astro` | **361** |
| `envelope_of_name_and_location_rows` | 其余（含"仅单侧有值"） | **17,108** |

- 合计 **19,039（入库口径；暂存态干跑计数，加 `sr.is_active` 后待复算）**。
- ⛔ `single_point` **不得**写成 `MIN(f) = MAX(t)` 而不校验非 NULL——两端皆 NULL 时该表达式为 NULL（不是 TRUE），会落到 ELSE，把"无证据"误判成"包络"。

**`no_evidence` 的构成（暂存态干跑）= 1,570**：

| 组 | 数量 | 成因 |
|---|---:|---|
| **无子行** | **315** | 全部 Pleiades，走 T5 豁免 ① |
| **有子行但有效子行无年份** | **1,255** | 走 T5 豁免 ③；= `none` **1,230** + `tpq_taq_of_children` **25** |

⚠️ **那 1,255 个是两种不同成因，不得混为一谈**：

| 组 | 数量 | 成因 | 会不会被误读 |
|---|---:|---|---|
| `none` | **1,230** | **源端本来就没有年份**——子行无年份，地点自身也无年份 | 会（属"源端缺失"，找源数据是对的） |
| `tpq_taq_of_children` | **25** | **年份源是 connection，被「排除 connection」切掉了**。**这 25 个地点自身带年份**（实测 25/25 `valid_from/to_year_astro` 非空、`time_bound_type='derived_tpq_taq'`） | **会**——若写成"源端缺失"，下一轮会去源数据里找根本没有的缺失（死路） |

> **⚠️ 施工级硬提醒 H2**：`derivation_kind` 与 `no_evidence` 的计数**必须基于「只聚合 name + location、排除 connection」的重算结果**；
> **不得直接引用暂存 `historical_places.valid_from_year_astro` / `valid_to_year_astro`**——该两列由含 connection 的旧口径生成 ⇒ 会使 `no_evidence` **系统性偏低 65**（1,505 + 65 = 1,570）。

**为什么必须排除 connection/edge（四条证据链）**：① 实测 1,816/1,816 个有地点级时间的 Pleiades 地点，其值 == "全部 name+location+**connection** 源记录的年值包络"，0 例外；② 65/65 个"有地点级时间、但全部子行无时间"的地点，全部由 connection 的时间解释；③ 代码：`normalize.py:666` 把 `connection` 放进 `extra_children`，`normalize.py:494–509` 对全部 children 求包络；④ 语义：connection 的年份描述"两个地点之间关系的存续期"，不是"该地点存在到 X 年"——把边的时间写进点的存在期是**量纲错误**。

---

## 7. 门禁

三道门禁，全部在数据库层强制，不依赖导入器自觉。

| 门禁 | 约束 | 挡住什么 | 实测挡住 |
|---|---|---|---|
| **CRS** | `crs_confidence <> 'unknown' OR record_status <> 'published'`（C14） | 未知基准面的坐标进入正式层 | MCGD 643 条 + WHG 3 条 = **646 条** |
| **几何** | `geom IS NOT NULL OR record_status <> 'published'`（C15） | 无坐标的位置被发布 | 10 条（CHGIS `**********`） |
| **合并** | `merged_into_place_id IS NULL OR (record_status='merged' AND merge_review_ref IS NOT NULL AND merged_at IS NOT NULL)`（C06） | 无人审批的合并 | 本阶段 0 条合并 |

### 7.1 ⛔ 许可门禁已废除

**V2.1 §7 的第四道门「许可」在 V2.1.1 中不存在。**

- `data_dataset` 的 9 列许可相关列**全部删除**（§5.2）【留痕：明确不做语境】，`redistributable` / `license_id` / `attribution_text` 均不落库；
- **`data_source` 的 2 列许可相关列同样删除**（§5.1：`default_license_id` / `default_redistributable`）【留痕：已删除列说明，保留以便追溯，非现行模型】——**这一处极易漏**：V2.1 §5.1 只写「无变化」三字，继承了 V2 §5.1 的这两列，按列名 grep 查不到；
- V2.1 §7.1 的两步 SQL（经 `created_from_source_record_id` 回溯 `data_dataset` 查 `redistributable`）**不再可执行**【留痕：已作废 SQL 说明】；
- V2.1 §7.2 的"本轮实际可发布量"表（3,293 / 3,291 / 1,590）**一并作废**，其数字不得进入 V2.1.1 的权威数字表。

**本版显式声明**【留痕：明确不做语境】：本模型**不做**任何授权、许可、再分发判断（V0.2.2 §3.3）。**不重新引入 `attribution_text`、`citation_text` 或任何替代字段。**

### 7.2 内部视图的上图能力（口径：入库）

- 可上图的定位数：**入库 18,101** − 10（`geom IS NULL`）= **18,091**，覆盖 **17,971 个地点**；
- 无任何坐标的地点：**1,068**（Pleiades 1,058 + CHGIS 10）。

> V2 §12 写"Pleiades 2,643 个 place 里只有 2,233 个带坐标"**已作废**：实测是 **1,585 个带坐标、1,058 个不带**。差额 648 的来源是 V2 混用了两个口径（"有 location 行" vs "location 行有坐标"）。**任何写进对外材料的覆盖率数字，都必须指明分子分母的确切口径。**

---

## 8. 导入前置校验（写入前必须全部通过）

| # | 校验 | 不通过的后果 | 依据 |
|---|---|---|---|
| 1 | `data_dataset.record_scopes` 非空；源文件表头与声明一致；未出现未声明 scope | 整批拒绝 | §5.2 |
| 2 | `input_sha256` 与 `data_dataset.content_sha256` 的关系符合预期（相同 = 重导，不同 = 新版本） | 不同则要求显式确认 | §5.3 |
| 3 | 每条记录的 `record_scope` **与** `parent_external_id` 可派生；`parent_external_id` 无父级时写哨兵 `'-'` | **整批拒绝**（不允许默认值兜底、不允许 NULL） | §5.4.2、**C29** |
| 4 | 五段业务键唯一性预检；重复键全部命中"已知重复"清单 | 出现新重复 ⇒ 整批拒绝，人工确认后才可继续 | §4.1、§4.6 |
| 5 | 每个 place 能派生出唯一 `created_from_source_record_id` | 整批拒绝 | §5.5.4 |
| 6 | 每个 place 能派生出唯一 `grain_key`（`place_grain` 值域内） | 整批拒绝 | §5.5.3 |
| 7 | 地点级时间重算与暂存值比对，偏差行数写入预期台账 | 偏差数超出预登记阈值 ⇒ 警告 | §5.10.3、§6.3 |
| 8 | `derivation_version` 已声明 | 整批拒绝 | §5.3 |

**第 3 条为什么这么硬**：`parent_external_id` 漏掉的后果是 398 组 / 2,335 行被误判为重复（真实 7 组 / 14 行），**数百条记录被误隔离**。这是**静默数据损坏，不报错**。
**第 1 条为什么这么硬**：`record_scope` 派生失败时若兜底成 `place`，MCGD 的 960 行会变成 960 个地点（而不是 643 个），错误会以"看起来正常"的形态进库，事后极难发现。**宁可整批失败。**

---

## 9. 本轮实测基线

> **口径纪律（F18 / K4）**：`暂存原始` = 七张暂存 CSV 的实测行数；`隔离后` = 执行 V2.1.1 隔离规则后的行数；`预计入库` = 进入目标表的行数。三者**不得混用**，凡出现必须带口径词。**只写一个数即判缺陷。**

### 9.1 暂存输入（七张 CSV）

| 文件 | **暂存原始**行数 | 字节 |
|---|---:|---:|
| `historical_places.csv` | 19,039 | 4,953,976 |
| `historical_place_locations.csv` | 18,103 | 11,698,567 |
| `historical_place_names.csv` | 47,503 | 8,937,942 |
| `source_records.csv` | 29,391 | 26,942,777 |
| `candidate_matches.csv` | **53,137**（登记项，见 §9.4） | 17,315,204 |
| `data_quality_issues.csv` | 12,631（**暂存原始**） | 5,277,273 |
| `data_datasets.csv` | 7 | 6,018 |

### 9.2 权威数字（N01–N18，逐字抄自 V0.2.2 §0 行 25–44）

| # | 项 | **暂存原始** | **隔离后 / 预计入库** | 差 | 说明 |
|---|---|---:|---:|---:|---|
| N01 | `source_record` | 29,391 | 29,391 | 0 | 隔离不删行，只置 `is_active=false` |
| N02 | 其中 `is_active=false` | 0 | **3** | +3 | 2 CHGIS（`sr_0004941`/`sr_0004942`）+ 1 Pleiades edge |
| N03 | 活性源记录 | 29,391 | **29,388** | −3 | |
| N04 | `duplicate_ordinal=0` | **29,377** | 29,377 | 0 | 另 7 组 × 2 行 = 14 行，ordinal 1/2 各 7 行 |
| N05 | `historical_place` | 19,039 | **19,039** | 0 | CHGIS 15,746 + Pleiades 2,643 + MCGD 643 + WHG 7 |
| N06 | `historical_place_name` | **47,503** | **47,499** | −4 | 被隔离的 2 条 CHGIS 各派生 2 条名称 |
| N07 | `historical_place_location` | **18,103** | **18,101** | −2 | 被隔离的 2 条 CHGIS 各派生 1 条位置 |
| N08 | `data_quality_issue` | 12,631（**暂存原始**） | **12,831（预计入库）** | +200 | = 12,631 − 2（删 `licence_unconfirmed`【留痕：删枚举值】）+ 5 + 197。⛔ **两个数不得混用**：`12,631` 只在「暂存原始」语境，`12,831` 只在「入库」语境 |
| N09 | `record_scope='place'` 记录 | **18,398** | **18,396** | −2 | 18,398 − 2 隔离 = 18,396 = 19,039 − 643 ✓ |
| N10 | `record_scope` 全域 | place 18,398 / name 5,762 / location 2,468 / edge 2,763 | 同 | 0 | **仅 4 种，无第五种** |
| N11 | 无子行地点 | **315** | 315 | 0 | 全部 Pleiades，`canonical_name` 315/315 非空 |
| N12 | 无子行的源记录 | **8,682**（**口径 A**） | 8,682 | 0 | place 2,650 / name 2,513 / location 756 / edge 2,763。**口径 B** = **8,218**；差 464 = place 74 + edge 390。**钉死口径 A** |
| N13 | name 表 `time_bound_type` | exact 21,614 / exact_or_bounded **2,360** / unknown 20,535 / **bounded 1,166** / snapshot 54 / tpq_taq 1,774 | 同 | 0 | 2,360 与 1,166 **不得互换** |
| N14 | 时间视图有跨度地点 | **17,469** / 19,039 | — | 待复算 | 过滤改为"有效证据"后需重算（**未验证**） |
| N15 | 时间三值（只聚合 name+location） | `no_evidence` **1,570** / `single_point` 361 / `envelope…` 17,108 | 同 | 0 | 合计 19,039。⚠️ 暂存 `historical_places` 列算出的 1,505 是旧口径（含 connection），**偏低 65** |
| N16 | `no_evidence` 的构成（**暂存态干跑**） | 1,570 = **315** + **1,255**（`none` 1,230 + `tpq_taq_of_children` 25） | — | 0 | **T5 三项豁免后干跑 = 0** |
| N17 | 重复组口径对照 | 漏 `parent_external_id`：**398 组 / 2,335 行**；五段键：**7 组 / 14 行** | 同 | 0 | 差两个数量级；`ordinal=0` = **29,377** |
| N18 | 被隔离的 3 条 | `sr_0004941` / `sr_0004942`（CHGIS）+ `sr_0027175`（Pleiades connection 20469） | 同 | 0 | 活性 **29,388** |

**入库后各源份额（复算，供核对）**

| 表 | CHGIS | Pleiades | MCGD | WHG | 合计（**预计入库**） |
|---|---:|---:|---:|---:|---:|
| `historical_place` | 15,746 | 2,643 | 643 | 7 | **19,039** |
| `historical_place_location` | 15,746 | 1,704 | 643 | 8 | **18,101** |
| `historical_place_name` | 44,242 | 2,074 | 960 | 223 | **47,499** |
| `source_record`（活性，**隔离后**） | 15,746 | 12,442 | 960 | 238 | **29,388** |

> **Pleiades 的 4,579 条 name 记录只产出 2,074 行名称，2,460 条 location 记录只产出 1,704 行位置**。差额（2,505 + 756）不是错误，是"父地点不在切片内"——切片按 `places.csv` 前 2,643 行截断。这类记录**不入库**（否则会造出没有地点的孤儿名称），全部记 `parent_place_not_in_sample`。**这是切片方法的必然代价，不是数据质量问题。**

### 9.3 七个数据集的关键取值（删许可列后）

| dataset_id | `place_grain` | `record_scopes` | 记录数（**暂存原始**） |
|---|---|---|---:|
| `chgis_v6_prefecture_points` | `per_record` | `{place}` | 5,226 |
| `chgis_v6_county_points` | `per_record` | `{place}` | 10,522 |
| `mcgd_zenodo_22094815_head960` | **`per_parent_external_id`** | `{name}` | 960 |
| `pleiades_gis_4_1_slice` | `per_record` | `{place,name,location,edge}` | 12,445 |
| `whg_geoname_s_gn_sample` | `per_record` | `{place,name,location}` | 209 |
| `whg_getty_tgn_sample` | `per_record` | `{place,name,location}` | 21 |
| `whg_hgis_de_las_indias_sample` | `per_record` | `{place,name,location}` | 8 |

### 9.4 ⛔ `candidate_match` 不得进权威数字表

```
candidate_match 暂存 53,137 / 隔离后 53,103 —— 是【登记项 U18，待 Owner 拍板】，
不得写入本文件 §9.2 的 N01–N18 权威数字表。
```

（V0.2.2 §5.3 行 1039，逐字）：V0.2.1 写 53,133；实测**暂存 53,137**；与 2 条隔离记录相关的候选行共 34 行 / 33 个键，按 Owner 决策 4 应扣 34 ⇒ **53,103**；V0.2.1 只扣了 C09 同向收敛的 4 行。**以 data-auditor 审计报告为准，架构侧只登记、不自行改数。**

---

## 10. 与 V2.1 / V2 的差异一览

| 项 | V2.1 | V2.1.1 | 为什么改 |
|---|---|---|---|
| 业务唯一键 | 四段（含 `occurrence_key`） | **五段**（`parent_external_id` + `duplicate_ordinal`） | 漏 `parent` ⇒ 398 组误判，静默数据损坏 |
| `parent_external_id` | 可 NULL | **必需段**，无父级写哨兵 `'-'` | Postgres UNIQUE 对多列 NULL 不去重 |
| `content_hash` | 未写死表达式 | **`sha256(json.dumps(...))` 逐字写死** | 表达式不写死 ⇒ 跨实现分歧 |
| 台账唯一键 | 两条部分索引 | **`UNIQUE(issue_fingerprint)`**，md5 + JSON 数组六段 | 197 条派生偏差要有稳定身份 |
| 台账语义 | 未声明 | **语义 A + 三个伴生列** | 重导不得产生第二行 |
| `rejected_by` | 无 | **name/location 各 1 列** | 自动失效与人工拒绝不可混 |
| `liveness` | 7 值 | **8 值**（+`mixed_inactive`） | 多原因混合是枚举缺值 |
| `evidence_role` | `place_record` / `creator` 并存 | **3 值**，禁用 `place_record` | 同名异义 |
| 建点判据 | `record_scope <> 'place'` | **白名单 + `place_grain` 显式声明** | `edge` 与未知类型不得默认放行 |
| `historical_place` dataset 列 | **不带** | **带 `dataset_id` + `grain_key`** | 白名单 join 与按组建点的前提 |
| `record_status`（地点） | 4 值 | **3 值** | `published` 在地点层无动作 |
| 时间视图过滤 | `= 'published'` | **`<> 'rejected'` AND `sr.is_active`** | `'published'` 使 0/19,039 有跨度 |
| `v_place_evidence` | 4 列 | **11 列** | 子行状态与源状态要可见 |
| `data_dataset` 许可列 | 9 列 | **0 列（全删）** | 不做授权/再分发判断 |
| 许可门禁 | 第 4 道门禁 | **废除** | 同上 |
| `issue_type` | 20 值 | **19 值** | 删 `licence_unconfirmed`【留痕：删枚举值】 |
| `canonical_name` 追溯 | 无视图列 | **`is_canonical_row` 视图派生列**（外层窗口定序） | **315 个（入库口径）**无子行地点要可追溯 |
| ER 图 | `ER_DIAGRAM_V2.1.svg` | **已作废**（图注仍写 `'published'`） | 照图施工 ⇒ 时间全 NULL |
| `place_grain` | 2 值（V2.1 收敛） | **不变，V2 既有列** | ⛔ 不得写成 V2.1.1 新增 |

---

## 11. 防漂移声明

本文件是 **V2.1.1 的唯一模型定义**。以下八条在后续修订中不得违反：

1. **地点表不带时间列、不带几何列、不带失效原因列。** 三样分别在子表与视图里。任何"顺手加一列"的补丁都会让 §5.5.5 的建点白名单与 §5.10.3 的时间口径脱钩。
2. **五段业务键的每一段都不得省略。** 尤其 `parent_external_id`（C29）——漏掉它是**静默数据损坏**，不是报错。
3. **枚举值必须是数据里出现过的，或明确标注为空集。** 新增枚举值时，必须在 §9 的复算里有对应计数。
4. **两种摘要算法（sha256 / md5）不得统一。** 改 `issue_fingerprint` 算法会使 197 条已算历史指纹全部对不上（ALG-1）。
5. **`candidate_match` 的行数不得进权威数字表**，直到 U18 由 Owner 拍板。
6. **三张视图的 SQL 必须是可编译的完整 SQL，不得出现占位符或引用视图不存在的列。** 本轮已修掉三类回归（§5.10.1 的 `<canonical 定序>` 占位符与写死 `FALSE`、§5.10.2 引用 `v_place_evidence` 不存在的 `inactive_at`、§5.10.3 用裸 `count(*)` 当有效行数）。**下轮若要从权威设计（V0.2.2）重新抄视图，必须先核这三条**——V0.2.2 §2.2.2 / §2.2.4 自身含这些缺陷，照抄即复发。
7. **`is_canonical_row` 的定序键 `duplicate_ordinal` / `external_id` 必须回连 `source_record` 取值。** 它们不是 `v_place_evidence` 的列；任何"在视图内直接 ORDER BY"的写法都不可执行（§5.10.4）。
8. **`data_quality_issue.dataset_id` 必须保持可空。** 改回 NOT NULL 会让 C11/C12 同时退化为恒真死约束（§5.9 / §5.0）。

### 11.1 两条施工级硬提醒（写进交付物正文）

**H1｜`normalize.py:306` 一旦改动必须回归 `content_hash`**

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

**H2｜`derivation_kind` / `no_evidence` 不得直读暂存 `valid_from/to_year_astro`**

```
计数必须基于「只聚合 name + location、排除 connection」的重算结果。
暂存 historical_places.valid_from_year_astro / valid_to_year_astro 由含 connection 的
旧口径生成 ⇒ 直接引用会使 no_evidence 系统性偏低 65（1,505 vs 1,570）。
```

---

## 附录 A｜约束全集 C01–C29 与有效条目计数

> **⭐ 唯一权威计数（不留多口径）**

| 口径 | 数 | 算法 |
|---|---:|---|
| C 编号总数 | **29** | C01–C29 |
| 减：废除 | −1 | C02（由 C20 取代） |
| 减：双编号 | −1 | C18 与 C03 同一条，去重后不另计 |
| **有效约束条目（唯一权威数）** | **27** | = V0.2.1 的 **22** + **C25/C26/C27/C28/C29** 共 5 条 |
| ├ 可落库的 SQL 约束（UNIQUE / CHECK） | **24** | = 22 + C25/C26 |
| └ 断言级 / 键级硬约束（**不落成 SQL CHECK**） | **3** | **C27 / C28 / C29** |

- **24 与 27 是同一全集的两个子集口径**（可落库 vs 全部有效），**不是矛盾**——这个关系必须写进交付物，否则下轮又会当成两个数打架。
- V0.2.2 §4-11（行 956）写的「编号范围 **C01–C26**」是 **r1 时刻的旧值**（当时 C27/C28/C29 未引入）。**V0.2.2 原文不动**；八份交付物一律写 **C01–C29**，并在 CHANGELOG 注明该编号范围的演进。
- **不属于 C 编号集合、单独列出**（不并入 24/27 任一数字）：**R2c**、**INV-1**、**ALG-1**、**CIT-1′**、**CIT-2′**、**T5**、**R4a–R4f**、**V3′/V4/V5**、**A12**。

**逐条落点**

| # | 约束 | 落点 | 状态 |
|---|---|---|---|
| C01 | `UNIQUE (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` | `source_record` | 保留（**五段**） |
| C02 | `CHECK (is_active OR duplicate_ordinal > 0)` | `source_record` | **废除** → C20 |
| C03 | `CHECK ((is_active AND inactive_reason IS NULL) OR (NOT is_active AND inactive_reason IS NOT NULL))` | `source_record` | 保留（不变量） |
| C04 | `UNIQUE (dataset_id, grain_key)` | `historical_place` | 保留 |
| C05 | `CHECK (created_by='manual' OR created_from_source_record_id IS NOT NULL)` | `historical_place` | 保留 |
| C06 | `CHECK (merged_into_place_id IS NULL OR (record_status='merged' AND merge_review_ref IS NOT NULL AND merged_at IS NOT NULL))` | `historical_place` | 保留 |
| C07 | `UNIQUE (source_record_id) WHERE source_record_id IS NOT NULL` | `historical_place_location` | 保留（0 冲突） |
| C08 | `UNIQUE (source_record_id, name_type, name_text, name_lang)` | `historical_place_name` | 保留（不得改单列 UNIQUE） |
| C09 | `UNIQUE (relation_type, place_id_a, place_id_b)` | `candidate_match` | 保留 |
| C10 | `UNIQUE (issue_fingerprint)` | `data_quality_issue` | 保留（替换两条部分索引） |
| C11 | `CHECK (dataset_id IS NOT NULL OR place_id IS NOT NULL)` | `data_quality_issue` | 保留 |
| C12 | `CHECK (dataset_id IS NOT NULL OR source_record_id IS NULL)` | `data_quality_issue` | 保留 |
| C13 | `CHECK (source_time_columns = '' OR (source_beg_rule IS NULL AND source_end_rule IS NULL))` | `historical_place_location`（**改名后**；name 表无 `source_beg_rule`/`source_end_rule`，故 C13 不落 name） | 保留（改名后） |
| C14 | `CHECK (crs_confidence <> 'unknown' OR record_status <> 'published')` | `historical_place_location` | 保留（CRS 门禁） |
| C15 | `CHECK (geom IS NOT NULL OR record_status <> 'published')` | `historical_place_location` | 保留（几何门禁） |
| C16 | `CHECK (time_bound_type <> 'exact' OR (两端均 NOT NULL))` | name / location | 保留 |
| C17 | `CHECK (direction = 'none' OR relation_type = 'location_migration_candidate')` | `candidate_match` | 保留 |
| C18 | 同 C03（V0.2 正式编号） | `source_record` | 保留（**双编号，去重后不另计**） |
| C19 | `CHECK (inactive_reason IS NULL OR inactive_reason IN (3 值))` | `source_record` | 保留 |
| C20 | `CHECK (inactive_reason <> 'duplicate_quarantine' OR duplicate_ordinal > 0)` | `source_record` | 保留（**取代 C02**） |
| C21 | `CHECK ((inactive_at IS NULL) = (inactive_reason IS NULL))` | `source_record` | 保留 |
| C22 | `CHECK ((inactive_in_batch_id IS NULL) = (inactive_reason IS NULL))` | `source_record` | 保留 |
| C23 | `CHECK (occurrence_count >= 1)` | `data_quality_issue` | 保留 |
| C24 | `CHECK (first_batch_id IS NULL OR last_batch_id IS NOT NULL)` | `data_quality_issue` | 保留 |
| **C25** | `CHECK ((record_status='rejected') = (rejected_by IS NOT NULL))`（name + location 各 1 条） | name / location | **新增（V0.2.2）** |
| **C26** | `CHECK (rejected_by IS NULL OR rejected_by IN ('auto','manual'))`（name + location 各 1 条） | name / location | **新增（V0.2.2）** |
| **C27** | 真值表除 `orphaned` 行外每行 ✅ 恰 1 个，`orphaned` 行恰 0 个 | §5.10.2 真值表 | **新增** — 断言级 |
| **C28** | 真值表与派生优先级衔接；冲突格恒不可达，必须置 ❌ | §5.10.2 真值表 | **新增** — 断言级 |
| **C29** | `parent_external_id` 必需段（不得省略/NULL/空串；无父级写哨兵 `'-'`；派生失败整批 failed；哨兵在 `data_dataset` 或常量表声明一次） | §4.2 五段键 | **新增** — 键级 |
| — | `CHECK (is_active OR occurrence_key <> '')` | `CORE_DATA_MODEL_V2.1.md:279` | **未编号，不计入 24/27**；意图已被 C20 + C29 覆盖 |

---

## 附录 B｜施工验证清单（**不得写成 PASS**）

> **本附录的每一项状态都是「未验证 / 未解决」。本文件不宣布通过，也不为任何一项预置通过结论。**
> QA 阶段二累计计数（`V0.2.2_QA_VERIFICATION.md` 行 704）：**PASS 35 / FAIL 1 / WARN 12 / 未验证 13 —— 存在 FAIL，不宣布通过。**
> **⚠️ 计数已更新（终检）**：终检（同文件 §16.5 **L794–797**）已更新为 **PASS 37 / FAIL 0 / WARN 12 / 未验证 13**，**X1/X2 已关闭**；本附录保留的是**需施工关闭的 12 WARN + 13 未验证**——即上行的 PASS 35 / FAIL 1 是**阶段二中间计数**，不是终态。**引用本附录时不得只抄 PASS 35 / FAIL 1 两个数**，必须连带本句，否则会把已关闭的 X1/X2 当成未关闭缺陷。
>
> **⭐ 禁用词留痕豁免规则（F-01 / D1-5 修订，适用全文）**：凡因「**已删除列逐列清单** / **明确不做** / **禁用词清单** / **删枚举值说明**」四类语境而引用旧列名（`attribution_text` / `citation_text` / `licence_unconfirmed` / `license_url` / `license_evidence` 等）者，**必须逐处标注【留痕】**。带【留痕】标记者**不计入**「命中数应为 0」的禁用词扫描。
> **不得删除这些引用**：§5.0 / §5.2 逐列列明已删列是 V0.2.2 / V0.2.1 的硬要求，删掉会制造追溯断点（下轮无法确认"曾经有这些列、为何删"）。**也不得把清单改写成"不复现旧名"的模糊表述**——那等于用不可核对换扫描通过。

### B.1 V0.2.2 §5.3 未解决 / 未验证清单（10 项，逐字抄录）

| # | 项 | 何时解决 |
|---|---|---|
| U3 | `v_place_evidence` 的 V1–V3 | 建库后首次导入 |
| U4 | `v_place_time_span` 的 V1–V3、T1–T5 | 同上 |
| U5 | 7 类操作（含判定表第 0 行）能否真正拦住 | 施工后造 7 个测试批次 |
| U12 | `v_place_time_span` 加 `sr.is_active` 后 17,469 的变化 | 建视图后复算 |
| U13 | `rejected_by` 两列是否误伤既有写入路径 | 建库后空跑导入 |
| U14 | 四场景 A–D 的端到端行为（暂存 0 条 rejected/merged/locked，无数据可验） | 施工后造影子批 |
| U15 | `STOP_AUTO` 的真实触发率（当前 0 例，需内容变更的源版本） | 下一次源更新 |
| U16 | `raw_record_index` 的真实语义（是"每文件计数器重新计数"，还是 WHG 抽取时的多文件合并残留？）实测**不是**文件内 1-based 唯一编号 | 下一轮；本轮只做"使用限制" |
| **U18** | `candidate_match` 总数（暂存 53,137 / 隔离后 53,103 vs V0.2.1 的 53,133） | **需 Owner / team-lead 裁定**是否连带修 V0.2.1 §0.2 |
| U19 | `issue_fingerprint` 是否同步改为 sha256 | **需 team-lead 转 Owner 裁定**（本版按 ALG-1 保持 md5） |

### B.2 V0.2.2 §5.2 标注「未验证」的断言（逐条）

| 断言 | 内容 | 状态 |
|---|---|---|
| R1 / R2 | 回滚统计口径（R1 的 RHS 已补 `- N_noop`） | 结构已验证；**未验证**：需真实回滚批次（U5）。**R2 未被降级** |
| **R2c** | `count(import_row_error WHERE batch_id=:Rb) == N_fail_rb` | **结构断言 + 未验证**：回滚期失败台账记在回滚批 `:Rb`；暂存原始 12,631 条台账中 `import_row_error` 零命中，入库预计 12,831 条中亦为 0，暂无真实回滚批次可代入 |
| T5 | `no_evidence` 可解释（三项豁免） | 暂存态干跑 **= 0** ✓；**未验证**：入库后（加 `sr.is_active` 需重跑） |
| C25 / C26 | `rejected_by` 同生同灭 + 值域 | 结构已验证；**未验证**：建库后误伤（U13） |
| C27 / C28 / C29 | 真值表机器可校验 + `parent_external_id` 必需 | 结构已验证；**未验证**：**建库后行为** |
| S1 | `duplicate_quarantine` 行不得派生任何子行 | 结构已验证；**未验证**（真实隔离批需施工后） |
| S2 | 回滚作用集不含 `duplicate_quarantine` 行 | 同上 |
| S3 | `STOP_AUTO` 时该组 `content_hash` / ordinal 不变 | 结构已验证；**未验证**（需造内容变更批次，U15） |
| V3′ / V4 / V5 | 建点白名单 | **未验证**（需建视图后跑） |
| V1 / V2 | 视图覆盖 | **未验证** |
| **V-8 / V-9 / V-10** | 本轮 9 条施工级缺陷修正的落地（`is_canonical_row` 窗口定序 / `v_place_liveness` 补 JOIN / `count(e.place_id)`） | **SQL 已改为可编译可执行**（占位符与裸 `count(*)` 已消除）；**未验证**：建视图后按 V-8/V-9/V-10 逐条复算 |
| K3 | 禁用词扫描（`place_record` / `attribution_text` / `citation_text` / `license`…）**【留痕：禁用词清单】** | **未验证**（属交付物阶段）。判据：命中数应为 0，**但带【留痕】标记者豁免**（凡「已删除列清单 / 明确不做 / 禁用词清单 / 删枚举值说明」语境） |
| CIT-1′ | 引用纪律（CIT-1a′/1b′/1c′） | 结构已验证；**未验证**：交付物编制后由 QA 扫 |
| CIT-2′ | `content_hash` 表达式三处逐字一致 | **已验证**（两处逐字相同 + `len 85` / sha1 复算一致）；**未验证**：交付物侧 |
| ALG-1 | 两种摘要算法并存不可统一 | 结构已验证；**未验证**：建库后行为 |
| L1 / L2 / L5 | `source_record` 侧状态 | 结构已验证 |

### B.3 12 项 WARN（逐条保留，均**未关闭**）

| # | 项 | 内容 |
|---|---|---|
| 1 | **A3** | V0.2.2 §4-11 只写"CHECK C01–C26"，未给总数 ⇒ 本版已在附录 A 给唯一数 27 / 24，并在 CHANGELOG 注明编号范围演进 |
| 2 | **C5** | P0-04 集合与恒等式（`N_normal = N_rolled_back + N_blocked + N_fail_rb + N_noop`）依赖五级判定顺序，顺序错 ⇒ 四类不互斥 ⇒ R1 不成立 |
| 3 | **D2** | ④「两条内容交换」与 §2.5 总原则的表面冲突 ⇒ 本版已按裁定写明"显式接受该不可观测性，不构成台账事件；STOP_AUTO 有意不触发" |
| 4 | **D3** | ②「已有行身份与 ordinal **尽量**不动」不可实现 ⇒ 已改为可判定式 |
| 5 | **F2** | `bounded` / `snapshot` 入库口径未标 ⇒ 本版 §9 全部带口径词 |
| 6 | **W9** | R2c 曾被写成"已验证" ⇒ **已降级为「结构断言 + 未验证」**（`import_row_error` 零命中，无数据可验） |
| 7 | **W10** | `tpq_taq_of_children` 的 25 个实为 connection 派生，暂存标签本身有误 ⇒ 本版 §6.3 已给两种成因对照表 |
| 8 | **W11** | R2b 注释把 `import_row_error` 归入"正常质量问题"措辞别扭（无害）⇒ 建议改为"补集，由 R2c 单独校验" |
| 9 | **WARN-1**（CIT-1b 判定式自伤） | 豁免集必须写进判定式单元格，否则只按表格实现的脚本会把 V0.2.2 自身扫成 FAIL |
| 10 | **WARN-2**（CIT-1a 过宽） | 裸串 `3.6` 会误伤版本号 ⇒ 收紧为正则 `平均\s*3\.6\|3\.6\s*行\|3\.6\s*数学` |
| 11 | **归档位置**（§11.4 追加） | `content_hash` 规范化曾被归档在 `raw_record_index` 主题下 ⇒ 已单列 §2.5.6 / D-03 |
| 12 | **X2** | CHANGELOG L929 定式块标题仍写「CIT-2」，应为 CIT-2′（team-lead 已将其由 WARN 升级为 FAIL 后修复） |

### B.4 本版新增待验项（V-1 … V-10）

| # | 项 | 为什么需要验 |
|---|---|---|
| **V-1** | **`v_place_liveness` 的 SELECT 补全是否正确**（§5.10.2 标记为**补全项**） | V0.2.2-r2 §2.2.4 用 `...` 省略，本文件的对外列清单是据 §2.1.2 / §2.2.3 / §2.2.5 与 V0.2.1 §2.3.4 补全的 ⇒ **待 QA 复算确认**。本轮已补回 `JOIN source_record`（A-1），编译性见 **V-9** |
| **V-2** | **`is_canonical_row` 与暂存 `canonical_name` 是否逐行相等** | 两者是不同机制（视图定序 vs 暂存派生）。315 个（入库口径）无子行地点、MCGD 643 个按组地点、CHGIS 三类的落点需逐行核对，**未验证**。本轮已把定序落成可执行 SQL（A-3 方案①），复算细节见 **V-8** |
| ~~**V-3**~~ | **`occurrence_key_rule` 悬空** → **已裁定：保留该列** | 裁定：V2.1 既有列**不得静默删除**；在 §5.2 列说明中显式标注「服务对象 `occurrence_key` 已被 `duplicate_ordinal` 取代（V0.2.2 全篇零命中），本列在 V2.1.1 中**不再参与键生成**；去留待施工验证后由下轮决定」。**也不得写成仍在使用** |
| **V-4** | 视图派生列总数裁定的落地是否一致 | 本版已按"逐视图逐列名清单 + 作废口径对照表"统一（§5.10.5），**不得再出现任何合计数**；需 QA 扫八份交付物确认无残留 +8 / 6 / 10 |
| **V-5**（D-5） | **`parent_external_id` 按新哨兵规则复算** | 本版补全规则（§4.2）：凡 `record_scope='place'` 或 payload 顶层无 `place_id`/`LocID` 者一律落 `'-'`。实测：**可派生 10,765**（Pleiades 9,802 + MCGD 960 + **`whg_geom_index` 3**）／**落哨兵 18,626**（place 全域 18,398 + `whg_place_name_index` 223 + `whg_geometry` 5）／**相对 C29② 原文缺口 2,878**。⛔ `whg_geom_index` 3 行**可派生，不得计入缺口**。属**补全项不是新设计** ⇒ **待 QA 复算** |
| **V-6**（D-6 → **B-4**） | `data_quality_issue` 中 6 行空 `source_record_id` 的 `dataset_id` 来源 | ⭐ **已核实并给出派生规则，B-4 关闭**（§5.9.1）。两条派生链：① `source_record.dataset_id`；② `source_dataset` 图层键映射。**实测这 6 行** = 2 条 `chgis_pref`（`nonstandard_field_name`）+ 4 条 `pleiades_gis_4_1_slice`（`truncated_slice_tail`），**全部可经②派生**（→ `chgis_v6_prefecture_points` ×2、`pleiades_gis_4_1_slice` ×4），C11 不违反。⛔ 原表述「这 6 行由 C11 要求带 `place_id`」**错误，已更正**：它们无 `place_id`、无 `source_record_id`，一行都不是地点级。**残留未验证项（1 项）**：`whg_api_sample` 对应 3 个 whg dataset，**不能一对一映射**，其台账行须靠 `source_record_id` 追溯；"`whg_api_sample` 且 `source_record_id` 为空"的情形本轮未出现，**未验证** |
| **V-7**（D-3） | `external_id_type` 实测 11 种 vs V2.1 notes 的 16 种 | 已在 §5.4.2 标注更正；需 QA 扫交付物确认无残留"16 种" |
| **V-8**（F-11 落地） | **`is_canonical_row` 外层窗口定序的两个补全键**：⓿「有效证据优先」、⑤「`coalesce(child_row_id,0)` 破并列」 | 两键由本版补全（§5.10.1 / §5.10.4），**待 QA 复算确认**：① 315 个无子行地点的 canonical 是否全部落在 creator 行；② MCGD 643 个按组地点是否落到最小 `NameID`；③ 同记录多行 name 时 canonical 是否确定性唯一（同输入两次查询结果必须相同） |
| **V-9**（F-03 落地） | **`v_place_liveness` 补回 `JOIN source_record` 后能否编译** | 补 JOIN 后 `ORDER BY sr.inactive_at / sr.inactive_in_batch_id` 的两列真实存在（`source_record` 表列，§5.4）⇒ 语法可编译；`GROUP BY e.place_id` 的充分性（功能依赖）**待建视图验证** |
| **V-10**（F-05 落地） | **`count(e.place_id)` 修正后的 `valid_child_rows` / `all_children_rejected`** | 修正后「无有效子行⇒0」的语义恢复；**待复算**：`all_children_rejected=true` 的地点实际行数（暂存态下子表无 rejected 行，预期为 **0**），以及 T5 豁免 ② 是否首次可被真实触发 |

> **B.1 + B.2 + B.3 + B.4 的每一项均为「未验证 / 未解决」。本文件不宣布通过。**

---

> **V2.1.1 到此结束。本版只出模型定义与视图 SQL，不含任何数据库施工。架构师不代替独立复核员与 QA 宣布通过——附录 B 的每一项需在施工阶段逐条关闭。**

