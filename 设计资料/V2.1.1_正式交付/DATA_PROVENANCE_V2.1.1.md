# 数据来源追溯 DATA_PROVENANCE V2.1.1

> 本文是 V2.1.1 八份交付物之一。**权威依据**：V0.2.2-r2（`00_PROBLEM_LIST_AND_PLAN_V0.2.2.md`）；模型字段与视图定义以 `CORE_DATA_MODEL_V2.1.1.md` 为准。V2.1 没有这份文件，来源追溯散落在三处（`CORE_DATA_MODEL_V2.1.md` §5.5.3、§7.1，以及一份已被本版取消的独立文件）。

---

## 0. 本文件回答什么、不回答什么

**回答**：每一行数据来自哪个文件的第几条。

**不回答**：除上面这句以外的任何问题。

### 0.1 B-01 硬要求（V0.2.2 §3）

> **追溯不是"这批数据能不能用"的判据。**
> V0.2.1 第 62 行（"来源追溯必须保留并加强……"）与第 1678 行（§3.6 立项理由）把追溯写成"取消许可后唯一剩下的『能不能用』判据"。**该表述已被 V0.2.2 §3.1 明令撤销，本文件不沿用。**【留痕：已作废表述引用，保留以便追溯，非现行判据】
> 本文件的立项理由只有一句：**追溯服务于 §2 的六项用途；V2.1 把它散落在三处，需要收敛成一卷。**

**本文件不处理授权 / 再分发。**（这是本文件对该事务的唯一交代；全文不再出现相关表述。）【留痕：明确不做声明，保留以便追溯，非现行功能——`data_dataset` 的 9 列许可相关列与 `data_source` 的 2 列（`default_license_id` / `default_redistributable`）均已删除，本系统不做授权 / 再分发判断】

### 0.2 三条边界（写死）

| # | 边界 |
|---|---|
| 1 | 追溯只承担"来自哪个文件、第几条、经过了哪些派生步骤"，**不承担**任何对外可用性判断 |
| 2 | 追溯通路**只读**，不写业务结论；任何"这条数据是否有效/是否冲突"的判断在 `v_place_evidence` / `v_place_liveness` 与台账里 |
| 3 | 追溯**不补造数据**：源端没有的行不得为凑通路而生成（见 §5.1 的 315） |

---

## 1. 一句话原则

> **每一行数据必须能回答"它来自哪个文件的第几条"，不需要回答别的问题。**

推论（实现者容易做反的三条）：

| 推论 | 说明 |
|---|---|
| 追溯是**通路**，不是**判据** | 有通路 ⇒ 可定位；无通路 ⇒ 整批 `failed`（同 A12），不是"降级放行" |
| 追溯信息**只增不改** | `raw_payload` 逐字保留；`source_record_id` / `created_from_source_record_id` / `duplicate_ordinal` 在 STOP_AUTO 期间**一律不动** |
| 追溯**不跨层代偿** | 子表（name / location）的源就是它自己的 `source_record_id`，**不得**用地点的锚点顶替 |

---

## 2. 来源追溯的六项正当用途（V0.2.2 §3.2，逐字）

1. **原始数据定位**：这一行来自哪个文件的第几条。
2. **数据更新**：源端重导时，能否把新版本对应到已有的同一条记录。
3. **数据纠错**：发现错误时，能否定位到源端的具体位置并判断影响面。
4. **记录身份**：这条记录的稳定身份由什么构成（五段自然键 + `content_hash`）。
5. **数据转换过程**：从原始字段到目标字段经过了哪些派生步骤（`grain_key` / `duplicate_ordinal` / `time_bound_type` 等）。
6. **数据质量问题排查**：台账里的问题能否回溯到具体源文件与字段。

> **这六项是本文件存在的全部理由。** 任何超出这六项的用途（尤其是"用它来判断某批数据能不能对外"）都不属于本文件，也不属于本系统。

---

## 3. 追溯基础设施

### 3.1 三层标识，互不混用

| 层 | 标识 | 谁产生 | 语义 | 是否入库 |
|---|---|---|---|---|
| ① 暂存流水号 | `sr_*` / `hp_*` / `nm_*` / `loc_*` / `cm_*` / `ds_*` | 上游规范化脚本 | **仅本批有效**；`FIELD_MAPPING` 标 `(discarded)` | ❌ 不入库 |
| ② 业务唯一键 | 五段 `(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)`（C01） | 导入器派生 | 源端身份 | ✅ |
| ③ 库内主键 | `source_record_id` / `place_id` / `name_id` / `location_id` / … | PostgreSQL IDENTITY | 库内身份 | ✅ |

> ⛔ **① 与 ③ 不得混用**：暂存 `source_records.source_record_id`（`sr_*`）是流水号，入库后由 IDENTITY 重新分配。任何把 `sr_*` 当持久 ID 引用的写法都会在下一次重导后失效。

### 3.2 定位三元组（追溯的终点）

```
source_record.raw_file            -- 项目根相对路径
source_record.raw_record_index    -- 文件内第几条（1-based）
source_record.raw_payload         -- 该行全部原始字段（jsonb，键名保持源原样）
```

⇒ **任一入库行都能定位到上游物理文件与行号**，覆盖率要求 `19,039 / 19,039`（地点口径，入库）。

三条使用纪律：

