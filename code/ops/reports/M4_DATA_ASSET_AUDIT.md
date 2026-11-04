# M4-0 数据资产与数据源现状核查报告

- 核查时间：2026-11-04（Asia/Shanghai）
- 核查范围：P0 原始数据、P0 归一化程序、抓取/检查脚本、七张暂存 CSV、八份问题清单、数据模型与导入规则、M1 数据库模型、当前导入与本地化状态
- 核查方式：**只读**。`ls / stat / sha256sum / unzip -l / psql SELECT / Python 解析 JSON`；未下载任何数据、未修改原始文件、未执行 Migration、未写数据库、未改动正式环境
- 核查结论（一句话）：**数据本身可用、流水线能力真实存在；但 P0 的原始样本、八份问题清单、全部处理脚本已于 2026-11-03 12:14 被移入回收站，当前项目目录只剩 7 张归一化 CSV；同时系统内仍有 5 处许可检查/许可字段残留（另有 1 处设计留痕待标注），与最新 Owner 决策不一致。**

---

# 第一部分　事实

## 1. 资产现状：P0 成果的实际位置

### 1.1 当前项目目录内（仍在）

| 路径 | 内容 | 文件数 | 体积 |
|---|---|---:|---:|
| `设计资料/P0收敛/WB-002/normalized/` | 7 张归一化 CSV + `run_manifest.json` + `stats.json` | 9 | 72 MB |
| `code/data/staging/` | 导入器输入：同上 7 张 CSV（逐字节相同） | 8（含 `.gitkeep`） | 72 MB |

> 两处 7 张 CSV 的 SHA256 完全一致（逐文件对比见 §3.2），即 `code/data/staging` 是 P0 归一化产物的副本，不是第二次处理的结果。
> 两处均被 `.gitignore` 排除（根 `.gitignore` 忽略 `设计资料/P0收敛/`；`code/.gitignore` 忽略 `data/staging/*`），**不在 Git 版本控制内**。

### 1.2 已被移入回收站（不在项目目录）

| 回收站条目 | 原始路径 | 内容 | 文件数 | 体积 | 删除时间 |
|---|---|---|---:|---:|---|
| `$I4BI1K6` → `$R4BI1K6` | `设计资料/P0验证` | 四源原始样本（37 个文件）+ 5 份 P0 报告 + `FIELD_MAPPING.csv` | 43 | 1.90 MB | 2026-11-03 12:14:09 |
| `$IXROG9G` → `$RXROG9G` | `设计资料/P0收敛` | normalized + **issues（8 份清单）** + Pleiades 切片（6 个）+ 6 份报告 | 182 | 102.8 MB | 2026-11-03 12:14:09 |
| `$ICJY9IU` → `$RCJY9IU` | `code/p0` | `wb-002-normalize`（16 个脚本）+ `wb-002-tools`（7 个脚本）+ `wb-001-maptiler-demo` | 2,871 | 129.3 MB | 2026-11-03 12:14:14 |

> 删除后 12 分钟（12:26），`设计资料/P0收敛/WB-002/` 被重建，但**只回填了 `normalized/`**，
> `issues/` 与 P0 报告没有回来；`设计资料/P0验证` 与 `code/p0` 至今不存在。

**直接后果**

1. 八份数据质量问题清单（`issues/*.csv`）当前不在项目目录，只在回收站；
2. 四源原始样本（1.90 MB）只在回收站，`data_dataset.local_path` 指向的路径全部失效（§7）；
3. 归一化程序、抓取脚本、字段核验脚本（23 个文件）只在回收站，`code/p0/...` 路径已不存在；
4. `ops/reports/M4_DATA_ASSET_AUDIT.md` 本次之所以能给出完整文件级证据，是因为回收站内容尚未被清空——**这是一次性的**。

## 2. 四个数据源逐一核查

### 2.1 Pleiades

| 项 | 事实 |
|---|---|
| 当前版本 | GIS 发布版 **4.1（2025-05-28，41,480 条 place）**（`pleiades/datasets_docs/README.md` 第 11–15 行） |
| 抓取方式 | 逐条 JSON API（4 条 place）+ GitHub raw 的 **HTTP Range 字节切片**（5 个 CSV） |
| 原始文件清单 | `places/423025.json`、`579885.json`、`893951.json`、`912816.json`；`gis_vocab/` 6 个词表；`datasets_docs/` 3 份文档（README / gis_README / CC-BY-3.0）；`sample_data_pleiades/` 5 个切片 + `FETCH_LOG.tsv` |
| 是否仅有字节切片 | **表格数据是**。`places.csv` 1,048,576 B、`names.csv` 1,048,576 B、`location_points.csv` 1,048,576 B、`connections.csv` 524,288 B 均为前段切片；`time_periods.csv` 40,909 B 为完整文件 |
| 实际覆盖 | 全库 41,480 → 切片内 **2,643 个 place（6.4%）**；名称 4,579 行（入库 2,074）；点位 2,460 行（入库 1,704）；连线 2,763 行（入库 390 条边） |
| 完整包缺哪些文件 | `locations.csv`、`location_polygons.csv`、`location_linestrings.csv`、`places_accuracy.csv`、`places_place_types.csv`、`connection_types.csv`、`languages_and_scripts.csv`；以及下表 4 个 CSV 的**完整版**（`time_periods.csv` 已是完整文件） |

已下载切片的「已取 / 全量」字节（`FETCH_LOG.tsv` 的 `Content-Range` 原文）：

| 文件 | 已取 | 全量 | 覆盖 |
|---|---:|---:|---:|
| `places.csv` | 1,048,576 | **16,640,585** | 6.3% |
| `names.csv` | 1,048,576 | **9,775,449** | 10.7% |
| `location_points.csv` | 1,048,576 | **9,705,808** | 10.8% |
| `connections.csv` | 524,288 | **2,810,509** | 18.7% |
| `time_periods.csv` | 40,909 | 40,909 | 100% |

> 仅这 5 个 CSV 的完整版合计 **38,933,260 B（≈37.1 MiB）**；其余 7 个缺失文件（面、线、精度、词表）体量未取，需下载时再核。
| places 处理 | 切片 2,643 个；`places.csv` **没有时间列**（与官方 README 声称不符，按数据处理）；327 个地点无坐标；时间由 `location_points.csv` 的 `year_after_which / year_before_which` 派生为 `tpq_taq` / `bounded` |
| names 处理 | 有效 4,579 行 → 入库 2,074 行；**2,505 行因父地点落在 1 MB 窗口外而入不了库**（标 `parent_place_not_in_sample`，不丢弃、不臆造父行） |
| location_points 处理 | 有效 2,460 行 → 入库 1,704 行（756 行父地点缺失）；1 条 `POINT Z` 丢弃 Z 值 |
| polygons 处理 | **未下载、未处理（0 条）** |
| linestrings 处理 | **未下载、未处理（0 条）** |
| 其他 | 每个切片末尾有 1 行被字节截断，共 4 行丢弃并记账（`truncated_slice_tail`）；HTML 页面有反爬挑战，JSON 端点正常 |

