# M4-2 最终收尾报告（验证器与测试可靠性修正）

| 项 | 值 |
|---|---|
| 执行时间 | 2026-11-04 14:30–15:10（Asia/Shanghai） |
| 分支 | `m4-2-import-rules` |
| 起始 HEAD | `23504b767ff9543b3aee79c37d85f1d9230907c5`（与复核报告一致） |
| 代码提交 | **`2233cb56ad5df9850a3ff0f82974c50c6c91fa97`** |
| 报告提交 | 本文件独立提交，见 §9 |
| 正式库 | `canvas_history` **仍 V5**，九表行数未变（§8） |
| 最终状态 | **M4-2 — FINAL CLOSURE / READY FOR OWNER ACCEPTANCE** |

> 本轮只处理复核报告列出的 8 项，未扩大范围：导入架构、来源可选化、地图规则、
> V1–V8 迁移、历史基线一律未动。

---

## 一、八项问题处理对照

| 编号 | 问题（复核报告） | 处理 | 证据 |
|---|---|---|---|
| **P1** | V2/V7 的合成台账期望值取自被验证表自身，漏生成/多生成都可能 PASS | **已修**：新增 `expected_synth_counts()`，只读暂存 CSV 独立复算两类合成台账；V2/V7 改用该期望值并逐类型输出「独立期望 / 库内实际 / 差异」 | `verify_import.py:record_expected_synth`；`ops/m4-2/fault_injection.txt` 11/11 |
| **P2** | V9b 第三轮只校验退出码，未校验状态 | **已修**：第三轮前后快照对比 9 项指标；删除未使用的 SQL | `ops/m4-2/v9b.txt` V18–V24 |
| **P3** | V9b 地点匹配跨图层、取首条、无唯一性断言 | **已修**：改用 `created_from_source_record_id → source_record.external_id → CSV(县级, primary_external_id)` 稳定对应，两侧断言唯一，0/多条即 FAIL | `v9b.txt` V3–V6 |
| **P4** | 隔离库固定名、无条件 DROP、无 try/finally | **已修**：新增 `ephemeral_db.py`（随机名 + 存在即拒绝 + 上下文管理 + 只删自建 + 失败报错） | `ops/m4-2/db_safety.txt` 8/8 |
| **P5** | 保护测试把地点级阻断标成 `blocked_count` | **已修**：输出拆成 `place_blocked` / `source_blocked`，判据本身未改 | `protection.txt` P1 行 |
| **P6** | 报告 §八/§十三 与 §十四 结论冲突 | **已修**：三条测试路径分开陈述；§十三 第 5 条标记已解决；新增 §15 | `M4_2_IMPORT_RULES_REPORT.md` §8/§13/§14.1/§15 |
| **P7** | Git 追溯信息不全 | **已补**：本报告 §9 列全部完整 SHA | — |
| **P8** | 死代码与不规范路径 | **已清**：删 `tempfile` 死导入、未用 `bid`、`C://` 双斜杠（改 `shutil.which` 回退） | `git show 2233cb5` |

---

## 二、合成台账独立复算方法（P1）

### 2.1 规则来源

两条合成台账由导入器在写库时生成，本轮把它们的**判定规则**在验证器里独立实现一遍，
只读暂存 CSV，**不查询 `data_quality_issue`**：

| 类型 | 规则（与导入器一致） |
|---|---|
| `duplicate_external_id` | 源记录按 (dataset_id, record_scope, parent_external_id, external_id) 分组；组内行数 > 1 为重复组；`external_id` 已出现在暂存 `duplicate_sysid` 台账的组不再重复登记 ⇒ **每组 1 行** |
| `derived_value_mismatch` | 地点级时间 = 其 name + location 子行（排除被隔离的源记录）的 `min(valid_from)` / `max(valid_to)` 包络；逐地点逐列与 `historical_places.csv` 的暂存值比较 ⇒ **每处不等 1 行** |

`record_scope` / `parent_external_id` / `content_hash` 的派生复用导入器的**纯常量与规范化函数**
（`SCOPE_MAP`、`VALID_SCOPES`、`SENTINEL_PARENT`、`canonical_json`、`to_int`），
不使用任何运行期计数器（`dq_stat` / `cnt_*`）。

### 2.2 复算结果（与库内实际逐类型对照）

```
合成台账独立复算（期望值只来自暂存 CSV，不读 data_quality_issue）：
  issue_type                         独立期望     库内实际     差异
  duplicate_external_id                 5        5     +0
  derived_value_mismatch              197      197     +0
  manual_edit_conflict（运行期产生）           —        0      —
  推导依据：源记录 29,384 组 / 多行组 7 / 其中需登记 5 组 / 隔离 3 条；偏差 197 处落在 130 个地点
台账口径：暂存 12,631 + 独立复算 202 + 人工冲突 0 = 12,833；实际入库 12,833
```

