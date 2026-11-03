# CHANGELOG ↔ CORE 逐字一致性复核报告

**性质**：交付物之间的**交叉核对**（只读）。**不改任何交付物**，也不改 V0.2.2 / V0.2.1 原文。
**复核人**：software-architect-6（架构）｜**日期**：本轮
**方法**：机械比对脚本 `_build/diff_changelog_core.py`（可重跑），**不靠目测**。

---

## 0. 核验基准（冻结）

| 文件 | 字节 | 行（`LF` 计数） | `sha256[:16]` |
|---|---:|---:|---|
| `CORE_DATA_MODEL_V2.1.1.md` | 145,369 | 1,693 | `c0422f679ceb88c3` |
| `V2.1_TO_V2.1.1_CHANGELOG.md` | 141,838 | 1,243 | `98199d279cc563d9` |

> **行数一律 `LF` 计数**（`b.count(b'\n')`），不用"文本行数"口径（team-lead 已定为规则）。文件身份以 `sha256[:16]` 为准，行数只作参考。

## 0.1 复核范围与选用的机械判据

| 范围 | CORE 侧 | CHANGELOG 侧 | 机械判据 |
|---|---|---|---|
| §C 表结构与列 | §5.0 列变更清单（26 行）+ §5.4–§5.9 逐表列定义 | §C.1–§C.9 | 逐行取列名 token 做包含判定；类型串做**逐字**包含判定 |
| §D 约束 | 附录 A（C01–C29，29 行）+ §4.3–§5.10 表内约束 | §D.1（计数）+ §D.2（29 行） | 编号正则集合差 + 约束文本/状态单元格逐字比对 |
| §E 视图 | §5.10.1 / §5.10.2 / §5.10.3 | §E.1–§E.4 | 「逐列标题表」解析列名与顺序；定序键/过滤串逐字包含 |
| §G 数字 | §9.2（N01–N18）+ §5.5/§6/§7 的实测数 | §G.1（N01–N18）+ §G.2（16 条作废旧数） | 按行提取数字 token 集合，做对称差 |

---

## 1. 结论（一句话）

> **CHANGELOG 与 CORE 在"机制层"（约束编号全集、有效计数、三视图列与列序、定序键、过滤条件、N01–N18 数字）逐字一致，无一处实质冲突；**
> **差异共 9 条，全部是"详略/口径/可读性"层面：CHANGELOG 侧 3 条欠完整（其中 2 条会让施工方少建 DEFAULT/漏一列）、CORE 侧 1 条不可直接执行（C19 用"3 值"占位）、纯口径差 5 条。**
> **⇒ 不构成"两份交付物互相矛盾"，但 §2 的 A-1 / A-2 / B-1 三条建议在下一轮合并修订时一并处理。本报告不宣布通过。**

---

## 2. 差异统计（四类）

| 类别 | 条数 | 编号 |
|---|---:|---|
| **① CHANGELOG 错 / 欠完整** | **3** | A-1、A-2、A-3 |
| **② CORE 错 / 欠完整**（只报告不改） | **1** | B-1 |
| **③ 纯口径差**（两边都对，但会被下轮读成矛盾） | **5** | C-1、C-2、C-3、C-4、C-5 |
| **④ 无差异**（机械核对通过项） | **10 项** | D-1 … D-10（见 §4） |

> 附：另有 **1 条"CHANGELOG 更完整"** 的情形（A-4），不计入差异，仅登记以免被反向误判。

---

## 3. 逐条差异

### ① CHANGELOG 错 / 欠完整（建议改 CHANGELOG）

#### A-1｜§C.5 未给三个伴生列的类型与约束