### 2.2 CHGIS

| 项 | 事实 |
|---|---|
| 当前版本 | **CHGIS V6**（README 2016-12；府级点层包内文件 2017-01-12，县级点层 2017-08-21） |
| 文件完整性 | **完整**。两个 zip 均含 `.dbf / .prj / .cpg / .shp / .shx`（府级另有 README）；`.prj` 原文为 `GCS_WGS_1984` |
| 记录数 | 府级 `v6_time_pref_pts_utf_wgs84` **5,226**；县级 `v6_time_cnty_pts_utf_wgs84` **10,522** |
| 已处理 | 15,748 条记录 → **15,746 个地点**（府级 5,226→5,224，2 条完全重复行）× 44,242 条名称 × 15,746 条位置（均为入库值） |
| 时间异常 | **28 条倒挂**（府 9 / 县 19）：原值保留、派生年份留空、`time_bound_type=unknown`、`quality_flag=beg_gt_end`；**21 条规则 9 快照**改判为 `snapshot`（原被误读为多年区间）；341 条 `BEG_YR=END_YR`；4 条年份越界；1,068 条两端确定性不同（`exact_or_bounded` / 部分 `unknown`） |
| 坐标异常 | 10 条 DBF 溢出标记（`geom IS NULL`）；6,013 个不同坐标承载 15,738 条记录，单点最多 34 条（同城共址，不是重复导入） |
| 重复 | 2 条 `duplicate_sysid`（同一外部 ID 内部重复）→ 隔离不入库；5 条 `duplicate_external_id` 台账 |
| 迁治候选 | **1,866 条腿 / 1,254 条链，0 条已确认**，全部 `needs_manual_review`；`confidence` 只反映年隙，不反映真实性 |
| 是否还需补图层 | **需要**。V6 README 列出 **33 个图层**，本项目只处理了 2 个点层；缺口含 `v6_time_pref_pgn`（31,098,173 B）、1820 系列（省/府/县/镇点面、海岸线、河流、湖泊）、1911 系列（省/府/县/镇点面）、1990 census、明代驿路/驿站、茶马古道、ChinaW 等 |

### 2.3 MCGD

| 项 | 事实 |
|---|---|
| 当前样本 | `MCGD_Data2026_08_25.csv.head-960rows.sample.csv`（65,478 B，960 行，从 64 KiB Range 推导） |
| 官方完整文件 | **未下载**。Zenodo 记录 22094815：`MCGD_Data2026_08_25.csv`，**31,953,904 B**，`md5:48b9c064c8e151169b76809d375d19b4`，`publication_date 2026-08-25`，`license cc-by-4.0`，`access_right open`；Zenodo 的 `metadata.version` 为 **null**，描述正文自称 `MCGD_Data_V2.2`、**472,749 条** |
| 完整 vs 样本 | 样本 960 / 472,749 = **0.20%**；样本只有前 9 列的表头与首批行，无法覆盖省份分布、`Code` 取值分布、坐标缺失比例 |
| 已处理 | 960 行 → **643 个地点**（`LocID` 才是地点键）→ 960 条名称、643 条位置 |
| CRS 未知 | **643 条全部 `original_crs='unknown'` + `crs_confidence='unknown'`**（文件无 CRS 声明；列名 `LAT/LONG` 与数值反证只支持轴序，不支持基准面）→ 646 条 `unknown_crs` 台账的主体 |
| 中文/拼音/转写映射 | `Name`（多为威妥玛转写）+ `Code`（A 中文正名 / C 中文别名 / P 拼音 / W 其他转写 / PP、WW 无对应中文名）；归一化按 `Code` 映射 `name_type`，`NameID` 为行键 |
| 其他 | 6 条坐标落在中国 bbox 之外（源数据标 `NA`）；文件无年代列（时间只能回 CHGIS 侧补） |

### 2.4 WHG

| 项 | 事实 |
|---|---|
| 样本 | **7 条记录**，全部来自 `whgazetteer.org` API（2026-11-02T02:38Z 前后） |
| 逐条 namespace / 外部 ID | ① `whg:169687`（legacy，Santa Fe，HGIS de las Indias）② `whg:169687-169688`（legacy 复合记录，Santa Fe\|Aguanuato）③ `gn:1790630` Xi'an ④ `gn:1816670` 베이징/Beijing ⑤ `gn:3169070` Roma ⑥ `gn:98182` Baghdad ⑦ `tgn:7011781` Londen |
| 抓取脚本与 API | `fetch_samples.sh` + `r2_verify_whg_mcgd_chgis.py`；使用 `GET /api/place/{id}/`（legacy）、`GET /entity/place:{gn\|tgn}:{id}/api`（LPF v1.1）、`GET /api/sources/`。探测结果：`/suggest/entity` **401**、`/reconcile` **401**、`/atlas/search` **403**、`/entity/dataset:14/api` **401**、whg 原生 ID `/entity/place:169687/api` **401** |
| 已处理 | 238 条 source_record（gn 209 / tgn 21 / hgis 8）→ **7 个地点 / 223 条名称 / 8 条位置**；`when.timespans` 多为空，时间统一 `unknown` |
| 哪些来源值得补充 | 按 `sources.json` 的 28 个命名空间与 `record_count`：GeoNames 13,454,817、Getty TGN 2,991,143、CHGIS 81,292（`redistributable=false`）、HGIS 14,105；其余（Pleiades、TM 等）按需。**但按 Owner 决策本轮不新增数据源、不做全量抓取**，只建议定向补 1–2 个与现有 CHGIS/Pleiades 不重叠的命名空间 |
| 与 CHGIS/Pleiades 重复风险 | **高**：WHG 本身就是聚合器，`chgis` 命名空间的 81,292 条即来自 CHGIS；`pleiades` 命名空间同理。若按名称/坐标自动合并会造成重复计数，必须只做「候选 + 人工复核」，与现有 `candidate_match` 机制一致 |

## 3. 原始文件清单、大小、版本、SHA256

### 3.1 原始样本（`sample_data/` 37 个文件，1,902,111 B；现位于回收站 `$R4BI1K6/WB-002/sample_data/`）

