# V2.1.1 正式交付物 —— 第 3 轮终检报告（QA_FINAL_CHECK）

**判定者**：QA 工程师（Edward / software-qa-engineer-6），未参与编制，独立复核
**判定对象**：`架构/V2.1.1/正式交付/`
**本轮职责**：① 验前两轮 16 项 FAIL 是否真关闭；② 按 `_build/ACCEPTANCE_CRITERIA_V2.1.1.md` 60 条逐条判定；③ 查是否引入新问题
**判据版本**：`ACCEPTANCE_CRITERIA_V2.1.1.md`（60 条，含 D1-5 / D1-6 / D2-1 / D2-2 / D2-10 / D4-2 / D4-10 / D6-1 的 V1 修订）
**哈希口径**：`sha256(open(path,'rb').read())[:16]`，输入为**文件原始字节**（遵守判据 §0，不用解码后文本重编码）

> **一句话结论**：**不达到"可提交 Owner 验收"的质量。** 60 条判据 **PASS 54 / FAIL 5 / PARTIAL 1**；前两轮 16 项 **CLOSED 12 / PARTIAL 4 / STILL-FAIL 0**。4 项 PARTIAL 与 3 个新 FAIL 同源于一件事：**`DATA_PROVENANCE_V2.1.1.md` 与 `ER_DIAGRAM_V2.1.1.svg` 没有参加第 1/2 轮修正**，导致已关闭的施工级缺陷（视图 SQL 不可编译、列数口径、许可列删除）在这两份文件里**原样复现**。另有 **交付物未冻结** 问题：QA 期间 CORE 被改 2 次、FIELD_MAPPING 被改 1 次，两份文件内引用的对方快照已失效。

---

## 0. 快照核对（首要动作；期间发生漂移，team-lead 已冻结，见 §0.5）

### 0.1 我拿到的期望值 vs 实测（首次核对，2026-11-03 10:2x）

| 文件 | 期望字节 / 行 / 哈希 | 首次实测 | 判定 |
|---|---|---|---|
| `CORE_DATA_MODEL_V2.1.1.md` | 144,265 / 1,690 / `a00084c26543b308` | 144,265 / 1,689 / `a00084c26543b308` | 字节+哈希**逐位吻合**；行数差 1 = 口径（见 0.3） |
| `ER_DIAGRAM_V2.1.1.svg` | 60,217 / 458 / `10542629e9ce23d7` | 60,217 / 457 / `10542629e9ce23d7` | 同上 |
| `FIELD_MAPPING_V2.1.1.csv` | 42,518 / 222 / `2791f3f82365f190` | 42,518 / 222 / `2791f3f82365f190` | **OK** |
| `IMPORT_RULES_V2.1.1.md` | 49,703 / — / `ba377a063edfe2cc` | 49,703 / 763 / `ba377a063edfe2cc` | **OK** |
| `DATA_PROVENANCE_V2.1.1.md` | 33,584 / — / `13c5bea3d99e2b6b` | 33,584 / 502 / `13c5bea3d99e2b6b` | **OK** |
| `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md` | 74,712 / — / `f45546fea7f5e72e` | 74,712 / 1,060 / `f45546fea7f5e72e` | **OK** |
| `_build/SHARED_BASELINE_V2.1.1.md` | 79,401 / 1,034 / `36f5b3f98765e8af` | 79,401 / 1,034 / `36f5b3f98765e8af` | **OK** |

**7 个哈希全部逐位吻合**（我自行重算，未采信转报值）。⇒ 我拿到的期望表**当时**是准的。

### 0.2 ⛔ 复核期间发生漂移（**新发现 FAIL 级问题**）

复核进行到一半再核对快照，发现两份被检文件已变：

| 文件 | 我首次核对时 | 复核结束时（当前状态） | mtime |
|---|---|---|---|
| `CORE_DATA_MODEL_V2.1.1.md` | 144,265 B / `a00084c26543b308` | **145,369 B / 1,693 换行 / `c0422f679ceb88c3`** | 10:32:08 |
| `FIELD_MAPPING_V2.1.1.csv` | 42,518 B / `2791f3f82365f190` | **43,168 B / 222 行 / `75ea47ca40394710`** | 10:32:43 |
| `V2.1_TO_V2.1.1_CHANGELOG.md` | 不存在 | 出现 → 138,649 B `3f2c57f62c08e39f`（10:41:01）→ **141,838 B `98199d279cc563d9`（10:44:54，最终态）** | 10:44:54 |

`CHANGELOG §J.3 第 1 项` 自己登记了这次漂移（CORE 三个状态 144,265 `a00084c26543b308` → 144,814 `7f890990a0171c71` → 145,369 `c0422f679ceb88c3`），说明"上游连续修订"是已知事实。**我在复核期间看到该文件两次落盘**：10:41 版本里 §A.4 表还写 CORE `144,814 / 7f890990a0171c71`、FIELD_MAPPING `42,518 / 2791f3f82365f190`，与其紧后的正文提醒自相矛盾；**10:44:54 的版本已把 §A.4 改为现值**（L125 `145,369 / 1,693 / c0422f679ceb88c3`、L128 `43,168 / 222 / 75ea47ca40394710`）**并把 FIELD_MAPPING 的变动并入 §J.3 第 1 项**——这一条**已由架构师自行修好**，本报告不再计为缺陷。

**仍存在的一处失效引用（可判定，未修）**：

- `FIELD_MAPPING_V2.1.1.csv` L218 的 notes 写：「⛔ 旧快照 4dd7d04e485c76e9 已作废，**现为 a00084c26543b308**」——CORE 现在是 `c0422f679ceb88c3`（且 CHANGELOG §A.4 L125 也这么写）。**该行钉住的快照已不存在**，任何按它复核的人都会得到"未修"结论。建议删掉硬编码哈希，只写"CORE §5.1 已删除该 2 列"。

> 附带观察：`CHANGELOG` L1242 自己写了「三张视图的 SQL 是**从 CORE 抄的，不是从 V0.2.2 抄的**」——这条纪律与 `DATA_PROVENANCE` §7.1 的现状（抄的是未修的旧版）恰好相反，可作为 B-1 的修复依据。

### 0.5 team-lead 冻结后的复验（第二轮指令：新快照 + 两处改动）

team-lead 于冻结后下发新快照表，并说明架构师又改了 CORE / FIELD_MAPPING 两处（「时间戳」明示、5 处 `updated_at` 核实依据）。**我按新快照重核，并按"不采信转报"逐项验证这两处改动**。

#### 0.5.1 新快照核对：7/7 命中，且已冻结

| 文件 | 新快照 | 实测 | 判定 |
|---|---|---|---|
| `CORE_DATA_MODEL_V2.1.1.md` | 145,369 B / `c0422f679ceb88c3` | 145,369 B / `c0422…` / 换行 1,693（split 口径 1,694）/ mtime 10:32:08 | **OK** |
| `FIELD_MAPPING_V2.1.1.csv` | 43,168 B / `75ea47ca40394710` | 43,168 B / `75ea47…` / 换行 222（split 223）/ mtime 10:32:43 | **OK** |
| `ER_DIAGRAM_V2.1.1.svg` | 60,217 B / `10542629e9ce23d7` | 一致 / 换行 457（split 458）/ mtime 10:23:57 | **OK** |
| `IMPORT_RULES_V2.1.1.md` | 49,703 B / `ba377a063edfe2cc` | 一致 / mtime 22:20:16 | **OK** |
| `DATA_PROVENANCE_V2.1.1.md` | 33,584 B / `13c5bea3d99e2b6b` | 一致 / mtime 22:45:36 | **OK** |
| `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md` | 74,712 B / `f45546fea7f5e72e` | 一致 / mtime 08:17:24 | **OK** |
| `_build/SHARED_BASELINE_V2.1.1.md` | 79,401 B / `36f5b3f98765e8af` | 一致 / 换行 1,034（split 1,035）/ mtime 10:04:28 | **OK** |

**7/7 命中，mtime 全部停在 10:32 及以前 ⇒ 冻结生效。** 本报告 §0.4 的判定本来就是在这一版上做的（不是旧值），**因此 60 条判定与 16 项结论无需因换版而改**。我另做了一次全文重跑作为独立确认（见 0.5.4）。

> ⚠️ **行数口径仍有两套在并行（必须一次钉死，否则下轮又是"版本错位"）**：
> - team-lead 表：CORE **1,694** 行、FIELD_MAPPING **223** 行 —— 用的是 `len(text.split('\n'))` 口径（末尾换行 ⇒ 多算 1 个空段）。
> - `CHANGELOG §A.4` L133/L134：CORE **1,693** 行、FIELD_MAPPING **222** 行 —— 用的是 `LF` 口径（= `wc -l`），且 L135 明写"行数为 `LF` 计数（两文件末尾均有换行符）"。
> - **两者差 1，都"对"，但并存就是缺陷**。建议全项目统一到 `LF` 口径（`wc -l`），并在快照表注明"末尾有换行符"。
> - 另：team-lead 表把 FIELD_MAPPING 写成「**223 行**（221 数据+表头）」，**括号内算术不符**——221 + 1 = 222，不是 223。实测物理行 **222**（1 表头 + 221 数据）；"223" 只有用 split 口径才成立（把末尾空段也算一行）。

#### 0.5.2 改动 ① 「时间戳」明示 —— **验证通过，且是一处真实修正**

| 核验点 | 实测 | 判定 |
|---|---|---|
| CORE §5.6（location）压缩行 | L767 `\| locked / manual_edited_fields / created_by / **`created_at` + `updated_at`**（timestamptz NOT NULL）\|` | ✓ 已明示 |
| CORE §5.7（name）压缩行 | L709 同上 | ✓ 已明示 |
| 两条核实注 | L711（称出处 `CORE_DATA_MODEL_V2.md:387`）、L769（称出处 `:350`） | ✓ 见下 |
| **出处是否真实**（我不采信转报，逐行查 V2 原文） | `V2:387` = `\| created_at / updated_at \| timestamptz \| NOT NULL \| \|` ✓<br>`V2:350` 同 ✓ | **✓ 引用为真** |
| 是否误给 `data_source` 加 `updated_at` | CORE L356 仍「⛔ **不加 `updated_at`**：V2 §5.1 的 `data_source` 只有 `created_at`」；§5.1 保留列仍为 6 列、末列是 `created_at` | ✓ 未污染 |
| **副作用（我的附加检查）** | 此改动**顺带消掉一个潜在 D5-2 风险**：改动前 name/location 的列清单只写"时间戳"，而 `FIELD_MAPPING` L121/L145 有 `historical_place_location.updated_at` / `historical_place_name.updated_at` 两行 ⇒ 严格按"target_column 必须在 CORE 中逐字存在"会判不符。改后逐字命中 ⇒ **D5-2 复扫 0 不符** | ✓ 净收益 |

> 结论：**改动 ① 成立，且是"用证据消除幽灵行"的正确做法**，不引入任何新缺陷。

