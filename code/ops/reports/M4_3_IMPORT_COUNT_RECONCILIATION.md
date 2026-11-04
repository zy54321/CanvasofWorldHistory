# M4-3 R1.1 · 导入数量重新核算报告（A2 口径）

日期：2026-11-04
依据：`code/ops/m4-3/import_counts.py` → `import_counts.json`；`code/ops/m4-3/connections_audit.py` → `connections_audit.json`
边界：只读。未写库、未执行 Migration、未改 staging、未改原始数据。

**三项决策（OWNER CONFIRMED，不再讨论）**

| # | 决策 | 对数字的影响 |
|---|---|---|
| 1 | 代表点采用 **A2**：3,317 条代表点合成独立 Point 位置行 | 位置 32,374 → **35,691**；source_record 124,512 → **127,829**；总量 **157,220** |
| 2 | `attested_form` **不补**名称行（10,297 条） | 名称行与 source_record **不增加** |
| 3 | `place_without_geometry` **不写台账**（7,200 只作验收查询） | 台账不增 7,200 行；V9 只加 3 种类型（共 23） |

---

## 一、集合

| 项 | 数值 |
|---|---:|
| v4.1 地点总数 | 41,480 |
| 现库切片地点（place 作用域，active） | 2,643 |
| 交集 | **2,552** |
| 仅切片有 | 91 |
| **NEW（导入对象）** | **38,928** |

校验：38,928 + 2,552 = 41,480；2,643 − 2,552 = 91。

---

## 二、source_record 增量（A2 为采纳口径）

| 组成 | 数量 |
|---|---:|
| 新地点（place） | 38,928 |
| 新名称（name） | 37,055 |
| 位置 — 来自三个 location 文件 | 32,374 |
| 位置 — 代表点合成（A2） | **3,317** |
| 位置合计 | **35,691** |
| 连接（connection，全量保留源记录） | 13,603 |
| 重叠地点 inactive 记录 | 2,552 |
| **增量合计（A2）** | **127,829** |
| **预计总量（A2）** | **157,220** |

对照（A1，仅供比较，不采纳）：位置 32,374 → 增量 124,512 → 总量 153,903。

```
38,928 + 37,055 + 35,691 + 13,603 + 2,552 = 127,829
29,391 + 127,829 = 157,220
```

**连接为什么按 13,603 全留源记录**：导入器对 `connections.csv` 每一行都产出 `ExtraRecord`，
源记录写入不以"两端可解析"为前提。现库台账里 `parent_place_not_in_sample` 有 4,810 行
（其中 1,549 是连接）即为证据——不可关联的连接**仍然**有源记录。

---

## 三、connections 逐条核实（本轮重点）

R1 里"孤儿 29 / 自环 2"与"悬空 28 / 自环 1"并存，属口径矛盾：一处数**端点侧数**，一处数**记录数**，
且自环与悬空的判定顺序不同。本轮回到原始文件逐条归类，得到**互斥**分类（`connections_audit.json` 有全部 ID）：

| 类别 | 记录数 | 说明 |
|---|---:|---|
| **A. 两端均可解析** | **13,575** | `place_id` 与 `connects_to` 都在 `places.csv` |
| A1. 真实自环（a == b） | 1 | `lydia-byzantine-province`：`1001909 → 1001909`（succeeds） |
| A2. 正常对 | 13,574 | 进入候选去重 |
| **B. 至少一端悬空** | **28** | 见下三子类 |
| B1. 整行字段全空 | 1 | `connections.csv` 第 4498 行 `,,,,,,,,,,,,`，id/两端/类型全空 |
| B2. 单端悬空 | 27 | 其中 **3 条**指向 `/errata/<id>`（本就不是地点） |
| B3. 两端都悬空 | 0 | — |
| **合计** | **13,603** | 13,575 + 28 |

端点侧数：**29**（`connects_to` 侧 28 + `place_id` 侧 1）。所以：

- 「29」= 悬空**端点侧数**
- 「28」= 悬空**记录数**
- 「2」= 字面上 `a == b` 的记录数（1 条真实自环 + 1 条空行）
- 「1」= **真实自环**数（可解析、两端都在 `places.csv`）

四者互不矛盾，只是口径不同。空行不是自环，只是空字符串等于空字符串。

### 3.1 悬空的 28 条构成（可逐条查 ID）

| 子类 | 数量 | 示例 |
|---|---:|---|
| 指向不存在的 place id | 24 | `altar-of-the-eudamenoi`：`999238742 → 368305523`（near）<br>`lucania`：`991362 → 487529761`（succeeds）<br>`chalcidean-league`：`491701 → 585841736`（member）×7 条 |
| 指向 `/errata/<id>` | 3 | `1001914 → /errata/991384`（succeeds）<br>`874316 → /errata/874325`（connection）<br>`462503 → /errata/991353`（connection） |
| 整行为空 | 1 | 第 4498 行 |