| 项 | 内容 |
|---|---|
| **CHANGELOG 位置** | **L337**（§C.5「修改后（V2.1.1）」行）："② 新增 `first_batch_id` / `last_batch_id` / `occurrence_count`（+ C23/C24）"——**只有列名，无类型、无 NULL、无 DEFAULT、无 FK** |
| **CORE 位置** | **§5.0 L310–L312**（逐列给出类型）＋ **§5.9 表 L830–L832** |
| **差异** | CORE：`first_batch_id` = `bigint` **FK → `import_batch`**；`last_batch_id` = `bigint` FK → `import_batch`；`occurrence_count` = **`integer NOT NULL DEFAULT 1`**。CHANGELOG 三项**全部缺失** |
| **影响（施工级）** | ① 按 CHANGELOG 建列 ⇒ `occurrence_count` 少了 `NOT NULL DEFAULT 1` ⇒ 首次 `INSERT` 若不显式赋值会失败或被建成可空，**C23 `CHECK (occurrence_count >= 1)` 在可空列上对 NULL 恒真 ⇒ 约束失效**；② 少了 FK ⇒ `first_batch_id` / `last_batch_id` 悬空引用无人拦；③ 与同文件 §C.1 的详尽度不一致（§C.1 对 4 个新增列都给了类型） |
| **建议改哪边** | **改 CHANGELOG**（§C.5 的「修改后」行补三个类型串）。CORE 不动——CORE 已经是逐列给类型的正确形态 |

#### A-2｜全文 0 次出现 `location_grain`

| 项 | 内容 |
|---|---|
| **CHANGELOG 位置** | **全文 0 命中**（`grep -c location_grain` = 0） |
| **CORE 位置** | **§5.0 L316**（`data_dataset.location_grain`｜**不变**｜V2 既有列）；**§5.2 保留列表 L393** |
| **差异** | CORE §5.0 把 `place_grain` 与 `location_grain` **并列两行**（一行"不变（⛔ 非新增）"、一行"不变"），CHANGELOG 只在 §B.5 / §C.9 写了 `place_grain`（且是"V2 既有列、不得写成新增"的正确写法），`location_grain` **一次未提** |
| **影响** | §5.0 的 26 行里，CHANGELOG 覆盖 **25 行**。下轮若做"§5.0 逐行对账"，`location_grain` 会显示为"CHANGELOG 漏项"；更实际的风险是：**只写 `place_grain` 不写 `location_grain`，会让读者以为后者不存在或已删**，而它是建点/建位置两条 grain 判据的另一半（`per_record` / `per_parent_external_id` 同域） |
| **建议改哪边** | **改 CHANGELOG**：在 §C.9 的 `place_grain` 注里补一句"`location_grain` 同为 V2 既有列、V2.1 收敛 2 值、本版**不变**（CORE §5.0 L316）"。CORE 不动 |

#### A-3｜§E.3 未逐列列出 `v_place_time_span` 的 10 列；`staging_evidence_rows` 全文 0 命中

| 项 | 内容 |
|---|---|
| **CHANGELOG 位置** | **§E.3 L589–L622**：只给"对外 **10 列**（新增 `child_rows_total` / `valid_child_rows` / `all_children_rejected`）"，**未逐列枚举** |
| **CORE 位置** | **§5.10.3 列清单（10 列）L1197–L1210**（逐列 1–10） |
| **差异** | CORE 10 列：`place_id` / `span_from_astro` / `span_to_astro` / `from_evidence_rows` / `to_evidence_rows` / **`staging_evidence_rows`** / `valid_child_rows` / `child_rows_total` / `derivation_kind` / `all_children_rejected`。CHANGELOG 以"列清单"形式只在 §E.4 列了**新增的 3 列**；其余 5 列（`span_from_astro` / `span_to_astro` / `from_evidence_rows` / `to_evidence_rows`）仅出现在 T1–T4 断言块里（无 `backtick` 列名形式），**`staging_evidence_rows` 全文 0 命中** |
| **影响** | ① 第 6 列 `staging_evidence_rows` 在 CHANGELOG 无任何痕迹 ⇒ 若施工方以 CHANGELOG 为清单建视图，会**少建一列**（且 T4 的 `derivation_kind` 计数校验不受影响，**不会报错**——静默缺列）；② CHANGELOG 内部详尽度不一致：§E.1 对 11 列逐列列出（与 CORE 完全一致，含顺序），§E.3 只给总数 + 3 个新增列 |
| **建议改哪边** | **改 CHANGELOG**：§E.3 补 10 列逐列清单（照抄 CORE §5.10.3 的 1–10 行）。CORE 不动 |