| # | 纪律 |
|---|---|
| 1 | `raw_record_index` **不保证文件内唯一**（14 个 `raw_file` 中 7 个不唯一，全为 WHG）⇒ **不得**单独作为定序键或唯一性依据，只能在 `content_hash` 完全相等时打破并列 |
| 2 | `raw_payload` 的**键名保持源文件原样**（CHGIS 县级层是 `ENT_DATE`，府级层是 `END_DATE`），**不做键名归一**——归一会让哈希无法回答"字段名变了没有" |
| 3 | `raw_payload` **不含**导入器补齐的任何字段（`record_scope` / `parent_external_id` / `duplicate_ordinal` / 批次号 / 时间戳），否则同一份文件重导哈希必变 |

### 3.3 两个摘要并存（ALG-1，不可互换、不可统一）

| 摘要 | 算法 | 谁算 | 用途 |
|---|---|---|---|
| `content_hash` | **sha256** | 导入器 | 内容身份：`duplicate_ordinal` 定序、跨版本稳定、重复隔离判定 |
| `issue_fingerprint` | **md5** | PostgreSQL 生成列 | 台账去重键，承载 `first_batch_id` / `last_batch_id` / `occurrence_count` |

**`content_hash` 的规范表达式（唯一）**：

```
sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))
```

- 完整串（带算法外壳）：`len == 85`、`sha1 == 9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5`；
- 内层 `json.dumps(payload, …)`：`len == 77`、`sha1 == 781f68645c4e2e3af4b18871f2f5b7848c5f3798`；
- 逐字节形式 `sha256(raw_payload_json 逐字节)` **仅当 `normalize.py:306` 保持 `sort_keys=True, ensure_ascii=False, separators=(",",":")` 时等价**。

**`issue_fingerprint` 的构成（六段，`place_id` 是必需段）**：

```sql
GENERATED ALWAYS AS
  md5(jsonb_build_array(source_record_id, dataset_id, place_id,
                        issue_type, field_name, observed_value)::text) STORED
```

- 编码用 **JSON 数组**（不用字符串拼接）：`null` / `""` / 含 `|` 的值三者互不相同；
- **不做 `coalesce`**：`NULL` 与 `''` 必须可区分；
- **不含 `batch_id`**（含了每导一批新增 197 行，台账自我膨胀）；
- 六段 ⇒ **197** 个不同指纹 / 0 冲突；去掉 `place_id` ⇒ **45** 个 / 24 冲突组 / 176 行。

> ⛔ **ALG-1（写死）**：两种算法并存是**有意设计**。`issue_fingerprint` 的 md5 若改 sha256，**197 条已算历史指纹会全部对不上**；两者语义不同（内容身份 / 台账去重）、计算位置不同（导入器 / PostgreSQL）。**后人若提出统一，先问：197 条已算指纹怎么办？没有答案就不要动。**

### 3.4 五段键：为什么每一段都是追溯的一部分

| 段 | 缺了会怎样（追溯视角） |
|---|---|
| `dataset_id` | 跨数据集 ID 空间混同（CHGIS `SYS_ID` 与 Pleiades `id` 都是数字）⇒ 定位到错的文件 |
| `record_scope` | 同一数据集内 place / name / location / edge 各有自己的 ID 空间（Pleiades 的 `981524` 既是 place id 又是 connection id）⇒ 同名不同物 |
| **`parent_external_id`** | 漏段 ⇒ 三段键口径下 **398 组 / 2,335 行**被误判为重复（真实只有 **7 组 / 14 行**）⇒ 数百条被误隔离，**且不报错**。哨兵值为 `'-'`（C29） |
| `external_id` | 源声明的 ID |
| `duplicate_ordinal` | 7 组 × 2 行无法区分；`ordinal=0` **29,377**（暂存原始口径） |

---

## 4. 逐表通路图（9 张表）

**读法**："源锚" = 本行靠哪一列指向 `source_record`；"通路" = 从本行走到物理文件行号的完整链条。

| # | 表 | 源锚 | 完整通路 | 备注 |
|---:|---|---|---|---|
| 1 | `data_source` | 无 | — | 4 行常量登记，不参与逐行追溯 |
| 2 | `data_dataset` | 无（`dataset_id` 是自然键） | 反向聚合：`source_record WHERE dataset_id = :d` → `raw_file` / `raw_record_index` | 数据集级元信息；无独立物理行 |
| 3 | `import_batch` | 无（批次登记） | `input_file` + `input_sha256` + `input_row_count` | 批次级定位；`derivation_version` 记"用哪版派生规则算的" |
| 4 | **`source_record`** | **自身即源** | `raw_file` + `raw_record_index` + `raw_payload` | **追溯终点**。隔离不删行，只置 `is_active=false` |
| 5 | `historical_place` | `created_from_source_record_id` → `source_record` | `place → created_from_source_record_id → source_record → raw_file + raw_record_index` | **锚点**，IDENTITY 永不改写 |
| 6 | `historical_place_name` | `source_record_id` → `source_record` | `name → source_record_id → source_record → raw_file + raw_record_index` | `UNIQUE(source_record_id, name_type, name_text, name_lang)`（C08） |
| 7 | `historical_place_location` | `source_record_id` → `source_record` | `location → source_record_id → source_record → raw_file + raw_record_index` | `UNIQUE(source_record_id) WHERE NOT NULL`（C07） |
| 8 | `candidate_match` | `source_record_id_a` / `_b` → `source_record` | `candidate → 两侧 source_record → raw_file + raw_record_index` | **交叉校验用，不是解析器** |
| 9 | `data_quality_issue` | `source_record_id`（可空）+ `dataset_id` + `place_id` | `issue → source_record_id → source_record → raw_file + raw_record_index` | ⚠️ **6 行 `source_record_id` 为空 ⇒ 无行级物理通路**；但 `dataset_id` 可由 `source_dataset` 图层键派生（CORE §5.9.1 **B-4 已关闭**）。这 6 行是层元数据/传输残片，**本就不是某一行数据的缺陷** |