结论：此前基线数字（5 / 197 / 130 / 12,833）本身是对的，**问题只在判据来源**；
现在同一组数字由两条独立路径得出并互相印证。

### 2.3 无法独立复算的一类（如实说明）

`manual_edit_conflict` 取决于导入那一刻库里哪些地点带 `locked` / `manual_edited_fields` /
`created_by='manual'`，**无法从暂存 CSV 复算**。本轮的处理是：单独列出、标注「运行期产生」，
不计入独立复算；它的正确性由 `verify_rollback_and_protection.py`（P1/P2、Q3、T1）单独证明。
这是一处**已知的残余自引用**，范围只限这一个类型，不影响另外两类的独立性。

---

## 三、故障注入结果（P1 验收）

全部在一次性隔离库执行（库名 `canvas_history_synth_fault_<pid>_<uuid8>`，跑完即删）。

| 步骤 | 操作 | 期望 | 实际 |
|---|---|---|---|
| A1 | 正常两轮导入后跑验证器 | exit 0 | **exit 0** |
| A2 | V2 / V7 判定 | PASS / PASS | **PASS / PASS** |
| B1 | 删除 1 条 `derived_value_mismatch` | exit ≠ 0 | **exit 1** |
| B2 | V2 判定 | FAIL | **FAIL** |
| B3 | V7 判定 | FAIL | **FAIL** |
| C1 | 插入 1 条不存在的 `duplicate_external_id` | exit ≠ 0 | **exit 1** |
| C2 | V2 判定 | FAIL | **FAIL** |
| D1 | 撤销注入、恢复原状 | exit 0 | **exit 0** |
| D2 | V2 / V7 | PASS / PASS | **PASS / PASS** |
| D3 | 台账恢复原状 | 12,833 / 197 / 5 | **12,833 / 197 / 5** |

**合计 11 / 11**，日志 `ops/m4-2/fault_injection.txt`。

> 这组实验同时证伪了上一轮的说法：当时「插 7 条额外行仍 PASS」被当成「不依赖固定数量」的证据，
> 实际上它暴露的是自我引用。本轮已把该对照实验从 M4-2 报告中撤下并注明原因。

---

## 四、V9b 三轮状态对照（P2/P3）

隔离库 `canvas_history_v9b_<pid>_<uuid8>`，跑完即删。**24 / 24 PASS**（`ops/m4-2/v9b.txt`）。

### 4.1 地点匹配（P3）

```
DB 侧：historical_place(place_id=5225, 由拳县) JOIN source_record(external_id=40052)
CSV 侧：(source_id='chgis', source_dataset='chgis_cnty', primary_external_id='40052') → 恰好 1 行
两侧唯一性均断言通过；同名（由拳县）验证为同一对象
```

不再使用 `canonical_name` 单条件 + `break` 取首条。

### 4.2 三轮状态

| 指标 | 第 1 轮（空库） | 第 2 轮（3 条 payload 变更） | 第 3 轮（同第 2 轮输入） |
|---|---|---|---|
| source_record 总数 | 29,391 | **29,391**（+0） | **29,391**（+0） |
| 新增源记录 | 29,391 | 0 | **0** |
| 内容更新 | 0 | **3** | **0** |
| content_hash（3 条目标） | 基线 | 3/3 变化 | **3/3 不变** |
| first_batch_id | 批 1–7 | 不变 | **不变** |
| last_batch_id | = 首轮批次 | 推进到第 2 轮批次 | **全部推进到第 3 轮批次** |
| `source_stat.updated` | — | 3 | **0** |
| 新批次 `inserted_source_record_ids` | 7 批非空 | 7 批非空 | **7 批全空** |
| 台账行数 / 指纹数 | 12,833 / 12,833 | 12,834 / 12,834 | **12,834 / 12,834** |
| Σ occurrence_count | 12,833 | 25,667 | **38,501（= 上轮 + 行数）** |
| 人工保护 | — | 1 条 `manual_edit_conflict`，地点正名未被覆盖 | 保持 |

判据说明：

- `last_batch_id` 推进与 `occurrence_count` +1 是**导入器的设计行为**（同一内容再次遇见仍要记录「最近一次被看到」），
  因此按「允许变化但必须精确符合设计」判定，不作为失败条件；
- 台账只按「行数 / 指纹数不变 + 每行 occurrence_count 恰好 +1」判定，
  没把合法的重复遇见误判成重复新增。

---

## 五、测试数据库安全管理（P4）

`ops/m4-2/ephemeral_db.py` 的约束：

