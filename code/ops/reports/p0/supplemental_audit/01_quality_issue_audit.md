# 01 · data_quality_issue 全量行级核验

> 对象：正式库 `canvas_history`（作为**导入前基线**，全程未被修改）→ 演练库 `canvas_history_p0_rehearsal`
> 工具：`ops/p0/supplemental/audit_quality_issue.py`　明细：`02_quality_issue_diff.csv`（7,993 行）

---

## 一、先确定"同一条质量事实"用什么键

直接看表结构（`\d data_quality_issue`）：

| 项 | 值 |
|---|---|
| 主键 | `pk_data_quality_issue (issue_id)`，identity 列 |
| 业务唯一键 | `uq_data_quality_issue_c10 UNIQUE (issue_fingerprint)` |
| 指纹定义 | 生成列 `fn_issue_fingerprint(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value)` |
| 导入冲突规则 | `ON CONFLICT (issue_fingerprint) DO UPDATE SET last_batch_id=EXCLUDED.last_batch_id, occurrence_count = occurrence_count + 1` |

**结论：跨库比对不能用 `issue_id`**——新行会重新取号，两库的 id 不可比。
唯一能判"是不是同一条事实"的是 `issue_fingerprint`，而且它正是导入器的冲突目标。

由此得到两条硬判据：

1. 原有 12,831 条的指纹必须**全部仍在**；
2. 原有行**允许变化的列只有两列**：`last_batch_id`（设计如此）、`occurrence_count`（重复命中 +1）。
   其余 15 列若变了，就是"内容被改写"，必须逐条列出。

---

## 二、核验结果

| 核验项目 | 数量 |
|---|---:|
| 原有记录总数 | **12,831** |
| 原有记录完整保留（指纹全部命中） | **12,831** |
| 原有记录字段发生变化（排除 `last_batch_id` / `occurrence_count`） | **0** |
| 原有记录丢失 | **0** |
| 暂存新增记录 | **7,957** |
| 系统生成记录（`duplicate_external_id`） | **31** |
| 本轮未被触及的历史留痕 | **197** |
| 最终数据库记录数 | **20,824** |

校验：12,831 + 7,993 = 20,824；12,634（命中并更新）+ 7,993（新增）+ 197（未触及）= 20,824。

---

## 三、四个数字之间的关系（这次把差额彻底对上）

提问里列了五个数：12,831 / 20,591 / 36 / 20,627 / 20,824，差额 197。逐个拆开：

| 数字 | 含义 | 来源 |
|---|---|---|
| 12,831 | 正式库里**已经有**的台账行 | 基线库直接查询 |
| 20,591 | 暂存 `data_quality_issues.csv` 的行数 | 暂存文件 |
| 36 | 导入器**本次运行**新算出的 `duplicate_external_id` 条数 | 导入日志 |
| 20,627 | 本次运行**计算出的质量事实总数** = 20,591 + 36 | 日志 |
| 20,824 | 导入后库里的总行数 | 演练库查询 |

关键一步：**20,627 是"本次算出来的"，不是"库里最终有的"。**

- 这 20,627 条事实里，有 **12,634 条**与库里已有行的指纹相同 → 走 `ON CONFLICT` 更新
  （`occurrence_count + 1`、`last_batch_id` 前移），**不新增行**；
- 剩下 **7,993 条**是新的 → INSERT。

于是：

```
20,824（最终） = 20,627（本次算出） + 197（既不在本次计算范围、也没被覆盖的历史行）
```

**这 197 条正好是 `derived_value_mismatch`**，而且不是巧合：
M4-5 修正后归一化与导入器口径一致，导入器**再也算不出** v4.1 的 mismatch，
所以基线里那 197 条切片时代的 mismatch **既不会被命中更新、也不会被重新插入**，
它们只是"原样留在那里"。这就是差额 197 的完整来源。

> 也就是说：**差额 197 不是"多出来的 197 条"，而是"没被本轮触及的 197 条"。**
> 上一版报告把它笼统说成"197 条历史留痕"，方向对，但没有把这层算术关系讲清楚，此处补齐。

---

## 四、7,993 条新增行的来源追溯