### 4.1 派生步骤清单（用途 5：数据转换过程）

从原始字段到目标字段，**每一步都必须可复算**：

| 派生列 | 规则（写死） | 复算结果（暂存原始口径） |
|---|---|---|
| `record_scope` | 按 `dataset_id` + `external_id_type` 查表（11 种 → 4 值），**不猜** | 29,391 行全部落到 4 值之一，0 未知 |
| `parent_external_id` | Pleiades → `raw_payload.place_id`；MCGD → `raw_payload.LocID`；无父级 → 哨兵 `'-'` | 可派生 **10,765** / 落哨兵 **18,626** / 合计 29,391 ✓ |
| `duplicate_ordinal` | 组内按 `(content_hash ASC, raw_record_index ASC)` 定序取 1..n；单行组 = 0 | `ordinal=0` **29,377**；另 7 组 × 2 行 = 14 行 |
| `content_hash` | §3.3 规范表达式 | 29,391 / 29,391 与规范化表达式逐字节相等 |
| `historical_place.dataset_id` | `join(created_from_source_record_id → source_record.dataset_id)` | 与 `grain_key` 组成 `UNIQUE`（C04） |
| `historical_place.grain_key` | `place_grain='per_record'` ⇒ `external_id`；`='per_parent_external_id'` ⇒ `parent_external_id` | MCGD 960 → 643 地点 |
| `created_from_source_record_id` | CHGIS / Pleiades / WHG 取本 place 的 `record_scope='place'` 记录；MCGD 取 `parent_external_id = LocID` 中 `external_id`（`NameID`）**字典序最小**的那条 | 15,746 / 2,643 / 643 / 7 各自闭合 |
| `crs_confidence` | 只能由 `original_crs` 派生：`EPSG:4326`→`confirmed`；`unknown`/`NULL`→`unknown` | 17,457 / 646 |
| `time_bound_type` | 7 值域 | 实测 6 值，均在域内 |

> ⚠️ **`derivation_version`**：上述九列全是派生的，规则变了结果就变 ⇒ `import_batch.derivation_version` NOT NULL（本版 `v2.1.1`）。**没有这一列，就无法回答"这条派生值是用哪版规则算出来的"。**

### 4.2 三处"看起来断链、实际没断"的地方（实现者易误判）

| 现象 | 真相 |
|---|---|
| 暂存 `historical_places.primary_external_id`（MCGD 643 行）与 `source_records.external_id` join 不上 | 前者填 `LocID`，后者是 `NameID`。**`LocID` 正是 `parent_external_id` 的来源**，用途不同。地点归属一律走 `created_from_source_record_id`，**不走** `primary_external_id` |
| 暂存 `historical_places` 有 `valid_from/to_year_astro` 两列 | 地点行**不带时间列**（CORE §5.5.1）。这两列在 V2.1.1 目标模型里是 `(dropped)`，时间由 `v_place_time_span` 从子表聚合 |
| `data_quality_issues` 没有 `raw_file` 列 | 不是缺失，是设计：台账经 `source_record_id` 回溯。⚠️ **6 行空 `source_record_id`** 确实没有行级物理通路（它们不是任何一行数据的缺陷），但其 `dataset_id` **可派生**（见 CORE §5.9.1 两条派生链，**B-4 已关闭**） |

---

## 5. 三个特殊集合（必须单列，给出数字与判据）

### 5.1 315（入库口径）：无子行的 Pleiades 地点

| 项 | 值 |
|---|---|
| 数量 | **315**（入库口径；暂存原始同为 315，差 0） |
| 构成 | **全部 Pleiades**；`canonical_name` **315 / 315 非空** |
| 判据 | 该地点在 `historical_place_name` / `historical_place_location` 中**没有任何子行** |
| **追溯通路** | `place → v_place_evidence(evidence_role='creator', is_canonical_row=true) → source_record → raw_file + raw_record_index`，其值为 **`raw_payload.title`** |
| 关键结论 | **通路已经成立**，不需要、也**不允许**制造名称子行来"补链" |

**为什么不补造名称行**（Owner 决策 1，V0.2.1 §7.3）：

1. 补名称行会让 `historical_place_name` 从 **入库 47,499** 变成 47,814；
2. 会造出与 Pleiades `names.csv` **语义重复**的行——Pleiades 的名称权威是 `names.csv`，`places.title` 是**标签**，不是名称证据；
3. 若改为"挡在 staging 不让进正式层"，315 个真实地点会在地图上消失。

⇒ 三者都不可接受。**结论：允许进入正式层，不补名称行。**