| 要求 | 实现 |
|---|---|
| 不用固定库名 | `<prefix>_<pid>_<uuid8>`，每次运行唯一 |
| 建前查重 | `SELECT 1 FROM pg_database WHERE datname=%s`，命中即 **抛错终止**，不做任何删除 |
| 记录是否自建 | `self.created` 标志，只有 `True` 才允许清理 |
| 异常清理 | 上下文管理器（`__enter__/__exit__`），异常也走 `drop()` |
| 连接关闭 | 建库/删库用独立 admin 连接并 `close()`；业务连接由调用方显式关闭后再释放 |
| 清理失败 | 抛 `RuntimeError` 并打印库名，**不尝试删除其他库** |
| 禁止项 | 无 `DROP DATABASE IF EXISTS` 作为创建前清理；无固定名删除 |

### 安全测试（8 / 8 PASS，`ops/m4-2/db_safety.txt`）

| 用例 | 结果 |
|---|---|
| S1 正常运行后临时库已删除 | PASS |
| S1b 库名带 pid + uuid（非固定名） | PASS |
| S2 主体抛异常后临时库仍被删除，异常照常上抛 | PASS |
| S3 目标库已存在时拒绝创建 | PASS（抛错，未删除） |
| S4 冲突库仍然存在 | PASS |
| S4b 冲突库里的原有数据完好（`keep me`） | PASS |
| S5 非本实例创建的库不会被 drop | PASS |
| S6 测试自建的冲突库由测试自己清理 | PASS |

运行后核对 `pg_database`：**没有任何 `*_v9b_*` / `*_synth_fault_*` / `*_safety_*` 残留**。

---

## 六、人工保护测试（P5 + 回归）

`verify_rollback_and_protection.py` 在干净库 `canvas_history_m4check` 上跑（事务内执行后 ROLLBACK）：

```
place_blocked（地点级人工保护）3（期望 3）；source_blocked（源记录级 quarantine_hold）3
台账 manual_edit_conflict 3 条（期望 3，一行一条，R2 的 1:1 前提）
✓ P1  locked / manual_edited_fields / created_by=manual 三种保护位均未被机器覆盖
✓ P2  19,039 = 新增 0 + 更新 0 + 无变化 19,036 + 人工保护跳过 3，无误挡
✓ Q1–Q5、T1 全通过
```

**合计 9 项：PASS 8 / FAIL 0**（1 项 INFO）。标签已从 `blocked_count` 改为
`place_blocked` / `source_blocked` 两个口径，数字与判据均未变。

---

## 七、全套回归（本轮真实执行）

| 套件 | 结果 | 说明 |
|---|---|---|
| `verify_import.py` 全量（干净库 `canvas_history_m4check`） | **PASS 11 / FAIL 0 / UNVERIFIED 1** | V2/V7 已改用独立复算；V9b 仍如实标 UNVERIFIED（本库两轮同输入） |
| 合成台账故障注入（隔离库） | **11 / 11** | §3 |
| V9b 内容变化 + 第三轮幂等（隔离库） | **24 / 24** | §4 |
| 数据库生命周期安全（隔离库） | **8 / 8** | §5 |
| 人工保护与回滚（`m4check`） | **PASS 8 / FAIL 0** | §6 |
| M4-2 来源可选化 API | **19 / 19** | 真实 HTTP |
| M4-2 无来源地点上图 E2E | **9 / 9** | 真实浏览器 |
| M3 接口 / 写保护 / 浏览器 E2E | **51 / 51**、**4 / 4**、**56 / 56** | — |
| M2-A / M2 完整 / M2 管理界面 | **43 / 43**、**36 / 36**、**14 / 14** | — |
| M0/M1 浏览器 E2E | **13–14 / 15**（M0-02 未通过，见下） | 12:38 同代码状态下曾 15 / 15 |

### M0/M1 · M0-02 的如实说明

本轮多次复跑 M0-02「四种样式可用」均在 13–14/15，失败项固定为样式切换采样：

```
FAIL M0-02 样式名互异 2 种： /  /  / Outdoor；raster 0/0/0/0；每步点层 0/0/0/400
```

同一时刻的独立探测（把采样窗口从固定 1.5 s 放宽到最多 8 s，见 `ops/m4-2/m0_style_probe.txt`）：

```
Streets    用时  540ms  name="Streets"           raster=0 places=400
Satellite  用时 1051ms  name="Satellite"         raster=1 places=400
Hybrid     用时  537ms  name="Satellite Hybrid"  raster=1 places=400
Outdoor    用时  557ms  name="Outdoor"           raster=0 places=400
```

四套样式均能切换、点层始终 400；`curl` 四套 `style.json` 带 key 全部 200。
**判定：不是功能回退，是采样窗口在同机负载较高时不够**（样式 JSON 异步加载期间
`getStyle().name` 为空、自定义 source 被清空，这正是失败的形态）。

