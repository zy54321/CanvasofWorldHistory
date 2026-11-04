# M4-3 · Pleiades GIS 4.1 完整数据获取与资产审计

执行日期：2026-11-04
分支：`m4-3-pleiades-gis`（从 M4-2 封存提交 `591459a` 拉出）
执行边界：**只读核查 + 下载 + 提取；未写数据库、未执行 Migration、未改 staging、未合并任何数据**

**状态：M4-3 — DATA ACQUISITION & AUDIT COMPLETED / READY FOR IMPORT PLAN ACCEPTANCE**

---

## 一、结论摘要

| 问题 | 结论 |
|---|---|
| 数据是否完整 | **是**。字节数 286,621,469 与 MD5 `ad339c92c6b895f0eb9a52228da498c4` 均与 Owner 给定值逐位一致；ZIP 87265 个条目测试无误 |
| 41,480 个地点是否全部核实 | **是**。行数 41,480，`id` 唯一 41,480，`uri` 唯一 41,480，0 重复、0 空标题 |
| 4,810 条切片孤儿 | **完整包中为 0**。名称孤儿 0、位置孤儿 0、连接孤儿仅 29 条（且是源里真实悬空，不是切片造成） |
| 点 / 面 / 线 | 点 25,038 · 面 4,385 · 线 5,265（合计 34,688 条位置） |
| 新增 / 更新 / 重复 / 待人工判断 | 新增地点 **38,928**；与现库同源重合 **2,552**（其中值有变化 104）；真正重复 **0**；需人工判断 **104 + 91 + 5**（详见 §10、§11） |
| 当前模型能否完整承载 | **面可以，线不行**。`ck_hpl_geom_type` 只允许 Point / Polygon / MultiPolygon，缺 LineString |
| 最小改造 | 1 个 Migration（几何值域 + 可选 `accuracy_m` 语义）+ 3 处脚本改造 + 1 条"不降级"导入规则（见进口方案） |
| 正式库是否完全未变 | **是**。仍 V5，九表行数与本轮开工前一致 |

**最重要的两条新事实（与既有认知不同，必须更正）：**

1. **v4.1 的 GIS 目录里没有 `locations.csv`**。M4-0 审计把 `locations.csv` 列为"缺失文件"，实际是 v4.1 把位置属性直接并进了 `location_points/polygons/linestrings` 三个文件（列完全相同），README 的文件清单与包内实体不一致。**不得凭名字创建这个文件。**
2. **现库里的 `pleiades_gis_4_1_slice` 不是 v4.1，而是比 v4.1 更新的快照**（2026-11 抓取）。证据：91 个已入库地点 id 在 v4.1 中不存在，其中 **87 个的 `created` 晚于 2025-05-28**（最晚 2026-10-14）；`time_periods.csv` 切片 220 行 vs v4.1 204 行，且 11 行 `term` 文案被改过。→ **整包覆盖会造成 104 个地点的信息退化、91 个地点"消失"**，必须用增量规则。

---

## 二、下载与完整性校验

| 项 | 值 |
|---|---|
| 来源 | `https://zenodo.org/records/15540082/files/isawnyu/pleiades.datasets-v4.1.zip?download=1` |
| 记录 | Zenodo record 15540082，DOI `10.5281/zenodo.15540082`，Datasets v4.1，发布 2025-05-28 |
| 下载开始（UTC） | 2026-11-04T07:56:59Z |
| 下载耗时 | 452.17 s（约 634 KB/s） |
| HTTP | 200 |
| 落盘大小 | **286,621,469** 字节（期望 286,621,469，**一致**） |
| MD5 | **`ad339c92c6b895f0eb9a52228da498c4`**（期望同值，**一致**） |
| SHA256 | `94c5c337d27a07f1a5fa231b6513e40e6d3cf7d5ad7b8c010f8e8bfd9159cd85` |
| ZIP 完整性 | `unzip -t` → **No errors detected**，87,265 个条目 |
| 归档顶层目录 | `isawnyu-pleiades.datasets-b6a6790/` |
| 存放 | `code/data/raw/pleiades_gis_4_1/`（`data/raw/` 已加入 `code/.gitignore`，不入库） |

