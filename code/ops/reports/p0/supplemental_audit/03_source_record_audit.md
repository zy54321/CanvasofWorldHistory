# 03 · source_record 指纹口径与逐字段核验

> 对象：正式库 `canvas_history`（基线，未修改）→ 演练库 `canvas_history_p0_rehearsal`
> 工具：`ops/p0/supplemental/audit_source_record.py`　明细：`04_source_record_diff.csv`（29,391 行）

---

## 一、先把问题摆清楚

导入日志写着：

```
新增 0 / 内容变更 0 / 仅触 last_batch_id 157,213 / 隔离保持 3
```

而上一版 P0 报告据 `unification_check.sql` 得出"原有记录指纹完全不变"。
两句话放在一起就是矛盾的信号：**29,391 条里有 29,388 条说"只动了 last_batch_id"，
但又说"指纹不变"**。本轮把这件事逐字段查清楚。

---

## 二、逐字段核验结果

把两库的 29,391 条按 `source_record_id`（克隆库，编号相同）一一对齐，比较全部 17 个字段：

| 项 | 结果 |
|---|---:|
| 基线原有行 | 29,391 |
| 导入后原有行 | 29,391 |
| 缺失 | **0** |
| 多出 | **0** |
| 发生变化的行 | **29,391**（不是 29,388） |
| 变化涉及的列 | **仅 `last_batch_id` 一列** |
| 除 `last_batch_id` 外还有其他列变化的行 | **0** |
| 完全未变的行 | **0** |

`last_batch_id` 的取值迁移（全部命中行）：

| 迁移 | 行数 | 数据集 |
|---|---:|---|
| 17 → 24 | 12,445 | `pleiades_gis_4_1_slice` |
| 15 → 22 | 10,522 | `chgis_v6_county_points` |
| 14 → 21 | 5,226 | `chgis_v6_prefecture_points` |
| 16 → 23 | 960 | `mcgd_zenodo_22094815_head960` |
| 18 → 26 | 209 | `whg_geoname_s_gn_sample` |
| 19 → 27 | 21 | `whg_getty_tgn_sample` |

合计 29,383；余下 8 条为 `whg_hgis_de_las_indias_sample`（20 → 28）。

---

## 三、回答提问里的五个问题

### 1. 原有 29,391 条是否全部保留？

**是。** 缺失 0、多出 0，编号区间两库完全相同（29,399–58,789）。

### 2. 29,388 条究竟修改了哪些字段？

**只修改了 `last_batch_id`**，一列。而且实际是 **29,391 条**都改了，不是 29,388。

差额 3 的来历：日志里的 `touched=29,388` 与 `held=3` 是**两个互斥的计数口径**——
`held` 记的是"源记录保持隔离状态（`is_active=false` + `duplicate_quarantine`），未被重新激活"，
**不等于"这一行没被碰过"**。代码里隔离分支同样执行了：

```python
self.cur.execute("UPDATE source_record SET last_batch_id=%s WHERE source_record_id=%s", ...)
self.cnt_blocked[x["ds"]] += 1      # 记为 quarantine_hold
```

所以那 3 条是"隔离状态保持不变，但 `last_batch_id` 前移了"。
它们分别是：

| source_record_id | 数据集 | 范围 | external_id | 状态 | last_batch_id |
|---:|---|---|---|---|---|
| 34339 | chgis_v6_prefecture_points | place | 35000 | `is_active=false` / `duplicate_quarantine` | 14 → 21 |
| 34340 | chgis_v6_prefecture_points | place | 35001 | 同上 | 14 → 21 |
| 56573 | pleiades_gis_4_1_slice | edge | 20469 | 同上 | 17 → 24 |

> 上一版 P0 报告里"3 条隔离记录保持不变"的表述**不准确**，应更正为
> "3 条隔离记录**继续保持隔离**，其 `last_batch_id` 与其余行一样前移"。

### 3. 是否只有 `last_batch_id` 发生变化？

**是。** 17 列逐列比对，只有这一列有差异，其余 16 列（含 `raw_payload`、`content_hash`、
`is_active`、`inactive_reason`、`ingested_at`、`first_batch_id`）**零差异**。

### 4. 是否还有其他字段变化？

**没有。** 见上表与 `04_source_record_diff.csv`（29,391 行 × 1 列，没有第二种列名出现）。

### 5. 现有 SHA256 不变究竟证明了什么？

这里要区分两种指纹，本轮都算了一遍：

| 指纹口径 | 是否包含 `last_batch_id` | 基线 | 导入后 | 结果 |
|---|---|---|---|---|
| **A 整行指纹** | 包含 | `6730280687859e65…` | `fbb711b8704aa07c…` | **不同** |
| **B 业务内容指纹** | 不包含 | `2dff3f58b41333f6…` | `2dff3f58b41333f6…` | **相同** |

`unification_check.sql` 用的是 B 口径（显式 `- 'last_batch_id'`），所以它证明的是：

> **29,391 条源记录的业务内容（哪一行、什么内容、属于哪个数据集、是否有效、原始载荷、内容哈希）
> 逐字节未变；只有导入维护指针 `last_batch_id` 按设计前移。**

它**不能**证明"整行字节不变"。

### 6. 「逐字节不变」这个说法准不准？

**不准确，必须修正。**

- 准确说法：**业务内容逐字节不变**（B 口径）；
- 不准确说法：整行逐字节不变（A 口径实际不同）。

我已同步修改 `P0_DATABASE_UNIFICATION_REPORT.md` §7.2，把那句"逐字节不变"改成
"业务内容指纹不变；`last_batch_id` 指针按设计前移"。

---

## 四、为什么 `last_batch_id` 变了不算数据变更

`last_batch_id` 的语义是"这条源记录最近一次被哪一批次核对过"，
是**导入器的幂等推进指针**，不是业务字段：

- 它由每轮导入无条件重写（命中即前移），与内容是否变化无关；
- 它不参与任何业务读路径（详情、搜索、地图、时间轴都不用）；
- 它被 V2 的 C24 约束要求"有 first 就必须有 last"，属结构性维护列。

把它算进"业务内容"会让每次重导都报"内容变了"，从而失去审计意义——
这也正是 `unification_check.sql` 一开始就把它剔除的原因。

---

## 五、结论

**通过，但需修正表述。**

- 原有 29,391 条全部保留，一行不少；
- 唯一变化是 `last_batch_id`，29,391 行全部前移，没有第二列被改；
- 业务内容指纹（B 口径）完全相同；
- 整行指纹（A 口径）不同——上一版报告"逐字节不变"的说法已更正为"业务内容不变"；
- 日志 `touched=29,388 / held=3` 的口径已解释清楚：`held` 是隔离状态，不是"行未变"。