### ② CORE 错 / 欠完整（**只报告，不改**）

#### B-1｜CORE 附录 A 的 C19 用「`IN (3 值)`」占位，与 CORE §5.4 的自展开写法不一致，且不可直接执行

| 项 | 内容 |
|---|---|
| **CORE 位置（简写处）** | **附录 A L1596**：`C19 | CHECK (inactive_reason IS NULL OR inactive_reason IN (3 值)) | source_record | 保留` |
| **CORE 位置（展开处）** | **§5.4 约束表 L511**：`CHECK (inactive_reason IS NULL OR inactive_reason IN ('source_absent','batch_rolled_back','duplicate_quarantine'))` |
| **CHANGELOG 位置** | **§D.2 L470**：**展开了三个字面值**（与 CORE §5.4 一致） |
| **差异** | 同一 CORE 文件内两处写法不同：§5.4 可执行、附录 A 不可执行（`IN (3 值)` 不是 SQL）。CHANGELOG 采信了可执行的那一处 |
| **影响** | 附录 A 是"约束全集"的权威落点表；若有人从附录 A 复制 C19 建表，语句**直接语法错误**。此处 CORE 与 CHANGELOG 的差异**不是矛盾**，而是 CHANGELOG 更正确 |
| **建议改哪边** | **建议改 CORE**（附录 A L1596 改为展开三字面值），但**本报告不改**——CORE 已冻结在 `c0422f679ceb88c3`。列入下轮 CORE 修订项 |

#### A-4（不计入差异，仅登记）｜CHANGELOG 比 CORE 多给一个类型词

| 项 | 内容 |
|---|---|
| **CHANGELOG L261** | `parent_external_id` 的 V2.1.1 状态写 **`` `text **NOT NULL**` ``** |
| **CORE §5.4 L490** | 只写 **`NOT NULL`**（`text` 是 V2.1 原列类型，CORE 未重复） |
| **判定** | **非冲突**：CHANGELOG 更明确。登记以防被反向读成"CHANGELOG 自创类型" |

### ③ 纯口径差（两边都对；不处置则下轮必被判矛盾）

#### C-1｜约束状态用词不同，根因是**基线不同**（4 条）

| 编号 | CORE 附录 A（**以 V0.2.1 为基线**） | CHANGELOG §D.2（**以 V2.1 为基线**） | CORE 行 / CH 行 |
|---|---|---|---|
| **C01** | 保留（**五段**） | **调整** | L1578 / L452 |
| **C04** | 保留 | **新增（本版）** | L1581 / L455 |
| **C10** | 保留（替换两条部分索引） | **新增（本版）** | L1587 / L461 |
| **C13** | 保留（改名后） | **调整（改名后）** | L1590 / L464 |

> **两边都对**：相对 V0.2.1，C01 已是五段、C04/C10 已存在 ⇒ "保留"；相对 V2.1（四段、无 `grain_key`、无 `issue_fingerprint`）⇒ "调整 / 新增"。**但两份交付物对同一条约束给出两个状态词，任何"跨文档一致性"脚本都会判 FAIL。**
> **建议**：在 **CHANGELOG §D.2 表头补一行基线声明**（成本最低，一处解决 4 条）：
> 「本表状态以 **V2.1** 为基线（调整 / 新增 = 相对 V2.1）；CORE 附录 A 的状态以 **V0.2.1** 为基线，故 C01/C04/C10/C13 处用词不同，**两者不矛盾**。」
> **不建议**改 CORE 附录 A——它的基线是"相对 V0.2.1 的约束演进"，改动会牵连 V0.2.2 的行号引用。

#### C-2｜C27 / C28 的"落点"列使用两套节号

| 项 | 内容 |
|---|---|
| **CORE L1604–L1605** | 落点写 `§5.10.2 真值表` |
| **CHANGELOG L478–L479** | 落点写 `§E.2 真值表`（CHANGELOG 自身节号） |
| **判定** | 两处都指向同一张真值表，但编号体系不同（CORE 的 §5.10.2 = CHANGELOG 的 §E.2） |
| **建议** | CHANGELOG §E.2 标题处补一句"（= CORE §5.10.2）"，或在 §D.2 表头一并声明节号映射。**不建议**改 CORE |