| 文件 | 字节 | SHA256 |
|---|---:|---|
| `MANIFEST.tsv` | 7,310 | `d006adf4291ee5a04bc4807991a707d80f4d00b133a7ae561d2ddc7a673dc58b` |
| `PROBES.tsv` | 3,502 | `e44ce626ae834d2a90c0d2a99b8bdc2a9c2e39ace285f07b96a71cb09fc4a39b` |
| `chgis/CHGIS_V6_README.txt` | 2,323 | `8f31213af43fa47e72288d771b8e03e3a49fcc68155b6e64fa6f61ba3bae1bfb` |
| `chgis/CHGIS_data_dictionary.zip` | 47,149 | `77592074e1de4d082ab2e0141a3337598cac13fdaed30ef8409368ac7b52e505` |
| `chgis/README_DATA_DICTIONARY.txt` | 960 | `629b6562c4781729a0f279a59011c3fcdf9643363517f8529d9bd40d701d0d68` |
| `chgis/api/dataset_FDLFJ3_EULA.json` | 6,886 | `b626d6d6f915c503ae671ed2d3db834f74f9b0d2d4fd61cd8e162ccd96b4afc8` |
| `chgis/api/dataset_I0Q7SM_pref_pgn.json` | 11,002 | `ac2ee662b97f23e9778bb10490347c0e8d321f00bbcf51361bbe93ceec215554` |
| `chgis/api/dataset_Q9VOF5_cnty_pts.json` | 7,234 | `ac45d9cdfa5e1d91c464551095a9046742eeab6c4ac04f651714c247b4698af5` |
| `chgis/api/dataset_WW1PD6_pref_pts.json` | 9,640 | `ca25f596b996c6639fad685b5c226ac0116055bfd5ed5099f789b6978ff9fbda` |
| `chgis/api/dataverse_chgis_v6_contents.json` | 1,974 | `c3e2464c232319a35c3bd6f97f802a2b33aacd5b9f9c56fd02ca761a567f5805` |
| `chgis/v6_time_cnty_pts_utf_wgs84.zip` | 544,703 | `3b431d2e587bcb738e632385703824d252e0b4744ddd726fc5eb10364dd2d8c5` |
| `chgis/v6_time_pref_pts_utf_wgs84.zip` | 288,343 | `48f6a50bcc3dd9cf4391efab2153f0e333f2040a08cf96c4d4b950cf9977d1fc` |
| `mcgd/MCGD_Data2026_08_25.csv.head-960rows.sample.csv` | 65,478 | `7d05bfa5e72b0fd7fcbe77ceb11b35f5a06b9525f1ffa3722a739bca1c4c4d85` |
| `mcgd/MCGD_Data2026_08_25.csv.range-0-65535.raw` | 65,536 | `114d4a0c2859e4790337ae520df264d9b72ea6047d0dc3d93456c1e1270ad39e` |
| `mcgd/zenodo_record_22094815.json` | 9,643 | `dfe597b4f11ac9319ba4b81a0cdb61ae3ec9005e330c2f574f3b8cbf35bf04f6` |
| `pleiades/datasets_docs/LICENSE_CC-BY-3.0.txt` | 19,467 | `e6bc9e9c474700b708f568bac9e5a8a9bcb2b1dad53442f5ba449fcb848b8e76` |
| `pleiades/datasets_docs/README.md` | 14,395 | `5dde1ee9473e22c6768e53b144c104cbcb8a57c3450139eeb06fd51e0c1a851d` |
| `pleiades/datasets_docs/gis_README.md` | 18,514 | `8a2de1089d80e0ac2f6d502bf30555881cc758de20ddcaafaec7a2917fc3b023` |
| `pleiades/gis_vocab/archaeological_remains.csv` | 621 | `7573bb7847ddf82f56635940dbae15ebba84e67a14cbb1a0ea0f7af576f5ce04` |
| `pleiades/gis_vocab/association_certainty.csv` | 700 | `20f155e0e0a1f2d053547106dc6cf2c8420d915db211521b4e139a87800f8d59` |
| `pleiades/gis_vocab/name_types.csv` | 1,212 | `5b057900e8c4bcf3790b4924ac1c79fa98f810878d603cdef8a94db880fc9e87` |
| `pleiades/gis_vocab/place_types.csv` | 58,785 | `de1da9bc69f1276d4d7d91131b08de1b564710a05f4fdee44a5108c7d7f9d88a` |
| `pleiades/gis_vocab/transcription_accuracy.csv` | 657 | `8a00f9bda4c00a7ed3645136b7450801223d20d71a5a9e16775240a4318e6b4f` |
| `pleiades/gis_vocab/transcription_completeness.csv` | 817 | `b34a99f9d800066bbdafa803bcbe69b1c55cf7a5c92d45b2b3ae9a74eb25ee19` |
| `pleiades/places/423025.json` | 167,018 | `d602f3bc04b9241fe4516a9c1a46ee473946b3fd195f742e067a5cf613ea3fe4` |
| `pleiades/places/579885.json` | 91,658 | `4156a6fb8a276a1cdbb0e6bb38382b30632468a76f05dca485c985974a41dcb9` |
| `pleiades/places/893951.json` | 98,900 | `201b974c8e47b7bd53a21d8b3ca07625bfdbf769eb598c88d87a54e656c8fe1f` |
| `pleiades/places/912816.json` | 48,268 | `3bd3710258c54801480ec4fdfcd01cf1167fda165b52aa958216cd8ee195c865` |
| `whg/api/place/169687-169688.json` | 3,774 | `4f68eb7abbb5a13f608b68e5e4822dca5609cbcc0dddc7b4cb95484850ea122c` |
| `whg/api/place/169687.json` | 2,102 | `25d4ac5093989dfdefcc56c6e84cc578aa030e43843065e0317d817d9819e2ff` |
| `whg/api/place/gn_1790630_xian.json` | 3,956 | `62af3ae915c3210d4b2d07e2142aafb909ddd0dce95eca5968b0b1ecec8361fa` |
| `whg/api/place/gn_1816670_beijing.json` | 6,217 | `b68065036d038d2da4e48e99c6e86a6b204bf97802e899632ef10beb0035e584` |
| `whg/api/place/gn_3169070_roma.json` | 4,220 | `4d13f8a36618b9dcb5c23fab9e01a05aebae9ddf68e1a5cd1ac0d90641a25478` |
| `whg/api/place/gn_98182_baghdad.json` | 3,939 | `99af0c93090372c7d386e1306edbc428e54ea8ce5b583ea5619bc11d58f33790` |
| `whg/api/place/tgn_7011781_london.json` | 3,360 | `5e5e63729d23fe83fe7b8b451bd0ebcf8842a20da1a1019b49df402b11d8b4a4` |
| `whg/api/sources.json` | 12,316 | `ad90746795ab1e44142c601b53fd98b36ae9838680b9a4995838a1e3f65ad50d` |
| `whg/whg_apis_docs.html` | 269,532 | `b38258e722c3660e11322bd03b4b360273f8039d83f9c086d3ed808310f2a901` |

同目录另有 6 个 P0 报告/映射文件（91,113 B，同为回收站内）：

| 文件 | 字节 |
|---|---:|
| `README.md` | 15,927 |
| `DATA_SOURCE_MATRIX.md` | 21,998 |
| `SAMPLE_RECONCILIATION.md` | 14,176 |
| `LICENSE_REVIEW.md` | 13,774 |
| `IMPORT_RECOMMENDATION.md` | 11,507 |
| `FIELD_MAPPING.csv` | 13,731 |

> 上述 37 + 6 = 43 个文件合计 **1,993,224 B**。凡在 `MANIFEST.tsv` 中登记的文件，SHA256 与记录值逐条一致。

Pleiades 切片（6 个文件，3,731,163 B；现位于回收站 `$RXROG9G/WB-002/sample_data_pleiades/`）：

