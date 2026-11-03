# 阶段三 · 最终收尾修订 R1.2 —— 验收材料

> 本轮范围：修 Owner 源码审查指出的 5 处实际缺陷（V5 / V8 / V6 / P2 / V13）+ 凭证处理。
> 未改 V1–V3 Migration、未改库结构、未改七张原始 CSV、未改变导入程序数据处理语义、**未导入正式库**。
> R1 / R1.1 历史证据（日志、验证库、`r1_1/STAGE3_ACCEPTANCE_R1_1.md`）全部原样保留，无覆盖。

- 修订对象：`ops/verify_import.py`、`ops/import_staging.py`（仅记账）、`ops/verify_rollback_and_protection.py`（P2）
- 新验证库：`canvas_history_stage3_r12`、`canvas_history_stage3_r12_fault`（均为空库新迁 V1–V3）
- 本轮日志目录：`ops/reports/r1_2/`（00–15 按序）、`ops/reports/r1_2_negctl/`（负向夹具）
- 修订明细：`ops/reports/r1_2/REVISION_NOTES.md`

---

## 1. 五处修订要点（详见 REVISION_NOTES.md）

| 判据 | R1.1 的问题 | R1.2 的判据 |
|---|---|---|
| **V5** | 单侧 NULL 只查一个方向且不进判定；`有坐标缺 geom` 只打印；`notes` 空值只分组打印 | lon 空 / lat 空**双向分别**统计且都必须为 0；`有 geom 缺坐标 = 0`、`有坐标缺 geom = 0`；无 geom 行 `notes` 空 0 行 **且** `missing_coordinate` 台账覆盖率 100% 才 PASS |
| **V8** | 必备键只有 11 个，正文却直接读 `dry_run` / `inject_fault`（缺键 = 未捕获 `KeyError`）；`source_stat` 只判"是对象" | 必备键 13 个；`source_stat` 的 `inserted/updated/touched/held`、`candidate_stat` 的 `staging/inserted` 逐个校验存在且为整数；正文全改 `.get()`；新增 `四类之和 = 库中源记录数` 独立对账 |
| **V6** | 双向差集只比 `(place_id, child_row_id)`；role / creator 只查"字段为空 + anchor 唯一" | 双向差集扩到 `(place_id, source_record_id, child_table, child_row_id)` 四列；追加 role 越界、`child_table` 与角色一致、每地点有 creator、creator 必带源记录 |
| **P2** | 只断言 `len(manual_blocks) == 3`，"其余 19,036 均 no_change"是文案声称 | 新增/更新/无变化/保护跳过四类逐项断言，且四类之和 = 地点数 19,039、`noop = 19,039 − 3`、`blocked = protected = 3` |
| **V13** | 缺列被 `k in t` 静默跳过；行号/ID 不查重；C09 目标只打印不验证 | 原始 19 列必须全在且逐字相等；`staging_row_no`/`candidate_id` 不许重复；行号指向的原始行 ID 必须自洽；C09 目标须在原始 CSV 存在、键一致、库中有对应保留行；自指行不得有目标 |

改动仅限上述三份文件；`import_staging.py` 只增加 `self.place_stat` 记账（6 行），保护位判断、跳过顺序、台账写入**一行未改**。

## 2. 执行记录（`ops/reports/r1_2/`，全部为本轮真实执行）