#### C-3｜N14 行多一个数字 token（引用号，非数据）

| 项 | 内容 |
|---|---|
| **CORE §9.2 N14** | `17,469 / 19,039`；差列 `—`；说明"待复算" |
| **CHANGELOG §G.1 N14** | 同数字，说明列多 **`U12`** ⇒ 数字 token 差集 = `{'12'}` |
| **判定** | **无实质差异**（`12` 来自未验证项编号 `U12`）。机械比对会报"数字不一致"，**属判据噪声**，建议比对脚本把 `U\d+` / `V-\d+` 引用号先剔除 |

#### C-4｜`1,162` 出现次数：**2 次**（同一行），不是 1 次

| 项 | 内容 |
|---|---|
| **CHANGELOG L1191** | 同一行内两次：①「本文件编制中被转报为 **1,162**」②「**1,162** 登记为无出处数字，不得引用」 |
| **team-lead 回报** | "`1,162` 出现 1 次（登记项）" |
| **判定** | 计数口径差（按"出现次数"=2，按"登记条目"=1）；**内容处置正确**（已定为无出处数字） |

#### C-5｜`rejected_by` 类型表述字符不同、语义相同

| 项 | 内容 |
|---|---|
| **CORE §5.6/§5.7** | `` `text` 可空，CHECK IN (`auto`,`manual`) `` |
| **CHANGELOG §C.3** | `` `rejected_by text`（可空，CHECK IN `auto` / `manual`） `` |
| **判定** | 语义一致（`text`、可空、2 值域）。差异仅在括号与斜杠空格。**不建议改任何一边**，登记以免被"逐字比对"判 FAIL |

---

## 4. 无差异（机械核对通过项）

| # | 核对项 | 结果 |
|---:|---|---|
| **D-1** | CORE §5.0 的 **26 行**列变更清单 → CHANGELOG 覆盖 | **25 / 26 命中**（唯一缺口 = `location_grain`，见 A-2）；其余 25 行的列名在对应 §C.x 小节内均出现 |
| **D-2** | 约束编号 **C01–C29** | CORE 附录 A **29 行** / CHANGELOG §D.2 **29 行**；**无缺失、无重复、无多余**（集合差两侧皆空） |
| **D-3** | 约束**文本**逐字 | 29 条中 **27 条逐字相同**；2 条为 CORE 简写（C19 见 B-1）／CHANGELOG 加举例（C28，语义一致） |
| **D-4** | 有效约束计数 | `29 − 1（废除 C02） − 1（双编号 C18） = 27 = 24 可落库 + 3 断言级/键级`；`V0.2.1 的 22`、`C01–C26 旧值` 说明——**两文件逐字一致** |
| **D-5** | `v_place_evidence` 11 列 | **列名与顺序 11/11 完全一致**（`place_id` → `is_canonical_row`） |
| **D-6** | 定序键 ⓿①②③④⑤ | **6 键逐字一致**（含 `NULLS LAST`、`IS DISTINCT FROM 'rejected'`、`coalesce(child_row_id, 0)`） |
| **D-7** | `liveness` 8 值 | **8/8 全部命中**，无多余值；`FAILURE_SET` 定义一致 |
| **D-8** | 视图过滤条件 | `<> 'rejected'`、`sr.is_active`、`count(e.place_id)`、`GROUP BY e.place_id` —— **两侧全部命中且语义一致**（`< > 'rejected'` 而非 `= 'published'`） |
| **D-9** | N01–N18 权威数字 | **18/18 行齐全**；数字 token 逐格一致（唯一差 = N14 的 `U12` 引用号，见 C-3） |
| **D-10** | 许可列名 | `data_dataset` **9 列** + `data_source` **2 列**，**11 个列名逐一命中**（各出现 2–9 次，均在【留痕】语境）；关键类型串 `text NOT NULL DEFAULT ''`、`integer NOT NULL DEFAULT 0`、`GENERATED ALWAYS AS md5(jsonb_build_array(...))`、五段 UNIQUE 全串、`UNIQUE (dataset_id, grain_key)` **逐字一致** |

