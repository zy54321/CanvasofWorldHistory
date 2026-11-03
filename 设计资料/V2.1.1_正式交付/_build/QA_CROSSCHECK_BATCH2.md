# QA_CROSSCHECK_BATCH2 —— V2.1.1 五份交付物独立交叉检查

> **判定者**：QA 工程师 Edward（独立交叉检查，第 2 批）
> **判定时间**：2026-11-03
> **本轮范围**：仅 5 份（`CORE_DATA_MODEL_V2.1.1.md` 正在被另一架构师修改，本轮**不检查**）
> **纪律**：任何 FAIL 不宣布通过；未验证不伪装 PASS；②③ 不作结论，须回 ①/④ 核实；不做纯关键词扫描，逐条核语义。
> **本报告不宣布通过。**

---

## 0. 五份文件快照（自行重算，未采信转报值）

口径：`sha256(open(path,'rb').read())[:16]` + 原始字节数 + mtime

| 文件 | 字节数 | 行数（splitlines） | sha256[:16] | mtime | 与 team-lead 转报值 |
|---|---:|---:|---|---|---|
| `IMPORT_RULES_V2.1.1.md` | 49,703 | 763 | `ba377a063edfe2cc` | 2026-11-02 22:20:16 | **一致** |
| `FIELD_MAPPING_V2.1.1.csv` | 39,553 | 221 | `4032e9f5b36c9347` | 2026-11-02 22:37:07 | **一致** |
| `DATA_PROVENANCE_V2.1.1.md` | 33,584 | 502 | `13c5bea3d99e2b6b` | 2026-11-02 22:45:36 | **一致** |
| `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md` | 74,712 | 1,060 | `f45546fea7f5e72e` | 2026-11-03 08:17:24 | **一致** |
| `ER_DIAGRAM_V2.1.1.svg` | 60,010 | 456 | `1b8b62ca0317851f` | 2026-11-03 09:15:11 | **一致** |

> **行数口径说明**：`wc -l` 报 763/221/502/1060/456，因五份文件均**以换行符结尾**（`endswith(b'\n')=True`），`splitlines()` 与 `wc -l` 一致；team-lead 转报的 764/222/503/1061/457 为「行数 +1」口径（按行数计数含末尾空行）。**差异仅口径，字节数与哈希全部一致，不构成缺陷**，但建议后续统一用 `wc -l` 以免反复对齐。

### 参照文件快照（只读，本轮未改动）

| 文件 | 字节数 | sha256[:16] | 与 ACCEPTANCE §9 基线 |
|---|---:|---|---|
| `架构/CORE_DATA_MODEL_V2.md` | 128,784 | `91b459a8070364df` | **一致** |
| `架构/V2.1/` 十份 | 见 §7 | 全部一致 | **一致** |
| `V2.1.1/V0.2.2/` 两份 | 105,526 / 69,320 | `0356ff721a7fb4f1` / `881087457b59d38a` | **一致** |
| `V2.1.1/00_PROBLEM_LIST_AND_PLAN.md` | 190,222 | `0a9c56fbfc002769` | **一致**（mtime 17:43:53） |
| 七张暂存 CSV | 见 §7 | 全部一致 | **一致** |
| `code/p0/wb-002-normalize/normalize.py` | 102,275 | `4a0a6fed7f656de5` | **一致** |

---

## 1. 机械核验复核结果（不采信转报，逐条独立重算）

### 1.1 FIELD_MAPPING 行分类（重算）

| 类 | 转报 | 我的重算 | 判定 |
|---|---:|---:|---|
| 数据行总数 | 220 | **220** | 一致 |
| 真实命中实测字段（`staging_column` 在实测列头中） | 86 | **86** | 一致 |
| 标 `(derived)` / `(generated)` | 109 | **109**（`(derived)` 88 + `(generated)` 21+5） | 一致 |
| `(dropped)` 行 | 25 | **25** | 一致 |
| **幽灵列**（`staging_column` 在对应 CSV 中不存在且未标 derived） | 0 | **0** | **PASS** |

> 精确拆分（供追溯）：`staging_column` 为 `(derived)`=88、`(generated)`=26、真实列=106（其中 86 映射 / 19 dropped / 1 dropped-generated）；`(none)` 表 = 26 行全部 `(generated)`。

### 1.2 M1 正则复核

`^(attribution|citation|license)_` 作用于 `target_column` → **命中 0**（与转报一致）。

**但发现更严重的问题**：正则只扫 `target_column` 会漏掉 `target_table` 层面的检测——第 217 行（`L217`）的 `target_column` 已被写成字面量 `(dropped)`，其原目标列名只存在于 `notes` 中。这不是本判据的漏洞（该行处置正确），但说明**单靠 M1 正则不足以证明「许可列已清零」**。我已改用「全表逐处语义核查」（见 §2 D1-5）。

### 1.3 已知遗漏：`source_time_columns` 缺失 —— **确认成立，判 FAIL**

| 项 | 实测 |
|---|---|
| `FIELD_MAPPING_V2.1.1.csv` 中 `source_time_columns` 命中数 | **0**（`grep -c` = 0） |
| `FIELD_MAPPING_V2.1.1.csv` L110 `target_column` | `source_rule_vocabulary`（**旧名**） |
| `FIELD_MAPPING_V2.1.1.csv` L102 | `time_rule_code → (split)`，notes 明确写「拆成 `source_beg_rule` / `source_end_rule` / `source_rule_vocabulary` 三列，见下三行」 |
| `CORE_DATA_MODEL_V2.1.1.md` L306 / L671 | `historical_place_location.source_rule_vocabulary` → **改名** `source_time_columns` |
| `CORE_DATA_MODEL_V2.1.1.md` L307 / L728 | `historical_place_name.source_time_columns` —— **新增列**，`text NOT NULL DEFAULT ''` |
| `CORE_DATA_MODEL_V2.1.1.md` L684 / L1475 | **C13** = `CHECK (source_time_columns = '' OR (source_beg_rule IS NULL AND source_end_rule IS NULL))` |
| `ER_DIAGRAM_V2.1.1.svg` L258 | `source_rule_vocabulary  text NOT NULL DEFAULT ''`（**旧名**） |
| `historical_place_names.csv` 侧 | L134 `time_rule_code → (split)`，notes 写「全部进 vocabulary（目标表不设 smallint 列）」——**目标列不存在** |

**三重断裂**（这是本轮最严重的发现，比转报的「一行旧名」更严重）：

1. **改名未同步**：CORE §5.0 裁定 `source_rule_vocabulary → source_time_columns`（改名），但 `FIELD_MAPPING_V2.1.1.csv` L110 与 `ER_DIAGRAM_V2.1.1.svg` L258 仍是旧名 ⇒ 施工者照映射表/照图建库，会建出 `source_rule_vocabulary` 列，而 CORE §5.6 的 **C13 约束引用 `source_time_columns`** ⇒ **DDL 直接编译失败**（引用不存在的列）。
2. **name 表新增列完全缺失**：CORE §5.7 L728 要求 `historical_place_name.source_time_columns`（`NOT NULL DEFAULT ''`，收纳 2,074 行掩码）；`FIELD_MAPPING_V2.1.1.csv` **无任何行产出该列**，`historical_place_names.csv` 的 `time_rule_code`（L134）标 `(split)` 但其 notes 指向的「vocabulary」目标列不存在 ⇒ **这 2,074 行掩码会静默丢失**，正是 CORE §5.7 明言要避免的后果。
3. **L134 notes 自相矛盾**：写「目标表不设 smallint 列，全部进 vocabulary」，但 name 表既无 `source_beg_rule`/`source_end_rule`（正确），也无 `source_time_columns`（**缺失**）⇒ 「进 vocabulary」无落点。

| 判据 | 判定 | 依据 |
|---|---|---|
| **D5-2**（每个 `target_column` 在 CORE 中真实存在） | **FAIL** | L110 `source_rule_vocabulary` 在 CORE `historical_place_location` 列清单中**零命中**（CORE 已改名）；CORE §5.7 的 `source_time_columns` 在映射表**零产出** |
| **D2-12**（三视图/字段跨文档逐字一致） | **FAIL** | 同一列在三份文件里两个名字（CORE 用新名、FM/SVG 用旧名），属「两处各写一套」 |
| **D3-2**（ER 图字段与数据模型逐字一致） | **FAIL** | `ER_DIAGRAM_V2.1.1.svg:258` 写 `source_rule_vocabulary`，CORE §5.6 写 `source_time_columns` |

**修正建议（不改文件，仅建议）**：
- `FIELD_MAPPING_V2.1.1.csv` L110：`target_column` 改 `source_time_columns`；notes 保留旧名并加「V2.1 旧名，V2.1.1 改名」。
- `FIELD_MAPPING_V2.1.1.csv` 需**新增 1 行**：`historical_place_names.csv,time_rule_code → historical_place_name.source_time_columns`（或改 L134 的 `(split)` 处置为两行产出：location 三列 + name 一列）。**注意**：新增行不得违反 Owner「不得手写猜测」——该列的派生规则已在 CORE §5.7 与 V0.2.1 §2.7.1 写死，属转录而非猜测。
- `ER_DIAGRAM_V2.1.1.svg` L258：改 `source_time_columns`；并在 `historical_place_name` 卡片补一行 `+ source_time_columns text NOT NULL DEFAULT ''`。
- **连带**：`IMPORT_RULES_V2.1.1.md` 与 `DATA_PROVENANCE_V2.1.1.md` 未出现该列名，本身不算缺陷（非必列字段），但 §5.0 的改名若不同步，三份文件的「同一列」表述将永久分裂。

---

## 2. 逐条判定

### 2.1 §1 八份交付物完整性（本轮涉 4 条）

```
[D1-1] 八份文件全部存在，文件名逐字
  快照：五份见 §0
  实测：正式交付/ 根目录实列 5 份（其余 3 份不在本轮范围，其中 CHANGELOG / QA_REPORT 尚未产出）
        本轮 5 份文件名逐字正确（含 .md/.csv/.svg 扩展名与 V2.1.1 版本段）
  判定：PASS（仅就本轮 5 份）
  来源层级：①目录实测
```