| 文件 | 字节 | SHA256 |
|---|---:|---|
| `FETCH_LOG.tsv` | 1,699 | `0d0fb62eedd575cc4018de079caadf2270aabd4ea076d00e35187ccd7bb17c46` |
| `places.csv.range-0-1048575` | 1,048,576 | `a1dbb2f89b3277cba7336a7f9ff0c735a5f4f506089186a10aa1c40216b90256` |
| `names.csv.range-0-1048575` | 1,048,576 | `340f065bb56356ff67715d399a8407f8174e18c1fcf8df9099a28613d7503506` |
| `location_points.csv.range-0-1048575` | 1,048,576 | `6fe69afd7f4be951febbf0d3708b57b219782d037a99a486c56bcacecb571d37` |
| `connections.csv.range-0-524287` | 524,288 | `8260065124005cda80bea04b113436ec33b8cdbe82d8353c7d8b26037b4d31ba` |
| `time_periods.csv.range-0-999999` | 40,909 | `d1395f5f020f02de1deca003258c195227d69eb295e55044bc20bc82219da119` |

> 每个切片文件的 SHA256 与 `FETCH_LOG.tsv` 记录值一致；归一化程序运行前后对 21 个输入文件的复算结果也一致（`run_manifest.json → input_integrity.verified = true`）。

### 3.2 七张暂存 CSV（`code/data/staging/`，与 P0 `normalized/` 逐字节相同）

| 文件 | 字节 | 数据行 | SHA256 |
|---|---:|---:|---|
| `historical_places.csv` | 4,953,976 | 19,039 | `86db3ce6b94f9e31036a3785a55510d48eb43bd4ce998aaa5cad2f59b068533f` |
| `historical_place_names.csv` | 8,937,942 | 47,503 | `80674c0ded553241c6f4745db0d6957d4dd6617acdfa7918d503128c1690ebbd` |
| `historical_place_locations.csv` | 11,698,567 | 18,103 | `9e987ba578e933ed9bdb11564487125783b22623abf348b9201a74d562d637a2` |
| `source_records.csv` | 26,942,777 | 29,391 | `30fed0e40ba124960ba008b030948394398a418a9cc58b333095614469771c5d` |
| `candidate_matches.csv` | 17,315,204 | 53,137 | `4e29c2ec64ebe263c325bab5f0eb70dc922116dd737542cf234373d86c98ab12` |
| `data_quality_issues.csv` | 5,277,273 | 12,631 | `7a8ab3916e00dcb04308d89c816c7c8771c6f71ec598ee3e4188c6b643263602` |
| `data_datasets.csv` | 6,018 | 7 | `fa44197e54b4da4a8af78b589d10a63a668184397f63dbdf842b5051a2ef636f` |

P0 目录另有 `run_manifest.json`（18,488 B，`4000bce6036726eb070907ccd61a5741bf57ee6fee51c65b84a94741064050b3`）与 `stats.json`（215,232 B，`7e9fae44aa23bfe2e7a02fc53dbdd01f9cf680868459c3e12d7bb41c6741a4c9`）。

### 3.3 八份问题清单（现位于回收站 `$RXROG9G/WB-002/issues/`）

| 文件 | 字节 | 行数 | 内容 | SHA256 |
|---|---:|---:|---|---|
| `chgis_all_records.csv` | 4,539,937 | 15,748 | CHGIS 全量记录（含原始字段 + 派生年/坐标） | `d25d6dea601243c0263f0ebdc357753bea61d0f953fac80023f14e6ddc32dc3f` |
| `cluster_members.csv` | 2,133,219 | 15,738 | 坐标簇成员（同一坐标上的记录） | `08de8e2ffc5f81e1d95d5a95e64489ed2a98e84d0a2da0456e4e128feaa15421` |
| `coordinate_clusters.csv` | 713,834 | 6,013 | 坐标簇汇总（6,013 个不同坐标） | `de6ea57090ba091e2c804f23cc2a41e1932fd47859f29ccf5fc58194eb57021e` |
| `cross_layer_disagreements.csv` | 2,452 | 29 | 府/县两层同名同年段不同坐标 | `aa213a5b93a58911b7fb11ed712269d5c7dccf19c1653244b20371d5ff0bc548` |
| `homonyms.csv` | 151,959 | 2,071 | 同名异地（2,071 个名称对应 ≥2 坐标） | `620289a2a53be1754367a2a4cc81a8c084ad0f316f228d80648b18cd65c1ab9d` |
| `migration_chains.csv` | 322,823 | 1,254 | 迁治候选链（1,254 条） | `f4a2e54bced69f564dac9b8baa88509fbd4002863f6f1b4ae15d5558e8a9ecba` |
| `migration_review_queue.csv` | 495,033 | 1,866 | 迁治待审队列（1,866 条腿，按优先级） | `5b642ef3eb5ac6d3be5e004b70fe300ad2b8066aa69975b8a53d767b33a569bc` |
| `time_inversions.csv` | 3,544 | 28 | 时间倒挂明细（BEG_YR > END_YR） | `75433d1239459721c2965cb38cdd8921f94ac862b1e38787f5ab3a4d83af8f9c` |

### 3.4 处理脚本（23 个；现位于回收站 `$RCJY9IU/`）

| 目录 | 文件（字节） |
|---|---|
| `wb-002-normalize/` | `run_all.py` 26,321 · `normalize.py` 102,275 · `chgis_extract.py` 16,253 · `chgis_migration.py` 32,810 · `mcgd_extract.py` 6,781 · `pleiades_extract.py` 23,361 · `whg_extract.py` 24,412 · `quality_checks.py` 32,927 · `report_stats.py` 30,736 · `time_semantics.py` 11,414 · `datasets.py` 13,847 · `dbf_reader.py` 10,172 · `xlsx_reader.py` 6,145 · `csv_io.py` 2,655 · `extra_record.py` 8,307 · `README.md` 54,425 |
| `wb-002-tools/` | `fetch_samples.sh` 9,080 · `r2_fetch_pleiades_gis.sh` 2,580 · `verify_wb002.py` 10,691 · `r2_verify_pleiades_fields.py` 14,383 · `r2_verify_whg_mcgd_chgis.py` 16,089 · `r2_build_field_mapping.py` 52,420 · `derive_mcgd_sample.py` 3,141 |

> 抓取脚本两个：`fetch_samples.sh`（四源小样本，逐条写 MANIFEST/PROBES）、`r2_fetch_pleiades_gis.sh`（Pleiades 5 个 CSV 的 Range 切片，写 FETCH_LOG）。
> 检查脚本三个：`verify_wb002.py`（源级复核）、`r2_verify_pleiades_fields.py`（GIS 字段/轴序）、`r2_verify_whg_mcgd_chgis.py`（WHG 两套 schema / MCGD 坐标 / CHGIS 字段）。

## 4. 已处理数据数量

### 4.1 记录级（`source_records.csv` / `source_record` 29,391 行）

