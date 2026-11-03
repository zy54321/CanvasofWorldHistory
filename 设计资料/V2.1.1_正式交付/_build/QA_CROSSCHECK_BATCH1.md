# QA 独立交叉检查报告 · 第一批 V2.1.1 交付物

> 检查人：software-qa-engineer-3（Edward，独立 QA；未参与本批文件编制）
> 检查对象：`CORE_DATA_MODEL_V2.1.1.md`、`_build/SHARED_BASELINE_V2.1.1.md`
> 判据：`_build/ACCEPTANCE_CRITERIA_V2.1.1.md`（60 条谓词，**逐条判定，无跳过、无合并**）
> 权威设计：`V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md`（1,127 行，下称 V0.2.2-r2）
> 基线：`CORE_DATA_MODEL_V2.md` / `V2.1/CORE_DATA_MODEL_V2.1.md` / `V2.1.1/00_PROBLEM_LIST_AND_PLAN.md`（V0.2.1）
> 事实基线：`WB-002/normalized/` 七张暂存 CSV（只读，逐行复算）
> 记录格式：判据 §8；来源层级：①原始 CSV 逐行算 ②上游脚本产物 ③上游文档结论 ④基线文档定义。**②③不单独当结论**，全部回到 ① 或 ④ 复核。
> 只读脚本：`_build/qa_scripts/qa_crosscheck_scan.py`（新建，只读；未修改任何被检文件/参照物/CSV/`normalize.py`）

---

## 0. 快照核对（第一道闸）——⚠️ 发现版本错位

哈希口径：`sha256(open(path,'rb').read())[:16]`，**未**用解码后文本。`sha256sum` 与 Python `hashlib` 双工具交叉复核。

### 0.1 开工时核对（PASS）

| 文件 | 任务书给定 | 本人实测 | 结论 |
|---|---|---|---|
| `CORE_DATA_MODEL_V2.1.1.md` | `862eb9ee9417e1e3` / 115,918 B / 1,543 行 | `862eb9ee9417e1e3` / 115,918 B / mtime `2026-11-02 22:09:36` / `wc -l=1543` | ✅ 一致 |
| `_build/SHARED_BASELINE_V2.1.1.md` | `c85f742e3d12ff5d` / 68,963 B / 966 行 | `c85f742e3d12ff5d` / 68,963 B / mtime `2026-11-02 21:50:15` / 966 行 | ✅ 一致 |

⇒ 第一道闸通过，遂继续检查。

### 0.2 审计中途发现文件被改动（**FAIL · 快照纪律事件**）

约 4 分钟后复核，`CORE_DATA_MODEL_V2.1.1.md` **已被改动**：

| 项 | 开工快照 | 现快照 |
|---|---|---|
| sha256[:16] | `862eb9ee9417e1e3` | `4dd7d04e485c76e9` |
| 字节数 | 115,918 | 116,689（+771） |
| 行数 | 1,543 | 1,557（+14） |
| mtime | 2026-11-02 22:09:36 | 2026-11-02 22:13:35 |

- `SHARED_BASELINE_V2.1.1.md` 未变（仍 `c85f742e3d12ff5d`）。
- 行号比对（「补全项声明」L970、「9.2 权威数字」L1311、「V2.1.1 到此结束」L1556）确认：**本报告全部内容判定所依据的是现快照 `4dd7d04e485c76e9`**，不是任务书指定的 `862eb9ee9417e1e3`。
- 这正是判据 §0 明令防范的「版本错位」（本轮已实际发生）。已第一时间 SendMessage 报 team-lead 请求冻结/裁定；**在收到裁定前，本报告不宣布通过**。
- 另：审计收尾时根目录又新增第 3 份交付物 `IMPORT_RULES_V2.1.1.md`（49,703 B / 763 行 / mtime `22:20` / `sha16=ba377a063edfe2cc`），**非冻结、非本批指定被检文件**，仅作漂移预警（见 §4 附注），不计入判定。

**本报告采用的固定快照（每条判定均带此二值）**：

```
S_C = 4dd7d04e485c76e9 / 116,689 B / mtime 2026-11-02 22:13:35   (CORE_DATA_MODEL_V2.1.1.md)
S_B = c85f742e3d12ff5d /  68,963 B / mtime 2026-11-02 21:50:15   (_build/SHARED_BASELINE_V2.1.1.md)
```

> 若 team-lead 裁定回退到 `862eb9ee9417e1e3`，本报告的全部 CORE 侧判定须按该快照重跑；§0.2 事件本身不改变结论——它是一条独立的 FAIL。

---

## 1. 60 条谓词逐条判定

> 每条「快照」栏的三要素（sha256[:16] / 字节数 / mtime）以 `S_C` / `S_B` 指代，取值见 §0；涉及只读 CSV 者另注 ① 实测快照（§9 基线）。
> 「未验证」= 判据所依赖的文件/产物在本批尚未产出或未冻结，**不是 PASS**。

### §1 八份交付物完整性（6 条）

```
[D1-1] 八份文件全部存在、文件名逐字一致
  快照：S_C / S_B
  实测：列目录 —— 根目录仅 CORE_DATA_MODEL_V2.1.1.md（22:13）；收尾时另有 IMPORT_RULES_V2.1.1.md（22:20）。
        缺 ER_DIAGRAM_V2.1.1.svg / FIELD_MAPPING_V2.1.1.csv / ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md /
        DATA_PROVENANCE_V2.1.1.md / V2.1_TO_V2.1.1_CHANGELOG.md / V2.1.1_QA_REPORT.md 共 6 份。
  判定：未验证（本批为分批编制的中间态，2/8 到位；不判 FAIL，因属正常分批）
  依据来源层级：④（判据 §1 交付物清单）+ 文件系统实测
[D1-2] 无第九份越界文件混入正式交付根目录
  快照：S_C / S_B
  实测：根目录 = CORE + IMPORT_RULES + _build/；_build/ 为编制辅助目录不计入；无任何第九份越界文件。
  判定：PASS
  依据来源层级：④（判据 §1）+ 文件系统实测
[D1-3] ER_DIAGRAM_V2.1.1.svg 是格式良好的 XML
  快照：S_C / S_B
  实测：文件未产出，无可解析对象。
  判定：未验证
  依据来源层级：④（判据 §1）
[D1-4] FIELD_MAPPING_V2.1.1.csv 列头逐字一致
  快照：S_C / S_B
  实测：文件未产出，无列头可比。
  判定：未验证
  依据来源层级：④（判据 §1）
[D1-5] 八份文件禁用串命中数为 0（CHANGELOG 留痕除外，须逐处标注留痕）
  快照：S_C / S_B
  实测：CORE 命中 attribution_text×8(L308,326,332,340,477,1262,1266,1517)、citation_text×4(L326,340,1266,1517)、
        licence_unconfirmed×5(L52,307,794,1322,1387)、license_url×2(L308,331)、license_evidence×2(L308,337)、
        LICENSE_GATE×0 ⇒ 合计 21；BASE 命中 attribution_text×1(L955)、citation_text×2(L230,955)、
        licence_unconfirmed×4(L491,516,886,944) ⇒ 合计 7。全部为「已删除 / 明确不做 / 禁用词清单 / 删 issue_type 值」语境，
        **无一处标注「留痕」**，且 CORE 不是 CHANGELOG。
  判定：FAIL（严格字面命中数非 0；详见 §2 F-01，含修正文本与语义豁免建议）
  依据来源层级：④（判据 §1 / V0.2.2 §3.3）+ 精确串逐行扫描实测
[D1-6] 每份文件首部声明版本号 V2.1.1 且声明以 V0.2.2-r2 为权威依据
  快照：S_C / S_B
  实测：CORE L4「**版本**：2.1.1」✓；L19「把 V0.2.2-r2 已经定下的定式…落成」✓；L970/L1173/L1544 亦带 `-r2`。
        BASE L3「不得凌驾于 V0.2.2-r2」✓（BASE 不参与八份计数）。注：CORE L7「权威来源」列表写「V0.2.2（1,127 行）」未带 `-r2` 后缀。
  判定：PASS（附注 WARN：L7 建议补 `-r2`）
  依据来源层级：④（V0.2.2-r2 文件头 L1）+ 逐行实测
```

### §2 跨文档字段与枚举一致性（12 条）