> ⚠️ **口径提示**：这 315 个地点的**名称只存在于 `canonical_name`（派生显示字段）**，不是名称行。因此"点名称看来源"在这些地点会落到 **place 记录**而非 name 行——这是**设计选择，不是缺陷**，UI 需说明（V0.2.1 §7.5-D）。

### 5.2 643（入库口径）：按组创建的 MCGD 地点

| 项 | 值 |
|---|---|
| 数量 | **643** 个地点（**入库口径**），由 **960** 条 `record_scope='name'` 源记录（暂存原始口径）按组建成 |
| 判据 | `data_dataset.place_grain = 'per_parent_external_id'`（MCGD）⇒ 建点走**白名单第 ② 支**（CORE §5.5.5） |
| **追溯通路** | `place.grain_key = parent_external_id（= LocID）` ⇒ 回溯到该组 **N 条名称记录** ⇒ 各自 `source_record_id` ⇒ `raw_file + raw_record_index` |
| 与 `canonical_name` 的一致性 | 组的代表行 = `external_id`（`NameID`）**字典序最小**的那条；`created_from_source_record_id` 与 `canonical_name` **必须取同一条**，否则会出现"地点名来自 A 行、证据来自 B 行"的脱钩 |

### 5.3 1,068（入库口径）：无坐标地点

| 项 | 值 |
|---|---|
| 数量 | **1,068**（**入库口径**；Pleiades **1,058** + CHGIS **10**） |
| 对照 | 可上图的定位数 = 入库（**入库口径**）**18,101** − 10（`geom IS NULL`）= **18,091**，覆盖 **17,971 个地点** |
| 判据 | 该地点在 `historical_place_location` 中没有任何 `geom IS NOT NULL` 的行 |
| 追溯后果 | **无坐标 ≠ 无来源**。这 1,068 个地点的追溯通路与 §4 第 5 行完全相同（走 `created_from_source_record_id`），只是没有 location 子行 |

> ⛔ **V2 §12 写"Pleiades 2,643 个 place 里只有 2,233 个带坐标"已作废**：实测是 **1,585 个带坐标、1,058 个不带**。差额 648 的来源是 V2 混用了两个口径（"有 location 行" vs "location 行有坐标"）。**任何写进对外材料的覆盖率数字，都必须指明分子分母的确切口径。**

---
## 6. `canonical_name` 的证据链

`canonical_name` 是**派生显示字段**，不是源字段。它的证据是"该地点**当前最佳**的那条记录"，由视图派生列 `is_canonical_row` 指出。

### 6.1 `is_canonical_row` 的定序（写死，**6 个键；已落地为可执行 SQL**）

```
is_canonical_row ⇔ 该行是本地点证据集中定序第一的行
实现位置：CORE §5.10.1 / 本文 §7.1 视图的外层窗口函数
          row_number() OVER (PARTITION BY place_id ORDER BY …) = 1

排序键（写死，顺序不可换）：
  ⓿ (source_is_active AND child_record_status IS DISTINCT FROM 'rejected') DESC
                                                 -- 有效证据优先
  ① (evidence_role = 'creator') DESC             -- 创建记录优先
  ② sr.duplicate_ordinal ASC NULLS LAST          -- 与五段键 §4.3 同源（回连 source_record 取值）
  ③ sr.external_id       ASC NULLS LAST          -- MCGD 即"NameID 最小"（回连 source_record 取值）
  ④ source_record_id     ASC                     -- 破并列（可复现）
  ⑤ coalesce(child_row_id, 0) ASC                -- 同记录多行 name 的行级破并列（可复现）
```

> ⛔ **②③ 必须回连 `source_record`**：`duplicate_ordinal` / `external_id` **不是** `v_place_evidence` 的列（本文 §7.1 只有 11 列）。任何"在视图内直接 `ORDER BY` 这两列"的写法都**不可执行**。
> ⛔ **④ 不能单独破并列**：C08 允许一条 `source_record` 派生最多 3 行 name（`name_type` 不同），此时 ②③④ 键**全同** ⇒ 必须靠 ⑤ `coalesce(child_row_id,0)` 破并列，否则 `row_number()` 在并列上的取值**不可复现**（同输入两次查询结果会不同）。
> ⛔ **⓿ 不可省略**：定义句写的是"**有效证据**中定序第一的行"。缺 ⓿ 时，一条 `rejected` 子行或失效源行可能排到有效证据之前成为 canonical ⇒ 与定义句自相矛盾。
> **⛔ canonical ≠ 有效**：零有效证据的地点，`row_number()=1` 仍会选出一行（"最佳可得"），该行 `is_canonical_row=true`，但**不构成"有效证据"**——**是否 canonical 与是否有效是两件事**。此时该地点的 `liveness` 必属 `FAILURE_SET` 或 `orphaned`（CORE §5.10.2），二者不冲突。⛔ **不得**表述为"全为 FALSE、不得回退任取一行"——那是与 SQL 事实相反的写法。

**"有效证据"的唯一定义**（视图 / 存活 / 时间三处共用）：

```
有效证据(e) ⇔ e.source_is_active IS TRUE                      -- 源记录必须明确为活性；NULL（无源的人工子行）不算有效
             AND e.child_record_status IS DISTINCT FROM 'rejected'  -- 子行未被拒
且：child_rejected_by = 'manual' 的行永远不是有效证据，且不参与任何自动恢复
```

### 6.2 三个数据集的落点

