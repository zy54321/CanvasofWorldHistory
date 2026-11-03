# 回滚与人工修改保护 V2.1.1

**项目**：《世界历史时空画布》
**版本**：2.1.1（取代 `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.md` 2.1.0；V2 / V2.1 文件保留原样不覆盖）
**性质**：设计文档。**本轮不含任何数据库施工**——无 DDL 执行、无 Migration、无数据导入、无 Git 操作。
**权威依据**：`V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md`（即 **V0.2.2-r2**，全文简称 **V0.2.2**；1,127 行）；`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md`（V0.2.1）；`V2.1/CORE_DATA_MODEL_V2.1.md`（V2.1 基线）。
**一致性锚（只读，本文件不得改写其口径）**：`CORE_DATA_MODEL_V2.1.1.md`（§4 / §5 / §5.9 / §5.10 / 附录 A / 附录 B）、`IMPORT_RULES_V2.1.1.md`（§6 / §7 / §8）、`FIELD_MAPPING_V2.1.1.csv`、`DATA_PROVENANCE_V2.1.1.md`。

> **效力顺序**：**V0.2.2 > V0.2.1 > V2.1 > V2**。
> **本文件的定位**：V2.1 基线的 §1–§7 骨架**全部保留**（回滚=一次新批次、`should_write()` 唯一实现、合并可逆、禁止 DELETE），本版在其上补一件事——
>
> > **把「导入结果」与「回滚结果」拆成两组互斥且穷尽的集合，各自给出恒等式，并写死判定顺序，使两组永不被同一个布尔表达式截走。**
>
> 上一轮 QA 判 FAIL 最密集的地方正是这里（D4-5 / D4-6 / D4-7）：集合没有分开写，导致一条行可以同时落进两个集合，而恒等式在"看起来成立"的数字例子里恰好成立。

---

## 0. 本文件回答什么

| # | 问题 | 落在 |
|---|---|---|
| 1 | 一次导入把库改坏了怎么办 | §2、§3.2、§3.4 |
| 2 | 人改过的数据怎么保证不被机器抹掉 | §6、§7 |
| 3 | **一次导入的结果怎么数，一次回滚的结果怎么数，两组能不能混** | **§3（本版核心）** |
| 4 | 哪些行参与回滚、哪些不参与、哪些连统计都不进 | §3.4、§4 |
| 5 | 怎么用 SQL 在事后复算上面每一条 | §4、§5 |
| 6 | 哪些结论**还没有被验证** | §11 |

**一句话**：回滚不是"撤销操作"，是**再执行一批**；而"这一批到底动了哪些行"必须能被两条恒等式独立复算出来——**导入的账算导入、回滚的账算回滚，两者的集合名相同不代表集合相同。**

---

## 1. 为什么回滚与人工保护必须写在同一份文件里

两条路径共用**同一个判定函数**（§6.2）与**同一套计数集合**（§3）。分开写就必然出现 V2 的三类漏洞：

| 洞 | V2 的写法 | 后果 |
|---|---|---|
| **洞 1：不看保护位** | 按 `batch.inserted_source_record_ids` 直接 `is_active=false` + 子行 `rejected` | 人改过的名字还在行里，但那一行从所有查询里消失了——**没被覆盖，被藏起来了**，用户视角完全等价 |
| **洞 2：不看墓碑** | 同上 | `CHECK (merged_into_place_id IS NULL OR (record_status='merged' AND …))` 立刻违反，回滚语句直接报错；若 CHECK 未生效，则读路径 `COALESCE(merged_into_place_id, place_id)` 会把"已拒绝"的地点解析到目标地点 |
| **洞 3：不看批次先后** | 同上 | 第 3 批插入、第 4 批更新、回滚第 3 批 ⇒ **连带撤销第 4 批的更新，且没有任何记录** |
| **洞 4（V2.1.1 新增发现）：不看集合归属** | 用 `is_active=false OR inactive_reason IS NOT NULL` 一个布尔式去判"是不是本批作用集内的行" | **本批新产生的 `duplicate_quarantine` 被提前截走**，同一行同时计入 `N_quar` 与 `N_noop`，两条恒等式同时破裂（§3.5 给出代数证明） |

洞 4 是**本版新增的发现**，也是 §3 存在的全部理由。它比前三个更隐蔽：前三个会报错或留下可见异常，洞 4 **不报错、不留痕、只在数字上不对**，而数字对不对要靠 §5 的四条断言去查——而那四条断言本身在暂存数据上**验不出来**（暂存 0 个回滚批次）。

---

## 2. 回滚的唯一合法形态：一次新的导入

### 2.1 回滚产生一行 `import_batch`

```
import_batch(status='rolled_back' | 'partial', rollback_of_batch_id=<被回滚的批次>)
```

三条理由（沿用 V2.1，不重复论证）：① 回滚会失败、会只成功一半，失败时必须有地方记录；② 审计链要连续（第 3 批导入、第 4 批回滚第 3 批、第 5 批重导）；③ 回滚是写入，必须过同一套 `should_write()`。

**新增第 ④ 条（本版）**：`import_batch` 的六个计数列（`quarantined_count` / `blocked_count` / `skipped_count` / `failed_count` / `inserted_source_record_ids` / `updated_source_record_ids`）是 **§3.3 回滚恒等式的左式来源**。若回滚不落成批次，R1 的右式就没有可读的计数对象。

### 2.2 回滚的判定流程（六步，顺序不可换）

```
rollback(batch R):
    # —— 操作级前置（4 种 BLOCK_OP，见 §2.5）——
    B1  断言 R.status ∈ {'succeeded','partial'}                    否则 BLOCK_OP
    B2  断言 ∄ C: C.rollback_of_batch_id = R.batch_id               否则 BLOCK_OP
    B3  断言 ∄ C: C.status = 'running'                              否则 BLOCK_OP
    B4  断言 operator 非空                                          否则 BLOCK_OP

    新开批次 Rb（status='running'，rollback_of_batch_id = R.batch_id，operator 同上）
    B ← R.inserted_source_record_ids                       # B 只含「已落库」的行

    for r in B:                                            # 判定顺序见 §3.4
        步骤 0  r.inactive_reason = 'duplicate_quarantine' → N_quar++      → 终止
        步骤 1  r 的其余历史失效                          → N_noop++      → 终止
        步骤 2  r.last_batch_id ≠ R.batch_id              → N_blocked++   → 终止（台账 rollback_conflict）
        步骤 3  派生行带保护位（created_by='manual' / locked / manual_edited_fields）
                                                          → N_blocked++   → 终止（台账 manual_edit_conflict）
        步骤 4  派生行已成墓碑（merged_into_place_id 非空）
                                                          → N_blocked++   → 终止（台账 rollback_conflict）
        步骤 5  写入失败                                  → N_fail_rb++   → 终止（台账 import_row_error）
        步骤 6  执行软撤                                  → N_rolled_back++
                r.is_active=false; r.inactive_reason='batch_rolled_back'
                r.inactive_at=now(); r.inactive_in_batch_id=R.batch_id
                派生行（place / location / name）record_status='rejected'

    Rb.status = 'rolled_back'  if blocked_count = 0 and failed_count = 0
              = 'partial'      otherwise
```

**六步的排序理由（每条都是"换位就开一个新的丢失窗口"）**：

| 序 | 为什么必须在这里 |
|---|---|
| 0 < 1 | 隔离行也满足 `is_active=false`。**步骤 1 在步骤 0 之前 ⇒ 隔离行被截走 ⇒ 同一行进两个集合**（§3.5 代数证明） |
| 1 < 2 | 一行"已被后续批次置为 `source_absent`"同时满足"历史失效"与"`last_batch_id` 不符"。历史失效在前 ⇒ 记 `N_noop`（正确，它确实无事可做）；`last_batch_id` 在前 ⇒ 记 `N_blocked` 并**凭空产生一条 `rollback_conflict` 台账**，而 R2 会因此显示"有冲突要人工处理"，把运维引向一个不存在的问题 |
| 2 < 3 | 一行既被后续批次碰过、又带保护位。批次先后在前 ⇒ 台账类型是 `rollback_conflict`（处置：决定要不要等后续批次）；保护位在前 ⇒ 台账类型是 `manual_edit_conflict`（处置：决定人工值保不保留）。**两种处置人不同**，台账类型必须稳定 |
| 3 < 4 | 一行既 `locked` 又被合并。保护位在前 ⇒ `manual_edit_conflict`；墓碑在前 ⇒ `rollback_conflict`。二者都只产生 **1 条**台账，R2 的 1:1 不受影响（§5.2 注） |
| 4 < 5 | 墓碑行的回滚 UPDATE 会违反 C06。必须先跳过，不能"试一下让它失败"——那会把一次可解释的跳过变成一条 `import_row_error` |

### 2.3 回滚能力边界（诚实版，沿用 V2.1 并补第 4 行）

| 场景 | 能自动回滚？ | 做法 |
|---|---|---|
| 本批**新增**、之后没被碰过、无保护位、无墓碑 | **能** | `is_active=false` + `reason='batch_rolled_back'` + 子行 `rejected` |
| 本批**新增**，但有人工修正 | **不能** | 记录级跳过 + `blocked_count+1` + `manual_edit_conflict` |
| 本批**新增**，但已被合并 | **不能** | 记录级跳过 + `blocked_count+1` + `rollback_conflict`（先解除合并） |
| 本批**新增**，但后续批次更新过 | **不能** | 记录级跳过 + `blocked_count+1` + `rollback_conflict` |
| 本批**更新**的记录 | **不能字段级回滚** | 不存旧值快照（见下） |
| 本批产生的候选 / 台账 | **能** | 按 `batch_id` 撤销；台账置 `resolved=true` + `resolution_note='batch rolled back'`，**不删行** |
| **本批之前已失效的行**（在 `B` 内） | **不适用** | 记 `N_noop`，不动、不落台账 |

**关于"本批更新不能回滚"**：需要一张"每次更新存旧值"的 history 表。`historical_place_name` **47,499 条（预计入库）** + `historical_place_location` **18,101 条（预计入库）** + `source_record` **29,391 条（暂存原始；隔离不删行，入库同为 29,391）**，全量历史会变成数十万行（数量级估算，非统计值），而实际使用频率接近 0（个人项目，一次导入搞错直接重导旧文件更快）。**这是有意识的取舍，不是遗漏**——写在文档里，否则会被当成 bug 反复报。

**`partial` 的语义（沿用 V2.1，写死）**：`blocked_count > 0` **或** `failed_count > 0` ⇒ `status='partial'`；两者皆 0 ⇒ `'rolled_back'`。一个"部分回滚"的库比"完全没回滚"更危险，因为前者看起来像干净的——**所以这个状态必须显式存在，且 `notes` 必须写明各集合的计数**。

