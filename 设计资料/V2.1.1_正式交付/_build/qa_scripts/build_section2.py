#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成 STAGING_FIELD_BASELINE.md 第二节：V2.1 → V2.1.1 映射差异预判。

本脚本只做「把已核实的结论写成 Markdown 并追加」，不做任何推断：
所有数字均来自本目录另两个脚本的实算输出（来源层级①）或已标注的上游文档行号（层级②③
仅作引用，未直接当结论）。

严格只读：不触碰 normalized/、V2.1/、V0.2.2/ 下任何文件。
"""

from __future__ import annotations

import io
import os

BUILD_DIR = (
    r"E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory"
    r"\设计资料\P0收敛\架构\V2.1.1\正式交付\_build"
)
OUT_MD = os.path.join(BUILD_DIR, "STAGING_FIELD_BASELINE.md")

L = []


def w(s=""):
    L.append(s)


# ======================================================================
w()
w("---")
w()
w("## 第二节 V2.1 → V2.1.1 映射差异预判")
w()
w("### 2.0 方法、来源层级与判定纪律")
w()
w("**比对对象**")
w()
w("| 项 | 路径 | 说明 |")
w("|---|---|---|")
w("| V2.1 映射表 | `架构/V2.1/FIELD_MAPPING_V2.1.csv` | **208 行 = 1 表头 + 207 数据行**；本文引用格式为 `L<n>` = CSV 第 n 行 |")
w("| V2.1 数据模型 | `架构/V2.1/CORE_DATA_MODEL_V2.1.md` | 目标表列定义与 CHECK |")
w("| V2.1.1 定式 | `架构/V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md` | V0.2.2-r2 定式正文 |")
w("| 变更依据 | `架构/V2.1.1/V0.2.2/V0.2.1_TO_V0.2.2_CHANGELOG.md` | 逐项原设计→修改后 |")
w("| 实测基线 | 本文第一节（① 原始 CSV 逐行实算） | 七张表逐列统计 |")
w()
w("**来源层级标注（逐行标注，不得省略）**")
w()
w("| 符号 | 层级 | 可否直接当结论 |")
w("|---|---|---|")
w("| **①** | 原始 CSV 逐行实算（本文第一节及 `verify_v211_gaps.py` / `probe_parent_external_id.py`） | ✅ 可 |")
w("| **②** | 上游脚本产物（`run_manifest.json` / `stats.json` / `normalize.py`） | ❌ 仅作引用 |")
w("| **③** | 上游文档结论（V0.2.2 / V2.1 文档，带行号） | ❌ 仅作引用，须与①对碰 |")
w("| **④** | 基线文档定义（本文第一节） | ✅ 可（其本身由①构成） |")
w()
w("**判定纪律**：凡 ② ③ 与 ① 冲突，**以 ① 为准并在 §2.3 点名**。本节的每处处置都标注了层级；"
  "凡只标 ③ 而无 ① 支撑的，属于「定式已给、暂无数据可验」，已在 §2.6 单列。")
w()
w("---")
w()
w("### 2.1 差异行总表")
w()
w("**统计口径**：`失效` = V2.1 映射行在 V2.1.1 下语义错误、目标列消失或判据被推翻，必须删除或改写；"
  "`新增` = V2.1 映射表完全没有、V2.1.1 必须补的行；`连带` = 行本身保留但 notes/判据须改写。")
w()
w("| 组 | 目标表 | 失效 | 新增 | 连带 | 小计 |")
w("|---|---|---:|---:|---:|---:|")
w("| A | `data_dataset`（许可 9 列删除） | 11 | 0 | 0 | **11** |")
w("| A′ | `source_record` 许可三列 notes | 0 | 0 | 3 | **3** |")
w("| B | `source_record`（五段键 / 隔离 / 新增列） | 3 | 4 | 1 | **8** |")
w("| C | `historical_place` | 1 | 1 | 1 | **3** |")
w("| D | `historical_place_name` / `_location`（`rejected_by`） | 2 | 2 | 0 | **4** |")
w("| E | `data_quality_issue`（指纹 / 批次 / 计数） | 1 | 3 | 0 | **4** |")
w("| F | `source_record.record_scope`（4 值收敛） | 2 | 0 | 0 | **2** |")
w("| — | **`candidate_match`** | **0** | **0** | **0** | **0**（已核，见 §2.5） |")
w("| **合计** | | **20** | **10** | **5** | **35** |")
w()
w("> **合计 35 行 = 失效 20 + 新增 10 + 连带 5**。占 V2.1 全部 207 数据行的 **16.9%**。")
w()
w("---")
w()
w("### 2.2 逐行详述")
w()
w("#### 2.2.A `data_dataset`：许可 9 列删除（**11 行失效**）")
w()
w("**待删的 9 个目标列**（③ `CORE_DATA_MODEL_V2.1.md:144–152` 逐列核对，顺序与原文一致）：")
w("`license_id`(144) / `license_url`(145) / `attribution_text`(146) / `attribution_required`(147) / "
  "`modification_note_required`(148) / `overlay_license_id`(149) / `redistributable`(150) / "
  "`license_evidence`(151) / `license_verified_at`(152) —— **恰 9 列**，与任务书口径一致。")
w()
w("**删除依据**（③ `V0.2.2 §3.3` 逐字）：「不设计授权、许可、再分发管理；不重新引入 "
  "`attribution_text`、`citation_text` **或任何替代字段**」。")
w()
w("| V2.1 映射行（`L<n>`） | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |")
w("|---|---|---|---|")
w("| `L5` `data_datasets.homepage` → `data_dataset.license_url` | 目标列 `license_url` 删除（③:145）；且 notes「许可页缺失时暂用 homepage」把主页当许可页兜底，属 §3.3 禁止的许可语义 | **删除映射行**，或改指 `data_source.homepage`（`L203` 已有该列）。**不得**改名落到 `notes`/`evidence` 变相保留 | **存在**（①）：`data_datasets.homepage` 7/7 非空、唯一 5 |")
w("| `L6` `data_datasets.license_id` → `data_dataset.license_id` | 目标列删除（③:144） | **删除映射行**。暂存列随之失去入库通路 | **存在**（①）：7/7 非空、唯一 5（`no_spdx_academic_noncommercial` / `CC-BY-4.0` / `CC-BY-3.0` / `ODC-By-1.0` / `unconfirmed`） |")
w("| `L7` `data_datasets.license_url` → `(dropped)` | 行本身已是 dropped，但 notes「保留在 `license_evidence` 文本里」指向**已删除**的列（③:151） | **保留 dropped，改写 notes**：去掉 `license_evidence` 引用，改为「与 `homepage` 同源重复，V2.1.1 目标模型不设许可列 ⇒ 整列 dropped」 | **存在**（①）：6/7 非空、**1 行空** |")
w("| `L8` `data_datasets.redistributable` → `data_dataset.redistributable` | 目标列删除（③:150）；其「三态拆分」（`unconfirmed→true`+`license_id='unknown'`）随 `license_id` 一起消失 ⇒ transform 无落点 | **删除映射行** | **存在**（①）：7/7 非空、唯一 3（`no`/`yes_with_attribution`/`unconfirmed`） |")
w("| `L9` `data_datasets.attribution_text` → `data_dataset.attribution_text` | 目标列删除（③:146）；§3.3 明令**不重新引入 `attribution_text` 或任何替代字段** | **删除映射行**。**禁止**改名为 `citation_text` / `credit` / `source_credit` 落到其它列 | **存在**（①）：6/7 非空、1 行空、最长 158 字符 |")
w("| `L10` `data_datasets.acquisition_method` → `(derived)` `license_evidence` | 目标列 `license_evidence` 删除（③:151） | **删除映射行**。`acquisition_method` 若需保留须另找**非许可**目标列，否则整列 dropped（见 §2.6 Q2） | **存在**（①）：7/7 非空、唯一 6 |")
w("| `L11` `data_datasets.evidence` → `data_dataset.license_evidence` | 目标列删除（③:151）；且 `evidence` 的主要内容就是 EULA/授权取证文本 | **删除映射行** | **存在**（①）：7/7 非空、唯一 7、最长 459 字符 |")
w("| `L14` `(derived)` → `data_dataset.attribution_required` | 目标列删除（③:147）；其判据「`attribution_text` 非空 ⇒ true」随源列一起删 | **删除映射行** | `derived`（① 暂存无此列） |")
w("| `L15` `(derived)` → `data_dataset.modification_note_required` | 目标列删除（③:148） | **删除映射行** | `derived`（① 暂存无此列） |")
w("| `L16` `(derived)` → `data_dataset.overlay_license_id` | 目标列删除（③:149） | **删除映射行** | `derived`（① 暂存无此列） |")
w("| `L17` `(derived)` → `data_dataset.license_verified_at` | 目标列删除（③:152） | **删除映射行**。连带：`L759` 系列「导入前置校验会拒」的许可门禁（③ `CORE_DATA_MODEL_V2.1.md:759`）**同时失效**，须从 V2.1.1 `IMPORT_RULES` 前置校验清单中摘除 | `derived`（① 暂存无此列） |")
w()
w("> **A 组判定要点（防「改名替代」）**：§3.3 写的是「不重新引入 `attribution_text`、"
  "`citation_text` **或任何替代字段**」。因此 V2.1.1 的 `FIELD_MAPPING` 若出现任何以 "
  "`citation_`/`credit_`/`attribution_` 开头的 `target_column`，即判 FAIL——不管它挂在哪个表下。"
  "判定式可直接实现：`target_column` 正则 `^(attribution|citation|license)_` 命中行数 == 0。")
w()
w("---")
w()
w("#### 2.2.A′ `source_record` 许可三列：`dropped` 保留，notes 须改写（**3 行连带**）")
w()
w("| V2.1 映射行 | 失效原因 | V2.1.1 应有处置 | 暂存是否真实存在 |")
w("|---|---|---|---|")
w("| `L39` `source_records.license_status` → `(dropped)` | 行本身保留，但 notes「许可只从 `data_dataset` 读」——`data_dataset` 的许可列已全删，该理由**不再成立** | 保留 dropped，**改写 notes** 为「暂存按行冗余的许可三列，V2.1 已判 dropped；V2.1.1 目标模型不设任何许可列」。判据并入 §3.3 禁用词扫描 | **存在**（①）：29,391/29,391 非空、唯一 6、0 空 |")
w("| `L40` `source_records.redistributable` → `(dropped)` | 同上 | 同上 | **存在**（①）：29,391/29,391 非空、唯一 3（`no`/`yes_with_attribution`/`unconfirmed`）、0 空 |")
w("| `L41` `source_records.attribution_text` → `(dropped)` | 同上 | 同上 | **存在**（①）：29,383/29,391 非空、**8 行空**、唯一 5 |")
w()
w("> **连带待裁定项**：`L204` `(none).(generated)` → `data_source.license_homepage`。"
  "`data_source` 表的这一列也是许可列，但 V0.2.2 §3.3 只约束 `DATA_PROVENANCE` 文档与 "
  "`data_dataset` 的 9 列，**未提及 `data_source`**。见 §2.6 Q1。")
w()
w("---")
w()
w("#### 2.2.B `source_record`：五段键、隔离优先、4 个新增列（**3 失效 + 4 新增 + 1 连带**）")
w()
w("**定式依据**（③ `V0.2.2 §2.5.0` C29、`§2.3.1` 第 0 行、`§2.5`）：")
w()
w("```")
w("自然键 = (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)")
w("C29  parent_external_id 为必需段：")
w("     ① 任何情况下不得省略、不得以 NULL 兜底、不得用空串代替；")
w("     ② 无父级概念的数据集（CHGIS place）写入哨兵值 '-'（不是 NULL）；")
w("     ③ 派生失败 ⇒ 整批 failed（与 A12 同一处置），不是默认放行；")
w("     ④ 哨兵必须是 parent_external_id 值域之外的保留字，且只能在 data_dataset")
w("        或一张常量表里声明一次。")
w("```")
w()
w("| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |")
w("|---|---|---|---|")
w("| `L46` `(derived)` → `source_record.parent_external_id`，`text`，**`required=N`**，`json_field`，notes「Pleiades→place_id；MCGD→LocID；**CHGIS/WHG→NULL**」 | **三重失效**：(a) `required` 由 `N` 变为**必需段**（③ C29①）；(b) notes 的「→NULL」被 C29① 明文禁止，CHGIS place 须写哨兵 `'-'`（③ C29②）；(c) V2.1 目标列定义是可空无约束（③ `CORE_DATA_MODEL_V2.1.md:265`），V2.1.1 须加 `NOT NULL` | **改写**：`required=Y`；`transform=json_field+sentinel`；notes 改为「Pleiades `name`/`location`/`edge` → `raw_payload.place_id`；MCGD → `raw_payload.LocID`；无父级概念者 → 哨兵 `'-'`（哨兵在常量表声明一次，③ C29④）；派生失败 ⇒ 整批 failed」。**必须补齐 Pleiades place 与 WHG 全组的规则**（见 §2.4） | **`derived`**（① 暂存 14 列中**无** `parent_external_id`）；派生来源 = `source_records.raw_payload_json` |")
w("| `L50` `(derived)` → `source_record.is_active`，`rule`，notes「重复 ID 的第 2 行 ⇒ false（QUARANTINE）」 | notes 的判据被 V0.2.2 §2.3.1 **第 0 行**推翻：判定表在最前面新增「重复检测优先」行，先于 V2.1 的全部 10 行；且「第 2 行」的定序依据由 `raw_record_index` 改为 `content_hash` | **改写 notes**：`is_active=false` ⇔ 同**五段键的四段前缀**（含 `parent_external_id`）下存在另一行 `content_hash` 相同且 `duplicate_ordinal` 更小；隔离是**每批重算的派生结论**，不是一次置位；O7 解除保护**不得**复活它 | `derived`（① 暂存无此列） |")
w("| `L45` `(derived)` → `source_record.occurrence_key`，`parent_ordinal\\|''` | **语义冲突（连带）**：V2.1 §4.2 定义 `occurrence_key = <parent_external_id>#<按 raw_record_index 升序的名次>`；V0.2.2 的 `duplicate_ordinal` 按 **`content_hash`** 定序。**两者定序依据不同，不是同一列**，但 V2.1 的 `UNIQUE(dataset_id, record_scope, external_id, occurrence_key)` 与 V0.2.2 的五段键在段集上重叠 | **改写 notes**，写明 `occurrence_key`（`raw_record_index` 定序、V2 遗留）与 `duplicate_ordinal`（`content_hash` 定序、V2.1.1 新增）**并存且定序依据不同**；并明确 `UNIQUE` 由 4 段升级为 **5 段**（含 `parent_external_id`）⇒ CHECK `is_active OR occurrence_key <> ''`（③:279）需同步复核 | `derived`（① 暂存无此列） |")
w()
w("**B 组必须新增的 4 行（V2.1 映射表完全没有）**")
w()
w("| 新增行 | 定式（含层级） | 暂存是否真实存在 |")
w("|---|---|---|")
w("| `source_records.(derived)` → `source_record.duplicate_ordinal` | 组内按 `(content_hash ASC, raw_record_index ASC)` 定序后的名次（③ `V0.2.2 §2.5`）。实测权威值：`ordinal=0` = **29,377**，另 7 组 × 2 行 = 14 行、`ordinal` 1/2 各 7 行（③ `§0 N04`） | **`derived`**（① 暂存无此列）。由 `raw_payload_json` + 定序规则派生 |")
w("| `source_records.(derived)` → `source_record.inactive_reason` | 3 值：`duplicate_quarantine` / `source_absent` / `batch_rolled_back`（③ `§2.3.1` 第 0 行、`§2.2.4`）。**V2.1 目标表根本没有这一列**（③ `CORE_DATA_MODEL_V2.1.md:258–273` 逐列核对：无）⇒ 这是 V2.1.1 的新表列，但 V0.2.2 §1「新列 +2」**未计入** | **`derived`**（① 暂存无此列） |")
w("| `source_records.(derived)` → `source_record.inactive_at` | 与 `inactive_reason` 同生（③ `§2.3.2` 第 5 条「`inactive_reason` + `inactive_at` + `inactive_in_batch_id`（C21/C22）完整保留」；`§2.2.4` 视图按 `inactive_at DESC NULLS LAST` 取「最后失效原因」） | **`derived`**（① 暂存无此列） |")
w("| `source_records.(derived)` → `source_record.inactive_in_batch_id` | 同上（③ `§2.3.2`、`§2.2.4`） | **`derived`**（① 暂存无此列） |")
w()
w("> **⚠ B 组内部结构冲突（必须点名，③ 与 ③ 冲突）**："
  "V0.2.2 §1 合计栏逐字写「**新表 0，新列 +2（仅 `rejected_by` × 2 表）**」，"
  "§1 第 66 行与 CHANGELOG 第 17 行同样写 +2。"
  "但 §2.3.1 / §2.3.2 / §2.2.4 三处实际引用了 `source_record` 的 "
  "`inactive_reason` / `inactive_at` / `inactive_in_batch_id` 三列，"
  "而 V2.1 目标表（③ `CORE_DATA_MODEL_V2.1.md:258–273`）**一列都没有**。"
  "⇒ 真实新列数至少为 **+5（2 × `rejected_by` + 3 × 隔离台账列）**，不是 +2。"
  "这不是 QA 推断，是 V0.2.2 正文与 V2.1 表定义逐列对碰的结果（① 侧可佐证：暂存 14 列中 3 列全无）。"
  "**V2.1.1 编制时必须先裁定这 3 列加不加**，否则 `IMPORT_RULES` 第 0 行判定表无字段可写。")
w()
w("> **C29 与索引的连带**：V2.1 的 `UNIQUE` 是 **4 段** "
  "`(dataset_id, record_scope, external_id, occurrence_key)`（③ `CORE_DATA_MODEL_V2.1.md:276`），"
  "V0.2.2 C29 要求 **5 段含 `parent_external_id`**。"
  "这不是映射行，但直接决定 `L45` / `L46` 的语义；V2.1.1 `CORE` 与 ER 图必须同步，"
  "否则 UNIQUE 会退化成四段键 ⇒ 398 组误隔离（③ `§2.5.0`）。")
w()
w("---")
w()
w("#### 2.2.C `historical_place`（**1 失效 + 1 新增 + 1 连带**）")
w()
w("| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |")
w("|---|---|---|---|")
w("| `L59` `historical_places.record_status` → `historical_place.record_status`，`enum_rule = staging\\|published\\|merged\\|rejected`（**4 值**） | V0.2.2 §2.1.1 定 `record_status` 为 **3 值** `staging` / `rejected` / `merged`（③）；而 V2.1 目标表的 CHECK 是 **4 值**（③ `CORE_DATA_MODEL_V2.1.md:338`，含 `published`）。⇒ `published` 的去留是本轮真实变更点，但 V0.2.2 只在 §5.5「视图派生列」一带隐含处理，**未在 §2.1.1 声明该 CHECK 变更** | **改写 `enum_rule` 为 3 值**，并在 V2.1.1 `CORE` 中同步修订 CHECK。若 `published` 需保留作发布态，须由架构师显式裁定（§2.6 Q3） | **存在**（①）：`historical_places.record_status` 19,039/19,039 非空、**唯一 1 值 = `staging`** |")
w("| **新增**：`historical_places.(derived)` → `historical_place.dataset_id` | V0.2.2 §2.2.2 的 `v_place_evidence` 视图 SQL **逐字依赖**它：`FROM historical_place p JOIN source_record sr ON sr.dataset_id = p.dataset_id`（③ 第 203 行）。但 V2.1 §5.2.1 规则 1 明文「`historical_place` / `_name` / `_location` **不带 dataset 列**，归属通过 `source_record_id` 回溯」（③ `CORE_DATA_MODEL_V2.1.md:176`），且 V0.2.2 §1「新列 +2」**未计入它** | **必须新增该映射行**，`transform = join(created_from_source_record_id → source_record.dataset_id)`（`L69` 已定义 `created_from_source_record_id` 的派生规则，可直接复用）。**同时必须修订 V2.1 §5.2.1 规则 1 或改用 `JOIN source_record` 表达**——两条定式当前互斥 | **`derived`**（① `historical_places` 15 列中**无** `dataset_id`）；派生来源 = `created_from_source_record_id`（① 亦为 derived，`L69`） |")
w("| `L58` `historical_places.primary_external_id` → `(dropped)`（连带） | 行本身保留 dropped，但 notes「MCGD 643 行填 LocID 而 source_record 用 NameID，join 不上」**与本轮冲突**：C29 把 `parent_external_id` 定为必需段后，MCGD 的 `LocID` 正是 `parent_external_id` 的来源（③ `§2.5.0`、`CORE_DATA_MODEL_V2.1.md:298`）⇒ 「join 不上」的说法需要重新表述 | 保留 dropped，**改写 notes**：补一句「MCGD 的 `LocID` 不用于 `external_id` 的 join，但它是 `parent_external_id` 的来源，二者用途不同、不可混淆」 | **存在**（①）：19,039/19,039 非空、唯一 18,997、最长 15 字符 |")
w()
w("> **⚠ 关于「`historical_place` 新增 `grain_key`」——任务书该项与 V0.2.2-r2 正文不符，予以驳回**：")
w("> - ③ `V0.2.2 §2.7.2` 第 750 行逐字写：`OR (p.grain_key = sr.parent_external_id AND sr.record_scope <> 'place')` "
  "是 **V0.2.1 的旧写法**，V0.2.2 已将「`<> 'place'` 过宽」改为**白名单 + 数据集显式声明**。")
w("> - ③ `CHANGELOG` 第 271 行在「本轮新增字段」栏逐字写：**「字段：无（`data_dataset.place_grain` "
  "已在 V0.2.1 的 `grain_key` 派生式中使用）」**。")
w("> - ③ `CHANGELOG` 第 254 行的 `p.grain_key` 出现在「原设计」列（即被替换的旧式），不是「修改后」列。")
w("> ⇒ **`grain_key` 不是 V2.1.1 新增列，而是已被 `data_dataset.place_grain` 取代的废弃概念。** "
  "V2.1.1 的 `FIELD_MAPPING` **不应**新增 `grain_key` 行；若新增即判 FAIL。")
w("> 附带：`data_dataset.place_grain` 本身也**不是**新增列（③ `V0.2.2 §1` 第 68 行与 §2.7.2 第 711 行两处回退，"
  "它是 V2 既有列 `CORE_DATA_MODEL_V2.md:208`，V2.1 收敛为 2 值），其映射行 `L19` 只需把 "
  "`enum_rule` 从 3 值改为 `per_record\\|per_parent_external_id` 2 值——**这已计入 `L19` 的常规修订，不属本轮新增**。")
w()
w("---")
w()
w("#### 2.2.D `historical_place_name` / `_location`：`rejected_by`（**2 失效 + 2 新增**）")
w()
w("**定式依据**（③ `V0.2.2 §2.2.1`，逐字）：")
w()
w("```sql")
w("ALTER TABLE historical_place_name     ADD COLUMN rejected_by text NULL;")
w("ALTER TABLE historical_place_location ADD COLUMN rejected_by text NULL;")
w("-- C25：(record_status = 'rejected') = (rejected_by IS NOT NULL)   —— 同生同灭")
w("-- C26：rejected_by IS NULL OR rejected_by IN ('auto','manual')     —— 值域 2")
w("```")
w()
w("| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |")
w("|---|---|---|---|")
w("| `L110` `historical_place_locations.(derived)` → `record_status`，`gate`，`staging\\|published\\|rejected`，notes「`crs_confidence='unknown'` 或 `geom` NULL ⇒ `staging`」 | 由**单列 gate** 变为**双列联动**：C25 要求 `record_status='rejected'` ⟺ `rejected_by IS NOT NULL`，只写 `record_status` 的映射行无法满足该 CHECK | **改写**：保留 `gate` 逻辑，但 `transform` 改为 `gate + rejected_by 联动`；`enum_rule` 的 `published` 去留随 `L59` 一并裁定（§2.6 Q3） | **`derived`**（① `historical_place_locations` 22 列中**无** `record_status`、无 `rejected_by`） |")
w("| `L132` `historical_place_names.(derived)` → `record_status`，`literal 'staging'`，`staging\\|published\\|rejected` | 同上；且 `literal 'staging'` 写法下 C25 自动满足（`staging≠rejected` ⇒ `rejected_by` 必为 NULL），但映射行**未表达**该联动 | **改写**：`transform = literal 'staging' + rejected_by=NULL`，notes 补「C25 由本行与 `rejected_by` 行共同满足」；`published` 去留同 Q3 | **`derived`**（① `historical_place_names` 13 列中**无** `record_status`、无 `rejected_by`） |")
w()
w("**D 组必须新增的 2 行**")
w()
w("| 新增行 | 定式（含层级） | 暂存是否真实存在 |")
w("|---|---|---|")
w("| `historical_place_names.(derived)` → `historical_place_name.rejected_by` | `text NULL`，初值 `literal NULL`（本批 0 条 rejected，③ `V0.2.2 §0 R24`：暂存 0 条 rejected / merged / locked）；值域 `auto\\|manual`（C26）；与 `record_status` 同生同灭（C25） | **`derived`**（① 暂存 13 列中**无** `rejected_by`）。本批无源列可导，只能按规则置 NULL |")
w("| `historical_place_locations.(derived)` → `historical_place_location.rejected_by` | 同上 | **`derived`**（① 暂存 22 列中**无** `rejected_by`） |")
w()
w("> **① 侧实测支撑（R24 印证）**：暂存 `historical_place_names` / `historical_place_locations` "
  "**均无 `record_status` 列、无 `rejected_by` 列**，两表 47,503 / 18,103 行里也**没有**任何 "
  "rejected / merged / locked 语义列。⇒ 本批两列的入库值**只能**是 "
  "`record_status='staging'` + `rejected_by=NULL`，C25/C26 **构造上自动满足**，无需运行期判定。"
  "这一点应当写进 V2.1.1 `IMPORT_RULES`，避免实现者去找一个不存在的暂存列。")
w()
w("---")
w()
w("#### 2.2.E `data_quality_issue`：指纹、批次、计数（**1 失效 + 3 新增**）")
w()
w("**定式依据**（③ `V0.2.2 §2.5.7`，r2 新增，team-lead 裁定 U19，逐字）：")
w()
w("```")
w("content_hash       : sha256   -- 内容身份。导入器算。用于 ordinal 定序、跨版本稳定、重复隔离判定")
w("issue_fingerprint  : md5      -- 台账去重键。PostgreSQL 内算")
w("                              -- （GENERATED ALWAYS AS md5(jsonb_build_array(...)::text) STORED）")
w('                              -- 用于识别"同一问题重复出现"，承载 first_batch_id / last_batch_id / occurrence_count')
w("```")
w()
w("| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |")
w("|---|---|---|---|")
w("| `L176` `data_quality_issues.(derived)` → `data_quality_issue.batch_id`，`bigint`，`Y`，`batch` | V0.2.2 §2.5.7 把单列 `batch_id` 拆为 **`first_batch_id` + `last_batch_id`**，并由 `issue_fingerprint` 承载「同一问题重复出现」的 `occurrence_count`（③） | **拆为两行**：`first_batch_id`（`bigint`，`Y`，`batch`）与 `last_batch_id`（`bigint`，`N`，`batch`） | **`derived`**（① 暂存无 `batch_id` / `first_batch_id` / `last_batch_id`） |")
w()
w("**E 组必须新增的 3 行**")
w()
w("| 新增行 | 定式（含层级） | 暂存是否真实存在 |")
w("|---|---|---|")
w("| `data_quality_issues.(derived)` → `data_quality_issue.occurrence_count` | `integer`，`NOT NULL DEFAULT 1`；同一 `issue_fingerprint` 每批重复出现则 `+= 1`（③ `§2.5.7`、`CHANGELOG:190`） | **`derived`**（① 暂存 11 列中**无**） |")
w("| `data_quality_issues.(derived)` → `data_quality_issue.issue_fingerprint` | **PostgreSQL 生成列**，非导入器写入：`GENERATED ALWAYS AS md5(jsonb_build_array(...)::text) STORED`（③ `§2.5.7`） | **`derived`**（① 暂存 11 列中**无** `issue_fingerprint`）；构成要素只能取自暂存的 11 列 |")
w("| `data_quality_issues.(derived)` → `data_quality_issue.first_batch_id` | `bigint`，`Y`，= 本批 `batch_id`（与 `L176` 原值同源） | **`derived`**（① 暂存无） |")
w()
w("> **⚠ E 组算法更正（与任务书口径的差异，须点名）**：")
w("> 任务书写「`issue_fingerprint` **改 JSON 数组编码**」——**编码**部分正确"
  "（`jsonb_build_array(...)::text`），但必须一并写明：**算法是 `md5`，且 V0.2.2-r2 已明确裁定不得改为 `sha256`**。")
w("> ③ 依据：`V0.2.2 §2.5.7` 标题即「两种摘要算法并存是**有意设计**，不可互换、不可统一（r2 新增，team-lead 裁定 U19）」；"
  "§5.2 断言 `ALG-1`；`CHANGELOG` R2-03（第 835–842 行）与 r2 裁定表第 19 行："
  "「**`issue_fingerprint` 保持 md5**……改算法会使 **197 条已算历史指纹全部对不上**」。")
w("> ⇒ V2.1.1 的 `FIELD_MAPPING` / `CORE` / `SQL` 三处若把 `issue_fingerprint` 写成 `sha256`，**即判 FAIL**。"
  "同理，`content_hash` 必须是 **sha256**（`§2.5.6` 规范定义），两者**不得互换**。")
w()
w("> **⚠ E 组实测缺口：`L174` 的 fallback 无源列可实现（① 实测）**")
w("> `L174` notes 写「有 `source_record_id` 则 join 取；**数据集级问题按 `raw_file` 归属**」。")
w("> 但①实测：`data_quality_issues.csv` 只有 **11 列**"
  "（`issue_id`/`source_id`/`source_dataset`/`source_record_id`/`issue_type`/`severity`/"
  "`field_name`/`observed_value`/`expected_rule`/`action_taken`/`notes`），**没有 `raw_file` 列**，"
  "也没有 `dataset_id` 列。而 `source_record_id` 有 **6 行空值**（12,625/12,631 非空）。")
w("> ⇒ 这 6 行**既无 `source_record_id` 可 join，也无 `raw_file` 可归属**，`L174` 的 `dataset_id`"
  "（`required=Y`）**无解**。V2.1.1 必须为这 6 行显式补一条规则（或判定为整批 failed / 落 `source_id` 级兜底），"
  "否则 `required=Y` 写不进去。见 §2.6 Q4。")
w()
w("**① 侧实测：`issue_fingerprint` 的可用构成要素**（暂存 11 列的实测基数，供架构师选段）：")
w()
w("| 暂存列 | 非空 / 总 | 唯一值 | 是否适合入指纹 |")
w("|---|---:|---:|---|")
w("| `issue_type` | 12,631 / 12,631 | **13** | ✅ 主段 |")
w("| `severity` | 12,631 / 12,631 | 3（`info`/`blocking`/`warning`） | ✅ |")
w("| `field_name` | 12,631 / 12,631 | **17**（含 `BEG_RULE\\|END_RULE` 复合写法） | ✅ |")
w("| `observed_value` | 12,304 / 12,631 | 3,406（**327 行空**） | ⚠️ 空值需约定 |")
w("| `expected_rule` | 12,631 / 12,631 | 16 | ✅ |")
w("| `action_taken` | 12,631 / 12,631 | 3（`preserved_and_flagged`/`needs_manual_review`/`discarded`） | ✅ |")
w("| `source_record_id` | 12,625 / 12,631 | 12,504（**6 行空**） | ⚠️ 空值需约定 |")
w("| `notes` | 12,631 / 12,631 | 50 | ❌ 自由文本，不建议 |")
w()
w("---")
w()
w("#### 2.2.F `record_scope` 值域收敛为 4 值，**不得出现 `connection`**（**2 失效**）")
w()
w("**定式依据**（③ `V0.2.2 §2.7.2` R21、§0 N10、`§2.7.3` A12）：")
w("「`record_scope` 全域只有 **4 种**（R21，**无第五种**）」，「出现第五种 ⇒ 整批 `failed`（不默认放行）」。")
w()
w("| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |")
w("|---|---|---|---|")
w("| `L35` `source_records.external_id_type` → `(derived)` `record_scope`，notes「**16 种取值** → 4 个 scope，逐条查表，不猜」 | **notes 与实测不符**：① 实测 `external_id_type` **只有 11 种**，不是 16 种（详见 §2.3 D-3）。「16 种」若被 V2.1.1 沿用，会让实现者去找 5 个不存在的取值 | **改写 notes 为 11 种**，并按 §2.3 的 11→4 查表逐条列全 | **存在**（①）：29,391/29,391 非空、唯一 **11** |")
w("| `L44` `source_records.(derived)` → `source_record.record_scope`，`Y`，`lookup(dataset_id, external_id_type)`，`place\\|location\\|name\\|edge` | 行本身保留，但：① 查表基数由 16 改为 **11**（同上）；② 判据由 V2.1 的「`external_id_type` 查表」升级为 V0.2.2 §2.7.1 **白名单 + 数据集显式声明**（`data_dataset.place_grain`）；③ 值域**必须**是 4 值，任何 `connection` 字面量出现即 FAIL | **改写**：`enum_rule` 保持 4 值；`transform` 改为 `lookup(11→4 查表) + §2.7.1 白名单`；notes 补「`external_id_type` 中的 `pleiades_connection_id` 映射到 **`edge`**，**不是** `connection`；值域外取值 ⇒ A12 整批 failed」 | **`derived`**（① 暂存 14 列中**无** `record_scope`） |")
w()
w("**① 实测的 11 → 4 权威查表**（`source_records` 29,391 行逐行实算，与 ③ `V0.2.2 §2.7.2` N10 完全闭合）")
w()
w("| `external_id_type` | 行数 | → `record_scope` | 所属 `dataset_id` |")
w("|---|---:|---|---|")
w("| `chgis_sys_id` | 15,748 | `place` | `chgis_v6_prefecture_points` 5,226 + `chgis_v6_county_points` 10,522 |")
w("| `pleiades_place_id` | 2,643 | `place` | `pleiades_gis_4_1_slice` |")
w("| `whg_source_id` | 5 | `place` | `whg_geoname_s_gn_sample` 4 + `whg_getty_tgn_sample` 1 |")
w("| `whg_place_id` | 2 | `place` | `whg_hgis_de_las_indias_sample` |")
w("| **place 小计** | **18,398** | | = ③ N10 的 18,398 ✓ |")
w("| `pleiades_name_id` | 4,579 | `name` | `pleiades_gis_4_1_slice` |")
w("| `mcgd_nameid` | 960 | `name` | `mcgd_zenodo_22094815_head960` |")
w("| `whg_place_name_index` | 223 | `name` | WHG 三个数据集（201 + 19 + 3） |")
w("| **name 小计** | **5,762** | | = ③ N10 的 5,762 ✓ |")
w("| `pleiades_location_id` | 2,460 | `location` | `pleiades_gis_4_1_slice` |")
w("| `whg_geometry` | 5 | `location` | `whg_geoname_s_gn_sample` 4 + `whg_getty_tgn_sample` 1 |")
w("| `whg_geom_index` | 3 | `location` | `whg_hgis_de_las_indias_sample` |")
w("| **location 小计** | **2,468** | | = ③ N10 的 2,468 ✓ |")
w("| `pleiades_connection_id` | 2,763 | **`edge`**（**非 `connection`**） | `pleiades_gis_4_1_slice` |")
w("| **edge 小计** | **2,763** | | = ③ N10 的 2,763 ✓ |")
w("| **总计** | **29,391** | | = ① 实测总行数 ✓ |")
w()
w("> **四条闭合校验全部通过**（① 侧逐项与 ③ N10 对碰，0 偏差）："
  "place 18,398 / name 5,762 / location 2,468 / edge 2,763，合计 29,391。")
w()
w("> **`connection` 判定式（可直接实现）**：V2.1.1 的 `FIELD_MAPPING` / `CORE` / `IMPORT_RULES` / `SQL` 中，"
  "正则 `record_scope\\s*(=|IN\\s*\\(|::)\\s*'?connection` 的命中次数 **== 0**；"
  "且 `record_scope` 的枚举声明处必须恰好含 4 个值 `place`/`name`/`location`/`edge`。")
w()
w("> **命名陷阱（实现者易踩，① 实测）**：`whg_place_name_index` 名字里有 `place`，"
  "但它映射到 **`name`** scope（223 行）；`whg_place_id`（2 行）才映射到 `place`。"
  "这正好印证 `L35` 原 notes 的「**逐条查表，不猜**」——V2.1.1 必须把 11 条逐条写出来，不得按名字子串推断。")
w()
w("---")
w()
w("### 2.3 实测发现与文档不一致之处（点名清单）")
w()
w("> 全部为 ① 与 ③ 对碰的结果。凡冲突，**以 ① 为准**。")
w()
w("| # | 不一致项 | ① 实测值 | ③ 文档值 | 影响 | 建议处置 |")
w("|---|---|---|---|---|---|")
w("| **D-1** | `source_record` 新列数 | V2.1 目标表（③ `CORE_DATA_MODEL_V2.1.md:258–273`）**无** `inactive_reason`/`inactive_at`/`inactive_in_batch_id`/`duplicate_ordinal`；暂存（①）亦 4 列全无 ⇒ 至少需新增 4 列 | ③ `V0.2.2 §1` §0/§4第11项/CHANGELOG 三处逐字写「新列 **+2**（仅 `rejected_by` × 2 表）」，但 §2.3.1/§2.3.2/§2.2.4 已引用这 4 列 | **定式自相矛盾**：`IMPORT_RULES` 第 0 行判定表与 `v_place_liveness` 视图无字段可写 | 请架构师裁定并统一「新列数」口径（§2.6 Q5） |")
w("| **D-2** | `historical_place.dataset_id` | ① 暂存 15 列中**无**；③ V2.1 §5.2.1 规则 1 明令「不带 dataset 列」 | ③ `V0.2.2 §2.2.2` 第 203 行视图 SQL 逐字写 `ON sr.dataset_id = p.dataset_id`，依赖该列存在 | **视图无法编译**；且与 V2.1 既有决策直接冲突 | 二选一：加列并修订 §5.2.1 规则 1，或改视图为 `JOIN source_record`（§2.6 Q6） |")
w("| **D-3** | `external_id_type` 取值种类数 | ① **11 种** | ③ `V2.1 FIELD_MAPPING L35` notes 写「**16 种取值**」 | 实现者会去找 5 个不存在的取值；`A12` 的「第五种 ⇒ 整批 failed」判据基数错 | 改为 11 种，并按 §2.2.F 查表逐条列全 |")
w("| **D-4** | `historical_place.record_status` 值域 | ③ V2.1 目标表 CHECK = **4 值**（`staging`/`published`/`merged`/`rejected`，`CORE_DATA_MODEL_V2.1.md:338`）；① 暂存唯一 1 值 = `staging` | ③ `V0.2.2 §2.1.1` 标题写「**3 值，不变**」 | 「不变」与 V2.1 的 4 值 CHECK 不符 ⇒ `published` 去留未声明 | 请架构师显式裁定（§2.6 Q3） |")
w("| **D-5** | `parent_external_id` 派生覆盖率 | ① 29,391 行中仅 **10,765 行**（36.6%）能从 `raw_payload_json` 取到 `place_id` / `LocID`；**18,626 行取不到** | ③ `V0.2.2 §2.5.0` C29② 只写了「无父级概念的数据集（**CHGIS place**）写入哨兵 `'-'`」，覆盖 15,748 行 | **2,878 行无规则可依**（详见 §2.4） | 请架构师补齐其余 2,878 行的规则（§2.6 Q7） |")
w("| **D-6** | `data_quality_issue.dataset_id` 的 fallback | ① `data_quality_issues` 11 列中**无 `raw_file`、无 `dataset_id`**；`source_record_id` **6 行空** | ③ `V2.1 L174` notes「数据集级问题按 **`raw_file`** 归属」 | 这 6 行 `dataset_id`（`required=Y`）**无解** | 补规则或判整批 failed（§2.6 Q4） |")
w("| **D-7** | `issue_fingerprint` 算法 | —（生成列，暂存无此列，① 无法验） | ③ `V0.2.2 §2.5.7` + `CHANGELOG R2-03` + §6 r2 裁定 19：**保持 `md5`**，明令不得改 `sha256` | 若 V2.1.1 误写 `sha256` ⇒ 197 条已算历史指纹全失效 | 三处（CORE / SQL / 映射）逐字写 `md5`，并加 `ALG-1` 断言 |")
w("| **D-8** | `candidate_matches` 行数 | ① **53,137 行 × 19 列** | ③ V0.2.2 §0 权威数字表**未列** `candidate_match` | 缺一张表的基线行数 | 建议补入 §0 或明确「不入权威表」 |")
w()
w("---")
w()
w("### 2.4 `parent_external_id` 派生覆盖率（**D-5 的展开，① 逐行实算**）")
w()
w("C29 把 `parent_external_id` 定为五段键的**必需段**且禁止 NULL，但暂存 CSV **没有这一列**，"
  "只能从 `raw_payload_json` 派生。下表按 `(dataset_id, external_id_type)` 交叉统计实测覆盖率：")
w()
w("| `dataset_id` | `external_id_type` | `record_scope` | 总行 | 可取到 | **取不到** | 命中键 |")
w("|---|---|---|---:|---:|---:|---|")
w("| `chgis_v6_county_points` | `chgis_sys_id` | place | 10,522 | 0 | **10,522** | — |")
w("| `chgis_v6_prefecture_points` | `chgis_sys_id` | place | 5,226 | 0 | **5,226** | — |")
w("| `mcgd_zenodo_22094815_head960` | `mcgd_nameid` | name | 960 | **960** | 0 | `LocID` |")
w("| `pleiades_gis_4_1_slice` | `pleiades_name_id` | name | 4,579 | **4,579** | 0 | `place_id` |")
w("| `pleiades_gis_4_1_slice` | `pleiades_connection_id` | edge | 2,763 | **2,763** | 0 | `place_id` |")
w("| `pleiades_gis_4_1_slice` | `pleiades_place_id` | place | 2,643 | 0 | **2,643** | — |")
w("| `pleiades_gis_4_1_slice` | `pleiades_location_id` | location | 2,460 | **2,460** | 0 | `place_id` |")
w("| `whg_geoname_s_gn_sample` | `whg_place_name_index` | name | 201 | 0 | **201** | — |")
w("| `whg_geoname_s_gn_sample` | `whg_source_id` | place | 4 | 0 | **4** | — |")
w("| `whg_geoname_s_gn_sample` | `whg_geometry` | location | 4 | 0 | **4** | — |")
w("| `whg_getty_tgn_sample` | `whg_place_name_index` | name | 19 | 0 | **19** | — |")
w("| `whg_getty_tgn_sample` | `whg_source_id` | place | 1 | 0 | **1** | — |")
w("| `whg_getty_tgn_sample` | `whg_geometry` | location | 1 | 0 | **1** | — |")
w("| `whg_hgis_de_las_indias_sample` | `whg_place_name_index` | name | 3 | 0 | **3** | — |")
w("| `whg_hgis_de_las_indias_sample` | `whg_geom_index` | location | 3 | **3** | 0 | `place_id` |")
w("| `whg_hgis_de_las_indias_sample` | `whg_place_id` | place | 2 | 0 | **2** | — |")
w("| **合计** | | | **29,391** | **10,765** | **18,626** | |")
w()
w("**按 `record_scope` 汇总**")
w()
w("| `record_scope` | 总行 | 可取到 | **取不到** | 覆盖率 | C29② 是否覆盖 |")
w("|---|---:|---:|---:|---:|---|")
w("| `place` | 18,398 | 0 | **18,398** | 0% | ⚠️ **仅覆盖 CHGIS 的 15,748 行** |")
w("| `name` | 5,762 | 5,539 | **223** | 96.1% | ❌ **未覆盖**（WHG 223 行） |")
w("| `location` | 2,468 | 2,463 | **5** | 99.8% | ❌ **未覆盖**（WHG 5 行） |")
w("| `edge` | 2,763 | 2,763 | 0 | 100% | —（不适用，本身有 `place_id`） |")
w()
w("**结论（① 实测）**：")
w()
w("1. **C29② 只覆盖了 15,748 / 18,626 = 84.6% 的「取不到」行，仍有 2,878 行无规则可依。**")
w("2. 未覆盖的 2,878 行构成：`pleiades_place_id` **2,643** + `whg_place_name_index` **223** + "
  "`whg_geometry` **5** + `whg_source_id` **5** + `whg_place_id` **2**。")
w("3. **尤其要注意 `place` scope 的 0% 覆盖率**：18,398 行 `place` 记录**全部**取不到父级——"
  "这不是缺陷，而是 `place` 记录本身就是实体（不是某实体的子行）。"
  "但 C29① 禁止 NULL，所以**全部 18,398 行都必须落哨兵或其它规则**，"
  "而 C29② 只说了「CHGIS place」。Pleiades place（2,643）与 WHG place（7）**口径缺失**。")
w("4. ① 侧可交叉印证 ③ 的正确部分：V2.1 `CORE_DATA_MODEL_V2.1.md:298` 写"
  "「Pleiades 9,802 行全有；MCGD 960 行全有」——① 实测 **Pleiades 命中 9,802 / MCGD 命中 960**，"
  "**逐项吻合**。⇒ ③ 的这条是对的，错的只是它没说清剩下 18,626 行怎么办。")
w()
w("---")
w()
w("### 2.5 已核、**无** V2.1.1 驱动变更的表")
w()
w("| 表 / 映射行段 | 核实结论 | ① 实测支撑 |")
w("|---|---|---|")
w("| `candidate_match`（`L139–L162`，24 行） | V0.2.2-r2 全篇**未对 `candidate_match` 提出任何结构变更**。⇒ 24 行**全部维持 V2.1 原样**，本轮 0 失效 / 0 新增 | `candidate_matches` **53,137 行 × 19 列**；`relation_type` 唯一 **6 值**（③ V2.1 `L140` 枚举报 7 值 ⇒ 6/7 出现，属正常，非 V2.1.1 变更）；`reviewer` / `reviewed_at` **53,137 行 100% 空、唯一值 0** ⇒ 印证 `L156`/`L157` 的 `derived` 判定；`status` 唯一 2 值（`candidate` / `needs_manual_review`） |")
w("| `import_batch`（`L183–L200`，18 行） | V0.2.2 §2.4 只改**统计口径**（R1 减 `N_quar`、`failed_count`；R2 只统计回滚相关台账类型），**未改表结构** ⇒ 18 行维持原样，但 `L193 quarantined_count` / `L195 failed_count` 的 **notes 须按 R1 口径改写** | — |")
w("| `data_source`（`L201–L208`，8 行） | 除 `L204 license_homepage` 待裁定（§2.6 Q1）外，其余 7 行维持原样 | — |")
w("| `data_dataset` 非许可列（`L2/L3/L4/L12/L13/L18–L29`，15 行） | 维持原样。`L19 place_grain` 的 `enum_rule` 由 3 值收敛为 2 值属 **V2.1 已完成的收敛**（③ `CORE_DATA_MODEL_V2.1.md:136/154`），不计入本轮 | `data_datasets` **7 行 × 11 列** |")
w()
w("---")
w()
w("### 2.6 待架构师裁定项（QA 不下判定，只列事实与选项）")
w()
w("> **本清单不是「已发现问题」的终审结论**，而是 V2.1.1 编制前**必须先有答案**的 7 个问号。"
  "每一条都给出了 ① 实测事实与可选处置，由架构师定夺。")
w()
w("| # | 问题 | ① 实测事实 | 可选处置 |")
w("|---|---|---|---|")
w("| **Q1** | `data_source.license_homepage`（`L204`）是否随 9 列一并删除？ | ③ `V0.2.2 §3.3` 只约束 `DATA_PROVENANCE` 文档与 `data_dataset` 的 9 列，**未提及 `data_source`** | (a) 一并删除（彻底无许可语义）；(b) 保留但改名（改名即触 §3.3「任何替代字段」）；(c) 保留原名并写明「仅展示链接、不构成许可判定」 |")
w("| **Q2** | `data_datasets.acquisition_method`（`L10`）失去 `license_evidence` 落点后怎么办？ | ① 7/7 非空、唯一 6，内容是取数方式（如 `full DBF + sidecars read from the shipped V6 zip`） | (a) 整列 dropped；(b) 落 `data_dataset.notes`（但会与 `L12 notes` 冲突，须定合并规则）；(c) 新增**非许可**目标列 |")
w("| **Q3** | `historical_place` / `_name` / `_location` 的 `record_status` 是否保留 `published`？ | ① 暂存唯一 1 值 = `staging`；③ V2.1 CHECK 为 4 值含 `published`，③ V0.2.2 §2.1.1 称 3 值 | (a) 统一为 3 值（删 `published`，同步改 4 处 CHECK：`CORE:338` / `CORE:479` / `CORE:483` / `CORE:484`）；(b) 统一为 4 值并更正 V0.2.2 §2.1.1 标题 |")
w("| **Q4** | `data_quality_issue.dataset_id` 对 6 行「无 `source_record_id`」如何取值？ | ① `data_quality_issues` 无 `raw_file` 列、无 `dataset_id` 列；`source_record_id` 6 行空 | (a) 按 `source_id`（4 值）落到 `data_source` 级并拒绝入库；(b) 整批 failed（同 A12）；(c) 落 `dataset_id = NULL` 并放宽 `required`（会破坏 `L174` 的 NOT NULL） |")
w("| **Q5** | `source_record` 是否新增 `inactive_reason` / `inactive_at` / `inactive_in_batch_id` / `duplicate_ordinal` 四列？ | ① 暂存 14 列中 4 列全无；③ V2.1 目标表 4 列全无；③ V0.2.2 §1 写「新列 +2」但正文已引用这 4 列 | (a) 加 4 列，§1 合计更正为 **+6**；(b) 不加，`v_place_liveness` 与判定表第 0 行改用其它表达（须重写 §2.2.4 与 §2.3.1） |")
w("| **Q6** | `historical_place.dataset_id` 加不加？ | ① 暂存无；③ `V0.2.2 §2.2.2:203` 视图依赖它；③ `V2.1 CORE:176` 规则 1 禁止它 | (a) 加列 + 修订 V2.1 §5.2.1 规则 1；(b) 不加列，视图改为 `JOIN source_record sr ON sr.source_record_id = p.created_from_source_record_id`（不改表结构，但 SQL 需重写且失去 `dataset_id` 直连能力） |")
w("| **Q7** | 未覆盖的 2,878 行 `parent_external_id` 怎么填？ | ① `pleiades_place_id` 2,643 + `whg_place_name_index` 223 + `whg_geometry` 5 + `whg_source_id` 5 + `whg_place_id` 2 | (a) 全部落哨兵 `'-'`（与 CHGIS place 一致，最简单且与 C29④ 的「常量表声明一次」兼容）；(b) WHG 的 `whg_place_name_index` 另行从 `raw_payload` 取父键（① 实测其 payload 顶层键无 `place_id`/`LocID`，不可行 ⇒ 只能取 (a)） |")
w()
w("---")
w()
w("### 2.7 本节的可直接实现判定式（供 V2.1.1 交付物扫描）")
w()
w("| # | 判定式 | FAIL 条件 | 来源层级 |")
w("|---|---|---|---|")
w("| **M1** | `FIELD_MAPPING_V2.1.1.csv` 的 `target_column` 列，正则 `^(attribution\\|citation\\|license)_` 命中行数 | `> 0` 即 FAIL（§2.2.A） | ③ §3.3 + ① 列清单 |")
w("| **M2** | `FIELD_MAPPING_V2.1.1.csv` 是否含 `target_column = grain_key` 的行 | `> 0` 即 FAIL（`grain_key` 已废弃） | ③ §2.7.2:750 + CHANGELOG:271 |")
w("| **M3** | `record_scope` 枚举声明处的值个数 | `!= 4` 或含 `connection` 即 FAIL | ① 11→4 查表 + ③ N10 |")
w("| **M4** | `issue_fingerprint` 定义处是否写 `md5` | 写成 `sha256` 或缺失即 FAIL | ③ §2.5.7 + CHANGELOG R2-03 |")
w("| **M5** | `content_hash` 定义处是否写 `sha256` | 写成 `md5` 即 FAIL | ③ §2.5.6 |")
w("| **M6** | `parent_external_id` 行的 `required` 列 | `!= Y` 或 notes 含「NULL 兜底」即 FAIL | ③ C29① + ① 覆盖率表 |")
w("| **M7** | `source_record` 是否有 `inactive_reason` / `inactive_at` / `inactive_in_batch_id` / `duplicate_ordinal` 四行的定义 | 缺失任一即 FAIL（§2.2.4 / §2.3.1 依赖） | ③ §2.3.1、§2.3.2、§2.2.4 |")
w("| **M8** | `historical_place_name` / `_location` 是否有 `rejected_by` 行，且值域为 `auto\\|manual` | 缺失或值域不符即 FAIL | ③ §2.2.1 C25/C26 |")
w("| **M9** | `external_id_type` 的 notes 是否写「11 种」并逐条列全 11 条 → 4 值 | 写「16 种」或条目数 `!= 11` 即 FAIL | ① 实测 |")
w("| **M10** | `data_quality_issue` 是否有 `first_batch_id` / `last_batch_id` / `occurrence_count` / `issue_fingerprint` 四行 | 缺失任一即 FAIL | ③ §2.5.7 |")
w()
w("---")
w()
w("### 2.8 本节结论与边界声明")
w()
w("- **本节是「预判」，不是「验收」。** 预判对象是 V2.1 的 207 条映射行在 V2.1.1 定式下的存废，"
  "判据来自 V0.2.2-r2 定式正文（③）与七张暂存 CSV 的逐行实算（①）。")
w("- **本节不对任何尚未产出的交付物下判定。** `FIELD_MAPPING_V2.1.1.csv` 尚未编制，"
  "§2.7 的 M1–M10 是**给未来扫描用的判据**，不是当前扫描结果。")
w("- **本节不宣布通过。** §2.3 的 8 条不一致（D-1 ~ D-8）与 §2.6 的 7 个待裁定项（Q1 ~ Q7）"
  "**全部处于未决状态**，需架构师在编制 V2.1.1 时逐条回应。")
w("- **行数口径**：V2.1 映射表 **208 行 = 1 表头 + 207 数据行**（① 实测，"
  "与任务书「208 行」口径一致）。本节差异行合计 **35 行**（失效 20 / 新增 10 / 连带 5）。")
w("- **可复现性**：本节全部 ① 类数字可由本目录三个脚本原样重算——"
  "`staging_field_inventory.py`（逐列统计）、`verify_v211_gaps.py`（字段存在性与值域）、"
  "`probe_parent_external_id.py`（父键覆盖率交叉表）。")
w()

text = "\n".join(L) + "\n"

# 幂等：若第二节已存在，先截断到第二节起点再重写，避免重复追加
MARKER = "## 第二节 V2.1 → V2.1.1 映射差异预判"
with io.open(OUT_MD, "r", encoding="utf-8") as fh:
    existing = fh.read()
idx = existing.find(MARKER)
if idx >= 0:
    cut = existing.rfind("---", 0, idx)
    if cut < 0:
        cut = idx
    base = existing[:cut].rstrip() + "\n"
    print("检测到已有第二节，截断至 %d 字符后重写" % len(base))
else:
    base = existing

with io.open(OUT_MD, "w", encoding="utf-8") as fh:
    fh.write(base + text)

print("已写入第二节到：%s" % OUT_MD)
print("新增字符数：%d" % len(text))
print("文件现总字节：%d" % os.path.getsize(OUT_MD))