| 数据集 | 源记录行 | 地点 | 名称 | 位置 |
|---|---:|---:|---:|---:|
| `chgis_v6_county_points` | 10,522 | 10,522 | 31,187 | 10,522 |
| `chgis_v6_prefecture_points` | 5,226 | 5,224 | 13,055 | 5,224 |
| `pleiades_gis_4_1_slice` | 12,445 | 2,643 | 2,074 | 1,704 |
| `mcgd_zenodo_22094815_head960` | 960 | 643 | 960 | 643 |
| `whg_geoname_s_gn_sample` | 209 | 4 | 201 | 4 |
| `whg_getty_tgn_sample` | 21 | 1 | 19 | 1 |
| `whg_hgis_de_las_indias_sample` | 8 | 2 | 3 | 3 |
| **合计** | **29,391** | **19,039** | **47,499（入库）** | **18,101（入库）** |

> 暂存为 47,503 条名称 / 18,103 条位置；导入隔离 4 条名称 + 2 条位置（对应 3 条失效来源记录：府级 2 + Pleiades 1），故入库数少 4 / 2。

### 4.2 数据库实际行数（正式库 `canvas_history`，只读核对）

```
data_source 5 / data_dataset 8（7 导入 + manual_entry） / import_batch 7
source_record 29,391（active 29,388 / 隔离 3）
historical_place 19,039 / historical_place_name 47,499 / historical_place_location 18,101
candidate_match 53,131 / data_quality_issue 12,831
event / person / event_place / event_person / person_place = 0
Flyway 版本 = 5（V1–V5）
```

- 名称/位置的来源追溯覆盖率：**47,499 / 47,499、18,101 / 18,101（100%）**；
- `historical_place_location` 坐标：`EPSG:4326` 17,455 条、`unknown` **646** 条；`geom IS NULL` 10 条；
- `candidate_match`：`candidate` 50,875 / `needs_manual_review` 1,866 / `confirmed` 390（全部为 Pleiades 源声明连线，`reviewer=system:source_attested`）/ `rejected` 0；
- `historical_place`：`staging` 19,039、`merged` **0**（未发生任何合并）。

### 4.3 覆盖率（相对各源全量）

| 源 | 全量 | 已处理 | 覆盖率 |
|---|---:|---:|---:|
| Pleiades place | 41,480 | 2,643 | **6.4%** |
| CHGIS 时间点层（2 层） | 5,226 + 10,522 | 15,748 条 | **该两层 100%**（其余 31 层 0） |
| MCGD | 472,749 | 960 | **0.20%** |
| WHG | 28 个命名空间（千万级） | 7 条 | 抽样级 |

### 4.4 未完成的数据下载与处理任务（清单）

| # | 任务 | 类型 | 体量 / 规模 | 现状 |
|---|---|---|---|---|
| 1 | 恢复 P0 原始样本（`设计资料/P0验证`） | 本地恢复 | 43 文件 / 1.90 MB | 仅在回收站 |
| 2 | 恢复 8 份问题清单 + P0 报告（`P0收敛/WB-002/issues` 等） | 本地恢复 | 8 CSV / 8.0 MB + 6 报告 | 仅在回收站 |
| 3 | 恢复归一化与抓取脚本（`code/p0`） | 本地恢复 | 23 脚本 | 仅在回收站 |
| 4 | Pleiades GIS 4.1 完整 CSV（4 个） | 下载 | **38,933,260 B** | 只有切片 |
| 5 | Pleiades 缺失文件（面/线/精度/词表 7 个） | 下载 | 未测量 | 完全缺失 |
| 6 | CHGIS `v6_time_pref_pgn` | 下载 | **31,098,173 B** | 完全缺失 |
| 7 | CHGIS 1820 / 1911 点层（省/府/县/镇） | 下载 + 归一化 | 未测量（约 8–10 个 zip） | 完全缺失 |
| 8 | CHGIS 明代驿路 / 驿站 / 茶马古道 / 1990 census | 下载 + 归一化 | 未测量 | 完全缺失 |
| 9 | MCGD 全量主文件 | 下载 | **31,953,904 B** | 只有 64 KiB / 960 行 |
| 10 | WHG 定向补充（1–2 个不重叠命名空间） | 下载 | 单条 JSON，按 ID 取 | 只有 7 条 |
| 11 | Pleiades 4,810 条孤儿子记录挂接 | 处理 | 4,810 条 | 等完整包 |
| 12 | 28 条时间倒挂裁决 | 人工 | 28 条 | 未开始 |
| 13 | 646 条未知 CRS 裁决 | 人工 | 646 条 | 未开始 |
| 14 | 337 条缺坐标裁决 | 人工 | 337 条 | 未开始 |
| 15 | 1,866 条迁治候选复核 | 人工 | 1,866 条 | 未开始 |
| 16 | 2,071 条同名异地消歧 | 人工 | 2,071 条 | 未开始 |
| 17 | 29 对跨层矛盾裁决 | 人工 | 29 对 | 未开始 |
| 18 | 数据集 `content_sha256` / `local_path` / WHG 版本补全 | 代码 + 回填 | 8 个数据集 | 未开始 |
| 19 | 许可残留清理（代码 2 处 + 文档 1 处 + CSV 4 列 + 脚本 1 个） | 代码/文档 | 见问题 5 | 未开始 |

### 4.5 应用与本地化状态

| 项 | 事实 |
|---|---|
| 数据来源 | 前端/后端全部读本机 PostgreSQL；检索、详情、bbox、时间轴、矩阵均无外部数据请求 |
| 正式库业务数据 | `event / person / event_place / event_person / person_place = 0`；地图上只有 19,039 个历史地点，没有事件与人物 |
| 测试库 | 另有 M2/M3 的测试与演示数据（16 事件 / 8 政权 / 12 关联、若干人物地点），与本轮数据资产无关 |
| 唯一外部运行时依赖 | 底图瓦片 `api.maptiler.com`（`frontend/src/map/basemaps.ts:25`），不属于历史数据；断网时降级为离线底色，数据能力不受影响 |
| 服务状态（核查时） | 5180（正式库只读）/ 5181（测试库可写）前端在线；8088 / 8089 API 在线；数据库容器 `canvas-history-db` 在线 |

## 5. 数据库模型现状（M1/M2/M3 之后）

- 15 张业务表（另 `flyway_schema_history`、PostGIS `spatial_ref_sys`）+ 3 个项目视图（`v_place_evidence` / `v_place_liveness` / `v_place_time_span`；另有 PostGIS 自带 2 个视图）。
- 核心链路：`data_source`(6 列) → `data_dataset`(17 列) → `source_record`(17 列) → `historical_place`(20 列) / `historical_place_name`(22 列) / `historical_place_location`(33 列) → `candidate_match`(16 列) / `data_quality_issue`(20 列) / `import_batch`(19 列)。
- 地点/名称/位置**三表独立**；名称与位置都带 `source_record_id` 外键与独立 `record_status`、`locked`、`manual_edited_fields`、`created_by`。
- 时间只落在名称与位置行上；地点级时间由视图 `v_place_time_span`（19,039 行）现算，不落列。
- `data_source` 只有 `source_id / display_name / homepage_url / display_priority / notes / created_at` 6 列；`data_dataset` **无任何许可列**。
- M2/M3 追加了 `person*` / `event*` / `historical_polity`（仅测试库），与本轮数据资产无关。

