# 阶段三 · 最终收尾修订 R1.2 —— 简明修订记录

> 范围：只修 Owner 指出的 5 处实际缺陷（V5 / V8 / V6 / P2 / V13）+ 凭证处理。
> 未改 V1–V3 Migration、未改库结构、未改七张原始 CSV、未改变导入程序的数据处理语义、未导入正式库。
> R1 / R1.1 的全部日志与验证库原样保留（本轮的留痕文件另起 `r1_2/`，不覆盖旧文件）。

## 0. 一句话结论

五处判据全部按"判据必须来自实际查询、缺数据一律 FAIL"的原则收紧；新验证库 `canvas_history_stage3_r12`
从空库重迁 + 首轮 + 幂等轮后，13 项核验 **PASS 11 / FAIL 0 / UNVERIFIED 1**（V9b 为已知未走到路径），
P1/P2/Q/T 9 项 **PASS 8**（V12b INFO 不计），缺字段负向测试 2 例均 **FAIL + 退出码 1**，
断言注入仍 **退出码 3 / 九表 0 行**，正式库仍 **全 0 行**。

## 1. 逐条修订

### 1.1 V5 —— 坐标单侧 NULL 双向 + 完整性/原因说明入判据

文件：`ops/verify_import.py` → `v5_geom()`

| 项 | R1.1 | R1.2 |
|---|---|---|
| 单侧 NULL | 只统计 `lon IS NULL AND lat IS NOT NULL` 一个方向，且**未进 PASS 判据** | 双向分别计数（`n_lon_null` / `n_lat_null`），两者都必须为 0 |
| 有坐标缺 geom | 只在文案里打印 `n_coord_nogeom`，不参与判定 | `n_coord_nogeom == 0` 进入 `geom_ok` |
| 无坐标原因说明 | 只按 `record_status × crs_confidence` 打印每组 notes 空的行数 | `notes` 去空白后为空的行数必须为 0；且每条无 geom 行必须有 `missing_coordinate` 台账（覆盖率 100%） |
| 数据 | — | **未改任何坐标**，10 行无 geom 仍是 10 行，越界 1 行仍原样保留 |

实测（`07_verify_import.log`）：18,101 行坐标行 / 有 geom 18,091；单侧 NULL `lon 空 0 / lat 空 0`；
有 geom 缺坐标 0；有坐标缺 geom 0；无 geom 10 行（全部 staging/confirmed）、notes 空 0、台账缺口 0；越界 1 行台账相符。

### 1.2 V8 —— 摘要必备字段补齐 + 子字段校验 + 不再有裸 KeyError

文件：`ops/verify_import.py` → `SUMMARY_REQUIRED` / `_load_summary()` / `v8_idempotent()`

1. **必备键 11 → 13**：补 `dry_run`、`inject_fault`。这两个键在正文里被直接下标读取，却不在校验清单里 ——
   一旦缺失就是未捕获 `KeyError`（不是 FAIL）。
2. **source_stat 子字段必查**：`inserted / updated / touched / held` 必须存在且为整数；
   `candidate_stat` 至少 `staging / inserted`。缺一个即 `FAIL`，不再用 `.get()` 静默变 `None`。
3. **正文全部改 `.get()`**：任何漏检都只会输出 FAIL，不会抛异常中断核验。
4. **新增独立对账**：`source_stat` 四类之和必须等于库中 `source_record` 实际行数（29,391），
   防止"自报值自洽但和库不一致"。
5. 口径细节：`inject_fault` 在正常轮次本就为 `null`，故对它只要求"键存在"，其余键要求"存在且非空"。

负向测试（`r1_2_negctl/`，两份只在快照上做手脚、库不动）：

| 用例 | 造法 | 结果 |
|---|---|---|
| `missing_subfield` | `run2.source_stat` 删掉 `touched` | `✗ [V8] 执行快照不完整…["run2.source_stat 缺子字段或类型非整数 ['touched']"]`，EXIT=1 |
| `missing_key` | `run1` 整个 `dry_run` 键删除 | `✗ [V8] …["run1 快照缺字段 ['dry_run']"]`，EXIT=1（无 Traceback / 无 KeyError） |

### 1.3 V6 —— 双向比对扩到四列 + creator/role 基本完整性

文件：`ops/verify_import.py` → `v6_views()`