提取范围（只解 GIS 数据目录，未解整个包）：

- `data/gis/*.csv`（17 个）+ `README.md` + `howto.txt`
- 未提取 `data/gis/map_images/`（PNG 底图，非数据）、`data/bibliography/`、`data/data_quality/`、`pleiades/`（逐条 JSON）、`scripts/`、`tests/`

提取后 19 个文件合计 128,705,151 字节；逐文件 SHA256 见 §三。原始 zip 保留，可随时重提取。

---

## 三、文件清单与 SHA256

| 文件 | 字节 | SHA256 |
|---|---:|---|
| `places.csv` | 16,048,687 | `5dd09b1a92c53e50cb9962bab44df12c5f0b7b683d4f228367d843637cfe5a59` |
| `names.csv` | 8,481,492 | `04716712d78dce2b43c9d093ba908d8397ee17496ffec8644e84a4bad1dac02d` |
| `location_points.csv` | 9,408,267 | `20edc5ef9748354fe917a17ba949a17c7af8cc593e07522926924eada64d080d` |
| `location_polygons.csv` | 1,373,849 | `4946c2e5be47797c5e80dffba66c26e40fd2be94e4677c770d1f82ddac124452` |
| `location_linestrings.csv` | 9,227,776 | `a7eee64abdccfb6167dc4c3146b40ed22802bcf6150888fd9b7bee722bfda9ae` |
| `connections.csv` | 2,535,616 | `51e3f71c813b1132d9ef35f7dc2a0b9dea9cb9d5d95068e0b5f50e7e8925f1c3` |
| `places_accuracy.csv` | 80,605,903 | `740849bd213d78993ad754fb316962f6a7cfd9a44cc4cbe7af925c12457709e9` |
| `places_place_types.csv` | 922,188 | `846acc52098771ead0ee673bf92e8304906389fc681c1750107f28d584e09d24` |
| `time_periods.csv` | 38,271 | `3b6e2bb631b94ca342d120cabf10d106cb9262e6570023f31bdcabdbc572e4c5` |
| `place_types.csv` | 30,430 | `bfa08923af4ef739d5c54de7ce7434f87d332837b841fd6661a3e99272fc077b` |
| `connection_types.csv` | 2,710 | `897d76e91a48fd1cf4348df2f472c97122fbb9c81bd24761f434cc26634f06c3` |
| `languages_and_scripts.csv` | 8,811 | `9abdfdce50d3bad91faf623d023e01b9be8e1a7d79d57c9c49fa82cae4194395` |
| `name_types.csv` | 834 | `a90b194523803bce33e649e7b1c4459a192ae52f11a6a45b55201db49fec41ab` |
| `association_certainty.csv` | 471 | `8365c87db1e151a06d6dfed6080eab1d95b8305001992f21ca022ddd9f49a9f3` |
| `archaeological_remains.csv` | 172 | `3e660d5eb697487516e0199605be5bdf41c47547fb333be6c0128266233d8f44` |
| `transcription_accuracy.csv` | 457 | `f1b31e07de97f2833435bc2ccb8601cc4cfa84341b9a12c4b8aecac3f2a9c2ad` |
| `transcription_completeness.csv` | 586 | `384396ca31ebebebb42ee8b6b042e42dff04f201795db08851244fe0333e28e9` |
| `README.md` | 18,514 | `8a2de1089d80e0ac2f6d502bf30555881cc758de20ddcaafaec7a2917fc3b023` |
| `howto.txt` | 117 | `8666d379f366a63dac3b4fc19ce620596fb31f01edb09a90283e72e3a05c7719` |

### 3.1 与 M4-0 审计的差异（更正）

| M4-0 的说法 | 实际 |
|---|---|
| 缺 `locations.csv` | **v4.1 根本没有这个文件**；位置属性在 `location_*` 三个文件里（列完全一致：`accuracy_assessment_uri / accuracy_radius / archaeological_remains / association_certainty / geometry_wkt / year_after_which / year_before_which / location_precision`） |
| 缺 7 个文件 | 实际缺的是 **6 个**：`location_polygons / location_linestrings / places_accuracy / places_place_types / connection_types / languages_and_scripts`；`locations.csv` 不存在，不应算缺 |
| 四份完整 CSV 待补 | `places / names / location_points / connections` 已全部到手，且另有 13 个附表 |