## 6. 现有流水线实际能力（9 项逐条核查）

### 6.0 程序结构（23 个文件，纯标准库）

| 层 | 文件 | 职责 |
|---|---|---|
| 编排 | `run_all.py` | 读 21 个输入 → 调四源 extract → `normalize.build_bundle()` → 写 7 张表 + 8 份清单 + `stats.json` / `run_manifest.json`；`--timestamp` 固定可复现；输入哈希前后比对 |
| 抽取 | `chgis_extract.py` / `mcgd_extract.py` / `pleiades_extract.py` / `whg_extract.py` | 各源字段解析、切片尾行丢弃、父缺失标记 |
| 读取器 | `dbf_reader.py` / `xlsx_reader.py` / `csv_io.py` | 手写 DBF / XLSX / CSV（BOM + CRLF）读写，无第三方依赖 |
| 语义 | `time_semantics.py` / `chgis_migration.py` | 天文纪年与 `time_bound_type` 七值映射；迁治链识别与队列排序 |
| 归一 | `normalize.py` / `datasets.py` / `extra_record.py` | 三表构建、数据集登记、候选匹配（只产候选，不合并） |
| 质量 | `quality_checks.py` / `report_stats.py` | 14 类问题检测、统计口径与断言 |
| 核验 | `verify_wb002.py` / `r2_verify_*` | 独立复核原始字段与抓取完整性 |

> 全部 import 只有 `argparse, csv, dataclasses, datetime, hashlib, json, math, platform, struct, sys, time, traceback, xml.etree.ElementTree, zipfile`；无 pyproj、无 pandas、无网络。

### 6.1 九项核查

| # | 核查项 | 结论 | 证据 |
|---|---|---|---|
| 1 | 归一化程序能否重复执行 | **代码本身可以，当前环境不可以** | 固定 `--timestamp` 连跑两次，16 个数据产物 md5 全同（`run_manifest.json`）；但脚本在回收站、输入路径 `设计资料/P0验证/...` 已不存在 → 现在无法就地复跑 |
| 2 | 原始数据是否只读 | **是（进程级）** | 21 个输入文件运行前后 SHA256 一致并写入 `input_integrity`；脚本只读打开。**注意：文件系统权限仍是 `-rw-r--r--`，不是只读挂载** |
| 3 | 输出能否逐条追溯到原始记录 | **是** | 29,391 条 `source_record` 带 `raw_file / raw_record_index / raw_payload / content_hash`；名称与位置 100% 有 `source_record_id` |
| 4 | 坐标转换是否有明确依据 | **是（且未做任何重投影）** | CHGIS `.prj` 原文 `GCS_WGS_1984` → `confirmed`；Pleiades 官方 WGS84 → `confirmed`；MCGD 643 条 + WHG 旧扁平 3 条无声明 → `unknown`（合计 646）；全部只记录 `original_crs / crs_confidence / axis_order_verified`，无 pyproj |
| 5 | 天文纪年转换是否正确 | **是** | `astro = year + 1 (year < 0)`；5 条断言每次运行都跑；抽查：CHGIS `雁门郡` `BEG_YR=-221` → `-220`，共 474 条 `-220` 名称 |
| 6 | 时间边界语义是否完整保留 | **是** | 7 值域 `exact / bounded / exact_or_bounded / tpq_taq / derived_tpq_taq / snapshot / unknown`。入库名称：`exact` 21,610、`unknown` 20,535、`exact_or_bounded` 2,360、`tpq_taq` 1,774、`bounded` 1,164、`snapshot` 56；入库位置：`exact` 8,055、`unknown` 7,656、`tpq_taq` 1,159、`exact_or_bounded` 812、`bounded` 398、`snapshot` 21。倒挂 28 条不交换、不夹取 |
| 7 | 候选匹配是否存在误合并 | **否（零合并）** | `candidate_match` 只有候选与待审，`historical_place.merged_into_place_id` 全为 NULL；390 条 `confirmed` 是 Pleiades 源声明连线（`source_asserted`），不是合并；2 条自指候选被排除并留痕 |
| 8 | 人工修改保护是否有效 | **是（机制经真实导入路径验证）** | `created_by='manual' / locked / manual_edited_fields` 三种保护位都会让该行 `blocked` 并登记 `manual_edit_conflict`；R1.2 实测 19,039 = 0 + 0 + 19,036 + 3，三条夹具（locked / 字段级 / 人工创建）现值未被覆盖 |
| 9 | 新批次重复导入是否幂等 | **是** | 同一导入器连跑 4 次：六表 Δ=0、A1 新增=0（七批全部）、`source_record` 29,391 不变；失败注入时整批回滚（EXIT 3，九表前后 0） |

> `derived_tpq_taq` 只出现在 P0 的地点级统计里；入库后 `historical_place` 没有时间列，地点级跨度由视图 `v_place_time_span` 现算，因此数据库实际只出现 6 个值（名称与位置各 6 个）。

## 7. 追溯链的现状与断点

| 环节 | 现状 | 断点 |
|---|---|---|
| 来源 → 数据集 | `data_source` 5 行、`data_dataset` 8 行 | `whg_*` 三个数据集 `dataset_version` 为 **NULL** |
| 数据集 → 原始文件 | `data_dataset.local_path` 有值 | 值指向 `设计资料/P0验证/WB-002/sample_data/...`，**该目录已被删除**（仅 `manual_entry` 无路径，属正常） |
| 原始文件 → 记录 | `source_record.raw_file/raw_record_index/raw_payload` | 文件名仍在，但文件本体在回收站 |
| 批次 → 记录 | `import_batch` 7 批 + `inserted_source_record_ids` | 正常 |
| 数据集内容指纹 | `data_dataset.content_sha256` **全部 NULL** | 导入器明确留空（说明见 `notes`），只有批次级 `input_sha256` |

## 8. 已知数据质量问题（入库后 12,831 条台账）

| issue_type | 条数 | 严重度 | 处置 |
|---|---:|---|---|
| `unknown_time_bound_type` | 6,448 | info | 保留并标记 |
| `parent_place_not_in_sample` | 4,810 | info | 保留（Pleiades 切片边界效应） |
| `unknown_crs` | 646 | warning（P0 报告称「发布阻塞」） | 需人工裁决（MCGD 643 + WHG 旧扁平 3） |
| `beg_eq_end` | 341 | info | 保留（多为单年记录） |
| `missing_coordinate` | 337 | blocking | 保留并标记（DBF 溢出 10 + Pleiades 327） |
| `derived_value_mismatch` | 197（130 地点） | warning | 导入器合成，可解释 |
| `beg_gt_end` | 28 | blocking | 保留原值、派生列留空 |
| `coordinate_outside_china_bbox` | 6 | warning | 保留（源数据 `NA`） |
| `duplicate_external_id` | 5 | warning | 隔离并留痕 |
| `truncated_slice_tail` | 4 | info | 丢弃尾行 |
| `year_out_of_range` | 4 | warning | 保留并标记 |
| `duplicate_sysid` | 2 | warning | 隔离 |
| `nonstandard_field_name` | 2 | info | 保留原始列名 |
| `coordinate_out_of_range` | 1 | warning | 保留并标记 |
| **合计** | **12,831** | info 11,605 / warning 860 / blocking 366 | `preserved_and_flagged` 12,173 / `needs_manual_review` 654 / `discarded` 4 |