#### 0.5.3 改动 ② FIELD_MAPPING 5 处 `updated_at` 核实依据 —— **验证通过**

| # | 行 | 映射 | 声明的出处 | 我核 V2 原文 | 判定 |
|---:|---|---|---|---|---|
| 1 | L29 | `data_dataset.updated_at` | V2 §5.2 行 215 | `215: \| created_at / updated_at \| timestamptz \| NOT NULL \|` ✓ | ✓ 真 |
| 2 | L80 | `historical_place.updated_at` | V2 §5.5 行 309 | `309` 同 ✓ | ✓ 真 |
| 3 | L121 | `historical_place_location.updated_at` | V2 §5.6 行 350 | `350` 同 ✓ | ✓ 真 |
| 4 | L145 | `historical_place_name.updated_at` | V2 §5.7 行 387 | `387` 同 ✓ | ✓ 真 |
| 5 | L170 | `candidate_match.updated_at` | V2 §5.8 行 419 | `419` 同 ✓ | ✓ 真 |
| 6 | L222 | `data_source.(dropped)` | — | 仍为 `(dropped)` + 【留痕】「V2 §5.1 与 V2.1 §5.1 均无 `updated_at`」 ✓ | ✓ 未变（W-01 保持 CLOSED） |

**5/5 出处逐条核对为真，第 6 处仍正确判 dropped。无回归**：数据行仍 **221**；`(dropped)` 行仍 **26 行且 26 行带【留痕】**；幽灵 `staging_column` 仍 **0**；D5-2 复扫 **0 不符**。

#### 0.5.4 全文重跑（换版后的独立确认）

在冻结版上重跑：`ET.parse()` 成功；12 实体名 + 全字段双向比对无虚构字段；三视图 SQL 静态检查（CORE 侧）通过；四排列脚本代入 1/1/0/2；七张 CSV 行数 29,391/19,039/47,503/18,103/53,137/12,631/7 全对；E1–E6 的 21 项基线哈希逐项一致。**60 条判定结果与 §3 完全一致，无一条因换版而变。**

> 诚实声明：我**没有保留** 144,265 B 那一版的字节副本，因此**无法做逐字 diff**；我能证明的是"当前冻结版上全部判定已重跑且结论不变"，而非"两个版本之间改了哪几个字节"。

#### 0.5.5 ⭐ 独立裁决：`12,631` / `12,831` 口径到底是 3 处还是 7 处

**先说清一件事：我原报的就是 3 处，不是 7 处**（见本报告 §1 第 8 项、§3 的 D6-1/D2-4）。"7 处"不是我的结论，可能与其他 QA 的报告串了。

**我的穷举式裁决**（正则覆盖 `12,631` / `12,831` / 无千分位 `12631` / 全角逗号 / 空格变体；扫描范围含全部 8 份文件）：

| 计数单位 | CORE 结果 | 说明 |
|---|---:|---|
| **按"行"（= 语义落点）** | **3 行** | L1433 / L1447 / L1640 —— **与架构师实测一致** |
| **按"token 出现次数"** | **8 次** | L1433 ×1、L1447 ×5（左值+右值+算式两项+末句两个反引号引用）、L1640 ×2 |
| **"7 处"** | **0 口径下成立** | 行=3、次数=8，**7 在任何计数方式下都不存在** |

**CORE 三处是否都带口径词**：L1433「12,631（**暂存原始**）」✓；L1447「12,631（**暂存原始**）／12,831（**预计入库**）…⛔ 两个数不得混用」✓；L1640「**暂存原始** 12,631 条…**入库**口径为 12,831」✓ —— **三处全部带口径词，无缺陷**。

**关于 `197`**：全文 3 处（L240「197 个不同指纹」、L1447「+ 197」、L1644「197 条派生偏差」），**均指 `derived_value_mismatch` 的派生偏差条数，是 12,831 的加项，从未被当作台账总数别名**。我用 ① 复算：`12,631 − 2 + 5 + 197 = 12,831` ✓（`licence_unconfirmed` 在暂存实测 2 行、`+5` 与 `+197` 为设计新增）。

**⇒ 裁决：CORE 侧 3 处 / 8 次，全部合规；「7 处」不成立；W-03（第 2 轮）维持 CLOSED。**

**但穷举扫到 3 个此前无人检查的落点（我如实列，并按判据逐一判性质）**：

| 落点 | 内容 | 我的判定 | 理由 |
|---|---|---|---|
| `ER` L432 | `historical_place_location 18,101 · historical_place_name 47,499 · data_quality_issue 12,831。` | **不计缺陷** | 该行是 L431 那句「本图所有行数一律为「**预计入库**」口径：…」的**换行续写**（SVG 文本因宽度被拆成两个 `<text>`）⇒ 口径词在同一句句首，管辖成立。**勿再据"本行无口径词"报缺陷** |
| `_build/SHARED_BASELINE` L954 | N08 行 `\| 12,631 \| 12,831 \| +200 \|`（行内无口径词） | **不计缺陷（但建议补）** | `_build` 是**编制辅助件**，不参与八份交付物计数，D6-1 不以其为判定对象；但仍建议列头补「暂存原始／预计入库」，因为它是我这类复核者的锚点 |
| `CHANGELOG` L136 | 「…`18,626` / `10,765` / **`12,831`** / `29,377` 全部命中」 | **WARN（新 N-10）** | 该行是"命中清单"，`12,831` 裸写无口径词；同时该行所在 §A.4 的 L133/L134 用 LF 口径（1,693 / 222），与 team-lead 表的 split 口径（1,694 / 223）不一致 ⇒ 同一节内两套口径 |

#### 0.5.6 改动带来的一个新 WARN

**N-9（WARN，1 处、改 1 个词）**：CORE 已把「时间戳」明示为 `created_at` + `updated_at`（L709/L767），但 **`ER` 的 name 卡片仍写裸「时间戳」**（y=1233 那行：`locked / manual_edited_fields / created_by / 时间戳`，全文仅此 1 处）。
⇒ ① 两份交付物对同一件事不再逐字一致；② 这**恰好是"幽灵行"的产生机制**（V2.1 用"时间戳"三个字继承了 `updated_at`，按列名 grep 查不到 ⇒ 才出 `data_source.updated_at` 幽灵行）。建议 ER 该行改为 `… / created_at + updated_at`，与 CORE 对齐。

> **处置建议（不属我职权，交 team-lead 裁定）**：① **立即冻结**六份交付物（写入禁止状态）；② 冻结后由架构侧重跑 `CHANGELOG §A.4` 全表；③ `FIELD_MAPPING` L218 改为不写死哈希、只写"CORE §5.1 已删除该 2 列"；④ 本报告的全部判定按 **0.4 列出的最终快照**重做过一遍（见 0.4）。

### 0.3 行数差的真实原因（不是缺陷，但口径要写清）

CORE 1,689 vs 期望 1,690、ER 457 vs 期望 458：两份文件都以 `\n` 结尾，`wc -l` 得 N（= 换行符数），而 `content.split('\n')` 得 N+1（末位空串算一行）。字节数与 sha256 **完全相等** ⇒ 内容逐位相同，纯计数口径差异。`FIELD_MAPPING`（222）与 `BASE`（1,034）的期望值用的是 `wc -l` 口径。**建议在快照表统一写明"行数为 LF 计数、文件末尾有换行符"**——`CHANGELOG §A.4` 已这么写，建议 `ACCEPTANCE_CRITERIA §0` 同步。

### 0.4 本报告判定所依据的最终快照（全部判定已在新版上重跑）

| 文件 | 字节 | `sha256[:16]` |
|---|---:|---|
| `CORE_DATA_MODEL_V2.1.1.md` | 145,369 | `c0422f679ceb88c3` |
| `ER_DIAGRAM_V2.1.1.svg` | 60,217 | `10542629e9ce23d7` |
| `FIELD_MAPPING_V2.1.1.csv` | 43,168 | `75ea47ca40394710` |
| `IMPORT_RULES_V2.1.1.md` | 49,703 | `ba377a063edfe2cc` |
| `DATA_PROVENANCE_V2.1.1.md` | 33,584 | `13c5bea3d99e2b6b` |
| `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md` | 74,712 | `f45546fea7f5e72e` |
| `_build/SHARED_BASELINE_V2.1.1.md` | 79,401 | `36f5b3f98765e8af` |
| `V2.1_TO_V2.1.1_CHANGELOG.md`（新，最终态 10:44:54） | 141,838 | `98199d279cc563d9` |

> 本报告自身：`_build/QA_FINAL_CHECK.md`，58,452 B `2c49e39b47e6b9d9`（初稿；本次修订后字节数略增，以文件实算为准）。

> 简报：CORE 的 +4 行是把 §5.10.1 窗口 `ORDER BY` 里的列全部加上 `u.` 限定符（L910–929），并补了 2 行解释性注释——**是正确性改善，不影响任何已判事实**。我逐条把 16 项与全部判据在新版上重跑，结论与旧版一致（行号已按新版更新）。

---

## 1. 前两轮 16 项 FAIL —— 关闭状态（逐条，附实测证据）

判定用语：**CLOSED** = 该缺陷在所涉全部文件中都已消除；**PARTIAL** = 部分文件已修、仍有文件复现；**STILL-FAIL** = 未修。