| 数据集 | 落点 | 与源的同源性 |
|---|---|---|
| **315 个无子行地点（Pleiades）** | 唯一有效证据是 `creator` 行 ⇒ `is_canonical_row=true` 落在它身上，值为 **`raw_payload.title`** | ✓ 与 `places.csv.title` 同源 |
| **MCGD 643** | 全部证据 `evidence_role='name'`，定序落到 `external_id` ⇒ **最小 `NameID`** | ✓ 与 `canonical_name` 派生规则同源 |
| **CHGIS** | `creator` 优先 | ✓ 与 `places.csv` 的 `title` 同源 |

### 6.3 锚点 vs 当前最佳证据：指向不同记录**不是错误**

| 概念 | 列 | 语义 | 是否随导入变 |
|---|---|---|---|
| **锚点** | `created_from_source_record_id` | 首次导入时的身份记录（IDENTITY，永不改写） | 否 |
| **当前最佳证据** | `v_place_evidence.is_canonical_row` | 每次导入重算 | 是 |

> **这是设计选择，必须写明**：两者可以指向不同记录，**不视为错误、不落台账**。`created_from_source_record_id` 是单值，因此不能承担"全部证据"的职责——这正是加 `grain_key` 而不是把它改成数组的理由（数组无法加唯一约束、无法建 FK）。

### 6.4 人工修改后，追溯仍然成立

`canonical_name` 被人工修改 ⇒ 该字段进入 `manual_edited_fields` ⇒ 导入器 **KEEP_MANUAL**（不覆盖）。

此时：

- **显示值** = 人工值；
- **`is_canonical_row` 仍指向源行**，用于回答"这个地点本该叫什么、来自哪里"。

⇒ UI / 文档必须能**同时**展示三件事：显示名（可能人工）+ 源名（`is_canonical_row` 行的 `raw_payload`）+ 来源位置（`raw_file:raw_record_index`）。

---

## 7. 视图 DDL 与覆盖断言

> 以下 DDL 与 `CORE_DATA_MODEL_V2.1.1.md` §5.10 **逐字一致**；两份文件任一处改动必须同步另一处。

### 7.1 `v_place_evidence`（**11 列**）

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

> **⭐ 修正说明（A-3 / QA F-11，本版留痕；本段与 `CORE_DATA_MODEL_V2.1.1.md` §5.10.1 逐字一致）**
>
> **原缺陷（本文旧稿，逐处列出但不复制原文）**：① creator 分支把 `is_canonical_row` 写死成布尔常量 `false`；② name 分支写了一个**尖括号占位符**（指向 CORE §5.10.4 的定序，不是可执行 SQL）；③ location 分支同样写死两个布尔常量。三处都与 §6.1「315 个（入库口径）无子行地点的 `is_canonical_row=true` 落在 creator 行」**直接矛盾**；且定序键 `duplicate_ordinal` / `external_id` 也不在 `v_place_evidence` 的 11 列里（它们是 `source_record` 的列）。⇒ 旧稿视图**不可编译、不可执行**。
>
> **本版解法（外层窗口定序）**：三支 `UNION ALL` 整体下沉为子查询 `u`，外层用 `row_number() OVER (PARTITION BY place_id ORDER BY …) = 1` 计算 `is_canonical_row`；涉及 `duplicate_ordinal` / `external_id` 的定序键一律**回连 `source_record`** 取值。**写死常量与占位符全部消除**（creator 分支 1 处、location 分支 1 处、name 分支占位符 1 处），全视图为**可执行 SQL**。
>
> **6 个定序键（⓿①②③④⑤）见 §6.1 与 CORE §5.10.4**：⓿「有效证据优先」与 ⑤「`coalesce(child_row_id,0)` 破并列」是**必要补全**（不是新设计）：缺 ⓿ 时失效源或 `rejected` 子行可能排到有效证据之前成为 canonical，与"有效证据中定序第一"的定义句自相矛盾；缺 ⑤ 时同一 `source_record` 派生多行 name（C08 允许最多 3 行 `name_type`）会因 ②③④ 全同而**并列不可复现**。
>
> **⛔ canonical ≠ 有效**：零有效证据的地点，`row_number()=1` 仍会选出一行（"最佳可得"），该行 `is_canonical_row=true`，但**不构成"有效证据"**——是否 canonical 与是否有效是两件事。此时该地点的 `liveness` 必属 `FAILURE_SET` 或 `orphaned`（CORE §5.10.2），二者不冲突。

**11 列逐列**：`place_id` / `source_record_id` / `evidence_role`（3 值 `creator` / `name` / `location`）／`source_is_active` / `source_inactive_reason` / `child_table` / `child_row_id` / `child_record_status` / `child_rejected_by` / `is_anchor` / `is_canonical_row`（**第 11 列由外层 `row_number()` 实际计算，不是写死常量、也不是占位符**）。

> ⛔ **`evidence_role` 只有 3 值**（`creator` / `name` / `location`）；V0.2 旧稿里那个以 `place_` 开头的第四个角色名**已废弃，属禁用词，任何交付物不得出现**。
> ⛔ V0.2.2 §6 第 3 项写的「10 列」**已作废**（漏数 `is_canonical_row`）。

**join 条件的构成与"旧用法作废"声明**：