### 2.4 回滚批次也要过导入前置校验吗

| 校验 | 回滚批次 Rb 是否执行 |
|---|---|
| §1 表头/`record_scopes` 声明 | **不执行**（无输入文件，`input_file` 记被回滚批的文件仅供审计） |
| `record_scope` / `parent_external_id` / `duplicate_ordinal` / `grain_key` 可派生 | **不执行**（不派生新行） |
| `derivation_version` 已声明 | **执行**（继承 R 的值，用于回答"这次回滚按哪版规则解释派生列"） |
| 五段业务键唯一性预检 | **不执行**（不插入） |
| 重新执行重复检测（第 0 步） | **不执行**——`duplicate_quarantine` 是**每批重算的结论**，回滚不改内容 ⇒ 重算结果必然与当前一致（§3.4 步骤 0 直接读当前状态） |

> ⛔ **回滚不重算隔离**。若回滚时重算，会把"本批隔离行"变成"非本批隔离行"，`inactive_in_batch_id` 被改写，R1 与 G2 同时失去复算基础。

### 2.5 BLOCK_OP 只剩 4 种，且**全部是操作级**

| # | BLOCK_OP 情形 | 为什么是"整次操作不该继续" |
|---|---|---|
| **B1** | 目标批次 `status ∉ {'succeeded','partial'}` | 回滚一个从未成功过的批次没有语义 |
| **B2** | 目标批次**已被回滚过**（∃ `C.rollback_of_batch_id = R`） | 会二次撤销 |
| **B3** | 回滚运行期间存在另一个 `status='running'` 的批次 | 两个写者同时动 `source_record`，计数无意义 |
| **B4** | 无 `operator` | 审计链断裂，回滚不可追责 |

**⛔ 墓碑与 `created_by='manual'` 不是 BLOCK_OP（本版按裁定收为记录级跳过）**：

V0.2.1 §2.2.2a 曾把「回滚遇墓碑」「回滚遇 `created_by='manual'`」列为 BLOCK_OP 的第 ③ ④ 项，同时 §2.2.2 判定表第 3 行（`created_by='manual'`）O5 列又写 BLOCK_OP，而 G8-03 的修订方案第 1 条又要求"记录级跳过 + `blocked_count+1`"。**三处互相冲突。** 本版钉死：

```
判定表第 3 / 4 / 5 行（created_by='manual' / locked / manual_edited_fields）
  ⇒ 记录级跳过 + blocked_count += 1 + 落 1 条台账
  ⇒ 不是 BLOCK_OP。
墓碑（merged_into_place_id 非空）
  ⇒ 记录级跳过 + blocked_count += 1 + 落 1 条 rollback_conflict
  ⇒ 不是 BLOCK_OP。
BLOCK_OP 只剩 B1–B4 四种，全部是「整次操作不该继续」。
```

**理由**：一行是墓碑或人工创建，是**记录级属性**。把它升格为操作级阻断，会让"一条被合并的地点"停掉整批回滚——这正是 G8-03 要修的原始缺陷（记录级属性被升格为操作级），只是当时换了个例子。

> **登记为一致性观察（不修改冻结文件）**：`CORE_DATA_MODEL_V2.1.1.md` §5.3 把 `blocked_count` 的括注写成「记录级跳过（locked / 字段保护 / `last_batch_id` 不符）」，是**非穷尽列举**；完整构成见 §3.2 的 4 行子表（导入语境）与 §3.4 的 3 行子表（回滚语境）。

---

## 3. ⭐ 两组集合与恒等式（本版核心）

### 3.1 记号纪律：同名不等于同集

| 记号 | 在「导入结果统计」（G1）里指 | 在「回滚结果统计」（G2）里指 |
|---|---|---|
| `N_fail_import` | **导入期**写入失败（行根本没落库） | — |
| `N_fail_rb` | — | **回滚期**写入失败（行在库，UPDATE 违反约束） |
| `N_quar` | **本批新产生**的 `duplicate_quarantine` 行 | **`B` 中处于** `duplicate_quarantine` 的行（可能是被回滚批产生的，也可能是后续批次重判产生的） |
| `N_blocked` | 导入判定表的记录级跳过（4 种成因，§3.2） | 回滚六步的记录级跳过（3 种成因，§3.4） |
| `N_noop` | 命中既有活性行、`content_hash` 相同 ⇒ 只刷 `last_batch_id` | 在 `B` 内但**回滚前已失效** ⇒ 无事可做 |
| 输入全集 | `In_I`（本批输入行，`|In_I| = input_row_count`） | `B`（被回滚批**已落库**的插入集，`|B| = len(R.inserted_source_record_ids)`） |

> ⛔ **本文件不使用不带下标的 `N_failed` 或 `N_fail`**。导入期统一写 `N_fail_import`，回滚期统一写 `N_fail_rb`；R2c 的台账批次参数固定为 `:Rb`。
> ⛔ **`N_noop` 在两个组里都是致命项**：G2 的 `N_noop` 若判定顺序错，会把 `N_quar` 截走（§3.5）。

### 3.2 第 1 组：导入结果统计（批次 `I`）

**全集**：`In_I` = 本批输入行集合，`|In_I| = input_row_count`。

```
G1 恒等式
  input_row_count
    = N_fail_import      -- 写入失败、未落库
    + N_quar             -- 落库、本批隔离
    + N_inserted         -- 落库、活性新增
    + N_updated          -- 命中既有活性行、内容变化、写入非伴生列
    + N_noop             -- 命中既有活性行、内容未变、只刷 last_batch_id
    + N_blocked          -- 记录级跳过（该行不动，其他行继续）
```

| 集合 | 定义（逐字，可 SQL 复算） | 落库？ | 对应 `import_batch` 计数列 |
|---|---|---|---|
| `N_fail_import` | 该输入行在写入时违反约束或派生中断；**事务回滚到该行的 savepoint**，`source_record` 无此行的任何痕迹；仅留 1 条 `data_quality_issue(issue_type='import_row_error', batch_id=I)` | **❌ 不落库** | `failed_count` |
| `N_quar` | 落库，`first_batch_id=I`，`is_active=false`，`inactive_reason='duplicate_quarantine'`，`inactive_in_batch_id=I`，`duplicate_ordinal > 0`（C20）；**不派生任何子行**（place / location / name / candidate） | ✅ | `quarantined_count` |
| `N_inserted` | 落库，`first_batch_id=I`，`is_active=true`，`inactive_reason IS NULL`；派生全部子行 | ✅ | `len(inserted_source_record_ids)` |
| `N_updated` | 命中既有**活性**行（`is_active=true`，C03 ⇒ `inactive_reason IS NULL`），`content_hash` 不同，且至少一个非伴生列的真值发生变化 | — 更新 | `len(updated_source_record_ids)` |
| `N_noop` | 命中既有**活性**行，`content_hash` **完全相同** ⇒ 只写 `last_batch_id=I`（`raw_payload` / `content_hash` / `duplicate_ordinal` / `source_record_id` 一律不动） | — 只刷伴生列 | `skipped_count` |
| `N_blocked` | 命中既有行，但被 §3.2.1 的 4 种成因挡住 ⇒ 该行不动，其他行继续，`blocked_count += 1` | — 不动 | `blocked_count` |

**「伴生列」的唯一定义**：`last_batch_id`（唯一一个允许在 `N_noop` 里被改的列）。`raw_payload` / `content_hash` / `duplicate_ordinal` / `source_record_id` / `first_batch_id` 都不算伴生列。

#### 3.2.1 `N_blocked` 的 4 种成因（`blocked_count` 的完整构成）

| # | 成因 | 判据 | 台账 | 与判定表对应 |
|---|---|---|---|---|
| 1 | `created_by='manual'` | 行由人工创建 | `manual_edit_conflict`，`field_name=''` | 第 3 行 |
| 2 | `locked` | 整行冻结 | `manual_edit_conflict`，`field_name=''` | 第 4 行 |
| 3 | `manual_edited_fields` 非空 | 字段级冻结 | `manual_edit_conflict`，`field_name=<第一个被挡字段>` | 第 5 行 |
| 4 | `quarantine_hold` | 该行当前已是 `duplicate_quarantine` 且本批仍判定为完全重复 ⇒ 保持既有隔离结论 | **无**（不是数据质量问题，是"维持上一批已记录的结论"） | 第 0 行 / 第 8 行的 `quarantine_hold` 分支 |

> ⛔ **判定表第 3 / 4 / 5 行是记录级跳过 + `blocked_count+1`，不是 BLOCK_OP**（§2.5）。
> ⛔ **第 4 种成因不落台账**：它的台账已在"产生隔离结论的那一批"以 `duplicate_external_id` 记过，且有 `occurrence_count` 累加机制（CORE §5.9）。再记一条会破坏"重复发现 ⇒ UPDATE 不 INSERT"的语义 A。

#### 3.2.2 覆盖性与互斥性

```
互斥：6 个集合的判据两两不相交——
  · 落库/未落库 先把 N_fail_import 与其余 5 个分开；
  · 落库内用 (first_batch_id = I?) 分 N_quar+N_inserted 与 N_updated+N_noop+N_blocked；
  · 「命中既有行」内部由 (content_hash 相同?) 分 N_noop 与 {N_updated, N_blocked}；
  · N_updated 与 N_blocked 由「是否被挡住」分——挡住即不写，不可能同时"写了非伴生列"。

穷尽：任一输入行的结局只可能是这 6 种——
  ① 写不进去（含约束违反、派生中断）；
  ② 写进去且是隔离态；
  ③ 写进去且是活性新增；
  ④ 命中旧行且内容变了 → 写了；
  ⑤ 命中旧行且内容没变 → 只刷伴生列；
  ⑥ 命中旧行但被挡住 → 不动。
  没有第 7 种：判定表第 0/3/4/5/8/9 行的每一个分支都落在 ①–⑥ 之内。
```

#### 3.2.3 ⛔ D4-7：未落库的写入失败记录**不得**计入已插入集合

```
N_fail_import ∩ N_inserted = ∅            （结构不变量）
inserted_source_record_ids ∩ {失败行} = ∅  （B 里不得含失败行）
```

**三条必须写死的实现约束**：

1. 失败行**没有** `source_record_id`（未落库 ⇒ 主键未生成）⇒ 它不可能出现在 `inserted_source_record_ids` 里。若实现者先 INSERT 再回滚 savepoint 却把 id 记进数组，数组里会有"指向不存在的行"的悬空 id。
2. `failed_count` **不得**进入 `|B|`。`|B| = len(R.inserted_source_record_ids)`，而失败行从未进入该数组。**若有人为了"配平"把 `failed_count` 加进 `|B|`，R1 的右式会多减一次 `failed_count`**（§5.2）。
3. **A1 断言是这一条的可执行形式**：`count(source_record WHERE dataset_id=:ds AND first_batch_id=:b) == len(inserted_ids)`（`IMPORT_RULES_V2.1.1.md` §1.3）。它同时排除"漏记"与"多记"。

