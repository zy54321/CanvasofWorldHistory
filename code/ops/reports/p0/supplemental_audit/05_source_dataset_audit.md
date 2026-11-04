# 05 · data_source / data_dataset 数量差异核验

> 对象：正式库 `canvas_history`（V5）→ 演练库 `canvas_history_p0_rehearsal`（V9 + 导入后）
> 日志：`ops/reports/p0/02_rehearsal_import.log` 第 44 行

---

## 一、日志里那句"期望"是怎么来的

演练日志原文：

```
### 3.1 data_source / data_dataset（幂等初始化）
  data_source 5 行（期望 4） / data_dataset 9 行（期望 7）
```

这两个"期望"**不是**导入器算出来的，是 `import_staging.py` 第 656 行写死的字符串：

```python
print(f"  data_source {a} 行（期望 4） / data_dataset {b} 行（期望 7）")
```

它是 M4-2 时代留下的常量。那时全项目只有：

- 4 个来源：`chgis` / `mcgd` / `pleiades` / `whg`
- 7 个数据集：`chgis` 2 个 + `mcgd` 1 个 + Pleiades 切片 1 个 + `whg` 3 个

之后发生了两件事，常量就再也对不上：

| 时间 | 事件 | 影响 |
|---|---|---|
| V5（M2） | 迁移种入 `manual` 来源 + `manual_entry` 数据集 | 来源 +1、数据集 +1 |
| M4-4a | 新增 `pleiades_gis_4_1` 数据集 | 数据集 +1 |

所以正确值是 **5 个来源 / 9 个数据集**，日志里的 4 / 7 是**统计口径过期**，不是数据出错。

---

## 二、实际库中的 5 条来源

| source_id | display_name | 由谁创建 | 是否有数据集引用 |
|---|---|---|---|
| `chgis` | China Historical GIS | 初始导入 | 2 |
| `mcgd` | MCGD (Modern China Geospatial Database) | 初始导入 | 1 |
| `pleiades` | Pleiades | 初始导入 | 2 |
| `whg` | World Historical Gazetteer | 初始导入 | 3 |
| `manual` | 人工录入 | **V5 迁移种入** | 1（`manual_entry`） |

- 没有"未被任何数据集引用的孤儿来源"；
- 没有重复来源（`source_id` 是主键）。

---

## 三、实际库中的 9 条数据集

| dataset_id | source_id | record_count | 由谁创建 |
|---|---|---:|---|
| `chgis_v6_county_points` | chgis | 10,522 | 暂存导入 |
| `chgis_v6_prefecture_points` | chgis | 5,226 | 暂存导入 |
| `mcgd_zenodo_22094815_head960` | mcgd | 960 | 暂存导入 |
| `pleiades_gis_4_1_slice` | pleiades | 12,445 | 暂存导入 |
| `pleiades_gis_4_1` | pleiades | 127,829 | **本轮暂存新增** |
| `whg_geoname_s_gn_sample` | whg | 209 | 暂存导入 |
| `whg_getty_tgn_sample` | whg | 21 | 暂存导入 |
| `whg_hgis_de_las_indias_sample` | whg | 8 | 暂存导入 |
| `manual_entry` | manual | 0 | **V5 迁移种入** |

### 暂存 CSV 的 8 行如何对应

`data/staging_m4_5/data_datasets.csv` 有 8 行，与库内 8 个"暂存导入"数据集**一一对应**
（顺序不同，`dataset_id` 全部命中，无缺无多）：

```
chgis_v6_prefecture_points / chgis_v6_county_points / mcgd_zenodo_22094815_head960
pleiades_gis_4_1_slice / pleiades_gis_4_1
whg_geoname_s_gn_sample / whg_getty_tgn_sample / whg_hgis_de_las_indias_sample
```

暂存 CSV 只覆盖 4 个来源（`chgis` / `mcgd` / `pleiades` / `whg`）；
第 5 个来源 `manual` 与第 9 个数据集 `manual_entry` 来自 **V5 迁移**，不在暂存里，这是设计如此。

> 另外：CSV 的 `record_count` 列为空，库里的 `record_count` 是导入器按 `source_records` 实际行数写入的
> （例如 `pleiades_gis_4_1` = 127,829 条源记录）。这不是遗漏，是刻意让库内计数可复算。

---

## 四、差异逐条说明

| 差异 | 原因 | 是否问题 |
|---|---|---|
| 日志说 4 个来源，实际 5 个 | 常量停留在 M4-2；V5 种入 `manual` | **口径过期，非数据问题** |
| 日志说 7 个数据集，实际 9 个 | 常量停留在 M4-2；V5 种入 `manual_entry`、M4-4a 新增 `pleiades_gis_4_1` | **口径过期，非数据问题** |
| 暂存 CSV 8 行、库里 9 条 | 第 9 条 `manual_entry` 由迁移种入，不入暂存 | **设计如此** |
| 是否存在重复数据集 | 无（`dataset_id` 主键，8 个暂存 id 全部唯一命中） | 否 |
| 是否存在错误创建 | 无；9 条全部可由"暂存 8 + 迁移 1"解释 | 否 |
| 是否有未使用来源 | 无；5 个来源都被至少 1 个数据集引用 | 否 |

---

## 五、已修正的统计逻辑

不是把数字改对，而是**去掉魔法常量，改成可验证的不变量**。
`ops/import_staging.py` §3.1 现在这样做：

```python
cur_datasets = 库内 data_dataset 全量
cur_sources  = 库内 data_source 全量
want_datasets = set(DATASETS)                 # 暂存注册表
want_sources  = {d["source_id"] for d in DATASETS.values()}
seeded_datasets = {"manual_entry"}            # 迁移种入，显式列出
seeded_sources  = {"manual"}

missing_ds / extra_ds / missing_src / extra_src 任一非空 ⇒ DerivationError，整批中止
```

输出也改成说明性而非断言式：

```
data_source 5 行 / data_dataset 9 行（暂存登记 8 个数据集 + 迁移种入 ['manual_entry']；
暂存涉及 4 个来源 + 迁移种入 ['manual']）
```

复跑验证（dry-run，不改任何库）：

```
$ python ops/import_staging.py --db canvas_history_p0_rehearsal --staging-dir data/staging_m4_5 --dry-run
### 3.1 data_source / data_dataset（幂等初始化）
  data_source 5 行 / data_dataset 9 行（暂存登记 8 个数据集 + 迁移种入 ['manual_entry']；
  暂存涉及 4 个来源 + 迁移种入 ['manual']）
### 3.2 import_batch（每数据集 1 批，status=running）
```

日志见 `05_dataset_check_dryrun.log`。

> 这个检查现在还会**拦住未来的退化**：如果哪次导入少登记了一个数据集，或库里冒出暂存与迁移都解释不了的
> dataset，会直接 `DerivationError` 中止整批，而不是印一行假"期望"就过去了。

---

## 六、结论

**通过。** 5 个来源、9 个数据集都合理，且每一条都能说清来源；
日志里的 4 / 7 是过期常量，已改为按注册表推导 + 不变量校验，未为了对齐数字改动任何数据库记录。