| # | 缺陷 | 判定 | 实测证据（行号按 §0.4 快照） |
|---:|---|---|---|
| 1 | **F-02** `occurrence_key` 既删又存 | **CLOSED** | 全文 20 处 `occurrence_key` 已逐处核对：唯一"列定义"位置是 `CORE` L492 `\| ~~`occurrence_key`~~ \| — \| **已删除**（V2.1 列）\| … **本行保留仅为逐列对照，模型中没有该列**`；其余 19 处全为 B1/B3 对照、§5.2.3 删除说明、V-3 裁定、附录 A 未编号约束登记（L1607）。**无任何现行列定义仍含该列** |
| 2 | **F-03** `v_place_liveness` 的 ev CTE 引用 `e.inactive_at` / `e.inactive_in_batch_id` | **PARTIAL** | ✅ `CORE` L1044 `JOIN source_record sr ON sr.source_record_id = e.source_record_id`，`ORDER BY` 用 `sr.inactive_at` / `sr.inactive_in_batch_id`（L1035–1037），并有 L1065 根因留痕。✅ `_build/SHARED_BASELINE` L805–811 同步。<br>❌ **`DATA_PROVENANCE` §7.2 L346 仍是 `FROM v_place_evidence e`，L341 仍是 `e.inactive_at DESC NULLS LAST, e.inactive_in_batch_id DESC NULLS LAST`**，全文无 `JOIN source_record`、无 L366 附近的修正说明 ⇒ **该份文件里的视图 SQL 仍不可编译**（`v_place_evidence` 固定 11 列，无这两列） |
| 3 | **F-04** `v_place_liveness` 对外列 9 vs 7 | **PARTIAL** | ✅ `CORE` L1022 标题「本视图**对外 7 列**」；L1071「对外列清单（补全，**7 列**）」，表内编号 1–7，SQL `SELECT` 输出 7 列；L1282 给出 8−3+2=7 的算术核对。✅ `BASE` §14.2 L768「对外列清单（7 列）」+ L780「CTE 中间量（2 列，不在对外 SELECT 中）」+ L787 留痕。<br>❌ **`ER_DIAGRAM` 图注（第 235 条 text）仍写**「⚠️ **CORE §5.10.2 称「对外 9 列」**，但其编号表只列 7 项、SQL 的 SELECT 亦只产生 7 列」——CORE 已改为 7 列，该图注成为**对不存在缺陷的描述**，把"9 vs 7"的混乱留在唯一有效 ER 图里 |
| 4 | **F-05** `valid_child_rows` 用裸 `count(*)` | **CLOSED** | `CORE` L1168 `count(e.place_id) AS valid_child_rows, -- ⭐ A-2 修正：不用裸 count(*)`；L1179 `AND count(e.place_id) = 0 ) AS all_children_rejected`；L1186 修正说明。全视图再无"无 FILTER 的裸 `count(*)` 充当有效行数" |
| 5 | **F-06** C13 `source_rule_vocabulary` vs `source_time_columns` | **CLOSED** | `CORE` L718 `C13 CHECK (source_time_columns = '' OR …)`；L1590 落点「`historical_place_location`（**改名后**；name 表无 `source_beg_rule`/`source_end_rule`）」；L781 显式「**C13 在本表【不适用】**…×若把 C13 原式写在本表将引用不存在的列、SQL 无法编译 ⇒ **C13 仅落在 `historical_place_location`**」 |
| 6 | **F-07** §5.0 漏 `import_batch.blocked_count` | **CLOSED** | 两张表都有：`CORE` L293 §5.0 首行「`import_batch` \| `blocked_count` \| **新增** \| 无 \| `integer NOT NULL DEFAULT 0`；记录级跳过（`locked` / `manual_edited_fields` / `last_batch_id` 不符）时 +1 \| V0.2.1 G3-04（行 336）；V0.2.2 §2.4.3（行 509）」；§5.3 L466 列定义同 |
| 7 | **F-08** 两处引用错（§10.3→§9.3；V2.1 行 1639→V0.2.1 行 1639） | **CLOSED** | `CORE` L387「7 个实测值见 **§9.3**」（§9.3 实际在 L1470，标题存在）；全文 `§10.3` 命中 **0**。L1307「（**V0.2.1** `V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` 行 1639 记…）」，全文 `1639` 仅此 1 处且已带 V0.2.1 |
| 8 | **F-09** 6 处行数缺口径词 | **CLOSED** | `CORE` 全文 `12,631` 命中 **3 处**（L1433 / L1447 / L1640）——**与架构师实测"只有 3 处"一致，我未发现更多**。三处分别带「（**暂存原始**）」「（**暂存原始**）… **12,831（预计入库）**」「**暂存原始** 12,631 条…（口径说明：…**入库**口径为 12,831）」。**另：`197 条` 全文未与 12,631/12,831 混用**（L240「197 个不同指纹」、L1447「+ 197」、L1644「197 条派生偏差」，均为 `derived_value_mismatch` 派生偏差条数，是 12,831 的加项） |
| 9 | **F-10** `BASE §2.1` 旧隔离规则标"正确规则" | **CLOSED** | `BASE` L92–99「**正确规则**：组内按 `(content_hash ASC, raw_record_index ASC)` 定序后，同一 hash 子组内【最小 ordinal】保留；该子组内【后续相同 hash】的行 ⇒ 隔离；【不同 hash】的行 ⇒ 均保留（不隔离）」= **新规则**；L101「⛔「只比较 `ordinal = 1` 的 hash」是 V0.2.2 §2.5.0 的历史写法，已被 Owner r3 / P0-03 裁定禁用（此处仅作**【留痕】**）」+ L103–109「禁止只比 ordinal=1 / 禁止要求整组完全相同」 |
| 10 | **F-11** `is_canonical_row` creator 分支写死 FALSE + `<…>` 占位符 | **PARTIAL** | ✅ `CORE` L906–929：三支 `UNION ALL` 下沉为子查询 `u`，外层 `row_number() OVER (PARTITION BY u.place_id ORDER BY …) = 1`，定序键 `sr.duplicate_ordinal` / `sr.external_id` 回连 `source_record`，**creator / name / location 三处写死常量与占位符全部消除**；`CORE` 全文尖括号占位符仅剩 4 处（L971/L973/L1294/L1528），全部在"原缺陷说明/作废对照"语境。<br>✅ `BASE` §14.1 L728–742 六键定序与 CORE 逐字一致。<br>❌ **`DATA_PROVENANCE` §7.1 是未修版本**：L290 `FALSE AS is_canonical_row -- 由 ②③ 竞争，见 §6.1`、L304 `FALSE, <canonical 定序 CORE §5.10.4>`、L311 `FALSE, FALSE`。**交付物内仍有 1 处不可执行占位符**（直接违反 D4-10②）。而该节 L273 自称「以下 DDL 与 `CORE` §5.10 **逐字一致**；两份文件任一处改动必须同步另一处」——**事实相反** |
| 11 | **F-12** `data_quality_issue.dataset_id` NOT NULL | **CLOSED**（列属性层面） | `CORE` L824「`dataset_id` \| `text` \| **FK** → `data_dataset`，**可空** \| ⭐ **约束变化：NOT NULL → 可空**」；§5.0 L308 单独一行登记该约束变化 + L320 说明；§11 第 8 条「必须保持可空」；C11/C12 恢复为可触发约束（L865–868）。<br>⚠️ 但「**缺口已消解**」这个**结论不成立** ⇒ 见 §2 新发现 **N-1**（F-12 的列属性已修，但其推论错了） |
| 12 | **F-01/02/03（第 2 轮）** `source_time_columns` 三文件改名同步 | **CLOSED** | `FIELD_MAPPING` L110 改名行（`(derived) → historical_place_location.source_time_columns`，notes 首标**【改名】**）+ L135 新增行（`→ historical_place_name.source_time_columns`，notes 首标**【新增】**）；`ER_DIAGRAM` 第 149 条 text「source_time_columns … ⭐改名」+ 第 173 条「+ source_time_columns … ⭐新增（V0.2.1 §5.7）」；`CORE` §5.6 L707 改名 + §5.7 L764 新增。**旧名 `source_rule_vocabulary` 残留**：CORE 4 处 / FM 2 处 / BASE 3 处，逐处核对**全在"改名对照/改名后"语境**，无一处当现行列名用 |
| 13 | **W-02（最严重）** `data_source` 的 `default_license_id` / `default_redistributable` | **PARTIAL** | ✅ `CORE` §5.1 L342–351「保留列（**6 列**，逐列列出——本表今后不再用"无变化"三字）」+ L353–354「⛔ 已删除的 2 列【留痕】」逐列列明；§5.0 **两行**记录（L317 `default_license_id`、L318 `default_redistributable`，都标 **删除**）；§7.1 L1387 再述一次。<br>✅ `FIELD_MAPPING` L218 `data_source.(dropped)` + 【留痕】。<br>❌ **`ER_DIAGRAM` 的 `data_source` 卡片仍写**「本表 CORE V2.1.1 §5.1 声明「无变化」，上列 6 列为 V2 既有列；**另有 2 列来源级许可默认值（不画）：消费方已随 §7.1 许可门禁废除消失，去留待下轮裁定**」⇒ ① 声称这两列**仍然存在且"去留待下轮裁定"**，与 CORE「**删除**」互斥；② 无【留痕】标记；③ 属**结构层表述**（说明该表还有 2 列），已越过 D1-5③ 的字面层豁免边界 |
| 14 | **W-01** `data_source.updated_at` 幽灵行 | **CLOSED** | `FIELD_MAPPING` L222 `(none),(generated),data_source,(dropped)…` notes：「【留痕：幽灵行，非现行映射】V2 §5.1 与 V2.1 §5.1 的 `data_source` **均无 `updated_at` 列**（只有 `created_at`）… ⛔ 不得据此给 `data_source` 加 `updated_at`」。`CORE` L356 同步说明 |
| 15 | **F-04（第 2 轮）** FIELD_MAPPING `(dropped)` 行留痕 | **CLOSED** | 程序统计：`(dropped)` 行 **26 行**，其中 notes 含 **【留痕】26 行**（100%）。逐行核对语境均为「已删除列/禁用正则说明/删枚举值说明/幽灵行」，无遗漏 |
| 16 | **W-03** `12,631` vs `12,831` 口径 | **CLOSED** | 同 #8。另独立复算 N08 算式：`12,631 − 2 + 5 + 197 = 12,831` ✓；`licence_unconfirmed` 在暂存 `data_quality_issues.csv` 实测 **2 行**（我逐行数，见 §3 判据 D2-4），与算式减项一致 |

**小计：CLOSED 12 / PARTIAL 4（#2 #3 #10 #13）/ STILL-FAIL 0**

> **4 项 PARTIAL 的共同根因（单一、可一次修完）**：`DATA_PROVENANCE_V2.1.1.md`（mtime `11-02 22:45`）与 `ER_DIAGRAM_V2.1.1.svg`（`11-03 10:23`）**没有参加第 1/2 轮的修正**。CORE（10:32）、FM（10:32）、BASE（10:04）、ROLLBACK（08:17）都改过；DP 是**最早写、从未回改**的那一份。⇒ F-03 / F-04 / F-11 / W-02 在这两份文件里**原样复现**。

---

## 2. 新发现的 FAIL / WARN（前两轮未报）

### N-1（FAIL，施工级）5.9.1 与 FIELD_MAPPING「6 行缺口已消解」的结论不成立，C11 必然被违反

- `CORE` §5.9.1 L885：「6 行空 `source_record_id` … **缺口已消解**（根因修正）… 由 C11 要求它们必须带 `place_id`（**它们正是地点级台账**）」。
- `FIELD_MAPPING` L183 / L184 同口径：「这 6 行**合法留 NULL**，由 C11 要求它们必须带 `place_id`（它们正是地点级台账）」「那 6 行 `source_record_id` 为空的台账**靠本列归因**」。
- **我逐行读了那 6 行**（`data_quality_issues.csv`，① 原始 CSV）：

| issue_id | source_dataset | issue_type | 性质 |
|---|---|---|---|
| `dq_0007487` | `chgis_pref` | `nonstandard_field_name`（`END_DATE` vs `ENT_DATE`） | **层/文件级** |
| `dq_0007488` | `chgis_pref` | `nonstandard_field_name`（`GEOCOMPLR` vs `GECOMPLR`） | **层/文件级** |
| `dq_0007489` | `pleiades_gis_4_1_slice` | `truncated_slice_tail`（`places.csv`） | **文件级** |
| `dq_0007490` | `pleiades_gis_4_1_slice` | `truncated_slice_tail`（`names.csv`） | **文件级** |
| `dq_0007491` | `pleiades_gis_4_1_slice` | `truncated_slice_tail`（`location_points.csv`） | **文件级** |
| `dq_0007492` | `pleiades_gis_4_1_slice` | `truncated_slice_tail`（`connections.csv`） | **文件级** |