### 3.3 第 2 组：回滚结果统计（回滚批次 `Rb`，被回滚批 `R`）

**全集**：`B = R.inserted_source_record_ids`，`N_new = |B|`。**`B` 内的行全部已落库**——这是 §3.2.3 的直接推论。

```
G2 恒等式（两行，互为代入）
  (i)  N_new = N_quar + N_normal
  (ii) N_normal = N_rolled_back + N_blocked + N_fail_rb + N_noop
```

| 集合 | 定义（逐字，可 SQL 复算） | 参与回滚？ | 台账 |
|---|---|---|---|
| `N_new` | `|B|`，被回滚批**已落库**的插入总数 | — | — |
| `N_quar` | `B` 中 `inactive_reason='duplicate_quarantine'` 的行数 | **不参与**（从未派生对象，回滚它没有语义） | 无（隔离台账在产生批，`issue_type='duplicate_external_id'`） |
| `N_normal` | `N_new − N_quar` | — | — |
| `N_rolled_back` | 实际软撤成功的行数：`is_active=false`，`inactive_reason='batch_rolled_back'`，`inactive_in_batch_id=R`，且派生行 `record_status='rejected'` | **参与且成功** | 无 |
| `N_blocked` | 记录级跳过（3 种成因，见 §3.4 步骤 2/3/4） | **不参与** | **恰 1 条**：`rollback_conflict` 或 `manual_edit_conflict` |
| `N_fail_rb` | 回滚期写入失败（软撤 UPDATE 违反约束） | **尝试但失败** | 恰 1 条 `import_row_error` |
| `N_noop` | `B` 中**回滚开始前已失效**、且 `inactive_reason ≠ 'duplicate_quarantine'` 的行数 | **不参与**（无事可做） | 无（既有失效不是数据质量问题） |

**`N_noop` 的真实来源（必须写清，否则会被当成恒为 0 的占位项）**：`B` 内的行由 `R` 插入，回滚前若已失效，只可能来自**后续批次**的处置——① 后续批次判定源端消失 ⇒ `source_absent`；② 后续批次判定它是重复副本 ⇒ `duplicate_quarantine`（此情形进 `N_quar`，不进 `N_noop`）。**所以 `N_noop` 与 `N_quar` 在同一次回滚里可以同时非零，这正是洞 4 的触发条件。**

#### 3.3.1 `N_blocked` 的 3 种成因（回滚语境的 `blocked_count` 完整构成）

| # | 成因 | 判据 | 台账类型 | 台账 `field_name` |
|---|---|---|---|---|
| 1 | `last_batch_id` 不符 | `r.last_batch_id ≠ R.batch_id` | `rollback_conflict` | `''` |
| 2 | 保护位 | 派生行（place / location / name）任一满足 `created_by='manual'` / `locked` / `manual_edited_fields` 非空 | `manual_edit_conflict` | `''`（**行级判定，见下**） |
| 3 | 墓碑 | 派生行任一 `merged_into_place_id` 非空 | `rollback_conflict` | `''` |

> ⭐ **回滚期的记账粒度是「行」，导入期的记账粒度是「字段」——这是 R2 能否成立的前提**。
> 导入期：一条记录 3 个字段被挡 ⇒ 记 **3 行** `manual_edit_conflict`（`IMPORT_RULES_V2.1.1.md` §7.2）。
> 回滚期：一条记录不论被几个字段挡住 ⇒ 记 **1 行**，`field_name=''`（因为回滚是整行的一票否决，写入要么整行撤、要么整行不撤）。
> **若不这么写死，R2 的 `count(台账) == N_blocked` 会在"一行多字段受保护"时直接破**（3 ≠ 1）。

#### 3.3.2 覆盖性与互斥性（4 格穷尽表）

回滚期对一个 `B` 内行的判定，**只取决于两个字段**：`is_active` 与 `inactive_reason`。

| `is_active` | `inactive_reason` | 归属 | 依据 |
|---|---|---|---|
| `true` | `NULL` | **在回滚作用集内** ⇒ 继续判 §3.4 步骤 2/3/4/5，落 `N_blocked` / `N_fail_rb` / `N_rolled_back` | C03 |
| `false` | `'duplicate_quarantine'` | **`N_quar`** | §3.4 步骤 0 |
| `false` | `'source_absent'` / `'batch_rolled_back'` | **`N_noop`** | §3.4 步骤 1 |
| `true` | 非 `NULL` | **非法状态，不可能出现**（C03 违反） | C03 |

**3 格合法 + 1 格不可能 = 穷尽。** 三格互斥由 `inactive_reason` 的值域（3 值 + NULL，C19）保证。

### 3.4 判定顺序（写死，命中即终止）

```
对 B 中每一行 r，自上而下判定，命中即计入并终止：

步骤 0（先判「本批作用集」= 本批的隔离结论）
    r.inactive_reason = 'duplicate_quarantine'                   ⇒ N_quar++        ─ 终止

步骤 1（此时才判历史失效）
    r.is_active = false OR r.inactive_reason IS NOT NULL         ⇒ N_noop++        ─ 终止

步骤 2（批次先后）
    r.last_batch_id ≠ R.batch_id                                 ⇒ N_blocked++     ─ 终止  台账 rollback_conflict

步骤 3（保护位，含 created_by='manual'）
    派生行任一：created_by='manual' / locked / manual_edited_fields 非空
                                                                 ⇒ N_blocked++     ─ 终止  台账 manual_edit_conflict

步骤 4（墓碑）
    派生行任一：merged_into_place_id IS NOT NULL                  ⇒ N_blocked++     ─ 终止  台账 rollback_conflict

步骤 5（写入失败）
    软撤 UPDATE 违反约束 / 事务中断                               ⇒ N_fail_rb++     ─ 终止  台账 import_row_error

步骤 6（其余）
                                                                 ⇒ N_rolled_back++
```

> ⛔ **步骤 0 必须在步骤 1 之前**，这是本版对 V0.2.2 §2.4.1 判定顺序的**唯一实质性修正**（原顺序把"作用集"放在第 1 步、把 `duplicate_quarantine` 放在第 2 步，导致隔离行在第 1 步就被截走）。代数证明见 §3.5。
> ⛔ **步骤 0 的判据是 `inactive_reason` 的值，不是 `is_active` 的布尔值**。任何以 `is_active = false` 打头的实现都会把 `duplicate_quarantine` 与 `source_absent` 混为一谈。
> ⛔ **步骤 1 必须在步骤 2 之前**：一行"已被后续批次置 `source_absent`"同时满足两者；先判批次先后会凭空产生一条 `rollback_conflict`（§2.2 排序理由表第 2 行）。

### 3.5 洞 4 的代数证明：为什么 `is_active=false OR inactive_reason IS NOT NULL → N_noop` 必须禁止

设一次回滚，`|B| = 10`，真实构成：

```
本批隔离（quarantine）   N_quar        = 2     行 1, 2
回滚前已失效（noop）      N_noop        = 1     行 3       （后续批次置 source_absent）
保护位挡住                N_blocked     = 2     行 4, 5
回滚写入失败              N_fail_rb     = 1     行 6
正常软撤                  N_rolled_back = 4     行 7–10
                                 合计 = 2+1+2+1+4 = 10 = |B|  ✓
```

**修正后的判定顺序（步骤 0 在前）**：`N_quar=2`（行 1,2 在步骤 0 被终止）、`N_noop=1`（行 3）、`N_blocked=2`、`N_fail_rb=1`、`N_rolled_back=4`。G2(ii) 右式 = 4+2+1+1 = 8 = `N_normal` = 10−2 ✓。

**若使用 V0.2.2 §2.4.1 的原顺序（步骤 1 = 作用集，步骤 2 = quarantine）**：

```
行 1、2：is_active=false 命中步骤 1 ⇒ N_noop++   →  N_noop(算法) = 1 + 2 = 3
行 3   ：is_active=false 命中步骤 1 ⇒ N_noop++   →  （已含）
行 4,5 ：N_blocked = 2
行 6   ：N_fail_rb = 1
行 7–10：N_rolled_back = 4

而 N_quar 由集合定义（B 中 inactive_reason='duplicate_quarantine' 的行数）= 2，不受算法影响。

于是：
  G2(ii) 右式 = N_rolled_back + N_blocked + N_fail_rb + N_noop
              = 4 + 2 + 1 + 3 = 10
  N_normal     = |B| − N_quar = 10 − 2 = 8
  8 ≠ 10                              ⇒  ❌ G2(ii) 破裂
```

**同一行（行 1、2）同时计入 `N_quar` 与 `N_noop` ⇒ 隔离统计与历史失效统计不再互斥 ⇒ 恒等式恒不成立。**

**再看 R1**：

```
修正后：LHS = 4；RHS = N_normal − N_noop − N_blocked − N_fail_rb = 8 − 1 − 2 − 1 = 4   ✓
原顺序：LHS = 4；RHS = 8 − 3 − 2 − 1 = 2                                               ❌ 6 差 2
```

**结论（必须写进交付物）**：

| 命题 | 结论 |
|---|---|
| 洞 4 会不会被 R1 抓到 | **会**，但**只在 `N_noop > 0` 或 `N_quar > 0` 的真实回滚批上**。暂存数据 0 个回滚批次 ⇒ **无数据可验**（§11 U5） |
| 洞 4 会不会被 G2 抓到 | **会**，且不依赖 R1 的代入是否相同——G2 是**穷尽性**检查，R1 是**代数值**检查。两者互为独立校验，缺一不可 |
| 洞 4 的根因 | 把「集合定义」（`N_quar` 是集合基数）与「计数算法」（命中即终止）混用同一套判据。**集合必须先按 `inactive_reason` 的值划分，算法才有意义** |

### 3.6 两组不得混用的三个具体方式（QA 判 FAIL 的原始落点）

