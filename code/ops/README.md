# ops —— 运维与自检脚本

| 文件 | 用途 |
|---|---|
| `verify_db.py` | 宿主机经 TCP 连接数据库，验证连接、PostGIS 能力、数据卷持久化 |
| `flyway.sh` | Docker 内执行 Flyway（固定版本 13.12.0-alpine），凭证不进命令行 |
| `verify_schema.py` | 把实际库结构与 `CORE_DATA_MODEL_V2.1.1` 逐项比对（表/列/类型/可空/约束/索引/视图/PostGIS） |
| `verify_constraints.py` | 在事务内逐条触发 C01–C26 约束，证明它们真的拦得住；结束 ROLLBACK，不留数据 |
| `verify_no_licence_gate.py` | 许可门禁不存在性审计：目录级 0 命中 + 发布路径无许可谓词 + 342 条台账写入全通 |
| `verify_fingerprint.py` | `fn_issue_fingerprint` 的 IMMUTABLE 核验：元数据、跨会话确定性、生成列等价性 |
| `IMPORT_VALIDATION_RULES.md` | 阶段三导入程序须自行校验、数据库不强制的规则（含 `notes` 必填） |
| `import_staging.py` | **阶段三导入器**：七张暂存 CSV → 九表（单事务、可重复执行、失败整批回滚、**断言失败即回滚**） |
| `verify_import.py` | 导入结果只读核验 V1–V9 + V12 + V13（**批次逐条指纹** / 行数链 / 外键 / 唯一键 / **NULL 安全几何 + 双向单侧 NULL + 无 geom 原因覆盖** / **视图四列双向恒等 + role 完整性** / 台账 / **快照必备键与子字段校验 + 独立复算的幂等** / 批次推进 / C27-C28 / **候选表留痕 19 列全保留 + 收敛目标落地**）；**未实际执行的检查不判 PASS，缺字段只输出 FAIL** |
| `verify_rollback_and_protection.py` | 事务内受控实测：P 人工保护三态、Q 回滚四道闸 R1/R2/R2b/R2c、T 真值表 7 格 + orphaned 反例 |
| `reports/` | 各轮执行日志与验收材料（`STAGE3_ACCEPTANCE.md`、`stage3_*.log`） |
| `reports/r1/` | **R1 修订轮**的按序原始日志：00 试运行 / 01 首轮导入 / 02 幂等 / 03 断言失败回滚 / 04 全量核验 / 05 保护与回滚 |
| `reports/r1_1/` | **R1.1 修订轮**的按序原始日志：00–07（含 06 夹具回滚后复检、07 时间类型 SQL 侧取证），以及 `run1_summary.json` / `run2_summary.json` / `fault_injection_summary.json`、`STAGE3_ACCEPTANCE_R1_1.md` |
| `reports/r1_2/` | **R1.2 收尾轮**的按序原始日志：00 空库迁移 / 01 试运行 / 02 首轮 / 03 幂等轮 / 04–06 断言失败回滚三件套 / 07 全量核验 / 08 保护与回滚 / 09 夹具回滚后复检 / 10–11 V8 缺字段负向对照 / 12 正式库空表 / 13–14 凭证轮换 / 15 轮换后复检；含三份 summary JSON 与本轮留痕 CSV |
| `reports/r1_2_negctl/` | R1.2 负向对照的快照夹具（只改 summary JSON，库不动），说明见其中 `README.txt` |

## 依赖

`psycopg2-binary`，装在本目录下（gitignore），不污染全局环境：

```bash
python -m pip install --target ./ops/.deps psycopg2-binary
```

## 常用命令