**结论**：这 6 行**一行都不是地点级台账**，都是"字段名不一致 / 切片尾部截断"的**数据集级或文件级**问题。
且 `place_id` 在暂存 11 列里**根本不存在**（列头：`issue_id, source_id, source_dataset, source_record_id, issue_type, severity, field_name, observed_value, expected_rule, action_taken, notes`，我实测），唯一可能的归因通路 `source_record_id` 恰为空；另一条通路 `source_dataset` 已被 `FIELD_MAPPING` L174 **判 `(dropped)`**（理由"含非法值；改为 dataset_id"），而 `chgis_pref` 按 `CORE §5.2.1 规则 3` 是**图层键不是 dataset id**。
⇒ **这 6 行的 `dataset_id` 与 `place_id` 双双不可派生** ⇒ `C11 CHECK (dataset_id IS NOT NULL OR place_id IS NOT NULL)` **必然被违反** ⇒ 要么整批 failed，要么 6 行台账被丢弃（则 N08 的 12,831 少 6 行）。

**修法（三选一，需裁定）**：① 这 6 行按 `source_dataset` 派生 `dataset_id`（`pleiades_gis_4_1_slice` 合法；2 条 CHGIS 需先把 `chgis_pref` 映射到 `chgis_v6_prefecture_points`，即恢复一条"图层键→dataset_id"常量映射）；② 明确这 6 行**不入库**（改 N08 为 12,825 并说明）；③ 给 `data_quality_issue` 增加"文件级台账"的合法形态（属新设计，须 Owner 批）。**不得**把 `V-6` 写成"已消解/降级为待复核"就收工——它是**可判定为必然失败**的，不是"待复核"。

### N-2（FAIL，规格互斥）`is_canonical_row` 定序在四份文件里出现四套，且"零有效证据"结论互斥

| 文件 | 定序键 | 零有效证据时 |
|---|---|---|
| `CORE` §5.10.1 L920–929 / §5.10.4 L1244–1255 | **6 键**：⓿①②③④⑤ | `is_canonical_row` **仍落定序第一行**（"最佳可得"，仅追溯），L979 / L1260 明文 |
| `BASE` §14.1 L728–742 | **6 键**（与 CORE 逐字一致） | 同 CORE（L749 登记 V-8） |
| `IMPORT_RULES` §10.1 L638–641 | **4 键**（①②③④，**缺 ⓿ 与 ⑤**） | §10.2(2) L654：**「`is_canonical_row` 全为 FALSE，不得回退到"任取一行"」** |
| `DATA_PROVENANCE` §6.1 L227–230 | **4 键**（同上），且 §7.1 SQL 用 `FALSE` + 占位符 | §7.1 L290 写死 FALSE |

两处**硬互斥**：
1. **零有效证据**：CORE「必落在定序第一行」vs IMPORT「全为 FALSE」——`row_number()=1` 的实现**必然**给出一行 TRUE，两者不可能同时成立。这条直接决定 `liveness='orphaned'` 的地点（CORE R4f 断言 = 0）在 `v_place_evidence` 里是 0 个还是 ≥1 个 canonical。
2. **IMPORT §10.2(1) L653 断言「定序唯一（末位 `source_record_id` 破并列），**不可能并列**」是错的**：`C08` 允许**一条 `source_record` 派生最多 3 行 name**（`name_type` 不同），其 ①②③④ 键**全同** ⇒ 必然并列 ⇒ 缺 ⑤ 时 `row_number()` 取值不可复现。CORE L1254 已把这一点写成「⛔ ⑤ 不可省略」，IMPORT 未同步。

### N-3（WARN，记号级但会使断言恒不成立）R2c 用 `:R` 而非 `:Rb`

`ROLLBACK` §5.1 L698 把记号钉死：「`:R` = 被回滚批次；`:Rb` = 回滚批次（`rollback_of_batch_id = :R` 的那一批）」，L682/L683 还专门警告「❌ 用 `import_batch[R].blocked_count`」「❌ 用 `import_batch[R].failed_count`」。
但 §5.5 L768–771 写的是 `R2c count(data_quality_issue WHERE batch_id = :R AND issue_type='import_row_error') == N_fail_rb`，而 `N_fail_rb` 是**回滚期**失败（§3.3 L260、§3.4 步骤 5 L313、反例⑥b L597 明写「`batch_id=Rb`」）。⇒ **左式取导入期台账、右式取回滚期计数**，正是 §3.6 第 1 条要防的"两组混用"。`CORE` 附录 B L1640 抄同一式子（写 `== N_failed`），同样未指明批次。
**修法**：R2c 左式改 `batch_id = :Rb`；CORE L1640 同步。

### N-4（WARN，口径级）`98909/20469` 的"混合组（3 行里 2 行相同、1 行不同）"与四段前缀分组自相矛盾

`CORE` L201 与 `IMPORT_RULES` §5.2⑤ L316–326 都写「`pleiades_connection_id / 20469` 是**混合组**（**3 行里** 2 行相同、1 行不同）」，并给出 `A,A,B` 推演表（ordinal 3 的 B 保留）。
**我按五段键（四段前缀）实测**：

```
('pleiades_gis_4_1_slice','edge','98909','20469') n=2 hashes=[79753045, 79753045]   ← 该组只有 2 行且 hash 相同
sr_0027194  parent(place_id)=98930  external_id=20469  hash=b4025180                  ← 第 3 行属另一个组
```
⇒ 该"混合组"是**三段键口径**（`dataset+type+external_id`）的 3 行，按 §5.1 写死的四段前缀分组，它们**不在同一组**。隔离结论（隔离 `sr_0027175` 1 行）**是对的**，但推演表把"跨组"写成"组内 A,A,B"，**会诱导实现者按三段键分组**——这正是 C29/`parent_external_id` 要防的静默数据损坏（398 组 / 2,335 行）。
**修法**：改写为「同一父级 `98909/20469` 为 `A,A` ⇒ 隔离 1 行（`sr_0027175`）；另有 `20469` 在父级 `98930`，hash 不同，按四段前缀属**另一个组** ⇒ 保留（不因跨组被隔离）」。"禁止要求整组内容相同"的论证可保留，但改用它自己的理由，不要把跨组例子说成组内。

### N-5（WARN）`issue_type` 6 个 0 行枚举值缺"空集说明"

`CORE` §0 L30 自订硬原则：「模型里每一个 `CHECK` 枚举值，必须在暂存数据里有对应取值**或明确的空集说明**」。
实测暂存 `data_quality_issues.csv` 的 `issue_type` 只有 **13 种**（`unknown_time_bound_type` 6,448 / `parent_place_not_in_sample` 4,810 / `unknown_crs` 646 / `beg_eq_end` 341 / `missing_coordinate` 337 / `beg_gt_end` 28 / `coordinate_outside_china_bbox` 6 / `year_out_of_range` 4 / `truncated_slice_tail` 4 / `duplicate_sysid` 2 / `nonstandard_field_name` 2 / `licence_unconfirmed` 2 / `coordinate_out_of_range` 1，合计 12,631 ✓）。
19 值中的 6 个（`duplicate_external_id` / `empty_name` / `manual_edit_conflict` / `import_row_error` / `derived_value_mismatch` / `rollback_conflict`）在暂存为 0 行，CORE §5.9 L836–849 只列值名**未给空集说明**（只有 `import_row_error` 在别处说明"零命中"）。⇒ 违反 CORE 自己的 §0 原则。**修法**：在 19 值清单旁加一列"暂存实测行数 / 空集说明"。

### N-6（WARN，内容被检查工具扭曲）`ER` 把子表枚举值写成"发布态值"

`ER` 第 154 / 176 条 text：「【子表 3 值】CHECK IN (staging, **发布态值**, rejected)」，第 276 条解释「子表第三个合法值的字面量逐字见 CORE §5.6 / §5.7 的 CHECK；**本图只标注「它存在且与地点表不同」，不重复该字面量**」。
而 `FIELD_MAPPING` L63 是**照写**的：「子表 3 值是 staging / **published** / rejected」。⇒ 同一枚举，两份交付物一份给字面量、一份给代称。
成因清楚：`D3-3` 要求"`'published'` 命中数为 0"，架构师为过扫描把**子表枚举值**也改写成了"发布态值"。但 `D3-3` 约束的是 **`v_place_time_span` 的过滤条件**，不是子表 `record_status` 的值域。**这正是判据文件自己禁止的"让内容迁就检查工具"**（`ACCEPTANCE_CRITERIA` 开头：「改判据不改内容」）。**修法**：ER 恢复字面量 `published`（D3-3 的扫描改为只扫 `v_place_time_span` 图注内的过滤条件）。

### N-7（WARN）`<本批>` 伪代码占位符

`CORE` L257（§4.6）与 `IMPORT_RULES` L357（§5.4）写 `inactive_in_batch_id = <本批>`。**不构成 D4-10② 违规**（该条只管视图 SQL），但建议统一写 `:batch_id`——同一批文件的别处（`ROLLBACK` §5.2）已用 `:R` / `:Rb` 命名参数。

### N-8（WARN，快照引用已失效）见 §0.2

`FIELD_MAPPING` L218 钉住的 CORE 快照 `a00084c26543b308` 已不存在（现 `c0422f679ceb88c3`）。`CHANGELOG §A.4` 的快照表在 10:44:54 版本**已自行改对**，不再计缺陷。

### N-9（WARN，1 处改 1 个词）`ER` 仍用裸「时间戳」，与 CORE 新写法不再逐字一致
`CORE` L709/L767 已明示「时间戳 = `created_at` + `updated_at`」；`ER` 的 name 卡片仍写 `locked / manual_edited_fields / created_by / 时间戳`（全文仅此 1 处）。**这恰是"幽灵行"的产生机制**（V2.1 用"时间戳"三字继承了 `updated_at`，按列名 grep 查不到 ⇒ 才出 `data_source.updated_at` 幽灵行）。建议 ER 改为 `… / created_at + updated_at`。

### N-10（WARN，口径）`CHANGELOG §A.4` 内部两套行数口径 + 1 处裸数字
① L133/L134 用 **LF 口径**（CORE 1,693 / FM 222），L135 明写"行数为 LF 计数"；而 team-lead 下发的快照表用 **split 口径**（1,694 / 223）⇒ 同一事实两个数并存。
② L136 把 `12,831` 列入"命中清单"时**裸写无口径词**。
③ 另：team-lead 表把 FM 写成「223 行（221 数据+表头）」，括号内算术不符（221+1=222）；实测物理 **222**（1 表头 + 221 数据）。建议全项目统一 LF 口径并注明"末尾有换行符"。

---

## 3. 60 条判据逐条判定