| # | 混用方式 | 后果 | 本版的阻断手段 |
|---|---|---|---|
| 1 | 用导入期的 `failed_count`（即 `import_batch[R].failed_count`）代入 R1 的 `failed_count` | R1 右式多减一次；`|B|` 与 `failed_count` 来自同一批但含义不同（一个"落库了"，一个"没落库"） | R1 的 `blocked_count` / `failed_count` **只读 `import_batch[Rb]`**（回滚批次自己的计数）。§5.2 逐字写死 |
| 2 | 用回滚期的 `N_quar`（`B` 中隔离行数）去代替导入期的 `N_quar`（本批新产生隔离数） | 回滚批次的 `quarantined_count` 恒为 0（回滚不产生隔离），代入 R1 后右式恒多 0… 但 `B` 里可能真有隔离行 ⇒ 少减 | 两个 `N_quar` **必须分别命名**：`N_quar_import`（= `import_batch[I].quarantined_count`）与 `N_quar_B`（= 集合基数）。R1 只用 `N_quar_B` |
| 3 | 用 `A6` 的 `quarantined_count = count(source_record WHERE first_batch_id=:b AND NOT is_active)` 去反推 `N_quar_B` | A6 的口径是「本批插入且当前不活性」——它把"本批插入、后被后续批次置 `source_absent`"的行也算成 quarantined ⇒ 与 `N_quar_B` 差一个 `N_noop` | A6 是**导入期**幂等断言，**不得**用于回滚统计。§5.2 附注 |

---

## 4. 七种反例（每种 5 件事）

> 每个反例都必须回答 5 件事：**属哪个集合 / 是否参与回滚 / 是否产生质量台账 / 是否计入统计 / SQL 如何复算**。
> 凡涉及两个阶段的（导入 + 回滚），分两行写——**因为「属哪个集合」在不同阶段指不同的组**。

### 4.1 反例 ① 正常新增后回滚

**场景**：第 3 批导入 100 行全部成功，无重复、无保护位、无人再碰过；第 4 批回滚第 3 批。

| 问题 | 导入期（批次 3 = `I`） | 回滚期（被回滚批 3 = `R`，回滚批 4 = `Rb`） |
|---|---|---|
| 属哪个集合 | 100 行全部 ∈ `N_inserted` | 100 行全部 ∈ `N_rolled_back` |
| 是否参与回滚 | — | **参与，且全部成功** |
| 是否产生台账 | 否 | 否 |
| 是否计入统计 | `N_inserted = 100`，`input_row_count = 100` | `N_new = 100`，`N_quar = 0`，`N_normal = 100`，`N_rolled_back = 100`，其余三项 0 |
| SQL 复算 | `count(*) WHERE first_batch_id=3 AND is_active = 100` | 见下 |

```sql
-- G1：input_row_count = N_fail_import + N_quar + N_inserted + N_updated + N_noop + N_blocked
--     六项各自独立取数，互不代入
SELECT b.input_row_count,
       b.failed_count                          AS n_fail_import,   -- 未落库
       b.quarantined_count                     AS n_quar,          -- 落库且隔离
       (SELECT count(*) FROM source_record sr
         WHERE sr.first_batch_id = 3 AND sr.is_active)              AS n_inserted,
       coalesce(array_length(b.updated_source_record_ids,1),0)      AS n_updated,
       b.skipped_count                         AS n_noop,          -- 只刷 last_batch_id
       b.blocked_count                         AS n_blocked,
       b.input_row_count
         - b.failed_count - b.quarantined_count
         - (SELECT count(*) FROM source_record sr
             WHERE sr.first_batch_id = 3 AND sr.is_active)
         - coalesce(array_length(b.updated_source_record_ids,1),0)
         - b.skipped_count - b.blocked_count                        AS residual   -- 期望 0
  FROM import_batch b WHERE b.batch_id = 3;

-- G2：N_new = N_quar + N_normal；N_normal = N_rolled_back + N_blocked + N_fail_rb + N_noop
WITH b AS (SELECT inserted_source_record_ids AS ids FROM import_batch WHERE batch_id = 3),
     r AS (SELECT * FROM import_batch WHERE rollback_of_batch_id = 3)
SELECT count(*)                                                      AS n_new,
       count(*) FILTER (WHERE inactive_reason='duplicate_quarantine') AS n_quar,
       count(*) FILTER (WHERE inactive_reason='batch_rolled_back'
                          AND inactive_in_batch_id = 3)               AS n_rolled_back
  FROM source_record WHERE source_record_id = ANY((SELECT ids FROM b));

-- R1（左右式各自独立算，不得互相代入；完整可执行式见 §5.2）
SELECT (SELECT count(*) FROM source_record
         WHERE inactive_in_batch_id = 3
           AND inactive_reason = 'batch_rolled_back')                       AS lhs,   -- 期望 100
       (SELECT coalesce(array_length(inserted_source_record_ids,1),0)
          FROM import_batch WHERE batch_id = 3)
     - (SELECT count(*) FROM source_record
         WHERE source_record_id = ANY(SELECT inserted_source_record_ids
                                        FROM import_batch WHERE batch_id = 3)
           AND inactive_reason = 'duplicate_quarantine')                    AS n_normal_base,
       (SELECT blocked_count FROM import_batch WHERE rollback_of_batch_id = 3) AS blocked_rb,
       (SELECT failed_count  FROM import_batch WHERE rollback_of_batch_id = 3) AS failed_rb;
-- rhs = n_normal_base − 0(no_op) − blocked_rb − failed_rb = 100 − 0 − 0 − 0 = 100
-- ⚠️ n_normal_base 是 (|B| − N_quar)，不是 N_normal；N_noop 须另行减去（本例为 0）
```

**判定**：G1 `100 = 0+0+100+0+0+0` ✓；G2 `100 = 0 + 100`，`100 = 100+0+0+0` ✓；R1 `100 = 100` ✓。

### 4.2 反例 ② 新增后重复隔离

**场景**：第 3 批导入 100 行，其中 2 行（`sr_A`、`sr_B`）是 CHGIS `35000` / `35001` 组的完全重复副本 ⇒ 写入时 `is_active=false, inactive_reason='duplicate_quarantine', duplicate_ordinal=2`，**不派生任何子行**；第 4 批回滚第 3 批。

| 问题 | 导入期（批次 3） | 回滚期（回滚批 4） |
|---|---|---|
| 属哪个集合 | `sr_A`、`sr_B` ∈ `N_quar`（本批新产生隔离）；其余 98 行 ∈ `N_inserted` | `sr_A`、`sr_B` ∈ **`N_quar`（B 中隔离行）**；其余 98 行 ∈ `N_rolled_back` |
| 是否参与回滚 | — | **不参与**（SKIP，不计入任何"作用"类集合） |
| 是否产生台账 | **是**：2 条 `duplicate_external_id`（`severity='warning'`, `action_taken='preserved_and_flagged'`, `batch_id=3`） | **否**（不得再记一条；重复发现走 `occurrence_count += 1` 的 UPDATE 通道） |
| 是否计入统计 | `N_quar = 2`，`N_inserted = 98` | `N_quar = 2`，`N_normal = 98`，`N_rolled_back = 98`，`N_noop = 0` |
| SQL 复算 | `count(*) WHERE first_batch_id=3 AND inactive_reason='duplicate_quarantine'` = 2 | 同列复算，且 `inactive_reason` 仍须为 `'duplicate_quarantine'`（**不得被改成 `batch_rolled_back`**） |

```sql
-- 关键复算：隔离行的 reason 在回滚后必须原样保留
SELECT source_record_id, is_active, inactive_reason, inactive_in_batch_id
  FROM source_record
 WHERE source_record_id IN ('sr_A','sr_B');
-- 期望：false / duplicate_quarantine / 3    ← 不是 4，也不是 batch_rolled_back

-- R1 必须减 N_quar：不减则 LHS(98) ≠ RHS(100)
-- G2 必须先把它们判成 N_quar：误判成 N_noop ⇒ RHS 98-2-0-0 = 96，与 LHS 98 差 2
```

**判定**：G1 `100 = 0+2+98+0+0+0` ✓；G2 `100 = 2 + 98`，`98 = 98+0+0+0` ✓；R1 `98 = (100−2)−0−0−0` ✓。

### 4.3 反例 ③ 之前已失效的记录再次导入

**场景**（两个子情形，必须分开数）：

**③a 复活（不在 `B`）**：第 3 批导入 A；第 4 批源端 A 消失 ⇒ `is_active=false, inactive_reason='source_absent', inactive_in_batch_id=4`；第 5 批 A 重新出现 ⇒ O1 命中五段键 ⇒ `is_active=true, inactive_reason=NULL`。回滚第 5 批。

| 问题 | 导入期（批次 5） | 回滚期（回滚批 6，`R`=5） |
|---|---|---|
| 属哪个集合 | A ∈ `N_updated`（内容变化时）或 `N_noop`（内容未变时） | A **不在 `B`**——`B = inserted_source_record_ids(5)`，A 是第 3 批插入的 ⇒ **不属 G2 任何集合** |
| 是否参与回滚 | — | **不参与**。回滚第 5 批不撤销"复活" |
| 是否产生台账 | 否（复活不是数据质量问题） | 否 |
| 是否计入统计 | `N_updated` 或 `N_noop` 各 +1 | 不计入 |
| SQL 复算 | `first_batch_id` 仍是 3；`last_batch_id` 是 5 | `SELECT source_record_id FROM source_record WHERE source_record_id=A`：`first_batch_id=3` ⇒ `NOT (A = ANY(B_5))` |

> ⛔ **这是「本批更新不能字段级回滚」的一个具体后果**：复活是第 5 批做的，但它不是"插入"，所以回滚第 5 批不会把它退回去。**必须在 `notes` 里写明**，否则会被当成漏洞反复报。
> ✅ 若 A 在复活后又收到**人工拒绝**（`rejected_by='manual'`），则 §7 的"永不自动恢复"生效——但那与回滚无关。

**③b `B` 中被后续批次置 `source_absent`（`N_noop` 的真实来源）**：第 3 批导入 100 行；第 4 批发现其中 1 行（`sr_C`）源端消失 ⇒ `source_absent`，`inactive_in_batch_id=4`，`last_batch_id=4`；第 5 批回滚第 3 批。

| 问题 | 导入期（批次 3） | 回滚期（回滚批 5，`R`=3） |
|---|---|---|
| 属哪个集合 | `sr_C` ∈ `N_inserted` | `sr_C` ∈ **`N_noop`**（历史失效 + 非隔离） |
| 是否参与回滚 | — | **不参与**（已失效，无事可做） |
| 是否产生台账 | 否 | **否**。`source_absent` 本身不是数据质量问题（V0.2.1 判定表第 10 行「O3 无台账」） |
| 是否计入统计 | `N_inserted = 100` | `N_noop = 1`，`N_rolled_back = 99` |
| SQL 复算 | — | `count(*) WHERE source_record_id = ANY(B) AND inactive_reason='source_absent'` = 1 |