```
[D2-1] record_scope 恒 4 值；connection 命中数为 0
  快照：S_C / S_B
  实测：4 值 place/name/location/edge 在 CORE L448、L504、L626、BASE §5 L205–215 一致 ✓。
        但 `connection` 命中 CORE 24 处 / BASE 16 处，逐处核为：Pleiades 源端概念、`pleiades_connection_id`、
        「排除 connection」H2 告警、禁用说明；**无一处作为 record_scope 第 5 枚举值**。字面「命中 0」不成立。
  判定：WARN（语义意图满足；判据字面与 V0.2.2 §2.2.6a 必需的「排除 connection」告警冲突，建议改判据为「作为枚举值命中 0」并逐处留痕，沿用「改判据不改内容」）
  依据来源层级：④（V0.2.2 §2.7.2 / §2.2.6a）+ 逐行语义判读实测
[D2-2] evidence_role 恒 3 值；place_record 命中数为 0
  快照：S_C / S_B
  实测：3 值 creator/name/location 在 CORE L900、BASE §6 L229 一致 ✓。`place_record` 命中 CORE 4(L46,900,1379,1517) /
        BASE 4(L230,232,685,955)，**全部为「禁用词」声明**，无一处作为枚举值。字面「命中 0」不成立。
  判定：WARN（同 D2-1；建议改判据并逐处留痕）
  依据来源层级：④（V0.2.2 §2.6.1）+ 逐行语义判读实测
[D2-3] liveness 8 值 / record_status 3 值；rejected ⟺ liveness ∈ FAILURE_SET 表述一致
  快照：S_C / S_B
  实测：CORE §5.10.2 L986–1016（8 值优先级、真值表、FAILURE_SET 4 元素、R4a–R4f）与 BASE §7.2–7.4 L258–316 逐项一致；
        与 V0.2.2 §2.1.2/§2.1.3/§2.1.4（L82–149）核对无漂移。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.1.1–2.1.4）+ 逐格比对
[D2-4] time_bound_type 7 / derivation_kind 3 / inactive_reason 3 / issue_type 19 值域逐字一致
  快照：S_C / S_B
  实测：7 值 CORE §6.1 L1191–1201 ≡ BASE §9 L411–421 ≡ V2.1:674–684；3 值 CORE §6.3 ≡ BASE §10；
        3 值 CORE L460/L470 ≡ BASE §11.1；19 值 CORE L797–806 与 BASE L494–512 **19 行逐字相同**，
        与 V2.1:642 的 20 值删 licence_unconfirmed 反推一致。
  判定：PASS
  依据来源层级：④（V0.2.2 §0 N13 / V0.2.1 §4.2 L1766/1769/1773 / V2.1 §6.1）+ 清单逐行比对
[D2-5] 五段业务键逐字一致、无缺失段
  快照：S_C / S_B
  实测：完整串 `(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` 在 CORE 6 处
        (L38,83,97,297,469,1450)、BASE 2 处 (L27,593) 全部逐字一致；V2.1 四段键仅在 CORE L392、BASE L941 作为
        「已被 V0.2.2 §2.5.0 改为五段」的作废对照出现；未发现任何缺段落的变体。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.5.0 L525）+ 键串精确扫描
[D2-6] parent_external_id 哨兵恒为 '-'；NULL/空串作哨兵命中 0
  快照：S_C / S_B
  实测：CORE §4.2 L111–120（C29 ①–④）、L448、L450、§2 L73；BASE §1 L31–39、L48 —— 均写 `'-'`，并明令
        「不得 NULL 兜底、不得空串」。未发现以 NULL/空串为哨兵的写法。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.5.0 L527–534）+ 逐行实测
[D2-7] content_hash 主规范串逐字一致；旧 md5 版串命中 0
  快照：S_C / S_B
  实测：**本人自行重算**（未采信转报值）：完整串 `sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))`
        len=85、sha1=`9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5`；内层 len=77、sha1=`781f68645c4e2e3af4b18871f2f5b7848c5f3798`。
        与 CORE L213 / BASE L141–142 完全一致。规范串在 CORE L41,L206 与 BASE L126,L141 共 4 处逐字相同；
        旧 md5 表达式串 0 命中（BASE L147 仅以「已作废」提及指纹前缀，非完整串）。
        注：CORE L1374 有缩写 `sha256(json.dumps(...))`（差异对照表），非定式落点，附 WARN。
  判定：PASS
  依据来源层级：④（V0.2.2 §3.4 L927–933 / §2.5.6 L629）+ 独立重算实测
[D2-8] issue_fingerprint 恒 md5 六段含 place_id；存在 ALG-1 显式声明
  快照：S_C / S_B
  实测：CORE §4.5 L227–228 `md5(jsonb_build_array(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value)::text)`；
        L233 明写「**六段**，`place_id` 是**必需段**」；L240「两种摘要算法并存是【有意设计】，不可互换、不可统一（ALG-1）」。
        BASE §4.1 L174–184、§4.2 L186–197、§12 L547 同。与 V0.2.2 §2.5.7 L649–657 一致。
  判定：PASS（另见 §3 第 3 项：CORE L1501 的 U19 登记项含 sha256 字样，属保留项非实现）
  依据来源层级：④（V0.2.2 §2.5.7 / V0.2.1 §2.5.1）+ SQL 逐段核对
[D2-9] place_grain 标为 V2 既有列（CORE_DATA_MODEL_V2.md:208、V2.1:154），不得写 V2.1.1 新增
  快照：S_C / S_B
  实测：**已回到基线原文核实**：V2 `CORE_DATA_MODEL_V2.md:208` 确有 `place_grain | text | NOT NULL，CHECK IN (3 值)`；
        V2.1:136「枚举从 3 值收敛为 2 值」、V2.1:154 `NOT NULL，CHECK IN (per_record, per_parent_external_id)` ✓。
        CORE L309「**不变**（⛔ 非新增）」、L352、§5.2.2 L372–384 明写 V2 既有列并引 :208 / :136/154；
        §5.0 未把它列入「新增」行；BASE L648 同。未发现「V2.1.1 新增列」表述。
  判定：PASS
  依据来源层级：④（V2:208 / V2.1:136,154 / V0.2.2 §1 L68）+ 基线原文逐行核实
[D2-10] 新列总数口径唯一 +2；不得出现 +3 等其他计数（§7 历史留痕区除外）
  快照：S_C / S_B
  实测：CORE §5.0 L287 明写「**不写"新增 N 列"这类合计数**」；L55–59 专段澄清「+2 是 V0.2.2 相对 V0.2.1 的增量，
        不是 V2.1.1 相对 V2.1」——Owner「+2 陷阱」已正确识别并处理 ✓。
        但 CORE L384「V0.2.2-r1 曾记为 +3，**已回退为 +2**」这一留痕位于 §5.2.2，**不在 §7 历史留痕区**，且未标「留痕」。
  判定：WARN（口径处理正确；建议把 L384 的 +3 移入 §7 并标「留痕」，或就地标注豁免）
  依据来源层级：④（V0.2.2 §1 L66–68 / §7 L1114）+ 逐行实测
[D2-11] C01–C29 无缺失无重复；有效条数计数唯一
  快照：S_C / S_B
  实测：正则 `\bC\d{2}\b` 扫描：CORE 与 BASE 均覆盖 01–29 全部 29 个编号、无缺失；
        CORE 附录 A L1448–1479 与 BASE §13.1 L591–621 的「逐条落点表」每个编号恰 1 行、无重复定义。
        计数口径两文件一致：29 − 1(C02 废) − 1(C18 双编号) = **27**；可落库 SQL = **24**；断言/键级 = **3**(C27/C28/C29)。
        CORE L483 与 BASE §13.2 L636–641 均写明 24/27 是子集口径而非矛盾。
  判定：PASS
  依据来源层级：④（V0.2.2 §4-11 L956 / V0.2.1 §4.3 L1777–1804）+ 编号机器扫描
[D2-12] 三视图字段名逐字一致；inactive_at / inactive_in_batch_id 落点全文统一
  快照：S_C / S_B
  实测：① `v_place_evidence` 11 列逐列名在 CORE §5.10.1 L894–908、BASE §14.1 L679–693、V0.2.2 §2.2.2 L192–201 三者一致 ✓；
        ② **`v_place_liveness` 对外列清单冲突**：CORE L972 标「9 列」但表内仅编号 1–7，且 SQL L953–966 实际输出 **7 列**；
        BASE §14.2 L721–733 却列 **9 列**（含 `has_valid` / `reasons` 为对外列），与 CORE「CTE 中间量，不计入对外列」冲突（§2 F-04）；
        ③ **C13 列名冲突**：CORE L676/L1462 用 `source_rule_vocabulary`，BASE L605 用 `source_time_columns`（模型中不存在的列，§2 F-06）；
        ④ `inactive_at`/`inactive_in_batch_id` 在 CORE §5.4 L461–462 是 `source_record` 表列，
           却在 CORE §5.10.2 L945–946 被当作 `v_place_evidence` 的列 `e.inactive_at` 引用 —— **两处各写一套**（§2 F-03）。
  判定：FAIL
  依据来源层级：④（V0.2.2 §2.2.2 / §2.2.4 / V0.2.1 §2.3.4 L1044–1080 / V2.1:475,487）+ 视图 SQL 逐列比对
```

### §3 ER 图与数据模型一致性（9 条）