| 序号 | 文件 | 内容 | 结果 |
|---|---|---|---|
| 00 | `00_flyway_migrate.log` | 空库 `canvas_history_stage3_r12` 迁 V1–V3 | Successfully applied 3 migrations |
| 01 | `01_dryrun.log` | 试运行（事务回滚） | EXIT 0，Δ 符合预期 |
| 02 | `02_run1_import.log` | 首轮导入 + `run1_summary.json` | EXIT 0，六表净增，`place_stat` 新增 19,039 |
| 03 | `03_run2_idempotent.log` | 第二轮幂等 + `run2_summary.json` | EXIT 0，六表 Δ 全 0，`无变化 19,039` |
| 04 / 06 | `04_fault_before_state.log` / `06_fault_after_state.log` | 故障库注入前后九表 | 前后**全 0**，`succeeded` 0 |
| 05 | `05_fault_injection.log` | `--inject-fault g1` | **EXIT 3**，整批回滚 |
| 07 | `07_verify_import.log` | 全量核验 V1–V13 | **PASS 11 / FAIL 0 / UNVERIFIED 1** |
| 08 | `08_verify_protection_rollback.log` | P1/P2 + Q 四道闸 + T 真值表 | **PASS 8 / FAIL 0**（V12b 为 INFO） |
| 09 | `09_post_fixture_recheck.log` | 夹具事务回滚后复检 | 与 07 结论行 **逐字一致**（`diff` 为空） |
| 10 / 11 | `10_negctl_missing_subfield.log` / `11_negctl_missing_key.log` | V8 缺字段负向对照 | 两例均 **FAIL + EXIT 1**，无 Traceback |
| 12 | `12_formal_db_empty.log` | 正式库身份 + 九表 + 六库 Flyway 校验和 | 九表 **0 行**；六库校验和一致 |
| 13 / 14 | `13_credential_state_before.log` / `14_credential_rotation.log` | 凭证有效性与轮换 | 旧口令作废、新口令可用 |
| 15 | `15_final_recheck_after_rotation.log` | 轮换后连通性 + 全量核验复跑 | 仍 **PASS 11 / FAIL 0 / UNVERIFIED 1** |

## 3. 核验结果（`07_verify_import.log` 汇总）

```
✓ V1  7/7 文件指纹与基线逐字节相等；import_batch 14 个批次逐条核对，NULL 0 / 不符 0
✓ V2  六表行数 = 暂存 − 结构性排除；台账 12,631 − 2 + 5 + 197 = 12,831；隔离 3 行保留未删
✓ V3  25 条外键全部 0 孤儿（全表扫描）
✓ V4  5 组业务唯一键全部 0 冲突
✓ V5  18,091 行几何全 SRID=4326/Point；IS DISTINCT FROM 0 行；lon/lat 单侧 NULL 双向 0/0；
      有 geom 缺坐标 0、有坐标缺 geom 0；无 geom 10 行全非 published、notes 空 0、
      missing_coordinate 覆盖 100%；越界 1 行台账 blocking/preserved_and_flagged 相符
✓ V6  列数 11/7/10；两视图各 19,039 行；canonical 每地点恰 1；证据行 84,958
      = creator 19,358 + name 47,499 + location 18,101，四列双向差集 0；
      role 越界 0、child_table 不符 0、无 creator 地点 0；时间跨度 9 列重算 0 不一致，
      实际派生 17,469 行（envelope 17,108 / no_evidence 1,570 / single_point 361）
✓ V7  12,831 行 / 14 种 issue_type / mismatch 197 条落 130 地点 / duplicate_external_id 5 / licence 0
✓ V8  13 必备键 + 9 表计数 + source_stat 4 子字段 + candidate_stat 2 子字段齐备；
      独立复算首轮六表全净增、次轮全 0；run1.after = run2.before；与库实际行数逐表相等；
      source_stat 四类和 29,391 = 库中源记录数
✓ V9  29,391 行 last_batch_id 均指向最新批；first_batch_id 未被改写
? V9b UNVERIFIED（两轮输入相同，updated=0；UPDATE 路径本次未走到）
✓ V12 C27 六条 R4a–R4f 全 0；C28 19,039 行重算 0 不一致
· V12b INFO（真值表穷尽性由 T 段夹具证明，不由本库数据证明）
✓ V13 53,137 = 入库 53,131 + 留痕 6（自指 2 + C09 4）；19 列全保留逐字相符；
      行号/ID 无重复；4 条 C09 目标在库中均可定位

合计 13 项：PASS 11 / FAIL 0 / UNVERIFIED 1
```

保护与回滚（`08`）：P1（三态保护位未被覆盖、`blocked=3` / 台账 3 条 1:1）、**P2（19,039 = 0 + 0 + 19,036 + 3）**、
Q（R1/R2/R2b/R2c 六步判定 + `N_quar=2 N_noop=1 N_blocked=4 N_fail_rb=1 N_rolled_back=3` = 11）、T（7 格 + orphaned 反例）
→ **PASS 8 / FAIL 0**。

## 4. 负向测试与回滚证据

1. **V8 缺字段（两份独立夹具）**：`source_stat.touched` 缺失、`dry_run` 键缺失，两次都输出
   `✗ [V8] 执行快照不完整 …` 且 `EXIT=1`，**没有 Traceback / KeyError**。