来源层级：① 原始 CSV 逐行算 ② 上游脚本产物 ③ 上游文档结论 ④ 基线/判据文档定义。**②③未直接当结论**：凡标注 ①②③④ 混用的，结论均回到 ①（我自己的复算）或 ④。

### §1 八份交付物完整性（6 条）

| ID | 判据摘要 | 实测 | 判定 | 层级 |
|---|---|---|---|---|
| D1-1 | 八份文件全部存在、文件名逐字 | 目录实列 **7 份** + `_build`：CORE / ER / IMPORT / FIELD_MAPPING / ROLLBACK / DATA_PROVENANCE / **V2.1_TO_V2.1.1_CHANGELOG.md**（10:41 到位）。**缺 `V2.1.1_QA_REPORT.md`**——本报告的落点是 `_build/QA_FINAL_CHECK.md`，而 `_build` 按 D1-2 不计入交付物 | **FAIL** | ①（`ls`） |
| D1-2 | 无第九份越界文件混入根目录 | 根目录只有上列 7 份 + `_build/`；无 `.sql` / `.ddl` / `Dockerfile*` | **PASS** | ① |
| D1-3 | ER 图是良构 XML | `ET.parse('ER_DIAGRAM_V2.1.1.svg')` **成功**，root = `{http://www.w3.org/2000/svg}svg`，457 个 LF，60,217 B | **PASS** | ①（实际解析） |
| D1-4 | CSV 列头逐字一致 | `staging_table,staging_column,target_table,target_column,target_type,required,transform,enum_rule,notes`（9 列，含 UTF-8 BOM），221 数据行全部 9 字段，**列数不符行 0** | **PASS** | ① |
| D1-5 | 无许可功能：功能层 / 结构层 / 字面层 | ① **`LICENSE_GATE` 命中 0**（6 份全 0）✓；② 结构层无许可列 ✓（`data_dataset` 9 列、`data_source` 2 列均已删，`FIELD_MAPPING` 18 条许可相关映射全 `(dropped)`）；③ 字面层 **9 处未逐处标【留痕】**：`CORE` L317 / L322 / L332 / L334 / L353 / L354 / L357 / L1387、`IMPORT_RULES` L117（均在"删除说明"语境、内容正确，缺的只是标记） | **PARTIAL** | ①（逐行扫） |
| D1-6 | 每份首部声明 V2.1.1 + 以 V0.2.2-r2 为权威依据 | ✓ `CORE` L4「**版本**：2.1.1」+ L7「**权威来源**：`…V0.2.2…`」；✓ `IMPORT` L4/L6；✓ `ROLLBACK` L4/L6；△ `DATA_PROVENANCE` L1 标题含 V2.1.1、正文 11 处引 V0.2.2，**首部无"权威来源"行**；❌ **`ER` 全文 `V0.2.2` 命中 0**，`<desc>` 只写"字段名与 CORE §5 逐字一致"，未声明权威依据；△ `FIELD_MAPPING` 为 CSV，首行必须是 D1-4 规定的列头，无位置放首部声明（判据与格式冲突，建议豁免或改判为"文件名含 V2.1.1 + notes 引 V0.2.2"） | **FAIL** | ① |
| D1-6 附注 | — | 一处判据内部冲突：D1-6（要求首部声明）与 D1-4（要求列头逐字）在 CSV 上**不可能同时满足**。建议按"改判据不改内容"纪律修订 D1-6，明确 CSV 豁免 | — | — |

### §2 跨文档字段与枚举一致性（12 条）

| ID | 判据摘要 | 实测 | 判定 | 层级 |
|---|---|---|---|---|
| D2-1 | `record_scope` 恒 4 值，枚举语境 `connection` = 0 | 6 份文件 `connection` 共 39 处（CORE 29 / FM 9 / IMPORT 7 / DP 2 / ER 1 / ROLLBACK 0），**逐处判读，落在"值域列举/CHECK/字段取值"语境的 0 处**；全部为源端概念名（"排除 connection"、"pleiades_connection_id"、connection 年份）✓ 符合豁免条款。① 实测 `record_scope` 派生 = place 18,398 / name 5,762 / location 2,468 / edge 2,763，**4 值，无第五种** | **PASS** | ①④ |
| D2-2 | `evidence_role` 恒 3 值，枚举语境 `place_record` = 0 | `place_record` 全文 6 处，**全在 CORE**：L46（B9「为**禁用词**」）、L989（「⛔ `place_record` 是**禁用词**」）、L1500（§10 对照）、L1645（K3 禁用词清单）。**均为禁用词声明/历史对照，符合豁免** | **PASS** | ①④ |
| D2-3 | `liveness` 8 值、`record_status` 3 值、`rejected ⟺ FAILURE_SET` | 8 值齐（CORE/ER/DP 各自枚举完整）；`FAILURE_SET = {all_sources_absent, all_sources_rolled_back, quarantined_only, mixed_inactive}` 在 CORE L1116 / ER 第 233 条 / DP L371 三处一致；`rejected ⟺ liveness ∈ FAILURE_SET` CORE L1119 / ER 第 234 条逐字一致。CORE 真值表 8×3 格 + R4a–R4f 六条断言齐。地点 3 值（staging/rejected/merged）与子表 3 值（staging/published/rejected）**分别写明、不合并**（CORE §5.5.2 L623–630）✓。**但 ER 把子表第三值写成"发布态值"** ⇒ 见 N-6（记在该条，不重复计入其他判据） | **PASS**（附 N-6） | ①③④ |
| D2-4 | `time_bound_type` 7 / `derivation_kind` 3 / `inactive_reason` 3 / `issue_type` 19 | 四组值域在 CORE 逐一列明（§6.1 L1313–1325 / §6.3 L1342–1346 / §5.4 L500 / §5.9 L838–849），其余文件引用处不另立值域。① 实测 `issue_type` 暂存 **13 种、合计 12,631**，全部落在 19 值域内 ✓（6 个 0 行值缺空集说明 ⇒ N-5）。`inactive_reason` 3 值 + `import_error` 已删（0 条可达路径）✓ | **PASS**（附 N-5） | ①③ |
| D2-5 | 业务键五段逐字一致 | 五段串 `(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` 命中：CORE 12 / ER 2 / IMPORT 2 / DP 2 / BASE 4，**逐字一致**；`FIELD_MAPPING`、`ROLLBACK` **不陈述该键**（不是"缺某一段"，是整键不出现）；`ROLLBACK` L114 正确使用"四段前缀 g（= dataset_id, record_scope, parent_external_id, external_id）"并标明是前缀 | **PASS** | ④ |
| D2-6 | 哨兵恒 `'-'`；`NULL`/空串作哨兵写法 = 0 | 写法均为「哨兵 `'-'`（**不是 NULL**、不是空串）」（CORE L73/L116/L490、BASE L33/L48）。**无一处把 NULL/空串当哨兵**。C29 ④ 要求"在 `data_dataset` 或常量表声明一次"✓ 已写入 CORE §4.2 L118–120 | **PASS** | ①④ |
| D2-7 | `content_hash` 主规范串逐字；旧 md5 版 = 0 | 主串 `sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))` 命中 CORE 2 / IMPORT 3 / FM 1 / DP 1 / BASE 2。**我自行重算**：内层 `len=77`、`sha1=781f68645c4e…` ✓；完整串 `len=85`、`sha1=9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5` ✓ **与判据完全一致**。`md5` 命中仅用于 `issue_fingerprint`（ALG-1 有意设计），**无旧 md5 版 content_hash** | **PASS** | ①（自行重算） |
| D2-8 | `issue_fingerprint` 六段含 `place_id`；存在 ALG-1 显式声明 | CORE L229–231 `md5(jsonb_build_array(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value)::text) STORED`，六段、`place_id` 在列 ✓；ALG-1 声明 CORE L242–250「两种摘要算法并存是【有意设计】，**不可互换、不可统一**」+ L1522「后人若提出统一，先问：197 条已算指纹怎么办」；DP L92–… 亦声明。`batch_id` **不进指纹** ✓ | **PASS** | ④ |
| D2-9 | `place_grain` 标 V2 既有列，"V2.1.1 新增列"表述 = 0 | CORE §5.0 L315「**不变**（⛔ 非新增）」、§5.2.2 L412「⭐ `place_grain` 是 **V2 既有列**，不是 V2.1.1 新增」+ 附出处 `CORE_DATA_MODEL_V2.md:208` / `V2.1:136/154`；L424「⛔ 不得把 `place_grain` 写成 V2.1.1 新增列」。正则扫全 6 份，**无"新增 place_grain"表述** | **PASS** | ④ |
| D2-10 | ① "新列 +N" 合计数 = 0；② §5.0 逐列覆盖三轮 | ① 正则 `新列\s*[+＋]\s*\d+\|新增\s*\d+\s*列` 在 6 份文件 **命中 0**；CORE L55–59 专门写"关于新增列 +2 的常见误读"并指明 +2 是 V0.2.2 相对 V0.2.1 的增量。② §5.0 L293–318 共 **23 行逐列**登记（增 / 删 / 改名 / 约束变化 + 出处），覆盖 `import_batch` / `source_record`(6) / `historical_place`(3) / name+location `rejected_by` / `source_time_columns`(2) / `data_quality_issue`(8) / `data_dataset`(9 列 + 2 不变) / `data_source`(2)，**不给合计数** ✓ | **PASS** | ④ |
| D2-11 | C01–C29 无缺失无重复；有效条数唯一 | 附录 A L1578–1607：C01–C29 **29 个编号各 1 次**，无重号；L1560–1570 给出**唯一权威计数**：编号 29 − 废除 1（C02）− 双编号 1（C18=C03）= **27 有效**；其中**可落库 24**（= 22 + C25/C26）、**断言级/键级 3**（C27/C28/C29）；L1567 明文"24 与 27 是同一全集的两个子集口径，不是矛盾"。CORE 全文 `C01`–`C29` 全部出现 | **PASS** | ④ |
| D2-12 | 三视图字段名在三份以上文件逐字一致；`inactive_at` / `inactive_in_batch_id` 落点全文统一 | 字段名本身三份一致（11 / 10 / 7 列，CORE §5.10 三节 / BASE §14 三节 / DP §7 三节 / ER 三张卡片 名称逐字相同）。**`inactive_at`/`inactive_in_batch_id` 落点已统一**（都走 `source_record`，CORE/BASE/ER 三处一致）。❌ **但两处不统一**：① ER 图注仍称"CORE §5.10.2 称对外 9 列"（CORE 已是 7 列）；② `is_canonical_row` 定序键 CORE/BASE 6 键 vs IMPORT/DP 4 键（N-2） | **FAIL** | ①④ |

### §3 ER 图与数据模型一致性（9 条）