本轮**未改动前端与地图代码**（`git show 2233cb5 --stat` 可证），也未修改该测试
（不在本轮授权范围）。建议（待 Owner 批准）：把 M0-02 的固定 `wait(1500)` 改为
「轮询 `style.name === 目标` 或超时 8 s」，与本次探测一致。

---

## 八、正式数据库保护证明

```
canvas_history：Flyway max(version) = 5（未执行 V6/V7/V8）
source_record 29,391 / historical_place 19,039 / name 47,499 / location 18,101
candidate_match 53,131 / data_quality_issue 12,831 / import_batch 7 / data_dataset 8 / data_source 5
```

与 M3 封存、M4-2 各轮记录**逐表一致**。本轮所有写操作只发生在
`canvas_history_m4check`（干净库，只读核验 + 事务内保护测试）与三个一次性隔离库
（已全部删除）。未执行任何 Migration，未下载任何新数据。

---

## 九、Git 提交记录

| 提交 | 完整 SHA | 内容 |
|---|---|---|
| `0f4359e` | `0f4359e451377d6ef42e5ef89695971dba30e595` | 上轮：验证器去固定常量、删许可断言、V9b 首发、`cnt_place_blocked` 拆分 |
| `ab3f73f` | `ab3f73fdb9a214dd833182c627206552be8ba142` | 上轮：报告回填完整提交号 |
| `23504b7` | `23504b767ff9543b3aee79c37d85f1d9230907c5` | 上轮：报告修订指针可定位化 |
| `2233cb5` | `2233cb56ad5df9850a3ff0f82974c50c6c91fa97` | **本轮代码**：P1 独立复算 + `--only`、P2 第三轮状态、P3 地点匹配、P4 隔离库、P5 标签、P8 清理 |
| `c8bb465` | `c8bb46563477f5c9dedb4f505e6bf25646af5562` | **本轮报告**：新增本文件 + 统一 M4-2 报告口径 + 采样探测证据 |
| `6394d2d` | `6394d2dce8e879db1fa7d8205647826cd73742bf` | 清理误入库的回归截图（只动证据目录，不含逻辑） |

历史提交未被修改或重写；分支 `m4-2-import-rules` 线性推进，无远程推送。

---

## 十、未解决事项

| # | 事项 | 影响 | 建议 |
|---|---|---|---|
| 1 | `manual_edit_conflict` 无法从暂存独立复算 | 该类型仍以「运行期 + 库内实际」为准 | 若要彻底独立，需在导入前把保护位状态导出成可复算的输入快照，属模型变更 |
| 2 | M0-02 采样窗口偏紧（见 §7） | 负载高时会假失败 | 改为轮询等待样式名，需 Owner 批准修改该测试 |
| 3 | 正式库仍是 V5 + 旧台账 12,831 | 5180 上矩阵为降级态、台账少 2 行 | 发布窗口内授权 `flyway migrate` 到 V8 并重跑导入 |
| 4 | 写接口仍无鉴权 | 本机工具可接受 | 对外部署前必须补（M2 起遗留） |
| 5 | `source_records.attribution_text` 保留 | 属引用串，非准入条件 | 若需「零 attribution 字段」可再删一列，需同步重跑导入 |
| 6 | `issue_type` 值域为 20 值（设计文档 19 值） | 文档口径差一值 | 已在 `CORE_DATA_MODEL_V2.1.1.md` 旁注；后续新增类型应合并为一次修订 |

---

## 附：本轮新增 / 变更文件

| 路径 | 说明 |
|---|---|
| `code/ops/verify_import.py` | 新增 `expected_synth_counts()`、`--only`；V2/V7 改用独立期望值 |
| `code/ops/verify_rollback_and_protection.py` | `place_blocked` / `source_blocked` 标签 |
| `code/ops/m4-2/ephemeral_db.py` | 一次性数据库生命周期管理（新增） |
| `code/ops/m4-2/ephemeral_safety_test.py` | 数据库安全测试 8 项（新增） |
| `code/ops/m4-2/synth_ledger_fault_injection.py` | 合成台账故障注入 11 项（新增） |
| `code/ops/m4-2/v9b_update_path_test.py` | 第三轮状态幂等 + 地点匹配重写 |
| `code/ops/m4-2/{verify_import,protection,v9b,fault_injection,db_safety,m0_style_probe}.txt` | 本轮执行证据 |
| `code/ops/reports/M4_2_IMPORT_RULES_REPORT.md` | §8 / §13 / §14.1 口径统一，新增 §15 |

**M4-2 — FINAL CLOSURE / READY FOR OWNER ACCEPTANCE**