**§G.2 的 16 条作废旧数的落点核对**：`2,233` / `1,585` / `1,058` / `53,133` / `1,505` / `1,570` / `16 种 → 11 种` / `18,091` / `3,294` / `646` / `19,039` 等在 CORE 中**有对应落点且数值一致**；`327` / `1,564` / `1,562` / `96.1` / `12,833` / `18,093` / `644` / `16,389` / `1,164` / `1,162` 在 CORE 中**无落点**——这些是 **V2 / V2.1 / V0.1 独有的旧数**，CORE 不收录它们的作废前值属**预期行为**，不是漏项（CHANGELOG §G.2 的"出处"列已逐条标注 V2 §12 / V2.1 §7.2 / V0.1 等来源）。

---

## 5. 处置建议汇总（供 team-lead 决定，本报告不动任何文件）

| 优先级 | 条目 | 建议动作 | 涉及文件 |
|---|---|---|---|
| **高** | **A-1** | CHANGELOG §C.5 补 `first_batch_id` / `last_batch_id` / `occurrence_count` 三个类型串 | CHANGELOG |
| **高** | **A-3** | CHANGELOG §E.3 补 `v_place_time_span` 10 列逐列清单（尤其 `staging_evidence_rows`） | CHANGELOG |
| **中** | **A-2** | CHANGELOG §C.9 补一句 `location_grain` 不变 | CHANGELOG |
| **中** | **C-1** | CHANGELOG §D.2 表头加**基线声明**（一处解决 4 条状态用词差异） | CHANGELOG |
| **低** | **B-1** | CORE 附录 A L1596 的 C19 展开三字面值（**须先解冻 CORE**） | CORE |
| **低** | **C-2** | CHANGELOG 注明 `§E.2 = CORE §5.10.2` | CHANGELOG |
| **无需** | **A-4 / C-3 / C-4 / C-5** | 仅登记；建议比对脚本剔除 `U\d+` / `V-\d+` 引用号以减少噪声 | — |

> **若本轮不解冻 CHANGELOG**：以上 6 条均为"详略/口径"问题，**不影响三视图 SQL 与 29 条约束的正确性**；但 A-1 / A-3 会让"只读 CHANGELOG 施工"的人**少建 1 个 DEFAULT + 少建 1 个视图列**，建议至少把这两条传达到施工侧。

---

## 6. 复核边界（如实）

- 本次是**机械比对 + 人工判读差异性质**，覆盖 §C / §D / §E / §G 四块；**未覆盖**：§F（导入/隔离/回滚规则）与 `IMPORT_RULES` / `ROLLBACK` 的交叉一致性（不在本次授权范围）、§I 的 10 项矛盾与 V0.2.2 原文的逐字核对、ER 图的图注与 CORE 的一致性。
- 比对判据是"token 包含 / 单元格逐字"，**不能发现语义级错误**（例如某条约束文本两边完全相同但**本身写错**）。这类问题属 QA 断言与施工验证的范围。
- **本报告不宣布通过。** 它只回答"CHANGELOG 与 CORE 是否逐字一致"，不回答"设计是否正确"。

---

# 7. 修订后复测（team-lead 裁定解冻 CHANGELOG，5 处只增小修后）

**修订后 CHANGELOG 快照**：150,397 B / **LF 1,294** / `sha256[:16] = 5c80f224876983de` / mtime 2026-11-03 11:06:59（初版为 141,838 B / 1,243 / `98199d279cc563d9`）
**复测脚本**：`_build/diff_changelog_core.py`（`LOCK` 已更新为 CORE `34ff192009a5d2dd`、CHANGELOG `5c80f224876983de`）

## 7.1 五处落点