```sql
-- 关键：这一行同时满足「历史失效」与「last_batch_id ≠ R」
-- 若步骤 1 不先于步骤 2，会多产生 1 条 rollback_conflict 台账，
-- 使 R2 显示 blocked_count=1 而实际"没有需要人工处理的回滚冲突"。
SELECT source_record_id, is_active, inactive_reason, inactive_in_batch_id, last_batch_id
  FROM source_record
 WHERE source_record_id = 'sr_C';
-- 期望：false / source_absent / 4 / 4        ← last_batch_id=4 ≠ R=3
-- 正确归属：N_noop（步骤 1 命中）            ← 不是 N_blocked
```

**判定**：G2 `100 = 0 + 100`，`100 = 99+0+0+1` ✓；R1 `99 = (100−0)−1−0−0` ✓；R2 `0 = 0` ✓（**不得是 1**）。

### 4.4 反例 ④ 已锁定记录

**场景**：第 3 批导入 100 行，其中 `sr_D` 派生的地点被人 `locked=true`；第 4 批回滚第 3 批。

| 问题 | 导入期 | 回滚期（回滚批 4，`R`=3） |
|---|---|---|
| 属哪个集合 | 批次 3 时无人锁定 ⇒ `N_inserted` | `sr_D` ∈ **`N_blocked`**（步骤 3：保护位） |
| 是否参与回滚 | — | **不参与**（该行不动，其他 99 行继续） |
| 是否产生台账 | 否 | **是**：1 条 `manual_edit_conflict`，`severity='info'`，`field_name=''`，`action_taken='needs_manual_review'`，`batch_id=4` |
| 是否计入统计 | — | `N_blocked = 1`，`blocked_count = 1`，`status='partial'`，`N_rolled_back = 99` |
| SQL 复算 | — | 见下 |

```sql
-- 台账 1:1 复算（R2 的右式）
SELECT count(*) FROM data_quality_issue
 WHERE batch_id = 4
   AND issue_type IN ('rollback_conflict','manual_edit_conflict');   -- 期望 1 = N_blocked

-- 被挡的行必须原样保留（一个字段都不许动）
SELECT sr.source_record_id, sr.is_active, sr.inactive_reason, p.record_status, p.locked
  FROM source_record sr JOIN historical_place p ON p.created_from_source_record_id = sr.source_record_id
 WHERE sr.source_record_id = 'sr_D';
-- 期望：true / NULL / staging / true       ← 回滚不得把 is_active 改成 false
```

> ⛔ **不是 BLOCK_OP**：一条被锁的行不得停掉整批回滚（§2.5）。`status` 记 `partial`，`notes` 写明"1 行因保护位未撤"。

### 4.5 反例 ⑤ 人工修改保护记录

**场景**：`sr_E` 派生的 location 被人改了坐标 ⇒ `manual_edited_fields = {geom, representative_lon}`；`sr_F` 派生的 name 被人清空 ⇒ `manual_edited_fields = {name_text}`（**软清空**，§6.3）。回滚第 3 批。

| 问题 | 导入期 | 回滚期（回滚批 4，`R`=3） |
|---|---|---|
| 属哪个集合 | 批次 3 时无人工标记 ⇒ `N_inserted` | `sr_E`、`sr_F` ∈ **`N_blocked`**（步骤 3：字段级保护） |
| 是否参与回滚 | — | **不参与**（整行不撤——回滚是整行的一票否决，不存在"撤一半"） |
| 是否产生台账 | 否 | **是**：2 条 `manual_edit_conflict`，`field_name=''`（**回滚期行级记账，不是字段级**，§3.3.1） |
| 是否计入统计 | — | `N_blocked = 2`，`blocked_count = 2`，`N_rolled_back = 98` |
| SQL 复算 | — | `count(*) WHERE batch_id=4 AND issue_type='manual_edit_conflict'` = 2 |

```sql
-- 若实现者按"导入期字段级"记账（E 有 2 个字段、F 有 1 个字段）⇒ 记 3 条
-- ⇒ R2 得到 3 ≠ N_blocked=2 ⇒ 断言失败。这是必须写死的粒度差异。
SELECT count(*) FROM data_quality_issue
 WHERE batch_id = 4 AND issue_type = 'manual_edit_conflict';   -- 期望 2（每行 1 条）

-- 人工值必须原样存活
SELECT l.location_id, l.representative_lon, l.manual_edited_fields, l.record_status
  FROM historical_place_location l WHERE l.source_record_id = 'sr_E';
-- 期望：人工改后的坐标 / {geom,representative_lon} / staging（不是 rejected）

SELECT n.name_id, n.name_text, n.manual_edited_fields, n.record_status
  FROM historical_place_name n WHERE n.source_record_id = 'sr_F';
-- 期望：NULL（软清空）/ {name_text} / staging（不是 rejected）
```

> ⛔ **软清空必须被当成"保护"而不是"空着可以随便填"**：清空即把字段名加进 `manual_edited_fields`（§6.3）。若实现者漏了这一步，回滚（或下次导入）会把源值填回来，"我删掉了错误坐标"就失效了。

### 4.6 反例 ⑥ 写入失败但未落库

**必须分两个阶段，这是 D4-7 的全部内容**：

**⑥a 导入期失败（不进 `|B|`）**：第 3 批输入 100 行，其中 `sr_G` 写入时违反 `C16`（`time_bound_type='exact'` 但一端为 NULL）⇒ savepoint 回滚，`source_record` 中不存在该行，仅 1 条 `import_row_error`。

| 问题 | 导入期（批次 3） | 回滚期（回滚批 4，`R`=3） |
|---|---|---|
| 属哪个集合 | `sr_G` ∈ **`N_fail_import`** | `sr_G` **不在 `B`**（没有 `source_record_id`）⇒ 不属 G2 任何集合 |
| 是否参与回滚 | — | **不参与，也参与不了**（库里没有这一行） |
| 是否产生台账 | **是**：1 条 `import_row_error`，`batch_id=3` | 否 |
| 是否计入统计 | `N_fail_import = 1`，`input_row_count = 100`，`N_inserted = 99` | `N_new = |B| = 99`（**不是 100**） |
| SQL 复算 | `len(inserted_ids) = 99`；`failed_count = 1`；`99 + 1 = 100` | `SELECT count(*) FROM import_batch WHERE batch_id=3` ⇒ `|B|` 读数组长度 = 99 |

```sql
-- ⛔ D4-7：失败行不得出现在 inserted_source_record_ids 里
SELECT b.batch_id, array_length(b.inserted_source_record_ids,1) AS n_ids,
       b.failed_count, b.input_row_count
  FROM import_batch b WHERE b.batch_id = 3;
-- 期望：99 / 1 / 100    且 99 <> 100（差额正好是 failed_count）

-- ⛔ 任何 inserted id 都必须能 join 到真实行；否则就是"悬空 id"
SELECT unnest(b.inserted_source_record_ids) AS sid
  FROM import_batch b WHERE b.batch_id = 3
EXCEPT
SELECT source_record_id FROM source_record;
-- 期望：0 行
```

**⑥b 回滚期失败（`N_fail_rb`）**：回滚时对 `sr_H` 执行软撤 UPDATE，违反 `C21`（`inactive_at` 与 `inactive_reason` 同生同灭的实现错误）⇒ 该行事务中断，行保持活性，1 条 `import_row_error`（`batch_id=Rb`）。

| 问题 | 导入期 | 回滚期（`Rb`） |
|---|---|---|
| 属哪个集合 | 批次 3 时 `sr_H` ∈ `N_inserted` | `sr_H` ∈ **`N_fail_rb`** |
| 是否参与回滚 | — | **参与，但失败**（`is_active` 仍为 `true`） |
| 是否产生台账 | 否 | **是**：1 条 `import_row_error`，`batch_id=Rb` |
| 是否计入统计 | — | `N_fail_rb = 1`，`failed_count = 1`（**`Rb` 的**，不是 `R` 的） |
| SQL 复算 | — | 见下 |

```sql
-- R2c（结构断言 + 未验证，§5.4）
SELECT count(*) FROM data_quality_issue
 WHERE batch_id = 4 AND issue_type = 'import_row_error';   -- 期望 = failed_count(4)

-- ⭐ 三个计数的来源必须分别是：
--   |B|            ← len(import_batch[3].inserted_source_record_ids)
--   blocked_count  ← import_batch[4].blocked_count          （Rb）
--   failed_count   ← import_batch[4].failed_count           （Rb）
--   N_quar / N_noop ← 对 B 的集合基数（不是任何一行的计数列）
```

**判定**：⑥a G1 `100 = 1+0+99+0+0+0` ✓；⑥b G2 `|B| = 0 + |B|`，`|B| = (|B|−1)+0+1+0` ✓；R1 `|B|−1 = (|B|−0)−0−0−1` ✓。

### 4.7 反例 ⑦ 混合批次（唯一能同时压到全部集合的例子）

**回滚期**：`R = 3`，`|B| = 12`：

| 行 | 状态 | 步骤 | 集合 |
|---|---|---|---|
| 1, 2 | `duplicate_quarantine`，`inactive_in_batch_id=3` | 0 | `N_quar` |
| 3 | `source_absent`，`inactive_in_batch_id=4`，`last_batch_id=4` | 1 | `N_noop` |
| 4 | `locked=true`（派生子行） | 3 | `N_blocked` / `manual_edit_conflict` |
| 5 | `manual_edited_fields={geom}` | 3 | `N_blocked` / `manual_edit_conflict` |
| 6 | `last_batch_id=4`（第 4 批更新过） | 2 | `N_blocked` / `rollback_conflict` |
| 7 | 软撤写入失败 | 5 | `N_fail_rb` / `import_row_error` |
| 8–12 | 干净 | 6 | `N_rolled_back` |

| 问题 | 答案 |
|---|---|
| 属哪个集合 | `N_quar=2`，`N_noop=1`，`N_blocked=3`，`N_fail_rb=1`，`N_rolled_back=5`；`N_new=12`，`N_normal=10` |
| 是否参与回滚 | 只有 8–12 参与且成功；7 参与但失败；4/5/6 不参与（跳过）；1/2/3 不参与（不在作用集） |
| 是否产生台账 | 2（`manual_edit_conflict`）+ 1（`rollback_conflict`）+ 1（`import_row_error`）= 4 条；另有 2 条 `duplicate_external_id` 记在**批次 3**（不是 `Rb`） |
| 是否计入统计 | 见上；`Rb.status='partial'`（`blocked_count=3`，`failed_count=1`） |
| SQL 复算 | 见下 |