尚未裁决的高优先级项：**28 条时间倒挂、646 条 CRS 未知、337 条缺坐标、1,866 条迁治候选、2,071 条同名异地（24.94%）、29 对跨层矛盾**。

---

# 第二部分　问题

## 问题 1（最高优先级）：P0 数据资产已离开项目目录

- **事实**：`设计资料/P0验证`、`设计资料/P0收敛`（含 8 份问题清单与 6 份报告）、`code/p0`（23 个脚本）于 2026-11-03 12:14 被移入回收站；项目目录只剩 `normalized/` 的 7 张 CSV。
- **影响**：① 无法复跑归一化；② 8 份问题清单无法交付/复核；③ 数据库 `local_path` 全部悬空；④ 回收站一旦清空，P0 的原始证据与程序**不可恢复**（不在 Git、不在备份）。
- **判断依据**：`$I4BI1K6` / `$IXROG9G` / `$ICJY9IU` 三个 `$I` 元数据文件记录的原始路径与删除时间；当前目录 `ls` 结果。

## 问题 2：数据覆盖严重不足，且容易被误当成「已导入完成」

- Pleiades 只有 6.4%（切片），且缺 polygons / linestrings，几何覆盖先天不完整；
- MCGD 只有 0.20%（960 / 472,749），无法做质量体检；
- CHGIS 只做了 2 / 33 个图层，缺府级面与 1820/1911 系列；
- WHG 只有 7 条，且 2 条旧扁平记录无 `attribution`。
- **风险**：在这批数据上做「历史时空画布」的内容判断，会把抽样偏差当成历史分布（例如地中海只有罗马—雅典—两河三框）。

## 问题 3：质量待裁决项规模大，且全部处于「保留并标记」状态

台账里 366 条 `blocking`（`missing_coordinate` 337 + `beg_gt_end` 28 + `coordinate_out_of_range` 1）全部没有裁决；另有 646 条 `unknown_crs` 虽记为 `warning`，但 P0 报告把它列为「发布阻塞」——坐标基准未知会让位置偏几百米。337 条缺坐标无法上图；28 条倒挂的时间不可用于筛选；1,866 条迁治候选如果被当作结论会制造虚假的行政沿革。

## 问题 4：追溯链三处断点

`local_path` 悬空、`content_sha256` 全空、WHG 三个数据集 `dataset_version` 为空——与 Owner「保留来源、数据集、版本、原始记录、导入批次追溯」的要求只完成了一半。

## 问题 5：与最新 Owner 决策不一致的字段、逻辑、文档（具体位置）

先给决策对齐矩阵（逐条对应本轮核查）：

| Owner 决策 | 现状 | 判定 |
|---|---|---|
| 不增加新的外部数据源 | `data_source` 的 CHECK 只允许 `chgis / pleiades / whg / mcgd / manual`；代码中无新源接入 | **一致** |
| 优先处理现有 Pleiades / WHG / CHGIS / MCGD | 现有 7 个数据集全部来自这四源 | **一致**（但覆盖极低，见问题 2） |
| 尽量本地化 | 历史数据全部在本机 PostgreSQL；前端运行时只有底图瓦片走 MapTiler | **基本一致**（底图是否离线另议） |
| 数据授权由 Owner 负责 | 代码不做授权判断（除下述 2 处残留） | **基本一致** |
| 删除许可门禁、许可检查和相关字段 | 数据库已无许可列；但导入器仍按许可剔除 2 行、暂存 CSV 仍有 4 列、仍有 1 个许可审计脚本 | **不一致（4 处）** |
| 保留来源/数据集/版本/原始记录/导入批次追溯 | 五类实体齐全；但 `content_sha256` 全空、WHG 版本为空、`local_path` 悬空 | **部分一致** |
| 地点、名称、位置保持独立 | 三张独立表，名称/位置各有自己的状态与保护位 | **一致** |
| 禁止同名自动合并 | `merged_into_place_id` 全 NULL；同名只产候选 | **一致** |
| 禁止自动覆盖人工修改 | 三种保护位在真实导入路径上生效（R1.2 实测） | **一致** |

具体冲突位置：

| # | 位置 | 现状 | 与决策的冲突 | 建议 |
|---|---|---|---|---|
| 1 | `code/ops/import_staging.py:441-452` | `dropped_licence` 按 `issue_type='licence_unconfirmed'` **剔除 2 行台账** | 决策：删除许可检查；这是唯一按许可处置数据的代码路径 | 改为不剔除、按普通台账入库（或按新口径重新归类） |
| 2 | `code/ops/verify_import.py:52,181,202,720-753` | 硬编码 `LEDGER_DROPPED = 2`，并断言 `licence_unconfirmed = 0`、类型数 = 暂存类型 − 1 + 2 | 同上，校验逻辑把「许可剔除」当成正确基线 | 改基线为 12,631 + 200（不剔除）并删掉 licence 断言 |
| 3 | `code/ops/IMPORT_VALIDATION_RULES.md:29-38` | 明文要求「2 行 licence_unconfirmed 直接剔除」 | 决策：不做许可判断 | 改写为「不按许可处置」，保留历史说明但标注已废止 |
| 4 | `code/data/staging/data_datasets.csv`（表头第 5–8 列） | 仍有 `license_id / license_url / redistributable / attribution_text`，值为 `no` / `yes_with_attribution` / `unconfirmed` | 决策：删除许可相关字段 | 从暂存 CSV 删除这 4 列（导入器本就不读，删除不影响入库） |
| 5 | `code/ops/verify_no_licence_gate.py`（全文）+ `code/ops/README.md:9,46` | 许可门禁不存在性审计脚本与说明 | 决策：删除许可检查；该脚本本身是许可检查工具 | 归档到历史目录或删除；README 同步 |
| 6 | `设计资料/V2.1.1_正式交付/CORE_DATA_MODEL_V2.1.1.md:864` | 写明「2 行 licence_unconfirmed 按 Owner 决策 3 直接删除」 | 新决策已推翻该处置 | 文档加「已被 M4 Owner 决策取代」标注（留痕不删） |
| 7 | `code/ops/reports/STAGE3_ACCEPTANCE.md:58`、`ops/reports/r1_2/*` | 验收行含「licence 0」 | 属历史证据，不应改写 | 保留，但在 M4 报告中注明口径已变更 |

> 与之**一致**、无需改动的：`data_source` / `data_dataset` 表结构（无许可列）、`CORE_DATA_MODEL_V2.1.1` §5.1/§5.2 的删列决定、`IMPORT_RULES_V2.1.1` R-11、`DATA_PROVENANCE_V2.1.1` 的「不处理授权/再分发」声明。

## 问题 6：流水线无法自证可重复（环境层面）