| 组成 | 状态 |
|---|---|
| `ON sr.dataset_id = p.dataset_id` | ✅ 现行（依赖 V2.1.1 新增的 `historical_place.dataset_id`） |
| `p.grain_key = sr.external_id` / `p.grain_key = sr.parent_external_id` | ✅ 现行（`grain_key` 列本版新增） |
| 白名单 `sr.record_scope='place'` OR (`sr.record_scope IN ('name','location')` AND `dataset.place_grain='per_parent_external_id'`) | ✅ 现行 |
| ⛔ `AND sr.record_scope <> 'place'` | **已作废**——它把 `edge` 与未来任何新类型默认放行，被白名单取代 |

### 7.2 `v_place_liveness`（8 值 `liveness`；本视图**对外 7 列**）

> **⚠️ 两个数不是一回事**：「8 值」指 **`liveness` 列取 8 个枚举值**（`merged`/`manual`/`active`/`mixed_inactive`/`all_sources_absent`/`all_sources_rolled_back`/`quarantined_only`/`orphaned`）；「7 列」指**本视图对外输出的列数**（`place_id`/`dataset_id`/`grain_key`/`record_status`/`manual_rejected_rows`/`distinct_inactive_reasons`/`liveness`）。**枚举值个数 ≠ 列数，两者不矛盾。**

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

> **⭐ 修正说明（A-1 / QA F-03，本版留痕；本段与 `CORE_DATA_MODEL_V2.1.1.md` §5.10.2 逐字一致）**：本文旧稿的 `ev` CTE 只 `FROM v_place_evidence e`，却在 `ORDER BY` 里引用 `inactive_at` / `inactive_in_batch_id`——**该视图固定 11 列，不含这两列**（见 §7.1 列清单），SQL **无法编译**。
> 本版使用 `LEFT JOIN source_record sr ON sr.source_record_id = e.source_record_id`：既从源记录取 `sr.inactive_at` / `sr.inactive_in_batch_id`，又保留 `source_record_id IS NULL` 的人工子行。**不采用"给 `v_place_evidence` 加两列变 13 列"的解法**（会破坏 11 列定式）。
> **GROUP BY 仍充分**：`sr.inactive_at` / `sr.inactive_in_batch_id` 只出现在聚合函数内部（`array_agg(... ORDER BY ...)`），`source_record_id` 是 `source_record` 主键 ⇒ 功能上依赖 `e.place_id`。

**对外列清单（**7 列**）**：`place_id` / `dataset_id` / `grain_key` / `record_status`（均来自 `historical_place`）/ `manual_rejected_rows` / `distinct_inactive_reasons` / `liveness`。`has_valid` / `reasons` 是 `ev` CTE 的**中间量，不计入对外列**（与 SQL 一致：二者不出现在外层 `SELECT`）。

> ⚠️ **补全项声明（非新设计）**：V0.2.2-r2 §2.2.4 的 `SELECT` 用省略号未补全对外列清单；上表是依据 V0.2.2 §2.1.2 / §2.2.3 / §2.2.5 与 V0.2.1 §2.3.4 已枚举列**补全**的，属补全项不是新设计（CORE 附录 B **B-4-1**，待 QA 复算确认）。

**`liveness` 8 值**（派生优先级自上而下，命中即返回，顺序不可换）：
`merged` → `manual` → `active` → `all_sources_absent` → `all_sources_rolled_back` → `quarantined_only` → `mixed_inactive` → `orphaned`。

记 **`FAILURE_SET = {all_sources_absent, all_sources_rolled_back, quarantined_only, mixed_inactive}`**；`rejected` ⟺ `liveness ∈ FAILURE_SET`。

### 7.3 五条覆盖断言（**施工后必跑，本文不预设结果**）

```
V1  SELECT count(*) FROM historical_place p
      WHERE NOT EXISTS (SELECT 1 FROM v_place_evidence WHERE place_id = p.place_id);   -- 期望 0
V2  count(place WHERE 只有 role='creator' 且无 name/location)                            -- 期望 315（入库口径，Pleiades）
V3  count(creator 行 WHERE place.grain_key 命中且 record_scope='place')                  -- 期望 18,396（入库口径；= 19,039 − 643）
V3' count(creator 证据行 WHERE is_anchor)                                                -- 期望 19,039（入库口径）
V4  count(证据行 WHERE evidence_role='creator' AND source.record_scope='edge')           -- 期望 0
V5  count(证据行 WHERE evidence_role='creator' AND source.record_scope='name'
              AND dataset.place_grain <> 'per_parent_external_id')                       -- 期望 0
```

> **V5 的等价关系必须注明**：`place_grain` 是 `NOT NULL + CHECK(2 值)` ⇒ `<> 'per_parent_external_id'` **等价于** `= 'per_record'`，语义不变、仍应恒为 0，且不再可能命中 NULL（旧写法下 NULL 会因 `NULL <> …` 为 NULL 而被 `count` 漏掉——那才是隐患）。

---

## 8. 出处引用：本版为什么"没有"

> **本条是对"引用"义务的唯一交代，其作用是显式声明『没有』**，避免后续编制时想当然地补一个引用列。