```sql
-- G2(i)：12 = 2 + 10
-- G2(ii)：10 = 5 + 3 + 1 + 1
WITH b AS (SELECT inserted_source_record_ids AS ids FROM import_batch WHERE batch_id=3)
SELECT count(*)                                                         AS n_new,
       count(*) FILTER (WHERE inactive_reason='duplicate_quarantine')    AS n_quar,
       count(*) FILTER (WHERE inactive_reason='batch_rolled_back'
                          AND inactive_in_batch_id = 3)                  AS n_rolled_back
  FROM source_record WHERE source_record_id = ANY((SELECT ids FROM b));
-- 期望 12 / 2 / 5   ⇒ n_normal = 10；10 − 5 = 5 = blocked(3) + fail_rb(1) + noop(1) ✓

-- R1：LHS 5 == (12−2) − 1 − 3 − 1 == 5
SELECT count(*) FROM source_record
 WHERE inactive_in_batch_id = 3 AND inactive_reason='batch_rolled_back';   -- 5
SELECT (array_length(inserted_source_record_ids,1)) FROM import_batch WHERE batch_id=3;  -- 12
SELECT blocked_count, failed_count FROM import_batch WHERE rollback_of_batch_id=3;      -- 3 / 1

-- R2：3 == 3
SELECT count(*) FROM data_quality_issue
 WHERE batch_id=(SELECT batch_id FROM import_batch WHERE rollback_of_batch_id=3)
   AND issue_type IN ('rollback_conflict','manual_edit_conflict');         -- 3

-- R2b：其余台账 >= 0（本批 1 条 import_row_error）⇒ 1 >= 0 ✓
-- R2c：1 == failed_count(Rb) = 1（结构断言 + 未验证）
```

**判定**：两组恒等式 + 四条断言全部在纸面成立。**但这是纸面推演，不是验证**——见 §11。

---

## 5. 四条断言 R1 / R2 / R2b / R2c

### 5.1 记号与取数来源（逐项钉死，防混用）

| 记号 | 取值来源（**唯一**） | 常见错用 |
|---|---|---|
| `|B|` / `N_new` | `len(import_batch[R].inserted_source_record_ids)` | ❌ 用 `input_row_count`（含失败行） |
| `N_quar` | `count(B 中 inactive_reason='duplicate_quarantine')`，即**集合基数** | ❌ 用 `import_batch[R].quarantined_count`（那是**导入期**的本批新产生隔离数；`Rb` 的该列恒 0） |
| `N_noop` | `count(B 中 非隔离 且 回滚前已失效)` | ❌ 用 `import_batch[R].skipped_count`（那是**导入期**的 `no_change` 数） |
| `blocked_count` | `import_batch[Rb].blocked_count` | ❌ 用 `import_batch[R].blocked_count`（导入期跳过数与回滚期无关） |
| `failed_count` | `import_batch[Rb].failed_count` | ❌ 用 `import_batch[R].failed_count`（导入期失败行根本不在 `B` 里，多减一次） |

### 5.2 R1：回滚成功行数

```sql
R1   count(source_record
           WHERE inactive_in_batch_id = :R
             AND inactive_reason = 'batch_rolled_back')
       == N_normal - N_noop - N_blocked - N_fail_rb
       == (|B| - N_quar) - N_noop - blocked_count - failed_count
```

**规范写法（一次查询算出 LHS 与 RHS，两者不互相代入）**：

```sql
-- :R  = 被回滚批次 ;  :Rb = 回滚批次（rollback_of_batch_id = :R 的那一批）
WITH b AS (
  SELECT coalesce(array_length(inserted_source_record_ids,1),0) AS n_new
    FROM import_batch WHERE batch_id = :R
), q AS (
  SELECT count(*) FILTER (WHERE sr.inactive_reason = 'duplicate_quarantine')     AS n_quar,
         count(*) FILTER (WHERE sr.inactive_reason IS NOT NULL
                            AND sr.inactive_reason <> 'duplicate_quarantine')   AS n_noop
    FROM source_record sr
   WHERE sr.source_record_id = ANY (
           SELECT inserted_source_record_ids FROM import_batch WHERE batch_id = :R)
), rb AS (
  SELECT blocked_count, failed_count
    FROM import_batch WHERE rollback_of_batch_id = :R AND status IN ('rolled_back','partial')
)
SELECT
  -- LHS：完全靠库状态独立算出，不看任何批次计数列
  (SELECT count(*) FROM source_record
    WHERE inactive_in_batch_id = :R
      AND inactive_reason = 'batch_rolled_back')                            AS lhs,
  -- RHS：(|B| − N_quar) − N_noop − blocked_count(Rb) − failed_count(Rb)
  (b.n_new - q.n_quar) - q.n_noop - rb.blocked_count - rb.failed_count      AS rhs,
  b.n_new, q.n_quar, q.n_noop, rb.blocked_count, rb.failed_count,
  (SELECT count(*) FROM source_record WHERE inactive_in_batch_id = :R
      AND inactive_reason = 'batch_rolled_back')
    = (b.n_new - q.n_quar) - q.n_noop - rb.blocked_count - rb.failed_count  AS r1_holds
FROM b, q, rb;
```

> **可执行性说明**：`array_length(x, 1)` 在空数组上返回 `NULL`，故用 `coalesce(...,0)`；`rb` 子查询取 `status IN ('rolled_back','partial')` 是为了排除"`running` 中的回滚批"。本查询**未在真库上跑过**（本轮无建库），属**结构级可执行式**，其返回值语义见 §11.2。

**三条必须同时写在 R1 旁边的注**：

1. **必须减 `N_quar`**：隔离行不在回滚作用集内，减漏则 R1 恒不成立。
2. **必须减 `N_noop`**：`N_noop` 不可能被本批回滚。反例（V0.2.2 QA C8 的原始反例，本版复算一致）：`|B|=10, N_quar=2, N_blocked=1, N_noop=1, N_rolled_back=5, N_fail_rb=1` ⇒ LHS=5、不减 `N_noop` 时 RHS=6。
3. **减的必须是 `Rb` 的 `blocked_count` / `failed_count`**：`R` 的这两个数是**导入期**的，与回滚无关（§3.6 混用方式 #1）。

> ⚠️ **R1 与 §3.4 判定顺序是同一套计数的两面**：顺序错 ⇒ 四类不再互斥 ⇒ `N_normal = N_rolled_back + N_blocked + N_fail_rb + N_noop` 破裂 ⇒ R1 随之不成立。**改一处必须验另一处。**

### 5.3 R2：回滚期台账行数与记录级跳过 1:1

```sql
R2   count(data_quality_issue
           WHERE batch_id = :Rb
             AND issue_type IN ('rollback_conflict','manual_edit_conflict'))
       == N_blocked
```

- **右式是 `N_blocked`，不是 `N_blocked + N_fail_rb`**。`N_fail_rb` 由 R2c 单独校验（V0.2.2 QA FAIL-3 取 (b)）。
- **`:Rb` 是回滚批次**，不是被回滚批。回滚期的台账记在 `Rb` 上，才能"回滚自己能被审核"。
- **1:1 成立的两个前提（本版新增写死）**：
  1. §3.4 步骤 2/3/4 命中即终止 ⇒ **一行最多一条**台账；
  2. §3.3.1 回滚期记账粒度为「行」（`field_name=''`）⇒ **一行恰好一条**。
  缺任一前提，R2 只能在"恰好单字段受保护"的例子下成立。
- ⛔ **不得为了让 R2 成立而新增或修改台账类型**（§5.5）。

### 5.4 R2b：补集

```sql
R2b  count(data_quality_issue
           WHERE batch_id = :Rb
             AND issue_type NOT IN ('rollback_conflict','manual_edit_conflict'))
       >= 0
```

**R2b 的注释（按 W11 建议改写）**：**补集**。`import_row_error` 虽在此集合内，但由 R2c 单独校验；其余成员是正常数据质量问题（`duplicate_external_id` / `derived_value_mismatch` / `truncated_slice_tail` 等）。`>= 0` 恒真，故 R2b **不做校验**，它的作用是**显式保留这个集合**，防止有人为了配平把质量问题归类成回滚问题。

### 5.5 R2c：`import_row_error` 与 `N_fail_rb`（**结构断言 + 未验证（U5）**）

```sql
R2c  count(data_quality_issue
           WHERE batch_id = :Rb
             AND issue_type = 'import_row_error')
       == N_fail_rb
```

> **⛔ 状态：结构断言 + 未验证（U5）**。
> 理由（如实）：暂存 `data_quality_issues.csv` **12,631 条（暂存原始）**台账中，`import_row_error` / `rollback_conflict` / `manual_edit_conflict` **三类全为 0 行**——**无任何脚本可在暂存态证伪 R2c，也无任何真实回滚批次可代入**。它在设计上必须存在（否则 `N_fail_rb` 无任何校验），但**不得写成已验证**。
> **⛔ R2 不得被连带降级**：R2 的判据自洽性（1:1 的记账粒度）是可以静态核对的，与被验数据无关；R1/R2/R2b 与 R2c **必须分两行记录状态**。

### 5.6 三条硬禁止（防"为了配平而改语义"）

| # | 禁止 | 为什么 |
|---|---|---|
| 1 | **不得新增或修改 `data_quality_issue.issue_type` 的任何值** | 冻结为 **19 值**（CORE §5.9）。回滚期只用 `rollback_conflict` / `manual_edit_conflict` / `import_row_error` 三个**既有**类型。为凑 R2 而新增类型，会让下一轮的"19 值"核对直接失败 |
| 2 | **不得把质量问题归类成回滚问题** | R2b 显式保留"正常质量问题"集合就是为了防这个 |
| 3 | **不得为了 R1 成立而修改 `|B|` 的构成**（如把 `failed_count` 加进去再减回来） | `|B|` 是**已落库集合**的基数。改它会让 A1 断言与 `inserted_source_record_ids` 失联 |

---

## 6. 人工修改保护的完整规则

### 6.1 两个保护位，粒度不同（沿用 V2.1）

| 位 | 粒度 | 语义 | 导入时 | 回滚时 |
|---|---|---|---|---|
| `locked = true` | 整行 | "这是我定的最终版，机器别碰" | 整行跳过 + 台账 | 整行不撤 + 台账 |
| `manual_edited_fields = {...}` | 字段 | "这几个字段是我改的，其它随源更新" | **逐字段**判定 | **整行不撤**（回滚是整行的一票否决） |

`locked` 蕴含"所有字段受保护"，所以不需要把字段名全塞进 `manual_edited_fields`。

> ⭐ **粒度不对称是本版新增写死的一条**：同一个保护位在导入期是字段级、在回滚期是行级。这不是不一致，是两种操作的语义不同——导入可以"只写这个字段"，回滚不能"只撤这个字段"。

### 6.2 唯一的写入判定：`should_write()`