脚本与输入都在回收站，`run_all.py` 的输入/输出路径写死为 `设计资料/P0验证/...` 与 `设计资料/P0收敛/...`；`code/data/staging` 是产物副本，不是可重跑的输入。**当前状态下任何人都无法复现 P0 的 16 个产物。**

## 问题 7：切片造成的结构性缺口

Pleiades 4,810 条子记录（名称 2,505 / 点位 756 / 连线 1,549）因父地点不在 1 MB 窗口内无法入库。这不是数据缺陷，但只要不换完整包，这 4,810 条会永久停在 `source_record` 里，无法形成名称/位置/边。

## 问题 8：许可口径变更会让既有验收基线失效（实施风险）

`ops/reports/STAGE3_ACCEPTANCE.md`、`r1_2/07_verify_import.log` 等历史证据里的「台账 12,831 / licence 0」是**按旧口径**成立的。
一旦按 M4 决策停止许可剔除，台账总数会从 12,831 变成 **12,833**（= 暂存 12,631 全量 + `duplicate_external_id` 5 + `derived_value_mismatch` 197），
`verify_import.py` 的 `LEDGER_DROPPED = 2` 与「licence = 0」断言会失败。**必须在 M4-2 同轮更新基线与验收证据，不能只改代码不改验收。**

---

# 第三部分　建议

## 建议的下一步实施顺序（M4-1 起，逐轮可验收）

| 轮次 | 内容 | 入口条件 | 完成判据 |
|---|---|---|---|
| **M4-1** | **资产复位与基线**：把回收站中的 `设计资料/P0验证`、`P0收敛`（`issues` + `sample_data_pleiades` + P0 报告）、`code/p0` 恢复到项目目录（非回收站路径）；恢复后逐文件复算 SHA256，与 §3 表核对；把「文件清单 + 哈希」这份小体积清单纳入 Git | Owner 批准文件系统写入 | 43 + 6 + 8 + 23 个文件哈希全部命中；`run_all.py` 能在不改代码的情况下复跑出 16 个同 md5 产物 |
| **M4-2** | **许可残留清理**：按问题 5 表逐项处理（代码 2 处、文档 1 处、暂存 CSV 4 列、审计脚本 1 个、设计留痕 1 处） | M4-1 完成（需能重跑导入验证） | 全库 `grep -i licen` 仅剩「已删除/留痕」说明；台账恢复为 12,833（不再剔除）；`verify_import.py` 新基线通过 |
| **M4-3** | **Pleiades 完整 GIS 4.1**：下载 7 个缺失文件 + 4 个完整 CSV（这 5 个 CSV 约 38.9 MB），新建数据集 `pleiades_gis_4_1`（不覆盖现有 `_slice`），重跑归一化 → 候选表 | Owner 批准下载；M4-1 完成 | 41,480 place 全部入库；polygons/linestrings 有独立记录；4,810 孤儿子记录归零 |
| **M4-4** | **CHGIS 补层**：`v6_time_pref_pgn`（31.1 MB）+ 1820 / 1911 点层；仍只用 `wgs84` 版本 | M4-3 完成或并行（独立数据集） | 面几何与 1820/1911 点可查询；不与现有点层重复建 place |
| **M4-5** | **MCGD 全量**：下载 31,953,904 B 主文件，先做质量体检（Code 分布、坐标缺失、CRS 抽样），再决定是否只导 `W/WW/P` 别名 | Owner 批准下载 | 体检报告 + 明确导入子集；不整表灌入 |
| **M4-6** | **质量裁决**：先处理 366 条 blocking（337 缺坐标、28 时间倒挂、1 坐标越界），再处理 646 条 CRS 未知，最后处理人工队列（1,866 迁治、2,071 同名、29 跨层） | M4-3/4/5 至少一项完成 | 每条 blocking 有结论（修/弃/降级），台账 `resolved` 可追踪 |
| **M4-7** | **追溯补全**：为每个数据集补 `content_sha256`（按数据集切分的原始文件哈希）、WHG `dataset_version`（抓取日期或 sources.json 版本）、修正 `local_path` | M4-1/3 完成 | 8/8 数据集三字段非空且可解析到真实文件 |
| **M4-8** | **本地化验收**：确认全部历史数据来自本地 PG、无运行时外部数据请求；底图瓦片是否离线另行决策 | M4-3~7 完成 | 断网（除底图）后检索/详情/矩阵/地图标记仍可用 |

> 不建议的顺序：先做 WHG 聚合（token 与许可双重阻塞）、先做 CHGIS 面（31 MB 且对本项目「点」的价值低于点位）、先做同名消歧（没有完整 Pleiades 就没有对照基准）。

## 需要 Owner 明确批准的事项

1. **从回收站恢复 P0 资产**（3 个目录，合计约 234 MB）。这是文件系统写入，且回收站可被清空——**建议列为 M4-1 第一优先**。
2. **下载 Pleiades GIS 4.1 完整包**：4 个完整 CSV（约 38.9 MB）+ 7 个缺失文件（面/线/精度/词表）。当前只有 6.3%–18.7% 的切片覆盖。
3. **下载 CHGIS `v6_time_pref_pgn`**（31,098,173 B）及 1820 / 1911 点层（体量待查）。
4. **下载 MCGD 全量** `MCGD_Data2026_08_25.csv`（31,953,904 B，md5 `48b9c064…`）。
5. **确认 CHGIS 使用边界**：仅本地学术使用、不再分发；若未来要公开，需另行取得书面许可。
6. **确认许可字段清理口径**：是否同意按问题 5 表删除暂存 4 列、移除 `licence_unconfirmed` 剔除逻辑、归档 `verify_no_licence_gate.py`（会改变 `verify_import.py` 的既有基线）。
7. **确认「未知 CRS 646 条」的处置**：暂不上图（保留可查）还是接受偏差上图。
8. **确认 MCGD 的导入范围**：只做转写别名（`Code in W,WW,P`）还是也做主地点。

## 本轮未做、也不建议现在做的事

- 未下载任何完整数据包；
- 未恢复任何文件（回收站内容仅读取）；
- 未修改数据库、未执行 Migration、未动正式环境；
- 未合并任何地点（`merged_into_place_id` 仍全为 NULL）；
- 未重新设计 P0 已完成的任何模块。

---

## 附：核查方法与可复核命令

```bash
# 资产位置与删除时间（只读）
find "$RECYCLE_BIN" -maxdepth 8 -name 'normalize.py'
python - <<'PY'   # 解析 $I 元数据：原始路径 + 删除时间
PY

# 文件指纹
find <dir> -type f | while read f; do stat -c %s "$f"; sha256sum "$f"; done

# 数据库现状（只读 SELECT）
docker exec canvas-history-db psql -U canvas_app -d canvas_history -c "\dt"

# 轨迹核对
docker exec canvas-history-db psql -U canvas_app -d canvas_history \
  -c "select dataset_id,count(*) from historical_place group by 1;"
```

> 本报告的所有数字均可由上述只读命令复算；未使用任何推测值。凡无法直接观测的，均在文中标注「未核实/待确认」。