```bash
# 数据库连通性与 PostGIS
PYTHONPATH=./ops/.deps python ops/verify_db.py check

# 迁移（数据库名 + flyway 子命令，凭证从 .env 读取）
bash ops/flyway.sh canvas_history migrate
bash ops/flyway.sh canvas_history info
bash ops/flyway.sh canvas_history_migrationcheck migrate    # 空库初始化验证

# 结构核对（0 处差异时退出码 0）
PYTHONPATH=./ops/.deps python ops/verify_schema.py canvas_history

# 约束行为验证（全程事务内，结束回滚）
PYTHONPATH=./ops/.deps python ops/verify_constraints.py canvas_history_migrationcheck

# 许可门禁不存在性审计（结构层 + 发布路径 + 行为级正写）
PYTHONPATH=./ops/.deps python ops/verify_no_licence_gate.py canvas_history

# 指纹函数 IMMUTABLE 核验（19 个会话配置 × 8 组输入）
PYTHONPATH=./ops/.deps python ops/verify_fingerprint.py canvas_history

# 阶段三：导入（正式库此前禁止；先在独立验证库）
#   --excluded-csv 让每轮留痕各写各的，不覆盖上一轮证据
PYTHONPATH=./ops/.deps python ops/import_staging.py --db canvas_history_stage3_r12 --dry-run \
    --excluded-csv ops/reports/r1_2/stage3_excluded_rows.csv
PYTHONPATH=./ops/.deps python ops/import_staging.py --db canvas_history_stage3_r12 \
    --excluded-csv ops/reports/r1_2/stage3_excluded_rows.csv \
    --summary-json ops/reports/r1_2/run1_summary.json

# 阶段三：核验（--run-dir 指向本轮快照目录；V8 靠 run1/run2 两份摘要做独立复算）
PYTHONPATH=./ops/.deps python ops/verify_import.py --db canvas_history_stage3_r12 \
    --run-dir ops/reports/r1_2
PYTHONPATH=./ops/.deps python ops/verify_rollback_and_protection.py --db canvas_history_stage3_r12

# 断言失败→回滚 的受控验证（只用于**空库**，正常导入不得带此参数）
PYTHONPATH=./ops/.deps python ops/import_staging.py --db canvas_history_stage3_r12_fault \
    --inject-fault g1 --summary-json ops/reports/r1_2/fault_injection_summary.json
echo $?   # 期望 3
```

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 成功（dry-run 亦为 0，但事务已回滚） |
| 2 | 前置校验失败（含 I-01/I-02 必填、时间类型改判行不符）⇒ 整批回滚 |
| 3 | 断言失败（G1 / A1–A9 / A10）⇒ 整批回滚，`import_batch` 不残留 `succeeded` |

## flyway.sh 的约定

- 镜像固定 `flyway/flyway:13.12.0-alpine`（可用 `FLYWAY_IMAGE` 覆盖），不用 latest。
- 脚本目录固定 `backend/src/main/resources/db/migration`，Spring Boot 后端后续复用同一套。
- `FLYWAY_BASELINE_ON_MIGRATE=false` 写死：禁止用基线方式绕过真实迁移。
- 凭证经 `docker run -e VAR`（只传变量名）注入，不出现在命令行与日志。

## 阶段二 / 三留下的库

| 库 | 用途 | 说明 |
|---|---|---|
| `canvas_history` | 正式库 | V1–V3 已执行，业务表 **0 行**（阶段三未导入，等待 Owner 放行） |
| `canvas_history_migrationcheck` | 空库初始化验证库 | 从零跑通 V1–V3 的证明，保留待验收 |
| `canvas_history_stage3` | 阶段三首轮独立验证库 | **保留原状**（R1 未触碰）：`snapshot=54 / bounded=1,166`，即 R1 修复前的缺陷现场 |
| `canvas_history_stage3_r1` | **R1 独立验证库** | 从空库重跑：首轮 + 幂等轮，全部核验通过 |
| `canvas_history_stage3_r1_fault` | R1 断言失败回滚测试库 | 故意让断言失败，用于证明"失败不留残渣"；全部 9 表 0 行 |
| `canvas_history_stage3_r11` | **R1.1 独立验证库** | 从空库重跑：首轮 + 幂等轮 + 夹具（已回滚），13 项核验 PASS 11 / UNVERIFIED 1 |
| `canvas_history_stage3_r11_fault` | R1.1 断言失败回滚测试库 | 退出码 3，九表前后全 0，`succeeded` 0 |
| `canvas_history_stage3_r12` | **R1.2 独立验证库** | 从空库重跑：首轮 + 幂等轮 + 夹具（已回滚），13 项 PASS 11 / FAIL 0 / UNVERIFIED 1，P/Q/T PASS 8 |
| `canvas_history_stage3_r12_fault` | R1.2 断言失败回滚测试库 | 退出码 3，九表前后全 0，`succeeded` 0 |