### 3.2 候选关系（`candidate_match`）

| 步骤 | 记录数 | 依据 |
|---|---:|---|
| 可解析非自环 | 13,574 | A2 |
| 减去同有序对重复 | −21 | `uq_candidate_match_c09 UNIQUE (relation_type, place_id_a, place_id_b)` |
| **最终候选行** | **13,553** | — |

- 去重键是 `(relation_type, place_id_a, place_id_b)`，**与 `connection_type` 无关**。
- 21 条重复 = **9 条**同三元组（a,b,type 完全相同）+ **12 条**同有序对但类型不同。
- 真实的 1 条自环进不了候选：`ck_candidate_match_distinct_places` 禁止 `a = b`。
- 空行同样进不了：两端都为空，先被"悬空"排除。
- 写入后按现有规则把 `pleiades_connection` 改写为 `status='confirmed'`、`reviewer='system:source_attested'`
  （满足 `ck_candidate_match_confirmed_edge_reviewer`）。

**结论：`candidate_match` 增量 = 13,553**（53,131 + 13,553 = **66,684**）。
这个数字不是"维持原值"，而是按 `uq_candidate_match_c09` 逐条去重算出来的；`connections_audit.json`
里 `ids.dropped_by_pair_dedup` 给出了被合并的 21 条记录 ID。

---

## 四、精度（两级，只算 NEW）

### 4.1 地点级（`places.csv.location_precision`）

| 范围 | precise | rough | 合计 |
|---|---:|---:|---:|
| 整包 | 29,396 | 12,084 | 41,480 |
| **NEW** | **27,418** | **11,510** | 38,928 |
| 切片 2,552（不导入） | 1,978 | 574 | 2,552 |

`historical_place` 没有精度列，地点级精度只体现在子行与 `places_accuracy`，不单独入库。

### 4.2 位置级（`historical_place_location.location_precision`，A2）

| 几何 | 新增 | precise | rough | `accuracy_radius` 有值 / 空 |
|---|---:|---:|---:|---:|
| Point（来自 `location_points`） | 23,367 | 23,367 | 0 | 23,366 / 1 |
| Point（代表点合成） | 3,317 | 2,589 | 728 | 2,589 / 728 |
| Polygon | 4,114 | 374 | 3,740 | 441 / 3,673 |
| LineString | 4,893 | 4,893 | 0 | 4,893 / 0 |
| **合计** | **35,691** | **31,223** | **4,468** | 31,289 / 4,402 |

**必须**源值直传（`precise→precise`、`rough→rough`），不得像现库那样把非 precise 一律写 `unknown`
（现库 16,399 条位置因此全成 `unknown`）。`ck_hpl_location_precision` 已允许四个值。

### 4.3 `-1` 哨兵

| 范围 | 行数 |
|---|---:|
| `places_accuracy` 整表含 `-1` | 12,007 |
| 其中 NEW 集合 | 11,438 |
| **其中真正入账（代表点合成行的 rough 部分）** | **728** |

`accuracy_radius` 与 `-1` 哨兵是两回事：位置表的 `accuracy_radius` 只有"有值/空"（空 3,674 条），
没有 0 也没有负值；`-1` 只出现在 `places_accuracy.max/min_accuracy_meters`。

---

## 五、代表点与"无几何"三口径

| 口径 | 整包 | NEW | A2 导入后 |
|---|---:|---:|---:|
| 有代表点 | 33,971 | 31,728 | 31,728 |
| 有任意 location 行 | 30,506 | 28,411 | 31,728（合成后） |
| 有代表点、无 location 行 | 3,465 | **3,317** | 0（已合成） |
| 无 location 行 | 10,974 | **10,517** | **7,200** |
| 无代表点 | 7,509 | **7,200** | 7,200 |
| 既无 location 行又无代表点/bbox（验收口径） | 7,509 | **7,200** | **7,200** |

验收采用**既无 location 行又无代表点/bbox = 7,200**：它在 A1/A2 下都稳定，不随是否合成而漂移。
7,509 是整包数字，10,517 是 NEW"无 location 行"的数字，两者都不得直接当验收值。

---

## 六、台账：可预测项与不可预测项

### 6.1 可预测（7,960 行）