### 3.2 六份旧词表不是 v4.1 版本

现存的 `design/.../gis_vocab/*.csv` 与 v4.1 同名文件**不一致**：

| 词表 | 旧（P0 样本）行/列 | v4.1 行/列 | 差异 |
|---|---|---|---|
| `place_types.csv` | 236 行 / 5 列 | 192 行 / 3 列 | 旧版多 44 个键，且多 `same_as` `uri` 两列 |
| `name_types.csv` | 6 行 / 5 列 | 6 行 / 3 列 | 键相同，旧版多两列 |
| `association_certainty.csv` | 3 行 / 5 列 | 3 行 / 3 列 | 同上 |
| 其余三份 | 均 5 列 | 均 3 列 | 同上 |

判定：旧词表来自 Pleiades **词汇表 API**（带 `uri`、`same_as`、含已废弃类型），不是 GIS 包的导出。**不建议用 v4.1 覆盖**——会丢掉 44 个键与 `uri`。导入时用"并集 + 缺失回退 key"。

### 3.3 `time_periods.csv` 版本差异

| 项 | P0 切片 | v4.1 |
|---|---:|---:|
| 行数 | **220** | **204** |
| 仅切片有 | 16 个键（`anuradhapura`、`bronze-eurasian-cenieh`、`eleventh-bce` …） | — |
| 同键不同文案 | — | 11 行（如 `qarakhanid-period-central-asia` 的 `term` 增加了 "(1000-1200 CE)"） |

→ 再次印证**切片比 v4.1 新**。v4.1 的 `time_periods` 不能回写覆盖现有切片副本。

---

## 四、地点主表（`places.csv`）

| 指标 | 值 |
|---|---:|
| 行数 | **41,480**（与官方口径一致） |
| 唯一 `id` | 41,480（0 重复） |
| 唯一 `uri` | 41,480（0 重复、0 空） |
| 空标题 | 0 |
| 有代表点（`representative_latitude/longitude`） | 33,971 |
| **无代表点且无 `bounding_box_wkt`** | **7,509（18.1%）** |
| `location_precision` | precise 29,396 / rough 12,084 |
| 经度范围 | −19.665682 … 111.078300 |
| 纬度范围 | −22.302631 … 63.200772 |

要点：

- `id` 只在各 CSV 内部唯一，**跨表必须用 `uri`**（本包里 41,480 个 uri 全唯一，可作稳定键）。
- 7,509 个地点**完全没有几何**（不是"几何为空"，是连 bbox 都没有）。它们多数是 `unlocated` 类地点（`places_place_types` 里 `unlocated` 有 6,452 行）。**这类地点不能上图，但必须入库**，否则会丢 18% 的地点史实。
- 经度到 111°E 的 17 个地点在**东南亚与蒙古**（吴哥、Koh Ker、Gol Mod 等），不是中国腹地。

---

## 五、名称（`names.csv`）

| 指标 | 值 |
|---|---:|
| 行数 | **38,862** |
| `name_type` | geographic 36,258 · ethnic 1,396 · associated_modern 1,028 · label 159 · undefined 14 · unknown 7 |
| 语言标签 | 91 种，其中 **空 23,221**（59.8%）；有值的 top：la 3,809 · grc 3,268 · en 2,046 · it 1,317 · akk 827 · tr 540 · ar 534 |
| 父地点不存在（孤儿） | **0** |
| 完全重复行（同 place + 同 title + 同 type） | 651 行 / 586 组 |
| 带 TPQ/TAQ | 35,591 |
| TPQ > TAQ（倒挂） | **0** |
| 空标题 | 0 |