```
def should_write(entity, field, new_value) -> Decision:
    # 1. 墓碑优先于一切
    if entity.merged_into_place_id is not None:   return SKIP_ROW('merged_tombstone')
    # 2. 整行冻结
    if entity.locked:                             return SKIP_ROW('row_locked')
    # 3. 人工创建的行永不被导入改写
    if entity.created_by == 'manual':             return SKIP_ROW('manual_created')
    # 4. 字段级冻结
    if field in entity.manual_edited_fields:      return KEEP_MANUAL('field_edited')
    # 5. 身份列永不被导入器改写
    if field in ('place_id','location_id','name_id','source_record_id','created_at','created_by'):
                                                  return KEEP('identity_column')
    return WRITE(new_value)
```

**三处调用方，必须是同一份实现**：upsert（`IMPORT_RULES_V2.1.1.md` §6）、回滚（本文件 §2.2）、人工解除保护后的重导（O7）。**不能有三份实现**——V2 的洞 1 正是"主路径有一份、回滚路径没有"。

**第 1 条必须排在最前**：`merged` 的行不一定 `locked`。若把墓碑判定放在 `locked` 之后，一个被合并的地点在源更新时会被直接改写墓碑行的字段，而 `merged_into_place_id` 不变 ⇒ 行仍是墓碑但内容已变，读路径 `COALESCE(...)` 把它解析到目标地点 ⇒ **用户看到目标地点的名字配上被改写的内容，没有任何报错**。

### 6.3 软清空

人工把一个字段清空（NULL）与"从未编辑过"必须区别对待，否则"我删掉了错误的坐标"会被下次导入原样填回。

- **清空字段** = 把字段名加入 `manual_edited_fields`（**即使值为 NULL**）。
- **恢复源值** = 显式触发"恢复为来源值"，从集合移除该字段名，再重导该记录或由 UI 从 `raw_payload` 就地回填。
- 该规则只适用于 `manual_edited_fields`，不适用于 `locked`（整行冻结时不存在"恢复单个字段"，只能先解锁）。

### 6.4 `is_preferred` 是保护位之外的第三类

`is_preferred` **永不**由导入器置 true。它**不参与** `should_write()`——导入器根本不写这一列。展示层的"按来源优先级选一个"只在渲染时生效（读 `data_source.display_priority`），**绝不写回**。理由：写回意味着系统替人做了裁决，且下次导入无法区分"人选的首选"与"系统猜的首选"。

### 6.5 保护冲突的记账

| 字段 | 导入期（字段级） | 回滚期（行级） |
|---|---|---|
| `issue_type` | `manual_edit_conflict` | `manual_edit_conflict` |
| `severity` | `info` | `info` |
| `field_name` | `<第一个被挡住的字段>`；整行/墓碑时 `''` | **恒 `''`** |
| `observed_value` | `'旧值 → 新值'`（截断 200 字符） | `'rollback blocked: <成因>'` |
| `expected_rule` | `'import would have overwritten a manually edited field'` | `'rollback would have revoked a protected row'` |
| `action_taken` | `needs_manual_review` | `needs_manual_review` |

**不静默跳过**：静默跳过会让"源已修正、我们没跟进"变成不可见状态。台账是唯一发现渠道。

**去重键**：`issue_fingerprint = md5(jsonb_build_array(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value))`（CORE §4.5，**六段含 `place_id`**，不含 `batch_id`）。重复发现 ⇒ `UPDATE`（`last_batch_id` 更新、`occurrence_count += 1`、`first_batch_id` 不变），**不 INSERT 第二行**。

> ⚠️ **与 R2 的潜在张力（必须写清）**：若同一行在**两次不同的回滚**中都被挡，第二次走 UPDATE 通道 ⇒ `batch_id` 仍是第一次的 `Rb` ⇒ R2 只在该批成立。**这是语义 A 的直接后果，不是缺陷**；本版不为此增设 `rollback_batch_ids[]` 列（那会让台账自我膨胀，与"不含 `batch_id`"的决策冲突）。登记为 U5 的一部分。

---

## 7. `rejected_by`：自动失效 vs 人工拒绝

| `rejected_by` | 产生 | 源端恢复后 | 导入器可否改 |
|---|---|---|---|
| `'auto'` | 源记录失效（O3/O4）时自动置 | **恢复 `staging`**，`rejected_by` 清 NULL | 可以（自动恢复） |
| **`'manual'`** | 人工拒绝（判定表第 5 行 / 场景 A） | **保持 `rejected`**，落 1 条 `manual_edit_conflict` 提示人工复核 | ⛔ **永远不可以 — 永不自动恢复** |

### 7.1 `rejected_by = 'manual'` 的"永不自动恢复"是绝对条款

```
rejected_by = 'manual'  ⇒  record_status 只能是 'rejected'
                        ⇒  任何自动流程（O1 / O2 / O3 / O4 / O5 / O7）都不得把它改成
                           'staging' 或 'published'
                        ⇒  唯一的解冻路径是**人工**把 rejected_by 置 NULL
                           （此时 record_status 由下一次导入重判，不由解冻动作直接置位）
```

**四条封锁线**：

| 路径 | 对 `rejected_by='manual'` 的行为 |
|---|---|
| O1 重新导入（源端恢复） | 保持 `rejected`；落 1 条 `manual_edit_conflict` 提示复核 |
| O2 更新 | 保持 `rejected`（该子行不是有效证据，不参与任何派生） |
| O3 源端消失 | 保持 `rejected`（已经拒绝了，不重复动） |
| O7 解除保护后重导 | 只解除 `locked` / `manual_edited_fields`；**不动 `rejected_by`**（两者是不同维度的保护位） |
| O5 批次回滚 | `rejected_by='manual'` 的派生行**已不参与**存活判定 ⇒ 回滚不碰它；若回滚会把它改成 `rejected_by='auto'`，那是**违规** |

> ⛔ **明确禁止**：「把所有 rejected 子行恢复成 staging」来绕过本条——那会一次性抹掉所有人工拒绝，正是本条要防的。
> **为什么必须有这两列**：没有 `rejected_by` 就无法区分"因源记录消失而自动 rejected"与"人工拒绝"。导入器只能在"恢复所有 rejected 子行"（覆盖人工决定，被明令禁止）与"一个都不恢复"（人工拒绝之外的合法数据永久丢失）之间二选一。**这不是"多存一列方便查询"，是规则可执行性的前提。**
> **与回滚的关系**：`rejected_by='manual'` 的行**永远不是有效证据** ⇒ 它不影响 `liveness='active'`；因此"回滚导致地点变成 `rejected`"与"人工拒绝导致地点变成 `rejected`"在**结果上可区分**（前者随源恢复自动回退，后者不会）。

### 7.2 四组场景的状态转换（沿用 CORE §5.6.1，逐字对齐）

| 场景 | 触发 | 子行 `auto` | 子行 `manual` | 地点 |
|---|---|---|---|---|
| **A** | 源仍 active，子行被人工拒 | — | 置 `rejected`+`manual`；该证据**无效** | 若仍有其他有效证据 ⇒ 不变；否则 `liveness∈FAILURE_SET` + `rejected`。**不落台账** |
| **B** | 源 `source_absent` 失效 | 置 `rejected`+`auto` | — | 若 ∃ 其他有效证据 ⇒ 保持；否则 `all_sources_absent` + `rejected` |
| **C** | 源重新出现（O1/O7 复活） | **恢复 `staging`**，`rejected_by` 清 NULL | **保持 `rejected`**；落 1 条 `manual_edit_conflict` | 若 ∃ 有效证据 ⇒ `'staging'`（不新建） |
| **D** | 源端重新导入 | 源已恢复 ⇒ 恢复 staging | **保持 rejected**，导入器不得改 | — |

---

## 8. 合并的可逆性（沿用 V2.1）

### 8.1 非破坏性合并

```
A.merged_into_place_id = B
A.record_status        = 'merged'
A.merge_review_ref     = <candidate_match.candidate_id>   -- NOT NULL（C06）
A.merged_at            = now()
```

**只有 A 行被改。** B 行不动，A 的 location / name 的 `place_id` **也不动**——它们仍然指向 A。读路径统一用 `COALESCE(merged_into_place_id, place_id)` 解析。

**为什么不动子行**：若合并时把 A 的 47 条名称的 `place_id` 改成 B，解除合并就无法还原——哪 47 条原本属于 A 就不知道了。现在的做法让解除合并只是一句 `A.merged_into_place_id = NULL; A.record_status = 'staging'`，**零信息损失**。

### 8.2 解除合并的前置条件

| 条件 | 不满足时 |
|---|---|
| `merge_review_ref` 指向的候选仍存在且 `status='confirmed'` | 需先恢复候选状态 |
| A 行没有 `locked` | 先解锁 |
| 没有任何 `import_batch` 处于 `running` | 等批次结束（同 §2.5 B3） |

**解除合并本身也要留痕**：写一条 `data_quality_issue(issue_type='manual_edit_conflict', field_name='merged_into_place_id', observed_value='B → NULL', action_taken='needs_manual_review', resolution_note='unmerge')`。合并与解除合并都是人做的决定，两者都要有记录。

### 8.3 链深规则

`merged_into_place_id` **只允许一层**。合并时若目标 B 自身已被合并，直接把 A 指向 B 的最终目标（路径压缩）。

巡检 SQL（必须返回 0 行）：

```sql
SELECT a.place_id FROM historical_place a
  JOIN historical_place b ON a.merged_into_place_id = b.place_id
 WHERE b.merged_into_place_id IS NOT NULL;      -- 期望 0 行
```

**本轮实测：0 行**（`record_status='merged'` 的记录数为 0，尚未发生任何合并）。**这是"无数据可验"，不是"已验证"。**

---

## 9. 禁止 DELETE（沿用 V2.1）

| 表 | 失效时 | 不做的 |
|---|---|---|
| `source_record` | `is_active=false` + `inactive_reason` + `inactive_at` + `inactive_in_batch_id` | 不 DELETE |
| `historical_place_location` / `_name` | `record_status='rejected'` + `rejected_by` | 不 DELETE |
| `historical_place` | `record_status='rejected'` 或 `'merged'` | 不 DELETE |
| `candidate_match` | `status='superseded'` / `'rejected'` | 不删行 |
| `data_quality_issue` | `resolved=true` + `resolved_at` + `resolver` + `resolution_note` | 不删行 |

**唯一例外**：本批次刚插入、从未被任何人工操作引用、且回滚操作明确记录的行——即使这种，默认也走软删。物理 `DELETE` 需要一个显式运维开关，默认关闭。

> **与回滚的关系**：回滚**不删行**，只改 4 个状态列（`is_active` / `inactive_reason` / `inactive_at` / `inactive_in_batch_id`）。这是 R1 的 LHS 能靠"查状态"复算的前提——若删行，LHS 恒为 0 而 RHS 不为 0。

---

## 10. 与 V2.1 的差异