| 类型 | 数量 | 依据 |
|---|---:|---|
| `missing_coordinate` | **7,200** | 每个无坐标地点 1 行（place 级 flag） |
| `geometry_invalid_repaired` | 4 | NEW 里的无效多边形 |
| `connection_endpoint_missing` | **28** | 悬空连接记录（24 missing + 3 errata + 1 空行） |
| `accuracy_unknown_sentinel` | 728 | 代表点合成行中的 `-1` |
| `coordinate_out_of_range` | 0 | 全包 0 越界 |
| `parent_place_not_in_sample` | 0 | 完整包无孤儿（切片时代是 4,810） |
| `truncated_slice_tail` | 0 | 无字节切片 |
| `unknown_time_bound_type` | **0** | 见 §6.2 |
| **合计** | **7,960** | — |

### 6.2 `unknown_time_bound_type` 对 Pleiades 恒为 0（有代码依据，不是猜测）

- `normalize.py:615`：`rule_basis_available = date_rules.loaded` —— 依赖 **CHGIS 的 date-rule 工作簿**。
- `normalize.py:621`：`for record in chgis_records:` —— 这个开票逻辑在 **CHGIS 循环内部**。
- `normalize.py:1509-1523`：只有 `rule_basis_available` 为真、且 `BEG_RULE/END_RULE` 不在工作簿里、
  且 `time_bound_type == "unknown"` 时才 `add_issue("unknown_time_bound_type", ...)`。

Pleiades 记录不在 `chgis_records` 里，也没有 `BEG_RULE/END_RULE`，**因此永远不会产生这个类型**。
3,317 条合成位置行的 `time_bound_type='unknown'` 不会触发任何台账。

> R1 曾写"`unknown_time_bound_type` ≥7,546（名称 2,986 + 位置 1,977 + 地点 2,583）"——那是把
> "时间未知"当成"必然开票"的算术推断，**错误**，现予撤销。

### 6.3 子行 flag 为什么不单独开票

`normalize.py:1683-1695` 只遍历 `group.primary.quality_flags`（地点行）。子行（名称/位置）的
`empty_name` / `missing_coordinate` / `z_ordinate_discarded` **不单独开票**；
唯一例外是 `parent_place_not_in_sample`（`normalize.py:1704-1720`）。

### 6.4 不可预测（必须 M4-4a 实测）

| 类型 | 为什么 |
|---|---|
| `duplicate_external_id` | 导入器按多行组运行期合成 |
| `derived_value_mismatch` | 地点级时间包络 vs 暂存值，逐地点比较后才知 |
| `manual_edit_conflict` | 取决于导入时哪些地点带保护位 |
| 台账类型总数 | 若上述为 0，类型数会少 |

---

## 七、其它可入库字段覆盖

| 项 | 数值 |
|---|---:|
| NEW 名称行 | 37,055（`association_certainty` 100% 有值；`romanized_form_1` 100%；`attested_form` 10,297） |
| NEW 位置行 | 35,691（`archaeological_remains`、`association_certainty` 均 100%） |
| NEW 类型关系行 | 48,030（覆盖 38,926 个地点；**无逐行记录**，见承载矩阵 §四） |
| 类型词表 | 192 键，被引用 206，**29 键未定义** |
| 语言词表 | 103 代码；NEW 用 87 种；3 个不在表内（`bn`、`egy-leidentr`、`si`） |
| 无效多边形 | 整包 5，NEW 4 |

---

## 八、可复核性

```bash
cd code
python ops/m4-3/import_counts.py        # → ops/m4-3/import_counts.json
python ops/m4-3/connections_audit.py    # → ops/m4-3/connections_audit.json（含全部记录 ID）
```

两个脚本只读 `code/data/raw/pleiades_gis_4_1/gis/*.csv` 与 `code/data/staging/source_records.csv`，
不查数据库、不写任何业务文件。

---

## 九、与上一版的差异

| 项 | R1 | R1.1 | 原因 |
|---|---:|---:|---|
| source_record 增量 | 124,512（A1） | **127,829（A2 采纳）** | OWNER 决定合成代表点 |
| source_record 总量 | 153,903 | **157,220** | 同上 |
| 位置行 | 32,374 | **35,691** | 同上 |
| `unknown_time_bound_type` | ≥7,546 | **0** | 代码证明它只在 CHGIS 分支开票 |
| 台账可预测合计 | ≥15,506 | **7,960** | 同上 |
| V9 新增类型数 | 4（24 种） | **3（23 种）** | `place_without_geometry` 不写台账 |
| 连接分类 | 28 悬空 / 2 自环（未区分空行与 errata） | 28 悬空 = 24+3+1；真实自环 1 | 逐条核实 |
| candidate | 13,553 | 13,553（不变） | 按约束去重，未调整口径 |