- 651 条"完全重复"是**同地点同名称同类型但不同 `id`** 的记录（不同出处/不同 `created`），属源数据冗余，不是导入错误。导入时按 `(dataset, record_scope, parent, external_id)` 唯一键各建一条 source_record，不做合并。
- 59.8% 的名称没有语言标签 —— 归一化时用 `und`，与 M4-2 现状一致。

---

## 六、位置（点 / 线 / 面）

| 指标 | `location_points` | `location_polygons` | `location_linestrings` |
|---|---:|---:|---:|
| 行数 | 25,038 | 4,385 | 5,265 |
| 解析成功 | 25,038 | 4,385 | 5,265 |
| 空几何 | 0 | 0 | 0 |
| **OGC 无效** | **0** | **5** | **0** |
| 坐标越界 | 0 | 0 | 0 |
| 父地点不存在 | **0** | **0** | **0** |
| `location_precision` | precise 25,038 | rough 3,942 / precise 443 | precise 5,265 |
| `accuracy_radius` | 有值 25,037 / 缺 1 | 有值 514 / 缺 3,871 | 有值 5,265 |
| 带 TPQ/TAQ | 23,366 | 3,849 | 4,777 |
| TPQ > TAQ | 0 | 0 | 0 |
| 同地点同 WKT 重复行 | 49 | 0 | 6 |

**5 条无效多边形**（`shapely.is_valid` 判定，均为源数据缺陷）：

| id | place_id | 原因 |
|---|---|---|
| `total-station-coordinates` | 977,420,436 | Ring Self-intersection @ 40.7274, 34.7512 |
| `total-station-coordinates` | 747,016,480 | Ring Self-intersection @ 40.7272, 34.7508 |
| `plan-location-south` | 15,685,985 | Ring Self-intersection @ 40.7307, 34.7439 |
| `location-of-balochistan` | 84,624,811 | Self-intersection @ 65,28（蝴蝶结：`POLYGON ((60 32, 70 32, 60 24, 70 24, 60 32))`） |
| `total-station-coordinates` | 288,390,870 | Ring Self-intersection @ 40.7270, 34.7511 |

处理建议：**不修改源数据**；导入时 `ST_MakeValid` 落库并登记一条 `geometry_invalid_repaired` 质量记录（保留原始 WKT 在 source_record）。`location-of-balochistan` 那条是**跨 10° 的粗框**（60–70E, 24–32N），精度应判 `rough`，不能当实际范围使用。

### 6.1 每地点覆盖

| 指标 | 值 |
|---|---:|
| 有任意位置的地点 | 30,506 |
| 有点 / 有面 / 有线 | 22,285 / 4,366 / 4,915 |
| **完全没有位置** | **10,974**（其中 7,509 连 bbox 也没有） |
| 每地点位置数 | 1 个：26,918 · 2 个：3,198 · 3 个：319 · 4 个：38 · 最多 **27** |
| 多位置地点 | 3,588（其下共 7,770 条位置） |
| 每地点名称数 | 1 个：18,213 · 2 个：4,307 · 最多 8+；平均 0.94 |
| 有 `names.csv` 行的地点 | 25,174（其余 16,306 个只有 `places.csv` 的 title） |

### 6.2 精度附表（`places_accuracy.csv`）

- 41,480 行（每地点一行），`location_precision` 与主表完全一致（precise 29,396 / rough 12,084）。
- `accuracy_hull` 为空 **12,085** 行（= 无几何地点 7,509 + 只有点/线而无精确位置的 4,576）。
- `max/min_accuracy_meters` 中 **12,007 行是 `-1`**（"未知"哨兵值）。**导入时绝不能把 −1 当米数存**，必须转 NULL 并记质量标记。

---

## 七、连接（`connections.csv`）

| 指标 | 值 |
|---|---:|
| 行数 | **13,603** |
| `connection_type` | 40 种；top：connection 3,622 · at 2,963 · on 1,223 · part_of_physical 1,144 · near 963 · part_of_regional 784 · part_of_admin 594 · part_of_analytical 517 |
| `association_certainty` | certain / less certain / uncertain 等 |
| **孤儿** | **29**（`connects_to` 指向的 place id 不在 `places.csv`，如 `368305523`、`487529761`） |
| 自环（两端同点） | 2 |
| 同三元组重复 | 9 |
| 带 TPQ/TAQ | 3,647（其余连接没有时间界定）；倒挂 0 |