| 项 | V2.1（2.1.0） | V2.1.1 | 为什么 |
|---|---|---|---|
| 回滚统计集合 | 一组（`N_normal = N_rolled_back + N_blocked + N_failed + N_noop`） | **两组**（G1 导入 / G2 回滚），各含 2 行恒等式 | D4-5：一组集合无法同时表达"导入的账"与"回滚的账" |
| 判定顺序 | 步骤 1 = 作用集，步骤 2 = quarantine | **步骤 0 = quarantine，步骤 1 = 其余失效** | 洞 4：隔离行被提前截走，同时进 `N_quar` 与 `N_noop` |
| `N_failed` | 单一名 | **`N_fail_import` / `N_fail_rb`** | D4-7：导入期失败行不落库，回滚期失败行在库 |
| `blocked_count` / `failed_count` 的取数批 | 未写明 | **恒取 `Rb`** | R1 的常见错用（§3.6 #1） |
| 回滚期台账粒度 | 未写明（隐含字段级） | **行级，`field_name` 恒 `''`** | R2 的 1:1 前提 |
| BLOCK_OP | 4 种含"墓碑"与"`created_by='manual'`" | **4 种全为操作级前置（B1–B4）**；墓碑与人工创建收为记录级跳过 | 记录级属性不得升格为操作级（G8-03 本意） |
| 回滚统计的台账 `batch_id` | 未写明 | **记在 `Rb`**（回滚批次本身） | 让回滚可被独立审核；R2 的 `:Rb` 有明确所指 |
| `rejected_by='manual'` | 分散在场景 A/C/D | **单列一条绝对条款（§7.1）+ 五条封锁线** | 防"批量恢复 rejected 子行"绕过 |
| 反例 | 无 | **7 种，每种 5 件事**（§4） | D4-5 的硬要求 |
| `N_noop` 的来源 | "本批之前已失效"（未说明怎么产生） | **两种具体来源 + 与 `N_quar` 可同时非零** | 洞 4 的触发条件必须写明 |
| 施工验证清单 | 无 | **§11，U5/U12/U13/U14 如实保留，不写 PASS** | 验收判据 |

---

## 11. 施工验证清单（**不得写成 PASS**）

> **本节的每一项状态都是「未验证 / 未解决」。本文件不宣布通过，也不为任何一项预置通过结论。**
> 本轮性质：**设计文档**，无 DDL、无建库、无导入 ⇒ 以下全部无运行期证据。

### 11.1 V0.2.2 未解决 / 未验证清单（逐项如实保留，仅列与本文件相关的）

| # | 项 | 为什么本文件验不了 | 何时解决 |
|---|---|---|---|
| **U5** | **7 类操作（含判定表第 0 行）能否真正拦住** | 暂存 **0 个回滚批次**、0 行 `locked`、0 行 `merged`、0 行 `rejected` ⇒ §4 的 7 个反例**全部是纸面推演**，无一有真实数据可代入 | 施工后造 7 个测试批次 |
| **U12** | `v_place_time_span` 加 `sr.is_active` 后 17,469 的变化 | 回滚会把 `is_active` 改 false ⇒ 影响时间跨度；但建视图前无法复算 | 建视图后复算 |
| **U13** | `rejected_by` 两列是否误伤既有写入路径 | 回滚路径也要写 `rejected_by`（`auto`）；暂存 0 条 rejected ⇒ 无数据 | 建库后空跑导入 + 造 1 个回滚批 |
| **U14** | 四场景 A–D 的端到端行为 | 暂存 0 条 rejected / merged / locked | 施工后造影子批 |
| U15 | `STOP_AUTO` 的真实触发率 | 当前 0 例 | 下一次源更新 |
| U16 | `raw_record_index` 的真实语义 | 与回滚无直接关系，但影响 ordinal 定序 | 下一轮 |
| U18 | `candidate_match` 总数 | 与本文件无关（不参与回滚统计） | 需 Owner / team-lead 裁定 |
| U19 | `issue_fingerprint` 是否同步改为 sha256 | 本文件按 ALG-1 保持 md5 | 需 team-lead 转 Owner 裁定 |

### 11.2 本文件的断言状态（**分两行记录，R2 不连带降级**）

| 断言 | 内容 | 状态 |
|---|---|---|
| **G1 恒等式** | `input_row_count = N_fail_import + N_quar + N_inserted + N_updated + N_noop + N_blocked` | **结构自洽（代数已核）；未验证**（需真实导入批次；暂存七张 CSV 是**输入**，不是批次台账） |
| **G2 恒等式** | `N_new = N_quar + N_normal`；`N_normal = N_rolled_back + N_blocked + N_fail_rb + N_noop` | **结构自洽（§3.5 已给代数证明）；未验证**（需真实回滚批次 U5） |
| **R1** | 回滚成功行数 == `(N_new − N_quar) − N_noop − blocked_count − failed_count` | **结构自洽（代数代入已核，非运行期验证）；未验证**：需真实回滚批次（U5） |
| **R2** | 回滚期台账行数 == `N_blocked` | **结构自洽（仅代数/规则核对，非运行期验证）**（1:1 的两个前提已写死，§5.3）；**未验证**：需真实回滚批次（U5）。**R2 未被降级** |
| **R2b** | 补集 `>= 0` | 恒真，**不做校验**（设计如此） |
| **R2c** | `import_row_error` 条数 == `N_fail_rb` | **结构断言 + 未验证（U5）**：暂存 12,631 条（暂存原始）台账中 `import_row_error` / `rollback_conflict` / `manual_edit_conflict` **三类全为 0 行**，无数据可验 |
| **S2** | 回滚作用集不含 `duplicate_quarantine` 行 | **结构自洽（仅代数/规则核对，非运行期验证）**（§3.4 步骤 0）；**未验证**（U5） |
| **S1** | `duplicate_quarantine` 行不得派生任何子行 | **结构自洽（仅代数/规则核对，非运行期验证）**；**未验证**（真实隔离批需施工后） |
| **rejected_by 永不自动恢复** | §7.1 五条封锁线 | **结构自洽（仅代数/规则核对，非运行期验证）**；**未验证**（U14：暂存 0 条 `rejected_by='manual'`） |

### 11.3 本文件新增待验项

| # | 项 | 为什么需要验 |
|---|---|---|
| **V-7（本版新增）** | **`inactive_in_batch_id` 在三种失效原因下的取值规则** | 冻结的 R1 SQL 写 `inactive_in_batch_id = :R`（`:R` = 被回滚批），只有在「`batch_rolled_back` ⇒ 写入**被回滚批**的 id」时才成立。而 `duplicate_quarantine` 写"产生隔离结论的批"、`source_absent` 写"发现消失的批"。**三值规则此前从未被逐字写下** ⇒ 本文件 §3.4 步骤 6 首次钉死，属**补全项不是新设计**，待 QA 复算确认 |
| **V-8（本版新增）** | **回滚期台账行级记账与导入期字段级记账并存**是否会被实现成一套 | 若实现者共用一份"字段级"记账代码，R2 会在"一行多字段受保护"时直接破（3 ≠ 1）。需在施工后造一个"一行 3 字段受保护"的回滚批验证 |
| **V-9（本版新增）** | **同一行在两次不同回滚中都被挡**时 R2 的成立范围 | 台账走 UPDATE 通道 ⇒ `batch_id` 停留在第一次的回滚批 ⇒ R2 只在第一次成立。本版不增设 `rollback_batch_ids[]`（与"指纹不含 `batch_id`"冲突），登记待裁定 |
| **V-10（本版新增）** | §2.5 把 V0.2.1 §2.2.2a 的「墓碑 / `created_by='manual'` = BLOCK_OP」收为记录级跳过 | 这是对 V0.2.1 三处互相冲突表述的裁定落地。**需 team-lead 复核该裁定是否与 Owner 原意一致**（本文件按 team-lead 任务书执行，未自行改变裁定） |

---

## 12. 一页速查

```
导入时：should_write() 五道判定
        ├ merged_into_place_id 非空 → 整行跳过 + 台账（manual_edit_conflict）
        ├ locked                     → 整行跳过 + 台账
        ├ created_by='manual'        → 整行跳过 + 台账
        ├ 字段在 manual_edited_fields → 该字段保留人工值 + 台账
        └ 其余                        → 写入（身份列除外）

导入结果的账（G1）：input_row_count
        = 失败未落库 + 本批隔离 + 活性新增 + 更新 + 无变化 + 记录级跳过

回滚时：六步判定（顺序不可换）
        步骤 0  quarantine            → N_quar       ─ 先判，否则被步骤 1 截走
        步骤 1  其余历史失效           → N_noop
        步骤 2  last_batch_id 不符     → N_blocked    + rollback_conflict
        步骤 3  保护位                → N_blocked    + manual_edit_conflict
        步骤 4  墓碑                  → N_blocked    + rollback_conflict
        步骤 5  写入失败               → N_fail_rb    + import_row_error
        步骤 6  其余                  → N_rolled_back
        全过 → is_active=false + reason='batch_rolled_back'
        任一不过 → 该行不动，批次记 partial

回滚结果的账（G2）：|B| = 隔离 + 其余
                       其余 = 撤成功 + 记录级跳过 + 写入失败 + 此前已失效

四条断言：R1 ↔ N_rolled_back   R2 ↔ N_blocked   R2b = 补集   R2c ↔ N_fail_rb（未验证）
取数纪律：|B| / N_quar / N_noop 靠集合复算；blocked_count / failed_count 恒取「回滚批次」
台账纪律：回滚期一行一条（field_name=''）；导入期一字段一条
禁止：新增/修改 issue_type（冻结 19 值）｜删行｜为配平改 |B|

人工保护：locked（整行）｜manual_edited_fields（字段；清空也是编辑）
          rejected_by='manual' ⇒ 永不自动恢复（绝对条款，五条封锁线）
合并：只改 A 一行，子行 place_id 不动 ⇒ 解除合并零信息损失
任何时刻：不 DELETE
```

---

## 13. 收尾声明

1. 本文件**不宣布通过**，也不为任何一项预置通过结论。§11 全部为「未验证 / 未解决」。
2. 本文件**未修改** `CORE_DATA_MODEL_V2.1.1.md`、`IMPORT_RULES_V2.1.1.md`、`FIELD_MAPPING_V2.1.1.csv`、`DATA_PROVENANCE_V2.1.1.md`（四份已冻结）。
3. 本文件**未新增**任何 `data_quality_issue.issue_type` 值（冻结 19 值），**未新增**任何表或列。
4. 本文件**未**产生 DDL / Migration / 建库 / 导入 / Git 操作。
5. §11.3 的 V-7 / V-8 / V-9 / V-10 是本文件编制过程中**新发现的不一致与待裁定项**，均未自行裁定为"已解决"。