1. V2.1 的**署名文本列**（`attribution_text` / `citation_text`）**已删除**【留痕：已删除列说明，保留以便追溯，非现行模型】，且**不新增任何引文文本列、也不新增任何替代字段**。
2. **不新增的必要性未通过**：数据集级出处可以由 `data_dataset` 元信息 + `v_place_evidence` 的 `raw_file` / `raw_record_index` **现场拼出**，不需要落库。
3. 因此本系统**不存在**"导出时必须带出某段引用文本"这一要求；导出物需要标注出处时，**现场拼**，拼不出来就说明溯源断了（那是缺陷，应修通路而不是补一列）。
4. ⛔ **下轮不得因为"导出时想带出处"而新增任何文本列**（`attribution_text` / `citation_text` 及任何替代字段）——那是把 §0.1 的边界重新打开。【留痕：禁用词清单，保留以便追溯，非现行字段】

---

## 9. 两条施工级硬提醒

### 9.1 H1：`normalize.py:306` 一旦改动，必须回归 `content_hash`

`content_hash` 的逐字节等价形式依赖上游 `normalize.py:306` 的一个约定（`sort_keys=True, ensure_ascii=False, separators=(",",":")`）。该行一旦被改：

```
29,391 条（暂存原始口径）content_hash 全部改变
  ⇒ duplicate_ordinal 大规模重排
  ⇒ STOP_AUTO 误触发、整批 SKIP_UPDATE
  ⇒ 静默，不报错
```

⇒ **该行是本系统 `content_hash` 等价性的唯一支点，改动而不同步回归即为事故。**

### 9.2 H2：`derivation_kind` / `no_evidence` 不得直读暂存时间列

⛔ **禁止**直接读暂存 `historical_places.valid_from_year_astro` / `valid_to_year_astro` 来判定 `derivation_kind` 或 `no_evidence`。

- 旧口径（含 connection）算出的 **1,505** 是**偏低 65** 的错值；
- 新口径（只聚合 name + location 子行）：`no_evidence` **1,570** = **315** 无子行 + **1,255** 有子行但子行无年份（`none` 1,230 + `tpq_taq_of_children` 25）；`single_point` **361**；`envelope…` **17,108**；合计 19,039；
- 1,570 / 315 / 1,255 三个数均为**暂存态干跑**口径，**入库后需重跑**。

---

## 10. 本文引用的权威数字（全部带口径词）

**口径纪律**：`暂存原始` = 七张暂存 CSV 的实测行数；`入库` = 执行 V2.1.1 隔离规则后进入目标表的行数。**二者不得混用**，凡出现必须带口径词。

| # | 项 | 暂存原始 | 入库 | 说明 |
|---|---|---:|---:|---|
| N01 | `source_record` | 29,391 | 29,391 | 隔离不删行，只置 `is_active=false` |
| N02 | 其中 `is_active=false` | 0 | **3** | `sr_0004941` / `sr_0004942` / **`sr_0027175`** |
| N03 | 活性源记录 | 29,391 | **29,388** | |
| N04 | `duplicate_ordinal=0` | **29,377** | 29,377 | 另 7 组 × 2 行 = 14 行 |
| N05 | `historical_place` | 19,039 | **19,039** | CHGIS 15,746 + Pleiades 2,643 + MCGD 643 + WHG 7 |
| N06 | `historical_place_name` | **47,503** | **47,499** | −4（被隔离的 2 条 CHGIS 各派生 2 条名称） |
| N07 | `historical_place_location` | **18,103** | **18,101** | −2 |
| N09 | `record_scope='place'` 记录 | **18,398** | **18,396** | 18,398 − 2 = 19,039 − 643 ✓ |
| N10 | `record_scope` 全域 | place 18,398 / name 5,762 / location 2,468 / edge 2,763 | 同 | **仅 4 种，无第五种** |
| N11 | 无子行地点 | **315** | 315 | 全部 Pleiades，`canonical_name` 315/315 非空 |
| N12 | 无子行的源记录 | **8,682**（**口径 A**） | 8,682 | 口径 B = 8,218，差 464 = place 74 + edge 390；**本文钉死口径 A** |
| N15 | 时间三值（只聚合 name + location） | `no_evidence` **1,570** / `single_point` 361 / `envelope…` 17,108 | 同 | ⚠️ 暂存列算出的 1,505 是旧口径，**偏低 65** |
| N16 | `no_evidence` 构成（**暂存态干跑**） | 1,570 = 315 + 1,255（1,230 + 25） | 见 CORE §5.10.3 | 入库后需重跑 |
| N17 | 重复组口径对照 | 漏 `parent_external_id`：398 组 / 2,335 行；五段键：**7 组 / 14 行** | 同 | 差两个数量级 |
| — | 无坐标地点 | — | **1,068**（入库口径） | Pleiades 1,058 + CHGIS 10 |
| — | 可上图定位数 | — | **18,091**（入库口径，覆盖 17,971 地点） | = 18,101 − 10 |

> ⛔ **`candidate_match` 的行数不得进入权威数字表。** 暂存原始 **53,137** / 隔离后 **53,103** 是**登记项 U18，待 Owner 拍板**（V0.2.2 §5.3 行 1039）。与 2 条隔离记录相关的候选行 34 行 / 33 个键，按 Owner 决策 4 应扣 34 ⇒ 53,103。**以 data-auditor 审计报告为准，架构侧只登记、不自行改数。**

---

## 11. 施工验证清单（**逐项如实保留；任何一项都不得标记为校验通过或已关闭**）

> 本节全部条目处于**未验证**状态。建库后由施工方逐条跑；跑完也只是"本条已跑过"，不等于本文通过。