2. **断言失败回滚**：`canvas_history_stage3_r12_fault` 注入 g1 后 `EXIT=3`，九表前后全 0、`succeeded` 0。
3. **夹具不自证**：`verify_rollback_and_protection.py` 全程在事务内，结束 `ROLLBACK`；随后复检（09）与首检（07）
   结论行 `diff` 为空，证明夹具没在库里留下任何东西。

## 5. 凭证处理

| 项 | 结论 |
|---|---|
| 压缩包曾含 `.env` | 确认：旧 `code.zip` 内含 `code/.env`（旧包已作废，新包不含） |
| 旧凭证是否仍有效 | **有效**（`13`：TCP 连接成功；且错误口令被拒 ⇒ 密码认证真实生效，不是 trust 直通） |
| 是否轮换 | **已轮换**：`ALTER ROLE canvas_app WITH PASSWORD …`（28 位随机，scram-sha-256），`.env` 同步更新 |
| 轮换验证 | `14`：新口令可连；**曾泄露到压缩包的旧口令已被拒绝**；故意错误口令被拒 |
| 影响面 | 容器 `POSTGRES_PASSWORD` 只在 initdb 时使用，数据卷已存在；`.env` 同步后 `flyway.sh` / 三个 Python 脚本全部正常（`15`） |
| 交付包 | 重新打包，**不含 `.env`**，只保留 `.env.example`（其中 `POSTGRES_PASSWORD` 为空占位） |

## 6. 库状态

| 库 | 状态 | 核对 |
|---|---|---|
| `canvas_history`（正式） | **九张表全部 0 行** | `sr=0 place=0 name=0 loc=0 cand=0 ledger=0 batch=0 dataset=0 source=0` |
| `canvas_history_stage3`（R1 前缺陷现场） | 未触碰 | `snapshot=54 / bounded=1,166` |
| `canvas_history_stage3_r1` | 未触碰 | R1 首轮 + 幂等轮 |
| `canvas_history_stage3_r11` | 未触碰 | R1.1 首轮 + 幂等轮 + 夹具（已回滚） |
| `canvas_history_stage3_r11_fault` | 未触碰 | 九表 0 行 |
| `canvas_history_stage3_r12`（本轮） | 首轮 + 幂等轮 + 夹具（已回滚） | 29,391 / 19,039 / 47,499 / 18,101 / 53,131 / 12,831 / 14 / 7 / 4 |
| `canvas_history_stage3_r12_fault` | 故障注入专用 | 九表 0 行、`succeeded` 0 |

六库 Flyway 校验和完全一致，**无 DDL 漂移**：

```
1:882334605  2:966227528  3:-2058740630   （六库逐库相同，均 success=true）
```

## 7. 工程边界核对

| 约束 | 是否遵守 | 证据 |
|---|---|---|
| 不改 V1/V2/V3 Migration | ✅ | 六库 checksum 与 R1.1 完全相同 |
| 不改数据库结构 | ✅ | 未执行任何 DDL；`verify_schema` 结论沿用 R1.1 |
| 不改七张原始 CSV | ✅ | V1 现场 SHA256 7/7 = 基线 |
| 不改导入程序数据处理语义 | ✅ | 只加 `place_stat` 记账；两轮行数与 R1.1 逐表相同 |
| 保留 R1/R1.1 证据、不覆盖 | ✅ | `reports/r1/`、`reports/r1_1/` 未触碰；R1.1 验收文档另存 `r1_1/STAGE3_ACCEPTANCE_R1_1.md` |
| 不清理验证库 | ✅ | 六库全部保留 |
| 不执行正式库导入 | ✅ | 正式库仍 0 行 |

## 8. 仍未验证 / 待裁定（登记，不扩大范围）

1. **V9b**：`内容变更 ⇒ UPDATE` 路径仍未实测（两轮输入相同，`updated=0`）。需构造 `content_hash` 变化的第三轮。
2. **R2c**：失败路径只能靠受控注入，无真实数据缺陷可触发。
3. 4 源 + 7 数据集的种子数据归属（现由导入程序幂等 upsert）—— 待 Owner 裁定。
4. `canvas_history_migrationcheck` 是否保留 —— 待 Owner 裁定。