```
[D1-2] 无第九份越界文件混入
  快照：正式交付/ 根目录
  实测：根目录仅 5 份 + `_build/`（编制辅助目录，判据明示不计入）
        我在核查过程中产生的临时文件 `_build_ercards_tmp.txt` 已删除，收尾时根目录恢复为 5 份 + _build/
        `_build/` 内含 16 张 PNG 预览图（_c1/_c2/_c3/_cA/_crop_*/_er_preview/_full_small 等）与 2 个脚本、
        1 个 inventory CSV —— 均属编制辅助件，非交付物
  判定：PASS
  来源层级：①目录实测
```

```
[D1-3] ER_DIAGRAM_V2.1.1.svg 是格式良好的 XML —— 【team-lead 要求实际用解析器加载】
  快照：sha256[:16]=1b8b62ca0317851f / 60,010 B / 456 行
  实测：**实际执行** `xml.etree.ElementTree.parse('ER_DIAGRAM_V2.1.1.svg')`
        → **解析成功，无异常**
        root tag = `{http://www.w3.org/2000/svg}svg`
        root attrib = `viewBox="0 0 1720 2170"` `width=1720` `height=2170` `role="img"`
        `aria-label="Core Data Model V2.1.1 ER diagram: 9 tables plus 3 derived views"`
        元素统计：<title>1 / <desc>1 / <text> 283 个 / <g> 14 个 / <path> 若干 / <defs> 含 3 个 <marker>
        另用 `ElementTree.iter()` 遍历全部文本节点成功，共 283 个，无畸形转义
        （`&lt;&gt;` 用于显示 `<>`，属正确转义；`role`/`aria-label` 齐全）
  判定：**PASS**
  来源层级：①解析器实测（非估算）
```

```
[D1-4] FIELD_MAPPING 列头与 V2.1 逐字一致
  快照：FM sha256[:16]=4032e9f5b36c9347；V2.1/FIELD_MAPPING_V2.1.csv sha256[:16]=50fca40335f40066
  实测：两份文件首个物理行**原始字节完全相同**：
        b'\xef\xbb\xbfstaging_table,staging_column,target_table,target_column,target_type,required,transform,enum_rule,notes'
        · 均带 UTF-8 BOM（EF BB BF）· 均为 CRLF 行尾 · 9 列逐字相同、顺序相同
  判定：PASS
  来源层级：①原始字节比对
  附注：BOM 导致 `csv.DictReader` 若用 `encoding='utf-8'` 会把首列名读成 `'\ufeffstaging_table'`。
        本次核查用 `utf-8-sig` 读取正确。**建议施工方注意此点**，但 V2.1 同样带 BOM ⇒ 不构成两版差异。
```

```
[D1-5]（V1 修订，三层判定）八份不含许可/授权管理功能
  快照：五份见 §0
  ── ① 功能层（硬）：LICENSE_GATE 命中数 = 0 ──
  实测：IMPORT_RULES 0 / FIELD_MAPPING 0 / DATA_PROVENANCE 0 / ROLLBACK 0 / ER_DIAGRAM 0
        → **五份全部 0**
  ── ② 结构层（硬）：target_column / 表列定义不得出现许可列 ──
  实测：`target_column` 命中 `^(attribution|citation|license)_` = **0**
        ER 图九张卡片无任何许可列（已按卡片区域逐字段抽取，见 §3 D3-2）
        → **结构层 PASS**
  ── ③ 字面层（豁免）：允许出现在四类语境，但必须逐处标【留痕】 ──
  实测（逐处语义核查，非关键词计数）：
    · FIELD_MAPPING 命中 6 处，**全部位于 `target_column=(dropped)` 行**：
      L5 notes 提 license_url｜L6 license_id｜L7 license_url+license_evidence｜L8 redistributable+license_id
      L9 attribution_text｜L10 license_evidence｜L11 license_evidence｜L14 attribution_text
      L39 license_status｜L40 redistributable｜L41 attribution_text
      —— 这 11 处全部在「已删除列清单」语境（`target_column` 字面量 `(dropped)`，notes 以
      「V2.1.1 删除 / 目标列已删 / 判为有意丢弃」开头）⇒ **语境合法**
      **但这 11 处无一处标注【留痕】**（`grep -c '【留痕'` = 0）
    · ER_DIAGRAM 命中 1 处（L282 附近 `issue_type` 卡片：「本版删去 1 个许可类值【留痕】」）⇒ **已标**
    · CORE 命中 29 处【留痕】（CORE 不在本轮 5 份范围，但其 §5.2 已整体标『本表整体标【留痕】』）
    · IMPORT_RULES / DATA_PROVENANCE / ROLLBACK：三类词命中均为 0
  判定：**FAIL（字面层）**
        ① 功能层 PASS　② 结构层 PASS　③ 字面层 **FAIL**
        理由：判据原文「带【留痕】标记者不计命中；**未标【留痕】者计 FAIL**」。
              `FIELD_MAPPING_V2.1.1.csv` 的 11 处（L5–L14、L39–L41）语境合法但**未逐处标注【留痕】**。
  来源层级：①逐行实测 + 语义判读
  说明：这不是「许可功能回归」——表里没有任何许可列，处置全部正确。这是**留痕纪律的机械性缺失**，
        风险等级低于 D5-2，但判据是硬性的，不得不判 FAIL。
  修正建议：在 L5–L14、L39–L41 的 notes 末尾统一追加 `【留痕：已删除列清单】`。
            注意 CSV 单元格内不要引入裸逗号（须用引号或改用「；」）。
```

```
[D1-6] 每份文件首部声明版本号 V2.1.1 + 声明以 V0.2.2-r2 为权威依据
  快照：五份见 §0
  实测：
    · IMPORT_RULES L3「**版本**：2.1.1」；L5「**权威来源**：`V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md`（**V0.2.2**，1,127 行）> …」；L9 效力顺序 V0.2.2 > V0.2.1 > V2.1 > V2
    · ROLLBACK L3「**版本**：2.1.1」；L5「**权威依据**：`V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md`（下称 **V0.2.2**，1,127 行）」；L9 效力顺序
    · DATA_PROVENANCE L1「# 数据来源追溯 DATA_PROVENANCE V2.1.1」；**但首部无「权威依据 / 以 V0.2.2-r2 为准」声明**
      （`V0.2.2` 在全文出现 10 次，但首部 L1–L5 只有一句「本文是 V2.1.1 八份交付物之一」）
    · ER_DIAGRAM `<desc>`「V2.1.1 模型 ER 图。取代并作废 架构/V2.1/ER_DIAGRAM_V2.1.svg。字段名与 CORE_DATA_MODEL_V2.1.1.md 第 5 节逐字一致。」—— 有 V2.1.1、有作废声明，**无 V0.2.2 权威依据声明**
    · FIELD_MAPPING 是 CSV，**无任何文件首部/注释行**（首行即列头）
  判定：**WARN**（不判 FAIL 的理由见下）
        · IMPORT_RULES / ROLLBACK：PASS
        · DATA_PROVENANCE / ER_DIAGRAM：版本号有、权威依据声明缺失 ⇒ **WARN**
        · FIELD_MAPPING：CSV 无承载位置 ⇒ **WARN（判据与格式冲突）**
  来源层级：①文件头实测
  语义判定：判据「每份文件首部声明…以 V0.2.2-r2 为权威依据」对 **CSV 格式不可执行**（CSV 首行必须是列头，
            加注释行会破坏 D1-4 的逐字列头判据）。故此项**判据本身有缺陷**，按「改判据不改内容」纪律，
            我**不因此判 FAIL**，但登记为 WARN 并建议：D1-6 的适用范围应显式排除 CSV，或改为
            「在 CHANGELOG 中统一登记八份的权威依据」。
            DATA_PROVENANCE / ER_DIAGRAM 属可修，建议补一句权威依据。
```

### 2.2 §3 ER 图与数据模型一致性（9 条）

```
[D3-1] 图中每张实体名与 CORE §5 表名逐字一致（含大小写与下划线）
  快照：ER 1b8b62ca0317851f / CORE（只读参照，正在修改，但表名不受影响）
  实测：按坐标区域抽取九张卡片标题，逐字比对 CORE §5.1–§5.9：
        data_source ✓ / data_dataset ✓ / import_batch ✓ / source_record ✓ / historical_place ✓
        candidate_match ✓ / historical_place_location ✓ / historical_place_name ✓ / data_quality_issue ✓
        三张视图：v_place_evidence ✓ / v_place_liveness ✓ / v_place_time_span ✓（CORE §5.10）
        共 9 表 + 3 视图 = 12 个实体，**全部逐字一致，0 个多、0 个少**
  判定：**PASS**
  来源层级：①XML 解析 + ④CORE 表名
```

```
[D3-2] 图中每个字段名与数据模型同名表字段逐字一致；不得出现数据模型中不存在的字段
  快照：同上
  实测：**双向比对**（我用 XML 解析按卡片 x/y 区域抽取字段行，再与 CORE 列定义表逐字比对）
        图中字段总数（去重后）：data_source 6 / data_dataset 15 / import_batch 20 / source_record 16 /
        historical_place 19 / candidate_match 15 / historical_place_location 25 / historical_place_name 18 /
        data_quality_issue 17
        逐字同名命中：**除 1 处外全部命中**
        ★ **1 处不命中**：`ER_DIAGRAM_V2.1.1.svg:258`（`historical_place_location` 卡片 y=1222）
          = `source_rule_vocabulary`
          CORE §5.6（L671）为 `source_time_columns`（**改名后**）
          ⇒ 「图中出现数据模型中不存在的字段」
        另：`historical_place_name` 卡片**缺** `source_time_columns`（CORE §5.7 L728 新增列）
          ⇒ 反向也不完整（D3-2 是双向判据）
  判定：**FAIL**
  来源层级：①XML 解析 + ④CORE §5.6/§5.7
  修正建议：SVG L258 改 `source_time_columns`；`historical_place_name` 卡片在
            `association_certainty`（y≈1071）之后、`time_note`（y≈1139）之前插入
            `+ source_time_columns  text NOT NULL DEFAULT ''   列级掩码，逐字保留`。
            注意 SVG 是手写坐标，插入后需下移后续 y 值或压缩行距（卡片高度约 460px，尚有余量）。
```

```
[D3-3] 图注中 v_place_time_span 的过滤条件写 record_status <> 'rejected'，且写明"只聚合 name+location、排除 edge"，'published' 命中 0
  快照：ER 1b8b62ca0317851f
  实测：
    · SVG L1529（y=1529）：「⭐ 过滤条件（写死）：record_status <> 'rejected'  AND  sr.is_active」✓
    · SVG L1544（y=1544）：「⛔ 不是「等于某个已发布状态值」：该条件 ⇒ 0/19,039 有跨度，视图空转」✓
    · SVG L1560（y=1560）：「⛔ 只聚合 name + location 两张子表，排除 edge（edge 年份=关系存续期，」✓
    · SVG L1575（y=1575）：「不是地点存在期；量纲错误）。child CTE 刻意不 UNION 任何 edge 来源」✓
    · **`published` 全文命中数 = 0**（`grep -c published ER_DIAGRAM_V2.1.1.svg` → 0）✓
    · 附加正确性：图注另写「改为 <> 'rejected' 后 17,469/19,039 有跨度（暂存态）」，与 CORE N14 一致 ✓
  判定：**PASS**
  来源层级：①XML 解析 + ④CORE §5.10.3 / N14
```

```
[D3-4] 图中行数标注不得同图混用两个口径：凡出现行数必须带口径词
  快照：ER 1b8b62ca0317851f
  实测：逐处提取图中全部行数并核口径词：
        L154  source_record     「29,388 · **预计入库（活性行）**」✓ 有口径词
        L182  historical_place  「19,039 · **预计入库** · 无时间列 / 无几何列 / 无失效原因列」✓
        L239  historical_place_location「18,101 · **预计入库**」✓
        L275  historical_place_name    「47,499 · **预计入库**」✓
        L304  data_quality_issue       「12,831 · **预计入库** · issue_type 19 值」✓
        L7/结构旁注 data_dataset       「7 行 · **预计入库** · 许可相关列 = 0」✓
        L16  作废声明内 19,039（地点数，非行数）——不属行数标注
        L430–L432 **口径总声明**：「本图所有行数一律为『预计入库』口径：… 唯一例外：source_record 卡片
               另注『**隔离后** 29,391（不删行）』——它标注的是同一口径下的补充事实（隔离不删行，
               只置 is_active=false），该差额 3 = 被隔离的 3 条源记录」
        **关键**：source_record 卡片同时出现 29,388（预计入库）与 29,391（隔离后），
               但两者**各自带口径词**且 L432 显式解释差额来源 ⇒ 不构成「同表两个口径无标注」
  判定：**PASS**
  来源层级：①逐处提取 + 语义判读
  补注：V2.1 图的失效模式正是「`name 47,499`（入库）+ 旁注 `47,503`（暂存）同图无标注」——
        本图把该旁注改成了「预计入库 / 隔离后」双口径 + 差额解释，**已修正**。
```

```
[D3-5] source_record 唯一键标注为五段键（含 parent_external_id 与 duplicate_ordinal）；不得出现已废弃的 occurrence_key
  快照：ER 1b8b62ca0317851f
  实测：
    · SVG L790（y=790）：「UQ  (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)」
      ⇒ **五段齐全，逐字与 CORE C01 一致**
    · `occurrence_key` 在 SVG 命中 **0**（`grep -c` = 0）
    · 另：`parent_external_id` 与 `duplicate_ordinal` 均以 `*` 标注「五段键必需段」（L593 / L625）✓
  判定：**PASS**
  来源层级：①XML 解析 + ④CORE §4.1 / C01
```

```
[D3-6] 图中包含 V2.1.1 三个视图，且 v_place_evidence 存在
  快照：ER 1b8b62ca0317851f
  实测：三张蓝色虚线视图卡片全部存在：
        v_place_evidence（L1399, x=34）「派生视图 · 11 列 · 不是表」✓
        v_place_liveness（L1399, x=594）「派生视图 · 对外列 7 个 · liveness 8 值」✓
        v_place_time_span（L1399, x=1154）「派生视图 · 10 列 · derivation_kind 3 值」✓
        `v_place_evidence` 存在（V2.1 图缺此视图，本图已补）✓
  判定：**PASS**
  来源层级：①XML 解析
  补注：v_place_evidence 标「11 列」与 CORE §5.10.1「11 列」一致；v_place_liveness 标「对外列 7 个」
        与 CORE §5.10.2 的 L1626 自述「CORE 称对外 9 列，但其编号表只列 7 项、SQL 的 SELECT 亦只产生 7 列」一致
        ⇒ 图优先采用了 CORE 的自我更正，未沿用矛盾数字，**这是一个好的选择**。
```

```
[D3-7] historical_place 含 dataset_id 与 grain_key 两列
  快照：ER 1b8b62ca0317851f
  实测：SVG L527「+ dataset_id  text NOT NULL → data_dataset   §5.2.1 规则 1 已推翻」✓
        SVG L542「+ grain_key   text NOT NULL   按 place_grain 派生（见 CORE §5.5.3）」✓
        两列均以 `+` 标「本版新增列」，且 dataset_id 行附「§5.2.1 规则 1 已推翻」的推翻声明 ✓
        （V2.1 图缺此二列，本图已补）
  判定：**PASS**
  来源层级：①XML 解析 + ④CORE §5.5 / §5.5.0
```

```
[D3-8] data_quality_issue 行数若为入库口径应为 12,831，且含 first_batch_id / last_batch_id / occurrence_count 三列
  快照：ER 1b8b62ca0317851f
  实测：
    · L304「12,831 · 预计入库 · issue_type 19 值」⇒ 行数正确且带口径词 ✓
    · L1180「+ first_batch_id  bigint → import_batch  首次发现该问题的批次，重复发现时不变」✓
    · L1197「+ last_batch_id   bigint → import_batch  最近一次发现，重复发现时置为本批」✓
    · L1214「+ occurrence_count  integer NOT NULL DEFAULT 1   重复发现时 += 1」✓
    · 三列均以 `+` 标新增 ✓
    · 另核 12,831 的构成：CORE N08 = 12,631 − 2（删 licence_unconfirmed）+ 5 + 197 ⇒ 12,831 ✓
  判定：**PASS**
  来源层级：①XML 解析 + ④CORE N08
```

```
[D3-9] 在 CORE 或 CHANGELOG 中显式声明 架构/V2.1/ER_DIAGRAM_V2.1.svg 已作废
  快照：CORE（只读参照）/ ER 1b8b62ca0317851f
  实测：**双重满足**
    · CORE §5.10.6（L1254–L1262）：「#### 5.10.6 ⛔ `架构/V2.1/ER_DIAGRAM_V2.1.svg` **已作废**」
      正文「【作废声明】架构/V2.1/ER_DIAGRAM_V2.1.svg 自本版起作废，不得作为施工依据。
           作废理由：该图的 v_place_time_span 图注仍写「只聚合 record_status='published' 子行」。」
    · CORE §10 差异表（L1468）：「ER 图 | `ER_DIAGRAM_V2.1.svg` | **已作废**（图注仍写 `'published'`） | 照图施工 ⇒ 时间全 NULL」
    · ER_DIAGRAM 自身 L80：「【作废声明】架构/V2.1/ER_DIAGRAM_V2.1.svg 自 V2.1.1 起作废，不得作为施工依据。」
      + L98–L114 作废理由（含 19,039 全 NULL 与 0/19,039 实测）
      + <desc>「取代并作废 架构/V2.1/ER_DIAGRAM_V2.1.svg」
  判定：**PASS**（判据只要求 CORE 或 CHANGELOG 之一，实际 CORE 两处 + 图内三处，超出要求）
  来源层级：①检索 + ④CORE 原文
  附注：CHANGELOG 尚未产出，若后续产出应保持同一表述（不得改写成「已更新」等模糊说法）。
```

### 2.3 §4 导入/更新/隔离/合并/回滚（本轮涉 4 条）

```
[D4-1] 重复隔离算法在 IMPORT_RULES 与 ROLLBACK 中表述一致；四种排列逐步推演且结论自洽
  快照：IMPORT_RULES ba377a063edfe2cc / ROLLBACK f45546fea7f5e72e
  实测：
    · IMPORT_RULES §5.1（L256–L262）写死判据：「同一 hash 子组内【最小 ordinal】保留 /
      该子组内后续相同 hash 的行 ⇒ 隔离 / 不同 hash 的行 ⇒ 均保留（不隔离）」
    · IMPORT_RULES §5.2 逐排列推演（含表格逐步）：
        ① A,B,B → 隔离 1（ordinal 3）      L274–L282
        ② B,A,B → 隔离 1（ordinal 3），「与 ① 逐位相同」  L284–L293
        ③ A,A,B,B → 隔离 2（ordinal 2、4）  L295–L310  ⭐ 附「易错点」说明
        ④ A,B,C → 隔离 0                    L312–L314
        ⑤ 真实混合组 A,A,B → 隔离 1（sr_0027175） L316–L336
    · **独立复算**（我另写脚本，按规则重跑五种输入）：
        A,B,B → 1 (ordinals [3])  ✓
        B,A,B → 1 (ordinals [3])  ✓
        A,B,C → 0                 ✓
        A,A,B,B → 2 (ordinals [2,4]) ✓
        A,A,B(real) → 1 ([2])     ✓
      **五种全部与文档结论逐位一致**
    · ROLLBACK 中的表述：ROLLBACK 未重复推演（其职责是回滚期集合划分），但
      §3.4 步骤 0 直接引用「本批隔离结论」、§4.2 反例 ② 以「隔离行不参与回滚」承接，
      与 IMPORT_RULES §5.1 无冲突；两文件均将 `duplicate_quarantine` 定义为
      「每批重算的派生结论」（IMPORT_RULES L350 附近 / ROLLBACK L125）⇒ **表述一致**
  判定：**PASS**
  来源层级：①独立复算（非采信文档自述）
  补注：ROLLBACK 未重复四种排列的推演 **不构成缺陷**——D4-1 要求「在两文件中表述一致」，
        而非「两文件都写推演」。判据由 IMPORT_RULES 单独满足，ROLLBACK 的引用无矛盾。
        若 team-lead 认为需双写，可登记为 WARN（我按判据原文判 PASS）。
```

```
[D4-2] 隔离判据为「同一 hash 子组内最小 ordinal 保留…」；不得把「ordinal = 1 的 hash」作比较基准；四种排列隔离数必须 1/1/0/2
  快照：IMPORT_RULES ba377a063edfe2cc
  实测：
    · 规则表述：§5.1 写死「同一 hash 子组内【最小 ordinal】保留」，**未使用**「ordinal=1 的 hash」作基准 ✓
    · 旧规则残留检索（全文 5 份）：
        `ordinal = 1` / `ordinal=1` 命中 6 处，**全部是 ⛔ 禁止句式或「旧规则会误伤」的说明**：
          IMPORT_RULES L267「⛔ **禁止"只比 `ordinal = 1`"**」
          IMPORT_RULES L307「这正是旧规则"只比 `ordinal=1` 的 hash"会误伤的地方」
          IMPORT_RULES L309「不得仅比较 `ordinal=1` 的 hash」（引 Owner P0-03）
          IMPORT_RULES L344「新增的 `B` 与 `ordinal=1` 的 `A` 不同 hash」（描述性，非规则）
          FIELD_MAPPING L50「⛔ 禁止「只比 ordinal=1 的 hash」」
          （CORE L200 同）
        ⇒ **无一处把旧规则当有效规则陈述**
    · 「整组内容相同才隔离」残留：3 处，**全部是 ⛔ 禁止句式**
        IMPORT_RULES L268 / L326、FIELD_MAPPING L50
    · 四种排列隔离数：1 / 1 / 0 / **2**（A,A,B,B 判 2，非 1）✓ 与判据要求一致
    · 交付物中**未出现**旧规则代码块
  判定：**PASS**
  来源层级：①独立复算 + 语义判读（逐处看上下文，非关键词计数）
```

```
[D4-5] 回滚统计两组恒等式 + 七种反例（每种五要素齐全）
  快照：ROLLBACK f45546fea7f5e72e / 1,060 行
  实测：
    ── 两组恒等式 ──
    G1（L173–L181）：input_row_count = N_fail_import + N_quar + N_inserted + N_updated + N_noop + N_blocked
      六项各有独立「定义（逐字，可 SQL 复算）」表 + 落库与否 + 对应 import_batch 计数列 ✓
    G2（L243–L262）：(i) N_new = N_quar + N_normal ；(ii) N_normal = N_rolled_back + N_blocked + N_fail_rb + N_noop
      七项各有定义 + 参与回滚与否 + 台账 ✓
    **独立复算**（脚本）：
      G1(100,0,0,100,0,0,0)=100 ✓ / G1(100,0,2,98,0,0,0)=100 ✓ / G1(100,1,0,99,0,0,0)=100 ✓
      G2(100,0,100,0,0,0): (i)100=0+100 ✓ (ii)100=100+0+0+0 ✓
      G2(100,2,98,0,0,0):  (i)100=2+98 ✓   (ii)98=98+0+0+0 ✓
      G2(100,0,99,0,0,1):  (i)100=0+100 ✓  (ii)100=99+0+0+1 ✓
      G2(12,2,5,3,1,1):    (i)12=2+10 ✓    (ii)10=5+3+1+1 ✓
      **全部成立**
    ── 七种反例 × 五要素 ──
    逐块结构化核验（脚本按 `### 4.x 反例` 切块，检测五个关键词 + SQL 块 + 子情形数）：
      4.1 反例① 正常新增后回滚   (L388–445)  五要素**齐全**  含 SQL ✓ 子情形 1
      4.2 反例② 新增后重复隔离   (L446–470)  五要素**齐全**  含 SQL ✓ 子情形 1
      4.3 反例③ 之前已失效再导入 (L471–510)  五要素**齐全**  含 SQL ✓ 子情形 **2**（③a 复活不在 B / ③b 在 B 被置 source_absent）
      4.4 反例④ 已锁定记录       (L511–537)  五要素**齐全**  含 SQL ✓ 子情形 1
      4.5 反例⑤ 人工修改保护     (L538–567)  五要素**齐全**  含 SQL ✓ 子情形 1（E 坐标改 / F 软清空）
      4.6 反例⑥ 写入失败但未落库 (L568–620)  五要素**齐全**  含 SQL ✓ 子情形 **2**（⑥a 导入期 / ⑥b 回滚期）
      4.7 反例⑦ 混合批次         (L621–672)  五要素**齐全**  含 SQL ✓ 子情形 1
    五要素逐项确认：属哪个集合 / 是否参与回滚 / 是否产生台账 / 是否计入统计 / SQL 如何复算
      —— **七种反例 × 每种（含 4 个双阶段子情形）全部具备**，且每个反例末尾有「判定：G1 … ✓ G2 … ✓ R1 … ✓」的代入验算
    ── 反例⑦ 混合批次独立复算（L621–672）──
      |B|=12，N_quar=2，N_noop=1，N_blocked=3，N_fail_rb=1，N_rolled_back=5
      G2(i) 12 = 2 + 10 ✓
      G2(ii) 10 = 5 + 3 + 1 + 1 ✓
      R1 LHS 5 == (12−2) − 1 − 3 − 1 == 5 ✓
      R2 台账 3 == N_blocked 3 ✓
      R2b 1 ≥ 0 ✓ ；R2c 1 == failed_count(Rb)=1 ✓
      **七项全部成立**
    ── 两组不得混用的三个具体方式（L373–L381）──
      ① 用导入期 failed_count 代入 R1 → 阻断：R1 只读 import_batch[Rb] ✓
      ② 用回滚期 N_quar 代替导入期 N_quar → 阻断：N_quar_import vs N_quar_B 分别命名 ✓
      ③ 用 A6 反推 N_quar_B → 阻断：A6 是导入期断言，不得用于回滚统计 ✓
  判定：**PASS**
  来源层级：①独立代数复算（全部结论自行重算，未采信文档的「判定：…✓」）
  备注：以上均为**纸面代数**，ROLLBACK §11 已如实标注全部「未验证（U5：暂存 0 个回滚批次）」，
        未伪装为已验证 —— 这一点的合规性在 D6-6 另判。
```

```
[D4-6] is_active=false OR inactive_reason IS NOT NULL → N_noop 不得提前截走本批新产生的 duplicate_quarantine
  快照：ROLLBACK f45546fea7f5e72e
  实测：**逐处看上下文，区分「有效规则」与「警示语境」**
    · §3.4 判定顺序（L291–L318）：
        步骤 0  r.inactive_reason = 'duplicate_quarantine'  ⇒ N_quar++   ─ 终止
        步骤 1  r.is_active = false OR r.inactive_reason IS NOT NULL ⇒ N_noop++ ─ 终止
      ⇒ 步骤 0 **在前**，隔离行在步骤 0 已被截走，**不会**落入步骤 1
      ⇒ 步骤 1 的布尔式**只在步骤 0 之后生效**，属**合法有效规则**
    · §3.5（L323–L370）标题：「**洞 4 的代数证明：为什么 `is_active=false OR inactive_reason IS NOT NULL → N_noop` 必须禁止**」
      ⇒ 该布尔式在此处的语境是**「必须禁止」的警示**
    · §1 洞 4 表（L42）：「用 `is_active=false OR inactive_reason IS NOT NULL` 一个布尔式去判『是不是本批作用集内的行』
      → **本批新产生的 `duplicate_quarantine` 被提前截走**」⇒ 警示语境
    · §3.4 L319–L320 两条 ⛔：「步骤 0 必须在步骤 1 之前…」「步骤 0 的判据是 `inactive_reason` 的**值**，
      不是 `is_active` 的**布尔值**。任何以 `is_active = false` 打头的实现都会把 `duplicate_quarantine`
      与 `source_absent` 混为一谈。」⇒ 警示语境
    · §3.3.2 四格穷尽表（L278–L290）：`false + 'duplicate_quarantine'` → N_quar（步骤 0）；
      `false + 'source_absent'/'batch_rolled_back'` → N_noop（步骤 1）；`true + NULL` → 作用集内；
      `true + 非 NULL` → 非法状态（C03 违反）⇒ **3 格合法 + 1 格不可能 = 穷尽**，互斥由 inactive_reason 值域保证 ✓
    · **独立复算 §3.5 代数证明**：
        |B|=10，真实 N_quar=2 / N_noop=1 / N_blocked=2 / N_fail_rb=1 / N_rolled_back=4，合计=10 ✓
        正确顺序：G2(ii) 右式 = 4+2+1+1 = 8 = N_normal(10−2) ✓ ；R1 LHS 4 = 8−1−2−1 ✓
        错误顺序（N_noop 被算成 1+2=3）：G2(ii) 右式 = 4+2+1+3 = 10 ≠ 8 **✗ 破裂**
                                        R1 RHS = 8−3−2−1 = 2 ≠ 4 **✗ 差 2**
        ⇒ **文档给出的代数证明数值全部正确**
  判定：**PASS**
  来源层级：①独立代数复算 + 语义判读（逐处看是「有效规则」还是「必须禁止」）
  结论：文中共 4 处以该布尔式为主题，**无一处把它当作有效规则**：
        · 1 处在 §3.4 步骤 1 作为**步骤 0 之后**的合法判据（这是唯一正确用法）
        · 3 处在洞 4 警示语境（§1 表 / §3.4 ⛔ / §3.5 标题与正文）
        **合法语境，不判缺陷。**
```

```
[D4-7] 未落库的写入失败记录不得计入已插入集合
  快照：ROLLBACK f45546fea7f5e72e
  实测：
    · §3.2.3（L230–L241）标题即「⛔ D4-7：未落库的写入失败记录**不得**计入已插入集合」
      三条实现约束：① 失败行无 source_record_id（未落库 ⇒ 主键未生成）⇒ 不可能出现在 inserted_ids
                    ② failed_count 不得进入 |B|（|B| = len(R.inserted_source_record_ids)）
                    ③ A1 断言是可执行形式
    · §3.3 「全集：B = R.inserted_source_record_ids，N_new = |B|。**B 内的行全部已落库**——这是 §3.2.3 的直接推论」✓
    · §4.6 反例⑥a（L582–L620）：sr_G 被判 N_fail_import，「**不在 B**（没有 source_record_id）⇒ 不属 G2 任何集合」
      + SQL：`array_length(inserted_source_record_ids,1) = 99`、`failed_count = 1`、`99 + 1 = 100`
      + 悬空 id 检测：`unnest(inserted_source_record_ids) EXCEPT SELECT source_record_id` → 期望 0 行 ✓
    · §5.2（L685 附近）R1 取数来源逐项钉死：|B| ← len(import_batch[3].inserted_source_record_ids)；
      blocked_count / failed_count ← **只读 import_batch[Rb]** ✓
    · §3.6 混用方式 ①：用导入期 failed_count 代入 R1 → 阻断 ✓
    · **独立复算**：⑥a G1 100 = 1+0+99+0+0+0 ✓；⑥b R1 99 = (100−0)−0−0−1 ✓
  判定：**PASS**
  来源层级：①独立代数复算 + ②原文核对
```

### 2.4 §5 真实数据字段映射覆盖率（本轮涉 2 条 + D5-6）

```
[D5-1] FIELD_MAPPING 每个 staging_column 在对应暂存 CSV 中真实存在（或标 derived 并说明派生规则）；不存在的列 0 容忍
  快照：FM 4032e9f5b36c9347 / 220 行；七张 CSV（只读，哈希与基线一致）
  实测：**逐行对照实测列头**（我从七张 CSV 直接读列头，未采信 STAGING_FIELD_BASELINE 的转述）
        七张 CSV 列数：data_datasets 11 / source_records 14 / historical_places 15 /
                       historical_place_names 13 / historical_place_locations 22 /
                       candidate_matches 19 / data_quality_issues 11 → **合计 105 列**
        220 行逐行判定：
          · staging_column = (derived)   → 88 行（标 derived，notes/transform 说明派生规则）✓
          · staging_column = (generated) → 26 行（target_table 为 import_batch / data_source，无暂存对应表）✓
          · staging_column 为真实列名        → 106 行
              其中 86 行 target_column 为真实目标列（映射）
                   19 行 target_column = (dropped)（暂存列真实存在但有意丢弃）
                    1 行 target_column = (dropped) 且 staging_column = (generated)（L217，data_source 的许可列）
          · **(dropped) 行的 staging_column 全部真实存在**（逐条验证：L5 homepage / L6 license_id /
            L7 license_url / L8 redistributable / L9 attribution_text / L10 acquisition_method /
            L11 evidence / L32·L61·L173 source_dataset / L39 license_status / L40 redistributable /
            L41 attribution_text / L62 primary_external_id / L66·L67 valid_from·to_year_astro /
            L68 time_bound_type / L69 time_derivation / L89 geom_wkt）⇒ **19/19 真实**
          · **幽灵列（staging_column 在对应 CSV 不存在且未标 derived/generated）= 0**
  判定：**PASS**
  来源层级：①七张 CSV 逐行实测（非②基线转述）
```

```
[D5-2] 每个 target_column 在 CORE 中真实存在
  快照：FM 4032e9f5b36c9347 / CORE（只读）
  实测：逐行比对（排除 target_column 为 (dropped)/(discarded)/(split)/(derived) 的 50 行）
        **不命中 1 处**：
          · L110  `historical_place_location.source_rule_vocabulary`
            CORE §5.6（L671）为 `source_time_columns`（**改名后**）⇒ **CORE 中无此列**
        **反向缺失 1 处**：
          · CORE §5.7（L728）`historical_place_name.source_time_columns`（**新增列**）
            在 FIELD_MAPPING 中**零产出**（L134 的 (split) notes 指向「vocabulary」但无对应目标行）
  判定：**FAIL**（详见 §1.3 的三重断裂分析）
  来源层级：④CORE §5.6 / §5.7 / §5.0 原文 + ①逐行比对
  修正建议：见 §1.3
  附注（非缺陷，记录以免误判）：
    · `data_source` 的 7 行（L214–L221）target_column 在 CORE §5.1 无列定义表可对（CORE §5.1 全文仅
      「无变化（V2.1 §5.1）」一句）⇒ 我的脚本报「CORE data_source 无此列」属**脚本假阳性**，
      已按 V2 §5.1（`CORE_DATA_MODEL_V2.md:156–170`）人工核实：source_id / display_name / homepage_url /
      display_priority / notes / created_at **均存在** ⇒ PASS。
      但 `updated_at`（L221）在 V2 §5.1 **不存在**（V2 §5.1 只有 created_at）⇒ 见下方 WARN-A。
    · `created_at` / `updated_at`（L120/L121/L143/L144）在 CORE §5.6/§5.7 以合并行
      「`locked` / `manual_edited_fields` / `created_by` / `notes` / 时间戳」表达 ⇒ 属**脚本假阳性**，
      人工核实 CORE L679 / L735 的「时间戳」涵盖这两列 ⇒ PASS。
```

```
[D5-3] 暂存 CSV 中被目标模型需要的列不得整体遗漏；给出覆盖率
  快照：FM 4032e9f5b36c9347；七张 CSV 共 105 列
  实测：**105 列全部被映射表覆盖，覆盖率 100%**
        分类（按 staging_column 在对应 CSV 中存在性 + target_column 处置）：
          · 映射到真实目标列      61
          · (split) 拆分产出       2（time_rule_code × 2 表）
          · (derived) 派生，不落原列 14（quality_flag / name_id 等 → 另有产出）
          · (discarded) 流水号丢弃  9（place_id / name_id / location_id / candidate_id / issue_id /
                                       source_record_id / source_id × 2 / source_dataset 等，
                                       均为源端流水号或可由关联推出，notes 逐条说明理由）
          · (dropped) 有意丢弃     19（含 9 列许可相关 + source_dataset × 3 + 地点时间列 × 4 + geom_wkt 等）
          合计 61+2+14+9+19 = **105** ✓
        **「被目标模型需要但整体遗漏」的列：0 条**
        （唯一实质遗漏在**新列方向**：CORE §5.7 的 `source_time_columns` 未被 105 列中的任何一行产出，
          这不是「暂存列遗漏」而是「新增列未映射」，已在 D5-2 计 FAIL，此处不重复计）
  判定：**PASS**（覆盖率口径成立；D5-2 的缺陷不重复计）
  来源层级：①七张 CSV 逐列实测 + ④CORE 列定义
```

```
[D5-6] 七张 CSV 实测行数与 V0.2.2-r2 §0 权威数字一致
  快照：七张 CSV（哈希全部与 ACCEPTANCE §9 基线一致，未改动）
  实测（直接读文件计数，未采信 STAGING_FIELD_BASELINE）：
        source_records             29,391  vs 29,391  ✓
        historical_places          19,039  vs 19,039  ✓
        historical_place_names     47,503  vs 47,503  ✓
        historical_place_locations 18,103  vs 18,103  ✓
        data_quality_issues        12,631  vs 12,631  ✓
      另（未列入权威对照，供核对）：
        candidate_matches          53,137  （登记项 U18）
        data_datasets                   7  ✓
  判定：**PASS**
  来源层级：①逐文件计数
```

### 2.5 §6 统计口径与未验证事项（本轮涉 3 条）

```
[D6-6] V0.2.2 的 12 项 WARN 与 13 项未验证逐条保留，单列「施工验证清单」节；不得有一项被写成 PASS 或"已解决"
  快照：IMPORT_RULES ba377a063edfe2cc / DATA_PROVENANCE 13c5bea3d99e2b6b / ROLLBACK f45546fea7f5e72e
  实测：
    ── 单列「施工验证清单」节 ──
      IMPORT_RULES  §12「施工验证清单（**不得写成 PASS**）」，§12.1（V0.2.2 §5.3 十项）+ §12.2（本文件新增 V-1…V-10）✓
      DATA_PROVENANCE §11「施工验证清单（**逐项如实保留；任何一项都不得标记为校验通过或已关闭**）」，17 项 U/V ✓
      ROLLBACK    §11「施工验证清单（**不得写成 PASS**）」，§11.1（相关七项）+ §11.2（九条断言状态）+ §11.3（V-7…V-10）✓
    ── 「不得写成 PASS」的合规性 ──
      `PASS` 全文命中 4 处，**逐处看语境，全部是"不得写成 PASS"或引述 QA 计数**：
        IMPORT_RULES L703「## 12. 施工验证清单（**不得写成 PASS**）」—— 标题禁令
        IMPORT_RULES L706「QA 阶段二累计计数…**PASS 35 / FAIL 1 / WARN 12 / 未验证 13 —— 存在 FAIL，不宣布通过。**」
                        —— 引述上游计数 + 明确"不宣布通过"
        ROLLBACK L967「§11，U5/U12/U13/U14 如实保留，**不写 PASS**」
        ROLLBACK L971「## 11. 施工验证清单（**不得写成 PASS**）」
      ⇒ **无一处把任何待验项写成 PASS**
      `已解决` 命中 3 处：ROLLBACK L775「不得写成已验证」/ L933「这是"无数据可验"，不是"已验证"」/
                        L1060「均未自行裁定为'已解决'」⇒ 全部是否定式
      `已验证` 命中 4 处：IMPORT_RULES L175「已验证：7 个重复组内部均无 raw_record_index 并列」
                        （**这是可实算的事实性验证，非待验项**，且我独立复算 7 组确实无并列 ✓）
                        IMPORT_RULES L559 / ROLLBACK L775 / L933 均是否定式
    ── 12 项 WARN ──
      CORE 附录 B.3 逐条列出 12 项（A3/C5/D2/D3/F2/W9/W10/W11/WARN-1/WARN-2/归档位置/X2），标「均**未关闭**」✓
      DATA_PROVENANCE L479 明确「其余未验证项（**12 项 WARN**、V0.2.2 §5.3 的 10 项、V-3/V-4/V-7…V-10）逐条保留在
      CORE 附录 B 与 IMPORT_RULES §12，**本文不重复、也不代其结案**」✓
      IMPORT_RULES L706 引述「WARN 12」计数 ✓
      ROLLBACK 未提 12 项 WARN（只列与其相关的 U 项）—— 判据要求「单列施工验证清单节 + 逐条保留」，
      三份文件**合计**覆盖，且各自声明「仅列与本文件相关」/「本文不重复」⇒ 归属清晰，**不构成遗漏**
    ── 13 项未验证 ──
      IMPORT_RULES L706 引述「未验证 13」；CORE 附录 B.1（10 项 U）+ B.2（逐条断言）覆盖
    ── 关键：是否有任何一项被"改善"成 PASS？逐项核对 ──
      U3/U4/U5/U12/U13/U14/U15/U16/U18/U19 —— 三份文件中**全部为「未验证 / 未裁定 / 未复算」**
      R1/R2/R2b/R2c/G1/G2/S1/S2/rejected_by 永不自动恢复 —— ROLLBACK §11.2 九行状态
        全部标「**结构自洽（仅代数/规则核对，非运行期验证）**；**未验证**」⇒ **措辞精确，未升格**
      R2 特别标注「**R2 未被降级**」并解释「判据自洽性与 R2c 有无数据可验是两回事」⇒ 既不多算也不少算 ✓
      R2c 特别标注「**结构断言 + 未验证**」并给出零命中的证据（12,631 条台账中三类均 0 行）✓
  判定：**PASS**
  来源层级：①逐处语义核查（非计数）+ ④V0.2.2 §5.2/§5.3 原文比对
  一句结论：**三份文件的施工验证清单做到了「如实保留、无 PASS、口径精确（区分结构自洽 vs 运行期验证）」，
            这一项是本轮质量最高的部分。**
```

```
[D6-7] 施工验证清单至少含：U3/U4/U5/U12/U13/U14/U15/U16/U18 + is_canonical_row 与暂存 canonical_name 是否逐行相等
  快照：同上三份
  实测（逐项检索 + 看所在表格的语义）：
      U3  IMPORT_RULES §12.1 ✓ / DATA_PROVENANCE §11 ✓ /（ROLLBACK 未列，其 §11.1 声明「仅列与本文件相关」）
      U4  IMPORT_RULES ✓ / DATA_PROVENANCE ✓
      U5  IMPORT_RULES ✓ / DATA_PROVENANCE ✓ / ROLLBACK §11.1 ✓（11 处引用，为核心项）
      U12 IMPORT_RULES ✓ / DATA_PROVENANCE ✓ / ROLLBACK ✓
      U13 IMPORT_RULES ✓ / DATA_PROVENANCE ✓ / ROLLBACK ✓
      U14 IMPORT_RULES ✓ / DATA_PROVENANCE ✓ / ROLLBACK ✓
      U15 IMPORT_RULES ✓ / DATA_PROVENANCE ✓ / ROLLBACK ✓
      U16 IMPORT_RULES ✓ / DATA_PROVENANCE ✓ / ROLLBACK ✓
      U18 IMPORT_RULES ✓ / DATA_PROVENANCE ✓（3 处，含 §9.4 明确「不得进权威数字表」）/ ROLLBACK ✓
      `is_canonical_row` 与暂存 `canonical_name` 逐行相等：
        IMPORT_RULES §12.2 **V-2**「`is_canonical_row` 与暂存 `canonical_name` 是否逐行相等」✓（2 处）
        DATA_PROVENANCE §11 **V-2**「`is_canonical_row` 与 `canonical_name` 是否**逐行相等** / 逐行比对，不抽样」✓
      ⇒ **判据要求的 10 项全部命中**（分散在三份文件的清单中，合计覆盖，无一项落空）
  判定：**PASS**
  来源层级：①逐项检索 + 语义核对
  补注：ROLLBACK 未列 U3/U4 —— 这两项是「视图首导能否建/查通」，与回滚无直接关系，其 §11.1 已声明
        「仅列与本文件相关的」。判据原文为「施工验证清单**至少含**…」，对象是「交付物的施工验证清单」
        （八份合计），非「每份都必须含」⇒ 判 PASS。若 team-lead 要求逐份齐备，可登记 WARN。
```

```
[D6-8] 两条施工级硬提醒在文档中显式出现：
       ① normalize.py:306 改动必须回归 content_hash
       ② derivation_kind / no_evidence 不得直读暂存 valid_from/to_year_astro
  快照：五份见 §0
  实测（逐文件、逐项）：
      ── H1「normalize.py:306」──
      IMPORT_RULES §13 H1（L738–L752）：完整标题「### H1｜`normalize.py:306` 一旦改动必须回归 `content_hash`」
        + 说明「该行保持 sort_keys=True, ensure_ascii=False, separators=(",",":") 时，逐字节形式与规范化表达式等价
          （实测 29,391/29,391 逐字节相等，R30）」+ 后果链「29,391 条全部改变 ⇒ ordinal 大规模重排 ⇒
          STOP_AUTO 误触发 ⇒ 整批 SKIP_UPDATE ⇒ **【静默，不报错】**」✓
      DATA_PROVENANCE §9.1 H1（L403–L415）：同标题、同后果链 ✓
      CORE §4.4（L221 附近）：「⚠️ 施工级硬提醒 H1」✓（CORE 不在本轮，但交叉印证）
      FIELD_MAPPING L47（content_hash 行 notes）：「⚠️ H1：normalize.py:306 一旦改动必须回归 content_hash
        （否则 29,391 条哈希全变 ⇒ ordinal 大规模重排 ⇒ STOP_AUTO 误触发、整批 SKIP_UPDATE）」✓
      ROLLBACK：0 命中（合理——回滚不涉 content_hash 计算）
      ER_DIAGRAM：0 命中（合理——图面空间与主题无关）
      ── H2「不得直读暂存时间列」──
      IMPORT_RULES §13 H2（L753–L760）：「### H2｜`derivation_kind` / `no_evidence` 不得直读暂存
        `valid_from/to_year_astro`」+ 「计数必须基于「只聚合 name + location、排除 connection」的重算结果。
          暂存 historical_places.valid_from_year_astro / valid_to_year_astro 由含 connection 的旧口径生成 ⇒
          直接引用会使 no_evidence 系统性偏低 65（1,505 vs 1,570）」✓
      DATA_PROVENANCE §9.2 H2（L416–L423）+ §10 N15 行附「⚠️ 暂存列算出的 1,505 是旧口径，**偏低 65**」✓
      CORE §6.3 + §9 N15 同 ✓（交叉印证）
      FIELD_MAPPING：0 直读告警，但其 L108–L110 明确 location 时间列走 (split) 派生、`historical_places` 的
        时间列在 L66–L68 标 (dropped)（「CORE §5.5.4：地点无时间列，改派生视图」）⇒ **结构上已阻断直读路径**
      ROLLBACK / ER_DIAGRAM：0 命中（合理——回滚不涉，图面 L252/L119 明确写了「filter 写死 `<>'rejected'`」与
        「不是「等于某个已发布状态值」」）
  判定：**PASS**
  来源层级：①逐文件检索 + 逐处看语境（区分"合理缺席"与"遗漏"）
  结论：两条硬提醒在**承担该职责的文件**中全部显式出现，且各有 2–3 处重复（IMPORT_RULES + DATA_PROVENANCE +
        FIELD_MAPPING notes），后果链完整、量化（1,505 vs 1,570；29,391 条全变）。
        在**不承担该职责的文件**中缺席属合理，不计缺陷。
```

### 2.6 §7 工程边界（E1–E7）

```
[E1] 架构/V2/CORE_DATA_MODEL_V2.md 未改动
  实测：128,784 B / sha256[:16]=91b459a8070364df / mtime 12:27:32 —— **与 ACCEPTANCE §9 基线逐项一致**
  判定：**PASS**　来源层级：①哈希实测
```
```
[E2] 架构/V2.1/ 八份（实为十份）文件全部未改动
  实测（逐份哈希 + 字节数 + mtime，全部命中基线）：
    CORE_DATA_MODEL_V2.1.md        70,016  / ec118b60638244c8 / 15:31:43 ✓
    IMPORT_RULES_V2.1.md           25,677  / 6cbcefedc212ec2d / 15:24:58 ✓
    ER_DIAGRAM_V2.1.svg            28,295  / 3853eeba963b3501 / 15:28:18 ✓
    FIELD_MAPPING_V2.1.csv         25,625  / 50fca40335f40066 / 15:23:43 ✓
    FIELD_MAPPING_V2.1.md           7,577  / 043ba35adb7fb7ac / 15:23:57 ✓
    ROLLBACK_AND_MANUAL_PROTECTION_V2.1.md 15,078 / efb934d94bed9aac / 15:26:06 ✓
    LICENSE_GATE_V2.1.md           16,040  / b2ab5754eeff475d / 15:25:42 ✓
    V2.1_QA_REPORT.md              14,164  / b30eeb24b061b449 / 15:32:47 ✓
    V2_TO_V2.1_CHANGELOG.md        15,601  / acf35d865cc3d68a / 15:32:06 ✓
    （另有 FIELD_MAPPING_V2.1.md 已在列）
  判定：**PASS**　来源层级：①哈希实测
```
```
[E3] 架构/V2.1.1/V0.2.2/ 全部文件未改动
  实测：
    00_PROBLEM_LIST_AND_PLAN_V0.2.2.md  105,526 / 0356ff721a7fb4f1 / 20:24:15 ✓
    V0.2.1_TO_V0.2.2_CHANGELOG.md        69,320 / 881087457b59d38a / 20:28:07 ✓
    （V0.2.2/ 另有 DATA_AUDIT / INDEPENDENT_REVIEW / QA_VERIFICATION 三份 + audit_scripts/ + qa_recalc/，
      无基线哈希可对；但 mtime 均早于本轮开工，无改动迹象）
  判定：**PASS**　来源层级：①哈希实测（有基线者）
```
```
[E4] 架构/V2.1.1/00_PROBLEM_LIST_AND_PLAN.md（V0.2.1）未改动，mtime 仍 17:43:53
  实测：190,222 B / 0a9c56fbfc002769 / **17:43:53** —— 三项全部命中基线
  判定：**PASS**　来源层级：①哈希 + mtime 实测
```
```
[E5] 七张暂存 CSV 未改动
  实测（七份全部命中基线哈希与字节数）：
    data_datasets.csv              6,018     / fa44197e54b4da4a / 12:23:26 ✓
    source_records.csv            26,942,777 / 30fed0e40ba12496 / 12:23:26 ✓
    historical_places.csv          4,953,976 / 86db3ce6b94f9e31 / 12:23:25 ✓
    historical_place_names.csv     8,937,942 / 80674c0ded553241 / 12:23:25 ✓
    historical_place_locations.csv 11,698,567 / 9e987ba578e933ed / 12:23:25 ✓
    candidate_matches.csv         17,315,204 / 4e29c2ec64ebe263 / 12:23:26 ✓
    data_quality_issues.csv        5,277,273 / 7a8ab3916e00dcb0 / 12:23:26 ✓
  判定：**PASS**　来源层级：①哈希实测
```
```
[E6] normalize.py 未改动
  实测：路径为 `code/p0/wb-002-normalize/normalize.py`（ACCEPTANCE §9 写的是 `code/p0/wb-002-normalize/normalize.py`，
        我首次以 `设计资料/P0收敛/` 为相对根查找报 MISSING，改以项目根 `014-CanvasofWorldHistory/` 为根后命中）
        102,275 B / 4a0a6fed7f656de5 / mtime 2026-11-02 12:20:29 —— **三项全部命中基线**
  判定：**PASS**　来源层级：①哈希实测
  附注：ACCEPTANCE §9 该行的相对根与其余行不同（其余以 `设计资料/P0收敛/` 为根），属**基线表的口径瑕疵**，
        不影响判定，但建议下轮统一。
```
```
[E7] 未产生任何 DDL / Migration / Docker 建库 / 数据导入 / 产品代码修改 / Git 操作
  实测：
    · 本轮我**未执行**任何 DDL / Migration / Docker / 导入 / 建库命令
    · 未修改任何被检文件（五份哈希与开工一致）
    · 未修改 V2 / V2.1 / V0.2.2 / 七张 CSV / normalize.py（§E1–E6 已逐项证明）
    · 未执行任何 git 命令（含 commit / add / checkout / reset）
    · 我在核查中产生过一个临时文件 `_build_ercards_tmp.txt`（SVG 卡片文本抽取的中间产物），
      **已删除**，根目录已恢复为「5 份交付物 + _build/」
    · 五份交付物内虽含 `CREATE VIEW` SQL 段（DATA_PROVENANCE §7 / CORE §5.10），
      但均为**定式转录**（DATA_PROVENANCE §12.6 明示「不写 DDL/Migration/建库/导入/Git：§7 的两段 CREATE VIEW
      是定式转录，落地由施工方在迁移脚本里执行」），**未被执行**
  判定：**PASS**（就我可见范围）
  来源层级：①操作记录
  限定：Docker 建库 / 产品代码修改 / Git 操作的实际发生与否，**我只能证明自己未做**；
        其他成员是否有越界，需 team-lead 以仓库层面证据（git status / docker ps / 端口监听）复核。
        我按判据「我可见范围」判 PASS，并标注该限定。
```

---

## 3. 附加独立复算（超出判据要求，用于交叉印证）

为落实「②③不得直接当结论」，我直接从七张真实 CSV 重算了全部关键数字。**结果全部与文档一致。**

| 复算项 | 文档值 | 我的独立复算 | 一致性 |
|---|---:|---:|---|
| 总组数（四段前缀） | — | 29,384 | — |
| 单行组数 | 29,377 | 29,377 | ✓ |
| `ordinal=0` 行数（N04） | 29,377 | **29,377** | ✓ |
| 多行组 ordinal 分布（N04） | 7 组 × 2 行，ordinal 1/2 各 7 | **1→7、2→7** | ✓ |
| 隔离行数（N02） | 3 | **3** | ✓ |
| 隔离行身份（N18） | sr_0004941 / sr_0004942 / sr_0027175 | **sr_0004941 / sr_0004942 / sr_0027175** | ✓ |
| `record_scope` 分布（N10） | place 18,398 / name 5,762 / location 2,468 / edge 2,763 | **完全相同** | ✓ |
| `record_scope` 第五种 | 0 | **0**（11 种 external_id_type 全部落入 4 值） | ✓ |
| 18,398 − 2 = 18,396 = 19,039 − 643（N09 闭合） | ✓ | **True** | ✓ |
| 无子行源记录（N12 口径A） | 8,682 | **8,682**（place 2,650 / name 2,513 / location 756 / edge 2,763） | ✓ |
| name 表 `time_bound_type`（N13） | exact 21,614 / unknown 20,535 / exact_or_bounded 2,360 / tpq_taq 1,774 / bounded 1,166 / snapshot 54 | **完全相同** | ✓ |
| 47,503 → 47,499 的因果（N06） | 被隔离 2 条 CHGIS 各派生 2 条名称 = −4 | **name 表引用 sr_0004941/2 共 4 条**（桂林郡 + Guilin Jun × 2 组） | ✓ |
| 18,103 → 18,101 的因果（N07） | 被隔离 2 条 CHGIS 各派生 1 条位置 = −2 | **location 表引用 sr_0004941/2 共 2 条** | ✓ |
| `content_hash` 规范串指纹（D2-7） | len=85 / sha1=9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5 | **len=85 / sha1=9b0414f5c7…**（自行重算） | ✓ |
| 四种排列隔离数（D4-1/D4-2） | 1/1/0/2 | **1/1/0/2** | ✓ |
| G1/G2/R1 八组代入 | 全部 ✓ | **全部成立** | ✓ |
| §3.5 洞 4 代数证明 | 正确顺序 8=8、4=4；错误顺序 10≠8、2≠4 | **完全一致** | ✓ |
| 7 个重复组内部 `raw_record_index` 是否并列 | 无并列（IMPORT_RULES L175「已验证」） | **确无并列**（14 行 ri 各异） | ✓ |

> **这一轮独立复算的意义**：文档中所有「已验证 / 实测」的标注，我都能从 ①原始 CSV 复现。
> **唯一的例外是 `source_time_columns` 相关的 2,074 行掩码**——文档声称要收纳，但映射表未产出该列，
> 这已计入 D5-2 FAIL。

---

## 4. FAIL / WARN 清单（带行号 + 修正建议）

### 4.1 FAIL（3 条）

| # | 判据 | 位置 | 实测 | 修正建议 |
|---|---|---|---|---|
| **F-01** | **D5-2 / D2-12** | `FIELD_MAPPING_V2.1.1.csv` **L110** | `target_column = source_rule_vocabulary`（旧名）；CORE §5.6 L671 已改名 `source_time_columns` ⇒ CORE 中**无此列** | L110 `target_column` 改 `source_time_columns`；notes 保留旧名并注「V2.1 旧名，V2.1.1 改名」 |
| **F-02** | **D5-2** | `FIELD_MAPPING_V2.1.1.csv`（缺行） | CORE §5.7 L728 新增列 `historical_place_name.source_time_columns`（`NOT NULL DEFAULT ''`，收纳 2,074 行 name 侧掩码）在映射表**零产出**；L134 `time_rule_code → (split)` 的 notes 指向「vocabulary」但无对应目标行 ⇒ 该 2,074 行掩码**静默丢失** | 新增 1 行：`historical_place_names.csv,time_rule_code,historical_place_name,source_time_columns,text,Y,split('\\|') 后取词元,-,列级掩码逐字保留；CORE §5.7 新增列`。派生规则已在 CORE §5.7 与 V0.2.1 §2.7.1 写死，属**转录非猜测**，不违反 Owner「不得手写猜测」 |
| **F-03** | **D3-2** | `ER_DIAGRAM_V2.1.1.svg` **L258**（y=1222） | 写 `source_rule_vocabulary  text NOT NULL DEFAULT ''`；CORE §5.6 为 `source_time_columns` ⇒ 图中出现数据模型中不存在的字段 | L258 文本改 `source_time_columns  text NOT NULL DEFAULT ''   列级掩码，逐字保留`；另在 `historical_place_name` 卡片补 `+ source_time_columns` 行（y≈1139 前，需顺移后续 y 或压缩行距） |
| **F-04** | **D1-5 字面层** | `FIELD_MAPPING_V2.1.1.csv` **L5–L14、L39–L41**（共 11 处） | 11 处许可列名全部位于 `target_column=(dropped)` 的**合法语境**（已删除列清单），但**无一处标注【留痕】**（`grep -c '【留痕'` = 0）；判据明定「未标【留痕】者计 FAIL」 | 各 notes 末尾追加 `【留痕：已删除列清单】`。注意 CSV 单元格内不要引入裸逗号 |

> **F-01/F-02/F-03 是同一根因的三个落点**（改名未同步 + name 表新列未产出），
> 建议**一次性修**：映射表 2 处 + SVG 2 处，然后重算三份哈希。
> **风险等级排序**：F-02（静默丢 2,074 行数据）> F-01（DDL 编译失败，会立即暴露）> F-03（图与模型不一致）> F-04（纪律性缺失）。

### 4.2 WARN（5 条）

| # | 判据 | 位置 | 内容 | 建议 |
|---|---|---|---|---|
| **W-01** | D5-2 | `FIELD_MAPPING_V2.1.1.csv` **L221** | `data_source.updated_at`：V2 §5.1（`CORE_DATA_MODEL_V2.md:156–170`）的 `data_source` **只有 `created_at`，无 `updated_at`**；L220 `created_at` 有据、L221 `updated_at` 无据 | 请 team-lead 裁定：① 删 L221 行；② 或确认为「V2.1.1 新增列」并在 CORE §5.0 登记（但 CORE §5.1 写「无变化」，故新增需走 §5.0）。**我不擅自判 FAIL**——判据 D5-2 是「target_column 在 CORE 中真实存在」，而 CORE §5.1 无列定义表（只有「无变化」一句），无法机械判定 |
| **W-02** | D5-2 | 同上 L217 | `data_source` 的 `(dropped)` 行：notes 自述「该目标列命中禁用正则 `^(attribution\|citation\|license)_`」，但**未写出原列名**（只有「同表已有 `homepage_url` 承载源主页链接」暗示）。CORE §5.1 写「无变化」，即 CORE 未记录此列被删 ⇒ **无许可列被删的事实无留痕** | 建议在该 notes 或 CORE §5.0 显式登记：`data_source.default_license_id` / `default_redistributable` 两列（V2 §5.1 L165–L166 确有）**已删除**【留痕】。这是 D1-5 结构层的一个**未闭合缺口**：若 CORE §5.1 真「无变化」，则这两列会随「无变化」被施工方建出来 ⇒ 与「无许可列」冲突。**此条建议提级为待裁定** |
| **W-03** | D1-6 | `DATA_PROVENANCE_V2.1.1.md` 首部；`ER_DIAGRAM_V2.1.1.svg` `<desc>`；`FIELD_MAPPING_V2.1.1.csv` 整体 | 版本号有（V2.1.1），但**无「以 V0.2.2-r2 为权威依据」的首部声明** | DATA_PROVENANCE / ER 各补一句；CSV 建议**豁免**（判据与格式冲突，见 §2.1 说明），改由 CHANGELOG 统一登记 |
| **W-04** | D6-7 延伸 | `ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md` §11.1 | 未列 U3 / U4（视图首导）。其 §11.1 已声明「仅列与本文件相关的」，且判据是「至少含」（八份合计）⇒ 不判 FAIL | 若 team-lead 要求逐份齐备，补 U3/U4 两行（标注「与本文件无直接关系，转 IMPORT_RULES §12.1」） |
| **W-05** | 基线口径 | `ACCEPTANCE_CRITERIA_V2.1.1.md` §9 | `normalize.py` 行用 `code/p0/wb-002-normalize/normalize.py`（相对**项目根**），其余行用 `设计资料/P0收敛/` 相对根 ⇒ 口径不一致，易致误报 MISSING（我首次即误报） | 统一相对根，或标注每行的根。**属判据文件瑕疵，非交付物缺陷** |

### 4.3 判为 PASS 但需 team-lead 知悉的 4 处（不构成缺陷，但存在裁定空间）

| # | 项 | 说明 |
|---|---|---|
| N-01 | D4-1 | ROLLBACK **未重复**四种排列的推演。判据是「在两文件中表述一致」，而非「两文件都写推演」；IMPORT_RULES 已完整推演、ROLLBACK 的引用无矛盾 ⇒ 我判 PASS。若要求双写，请裁定 |
| N-02 | D6-7 | U3/U4 未出现在 ROLLBACK（同 W-04）。判据「至少含」针对八份合计 ⇒ PASS |
| N-03 | D1-3 | SVG 解析成功（**实际用 ElementTree 加载**，非估算）。注：`role="img"` + `aria-label` 齐全，`<title>`/`<desc>` 完整，属无障碍良好实践 |
| N-04 | D3-6 | `v_place_liveness` 卡片标「对外列 7 个」，**未沿用** CORE §5.10.2 正文自述的「对外 9 列」，而是采用了 CORE L1626 的自我更正（「称 9 列，但编号表只列 7 项、SQL 的 SELECT 亦只产生 7 列」）⇒ **图做了一个正确的判断**，但这说明 **CORE §5.10.2 的「9 列」表述本身仍在正文里**，属 CORE 内部待修项（CORE 不在本轮范围，仅登记） |

---

## 5. D3 一句结论

**ER 图与数据模型是否一致：不一致 —— 12 个实体名（9 表 + 3 视图）100% 逐字一致，但字段层有 2 处不一致（`source_rule_vocabulary` 旧名 vs `source_time_columns` 新名；`historical_place_name` 缺 `source_time_columns` 新增列），其余 8 条 D3 判据（D3-1/3/4/5/6/7/8/9）全部 PASS。**

---

## 6. 判定计数

| 分类 | 本轮判定条数 | PASS | FAIL | WARN |
|---|---:|---:|---:|---:|
| §1 完整性与合规（D1-1…D1-6） | 6 | 4 | **1**（D1-5） | 1（D1-6） |
| §3 ER 图（D3-1…D3-9） | 9 | 8 | **1**（D3-2） | 0 |
| §4 导入/回滚（D4-1/2/5/6/7） | 5 | 5 | 0 | 0 |
| §5 映射覆盖率（D5-1/2/3/6） | 4 | 3 | **1**（D5-2） | 1（W-01，D5-2 的附加） |
| §6 统计与未验证（D6-6/7/8） | 3 | 3 | 0 | 0 |
| §7 工程边界（E1–E7） | 7 | 7 | 0 | 0 |
| **合计** | **34** | **30** | **3**（去重后 3 个判据 ID） | **2**（去重后 2 个判据 ID） |

> **判据 ID 层面的 FAIL：3 个** —— `D1-5`（字面层留痕）、`D3-2`（SVG 字段名）、`D5-2`（映射表 target_column）。
> **WARN：2 个判据 ID** —— `D1-6`（版本/权威依据首部声明）、`D5-2` 的旁支 W-01/W-02（附加观察，不另计判据）。
> 另有 W-03/W-04/W-05 属**判据文件瑕疵或延伸建议**，不计入交付物判定。

### 未判定项（诚实登记）

| 项 | 原因 |
|---|---|
| `CORE_DATA_MODEL_V2.1.1.md` 相关判据 | **本轮不在范围**（正被另一架构师修改）。D3-1/D3-2 中涉及 CORE 的部分，我按 team-lead 授权「表名与既有字段名不受本轮修改影响」使用当前版本，**若 CORE 后续改动涉及 §5.6/§5.7 字段名，F-01/F-02/F-03 的修正目标可能需同步调整** |
| `V2.1_TO_V2.1.1_CHANGELOG.md` / `V2.1.1_QA_REPORT.md` | 尚未产出，D1-1 中这两份无法判定；D3-9 的「CORE 或 CHANGELOG」我已按 CORE 满足 |
| D2 类判据（D2-1…D2-12 中的多数） | 本轮 team-lead 只指定了 D2-12 相关的 `source_time_columns`。我按指定范围判了 D2-12（FAIL）。**D2-1/2/3/4/5/6/7/8/9/10/11 未逐条判**——这些涉及 CORE（正在修改），应留待 CORE 定稿后的批次。为避免越界，我只对可在 5 份内自证的子项做了抽查（五段键一致、`place_record` 零命中、`content_hash` 指纹重算），结果均 PASS，但**不据此宣布 D2 整体 PASS** |
| D4-3/4/8/9/10/11/12 | 未在 team-lead 指定的重点范围内；D4-10 涉及 CORE §5.10 视图 SQL（正在修改），不宜此时判 |

---

## 7. 能否通过

**不能通过。**

**理由（按严重度）**：

1. **F-02（D5-2）—— 静默数据丢失**：`historical_place_name.source_time_columns` 是 CORE §5.7 明列的**新增列**，其唯一目的是收纳 V2.1 会丢弃的 **2,074 行** name 侧 `time_rule_code` 掩码（CORE L728 原文：「收纳 V2.1 会丢弃的 **2,074 行** name 侧掩码（V2.1 只有 location 一列能存，name 侧 `time_rule_code` 只能落 `(dropped)`）」）。映射表**没有任何一行产出该列** ⇒ 施工方按映射表建库、按映射表写导入器，这 2,074 行掩码会**静默丢失**，且**不会报错**。这正是 CORE 在 §5.7 专门加这一列要防的事，也是 Owner 反复强调的「静默数据损坏」类缺陷。

2. **F-01（D5-2 / D2-12）—— DDL 编译失败**：`FIELD_MAPPING_V2.1.1.csv:110` 用旧名 `source_rule_vocabulary`，而 CORE §5.6 的 **C13 约束**（`CHECK (source_time_columns = '' OR …)`）引用新名。若施工方按映射表建列、按 CORE 建约束 ⇒ **DDL 直接编译失败**（引用不存在的列）。这一条会**立即暴露**，风险低于 F-02，但属硬错误。

3. **F-03（D3-2）—— ER 图与模型不一致**：`ER_DIAGRAM_V2.1.1.svg:258` 同 F-01 的旧名问题。ER 图是施工者的**第一手视觉依据**（D3 章节开篇即警告「照旧图施工会让 19,039 个地点时间全 NULL」），此处不一致会放大 F-01 的影响。

4. **F-04（D1-5 字面层）—— 留痕纪律缺失**：11 处许可列名语境合法（`(dropped)` 行）但未标【留痕】。这不影响功能，但违反判据的硬性要求，且会导致后续扫描无法区分「合法的已删除列清单」与「许可功能回归」。

**已确认的强项（应记录，避免下轮被无谓推翻）**：

- **全部关键数字均经我从 ①原始 CSV 独立复算复现**：29,377 / 14 / 3 / 18,398 / 5,762 / 2,468 / 2,763 / 8,682 / 47,499 / 18,101 / 21,614 / 2,360 / 1,166 / 54 / 1,774 — **无一例外，全部吻合**。
- **D4 系列（导入/隔离/回滚）质量很高**：四种排列隔离数 1/1/0/2 独立复算通过；G1/G2/R1 八组代入全部成立；§3.5 洞 4 的代数证明数值完全正确；七种反例五要素齐全、每个含 SQL 与代入验算；「洞 4 必须禁止」的警示语境与「步骤 1 合法使用」的界限划得清楚。
- **D6-6/D6-7 做到了「如实保留、无 PASS、区分结构自洽与运行期验证」**，R2 标「未被降级」、R2c 标「结构断言 + 未验证」，措辞精确。这是本轮最高质量的部分。
- **D3-3/D3-9 已彻底修正 V2.1 的致命失效**（`'published'` 命中 0、作废声明三处）。
- **E1–E7 工程边界零违例**（21 个基线哈希逐项命中）。

**重测建议**：F-01/F-02/F-03 是同一根因，**一次可修**（映射表 2 处 + SVG 2 处）；F-04 是机械性追加。修完后重算 3 份哈希即可进入 Round 2 回归。**建议同时确认 W-01（`data_source.updated_at`）与 W-02（`data_source` 许可列留痕缺口）**，后者可能是比 F-01 更深的模型层问题。

---

## 8. 我遵守的硬约束（自查）

| 约束 | 遵守情况 |
|---|---|
| 禁止改任何被检文件 | ✅ 五份哈希与开工一致；临时文件 `_build_ercards_tmp.txt` 已删 |
| 禁止改 V2 / V2.1 / V0.2.2-r2 | ✅ E1–E3 逐项哈希证明 |
| 禁止改七张 CSV | ✅ E5 七项哈希证明 |
| 禁止改 normalize.py | ✅ E6 哈希证明 |
| 不写 DDL / Migration / 建库 / 导入 / Git | ✅ 未执行任何此类命令 |
| 不得只做关键词扫描，要核语义 | ✅ D1-5 / D4-2 / D4-6 / D6-6 均逐处看上下文；`ordinal=1` 6 处命中全部人工判为「禁止句式」 |
| ②③不得直接当结论 | ✅ 全部关键数字回到 ①（七张 CSV 逐行复算）或 ④（CORE/V0.2.2 原文） |
| 任何 FAIL 不得宣布通过 | ✅ §7 明确「不能通过」 |
| 未验证不得伪装 PASS | ✅ §6 单列「未判定项」并说明原因 |