```
[D3-1] 图中实体名与 §5 表名逐字一致
  快照：S_C / S_B
  实测：ER_DIAGRAM_V2.1.1.svg 未产出；模型侧九表名齐备（§5.1–5.9）。
  判定：未验证
  依据来源层级：④（判据 §3）
[D3-2] 图中字段名与模型逐字一致、无模型外字段
  快照：S_C / S_B
  实测：ER 图未产出。
  判定：未验证
  依据来源层级：④（判据 §3）
[D3-3] 图注写 record_status <> 'rejected' 且「只聚合 name+location、排除 edge」；'published' 命中 0
  快照：S_C / S_B
  实测：ER 图未产出，无法判图注。模型侧 CORE §5.10.3 L1081–1089 与 §5.10.6 L1181 已写 `<> 'rejected' AND sr.is_active`；
        CORE 中 `'published'` 共 13 处，全部位于 C14/C15 门禁 CHECK（子表 3 值域合法值）与「V2.1 已作废」说明，非时间视图过滤。
  判定：未验证（模型侧已具备正确条件，图侧待出图）
  依据来源层级：④（V0.2.2 §2.2.6 L316–322）+ 逐行实测
[D3-4] 图中行数标注不得同图混用两个口径
  快照：S_C / S_B
  实测：ER 图未产出。
  判定：未验证
  依据来源层级：④（判据 §3）
[D3-5] source_record 唯一键标五段键；不得出现 occurrence_key
  快照：S_C / S_B
  实测：ER 图未产出。模型侧：CORE §4.1 L97、§5.4 L469 五段键 ✓；§5.0 L296 / §5.2.3 L386–396 明写 occurrence_key 已删除 ✓。
        **但 CORE §5.4 L452 仍在 source_record 列清单里保留 `occurrence_key` 一行并写「是否保留待裁定 V-13」**，
        与「已删除」自相矛盾、且 V-13 不存在（附录 B 仅 V-1…V-7）⇒ 见 §2 F-02（模型侧 FAIL）。
  判定：未验证（图侧）；模型侧缺陷另列 F-02
  依据来源层级：④（V0.2.2 §2.5.0 / C01）+ 逐行实测
[D3-6] 图中含三视图且 v_place_evidence 存在
  快照：S_C / S_B
  实测：ER 图未产出；模型侧 CORE §5.10 三视图齐备、§5.10.1 为 v_place_evidence ✓。
  判定：未验证
  依据来源层级：④（判据 §3）
[D3-7] historical_place 含 dataset_id 与 grain_key
  快照：S_C / S_B
  实测：ER 图未产出；模型侧 CORE §5.5 L527–528 两列 NOT NULL ✓、§5.0 L298–299 列为新增 ✓。
  判定：未验证
  依据来源层级：④（V0.2.1 §2.4.2 / Owner 决策 5）
[D3-8] 图中 data_quality_issue 入库 12,831 且含三伴生列
  快照：S_C / S_B
  实测：ER 图未产出；模型侧 CORE §9.2 N08 = 12,831 ✓、§5.9 L788–790 三列齐备 ✓。
  判定：未验证
  依据来源层级：④（V0.2.2 §0 N08 / V0.2.1 §2.5.5）
[D3-9] 显式声明 架构/V2.1/ER_DIAGRAM_V2.1.svg 已作废
  快照：S_C / S_B
  实测：CORE §5.10.6 L1175–1183 有独立「⛔ … 已作废」小节，含作废理由（图注 `'published'` ⇒ 0/19,039）与替代（§5.10.3 SQL）✓。
        **但 L1183 的出处标注错误**：写「V2.1 `CORE_DATA_MODEL_V2.1.md` 行 1639」，而该文件仅 856 行；
        原文实在 `V2.1.1/00_PROBLEM_LIST_AND_PLAN.md`（V0.2.1）L1639（§2 F-08）。
  判定：PASS（声明本身成立；出处错误另列 F-08，不推翻本条）
  依据来源层级：④（V0.2.1 L1639 / V0.2.2 §6 L1089）+ 全文检索核实
```

### §4 导入 / 更新 / 隔离 / 合并 / 回滚规则一致性（12 条）

```
[D4-1] 四种排列 A,B,B / B,A,B / A,A,B,B / A,B,C 逐步推演且结论自洽
  快照：S_C / S_B
  实测：IMPORT_RULES_V2.1.1.md 与 ROLLBACK_AND_MANUAL_PROTECTION_V2.1.1.md 均不在本批指定被检文件内
        （前者 22:20 才出现且未冻结）。CORE / BASE 均不含四排列推演。
  判定：未验证（非冻结文件的快速扫描见 §4 附注，不计入判定）
  依据来源层级：④（判据 §4）
[D4-2] 隔离判据为「同一 hash 子组内最小 ordinal 保留、后续相同 hash 隔离、不同 hash 均保留」；不得出现「只比较 ordinal=1 的 hash」旧规则
  快照：S_C / S_B
  实测：CORE §4.3 L189–199 **正确**：L193「同一 hash 子组内【最小 ordinal】保留」、L194「该子组内后续相同 hash ⇒ 隔离」、
        L195「不同 hash ⇒ 均保留」、L198「⛔ 禁止"只比 ordinal = 1"」✓。
        **BASE §2.1 L95–97 却把旧规则标为「正确规则」**：「ordinal > 1 且 content_hash 等于 `ordinal = 1` 的 hash 的行才隔离」，
        与同节 L99 标题「关键约束（不得只比 ordinal=1）」、L101–102 的新规则**自相矛盾**；
        该旧规则对 `A,B,B` 会漏隔离（ordinal3 的 B ≠ ordinal1 的 A）。
        交叉证据：V0.2.2-r2 §2.5.0 L562–563 原文亦为旧规则（属权威设计历史遗留），但 Owner r3 任务书 P0-03 已裁定禁用
        （22:20 出现的 IMPORT_RULES §5.1 L259–268、L309 明确「不得仅比较 ordinal=1 的 hash」并给出四排列推演）。
        ⇒ **共享定义基线仍留旧规则，而交付物已按新规则编制 ⇒ 跨文档漂移已实际发生**。
  判定：FAIL
  依据来源层级：④（V0.2.2 §2.5.0 L562–564 / §2.3.1 L398 / Owner r3 P0-03）+ 四种排列代入验算
[D4-3] raw_record_index 仅在 hash 相同时作辅助排序，不得当文件内唯一编号
  快照：S_C / S_B
  实测：CORE §4.3 L187、§5.4 L454、BASE §2 L90 均写「只能在 content_hash 完全相等时打破并列」「不保证文件内唯一
        （14 个 raw_file 中 7 个不唯一，全为 WHG）」，与 V0.2.2 §2.5.5 L619–623 一致。未发现当唯一编号使用的写法。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.5.5）+ 逐行实测
[D4-4] 判定表含第 0 行「重复检测优先」；七类操作不冲突
  快照：S_C / S_B
  实测：CORE §4.3 L201 仅引用「V0.2.2 §2.3.1 第 0 行」；完整 11 行 × 7 列判定表在 IMPORT_RULES / ROLLBACK（未在本批）。
  判定：未验证
  依据来源层级：④（V0.2.2 §2.3.1 L394–402）
[D4-5] 回滚统计集合互斥且穷尽、两组恒等式、反例至少 7 种情形
  快照：S_C / S_B
  实测：CORE 附录 B L1507 仅登记 R1/R2 结构；两组恒等式与 7 种反例在 ROLLBACK 文档（未产出）。
  判定：未验证
  依据来源层级：④（V0.2.2 §2.4.1–2.4.3）
[D4-6] is_active=false OR inactive_reason IS NOT NULL → N_noop 不得提前截走本批新产生的 duplicate_quarantine
  快照：S_C / S_B
  实测：相关五级判定顺序（V0.2.2 §2.4.1 L442–451）未在 CORE / BASE 正文中落地，仅在 BASE §15.5 L867 一句提及同一机制。
  判定：未验证
  依据来源层级：④（V0.2.2 §2.4.1）
[D4-7] 未落库的写入失败记录不得计入已插入集合
  快照：S_C / S_B
  实测：CORE §5.3 L436（failed 一行不许落库）、BASE §11.3 L531 有原则性表述；可复算的恒等式在 ROLLBACK 文档（未产出）。
  判定：未验证
  依据来源层级：④（V0.2.2 §2.4.2 L474）
[D4-8] 不得为凑恒等式新增/修改质量台账类型
  快照：S_C / S_B
  实测：CORE §5.9 L809「⛔ 禁止为凑满 20 值而新增替代类型」、L810「回滚阶段台账类型只有 rollback_conflict 与
        manual_edit_conflict」；BASE §11.2 L515、L517 同；与 V0.2.2 §2.4.3 L504、§2.8-C 一致。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.4.3 / V0.2.1 §2.8-C）
[D4-9] STOP_AUTO 规则与 duplicate_external_id 台账复用；三份相关文档表述一致
  快照：S_C / S_B
  实测：CORE §4.7 L263–277 与 BASE §15 L820–867 逐项一致（判据、整组 SKIP_UPDATE、复用既有类型、三条硬禁止/两条硬保留），
        与 V0.2.2 §2.5.2–2.5.3 L589–613 一致；但第三份文档（ROLLBACK）未产出。
  判定：未验证（已到的两份一致；三份齐备后复核）
  依据来源层级：④（V0.2.2 §2.5.2–2.5.3）+ 两份交叉比对
[D4-10] canonical 统一外层排序；每地点至多一个 canonical；无有效证据不得伪造；315 个无子行地点经 creator 追溯且不补造名称行
  快照：S_C / S_B
  实测：CORE §5.10.4 L1132–1154 文字部分满足（定序式、315 不制造名称子行、MCGD 最小 NameID、锚点 vs 当前最佳证据）✓。
        **但 §5.10.1 L869 的 SQL 在 creator 分支写死 `FALSE AS is_canonical_row`（「由 ②③ 竞争」）**，
        即 creator 行永远不可能成为 canonical；这与 L1142「315 个无子行地点：唯一有效证据是 creator 行 ⇒
        is_canonical_row=true 落在它身上」**直接矛盾**，315 个地点将无任何 canonical 行、追溯通路断裂。
        另：②分支 L883 的 `<canonical 定序 §5.10.4>` 是**不可执行占位符**；§5.10.4 的 ORDER BY 引用
        `duplicate_ordinal` / `external_id`，二者**不是 v_place_evidence 的 11 列**，需回连 source_record 才能算。
        V0.2.2 §2.2.2 L201 与 §2.8.2 L810–816 本身即含此矛盾，交付物原样复制且未加补全声明。
  判定：FAIL
  依据来源层级：④（V0.2.2 §2.8.2 / §2.2.2 / V0.2.1 §2.8）+ SQL 语义推演
[D4-11] MCGD 按最小 NameID 定 canonical；643 个地点按 parent_external_id 建点
  快照：S_C / S_B
  实测：CORE §5.5.4 L604（MCGD 取 external_id=NameID 字典序最小，643/643）、§5.10.4 L1143、§5.5.5 L613–618 白名单、
        BASE §1.1 L47、§14.1 L702；与 V0.2.2 §2.8.2 L817、§2.7.1 一致。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.8.2 / §2.7.1）+ 逐行实测
[D4-12] rejected_by（auto/manual）在 name 表与 location 表各 1 列，落点一致
  快照：S_C / S_B
  实测：CORE §5.6 L668、§5.7 L723、§5.0 L301–302、附录 A C25/C26 L1474–1475；BASE §8 L342–356、§13.1 L617–618；
        均为 `text` 可空 + CHECK IN (auto,manual)，各表 1 列。与 V0.2.2 §2.2.1 L166–185 一致。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.2.1）+ 逐表核对
```