**关键结构事实：`connects_to` 存的是完整 URI**（`https://pleiades.stoa.org/places/433032`），而 `place_id` 是裸 id。两侧必须归一，否则会算出 100% 假孤儿（本轮第一版脚本就踩了这个坑：13,604 条全被判孤儿，修正后为 29 条）。

**`connections` 不是合并依据**：`same_as` 只有 68 条，`relocated_to` 8 条。它们表达"关联/相邻/属于"，**任何一条都不能当作"同一个地点"**。

---

## 八、时间语义

- `places.csv` **没有任何时间列**（README 说 `year_after_which` 适用于 places，实际导出里没有）。地点级时间只能由子行聚合，与现有流水线 `derived_tpq_taq` 做法一致。
- 子表时间覆盖：名称 35,591 / 位置 31,992（点 23,366 + 面 3,849 + 线 4,777）/ 连接 3,647。
- **TPQ > TAQ 倒挂：0**（名称、位置、连接三处全为 0）。
- 原始年份沿用"前推儒略历、无公元 0 年"，与 CHGIS 同约定，沿用现有 `parse_signed_year` 换算（BCE n → 1−n）。
- 不得把子对象时间上提覆盖地点时间；地点级取包络（min 起 / max 止），并标 `derived_tpq_taq`。

---

## 九、与现有切片的对照（版本新旧的硬证据）

| 项 | 值 |
|---|---:|
| 现库切片地点数（`pleiades_gis_4_1_slice`，place 作用域） | 2,643 |
| v4.1 地点数 | 41,480 |
| 两者交集 | **2,552** |
| 仅切片有（v4.1 没有） | **91** |
| 仅 v4.1 有（新增） | **38,928** |
| 覆盖率（切片 / 完整包） | 6.15% |

**91 个"仅切片有"的地点，`created` 分布 2022-05-11 … 2026-10-14，其中 87 个晚于 v4.1 发布日 2025-05-28。**
结论：现库切片抓自比 v4.1 更新的快照。v4.1 是"数量更全但时间更早"的包。

交集里 2,552 个地点的值差异：

| 差异类型 | 数量 | 含义 |
|---|---:|---|
| 值完全未变 | 2,448 | — |
| v4.1 为空、切片有坐标 | **10** | 若用 v4.1 覆盖 → **丢坐标** |
| 切片为空、v4.1 有坐标 | 5 | v4.1 更全 |
| 坐标移动 > 100 m | **35** | 真实修订，方向需逐条判断 |
| 坐标移动 ≤ 100 m | 54 | 多为浮点末位差异 |
| `location_precision` 变化 | 5 | — |

→ **导入必须是增量 + 不降级**，不能"整包覆盖"。

---

## 十、跨数据源重复分析（只出候选，不合并）

方法两条，分开报：

- **名称归一化相等**：Pleiades 是拉丁/希腊文，CHGIS/MCGD 是汉文，跨文字系统基本命中不了。结果：与 CHGIS、MCGD 同名 **3 对**（且 2 对相距 > 50 km）。**这条判据在本项目里不可用**，不能作为去重依据。
- **坐标邻近**（0.1° 网格 + Haversine，取 50 km 内最近点，33,971 个有坐标的 Pleiades 地点参与）：

| 对比源 | ≤1 km | ≤10 km | ≤50 km | 50 km 内无点 |
|---|---:|---:|---:|---:|
| `chgis_cnty`（县级点） | 0 | 0 | **1** | 33,970 |
| `chgis_pref`（府级点） | 0 | 0 | **1** | 33,970 |
| `mcgd_zenodo_22094815_head960` | **1** | 2 | 43 | 33,925 |
| `whg_api_sample`（7 条） | **36** | 525 | 704 | 32,706 |

解读：