| ID | 判据摘要 | 实测 | 判定 | 层级 |
|---|---|---|---|---|
| D3-1 | 实体名与 CORE §5 表名逐字一致 | 12 个实体名（9 表 + 3 视图）在图文本中**全部命中**：`data_source` / `data_dataset` / `import_batch` / `source_record` / `historical_place` / `historical_place_location` / `historical_place_name` / `candidate_match` / `data_quality_issue` / `v_place_evidence` / `v_place_liveness` / `v_place_time_span`；大小写与下划线一致 | **PASS** | ①（程序比对） |
| D3-2 | 每个字段名与数据模型逐字一致，**不得出现模型中不存在的字段** | 抽出图内全部 `snake_case` 标识符与 CORE 列名全集双向比对：**不属列名的全部命中都是枚举值**（`a_to_b` / `admin_center_*` / `all_sources_absent` / `mixed_inactive` / `needs_manual_review` / `per_record` / `source_absent` …）、**函数名**（`jsonb_build_array` / `array_length` / `sort_keys` / `ensure_ascii`）、**实体名**。**虚构字段 = 0** | **PASS** | ① |
| D3-3 | `v_place_time_span` 图注写 `<> 'rejected'` + 只聚合 name+location 排除 edge；`'published'` 命中 0 | ER 全文 `published` **命中 0** ✓；第 244 条「⭐ 过滤条件（写死）：`record_status <> 'rejected'` AND `sr.is_active`」；第 246 条「⛔ 只聚合 name + location 两张子表，**排除 edge**（edge 年份=关系存续期，不是地点存在期；量纲错误）」；第 272–274 条图注复述并给 0/19,039 → 17,469/19,039 | **PASS** | ① |
| D3-4 | 行数不得同图混用两个口径 | 第 266 条「① 行数口径声明（全部带口径词，本图不混用两个口径）」：全图行数一律「**预计入库**」（`historical_place` 19,039 / `historical_place_location` 18,101 / `historical_place_name` 47,499 / `data_quality_issue` 12,831 / `data_dataset` 7）；**唯一例外显式标注**：「`source_record` 卡片另注「**隔离后**」…该差额 3 = 被隔离的 3 条源记录（2 CHGIS + 1 Pleiades edge），隔离不删行故两者可以并存」 | **PASS** | ① |
| D3-5 | `source_record` 唯一键标五段；`occurrence_key` = 0 | 第 96 条 text「UQ (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)」；全文 `occurrence_key` **命中 0** | **PASS** | ① |
| D3-6 | 含三视图且 `v_place_evidence` 存在 | 三视图卡片均在（第 205 / 221 / 236 条起），`v_place_evidence` 标「派生视图 · 11 列 · 不是表」 | **PASS** | ① |
| D3-7 | `historical_place` 含 `dataset_id` + `grain_key` | 第 89–90 条：「+ `dataset_id  text NOT NULL → data_dataset   §5.2.1 规则 1 已推翻`」「+ `grain_key   text NOT NULL   按 place_grain 派生（见 CORE §5.5.3）`」，且卡头标 `19,039 · 预计入库 · 无时间列 / 无几何列 / 无失效原因列` | **PASS** | ① |
| D3-8 | `data_quality_issue` 入库口径 12,831 + 三列 | 卡头第 182 条「12,831 · 预计入库 · issue_type 19 值」；三列齐：第 199/200/201 条 `first_batch_id` / `last_batch_id` / `occurrence_count`（含"重复发现时不变 / 置为本批 / +=1"语义） | **PASS** | ① |
| D3-9 | 显式声明 `架构/V2.1/ER_DIAGRAM_V2.1.svg` 已作废 | 双处：`CORE` §5.10.6 L1299–1306「【作废声明】…自本版起作废，不得作为施工依据…照图施工 ⇒ **19,039 个（入库口径）**地点的时间跨度全部为 NULL」；`ER` 图首第 3–5 条 text 同样声明 | **PASS** | ① |

### §4 导入/更新/隔离/合并/回滚规则一致性（12 条）

| ID | 判据摘要 | 实测 | 判定 | 层级 |
|---|---|---|---|---|
| D4-1 | 两文档隔离算法一致 + 四种排列逐步推演自洽 | `IMPORT` §5.1 L258–263 与 `ROLLBACK` §F.5 / `BASE` §2.1 表述同一套规则；`IMPORT` §5.2 给出 ①②③④ 四排列**逐步表**（L274–314）外加 ⑤ 真实混合组与"相同 hash 数量增减"五情形（§5.3）。**我独立实现算法复算**：`A,B,B`→1 / `B,A,B`→1 / `A,B,C`→0 / `A,A,B,B`→2 / `A,A,B`→1，**与文档逐项一致**（⑤ 的分组口径问题见 N-4） | **PASS** | ①（独立复算） |
| D4-2 | ① 不得以 `ordinal = 1` 的 hash 为基准；② 四排列隔离数 = 1/1/0/2；③ 编制辅助件残留旧规则须标留痕 | ① `IMPORT` L267「⛔ **禁止"只比 `ordinal = 1`"**」+ CORE L200 同；`BASE` L101 把"只比较 ordinal=1"标为历史写法+**【留痕】**+ 已被禁用 ✓。② **我用脚本代入验证四排列：1 / 1 / 0 / 2，全部命中判据**（见 §4.1 附脚本输出）。③ `BASE §2.1` 只保留新规则 + 留痕，**无旧规则代码块** | **PASS** | ①（脚本代入） |
| D4-3 | `raw_record_index` 仅用于同 hash 破并列，不得当文件内唯一编号 | CORE §4.3 L189「**只能**在 `content_hash` 完全相等时打破并列，**不参与常规定序**；**不保证文件内唯一**（14 个 `raw_file` 中 7 个不唯一，全为 WHG）⇒ 不得作为定序键或唯一性依据」；`IMPORT` §1.1 / `DP` §4 L84 同口径；`BASE` §2 L90 同。ER 第 74 条「`raw_record_index  integer（不保证文件内唯一）`」 | **PASS** | ④ |
| D4-4 | 判定表含第 0 行"重复检测优先"；七类操作与第 0 行不冲突 | `IMPORT` §6.1 L391「第 0 行：重复检测优先（**先于其余全部 10 行**）」；§6.2 其余 10 行；§6.3「七类操作与第 0 行**不得冲突**」；判定表 11 行 × 7 列（O1–O7）。`ROLLBACK` §3.2.1 的 `quarantine_hold` 成因明确挂"第 0 行 / 第 8 行" | **PASS** | ④ |
| D4-5 | 两组集合互斥穷尽 + 各一组恒等式 + 7 种反例 × 5 件事 | 第 1 组 G1：`input_row_count = N_fail_import + N_quar + N_inserted + N_updated + N_noop + N_blocked`（L179–186）；第 2 组 G2 两行：`N_new = N_quar + N_normal`、`N_normal = N_rolled_back + N_blocked + N_fail_rb + N_noop`（L248–251）；§3.2.2 / §3.3.2 给互斥+穷尽证明。**7 个反例小节（§4.1–4.7）我逐节机器核对，"属哪个集合 / 是否参与回滚 / 是否产生台账 / 是否计入统计 / SQL 复算" 五件事 7/7 齐全**。R1/R2/R2b/R2c 四条断言齐（R2c 记号问题见 N-3） | **PASS** | ①（程序核对） |
| D4-6 | `is_active=false OR inactive_reason IS NOT NULL → N_noop` 不得提前截走本批 `duplicate_quarantine` | §3.4 L296–300：**步骤 0** 先判 `r.inactive_reason = 'duplicate_quarantine' ⇒ N_quar++ 终止`，**步骤 1** 才判历史失效；L319「⛔ 步骤 0 必须在步骤 1 之前，这是本版对 V0.2.2 §2.4.1 判定顺序的**唯一实质性修正**」；§3.5 给**代数证明**（|B|=10，原顺序 G2 右式 10 ≠ N_normal 8 ⇒ 恒等式破裂；R1 差 2） | **PASS** | ①（代数复算） |
| D4-7 | 未落库的写入失败记录不得计入已插入集合 | §3.2.3 L230–241：`N_fail_import ∩ N_inserted = ∅`；`inserted_source_record_ids ∩ {失败行} = ∅`；三条实现约束（失败行无 `source_record_id` ⇒ 不可能进数组；`failed_count` 不得进 `|B|`；A1 断言是可执行形式） | **PASS** | ④ |
| D4-8 | 不得为让恒等式成立而新增/修改台账类型 | CORE L851–852「⛔ **禁止为凑满 20 值而新增替代类型**」；`ROLLBACK` §5.6 三条硬禁止，第 1 条「**不得新增或修改 `data_quality_issue.issue_type` 的任何值**，冻结为 19 值」；§6 亦不得把质量问题归类成回滚问题 ⇒ 19 值在 CORE/FM/ROLLBACK 三处一致 | **PASS** | ④ |
| D4-9 | `STOP_AUTO`：ordinal 无法一一对应 ⇒ 整组 `SKIP_UPDATE` + 复用 `duplicate_external_id` 台账；三份一致 | 判据在三处逐字同一：CORE §4.7 L270「若 `|old| = |new|` 且 `|old ∩ new| < |old| − 1` ⇒ STOP_AUTO」、`IMPORT` §8.3 L591、`DP` L464；实现三条（整组 `SKIP_UPDATE` / 复用 `duplicate_external_id` / `occurrence_count += 1`）在 CORE L274–276 与 `IMPORT` §8.3 一致；`IMPORT` §8.2 还写明 ④ 真交换时**有意不触发**（交集 = |old|） | **PASS** | ④ |
| D4-10 | canonical 统一**外层**定序；每地点至多 1 个；无有效证据不得伪造；315 可追溯不补造；① creator 不得写死 FALSE；② 视图 SQL 无不可执行占位符；③ 定序 `ORDER BY` 引用列必须在视图可见 | ① CORE L920–929 外层 `row_number()` ✓（三处写死常量/占位符已消除）；`BASE` §14.1 同步 ✓。<br>② ❌ **`DATA_PROVENANCE` §7.1 L304 仍有占位符 `<canonical 定序 CORE §5.10.4>`，L290 仍 `FALSE AS is_canonical_row`，L311 仍 `FALSE, FALSE`** ⇒ 交付物内存在不可执行占位符。<br>③ CORE 的 `sr.duplicate_ordinal` / `sr.external_id` 已回连 `source_record` ✓；但 `IMPORT` §10.1 与 `DP` §6.1 的 4 键版**缺 ⓿⑤**，且 IMPORT 断言"不可能并列"与 C08 冲突（N-2）。<br>315 追溯：CORE L1262「唯一证据是 `creator` 行 ⇒ `is_canonical_row=true` 落在它身上…**不需要也不允许制造名称子行**」✓ | **FAIL** | ①（SQL 静态检查） |
| D4-11 | MCGD 按最小 `NameID` 定 canonical；643 个地点按 `parent_external_id` 建点 | CORE §5.5.4 L648「MCGD…`external_id`（`NameID`）**字典序最小的那条**——与 `canonical_name` 同源」、§5.10.4 L1263「MCGD 643 个地点：全部证据 `evidence_role='name'`，定序落到 ③ `external_id` ⇒ 最小 `NameID` ✓」；`IMPORT` §10.4 L676 与 `DP` §6.2 L246 同；① 实测 MCGD `external_id_type='mcgd_nameid'` 960 行、父级 `LocID` 唯一值数 → 643（与 N09 的 19,039 − 643 闭合一致） | **PASS** | ①④ |
| D4-12 | `rejected_by`（`auto`/`manual`）name 与 location 各 1 列，落点一致 | CORE §5.6 L712 / §5.7 L768 各 1 行 + C25/C26 各 2 条（附录 A L1602–1603）；§5.6.1 给四场景 A–D 状态转换表；ER 两张子表卡片各「+ `rejected_by text CHECK IN (auto, manual)`」（4 处 `rejected_by`）；`ROLLBACK` §7 与 CORE §5.6.1「逐字对齐」 | **PASS** | ④ |