> **§4 附注（非冻结，不计入判定）**：审计收尾时根目录出现 `IMPORT_RULES_V2.1.1.md`（`ba377a063edfe2cc` / 49,703 B / 763 行 / 22:20）。
> 只读快速扫描见 §5.1 L259–268 已采用**正确**子组规则并明写「⛔ 禁止只比 ordinal = 1」，§5.2 L270–314 给出四排列逐步推演、
> L734 记 V-9「已裁定」。⇒ 它反过来印证 BASE §2.1 L95–97 的旧规则是**已实际发生的跨文档漂移**。该文件不在本批指定快照内、未冻结，故 D4-1/D4-2 不据它改判。

### §5 真实数据字段映射覆盖率（6 条）

```
[D5-1] FIELD_MAPPING 每个 staging_column 在对应 CSV 真实存在或标 derived
  快照：S_C / S_B
  实测：FIELD_MAPPING_V2.1.1.csv 未产出。已备好逐列核对依据：七张 CSV 表头实测见 §5.6 与 `_build/qa_scripts/qa_crosscheck_scan.py` 输出。
  判定：未验证
  依据来源层级：①（七张 CSV 表头逐行读，见下 D5-6）+ ④（判据 §5）
[D5-2] 每个 target_column 在 CORE_DATA_MODEL_V2.1.1.md 真实存在
  快照：S_C / S_B
  实测：映射文件未产出；模型侧列定义已逐表读出备用。
  判定：未验证
  依据来源层级：④（判据 §5）
[D5-3] 覆盖率 = 已映射 / 应映射；遗漏项逐条列明
  快照：S_C / S_B
  实测：映射文件未产出，无法计算覆盖率。
  判定：未验证
  依据来源层级：④（判据 §5）
[D5-4] data_dataset 的 9 列许可相关映射已全部删除且无替代列
  快照：S_C / S_B
  实测：映射文件未产出。模型侧 CORE §5.2 L326–338 **逐列列出 9 列删除**（license_id/license_url/attribution_text/
        attribution_required/modification_note_required/overlay_license_id/redistributable/license_evidence/license_verified_at），
        L340 明写「不重新引入 attribution_text、citation_text 或任何替代字段」，§5.0 L308 同；V0.2.1 §4.2 L1775 核对一致。
  判定：未验证（模型侧已具备，映射侧待产出）
  依据来源层级：④（V0.2.1 §4.2 L1775 / V0.2.2 §3.3）+ 逐列实测
[D5-5] 不得为凑覆盖率凭空补行
  快照：S_C / S_B
  实测：映射文件未产出；CORE §11 L1400 有「枚举值必须是数据里出现过的」硬原则，未见凭空补行内容。
  判定：未验证
  依据来源层级：④（判据 §5）
[D5-6] 七张 CSV 实测行数与 V0.2.2-r2 §0 一致
  快照：S_C / S_B + ①七张 CSV（sha16 与判据 §9 开工前基线全部一致，文件未改动）
  实测：**逐行复算**（Python csv 行数，不含表头）：
        source_records 29,391 ✓ / historical_places 19,039 ✓ / historical_place_names 47,503 ✓ /
        historical_place_locations 18,103 ✓ / data_quality_issues 12,631 ✓ / data_datasets 7 ✓ /
        candidate_matches 53,137 ✓（登记项，不进权威表）。
        与 V0.2.2 §0 L27–44、CORE §9.1 L1303–1309、判据 D5-6 所列 5 个权威数字全部吻合。
  判定：PASS
  依据来源层级：①（七张暂存 CSV 逐行算）+ ④（V0.2.2 §0）交叉复核
```

### §6 统计口径与未验证事项（8 条）

```
[D6-1] 每个统计数字带口径词；不得出现无口径词的行数
  快照：S_C / S_B
  实测：CORE §9 L1297 有口径纪律专段，§9.1/§9.2 表格以列头「**暂存原始** / **隔离后 / 预计入库**」承载口径（表格内数字视为已带）。
        但**正文散落的无口径词行数**确有多处：CORE L53「315 个无子行地点」、L1089「17,469/19,039 有跨度」、
        L1142「315 个无子行地点」、L1180「19,039 个地点的时间跨度全部为 NULL」、L1224「合计 19,039」、
        L1388「315 个无子行地点」；BASE L225「19,039 行」、L440「1,570 + 361 + 17,108 = 19,039」、
        L448/L472「315」、L926「53,137 / 53,103」。判据 §6 明确「只写一个数即判缺陷」（K4/F18）。
  判定：FAIL（纯文档错误，见 §2 F-09 逐处修正文本；不推翻设计）
  依据来源层级：④（V0.2.2 §4 L959 / §4.1 K4 L968 / F18）+ 逐行扫描
[D6-2] 权威数字表 N01–N18 与 V0.2.2-r2 §0 逐项一致（candidate_match 除外）
  快照：S_C / S_B
  实测：CORE §9.2 L1313–1332 与 V0.2.2 §0 L25–44 逐项比对：N01–N13、N15–N18 数值与说明一致；
        N14 的「隔离后」列 CORE 写「—（待复算）」、V0.2.2 写「见 §2.2.6」，均标「待复算/未验证」，不构成数值漂移；
        列头由「入库」细化为「隔离后 / 预计入库」属口径收紧，不改数值。
  判定：PASS
  依据来源层级：④（V0.2.2 §0）+ 逐项比对
[D6-3] 不得直读暂存 historical_places.valid_from/to 判定 derivation_kind / no_evidence；相关处须有显式告警
  快照：S_C / S_B
  实测：CORE §6.3 L1241–1242（H2，明写「偏低 65（1,505 + 65 = 1,570）」）、§11.1 L1419–1425（H2 专节）、
        §6.2 L1214；BASE §10.2 L458–465、§18 L962。与 V0.2.2 §2.2.6a L362–368 一致。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.2.6a）+ 逐行实测
[D6-4] candidate_match 不得写入权威数字表；列为 U18 待拍板；给出 53,137 / 53,103 及被排除行逐条来源
  快照：S_C / S_B
  实测：CORE §9.2 N01–N18 无 candidate_match ✓；§9.4 L1357–1364、§5.8 L769 均标「登记项 U18，待 Owner 拍板」并给
        暂存 53,137 / 隔离后 53,103 ✓；BASE §16.2 L917–926 同。
        **但「被排除行的逐条来源」只给汇总「34 行 / 33 个键」+ 指向 data-auditor 审计报告，未逐条列出 34 行**。
  判定：WARN（其余满足；建议补逐条清单或显式写明「逐条来源见 DATA_AUDIT_V0.2.2.md 附录」并给可定位键）
  依据来源层级：④（V0.2.2 §5.3 L1039 / §0）+ 逐行实测
[D6-5] 口径 A 8,682；8,218 明确定义为口径 B；二者不得混用
  快照：S_C / S_B
  实测：CORE §9.2 N12 L1326「**8,682（口径 A）**…**口径 B = 8,218**；差 464 = place 74 + edge 390。**钉死口径 A**」；
        BASE §16 N12 L890、R23 L904 同。与 V0.2.2 §0 L38 一致。
  判定：PASS
  依据来源层级：④（V0.2.2 §0 N12 / §5.1 R23）+ 逐行实测
[D6-6] V0.2.2 的 12 项 WARN 与 13 项未验证逐条保留、单列施工验证清单节；不得有任何一项写成 PASS/「已解决」
  快照：S_C / S_B
  实测：CORE 附录 B（L1483–1552）单列「施工验证清单」，含 B.1（U3/U4/U5/U12/U13/U14/U15/U16/U18/U19 共 10 项）、
        B.2（16 行断言状态）、**B.3 12 项 WARN 逐条保留**、B.4（V-1…V-7）；所有条目状态均为「未验证 / 未解决」，
        无一项写成 PASS ✓；L1552 明写「每一项均为未验证/未解决，本文件不宣布通过」。
        **但 L1486 引用 `V0.2.2_QA_VERIFICATION.md` 行 704 的「PASS 35 / FAIL 1 / WARN 12 / 未验证 13 —— 存在 FAIL」**：
        该计数是**阶段二中间态**；终检已在同文件 L794–797 更新为「PASS 37 / FAIL 0 / WARN 12 / 未验证 13」且 X1/X2 关闭
        （另见 INDEPENDENT_REVIEW_V0.2.2.md L316–325）。引用旧计数易被读成「权威设计仍有 1 项未关闭 FAIL」。
  判定：WARN（保留纪律满足；建议补注终检计数，见 §2 W-05）
  依据来源层级：④（V0.2.2 §5.3 / V0.2.2_QA_VERIFICATION.md L704 与 L794–797）+ 逐项比对
[D6-7] 施工验证清单至少含 U3/U4、U5、U12、U13、U14、U15、U16、U18、is_canonical_row 与暂存 canonical_name 逐行相等
  快照：S_C / S_B
  实测：CORE B.1 L1492–1501 含 U3/U4/U5/U12/U13/U14/U15/U16/U18（+U19）；B.4 V-2 L1545 含
        「`is_canonical_row` 与暂存 `canonical_name` 是否逐行相等」✓。
  判定：PASS
  依据来源层级：④（V0.2.2 §5.3）+ 清单逐项比对
[D6-8] 两条施工级硬提醒显式出现（normalize.py:306 回归 content_hash；derivation_kind/no_evidence 不得直读暂存时间列）
  快照：S_C / S_B
  实测：CORE §11.1 L1404–1425 设「两条施工级硬提醒」专节，H1（L1406–1417）、H2（L1419–1425）齐备；
        H1 另见 §4.4 L220、H2 另见 §6.3 L1241；BASE §3.1 L132、§10.2 L461 亦有对应表述。
  判定：PASS
  依据来源层级：④（V0.2.2 §2.5.6 / §2.2.6a）+ 逐行实测
```

