# -*- coding: utf-8 -*-
"""
由 架构/V2.1/FIELD_MAPPING_V2.1.csv 生成 架构/V2.1.1/正式交付/FIELD_MAPPING_V2.1.1.csv
只做"逐行改写 / 追加"，不凭空造行；V2.1 原文件只读不写。
"""
import csv, io, os, hashlib, datetime

SRC = r'./设计资料/P0收敛/架构/V2.1/FIELD_MAPPING_V2.1.csv'
DST = r'./设计资料/P0收敛/架构/V2.1.1/正式交付/FIELD_MAPPING_V2.1.1.csv'
HEADER = ['staging_table', 'staging_column', 'target_table', 'target_column',
          'target_type', 'required', 'transform', 'enum_rule', 'notes']

rows = list(csv.DictReader(io.open(SRC, encoding='utf-8-sig')))
assert len(rows) == 207, len(rows)

# ---------- 1) 逐行改写：key = 1-based 数据行号 ----------
EDIT = {}

def setrow(i, **kw):
    EDIT[i] = kw

# ---- data_datasets.csv：许可 9 列删除（11 行失效）----
setrow(4,  target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1 删除映射行：目标列 license_url 已随 9 列许可列一并删除（CORE §5.2）；data_dataset 不设 homepage 列。'
             '⛔ 不得改落到 notes / evidence 变相保留，也不得改指 data_source。暂存列真实存在（7/7 非空）。')