| `first_batch_id` | 条数 | 批次对应 |
|---|---:|---|
| 25 | 7,991 | Pleiades 4.1 数据集批次 |
| 28 | 2 | WHG HGIS 数据集批次 |

按 `issue_type`：

| 类型 | 条数 | 生成者 |
|---|---:|---|
| `missing_coordinate` | 7,200 | 暂存文件（归一化阶段） |
| `accuracy_unknown_sentinel` | 728 | 暂存文件（归一化阶段） |
| `duplicate_external_id` | 31 | **导入器合成**（重复隔离算法） |
| `connection_endpoint_missing` | 28 | 暂存文件（归一化阶段） |
| `geometry_invalid_repaired` | 4 | 暂存文件（归一化阶段） |
| `attribution_missing` | 2 | **导入器合成**（WHG HGIS 无逐条授权块） |

按 `dataset_id`：`pleiades_gis_4_1` 7,991 + `whg_hgis_de_las_indias_sample` 2。

**另查**：新增行里"除 `dataset_id` 外与某条既有行完全相同"的疑似重复 = **0 条**。
即不存在"同一条事实只是换了 dataset_id 被重复记一遍"的情况。

---

## 五、197 条 `derived_value_mismatch` 专项

| 项 | 值 |
|---|---|
| 基线 | 197 |
| 导入后 | **197**（新增 0，丢失 0） |
| 数据集 | 全部 `pleiades_gis_4_1_slice`（v4.1 的 623 条已被 M4-5 消除，见 M4-5 报告） |
| 字段 | `valid_from_year_astro` 123 / `valid_to_year_astro` 74 |
| 观察值/重算值组合 | 70 种（不是同一个数字复制 197 次） |
| `first_batch_id` | 全部为 M4-2 时代的批次 |
| 本轮是否被改写 | 否（`occurrence_count` 与 `last_batch_id` 均未变——它们没被本轮命中） |

**为什么保留**：这 197 条记录的是"M4-2 时期暂存里的地点级时间与导入器重算值不一致"这一**历史事实**。
M4-5 之后该不一致已被消除，若删掉这些行就等于抹掉"曾经发生过什么"；
按 Owner 规则"不得静默删除、清空或降级历史数据"，一律保留。

**但仍有一个待决问题**（如实登记，不擅自处理）：
这 197 行现在描述的是一个**已不存在的**条件。它们既没有 `resolved` 标记，也没有说明为什么失效。
建议在正式库升级时把它们标为 `resolved=true` 并在 `resolution_note` 里注明"M4-5 修正了地点级时间包络规则，
该差异不再产生"——这是一次**有据的数据写入**，需要单独授权；本轮不做。

明细：`02_quality_issue_diff.csv` 中 `kind=baseline_missing / baseline_field_changed / new_row` 三类，
197 条对应的行不在 CSV 里（因为它们既没丢也没变，这是本轮的预期结果）。

---

## 六、732 条 `action_taken` 越界记录的核验

| 项 | 结果 |
|---|---|
| 越界行数 | **732** |
| 原动词分布 | `null_written` 728 · `repaired` 4 |
| 落库值 | **全部 `preserved_and_flagged`**（符合库内 6 值域） |
| 原始动词是否保留 | **是，732/732** 写在 `resolution_note` |
| 保留格式 | `……；action_taken 原值=null_written（库内 6 值域无此动词，落库按 preserved_and_flagged 记，原动词在此保留）` |
| 是否信息丢失 | **否**：原动词可被 `resolution_note LIKE '%action_taken 原值=%'` 精确筛出，且原值与行一一对应 |

代码依据：`ops/import_staging.py` 第 557–571 行——先判越界，再取映射，映射不上直接 `DerivationError` 中止整批
（即"绝不放行未知动词"），并把原动词追加进 `resolution_note`，同时计入警告。

---

## 七、结论

**通过。** 原有 12,831 条一条不少、一个字未改；新增 7,993 条全部可追溯到具体批次与类型；
197 条历史留痕不是"多出来的"，而是"本轮没碰的"，算术与原因都已对上。

唯一遗留：197 行缺少 `resolved` 标记（见 §五），建议在下一阶段一并处理，需授权。