### §7 工程边界（7 条，合规非质量）

```
[E1] 架构/CORE_DATA_MODEL_V2.md 未改动
  快照：S_C / S_B + ①实测 128,784 B / sha16=91b459a8070364df / mtime 12:27:32
  实测：与判据 §9 开工前基线逐项一致。
  判定：PASS
  依据来源层级：④（判据 §9 基线）+ ①原始字节重算
[E2] 架构/V2.1/ 八份（实为 10 份）文件全部未改动
  快照：S_C / S_B + ①实测
  实测：V2.1 下 10 份文件（CORE / ER_DIAGRAM.svg / FIELD_MAPPING.csv / FIELD_MAPPING.md / IMPORT_RULES.md /
        LICENSE_GATE.md / ROLLBACK_AND_MANUAL_PROTECTION.md / V2.1_QA_REPORT.md / V2_TO_V2.1_CHANGELOG.md 等）
        字节数与 sha16 与判据 §9 基线全部一致，无 DIFF。
  判定：PASS
  依据来源层级：④（判据 §9 基线）+ ①原始字节重算
[E3] 架构/V2.1.1/V0.2.2/ 全部文件未改动
  快照：S_C / S_B + ①实测
  实测：§9 基线记录的 2 份（`00_PROBLEM_LIST_AND_PLAN_V0.2.2.md` 105,526 / `0356ff721a7fb4f1`；
        `V0.2.1_TO_V0.2.2_CHANGELOG.md` 69,320 / `881087457b59d38a`）逐项一致 ✓。
        其余 4 份 md（DATA_AUDIT / INDEPENDENT_REVIEW / QA_VERIFICATION 等）**无开工前哈希快照**，
        仅 mtime 全部 ≤ 20:32（早于开工 21:2x），无改动证据但不能证「未改动」。
  判定：WARN（基线记录缺口，见 §2 W-06；建议 team-lead 补记 4 份快照）
  依据来源层级：④（判据 §9 基线）+ ①原始字节重算（仅已记录者）
[E4] 架构/V2.1.1/00_PROBLEM_LIST_AND_PLAN.md（V0.2.1）未改动，mtime 仍 17:43:53
  快照：S_C / S_B + ①实测
  实测：190,222 B / sha16=0a9c56fbfc002769 / mtime **2026-11-02 17:43:53.503815100** —— 三项全一致。
  判定：PASS
  依据来源层级：④（判据 §9 基线）+ ①原始字节重算 + stat mtime
[E5] 七张暂存 CSV 未改动
  快照：S_C / S_B + ①实测
  实测：七张 CSV 字节数与 sha16 与判据 §9 基线全部一致（见 D5-6）；并逐行读出表头，无改写痕迹。
  判定：PASS
  依据来源层级：①（七张 CSV 原始字节重算 + 逐行表头读取）
[E6] normalize.py 未改动
  快照：S_C / S_B + ①实测
  实测：`code/p0/wb-002-normalize/normalize.py` = 102,275 B / sha16=`4a0a6fed7f656de5`，与 §9 基线一致。
  判定：PASS
  依据来源层级：①（原始字节重算）+ ④（判据 §9 基线）
[E7] 未产生任何 DDL / Migration / 建库 / 导入 / 产品代码修改 / Git 操作
  快照：S_C / S_B
  实测：本人全程只读；仅新增只读脚本 `_build/qa_scripts/qa_crosscheck_scan.py` 与本报告；
        未执行任何 DDL/Migration/Docker/数据导入/产品代码修改/Git 命令；目录内无新增 .sql/.py 产品代码。
  判定：PASS（我方行为断言；全局复核由 team-lead 收尾）
  依据来源层级：④（判据 §7）+ 操作日志自检
```

---

## 2. FAIL / WARN 清单（逐条含行号与修正文本）

### FAIL（判据内 5 条 + 补充缺陷 9 条 + 快照事件 1 条）