setrow(5,  target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1 删除：目标列 license_id 已删（CORE §5.2 删除 9 列之一）。暂存列真实存在（7/7 非空、唯一 5）但失去入库通路。⛔ 无替代列。')
setrow(6,  target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='与 homepage 同源重复；V2.1.1 目标模型不设任何许可列 ⇒ 整列 dropped。'
             '（V2.1 notes「保留在 license_evidence 文本里」指向已删除的列，已作废。）暂存 6/7 非空、1 行空。')
setrow(7,  target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1 删除：目标列 redistributable 已删；V2.1 的「三态拆分 unconfirmed⇒true + license_id=unknown」'
             '随 license_id 一起消失 ⇒ transform 无落点。暂存 7/7 非空、唯一 3。')
setrow(8,  target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1 删除：§3.3 明令不重新引入该列或任何替代字段——不改名、不落其它列、不新增引文列。'
             '导出时「原样带出」的义务随之不存在。暂存 6/7 非空、1 行空、最长 158 字符。')
setrow(9,  target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1：原落点 license_evidence 已删 ⇒ 本列无落点。判为**有意丢弃**（STAGING_FIELD_BASELINE §2.6 Q2 处置 (a)）。'
             '内容（取数方式）如需保留须由 Owner 新增非许可目标列，属新设计，本轮不做。暂存 7/7 非空、唯一 6。')
setrow(10, target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1：目标列 license_evidence 已删；本列主要内容为取证文本 ⇒ 整列 dropped。暂存 7/7 非空、唯一 7、最长 459 字符。')
setrow(13, target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1 删除：目标列已删（9 列之一）；判据「attribution_text 非空 ⇒ true」随源列一起删。')
setrow(14, target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1 删除：目标列已删（9 列之一）。')
setrow(15, target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1 删除：目标列已删（9 列之一）。')
setrow(16, target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='V2.1.1 删除：目标列已删（9 列之一）。连带：V2.1 CORE 行 759 的许可门禁前置校验在 V2.1.1 不存在（CORE §8）。')

# place_grain / location_grain：枚举 2 值 + 非新增声明
setrow(18, enum_rule='per_record|per_parent_external_id',
       notes='CORE §5.2.2：V2 既有列（CORE_DATA_MODEL_V2.md:208），V2.1 由 3 值收敛为 2 值（per_external_id 作废）。'
             '⛔ 不是 V2.1.1 新增列。暂存 data_datasets 11 列未导出它 ⇒ 标 derived（"暂存没有" ≠ "设计没有"）。'
             'MCGD = per_parent_external_id；Pleiades / CHGIS = per_record。')
setrow(19, enum_rule='per_record|per_parent_external_id',
       notes='V2 既有列，V2.1 由 3 值收敛为 2 值。⛔ 非 V2.1.1 新增。')
# occurrence_key_rule：V-3 裁定
setrow(21, notes='V2.1 新增列。⭐ V-3 裁定（team-lead）：**保留该列**；但其服务对象 occurrence_key 已被 '
                'parent_external_id + duplicate_ordinal 取代（V0.2.2 全篇零命中）⇒ 本列在 V2.1.1 中不再参与键生成；'
                '去留待施工验证后由下轮决定。')

# ---- source_records.csv ----
setrow(34, notes='⭐ D-3 更正：暂存实测 external_id_type **只有 11 种**（不是 V2.1 notes 写的 16 种——16 是映射行数，不是类型数）。'
                '11 种 = chgis_sys_id / mcgd_nameid / pleiades_place_id / pleiades_name_id / pleiades_location_id / '
                'pleiades_connection_id / whg_source_id / whg_place_name_index / whg_geometry / whg_place_id / whg_geom_index。'
                '逐条查表，不猜。')
setrow(38, notes='暂存按行冗余的许可三列，V2.1 已判 dropped；V2.1.1 目标模型不设任何许可列（§3.3）⇒ 判据改为「目标模型无许可列」。'
                '（V2.1 notes「许可只从 data_dataset 读」已随 data_dataset 9 列删除而失效。）暂存 29,391/29,391 非空、唯一 6。')
setrow(39, notes='同上（§3.3）。暂存 29,391/29,391 非空、唯一 3（no / yes_with_attribution / unconfirmed）。')
setrow(40, notes='同上（§3.3）。暂存 29,383/29,391 非空、8 行空、唯一 5。')
setrow(43, transform='lookup(dataset_id,external_id_type) + 白名单', enum_rule='place|name|location|edge',
       notes='⭐ 4 值，**不得出现 connection**。11 → 4 权威查表（CORE §5.4.2，暂存原始口径）：'
             'place = chgis_sys_id 15,748 + pleiades_place_id 2,643 + whg_source_id 5 + whg_place_id 2 = **18,398**；'
             'name = pleiades_name_id 4,579 + mcgd_nameid 960 + whg_place_name_index 223 = **5,762**；'
             'location = pleiades_location_id 2,460 + whg_geometry 5 + whg_geom_index 3 = **2,468**；'
             'edge = pleiades_connection_id **2,763**；合计 **29,391** ✓。'
             '⛔ 命名陷阱：whg_place_name_index 名字含 place 但映射 name；whg_place_id（2 行）才映射 place——不得按名字子串推断。'
             '第五种取值 ⇒ A12 整批 failed，不默认放行。')
setrow(44, target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='⭐ CORE §5.0：occurrence_key **已删除**，被 parent_external_id + duplicate_ordinal 取代（V0.2.2 全篇零命中）。'
             'V2.1 的 UNIQUE(dataset_id, record_scope, external_id, occurrence_key) 由 C01 五段键取代。'
             '⛔ 取代关系须写入 CHANGELOG。（CORE §5.4 另列 V-13 待裁定是否物理保留列；本表按删除处置，不写值。）')
setrow(45, target_type='text', required='Y', transform='json_field+sentinel',
       notes='⭐ **C29 五段键必需段**：NOT NULL，不得 NULL、不得空串（Postgres UNIQUE 对多列 NULL 不去重 ⇒ 五段键静默退化为四段键，'
             '398 组 / 2,335 行会被误隔离）。Pleiades name / location / edge → raw_payload.place_id；MCGD → raw_payload.LocID；'
             "record_scope='place'（本身即实体、无父级）一律落哨兵 '-'；payload 顶层确无 place_id / LocID 的 WHG 子记录同样落 '-'。"
             '实测（暂存原始口径）：可派生 **10,765** / 落哨兵 **18,626** / 合计 29,391 ✓。'
             '⛔ whg_geom_index 那 3 行 payload 顶层确有父键，属**可派生**，不得计入缺口。'
             '「缺口 2,878」是相对 C29② 原文的口径（18,626 与 2,878 是两个不同口径，都对）。'
             '派生失败 ⇒ 整批 failed（同 A12）。哨兵只在常量表声明一次（C29④）。')
setrow(46, notes='CORE §4.4 八条规则。规范表达式（唯一）：'
                "sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(',',':')))；"
                '完整串 len == 85、sha1 == 9b0414f5c7b9a4f3d3bfc1d6d5998ab73a6435a5；'
                '内层 json.dumps(...) len == 77、sha1 == 781f68645c4e2e3af4b18871f2f5b7848c5f3798。'
                '逐字节形式仅当 normalize.py:306 约定不变时等价。'
                '⚠️ H1：normalize.py:306 一旦改动必须回归 content_hash（否则 29,391 条哈希全变 ⇒ ordinal 大规模重排 ⇒ STOP_AUTO 误触发、整批 SKIP_UPDATE）。'
                'raw_payload 键名保持源原样；不含导入器补齐的任何字段。')
setrow(49, notes='⭐ 判据改写（V0.2.2 §2.3.1 第 0 行）：is_active=false ⇔ 同**五段键的四段前缀**（含 parent_external_id）下，'
                '存在另一行 content_hash 相同且 duplicate_ordinal 更小——即「每 hash 子组内最小 ordinal 保留、后续同 hash 隔离」。'
                '隔离是**每批重算的派生结论**，不是一次置位；O7 解除人工保护不得复活它。'
                '⛔ 禁止「只比 ordinal=1 的 hash」（会漏掉混合组 sr_0027175）；⛔ 禁止「要求整组内容完全相同才隔离」。'
                '本批 3 行（入库口径）：sr_0004941 / sr_0004942 / sr_0027175。')

# ---- historical_places.csv ----
setrow(57, notes='MCGD 643 行填 LocID 而 source_record.external_id 是 NameID ⇒ 不能用于 external_id 的 join；'
                '但 LocID 正是 parent_external_id 的来源（C29），**二者用途不同、不可混淆**。'
                '地点归属一律走 created_from_source_record_id。暂存 19,039/19,039 非空、唯一 18,997。')
setrow(58, enum_rule='staging|rejected|merged',
       notes='⭐ 地点 **3 值**（V0.2.2 §2.1.1 行 76、§4.1 K5）；V2.1 的 4 值含 published **已作废**。'
             '⛔ 子表 3 值是 staging / published / rejected——两套值域不同（地点有 merged 无 published；子表有 published 无 merged），不得合并成一套。'
             '本批暂存唯一 1 值 = staging（19,039/19,039）。rejected 是**派生态**（由证据集合求出），不是人置位。')

# ---- historical_place_locations.csv ----
setrow(109, transform='gate + rejected_by 联动', enum_rule='staging|published|rejected',
       notes='⭐ 子表 **3 值**（含 published），与地点表值域不同，不得合并。'
             'C25：(record_status = \'rejected\') = (rejected_by IS NOT NULL)——由本行与 rejected_by 行**共同**满足。'
             'crs_confidence=\'unknown\' 或 geom NULL ⇒ staging。'
             '暂存 historical_place_locations 22 列中无 record_status、无 rejected_by ⇒ derived。')
# ---- historical_place_names.csv ----
setrow(131, transform="literal 'staging' + rejected_by=NULL", enum_rule='staging|published|rejected',
       notes='⭐ 子表 **3 值**（含 published）。C25 由本行与 rejected_by 行共同满足：本批 literal \'staging\' ⇒ rejected_by 必为 NULL，'
             'C25 / C26 构造上自动满足，无需运行期判定。暂存 13 列中无 record_status、无 rejected_by ⇒ derived。')

# ---- data_quality_issues.csv ----
setrow(173, notes='⭐ D-6（**未解决**，CORE §5.9.1 / 附录 B V-6）：暂存 data_quality_issues 只有 11 列，**无 raw_file、无 dataset_id**；'
                  'source_record_id 有 **6 行空**（12,625/12,631 非空）⇒ 这 6 行既无 source_record_id 可 join、也无 raw_file 可归属，'
                  'dataset_id（NOT NULL，C11/C12）**无来源**。本版处置：标 derived + 列为待定。'
                  '⛔ 不得静默填默认值——那会让 C11/C12 的 NOT NULL 变成"看起来合法"的假约束。'
                  '正常路径：有 source_record_id 则 join source_record.dataset_id。')
setrow(175, notes='本批批次号（CORE §5.9 保留该列）。**不进指纹**（含了每导一批新增 197 行，台账自我膨胀）。R1 口径：与 first/last_batch_id 并存，语义不同。')

# ---- import_batch ----
setrow(185, transform="literal 'v2.1.1'")
setrow(192, notes='本批隔离的记录数（is_active=false），**既不是 inserted 也不是 failed**。'
                  '⭐ 期望值断言（新增）：本批 = **3**（sr_0004941 / sr_0004942 / sr_0027175，入库口径 N02 / N18）。'
                  'R1 口径：N_quar 与 inserted / failed 相互独立，不得相减混算。')
setrow(194, notes='写入失败行数。R1 口径：**不含** N_quar（隔离），也**不含** blocked_count。')

# ---- data_source ----
setrow(202, target_column='homepage_url',
       notes='对齐 V2 §5.1（经 V2.1.1 CORE §5.1 → V2.1 §5.1 → V2 §5.1）：列名是 **homepage_url**；V2.1 映射写成 homepage 属笔误，本版更正。')
setrow(203, target_column='(dropped)', target_type='-', required='-', transform='dropped', enum_rule='-',
       notes='⭐ Q1 处置：该目标列命中禁用正则 ^(attribution|citation|license)_ ⇒ 必须清零。'
             '处置 = **删除**（不改名——改名即触 §3.3「任何替代字段」；同表已有 homepage_url 承载源主页链接）。'
             '⛔ **双重删除理由**：① 许可管理残留，命中禁用正则；② **幽灵行**——该列只在 V2.1 映射表与 '
             'V2.1 ER 图中出现，`CORE_DATA_MODEL_V2.1.md` **零命中**（V2.1 CORE §5.1 未定义此列），映射表这行本就无源之水。'
             'CORE §5.1「data_source 无变化」指**表结构无变化**，该列从未进入 CORE 列清单 ⇒ 不存在"漏删"，CORE 无需解冻补注。'
             '⚠️ 连带：`ER_DIAGRAM_V2.1.svg:52` 含该字段 ⇒ `ER_DIAGRAM_V2.1.1.svg` 不得出现任何 `license_*` 字段。')
setrow(204, notes='展示层排序，默认关闭（默认 0 = 全部等权 = 不启用）。'
                  '⚠️ 列定义不在 V2.1.1 CORE 正文（CORE §5.1 只写"无变化"），出处为 V2 §5.1（CORE_DATA_MODEL_V2.md:156–170）。')

for i, kw in EDIT.items():
    rows[i - 1].update(kw)

# ---------- 2) 追加新行：挂在各 staging_table 组的末尾 ----------
NEW = {
    'source_records.csv': [
        dict(staging_table='source_records.csv', staging_column='(derived)', target_table='source_record',
             target_column='duplicate_ordinal', target_type='integer', required='Y',
             transform='ordinal_by_hash', enum_rule='0|1..n',
             notes='⭐ V2.1.1 新增（C01 五段键必需段，NOT NULL DEFAULT 0）。'\
                   '组内按 (content_hash ASC, raw_record_index ASC) 定序后的名次；单行组 = 0。'\
                   '实测（暂存原始口径）：ordinal=0 共 **29,377**，另 7 组 × 2 行 = 14 行（ordinal 1/2 各 7 行）。'\
                   '⛔ raw_record_index **只能**在 content_hash 完全相等时破并列；它不保证文件内唯一（14 个 raw_file 中 7 个不唯一，全为 WHG）。'\
                   '语义是"内容的函数"，不是身份：ordinal 绑定了哪一行没有语义。'),
        dict(staging_table='source_records.csv', staging_column='(derived)', target_table='source_record',
             target_column='inactive_reason', target_type='text', required='N', transform='rule',
             enum_rule='source_absent|batch_rolled_back|duplicate_quarantine',
             notes='⭐ V2.1.1 新增（V0.2.1 §4.3 C19；V2.1 目标表无此列）。3 值 + NULL 表 active；'
                   'import_error 已删除（0 条可达路径）。C03/C18：与 is_active 同生同灭；'
                   'C20：inactive_reason = duplicate_quarantine ⇒ duplicate_ordinal > 0。'
                   '本批落 duplicate_quarantine **3** 行（入库口径）。暂存 14 列无此列 ⇒ derived。'),
        dict(staging_table='source_records.csv', staging_column='(derived)', target_table='source_record',
             target_column='inactive_at', target_type='timestamptz', required='N', transform='rule', enum_rule='-',
             notes='⭐ V2.1.1 新增。失效时间戳，与 inactive_reason 同生。C21：(inactive_at IS NULL) = (inactive_reason IS NULL)。暂存无此列 ⇒ derived。'),
        dict(staging_table='source_records.csv', staging_column='(derived)', target_table='source_record',
             target_column='inactive_in_batch_id', target_type='bigint', required='N', transform='batch', enum_rule='-',
             notes='⭐ V2.1.1 新增。FK → import_batch。C22：(inactive_in_batch_id IS NULL) = (inactive_reason IS NULL)。暂存无此列 ⇒ derived。'),
    ],
    'historical_places.csv': [
        dict(staging_table='historical_places.csv', staging_column='(derived)', target_table='historical_place',
             target_column='dataset_id', target_type='text', required='Y',
             transform='join(created_from_source_record_id→source_record.dataset_id)', enum_rule='-',
             notes='⭐ V2.1.1 新增（Owner 决策 5）。⛔ V2.1 §5.2.1 规则 1「地点不带 dataset 列」**已被推翻**（CORE §5.5.0）。'
                   '与 grain_key 组成 UNIQUE(dataset_id, grain_key)（C04）。'
                   '这是 §5.5.5 建点白名单与 v_place_evidence 的 ON sr.dataset_id = p.dataset_id 能成立的唯一前提；'
                   '⛔ 下轮不得按 V2.1 旧规则把这两列删回去。暂存 15 列无此列 ⇒ derived。'),
        dict(staging_table='historical_places.csv', staging_column='(derived)', target_table='historical_place',
             target_column='grain_key', target_type='text', required='Y', transform='rule_by_dataset', enum_rule='-',
             notes='⭐ V2.1.1 新增（CORE §5.0）。派生唯一实现（CORE §5.5.3）：'
                   "dataset.place_grain = 'per_record' ⇒ record.external_id；"
                   "= 'per_parent_external_id' ⇒ record.parent_external_id；"
                   '其余 ⇒ NULL（NOT NULL + CHECK 2 值已封死；发生即整批 failed）。'
                   '⛔ 两件事必须分开写：① **grain_key 列**——V2.1 没有，V2.1.1 **新增**；'
                   "② 它在 v_place_evidence join 里的**旧用法** `p.grain_key = sr.parent_external_id AND sr.record_scope <> 'place'`——**已作废**，"
                   '被 V0.2.2 §2.7 白名单取代。本行只登记列，不登记旧谓词。'
                   '⚠️ 与 QA STAGING_FIELD_BASELINE §2.7 判定式 **M2** 冲突：M2 判「含 target_column = grain_key 的行 > 0 即 FAIL」，'
                   '该判据把"列"与"旧用法"混为一谈；本表按 team-lead 对 D-2 的裁定保留该行，**冲突已登记，待裁定**。'),
    ],
    'historical_place_locations.csv': [
        dict(staging_table='historical_place_locations.csv', staging_column='(derived)',
             target_table='historical_place_location', target_column='rejected_by', target_type='text',
             required='N', transform='literal NULL', enum_rule='auto|manual',
             notes='⭐ V2.1.1 新增（C25 / C26）。本批暂存 0 条 rejected ⇒ 初值 literal NULL，C25 / C26 **构造上自动满足**，'
                   '无需运行期判定（实现者不要去找一个不存在的暂存列）。'
                   '⛔ rejected_by = \'manual\' 永不自动恢复；O7 解除人工保护不得复活它。'
                   '⛔ 不得"把所有 rejected 子行恢复成 staging"来绕过本条。'),
    ],
    'historical_place_names.csv': [
        dict(staging_table='historical_place_names.csv', staging_column='(derived)',
             target_table='historical_place_name', target_column='rejected_by', target_type='text',
             required='N', transform='literal NULL', enum_rule='auto|manual',
             notes='⭐ V2.1.1 新增（C25 / C26）。本批暂存 0 条 rejected ⇒ 初值 literal NULL，C25 / C26 构造上自动满足。'
                   '⛔ rejected_by = \'manual\' 永不自动恢复（场景 C：源重新出现时保持 rejected，另落 1 条 manual_edit_conflict 提示人工复核）。'),
    ],
    'data_quality_issues.csv': [
        dict(staging_table='data_quality_issues.csv', staging_column='(derived)', target_table='data_quality_issue',
             target_column='issue_fingerprint', target_type='text', required='Y',
             transform='generated(md5 jsonb_build_array)', enum_rule='-',
             notes='⭐ V2.1.1 新增。**PostgreSQL 生成列，非导入器写入**：'
                   'GENERATED ALWAYS AS md5(jsonb_build_array(source_record_id, dataset_id, place_id, issue_type, field_name, observed_value)::text) STORED。'
                   '⛔ ALG-1：算法是 **md5**，不得改 sha256（197 条历史指纹会全部对不上）；与 content_hash 的 sha256 **并存是有意设计**，不得互换、不得统一。'
                   '六段（含 place_id）⇒ 197 个不同指纹 / 0 冲突；去掉 place_id ⇒ 45 个 / 24 冲突组 / 176 行。'
                   '**不做 coalesce**：NULL 与 \'\' 必须可区分。observed_value 只放暂存列原始字符串单值，空值渲染字面量 NULL，重算值进 notes。'
                   'UNIQUE(issue_fingerprint)（C10）替换 V2.1 的两条部分索引。'),
        dict(staging_table='data_quality_issues.csv', staging_column='(derived)', target_table='data_quality_issue',
             target_column='first_batch_id', target_type='bigint', required='Y', transform='batch', enum_rule='-',
             notes='⭐ V2.1.1 新增（C24）。首次发现该问题的批次；重复发现时**不变**。台账语义 A（唯一身份）。'),
        dict(staging_table='data_quality_issues.csv', staging_column='(derived)', target_table='data_quality_issue',
             target_column='last_batch_id', target_type='bigint', required='N', transform='batch', enum_rule='-',
             notes='⭐ V2.1.1 新增（C24）。最近一次发现的批次；重复发现时置为本批。C24：first_batch_id IS NULL OR last_batch_id IS NOT NULL。'),
        dict(staging_table='data_quality_issues.csv', staging_column='(derived)', target_table='data_quality_issue',
             target_column='occurrence_count', target_type='integer', required='Y',
             transform='literal 1 / 重复发现 +=1', enum_rule='-',
             notes='⭐ V2.1.1 新增，NOT NULL DEFAULT 1（C23：occurrence_count >= 1）。重复发现时 **UPDATE 不 INSERT**：'
                   'last_batch_id = 本批、occurrence_count += 1、first_batch_id 不变。'
                   '指纹**不含 batch_id**（含了每导一批新增 197 行，台账自我膨胀）。内容不同的多次冲突各占一行。'),
    ],
    'import_batch': [
        dict(staging_table='(none)', staging_column='(generated)', target_table='import_batch',
             target_column='blocked_count', target_type='integer', required='N', transform='count', enum_rule='-',
             notes='⭐ 补登记：V0.2.2 §2.4.2（行 438）/ §2.4.3（行 509）权威列 = 记录级跳过（locked / 字段保护 / '
                   'last_batch_id 不符）。V2.1 CORE §5.3 与 V2.1 映射表**均漏记**，V2.1.1 CORE §5.3 已补。'
                   '⛔ 与 failed_count 互斥：两者都**不含** N_quar。'),
    ],
}

def group_of(r):
    # (none)/(generated) 的两组（import_batch / data_source）按 target_table 分组
    return r['target_table'] if r['staging_table'] == '(none)' else r['staging_table']

out = list(rows)
for grp, newrows in NEW.items():
    idx = max(i for i, r in enumerate(out) if group_of(r) == grp)
    for off, n in enumerate(newrows):
        out.insert(idx + 1 + off, n)

with io.open(DST, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=HEADER, lineterminator='\r\n')
    w.writeheader()
    for r in out:
        w.writerow({k: r.get(k, '') for k in HEADER})

print('rows written:', len(out))
b = open(DST, 'rb').read()
print('bytes:', len(b), 'sha256[:16]:', hashlib.sha256(b).hexdigest()[:16])