| 项 | R1.1 | R1.2 |
|---|---|---|
| 6.4 双向差集 | `(place_id, child_row_id)` 两列 | `(place_id, source_record_id, child_table, child_row_id)` 四列，双向 `EXCEPT` |
| 6.5 角色完整性 | 只查 creator 的子行字段为空、anchor 唯一 | 追加：`evidence_role` 只能是 creator/name/location（越界 0）；`child_table` 必须等于角色名（不符 0）；每地点至少 1 条 creator 行（缺 0）；creator 必须带 `source_record_id`（空 0） |

实测：name 47,499 / location 18,101 双向差集均为 0；creator 19,358 行；无 creator 行的地点 0；role 越界 0；
`child_table` 与角色不符 0；creator 缺源记录 0。时间跨度 9 列独立重算 0 不一致（保持 R1.1 判据，未改）。

> 说明：creator 行数（19,358）大于地点数（19,039）属设计使然 —— 同一地点可经多条源记录锚定，
> `is_anchor` 每地点恰 1 条已单独断言（`is_anchor≠1 的地点 0`）。

### 1.4 P2 —— 四类处置纳入实际断言

文件：`ops/import_staging.py` → `write_places()`（只加记账）；`ops/verify_rollback_and_protection.py` → `part_p()`

- 导入器新增 `self.place_stat = {inserted, updated, noop, protected, blocked, total}`，
  3.4 小节日志顺带打印"无变化"；**处置逻辑一行未改**（`rows/upd/skip` 的判断顺序、保护位条件、台账写入全部原样）。
- P2 原来是 `len(manual_blocks) == 3` 就 PASS，其余"19,036 个地点均判为 no_change"只是文案声称。
  现在逐项断言：

```
新增 0 / 更新 0 / 无变化 19,036 / 人工保护跳过 3（登记台账 3）
四类之和 19,039 = 地点数 19,039；处理地点数 19,039；blocked == protected == 3；noop == 19,039 − 3
```

### 1.5 V13 —— 字段完整保留 + 键唯一 + 收敛目标可落地

文件：`ops/verify_import.py` → `v13_candidate_trace()`

| 项 | R1.1 | R1.2 |
|---|---|---|
| 字段保留 | `diff = [k for k in src if k in t and …]` —— 留痕**缺列会被静默跳过** | 原始 19 列必须全部存在于留痕表头（缺列直接 FAIL），且逐字相等 |
| 唯一性 | 未查 | `staging_row_no` 不得重复；`candidate_id` 不得重复 |
| 行号自洽 | 未查 | 行号指向的原始行，其 `candidate_id` 必须等于留痕自身 |
| C09 收敛 | 只打印目标值 | 目标必须①存在于原始 CSV ②键（relation_type, place_id_a, place_id_b）与被收敛行一致 ③在 `candidate_match` 中有对应保留行 |
| 自指 | 未查 | `self_reference` 行不得有收敛目标 |

实测：6 行留痕；原始 19 列全部保留、逐字相符；行号/ID 无重复；4 条 C09 收敛行的目标
（cm_0025045 ×2 / cm_0025179 / cm_0025181）全部在库中可定位。

## 2. 改动文件与规模

| 文件 | 改动 |
|---|---|
| `ops/verify_import.py` | V5 / V6 / V8 / V13 四处判据；`SUMMARY_REQUIRED` 与 `_load_summary` 的字段校验；默认 `--run-dir` → `r1_2`；版本标识 R1.2 |
| `ops/import_staging.py` | 只加 `self.place_stat` 记账（6 行），数据处理语义零变更 |
| `ops/verify_rollback_and_protection.py` | P2 由"数 blocked"改为四类处置逐项对账 |

未改动：`V1__*.sql` / `V2__*.sql` / `V3__*.sql`、`docker-compose.yml`、`data/staging/*.csv`、`设计资料/**`。

## 3. 本轮未做（登记，不扩大范围）

- `V9b`（内容变更 → UPDATE 路径）仍未走到：两轮输入完全相同，`updated=0`；需构造 `content_hash` 变化的第三轮才能实测。
- `R2c` 失败路径仍只能靠受控注入，无真实数据缺陷可触发。
- 4 源 + 7 数据集的种子数据归属、`canvas_history_migrationcheck` 是否删除 —— 仍待 Owner 裁定。