| # | 对应判据 / Owner 重点 | 文件·行号 | 问题 | 修正文本 / 处置 |
|---|---|---|---|---|
| **F-01** | D1-5 / 单独核第 4 项 | CORE L308,326,331–340,477,1262,1266,1517；BASE L230,491,516,886,944,955 | 6 个禁用串在 CORE 共 **21** 处、BASE **7** 处命中，全部为「已删除/明确不做/禁用词/删枚举值」语境，但**均非 CHANGELOG 且未标「留痕」**。按 D1-5「命中数为 0」字面不成立。 | 二选一（请 Owner 裁定）：**(a)** 按「改判据不改内容」把 D1-5 的豁免扩为「凡说明『已删除/明确不做/禁用词清单/删枚举值』而引用旧名者，须逐处标注【留痕】」，并在上述 28 处逐处加【留痕】；**(b)** 在 CORE 中把 9 列删除清单改为「9 列许可相关列（列名见 V0.2.1 §4.2 L1775）」等不复现旧名的写法。**(a) 更可取**——§5.0/§5.2 逐列列明已删除列是 V0.2.2 要求的内容，删掉会制造追溯断点。 |
| **F-02** | D3-5 / 重点 1、2 | CORE **L452** vs L296、L386–396、L1546 | §5.4 `source_record` 列清单仍列 `occurrence_key`「V2.1 列，不再是业务键段，见 §5.2.3（**是否保留待裁定 V-13**）」，而 §5.0 L296 与 §5.2.3 L386 明写「**删除**」；附录 B 只有 V-1…V-7，**无 V-13**；B.4 V-3 L1546 已裁定「`occurrence_key_rule` 保留」且对象不同。⇒ 列既删又存、引用不存在的待验编号。 | 删除 L452 整行；若需留对照，改写为：`\| ~~occurrence_key~~ \| — \| **已删除**（V2.1 列） \| 被 parent_external_id + duplicate_ordinal 取代，见 §5.2.3；V0.2.2 全篇零命中 \|`。同时把「V-13」改为「V-3」或删除该括注。 |
| **F-03** | D2-12 / 重点 6 | CORE §5.10.2 **L945–946**（`e.inactive_at` / `e.inactive_in_batch_id`）；对照 §5.10.1 L894–908、V0.2.1 §2.3.4 L1062–1063 | `v_place_liveness` 的 `ev` CTE 引用了 **`v_place_evidence` 并不存在的两列**（该视图固定 11 列，无 `inactive_at`/`inactive_in_batch_id`）⇒ **视图 SQL 无法编译**。根因在 V0.2.2-r2 §2.2.4 L246–247（r2 把 CTE 的 `JOIN source_record sr` 去掉、把 `sr.` 改成 `e.`，却未补列）；交付物原样复制且未标注。 | 在 `ev` CTE 补回连接并改用源表列：`FROM v_place_evidence e JOIN source_record sr ON sr.source_record_id = e.source_record_id`，`ORDER BY sr.inactive_at DESC NULLS LAST, sr.inactive_in_batch_id DESC NULLS LAST, …`（与 V0.2.1 §2.3.4 L1055–1061 一致）；**或**在 `v_place_evidence` 增两列并同步把「11 列」改为 13 列（不推荐，破坏定式）。因根因在权威设计，须 team-lead/Owner 裁定后由 CHANGELOG 留痕。 |
| **F-04** | D2-12 / 重点 6 | CORE **L972**（「对外列清单（补全，**9 列**）」）、L953–966（SQL 实为 **7 列**）、L1162（「**9 列**（对外）」）；BASE §14.2 **L721–733**（列 9 列，含 `has_valid`/`reasons`） | ① CORE 标 9 列，但表格只编号 1–7、SQL `SELECT` 只输出 7 列（`place_id, dataset_id, grain_key, record_status, manual_rejected_rows, distinct_inactive_reasons, liveness`）；② BASE 把 `has_valid`/`reasons` 列为对外列，CORE L983 明写它们是「CTE 中间量，不计入对外列」⇒ **两份被检文件对同一视图的对外列清单互斥**。 | 请裁定一种口径后两文件同步：**方案 A**（推荐，SQL 不动）：CORE L972 改「**对外列清单（补全，7 列）**」、L1162 改「**7 列**（对外）」、BASE §14.2 把第 5/8 行改为「— `has_valid` / `reasons`：CTE 中间量，不对外」并删「9 列」；**方案 B**：在 CORE L953–966 的 SELECT 补 `coalesce(ev.has_valid,false) AS has_valid` 与 `ev.reasons AS reasons`，使 SQL 真为 9 列，并同步 BASE 的说明与 §5.10.5 的「对外新增 2」。 |
| **F-05** | D2-12 / 重点 6 | CORE §5.10.3 **L1064**（`count(*) AS valid_child_rows`）、**L1075**（`AND count(*) = 0`）、**L1077**（`LEFT JOIN eff e`） | `LEFT JOIN` 无匹配时仍产生 1 行全 NULL，`count(*)` = **1** 而非 0 ⇒ `valid_child_rows` 对「无有效子行」的地点恒为 1；`all_children_rejected`（定义 `child_rows_total > 0 AND valid_child_rows = 0`）**永不可能为真**，T5 豁免 ② 失效。V2.1 §5.5.4 L417–418 原用 `COUNT(c.*) FILTER(...)`、V0.2.1 §2.6.1 L1345–1346 用 `count(*) FILTER(...)`，**本版新引入的裸 `count(*)` 是回归**。 | L1064 改 `count(e.place_id) AS valid_child_rows`；L1075 改 `AND count(e.place_id) = 0`；其余 `count(*) FILTER (...)` 保持（FILTER 已排除 NULL 行，安全）。同步复核 T4/T5 干跑值。 |
| **F-06** | D2-12 / 重点 1、3 | BASE **L605** `C13`；对照 CORE L676、L663、L1462、V2.1:475/487 | BASE 的 C13 写成 `CHECK (source_time_columns='' OR (…))`，而 **`source_time_columns` 在 CORE 模型中零命中**（CORE 与 V2.1 用的是 `source_rule_vocabulary`）⇒ 约束指向不存在的列，且两份文件 C13 文本不一致。 | 若以 CORE 为准：BASE L605 改为 `CHECK (source_rule_vocabulary = '' OR (source_beg_rule IS NULL AND source_end_rule IS NULL))`。若以 V0.2.1 §2.7.1 L1449–1451 为准（location 改名 `source_time_columns`、name 表新增同名列），则须**同时**改 CORE §5.6/§5.7 与 §5.0，并裁定 V0.2.1 该改名是否仍在效力内（见 W-07）。**两处不得各写一套**。 |
| **F-07** | 单独核第 2 项（+2 陷阱）/ 重点 1 | CORE §5.0 **L289–310** vs §5.3 **L426** | §5.0 自称「八份交付物编制列定义的**唯一依据**」「逐列标注 增/删/改名/约束变化」，但 §5.3 出现 `import_batch.blocked_count`（V2.1 §5.3 无此列，V0.2.1 G3-04 L336 明确 `import_batch +1 列 blocked_count integer NOT NULL DEFAULT 0`），**§5.0 未列该新增列**。三轮增量未覆盖全。 | §5.0 增一行：`\| import_batch \| blocked_count \| **新增** \| 无 \| integer NOT NULL DEFAULT 0；记录级跳过（locked / manual_edited_fields / last_batch_id 不符） \| V0.2.1 G3-04（行 336）；V0.2.2 §2.4.3（行 509） \|`，并把 §5.3 L426 的 `blocked_count` 类型/默认改为与之一致（现为 `integer`，无 NOT NULL DEFAULT）。 |
| **F-08** | 重点 7（引用行号/章节号） | CORE **L347**、**L1183** | ① L347「7 个实测值见 **§10.3**」——全文无 §10.3（§10 是「与 V2.1/V2 差异一览」，无子节）；7 个值实在 **§9.3 L1345**。② L1183「V2.1 `CORE_DATA_MODEL_V2.1.md` **行 1639** 记『保留 9 表 + 2 视图的布局骨架与配色』」——该文件仅 **856 行**；原文实在 `V2.1.1/00_PROBLEMLIST_AND_PLAN.md`（V0.2.1）**L1639**（已全文检索确认）。 | L347：`见 §10.3` → `见 §9.3`；L1183：`（V2.1 \`CORE_DATA_MODEL_V2.1.md\` 行 1639 记…）` → `（V0.2.1 \`V2.1.1/00_PROBLEM_LIST_AND_PLAN.md\` 行 1639 记…）`。 |
| **F-09** | D6-1 | CORE L53, L1089, L1142, L1180, L1224, L1388；BASE L225, L440, L448, L472, L926 | 正文出现无口径词的行数（K4/F18：只写一个数即判缺陷）。 | 逐处补口径，例：L53「315 个（**入库**口径；暂存/入库同为 315）无子行地点」；L1089「改为 `<> 'rejected'` 后（**暂存态干跑**，加 `sr.is_active` 后待复算）**17,469/19,039** 有跨度」；L1142/L1388「**315 个（入库口径）**无子行地点」；L1180「**19,039 个（入库口径）**地点」；L1224「合计 **19,039（暂存态干跑）**」；BASE L440「1,570 + 361 + 17,108 = 19,039（**暂存态干跑**）」；BASE L926「**暂存原始 53,137 / 隔离后 53,103**」。表格内数字因列头已带口径，视为合格。 |
| **F-10** | D4-2 / 重点 4 | BASE **§2.1 L95–97**（对照 L99–102、CORE §4.3 L189–199、IMPORT_RULES §5.1、Owner r3 P0-03） | 把**旧规则**标为「正确规则」：「`ordinal > 1 且 content_hash 等于 ordinal = 1 的 hash 的行才隔离`」，与同节 L99 标题「不得只比 ordinal = 1」及 L101–102 新规则自相矛盾；对 `A,B,B` 会漏隔离第 3 行。共享定义基线留旧规则，而交付物已按新规则编制 ⇒ **漂移已发生**。 | 删除 L95–97 的「正确规则」代码块，替换为：`正确规则：组内按 (content_hash ASC, raw_record_index ASC) 定序后，同一 hash 子组内最小 ordinal 保留、该子组内后续相同 hash 的行隔离、不同 hash 的行均保留；⛔ 只比较 ordinal=1 的 hash 是 V0.2.2 §2.5.0 L563 的历史写法，已被 Owner r3 / P0-03 裁定禁用（本处仅作【留痕】）。` |
| **F-11** | D4-10 / 重点 6 | CORE **L869** vs **L1142**；L883；L1136–1139 | `v_place_evidence` creator 分支写死 `FALSE AS is_canonical_row`，却要求 315 个无子行地点的 canonical 落在 creator 行 ⇒ 直接矛盾；`<canonical 定序 §5.10.4>` 为不可执行占位符，与 §0 L19「三视图**完整 SQL**」不符；定序 ORDER BY 引用视图不存在的 `duplicate_ordinal`/`external_id`。 | 三选一并全文同步：① 把 creator 分支改为可由外层层排序计算（用统一窗口函数 `row_number() OVER (PARTITION BY place_id ORDER BY …)` 包住 UNION ALL，并回连 `source_record` 取 `duplicate_ordinal`/`external_id`）；② 若坚持 creator 恒 FALSE，则删除 §5.10.4 L1142「is_canonical_row=true 落在 creator 行」的表述并改写 315 的追溯通路；③ 至少在 §5.10.1 标注「② 分支 `<canonical 定序>` 为待补全占位符，非可执行 SQL」，撤下 §0 L19 的「完整 SQL」措辞。**必须同时核 V0.2.2 §2.2.2 L201 与 §2.8.2 L816 的同类矛盾并留痕**。 |
| **F-12** | 重点 1（NULL/约束自洽） | CORE **L778**、**L835**、**L819–820**；对照 V0.2.1 **L1233 / L1629 / L1798–1799** | `data_quality_issue.dataset_id` 被定为 **NOT NULL**，但 C11 `CHECK (dataset_id IS NOT NULL OR place_id IS NOT NULL)`、C12 `CHECK (dataset_id IS NOT NULL OR source_record_id IS NULL)` 在 NOT NULL 下**恒为 TRUE（永不可能触发）**；V0.2.1 §2.5.1 L1233 明确设计 `dataset_id` **可空** + `CHECK (place_id IS NOT NULL)` 以容纳「人工创建、无 dataset_id、无 source_record_id」的地点台账，V0.2.2-r2 全文未覆盖该点（按效力顺序 V0.2.1 为准）。CORE §5.9.1 D-6「6 行 dataset_id 无来源」正是此 NOT NULL 造成的。 | L778 改为 `\| dataset_id \| text \| **FK** → data_dataset，**可空** \| 从 source_record.dataset_id 取；数据集级问题直接填；地点级问题可空，由 C11/C12 兜底 \|`，L835 改为「本表 `dataset_id` **可空**（C11/C12 保证可归因）…」；若有意推翻 V0.2.1，须在 §5.0 列一行「约束变化」并给 Owner 裁定依据，同时重估 D-6/V-6。 |
| **F-13** | 快照纪律（预判据，不计入 60 条） | 见 §0.2 | 指定快照 `862eb9ee9417e1e3` 在审计中途被 `4dd7d04e485c76e9` 取代；收尾时又出现未冻结的第 3 份交付物。 | 请 team-lead 冻结文件并确认唯一被检快照（A 回退重跑 / B 认可以现版为准并单列偏离 / C 其他）。**本报告的 CORE 侧判定全部按 `4dd7d04e485c76e9` 作出**，若裁定 A 须整体重跑。 |