| 编号 | 落点（修订后行号） | 内容 |
|---|---|---|
| **A-1** | **L343**（§C.5「修改后」行）＋ **L353–L360**（新增「逐列清单」表，4 行）＋ L361/L362 两条 ⛔ | 三个伴生列补类型：`first_batch_id` `bigint` FK（**可空**）、`last_batch_id` `bigint` FK（**可空**）、`occurrence_count` **`integer NOT NULL DEFAULT 1`** |
| **A-2** | **L446**（§C.9 的 `place_grain` 注之后） | 新增 `location_grain` 条：同为 V2 既有列、本版**不变**、CHECK IN 2 值、CORE §5.0 第 24 行 |
| **A-3** | **L632–L646**（§E.3 新增「列清单（10 列，逐列）」）＋ L647–L648 两条 ⛔ | 10 列逐列抄自 CORE §5.10.3；**`staging_evidence_rows` 落在第 6 行（L641）** |
| **C-1** | **L469–L475**（§D.2 表头之上） | 基线声明：本表以 **V2.1** 为基线、CORE 附录 A 以 **V0.2.1** 为基线 ⇒ C01/C04/C10/C13 用词差异源于基线，非冲突 |
| **C-2** | **L523**（§D.3 六要素表之后） | 节号对照：CORE `§5.10.2` = 本文 `§E.2`，同一张真值表 |
| 附带 | **L1245**（§J.3 新增第 7 项） | 登记 `first_batch_id` 的 NULL 性口径冲突（见 7.3） |

## 7.2 复测结果（对 CORE `34ff192009a5d2dd`）

| 项 | 修订前 | 修订后 |
|---|---|---|
| §5.0 列变更清单覆盖 | 25 / 26（缺 `location_grain`） | **26 / 26，缺口 0** ✅ |
| 约束编号 C01–C29 | 29 / 29，无缺失无重复 | **29 / 29，无缺失无重复无多重计数** ✅ |
| 有效计数 29 / 27 / 24 / 3 | 一致 | **一致** ✅ |
| `v_place_evidence` 11 列（含顺序） | 11 / 11 | **11 / 11** ✅ |
| `v_place_time_span` 10 列逐列命中 | **5 / 10** | **10 / 10** ✅（`staging_evidence_rows` 已入清单） |
| 定序键 ⓿①②③④⑤ | 6 / 6 | **6 / 6** ✅ |
| `liveness` 8 值 | 8 / 8 | **8 / 8** ✅ |
| 过滤 `<> 'rejected'` / `sr.is_active` / `count(e.place_id)` | 一致 | **一致** ✅ |
| N01–N18 数字 | 18 / 18（N14 差 `U12` 引用号） | **18 / 18**（同上，判据噪声） |

**残留差异（均已登记、均为"不处置"或"待 CORE 解冻"）**：B-1（CORE 附录A L1623 的 C19 仍用 `IN (3 值)` 占位）、C-3（N14 的 `U12` 引用号）、C-4（`1,162` 计 2 次）、C-5（`rejected_by` 类型表述字符差）、A-4（本文件比 CORE 多给 `text` 类型词）。**另 13 条"文本/状态差异"全部是加粗（`**`）与括注补充，语义等价。**

## 7.3 修订中发现的**新**口径冲突（已登记 §J.3 第 7 项，未处置）

修订指令要求把 `first_batch_id` 写成 **NOT NULL**；但：

- CORE §5.9 的列定义**没有** NOT NULL；
- **C24 写 `CHECK (first_batch_id IS NULL OR last_batch_id IS NOT NULL)`——前半句只在 `first_batch_id` 可空时有意义**；若加 NOT NULL，C24 退化为恒真死约束（与"`dataset_id` 改回 NOT NULL 会让 C11/C12 失效"同类）。

⇒ 本轮**按 CORE §5.9 + C24 落笔为「可空」**，并把 "NOT NULL" 这一转述登记为待裁定口径。**建议由 team-lead 转 Owner 或交施工阶段以 CORE 为准。**

## 7.4 复核边界（不变）

本报告只回答"CHANGELOG 与 CORE 是否逐字一致"，**不回答设计是否正确**；§F 与 `IMPORT_RULES` / `ROLLBACK` 的交叉一致性不在授权范围。**不宣布通过。**