| # | 待验项 | 期望 / 判据 | 状态 |
|---|---|---|---|
| **U3 / U4** | 视图首导 | `v_place_evidence` / `v_place_liveness` 首导能否建、能否查通 | **未验证** |
| **U5** | 七类操作的实际拦截效果 | 逐类实测，不止看代码 | **未验证** |
| **U12** | 加 `sr.is_active` 后 **17,469**（V0.2.1 旧口径，待重算）是否变化 | 过滤改为"有效证据"后需重算 | **未验证** |
| **U13** | `rejected_by` 是否误伤 | 人工拒绝是否被自动恢复 | **未验证** |
| **U14** | 四场景 A–D 端到端 | 场景 C（源复活）不得恢复 `rejected_by='manual'` | **未验证** |
| **U15** | STOP_AUTO 触发率 | 判据 `\|old\|=\|new\| AND \|old∩new\| < \|old\|−1` | **未验证** |
| **U16** | `raw_record_index` 语义 | 7 个 `raw_file` 内不唯一，是否已正确降级为"仅破并列" | **未验证** |
| **U18** | `candidate_match` 行数口径 | 53,137 / 53,103 待 Owner 拍板 | **未裁定** |
| **V-1** | `v_place_liveness` 的 `SELECT` 补全列清单 | 与 V0.2.2 §2.2.4 对碰（CORE 附录 B B-4-1） | **未验证** |
| **V-2** | `is_canonical_row` 与暂存 `canonical_name` 是否**逐行相等** | 逐行比对，不抽样 | **未验证** |
| **V-5** | `parent_external_id` 覆盖率复算 | 可派生 **10,765** / 落哨兵 **18,626**（暂存原始口径） | **未复算** |
| **V-6** | `data_quality_issue.dataset_id` 的 6 行派生 | 两条派生链（① `source_record.dataset_id` / ② `source_dataset` 图层键映射）已在 CORE §5.9.1 写死，6 行全部可经②派生 ⇒ **B-4 关闭**。残留：`whg_api_sample` 一对多（3 个 whg dataset）**未验证** | **B-4 关闭**（残留 1 项未验证） |
| **V-11** | 315（入库口径）条追溯通路逐条跑通 | `place → v_place_evidence(creator, is_canonical_row) → source_record → raw_file + raw_record_index` | **未验证** |
| **V-12** | 643（入库口径）条 MCGD 按组通路 | `grain_key = parent_external_id` 是否逐组闭合 | **未验证** |
| **V-13** | 1,068（入库口径）条无坐标地点的来源通路 | 无坐标 ≠ 无来源，通路应 1,068 / 1,068 | **未验证** |
| **V-14** | 19,039 / 19,039（**入库口径**）定位覆盖率 | 任一地点 → `raw_file` + `raw_record_index` 可定位 | **未验证** |
| **V-15** | 197 条历史指纹在新算法下是否仍能对上 | `count(DISTINCT issue_fingerprint) = 197`；去 `place_id` 段后必须 **< 197**（实测 45） | **未验证** |
| **V-16** | 两种摘要是否真的没被互换 | `content_hash` 必须 sha256、`issue_fingerprint` 必须 md5（ALG-1） | **未验证** |
| **V-17** | V1–V3' / V4 / V5 五条覆盖断言 | 见 §7.3 | **未验证** |

> 其余未验证项（12 项 WARN、V0.2.2 §5.3 的 10 项、V-3 / V-4 / V-7 … V-10）逐条保留在 `CORE_DATA_MODEL_V2.1.1.md` 附录 B 与 `IMPORT_RULES_V2.1.1.md` §12，**本文不重复、也不代其结案**。

---

## 12. 本文的不做之事与边界

1. **不处理 §0.1 声明的那类事务**（全文仅 §0.1 一处交代）。
2. **不判断任何一行数据"能不能用"**（B-01）。
3. **不补造数据**：315 个无子行地点不补名称行；无坐标地点不补坐标。
4. **不新增任何引用文本列**（`attribution_text` / `citation_text` 均不新增；§8）。【留痕：禁用词清单，保留以便追溯，非现行字段】
5. **不改动上游**：七张暂存 CSV、`normalize.py`、V2 / V2.1 / V0.2.2-r2 全部文件均**未改动**。
6. **不写 DDL / Migration / 建库 / 导入 / Git**：§7 的两段 `CREATE VIEW` 是**定式转录**，落地由施工方在迁移脚本里执行。
7. **不自行改数**：`candidate_match` 行数（U18）**待 Owner 拍板**，只登记不改数。D-6 的 6 行（V-6）已核实并给出派生规则（CORE §5.9.1），**B-4 关闭**，无需拍板。

---

## 13. 引用纪律（CIT-1）

八份交付物凡引用 V0.2.1 的 §2.1.4a / G1-02，必须同时标注 V0.2.2 §2.9 的更正，并且**不得单独转述** V0.2.1 的原文理由。

- 本文**未引用** V0.2.1 §2.1.4a / G1-02 的任何结论；
- 本文涉及行序重排的地方（§3.3 的 `duplicate_ordinal` 定序、§5.2 的 `NameID` 最小）**均按 `content_hash` 定序表述**，与 V0.2.1 的旧表述无继承关系；
- 本文**未出现** V0.2.1 中被撤销的"平均 3.6 行"相关表述。