### WARN（6 条判据内 + 6 条补充）

| # | 对应判据 | 位置 | 内容 | 建议 |
|---|---|---|---|---|
| **W-01** | D2-1 | CORE 24 处 / BASE 16 处 `connection` | 语义上均为源端概念、排除告警、禁用说明，非第 5 枚举值；但字面「命中 0」不成立，且 V0.2.2 §2.2.6a 的 H2 告警**必须**写「排除 connection」 | 按「改判据不改内容」把 D2-1 收紧为「作为 record_scope 枚举值命中 0」，并给这些必要引用逐处标【留痕】 |
| **W-02** | D2-2 | CORE 4 处 / BASE 4 处 `place_record` | 全部为「禁用词」声明，非枚举值；字面「命中 0」不成立 | 同 W-01 |
| **W-03** | D2-10 | CORE L384 | 「V0.2.2-r1 曾记为 +3，已回退为 +2」的留痕位于 §5.2.2，不在 §7 历史留痕区，且未标「留痕」 | 移入 §7 或就地标【留痕】并注明豁免 |
| **W-04** | D6-4 | CORE §9.4 L1364 / §5.8 L769 | U18 的「被排除行逐条来源」仅给 34 行 / 33 键汇总 + 指向审计报告 | 补逐条清单，或写明「逐条来源见 DATA_AUDIT_V0.2.2.md 附表 X」并给出可定位键 |
| **W-05** | D6-6 | CORE 附录 B **L1486** | 引用 `V0.2.2_QA_VERIFICATION.md` L704 的**阶段二中间计数**「PASS 35 / FAIL 1」，未同步终检 L794–797「PASS 37 / FAIL 0」 | 追加一句：「终检（同文件 §16.5 L794–797）已更新为 PASS 37 / FAIL 0 / WARN 12 / 未验证 13，X1/X2 已关闭；本附录保留的是需施工关闭的 12 WARN + 13 未验证。」 |
| **W-06** | E3 | `V2.1.1/V0.2.2/` 下 4 份 md | 无开工前哈希快照，仅 mtime ≤20:32 早于开工；不能证「未改动」 | team-lead 补记 4 份基线快照后收尾复核 |
| **W-07** | 单独核第 2 项 / 重点 1 | CORE §5.6 L663、§5.7（无该列）、附录 A L1462「改名后」；V0.2.1 §2.7.1 **L1449–1451**、§5.6/§5.7 **L1626–1627** | V0.2.1（V0.2.2 未覆盖处为权威）要求：location 列 `source_rule_vocabulary`→**改名** `source_time_columns`、name 表**新增**同名列、`import_batch +1 列 blocked_count`；CORE 保留旧名且 name 表无该列，§5.0 未列这两项。但 `DATA_AUDIT_V0.2.2.md:428`（③上游文档结论）仍列 `source_rule_vocabulary`，存在**效力冲突**。 | 请 Owner/team-lead 裁定 V0.2.1 §2.7.1 是否仍在效力内；若在，须同步 CORE §5.6/§5.7/§5.0 与 BASE §13.1（一并解决 F-06/F-07）。**③不得直接当结论**，本条按 ④（V0.2.1 基线原文）登记 |
| **W-08** | 单独核第 3 项 | CORE **L1501**（U19） | U19「`issue_fingerprint` 是否同步改为 sha256」含 sha256 字样；但同格明写「本版按 ALG-1 保持 md5」，且该登记项是 D6-6 要求逐条保留的 13 项未验证之一 ⇒ **非算法实现**，纯关键词扫描会误报 | 保留该行；在 ALG-1 旁加「U19 仅登记，实现恒 md5」以免后人误改 |
| **W-09** | 重点 6 | BASE **§14.2 L719** | 只写「注：… `...` 未逐列枚举，下表 = …」，**未标注「补全项、非新设计」**（CORE L970 已标 ✓） | 补：「⚠️ 本表为**补全项、非新设计**，依据 V0.2.2 §2.1.2/§2.2.3/§2.2.5 与 V0.2.1 §2.3.4，待 QA 复算（B-4-1 / V-1）」 |
| **W-10** | 重点 1、2 | CORE **L71 / L82** vs **L347**；V2.1 L51/L61、V2 L113/L123 | 「主键**全部** `bigint identity`」与 `data_dataset.dataset_id`（`text` 自然键 **PK**）自相矛盾。该矛盾继承自 V2/V2.1 基线，非本版新引入，但本版未加例外说明 | §2/§3 补一句：「例外：`data_dataset.dataset_id` 为 V2 既有的 `text` 自然主键（§5.2），其余表为 `bigint identity`」 |
| **W-11** | 重点 7 | CORE **L584**、**L1311**；BASE L873 | L584 引「V2.1 §5.7（行 535）」作为子表 3 值依据，但 V2.1 L535 只是 `record_status / locked / …` 合并行、**未给值域**（真正值域在 V2.1 L479）；CORE §9.2 L1311「V0.2.2 §0 行 25–45」而表实为 L25–44。属轻微引用不准 | L584 改引「V2.1 §5.6 L479 / 本文件 §5.7 L722」；L1311 改「行 25–44」 |
| **W-12** | 重点 1 / D5-4 | CORE §5.9.1 **L831–846** | D-6「6 行空 `source_record_id` 导致 `dataset_id` 无来源」标为未解决并列 V-6，但未指出**根因是 L778 的 NOT NULL**（见 F-12）；若按 V0.2.1 改为可空，该缺口可自然消解 | 在 V-6 中补「与 F-12 的 dataset_id 可空性裁定联动」，避免两处各写一套 |

---

## 3. Owner 七项重点 · 各一句结论

1. **数据表、字段及类型**：九张表的列名/类型/NULL/默认/约束大多自洽且与 V0.2.2-r2 一致，但存在 3 处硬伤——`source_record.occurrence_key` 既删又存（F-02）、`data_quality_issue.dataset_id NOT NULL` 使 C11/C12 恒真且与 V0.2.1 可空设计冲突（F-12）、C13 列名在两份文件间指向不同对象（F-06）；另有 `source_time_columns` 改名/`import_batch.blocked_count` 是否属三轮增量待裁定（F-07 / W-07）。⇒ **未通过**。
2. **主键、外键及业务键**：五段键 `(dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)` 在 CORE 6 处 / BASE 2 处逐字一致、无缺段，V2.1 四段键仅在作废对照中出现；外键所指向的九张表与对应列均真实存在；仅「全部 bigint identity」与 `data_dataset.dataset_id` 自然文本主键的自相矛盾为继承自 V2/V2.1 的 WARN（W-10）。⇒ **基本通过（1 项继承 WARN）**。
3. **枚举值和 CHECK 约束**：`record_scope` 4 / `evidence_role` 3 / `liveness` 8 / 地点 `record_status` 3 与子表 3（**值域不同，CORE §5.5.2 明确分列，未合并**）/ `time_bound_type` 7 / `derivation_kind` 3 / `inactive_reason` 3 / `issue_type` 19 全部逐字一致，C01–C29 无缺失无重复、27/24/3 唯一计数口径两文件一致；但 C13 列名冲突（F-06）与 `connection`/`place_record` 字面命中非 0（W-01/W-02，属判据缺陷）需处理。⇒ **枚举本身通过，判据字面与 1 处约束文本未通过**。
4. **导入、更新、重复隔离规则**：CORE §4.3 的隔离判据完全正确（子组内最小 ordinal 保留 / 后续同 hash 隔离 / 不同 hash 均保留，并明令禁止「只比 ordinal=1」），但 **SHARED_BASELINE §2.1 L95–97 仍把被 Owner r3 裁定禁用的旧规则标为「正确规则」**（F-10），且 22:20 出现的 IMPORT_RULES 已按新规则编制 ⇒ 跨文档漂移已实际发生。⇒ **未通过**。
5. **地点合并及回滚规则**：CORE/BASE 的 STOP_AUTO、duplicate_external_id 台账复用、C25/C26 四场景 A–D、判定表第 0 行引用、R1/R2 登记均与 V0.2.2-r2 §2.3/§2.4/§2.5 一致且两文件互相一致；但两套恒等式、7 种反例、判定表全表在 ROLLBACK/IMPORT_RULES（本批未产出/未冻结）⇒ **本批可判部分通过，整体未验证**。
6. **三个核心视图的定义和关联**：`v_place_evidence` 11 列逐列名与 V0.2.2 §2.2.2 / BASE §14.1 一致 ✓；`v_place_time_span` 过滤确为 `record_status <> 'rejected' AND sr.is_active`、SQL 中无 `'published'` ✓ 且已标「补全项、非新设计」；但 `v_place_liveness` 的补全**不合理**——标 9 列而 SQL 实为 7 列且与 BASE 的对外列清单互斥（F-04）、引用视图不存在的两列导致无法编译（F-03）、`is_canonical_row` creator 分支与 315 追溯自相矛盾（F-11），`v_place_time_span` 的 `count(*)`+LEFT JOIN 使 `all_children_rejected` 恒假（F-05），`v_place_evidence` 含不可执行占位符却自称「完整 SQL」。⇒ **未通过（本批最大问题集中区）**。
7. **与 V0.2.2-r2 权威设计的一致性**：抽查 20+ 处章节号/行号（§2.5.0 L521–572 / C29 L527–534 / 7 组 L549–557 / §2.5.6 L625–643 / §3.4 L929–934 / §4-11 L956 / §4.1 K5 L969 / §6-3 L1052 / §2.2.4 L254–265 / V0.2.1 L1769/1775/1785/1449–1451 / V2:208 / V2.1:136,154,235,263,265,279,413–427,479,642,674–684）**全部对得上**；仅 CORE L347「§10.3」与 L1183「V2.1 CORE 行 1639」两处出处错误（F-08）、L584/L1311 两处轻微不准（W-11）。⇒ **主体通过，2 处 FAIL 级引用错误**。