### §5 真实数据字段映射覆盖率（6 条）

| ID | 判据摘要 | 实测 | 判定 | 层级 |
|---|---|---|---|---|
| D5-1 | 每个 `staging_column` 真实存在，或标 derived 并说明规则；幽灵列 0 容忍 | **程序比对** `_build/staging_field_inventory.csv`（7 表 / **105 字段**）：非标记类 `staging_column` 全部命中 inventory；`(derived)` / `(generated)` / `(dropped)` 三类豁免。**幽灵列 = 0** | **PASS** | ①（程序比对） |
| D5-2 | 每个 `target_column` 在 CORE 中真实存在 | 非标记类 `target_column` 全部命中 CORE 列名全集（我按 §5.1–§5.9 逐表建白名单）；25 行使用 `(derived)` / `(discarded)` / `(split)` 标记，**逐行核对其 `transform` 或 `notes` 均写明去向**（如 L87 `derived→geom/representative_lon`、L102 `split('|')` + 指出拆成哪三列、L103 `derived→data_quality_issue`、L182 `derived→resolution_note`）；**虚构列 = 0** | **PASS** | ①（程序比对） |
| D5-3 | 暂存被需要的列不得整体遗漏；给覆盖率与遗漏项说明 | 105 / 105 字段**全部在映射中出现**（覆盖率 **100%**）；其中 26 行判 `(dropped)` 且**逐行说明是有意丢弃**（含 `homepage`、`license_*`、`acquisition_method`、`evidence`、`source_dataset`、`primary_external_id`、`time_derivation`、`geom_wkt` 等），无"映射缺失"项 | **PASS** | ① |
| D5-4 | `data_dataset` 的 9 列许可相关映射已全部删除且无替代列 | FM L5–L11、L14–L17 共 11 行落 `data_dataset.(dropped)`（覆盖 9 个许可列 + `homepage` + `acquisition_method` + `evidence`），每行带【留痕】并写明"⛔ 无替代列 / 不得改落到 notes / 不得改指 data_source"；`data_dataset` 剩余映射行**无任何许可列** | **PASS** | ① |
| D5-5 | 不得为凑覆盖率凭空补行 | 每行 `staging_column` 均可回溯到 inventory 实名（或标 derived/dropped）；`transform` 列逐行给规则（`direct` / `literal` / `literal_table` / `rule` / `split` / `sha256_file` / `identity` …），**无手写猜测行** | **PASS** | ① |
| D5-6 | 七张 CSV 实测行数与 V0.2.2-r2 §0 一致 | **我逐文件数行**（`for line in fh`）：`source_records` **29,391** / `historical_places` **19,039** / `historical_place_names` **47,503** / `historical_place_locations` **18,103** / `candidate_matches` **53,137** / `data_quality_issues` **12,631** / `data_datasets` **7** —— **7/7 全部命中**；字节数亦与 CORE §9.1 表逐项相同（4,953,976 / 11,698,567 / 8,937,942 / 26,942,777 / 17,315,204 / 5,277,273 / 6,018） | **PASS** | ① |

### §6 统计口径与未验证事项（8 条）

| ID | 判据摘要 | 实测 | 判定 | 层级 |
|---|---|---|---|---|
| D6-1 | 每个统计数字带口径词；表格列头已声明者合格；正文孤立行数即 FAIL | 表格侧全部合格（CORE §9.1 列头「**暂存原始**行数」、§9.2 列头「**暂存原始** / **隔离后 / 预计入库**」、ER 全图统一"预计入库"）。**正文侧有 FAIL**：`ROLLBACK` L113「47,499 条名称 + 18,101 条位置 + 29,391 条源记录，全量历史会变成数十万行」——**4 个孤立行数、无口径词**；`IMPORT` L220 `V3' … == 19,039`、L657「`V3' = 19,039` 的基数」同样无口径词。其余被扫出的行多为 `envelope` 分项或 `= 合计` 算术闭合（L148/L155/L162/L384/L421 等），按豁免条款合格 | **FAIL** | ①④ |
| D6-2 | 权威数字表 N01–N18 与 V0.2.2 §0 逐项一致 | CORE §9.2 L1438–1457 列 N01–N18。**我用 ① 交叉验证了 4 个可算项**：N04 `duplicate_ordinal=0` = **29,377**（我按五段键分组实测：7 组重复 / 14 行 ⇒ 29,391 − 14 = 29,377 ✓）；N09/N10 `record_scope` place **18,398** / name **5,762** / location **2,468** / edge **2,763**（我派生后实测逐项吻合 ✓）；N17 三段键 398 组 / 2,335 行 vs 五段键 7 组 / 14 行（**我实测 398 / 2,335 与 7 / 14，差两个数量级 ✓**）；N08 12,631 − 2 + 5 + 197 = 12,831 ✓。N02/N06/N07/N08 的差项与各源份额表内部闭合 | **PASS** | ① |
| D6-3 | 不得直读暂存 `valid_from/to_year_astro` 判 `derivation_kind`/`no_evidence`；须有显式告警 | CORE §6.3 L1365–1366 **H2 告警**：「必须基于「只聚合 name + location、排除 connection」的重算结果；**不得直接引用暂存**…会使 `no_evidence` **系统性偏低 65**（1,505 + 65 = 1,570）」；§11.1 L1547 再述；`IMPORT` §13 H2、`DP` §… 同。全文"排除 connection"4 处 | **PASS** | ④ |
| D6-4 | `candidate_match` 不进权威数字表；列 U18 + 给 53,137 / 53,103 与被排除行来源 | CORE §9.4 L1484–1489 独立成节并**在节内明令**「不得写入 §9.2 的 N01–N18」；§9.1 表内该行标「**53,137**（登记项，见 §9.4）」；§5.8 L815「暂存 **53,137** / 隔离后 **53,103** 是**登记项 U18，待 Owner 拍板**…34 行 / 33 个键…应扣 34 ⇒ 53,103」；附录 B `U18` 单列。`ER` 第 213 条亦标「行数不进权威数字表（U18 待 Owner 拍板）」 | **PASS** | ①④ |
| D6-5 | 无子行源记录采用口径 A 8,682；8,218 定义口径 B；不得混用 | CORE N12 L1451「**8,682**（**口径 A**）… **口径 B** = **8,218**；差 464 = place 74 + edge 390。**钉死口径 A**」；`DP` L… 同（8,682 两处 / 8,218 一处 / 口径 A、B 各标注）。其余文件不引用该数（不构成混用） | **PASS** | ④ |
| D6-6 | 12 项 WARN + 13 项未验证逐条保留，单列清单，不得写成 PASS/已解决 | CORE 附录 B：B.1「V0.2.2 §5.3 未解决/未验证清单（10 项）」、B.2「标注未验证的断言（逐条）」、**B.3「12 项 WARN（逐条保留，均未关闭）」L1656–1671 共 12 行**、B.4 新增 V-1…V-10。L1614–1616 计数说明「PASS 37 / FAIL 0 / WARN 12 / 未验证 13」并警告"不得只抄 PASS 35 / FAIL 1"；L1688 收尾「**本文件不宣布通过**」。`IMPORT` §12 / `ROLLBACK` §11 / `DP` §… 各自保留并均未写 PASS | **PASS** | ④ |
| D6-7 | 施工验证清单至少含 U3/U4/U5/U12/U13/U14/U15/U16/U18 + `is_canonical_row` 逐行相等 | 逐项命中：`U3`✓ `U4`✓ `U5`✓ `U12`✓ `U13`✓ `U14`✓ `U15`✓ `U16`✓ `U18`✓（CORE 附录 B.1 L1620–1632，另 `U19` 亦保留）；`is_canonical_row` 与暂存 `canonical_name` 是否逐行相等 → **B.4 V-2** L1678「两者是不同机制…**未验证**」✓ | **PASS** | ④ |
| D6-8 | 两条硬提醒显式出现在文档正文 | **H1**（`normalize.py:306` 改动必须回归 `content_hash`）：CORE §4.4 L222 + §11.1 L1534（`normalize.py:306` 在 CORE 命中 6 次）、`IMPORT` §13、`DP` L…（3 次）；**H2**（`derivation_kind`/`no_evidence` 不得直读暂存时间列）：CORE L1547、`IMPORT`、`DP` 均有独立小节 | **PASS** | ④ |

### §7 工程边界（7 条）

| ID | 判据摘要 | 实测 | 判定 | 层级 |
|---|---|---|---|---|
| E1 | `架构/CORE_DATA_MODEL_V2.md` 未改动 | 128,784 B / `91b459a8070364df`，与 §9 基线一致 | **PASS** | ①（自算哈希） |
| E2 | `架构/V2.1/` 八份未改动 | 逐一核对 8 份（CORE 70,016 `ec118b60638244c8` / IMPORT 25,677 `6cbcefedc212ec2d` / ER 28,295 `3853eeba963b3501` / FIELD_MAPPING.csv 25,625 `50fca40335f40066` / FIELD_MAPPING.md 7,577 `043ba35adb7fb7ac` / ROLLBACK 15,078 `efb934d94bed9aac` / LICENSE_GATE 16,040 `b2ab5754eeff475d` / QA_REPORT 14,164 `b30eeb24b061b449` / CHANGELOG 15,601 `acf35d865cc3d68a`）**全部一致** | **PASS** | ① |
| E3 | `V2.1.1/V0.2.2/` 全部未改动 | `00_PROBLEM_LIST_AND_PLAN_V0.2.2.md` 105,526 `0356ff721a7fb4f1` ✓；`V0.2.1_TO_V0.2.2_CHANGELOG.md` 69,320 `881087457b59d38a` ✓ | **PASS** | ① |
| E4 | `V2.1.1/00_PROBLEM_LIST_AND_PLAN.md`（V0.2.1）未改动，mtime 仍 17:43:53 | 190,222 B / `0a9c56fbfc002769` ✓；`ls` 显示 `Nov 2 17:43` ✓ | **PASS** | ① |
| E5 | 七张暂存 CSV 未改动 | 7 份逐一核对，字节与哈希**全部一致**（`fa44197e54b4da4a` / `30fed0e40ba12496` / `86db3ce6b94f9e31` / `80674c0ded553241` / `9e987ba578e933ed` / `4e29c2ec64ebe263` / `7a8ab3916e00dcb0`） | **PASS** | ① |
| E6 | `normalize.py` 未改动 | `code/p0/wb-002-normalize/normalize.py` 102,275 B / `4a0a6fed7f656de5` ✓ | **PASS** | ① |
| E7 | 未产生 DDL / Migration / Docker 建库 / 导入 / 产品代码修改 / Git 操作 | 全树检索 `*.sql` / `*.ddl` / `Dockerfile*` / `*.migration`：**0 命中**；`正式交付/` 只多出 `_build/`（编制辅助）；本轮我未执行任何 Git 命令、未连接任何数据库 | **PASS** | ① |