1. **Pleiades 与 CHGIS 在地理上几乎不相交**（各只有 1 例在 50 km 内）。两者去重几乎没有实际工作量，这符合"地中海古代世界 vs 中国历代行政区划"的分布。
2. 与 MCGD 的 43 例 50 km 内、1 例 1 km 内，值得人工过一遍（MCGD 也是"古代地点"，但坐标系未知，距离仅供参考）。
3. 与 WHG 的 36 例 1 km 内需要重点看：WHG 样本里有 4 条 GeoNames、1 条 TGN、2 条 HGIS。这些很可能是**同一现实地点的不同来源**，是真正的跨源重复候选（但仍需人工确认，不得自动合并）。
4. 切片自比对（同一来源两版）：1,515 对在 1 km 内、25 对 10 km 内、5 对 50 km 内、3 对 > 50 km —— 说明绝大多数切片地点能在完整包里按"名称 + 位置"对上，**这也是导入映射的可用性验证**。

---

## 十一、现有流水线兼容性（9 问逐条）

| # | 问题 | 现状 | 结论 |
|---|---|---|---|
| 1 | 支持 41,480 个地点？ | `pleiades_extract.py` 只读 5 个**固定文件名的字节切片**（`SLICE_FILES`，路径写死 `PLEIADES_SLICE_DIR`） | **不支持**，需参数化输入目录与文件表 |
| 2 | 支持全部名称及位置记录？ | 切片模式下按行流式读取，无行数上限；`_build_name` / `_build_location` 逐行构造 | **支持**（改输入即可） |
| 3 | 支持 Polygon / LineString？ | `extra_record.parse_wkt_point()` 只认 `POINT`；三个 `_build_*` 里 `geom_type` 硬编码 `Point` | **不支持**，需新增 WKT 几何解析与类型判定 |
| 4 | 支持多个位置对应同一地点？ | 位置行以 `parent_external_id` 挂到地点，模型 `historical_place_location` 一对多 | **支持**（最多 27 个/地点已存在） |
| 5 | 保留精度信息？ | 归一化写 `location_precision="point"`（staging 词表），`import_staging.py:757` 只认 `"precise"`，其余一律 `unknown` | **部分丢失**：`rough` 会被降级为 `unknown`，必须改映射 |
| 6 | 正确处理 TPQ/TAQ？ | `time_semantics.parse_signed_year` + `_pleiades_time_bound_type`，无年份 0 | **支持**（且本轮验证源数据 0 倒挂） |
| 7 | 保留原始 URI 与来源关系？ | `source_record.raw_payload_json` 存整行，`external_id` 存 id | **支持**，但 `uri` 只存在 raw 里，建议提升为可检索列（见进口方案 §9） |
| 8 | 会重复创建已存在的 Pleiades 地点？ | `uq_historical_place_c04 (dataset_id, grain_key)` 只保证"同数据集内不重"；换成新 dataset id 会**再建 2,643 行** | **会**，必须加"跨数据集同源识别"规则 |
| 9 | 保留人工修改保护？ | `created_by='manual'` / `locked` / `manual_edited_fields` 三档保护在 `write_places` 里，与数据集无关 | **支持**（M4-2 已实测 3 行被挡、1:1 台账） |

### 11.1 数据库模型的硬缺口

```
ck_hpl_geom_type: CHECK (geom_type = ANY (ARRAY['Point','Polygon','MultiPolygon']))
ck_hpl_geom_matches_type: CHECK (geom IS NULL OR st_geometrytype(geom) = 'ST_' || geom_type)
```

`geom` 列本身是 `geometry(Geometry,4326)`（通用类型，能存线），**只是 CHECK 值域挡着**。→ 只需扩值域，不用改列类型。

其他相关约束（都已满足，无需改）：

- `ck_hpl_location_precision` 允许 `precise / approximate / rough / unknown` → `rough` 可以直接落库。
- `ck_hpl_c15` 只要求 published 行有 geom；staging 行允许无几何 → 7,509 个无几何地点可以入库。
- `uq_hpl_c07 (source_record_id)` → 每条位置源记录对应一行，面/线不会被合并。
- 地图取点用 `PREFERRED_LOCATION`：**按 `location_id` 升序取第一条有 geom 且有代表点的行**。→ 面/线必须补 `representative_lon/lat`，且插入顺序决定"哪个点代表这个地点"。