## 4. 另外 4 件单独核事项

| 项 | 判定 | 实测依据 |
|---|---|---|
| **`place_grain` 必须标 V2 既有列** | **PASS** | CORE §5.0 L309「**不变**（⛔ 非新增）… V2 既有列（`CORE_DATA_MODEL_V2.md:208`），V2.1 收敛 2 值（`:136/154`）」、§5.2.2 L372–384、L352 `text NOT NULL CHECK IN (per_record, per_parent_external_id)`；BASE L648 同。**已回基线原文核实**：V2:208 确有该列（3 值）、V2.1:136 收敛 2 值、V2.1:154 NOT NULL + CHECK 2 值。全文无「V2.1.1 新增列」表述；§5.0 未列入新增行。来源层级 ④ |
| **「新列 +2」陷阱 / §5.0 列变更清单覆盖三轮增量** | **FAIL（1 项确定遗漏）+ WARN（1 项效力待裁定）** | §1 L55–59 **已正确识破陷阱**（明写 +2 是 V0.2.2 相对 V0.2.1、不是 V2.1.1 相对 V2.1，且 §5.0「不给合计数」）✓；已知清单逐列核对全部覆盖：`source_record` 增 4 列（L292–295）/ 删 `occurrence_key`（L296）/ UNIQUE 约束变化（L297）；`historical_place` 增 `dataset_id`/`grain_key`（L298–299）；name/location 各增 `rejected_by`（L301–302）；`data_quality_issue` 增 `first/last_batch_id`/`occurrence_count`（L304–306）+ `issue_fingerprint`（L303）；`data_dataset` 删 9 列（L308）。**遗漏**：`import_batch.blocked_count`（§5.3 L426 有列、V2.1 无、V0.2.1 G3-04 L336 明确 +1 列）未进 §5.0 ⇒ F-07。**待裁定**：V0.2.1 §2.7.1 的 `source_time_columns` 改名与 name 表增列（W-07）。来源层级 ④ |
| **`issue_fingerprint` 必须 md5 且 `place_id` 必需段；出现 sha256 即 FAIL** | **PASS（实现）+ WARN（登记项）** | CORE §4.5 L227–228 为 `md5(jsonb_build_array(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value)::text)`，L233 明写「六段，`place_id` 是**必需段**」；BASE §4.1 L174–179 / §12 L547 同；`UNIQUE(issue_fingerprint)`（C10）与 ALG-1 声明（CORE L240 / BASE L195）齐备。**实现中无 sha256**。唯一含 sha256 字样的是 CORE L1501 的 U19 登记项「是否同步改为 sha256」，同格明写「本版按 ALG-1 保持 md5」，且属 D6-6 必须逐条保留的未验证项 ⇒ 不是算法变更（W-08），纯关键词扫描会误报。来源层级 ④（V0.2.2 §2.5.7 / V0.2.1 §2.5.1） |
| **全文不得有任何许可/授权管理内容** | **FAIL（字面）/ 语义上无许可功能** | `LICENSE_GATE` 两文件均 0 ✓；但 `attribution_text` CORE 8 / BASE 1、`citation_text` CORE 4 / BASE 2、`licence_unconfirmed` CORE 5 / BASE 4、`license_url` CORE 2、`license_evidence` CORE 2，合计 CORE 21 / BASE 7。逐处核为「已删除列清单 / 明确不做 / 禁用词清单 / 删 issue_type 值」语境，**无任何许可列、许可门禁或授权判断**；但这些引用**均不在 CHANGELOG、且未标「留痕」**，按「命中数为 0（CHANGELOG 留痕除外）」字面不成立 ⇒ F-01，请裁定豁免范围（推荐 a：扩判据豁免 + 逐处标【留痕】）。来源层级 ④ + 精确串扫描 |

---

## 5. 判定计数与结论

### 5.1 60 条谓词计数（机器核对：27+5+6+22 = 60，无跳过、无合并）

| 判定 | 条数 | ID |
|---|---:|---|
| **PASS** | **27** | D1-2, D1-6, D2-3, D2-4, D2-5, D2-6, D2-7, D2-8, D2-9, D2-11, D3-9, D4-3, D4-8, D4-11, D4-12, D5-6, D6-2, D6-3, D6-5, D6-7, D6-8, E1, E2, E4, E5, E6, E7 |
| **FAIL** | **5** | **D1-5, D2-12, D4-2, D4-10, D6-1** |
| **WARN** | **6** | D2-1, D2-2, D2-10, D6-4, D6-6, E3 |
| **未验证** | **22** | D1-1, D1-3, D1-4, D3-1…D3-8, D4-1, D4-4, D4-5, D4-6, D4-7, D4-9, D5-1…D5-5 |
| **合计** | **60** | |

- 以上 5 条判据内 FAIL **另附** 9 条补充缺陷（F-02…F-09、F-11、F-12，见 §2；其中 F-01/F-10 分别归属 D1-5/D4-2）与 1 条快照纪律事件（F-13 / §0.2，**不计入 60 条**）。
- 补充 WARN 6 条（W-07…W-12）亦列于 §2，不重复计入判据计数。
- **未验证 22 条全部因本批仅 2 份（收尾时 2 份 + 1 份未冻结）文件到位**，不是 PASS；其中 D4-1/D4-2 涉及的新文件扫描已作非冻结预警附注。

### 5.2 结论（**不宣布通过**）

> **本人不建议判定「第一批交叉检查通过」。** 理由：
> ① 存在 **1 起快照纪律事件**（指定快照 `862eb9ee9417e1e3` 在审计中途被替换，收尾时又出现未冻结的第 3 份交付物）——按判据 §0，快照不稳时任何「已修/未修」结论都不成立；
> ② 存在 **5 条 FAIL 判据 + 9 条补充缺陷**，其中 F-03/F-04/F-05/F-11 集中在三个核心视图（SQL 不可编译、列数自相矛盾、`all_children_rejected` 恒假、315 个地点 canonical 落空），属**施工级阻断**，不是笔误级问题；
> ③ F-10 的旧隔离规则残留已在共享基线与新交付物之间造成**实际漂移**；
> ④ 22 条判据因文件未产出而**未验证**，不得伪装成 PASS。
>
> 但需同时说明：**设计骨架未被推翻**——五段键、8 值 liveness / 3+3 值 record_status、C01–C29、`place_grain` V2 既有列、md5 指纹、`<> 'rejected' + sr.is_active` 时间过滤、七张 CSV 权威数字、+2 陷阱识别、工程边界 E1/E2/E4/E5/E6 均核实正确；上述 FAIL 多为**可定点修正的文档/SQL 缺陷**，其中 F-03 与 F-11 的根因在 V0.2.2-r2 权威设计本身（§2.2.4 L246–247、§2.2.2 L201 vs §2.8.2 L816），按纪律**不得改权威文件**，须由 team-lead / Owner 裁定后在 CHANGELOG 留痕。
>
> 建议下一步：先冻结唯一快照 → 由架构师按 §2 修正文本逐条修（含两处需 Owner 裁定的 F-06/W-07、F-12）→ 本 QA 按**第 2 轮**（硬上限 2 轮）只跑回归，不再开新检查项；第 2 轮仍失败者按纪律登记为 Known Issues 并退出。最终是否通过，由 team-lead 与 Owner 判定。

---

## 附：本次检查产物与只读范围

- 报告：`_build/QA_CROSSCHECK_BATCH1.md`（本文件）
- 只读脚本：`_build/qa_scripts/qa_crosscheck_scan.py`（快照重算、禁用串/枚举/键串/C 编号/视图列数扫描、七张 CSV 行数与表头实测、E1–E7 基线哈希复核）
- **未修改**：两份被检文件、V2/V2.1/V0.2.2-r2/V0.2.1 基线、七张暂存 CSV、`normalize.py`、任何产品代码
- **未执行**：DDL / Migration / 建库 / 数据导入 / Git 操作
- 快照口径：`sha256(文件原始字节)[:16]`，全程未用「解码后文本再编码」口径