### §4.1 附：四排列隔离数脚本输出（D4-2② 的证据）

```
排列        排序后                      保留                     隔离                   隔离数  期望  判定
A,B,B     [(1,A),(2,B),(3,B)]        [(1,A),(2,B)]          [(3,B)]                    1     1   PASS
B,A,B     [(1,A),(2,B),(3,B)]        [(1,A),(2,B)]          [(3,B)]                    1     1   PASS
A,B,C     [(1,A),(2,B),(3,C)]        [(1,A),(2,B),(3,C)]    []                         0     0   PASS
A,A,B,B   [(1,A),(2,A),(3,B),(4,B)]  [(1,A),(3,B)]          [(2,A),(4,B)]              2     2   PASS
A,A,B     [(1,A),(2,A),(3,B)]        [(1,A),(3,B)]          [(2,A)]                    1     1   PASS
```
（独立实现：按 `(content_hash ASC, raw_record_index ASC)` 定序 → 赋 ordinal 1..n → 每个 hash 子组保留最小 ordinal、后续隔离。未使用文档给出的结论。）

---

## 4. 判定计数

| 分类 | 条数 | PASS | FAIL | PARTIAL/未验证 |
|---|---:|---:|---:|---:|
| §1 八份完整性（D1-1…6） | 6 | 2 | 2（D1-1、D1-6） | 1（D1-5）+1 内部冲突注 |
| §2 跨文档一致性（D2-1…12） | 12 | 11 | 1（D2-12） | 0 |
| §3 ER 一致性（D3-1…9） | 9 | 9 | 0 | 0 |
| §4 规则一致性（D4-1…12） | 12 | 11 | 1（D4-10） | 0 |
| §5 字段映射（D5-1…6） | 6 | 6 | 0 | 0 |
| §6 统计口径（D6-1…8） | 8 | 7 | 1（D6-1） | 0 |
| §7 工程边界（E1…E7） | 7 | 7 | 0 | 0 |
| **合计** | **60** | **54** | **5** | **1** |

**前两轮 16 项**：CLOSED **12** / PARTIAL **4**（F-03、F-04、F-11、W-02）/ STILL-FAIL **0**
**本轮新发现**：FAIL **2**（N-1 施工级、N-2 规格互斥）+ WARN **8**（N-3…N-10）+ 快照漂移（§0.2，判定阻断项）

> **冻结后复核（§0.5）**：team-lead 下发的 7 个新快照 **7/7 命中**、mtime 全部停在 10:32 及以前（冻结生效）。本报告全部判定**本来就在这一版上做出**，换版不改变任何结论；冻结版上全文重跑亦一致。**计数维持 PASS 54 / FAIL 5 / PARTIAL 1 不变。**
> 同时我按"不采信转报"逐条验证了架构师这两处改动（§0.5.2 / §0.5.3）：**「时间戳」明示成立**（2 处出处 `V2:387` / `V2:350` 逐行核对为真，且顺带修掉一个潜在 D5-2 风险）；**5 处 `updated_at` 核实依据成立**（`V2:215/309/350/387/419` **5/5 逐行核对为真**，第 6 处仍正确判 `(dropped)`）。**无回归**：221 数据行 / 26 dropped 全带留痕 / 幽灵列 0 / D5-2 零不符。

---

## 5. 结论与放行判断

### 5.1 是否达到"可提交 Owner 验收"的质量

> **没有达到。** 判据 60 条中 **5 条 FAIL、1 条 PARTIAL**；按判据纪律「任何 FAIL 不得宣布通过」，本报告**不宣布通过**。

**阻断项（必须关闭才能提交）**：

| # | 阻断项 | 性质 | 修复量 |
|---|---|---|---|
| **B-1** | `DATA_PROVENANCE` §7.1 的 `v_place_evidence` SQL 仍是**未修版本**（`FALSE AS is_canonical_row` + `<canonical 定序 CORE §5.10.4>` 占位符），§7.2 的 `v_place_liveness` **缺 `JOIN source_record`** | 施工级：两段 SQL **不可编译**；且该节自称"与 CORE §5.10 逐字一致"是反向陈述 | 把 CORE §5.10.1 / §5.10.2 的 SQL **整段替换过来**（约 90 行），并改 §6.1 定序为 6 键。**一处修完即关闭 F-03 / F-04（部分）/ F-11 / D4-10 / D2-12 的一半** |
| **B-2** | `ER_DIAGRAM` 三处陈旧/矛盾：① 图注称"CORE §5.10.2 对外 9 列"（已改 7 列）；② `data_source` 卡片称"另有 2 列许可默认值…**去留待下轮裁定**"（CORE 已**删除**、且未标【留痕】）；③ 称 CORE §5.1 声明"无变化"（CORE 明令不再用该措辞） | 结构层 + 口径级：ER 是"唯一有效 ER 图"，照图施工会保留 2 个已删列、并再次引入 9 列口径 | 改 3 处文字（<10 行） |
| **B-3** | `is_canonical_row` 规格在 CORE/BASE（6 键）与 IMPORT/DP（4 键）之间**四套并存**，且"零有效证据"结论**互斥**（CORE：落定序第一行 vs IMPORT：全 FALSE） | 规格级互斥：实现者按任一份做都可自证"符合文档" | 统一为 CORE 的 6 键 + CORE 的零证据处理；IMPORT §10.1/§10.2、DP §6.1 各改 ~8 行 |
| **B-4** | 6 行空 `source_record_id` 台账的 `dataset_id`/`place_id` **双双不可派生** ⇒ C11 必然被违反（N-1） | 施工级：12,831 台账里 6 行无法入库 | 需裁定（恢复"图层键→dataset_id"映射 / 改 N08 为 12,825 / 新增文件级台账形态） |
| **B-5** | **快照口径与冻结状态**：team-lead 已宣布冻结（§0.5.1 复核：7/7 命中、mtime 未再动）。**残留 3 件事**：① `FIELD_MAPPING` L218 引用的 CORE 哈希 `a00084c26543b308` **已失效**（现 `c0422f679ceb88c3`）；② 行数存在 **LF / split 两套口径**（CORE 1,693 vs 1,694；FM 222 vs 223），须择一钉死；③ team-lead 表把 FM 写成「223 行（221 数据+表头）」算术不符（221+1=222） | 流程级：快照机制是判据 §0 的地基 | 删 L218 硬编码哈希 → 统一 LF 口径 → 快照表加一句"末尾有换行符" |

**非阻断但应一并修（低成本，可同批处理）**：
- D1-5③ 9 处补【留痕】：`CORE` L317 / L322 / L332 / L334 / L353 / L354 / L357 / L1387、`IMPORT_RULES` L117；
- D1-6：`ER` 的 `<desc>` 加一句权威依据；`DATA_PROVENANCE` 首部加"权威来源"行；D1-6 判据注明 CSV 豁免；
- D6-1：`ROLLBACK` L113、`IMPORT` L220 / L657 补口径词；
- N-3：R2c 的 `:R` → `:Rb`（CORE 附录 B 同步）；
- N-4：`98909/20469` 的"3 行混合组"改写为"父级 98909 组内 A,A + 父级 98930 另一组"；
- N-5：`issue_type` 19 值补"暂存实测行数 / 空集说明"列；
- N-6：`ER` 恢复子表枚举字面量 `published`（并把 D3-3 的扫描范围限定到 `v_place_time_span` 图注）；
- N-7：`<本批>` → `:batch_id`；
- **N-9**：`ER` 的 name 卡片裸「时间戳」→ `created_at + updated_at`（与 CORE L709/L767 对齐，1 个词）；
- **N-10**：`CHANGELOG §A.4` 行数口径与 team-lead 表统一（LF 口径，FM = 222 = 1 表头 + 221 数据）+ L136 的 `12,831` 补口径词；
- D1-1：`V2.1.1_QA_REPORT.md` 需落到交付根目录（本报告现位于 `_build/`，按 D1-2 不计入交付物）。

### 5.2 一句话给 team-lead

**"12 项已真关闭、4 项只修了一半；半修的那 4 项全部集中在 `DATA_PROVENANCE` 和 `ER 图` 这两份没参加过前两轮修正的文件里，改法是把 CORE 已修好的段落整段搬过去。冻结已生效、新快照 7/7 命中，你这两处改动我逐条核过出处、全部为真——剩下的是把 DP 的 SQL 整段换掉、ER 改 4 处文字（含裸'时间戳'），就能进终审。"**

---

## 6. 判定纪律自查

- 本报告 60 条**逐条判定，无跳过、无合并**（含 §0.0 指出的 3 组泛化/特殊化：D2-12 与 D3-3 各判、D6-1 与 D3-4 各判、D4-1 与 D4-2 各判）。
- 来源层级：结论全部落在 **①（我自己的 CSV 复算 / 哈希自算 / 脚本代入 / XML 实解析）** 或 **④（判据与基线定义）**；**未把 ②③ 直接当结论**。凡架构师转报的数（如 `12,631` 只 3 处、`external_id_type` 11 种、`7 组/14 行`、`398 组/2,335 行`、`29,377`）我都回到 ① 重算了一遍，全部吻合；`197` 未被误当作台账总数。
- 未修改任何被检文件、V2 / V2.1 / V0.2.2-r2、七张 CSV、`normalize.py`；未写 DDL / Migration / 未建库 / 未导入 / 未做 Git 操作（E1–E7 全部 PASS，见 §3）。
- **对被检方声明的处理**：team-lead 与架构师转报的每一条事实我都回到 ① 重算——`12,631/12,831` 的口径（§0.5.5 裁决为 **3 行 / 8 次，"7 处"不成立**）、5 处 `updated_at` 的 V2 出处（`215/309/350/387/419` 逐行核对 **5/5 为真**）、2 处「时间戳」出处（`387/350` 为真）、`external_id_type` 11 种、7 组/14 行、398 组/2,335 行、29,377、七张 CSV 行数。**未因"架构师说 3 处"就直接采信，也未因 team-lead 说"你报 7 处"就自我改口。**
- 无法验证的**不伪装**：我未保留 144,265 B 那一版的字节副本，故**无法做版本间逐字 diff**，只能声明"当前冻结版上全部判定已重跑、结论不变"（§0.5.4）。
- **本文件不宣布通过。**