### 11.2 归一化脚本的硬编码点

| 位置 | 内容 |
|---|---|
| `pleiades_extract.py:53` | `PLEIADES_DATASET_ID = "pleiades_gis_4_1_slice"` |
| `pleiades_extract.py:56-63` | `SLICE_FILES` 固定 5 个切片文件名 |
| `normalize.py:105` | `EXTRA_SOURCE_DATASETS` 含 `pleiades_gis_4_1_slice` |
| `normalize.py:114` | `DATASET_ORDER` 含 `pleiades_gis_4_1_slice`（决定 place_id 分配顺序） |
| `normalize.py:566` / `887` | `if source_dataset == "pleiades_gis_4_1_slice"` 分支 |
| `normalize.py:1070 / 1220 / 1305` | `"geom_type": "Point"` 硬编码 |

---

## 十二、与既有资产的边界证明

- 未改 `code/data/staging` 七张 CSV（SHA256 与开工时一致，见进口方案 §0 记录）。
- 未改 `设计资料/P0验证`、`设计资料/P0收敛` 下任何文件。
- 未改数据库：正式库仍 **V5**，九表 29,391 / 19,039 / 47,499 / 18,101 / 53,131 / 12,831 / 7 / 8 / 5。
- 未执行任何 Migration；未向任何库写入。
- 原始 286 MB zip 与提取件都在 `code/data/raw/`（已 gitignore），**未提交 Git**。

---

## 十三、本轮遗留与风险

| # | 事项 | 影响 | 建议 |
|---|---|---|---|
| 1 | v4.1 比现库切片旧 | 整包覆盖会退化 104 个地点、丢 91 个 | 用增量 + 不降级规则（见进口方案 §3） |
| 2 | 7,509 个地点无任何几何 | 18% 的地点不上图 | 入库但标 `unlocated`，地图自然不显示；检索仍可用 |
| 3 | 5 条无效多边形 | `ST_IsValid=false`，写入后 spatial index 仍可用但分析会报错 | 导入时 `ST_MakeValid` + 台账留痕 |
| 4 | `accuracy_meters` 有 12,007 行 `-1` 哨兵 | 若当米数存会污染精度统计 | 转 NULL + 记 `accuracy_unknown_sentinel` |
| 5 | 29 条连接指向不存在的地点 | 若强约束会导入失败 | 丢弃该连接并记 `connection_endpoint_missing`，不删源记录 |
| 6 | `place_types` 有 29 个被引用但未定义的键 | 类型标签退化为 key | 用旧词表(236) ∪ v4.1(192) 做字典，缺的回退 key |
| 7 | `connections` 的 `connects_to` 是 URI | 不归一就会造 13,603 条假孤儿 | 导入前统一取 `/places/<id>` 段 |
| 8 | 名称为拉丁/希腊文，与 CHGIS 不可名匹配 | 跨源去重不能靠名字 | 只做坐标候选 + 人工判断 |
| 9 | 词表/时间周期与旧副本版本不同 | 覆盖会丢 44 个类型键、16 个时段 | 只增不覆盖，字典取并集 |

---

## 十四、交付物

| 文件 | 说明 |
|---|---|
| `code/ops/reports/M4_3_PLEIADES_GIS_ACQUISITION_REPORT.md` | 本文件 |
| `code/ops/reports/M4_3_IMPORT_PLAN.md` | 导入方案与最小改造清单 |
| `code/ops/m4-3/pleiades_audit.py` | 只读审计脚本（可重跑，输出 JSON） |
| `code/ops/m4-3/audit.json` | 全量审计结果（含 19 个文件 SHA256、全部计数、示例） |
| `code/ops/m4-3/audit_run.log` | 本次执行的控制台输出 |
| `code/data/raw/pleiades_gis_4_1/` | 原始 zip + 提取的 19 个文件（不入库） |

**M4-3 — DATA ACQUISITION & AUDIT COMPLETED / READY FOR IMPORT PLAN ACCEPTANCE**
