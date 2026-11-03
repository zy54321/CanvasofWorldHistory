# 暂存字段基线 STAGING_FIELD_BASELINE

> 版本：V2.1.1 准备性基线  
> 生成时间：2026-11-02 21:52:46  
> 生成脚本：`_build/qa_scripts/staging_field_inventory.py`  
> 数据来源（只读）：`P0收敛/WB-002/normalized/` 七张暂存 CSV  
> **本文件全部数字均为「①原始 CSV 逐行实算」层级**，未引用上游脚本产物或上游文档结论。

---

## 第一节 七张暂存 CSV 字段实测清单

### 1.0 文件级总览

| # | 暂存表 | 文件 | 字节数 | 数据行数 | 字段数 | 编码/BOM | 分隔符 | 行尾 | 嵌入换行单元格 | 不规则行 |
|---|--------|------|--------|----------|--------|---------|-------|------|----------------|----------|
| 1 | `data_datasets` | `data_datasets.csv` | 6,018 | **7** | 11 | UTF-8 BOM (EF BB BF) | 逗号 , | CRLF x8 | 0 | 0 |
| 2 | `source_records` | `source_records.csv` | 26,942,777 | **29,391** | 14 | UTF-8 BOM (EF BB BF) | 逗号 , | CRLF x280 | 0 | 0 |
| 3 | `historical_places` | `historical_places.csv` | 4,953,976 | **19,039** | 15 | UTF-8 BOM (EF BB BF) | 逗号 , | CRLF x1002 | 0 | 0 |
| 4 | `historical_place_names` | `historical_place_names.csv` | 8,937,942 | **47,503** | 13 | UTF-8 BOM (EF BB BF) | 逗号 , | CRLF x1472 | 0 | 0 |
| 5 | `historical_place_locations` | `historical_place_locations.csv` | 11,698,567 | **18,103** | 22 | UTF-8 BOM (EF BB BF) | 逗号 , | CRLF x372 | 0 | 0 |
| 6 | `candidate_matches` | `candidate_matches.csv` | 17,315,204 | **53,137** | 19 | UTF-8 BOM (EF BB BF) | 逗号 , | CRLF x721 | 0 | 0 |
| 7 | `data_quality_issues` | `data_quality_issues.csv` | 5,277,273 | **12,631** | 11 | UTF-8 BOM (EF BB BF) | 逗号 , | CRLF x691 | 0 | 0 |

**文件指纹（原始字节 SHA256）**

| 暂存表 | SHA256（完整） | SHA256 前 16 位 | mtime |
|--------|----------------|-----------------|-------|
| `data_datasets` | `fa44197e54b4da4a8af78b589d10a63a668184397f63dbdf842b5051a2ef636f` | `fa44197e54b4da4a` | 2026-11-02 12:23:26 |
| `source_records` | `30fed0e40ba124960ba008b030948394398a418a9cc58b333095614469771c5d` | `30fed0e40ba12496` | 2026-11-02 12:23:26 |
| `historical_places` | `86db3ce6b94f9e31036a3785a55510d48eb43bd4ce998aaa5cad2f59b068533f` | `86db3ce6b94f9e31` | 2026-11-02 12:23:25 |
| `historical_place_names` | `80674c0ded553241c6f4745db0d6957d4dd6617acdfa7918d503128c1690ebbd` | `80674c0ded553241` | 2026-11-02 12:23:25 |
| `historical_place_locations` | `9e987ba578e933ed9bdb11564487125783b22623abf348b9201a74d562d637a2` | `9e987ba578e933ed` | 2026-11-02 12:23:25 |
| `candidate_matches` | `4e29c2ec64ebe263c325bab5f0eb70dc922116dd737542cf234373d86c98ab12` | `4e29c2ec64ebe263` | 2026-11-02 12:23:26 |
| `data_quality_issues` | `7a8ab3916e00dcb04308d89c816c7c8771c6f71ec598ee3e4188c6b643263602` | `7a8ab3916e00dcb0` | 2026-11-02 12:23:26 |

### 1.1 数据行数 vs V0.2.2-r2 §0 权威数字对照

| 暂存表 | 实测行数（①逐行实算） | V0.2.2-r2 §0 权威数 | 差值 | 判定 |
|--------|----------------------|---------------------|------|------|
| `source_records` | 29,391 | 29,391 | +0 | 一致 |
| `historical_places` | 19,039 | 19,039 | +0 | 一致 |
| `historical_place_names` | 47,503 | 47,503 | +0 | 一致 |
| `historical_place_locations` | 18,103 | 18,103 | +0 | 一致 |
| `data_quality_issues` | 12,631 | 12,631 | +0 | 一致 |

未列入权威对照的表（实测值，供后续比对）：

- `data_datasets`：7 行
- `candidate_matches`：53,137 行

> ✅ 五张列入权威对照的表实测行数与 V0.2.2-r2 §0 完全一致。

### 1.2 逐表逐列实测明细

#### 1.2.1 `data_datasets` — 7 行 × 11 列

- 文件：`data_datasets.csv`（6,018 字节，SHA256 前 16 位 `fa44197e54b4da4a`）
- 编码/分隔符/行尾：UTF-8 BOM (EF BB BF) / 逗号 , / CRLF x8
- 嵌入换行单元格：0 个；最大单元格长度：459 字符

| # | staging_column | 总行数 | 非空 | 空值 | 空值率 | 唯一值 | 推断类型 | 样例值（最多 3 个，截断 120 字符） |
|---|----------------|--------|------|------|--------|--------|----------|-----------------------------------|
| 1 | `dataset_id` | 7 | 7 | 0 | 0.00% | 7 | text(短,<=64字符) | `chgis_v6_prefecture_points` ｜ `chgis_v6_county_points` ｜ `mcgd_zenodo_22094815_head960` |
| 2 | `source_id` | 7 | 7 | 0 | 0.00% | 4 | text(短,<=64字符) | `chgis` ｜ `mcgd` ｜ `pleiades` |
| 3 | `dataset_name` | 7 | 7 | 0 | 0.00% | 7 | text(中,<=512字符) | `CHGIS V6 time_pref_pts (prefecture-level point layer)` ｜ `CHGIS V6 time_cnty_pts (county-level point layer)` ｜ `MCGD (Modern China Geospatial Database) 2026-08-25, first 960 rows` |
| 4 | `homepage` | 7 | 7 | 0 | 0.00% | 5 | text(短,<=64字符) | `https://sites.fas.harvard.edu/~chgis/` ｜ `https://doi.org/10.5281/zenodo.22094815` ｜ `https://pleiades.stoa.org/` |
| 5 | `license_id` | 7 | 7 | 0 | 0.00% | 5 | text(短,<=64字符) | `no_spdx_academic_noncommercial` ｜ `CC-BY-4.0` ｜ `CC-BY-3.0` |
| 6 | `license_url` | 7 | 6 | 1 | 14.29% | 4 | text(短,<=64字符) | `https://doi.org/10.7910/DVN/FDLFJ3` ｜ `https://creativecommons.org/licenses/by/4.0/` ｜ `https://creativecommons.org/licenses/by/3.0/` |
| 7 | `redistributable` | 7 | 7 | 0 | 0.00% | 3 | text(短,<=64字符) | `no` ｜ `yes_with_attribution` ｜ `unconfirmed` |
| 8 | `attribution_text` | 7 | 6 | 1 | 14.29% | 5 | text(中,<=512字符) | `CHGIS, Version: 6. (c) Fairbank Center for Chinese Studies of Harvard University and the Center for Historical Geographi…[截断]` ｜ `Christian Henriot / ENP-China, MCGD (Zenodo 22094815), CC BY 4.0` ｜ `Pleiades: A community-built gazetteer and graph of ancient places. Copyright (c) Institute for the Study of the Ancient …[截断]` |
| 9 | `acquisition_method` | 7 | 7 | 0 | 0.00% | 6 | text(短,<=64字符) | `full DBF + sidecars read from the shipped V6 zip` ｜ `head slice of the CSV, 960 data rows, taken upstream` ｜ `from_slice=1MB_head; HTTP Range bytes=0-1048575 per file` |
| 10 | `evidence` | 7 | 7 | 0 | 0.00% | 7 | text(中,<=512字符) | `sample_data/chgis/api/dataset_FDLFJ3_EULA.json -> termsOfUse clause (3) forbids redistribution and clause (4) mandates t…[截断]` ｜ `same zip family and same EULA as chgis_v6_prefecture_points; the .prj sidecar inside the county zip is GEOGCS["GCS_WGS_1…[截断]` ｜ `sample_data/mcgd/zenodo_record_22094815.json -> metadata.license.id = 'cc-by-4.0'; metadata.access_right = 'open'` |
| 11 | `notes` | 7 | 7 | 0 | 0.00% | 7 | text(中,<=512字符) | `The README citation and the EULA mandatory citation disagree on three points (punctuation of 'Version 6', 'Center for Hi…[截断]` ｜ `Second CHGIS layer, listed separately because LEV_RANK, field order and BEG_RULE completeness differ from the prefecture…[截断]` ｜ `Row count is a fixed head slice, not the full dataset: any frequency computed here describes the slice, not MCGD.` |

#### 1.2.2 `source_records` — 29,391 行 × 14 列

- 文件：`source_records.csv`（26,942,777 字节，SHA256 前 16 位 `30fed0e40ba12496`）
- 编码/分隔符/行尾：UTF-8 BOM (EF BB BF) / 逗号 , / CRLF x280
- 嵌入换行单元格：0 个；最大单元格长度：42,469 字符

| # | staging_column | 总行数 | 非空 | 空值 | 空值率 | 唯一值 | 推断类型 | 样例值（最多 3 个，截断 120 字符） |
|---|----------------|--------|------|------|--------|--------|----------|-----------------------------------|
| 1 | `source_record_id` | 29,391 | 29,391 | 0 | 0.00% | 29,391 | text(短,<=64字符) | `sr_0000001` ｜ `sr_0000002` ｜ `sr_0000003` |
| 2 | `source_id` | 29,391 | 29,391 | 0 | 0.00% | 4 | text(短,<=64字符) | `chgis` ｜ `mcgd` ｜ `pleiades` |
| 3 | `source_dataset` | 29,391 | 29,391 | 0 | 0.00% | 5 | text(短,<=64字符) | `chgis_pref` ｜ `chgis_cnty` ｜ `mcgd_zenodo_22094815_head960` |
| 4 | `dataset_id` | 29,391 | 29,391 | 0 | 0.00% | 7 | text(短,<=64字符) | `chgis_v6_prefecture_points` ｜ `chgis_v6_county_points` ｜ `mcgd_zenodo_22094815_head960` |
| 5 | `external_id` | 29,391 | 29,391 | 0 | 0.00% | 27,319 | integer | `210001` ｜ `210002` ｜ `210003` |
| 6 | `external_id_type` | 29,391 | 29,391 | 0 | 0.00% | 11 | text(短,<=64字符) | `chgis_sys_id` ｜ `mcgd_nameid` ｜ `pleiades_place_id` |
| 7 | `raw_file` | 29,391 | 29,391 | 0 | 0.00% | 14 | text(中,<=512字符) | `设计资料/P0验证/WB-002/sample_data/chgis/v6_time_pref_pts_utf_wgs84.zip` ｜ `设计资料/P0验证/WB-002/sample_data/chgis/v6_time_cnty_pts_utf_wgs84.zip` ｜ `设计资料/P0验证/WB-002/sample_data/mcgd/MCGD_Data2026_08_25.csv.head-960rows.sample.csv` |
| 8 | `raw_record_index` | 29,391 | 29,391 | 0 | 0.00% | 10,522 | integer | `1` ｜ `2` ｜ `3` |
| 9 | `raw_payload_json` | 29,391 | 29,391 | 0 | 0.00% | 29,386 | json_like | `{"BEG_CHG_TY":"新建","BEG_RULE":"4","BEG_YR":"993","CHECKER":"","COMPILER":"王尚义王杰","END_CHG_TY":"更名","END_DATE":"","END_RU…[截断]` ｜ `{"BEG_CHG_TY":"更名","BEG_RULE":"4","BEG_YR":"1005","CHECKER":"","COMPILER":"王尚义王杰","END_CHG_TY":"更名","END_DATE":"","END_R…[截断]` ｜ `{"BEG_CHG_TY":"更名","BEG_RULE":"4","BEG_YR":"1182","CHECKER":"","COMPILER":"王尚义王杰","END_CHG_TY":"撤销","END_DATE":"","END_R…[截断]` |
| 10 | `license_status` | 29,391 | 29,391 | 0 | 0.00% | 6 | text(短,<=64字符) | `restricted_academic_only` ｜ `cc-by-4.0` ｜ `CC-BY-3.0` |
| 11 | `redistributable` | 29,391 | 29,391 | 0 | 0.00% | 3 | text(短,<=64字符) | `no` ｜ `yes_with_attribution` ｜ `unconfirmed` |
| 12 | `attribution_text` | 29,391 | 29,383 | 8 | 0.03% | 5 | text(中,<=512字符) | `"CHGIS, Version: 6." (c) Fairbank Center for Chinese Studies of Harvard University and the Center for Historical Geograp…[截断]` ｜ `Christian Henriot / ENP-China, MCGD (Zenodo 22094815), CC BY 4.0` ｜ `Pleiades: A community-built gazetteer and graph of ancient places. Copyright (c) Institute for the Study of the Ancient …[截断]` |
| 13 | `ingested_at` | 29,391 | 29,391 | 0 | 0.00% | 1 | timestamp | `2026-11-02T00:00:00Z` |
| 14 | `pipeline_version` | 29,391 | 29,391 | 0 | 0.00% | 1 | text(短,<=64字符) | `wb-002-normalize/1.2.0` |

#### 1.2.3 `historical_places` — 19,039 行 × 15 列

- 文件：`historical_places.csv`（4,953,976 字节，SHA256 前 16 位 `86db3ce6b94f9e31`）
- 编码/分隔符/行尾：UTF-8 BOM (EF BB BF) / 逗号 , / CRLF x1002
- 嵌入换行单元格：0 个；最大单元格长度：244 字符

| # | staging_column | 总行数 | 非空 | 空值 | 空值率 | 唯一值 | 推断类型 | 样例值（最多 3 个，截断 120 字符） |
|---|----------------|--------|------|------|--------|--------|----------|-----------------------------------|
| 1 | `place_id` | 19,039 | 19,039 | 0 | 0.00% | 19,039 | text(短,<=64字符) | `hp_000001` ｜ `hp_000002` ｜ `hp_000003` |
| 2 | `canonical_name` | 19,039 | 19,039 | 0 | 0.00% | 11,062 | text(短,<=64字符) | `福宁府` ｜ `永春州` ｜ `邵武府` |
| 3 | `canonical_name_lang` | 19,039 | 19,039 | 0 | 0.00% | 3 | text(短,<=64字符) | `zh` ｜ `zh-Latn` ｜ `und` |
| 4 | `place_type` | 19,039 | 19,039 | 0 | 0.00% | 4 | text(短,<=64字符) | `admin_center_prefecture` ｜ `unknown` ｜ `admin_center_other` |
| 5 | `source_id` | 19,039 | 19,039 | 0 | 0.00% | 4 | text(短,<=64字符) | `chgis` ｜ `mcgd` ｜ `pleiades` |
| 6 | `source_dataset` | 19,039 | 19,039 | 0 | 0.00% | 5 | text(短,<=64字符) | `chgis_pref` ｜ `chgis_cnty` ｜ `mcgd_zenodo_22094815_head960` |
| 7 | `primary_external_id` | 19,039 | 19,039 | 0 | 0.00% | 18,997 | integer | `32019` ｜ `32020` ｜ `32021` |
| 8 | `record_status` | 19,039 | 19,039 | 0 | 0.00% | 1 | text(短,<=64字符) | `staging` |
| 9 | `locked` | 19,039 | 19,039 | 0 | 0.00% | 1 | boolean | `false` |
| 10 | `created_at` | 19,039 | 19,039 | 0 | 0.00% | 1 | timestamp | `2026-11-02T00:00:00Z` |
| 11 | `valid_from_year_astro` | 19,039 | 17,534 | 1,505 | 7.90% | 1,724 | integer | `1734` ｜ `1368` ｜ `1662` |
| 12 | `valid_to_year_astro` | 19,039 | 17,534 | 1,505 | 7.90% | 1,553 | integer | `1911` ｜ `1683` ｜ `606` |
| 13 | `time_bound_type` | 19,039 | 19,039 | 0 | 0.00% | 6 | text(短,<=64字符) | `exact` ｜ `exact_or_bounded` ｜ `unknown` |
| 14 | `time_derivation` | 19,039 | 19,039 | 0 | 0.00% | 3 | text(短,<=64字符) | `min_max_of_children` ｜ `none` ｜ `tpq_taq_of_children` |
| 15 | `notes` | 19,039 | 19,039 | 0 | 0.00% | 19,039 | text(中,<=512字符) | `sys_id=32019; records=1; canonical_record_index=3602; type_py=Fu; type_ch=府; lev_rank=3; place_type_basis=lev_rank=3` ｜ `sys_id=32020; records=1; canonical_record_index=3603; type_py=Zhilizhou; type_ch=直隶州; lev_rank=3; place_type_basis=lev_r…[截断]` ｜ `sys_id=32021; records=1; canonical_record_index=3604; type_py=Fu; type_ch=府; lev_rank=3; place_type_basis=lev_rank=3` |

#### 1.2.4 `historical_place_names` — 47,503 行 × 13 列

- 文件：`historical_place_names.csv`（8,937,942 字节，SHA256 前 16 位 `80674c0ded553241`）
- 编码/分隔符/行尾：UTF-8 BOM (EF BB BF) / 逗号 , / CRLF x1472
- 嵌入换行单元格：0 个；最大单元格长度：403 字符

| # | staging_column | 总行数 | 非空 | 空值 | 空值率 | 唯一值 | 推断类型 | 样例值（最多 3 个，截断 120 字符） |
|---|----------------|--------|------|------|--------|--------|----------|-----------------------------------|
| 1 | `name_id` | 47,503 | 47,503 | 0 | 0.00% | 47,503 | text(短,<=64字符) | `nm_0000001` ｜ `nm_0000002` ｜ `nm_0000003` |
| 2 | `place_id` | 47,503 | 47,503 | 0 | 0.00% | 17,532 | text(短,<=64字符) | `hp_000001` ｜ `hp_000002` ｜ `hp_000003` |
| 3 | `name` | 47,503 | 47,503 | 0 | 0.00% | 25,185 | text(短,<=64字符) | `福宁府` ｜ `Funing Fu` ｜ `福寧府` |
| 4 | `name_lang` | 47,503 | 47,503 | 0 | 0.00% | 48 | text(短,<=64字符) | `zh` ｜ `zh-Latn` ｜ `und` |
| 5 | `name_script` | 47,503 | 45,206 | 2,297 | 4.84% | 3 | text(短,<=64字符) | `Hani` ｜ `Latn` ｜ `Hant` |
| 6 | `name_type` | 47,503 | 47,503 | 0 | 0.00% | 3 | text(短,<=64字符) | `primary` ｜ `transliteration` ｜ `alternate` |
| 7 | `transliteration_scheme` | 47,503 | 16,708 | 30,795 | 64.83% | 2 | text(短,<=64字符) | `pinyin` ｜ `wade_giles_probable` |
| 8 | `valid_from_year_astro` | 47,503 | 45,942 | 1,561 | 3.29% | 1,708 | integer | `1734` ｜ `1368` ｜ `1662` |
| 9 | `valid_to_year_astro` | 47,503 | 45,942 | 1,561 | 3.29% | 1,553 | integer | `1911` ｜ `1683` ｜ `606` |
| 10 | `time_bound_type` | 47,503 | 47,503 | 0 | 0.00% | 6 | text(短,<=64字符) | `exact` ｜ `exact_or_bounded` ｜ `unknown` |
| 11 | `time_rule_code` | 47,503 | 46,320 | 1,183 | 2.49% | 52 | text(短,<=64字符) | `4\|5` ｜ `5\|6` ｜ `3\|5` |
| 12 | `source_record_id` | 47,503 | 47,503 | 0 | 0.00% | 19,005 | text(短,<=64字符) | `sr_0003602` ｜ `sr_0003603` ｜ `sr_0003604` |
| 13 | `notes` | 47,503 | 47,503 | 0 | 0.00% | 10,540 | text(中,<=512字符) | `NAME_CH from record 3602; this is the name attested for the entity during this record's own time window, not the entity'…[截断]` ｜ `NAME_PY from the same record as the primary NAME_CH name` ｜ `NAME_FT differs from NAME_CH (traditional-character form)` |

#### 1.2.5 `historical_place_locations` — 18,103 行 × 22 列

- 文件：`historical_place_locations.csv`（11,698,567 字节，SHA256 前 16 位 `9e987ba578e933ed`）
- 编码/分隔符/行尾：UTF-8 BOM (EF BB BF) / 逗号 , / CRLF x372
- 嵌入换行单元格：0 个；最大单元格长度：896 字符

| # | staging_column | 总行数 | 非空 | 空值 | 空值率 | 唯一值 | 推断类型 | 样例值（最多 3 个，截断 120 字符） |
|---|----------------|--------|------|------|--------|--------|----------|-----------------------------------|
| 1 | `location_id` | 18,103 | 18,103 | 0 | 0.00% | 18,103 | text(短,<=64字符) | `loc_0000001` ｜ `loc_0000002` ｜ `loc_0000003` |
| 2 | `place_id` | 18,103 | 18,103 | 0 | 0.00% | 17,981 | text(短,<=64字符) | `hp_000001` ｜ `hp_000002` ｜ `hp_000003` |
| 3 | `geom_type` | 18,103 | 18,103 | 0 | 0.00% | 1 | text(短,<=64字符) | `Point` |
| 4 | `lon` | 18,103 | 18,093 | 10 | 0.06% | 8,302 | numeric | `119.990395` ｜ `118.28717` ｜ `117.483398` |
| 5 | `lat` | 18,103 | 18,093 | 10 | 0.06% | 8,309 | numeric | `26.883463` ｜ `25.32579` ｜ `27.337692` |
| 6 | `geom_wkt` | 18,103 | 18,093 | 10 | 0.06% | 8,366 | text(短,<=64字符) | `POINT(119.990395 26.883463)` ｜ `POINT(118.28717 25.32579)` ｜ `POINT(117.483398 27.337692)` |
| 7 | `representative_lon` | 18,103 | 18,093 | 10 | 0.06% | 8,302 | numeric | `119.990395` ｜ `118.28717` ｜ `117.483398` |
| 8 | `representative_lat` | 18,103 | 18,093 | 10 | 0.06% | 8,309 | numeric | `26.883463` ｜ `25.32579` ｜ `27.337692` |
| 9 | `original_x` | 18,103 | 18,103 | 0 | 0.00% | 8,303 | numeric | `119.990395` ｜ `118.287170` ｜ `117.483398` |
| 10 | `original_y` | 18,103 | 18,103 | 0 | 0.00% | 8,311 | numeric | `26.883463` ｜ `25.325790` ｜ `27.337692` |
| 11 | `original_crs` | 18,103 | 18,103 | 0 | 0.00% | 2 | text(短,<=64字符) | `EPSG:4326` ｜ `unknown` |
| 12 | `crs_confidence` | 18,103 | 18,103 | 0 | 0.00% | 3 | text(短,<=64字符) | `confirmed` ｜ `unknown` ｜ `inferred` |
| 13 | `axis_order_verified` | 18,103 | 18,103 | 0 | 0.00% | 1 | boolean | `true` |
| 14 | `location_precision` | 18,103 | 18,103 | 0 | 0.00% | 2 | text(短,<=64字符) | `point` ｜ `precise` |
| 15 | `uncertainty_m` | 18,103 | 1,703 | 16,400 | 90.59% | 16 | numeric | `5.0` ｜ `20.0` ｜ `10.0` |
| 16 | `valid_from_year_astro` | 18,103 | 16,879 | 1,224 | 6.76% | 1,716 | integer | `1734` ｜ `1368` ｜ `1662` |
| 17 | `valid_to_year_astro` | 18,103 | 16,879 | 1,224 | 6.76% | 1,560 | integer | `1911` ｜ `1683` ｜ `606` |
| 18 | `time_bound_type` | 18,103 | 18,103 | 0 | 0.00% | 6 | text(短,<=64字符) | `exact` ｜ `exact_or_bounded` ｜ `unknown` |
| 19 | `time_rule_code` | 18,103 | 17,452 | 651 | 3.60% | 52 | text(短,<=64字符) | `4\|5` ｜ `5\|6` ｜ `3\|5` |
| 20 | `quality_flag` | 18,103 | 685 | 17,418 | 96.22% | 6 | text(短,<=64字符) | `beg_gt_end` ｜ `missing_coordinate` ｜ `crs_unknown` |
| 21 | `source_record_id` | 18,103 | 18,103 | 0 | 0.00% | 18,103 | text(短,<=64字符) | `sr_0003602` ｜ `sr_0003603` ｜ `sr_0003604` |
| 22 | `notes` | 18,103 | 18,103 | 0 | 0.00% | 16,396 | text(长,>512字符) | `original_crs=EPSG:4326 confirmed from the .prj sidecar in the source zip (GEOGCS["GCS_WGS_1984"], DATUM["D_WGS_1984"]); …[截断]` ｜ `original_crs=EPSG:4326 confirmed from the .prj sidecar in the source zip (GEOGCS["GCS_WGS_1984"], DATUM["D_WGS_1984"]); …[截断]` ｜ `original_crs=EPSG:4326 confirmed from the .prj sidecar in the source zip (GEOGCS["GCS_WGS_1984"], DATUM["D_WGS_1984"]); …[截断]` |

#### 1.2.6 `candidate_matches` — 53,137 行 × 19 列

- 文件：`candidate_matches.csv`（17,315,204 字节，SHA256 前 16 位 `4e29c2ec64ebe263`）
- 编码/分隔符/行尾：UTF-8 BOM (EF BB BF) / 逗号 , / CRLF x721
- 嵌入换行单元格：0 个；最大单元格长度：194 字符

| # | staging_column | 总行数 | 非空 | 空值 | 空值率 | 唯一值 | 推断类型 | 样例值（最多 3 个，截断 120 字符） |
|---|----------------|--------|------|------|--------|--------|----------|-----------------------------------|
| 1 | `candidate_id` | 53,137 | 53,137 | 0 | 0.00% | 53,137 | text(短,<=64字符) | `cm_0000001` ｜ `cm_0000002` ｜ `cm_0000003` |
| 2 | `relation_type` | 53,137 | 53,137 | 0 | 0.00% | 6 | text(短,<=64字符) | `homonym_diff_place` ｜ `location_migration_candidate` ｜ `same_coord_diff_entity` |
| 3 | `place_id_a` | 53,137 | 53,137 | 0 | 0.00% | 12,339 | text(短,<=64字符) | `hp_011276` ｜ `hp_011274` ｜ `hp_011275` |
| 4 | `source_record_id_a` | 53,137 | 53,137 | 0 | 0.00% | 12,353 | text(短,<=64字符) | `sr_0010675` ｜ `sr_0010673` ｜ `sr_0010674` |
| 5 | `name_a` | 53,137 | 53,137 | 0 | 0.00% | 6,452 | text(短,<=64字符) | `邓川州` ｜ `云州` ｜ `太和县` |
| 6 | `lon_a` | 53,137 | 52,747 | 390 | 0.73% | 4,210 | numeric | `100.0416` ｜ `100.07986` ｜ `100.08584` |
| 7 | `lat_a` | 53,137 | 52,747 | 390 | 0.73% | 4,218 | numeric | `25.99123` ｜ `25.97593` ｜ `25.98929` |
| 8 | `place_id_b` | 53,137 | 53,137 | 0 | 0.00% | 11,994 | text(短,<=64字符) | `hp_004930` ｜ `hp_011275` ｜ `hp_011276` |
| 9 | `source_record_id_b` | 53,137 | 53,137 | 0 | 0.00% | 11,996 | text(短,<=64字符) | `sr_0002954` ｜ `sr_0010674` ｜ `sr_0010675` |
| 10 | `name_b` | 53,137 | 53,137 | 0 | 0.00% | 6,143 | text(短,<=64字符) | `邓川州` ｜ `云州` ｜ `太和县` |
| 11 | `lon_b` | 53,137 | 52,747 | 390 | 0.73% | 4,303 | numeric | `100.04159` ｜ `100.08584` ｜ `100.0416` |
| 12 | `lat_b` | 53,137 | 52,747 | 390 | 0.73% | 4,311 | numeric | `25.99123` ｜ `25.98929` ｜ `24.40797` |
| 13 | `distance_m` | 53,137 | 52,747 | 390 | 0.73% | 4,622 | numeric | `1.0` ｜ `4186.6` ｜ `1601.3` |
| 14 | `same_name` | 53,137 | 53,137 | 0 | 0.00% | 2 | boolean | `true` ｜ `false` |
| 15 | `evidence` | 53,137 | 53,137 | 0 | 0.00% | 53,125 | text(中,<=512字符) | `same NAME_CH='邓川州' at two places 1 m apart; sys_id 80079 (1384\|1640,云南省洱源县旧州) vs 212376 (1384\|1640,今云南省洱源县邓川镇旧州); either…[截断]` ｜ `same NAME_CH='邓川州' at two places 4187 m apart; sys_id 80077 (1641\|1911,云南省洱源县邓川镇新州) vs 212376 (1384\|1640,今云南省洱源县邓川镇旧州); …[截断]` ｜ `same NAME_CH='邓川州' at two places 1601 m apart; sys_id 80077 (1641\|1911,云南省洱源县邓川镇新州) vs 80078 (1274\|1383,云南省洱源县邓川镇德源城遗址处)…[截断]` |
| 16 | `confidence` | 53,137 | 53,137 | 0 | 0.00% | 4 | text(短,<=64字符) | `low` ｜ `high` ｜ `medium` |
| 17 | `status` | 53,137 | 53,137 | 0 | 0.00% | 2 | text(短,<=64字符) | `candidate` ｜ `needs_manual_review` |
| 18 | `reviewer` | 53,137 | 0 | 53,137 | 100.00% | 0 | empty(全空) | （无非空值） |
| 19 | `reviewed_at` | 53,137 | 0 | 53,137 | 100.00% | 0 | empty(全空) | （无非空值） |

#### 1.2.7 `data_quality_issues` — 12,631 行 × 11 列

- 文件：`data_quality_issues.csv`（5,277,273 字节，SHA256 前 16 位 `7a8ab3916e00dcb0`）
- 编码/分隔符/行尾：UTF-8 BOM (EF BB BF) / 逗号 , / CRLF x691
- 嵌入换行单元格：0 个；最大单元格长度：233 字符

| # | staging_column | 总行数 | 非空 | 空值 | 空值率 | 唯一值 | 推断类型 | 样例值（最多 3 个，截断 120 字符） |
|---|----------------|--------|------|------|--------|--------|----------|-----------------------------------|
| 1 | `issue_id` | 12,631 | 12,631 | 0 | 0.00% | 12,631 | text(短,<=64字符) | `dq_0000001` ｜ `dq_0000002` ｜ `dq_0000003` |
| 2 | `source_id` | 12,631 | 12,631 | 0 | 0.00% | 4 | text(短,<=64字符) | `chgis` ｜ `mcgd` ｜ `whg` |
| 3 | `source_dataset` | 12,631 | 12,631 | 0 | 0.00% | 5 | text(短,<=64字符) | `chgis_pref` ｜ `chgis_cnty` ｜ `mcgd_zenodo_22094815_head960` |
| 4 | `source_record_id` | 12,631 | 12,625 | 6 | 0.05% | 12,504 | text(短,<=64字符) | `sr_0003606` ｜ `sr_0003610` ｜ `sr_0003623` |
| 5 | `issue_type` | 12,631 | 12,631 | 0 | 0.00% | 13 | text(短,<=64字符) | `unknown_time_bound_type` ｜ `beg_eq_end` ｜ `beg_gt_end` |
| 6 | `severity` | 12,631 | 12,631 | 0 | 0.00% | 3 | text(短,<=64字符) | `info` ｜ `blocking` ｜ `warning` |
| 7 | `field_name` | 12,631 | 12,631 | 0 | 0.00% | 17 | text(短,<=64字符) | `END_RULE` ｜ `BEG_YR/END_YR` ｜ `BEG_RULE\|END_RULE` |
| 8 | `observed_value` | 12,631 | 12,304 | 327 | 2.59% | 3,406 | text(中,<=512字符) | `END_RULE=7` ｜ `BEG_YR=1887;END_YR=1887` ｜ `BEG_YR=606;END_YR=606` |
| 9 | `expected_rule` | 12,631 | 12,631 | 0 | 0.00% | 16 | text(中,<=512字符) | `every BEG_RULE/END_RULE code should appear in xtra_date_rules so the determinacy of the year can be established` ｜ `BEG_YR < END_YR for a span; equal years are valid only for a time slice (date rule 9)` ｜ `BEG_YR <= END_YR` |
| 10 | `action_taken` | 12,631 | 12,631 | 0 | 0.00% | 3 | text(短,<=64字符) | `preserved_and_flagged` ｜ `needs_manual_review` ｜ `discarded` |
| 11 | `notes` | 12,631 | 12,631 | 0 | 0.00% | 50 | text(中,<=512字符) | `one row per record listing each field whose rule code is blank or absent from the CHGIS date-rule workbook; time_bound_t…[截断]` ｜ `single-year span; beg_rule=6, end_rule=6` ｜ `single-year span; beg_rule=4, end_rule=4` |

### 1.3 全字段扁平索引（供 FIELD_MAPPING_V2.1.1 校验用）

共 105 个暂存字段，形如 `staging_table.staging_column`：

- **`data_datasets`**（11 列）：`dataset_id`、`source_id`、`dataset_name`、`homepage`、`license_id`、`license_url`、`redistributable`、`attribution_text`、`acquisition_method`、`evidence`、`notes`
- **`source_records`**（14 列）：`source_record_id`、`source_id`、`source_dataset`、`dataset_id`、`external_id`、`external_id_type`、`raw_file`、`raw_record_index`、`raw_payload_json`、`license_status`、`redistributable`、`attribution_text`、`ingested_at`、`pipeline_version`
- **`historical_places`**（15 列）：`place_id`、`canonical_name`、`canonical_name_lang`、`place_type`、`source_id`、`source_dataset`、`primary_external_id`、`record_status`、`locked`、`created_at`、`valid_from_year_astro`、`valid_to_year_astro`、`time_bound_type`、`time_derivation`、`notes`
- **`historical_place_names`**（13 列）：`name_id`、`place_id`、`name`、`name_lang`、`name_script`、`name_type`、`transliteration_scheme`、`valid_from_year_astro`、`valid_to_year_astro`、`time_bound_type`、`time_rule_code`、`source_record_id`、`notes`
- **`historical_place_locations`**（22 列）：`location_id`、`place_id`、`geom_type`、`lon`、`lat`、`geom_wkt`、`representative_lon`、`representative_lat`、`original_x`、`original_y`、`original_crs`、`crs_confidence`、`axis_order_verified`、`location_precision`、`uncertainty_m`、`valid_from_year_astro`、`valid_to_year_astro`、`time_bound_type`、`time_rule_code`、`quality_flag`、`source_record_id`、`notes`
- **`candidate_matches`**（19 列）：`candidate_id`、`relation_type`、`place_id_a`、`source_record_id_a`、`name_a`、`lon_a`、`lat_a`、`place_id_b`、`source_record_id_b`、`name_b`、`lon_b`、`lat_b`、`distance_m`、`same_name`、`evidence`、`confidence`、`status`、`reviewer`、`reviewed_at`
- **`data_quality_issues`**（11 列）：`issue_id`、`source_id`、`source_dataset`、`source_record_id`、`issue_type`、`severity`、`field_name`、`observed_value`、`expected_rule`、`action_taken`、`notes`
---

## 第二节 V2.1 → V2.1.1 映射差异预判

### 2.0 方法、来源层级与判定纪律

**比对对象**

| 项 | 路径 | 说明 |
|---|---|---|
| V2.1 映射表 | `架构/V2.1/FIELD_MAPPING_V2.1.csv` | **208 行 = 1 表头 + 207 数据行**；本文引用格式为 `L<n>` = CSV 第 n 行 |
| V2.1 数据模型 | `架构/V2.1/CORE_DATA_MODEL_V2.1.md` | 目标表列定义与 CHECK |
| V2.1.1 定式 | `架构/V2.1.1/V0.2.2/00_PROBLEM_LIST_AND_PLAN_V0.2.2.md` | V0.2.2-r2 定式正文 |
| 变更依据 | `架构/V2.1.1/V0.2.2/V0.2.1_TO_V0.2.2_CHANGELOG.md` | 逐项原设计→修改后 |
| 实测基线 | 本文第一节（① 原始 CSV 逐行实算） | 七张表逐列统计 |

**来源层级标注（逐行标注，不得省略）**

| 符号 | 层级 | 可否直接当结论 |
|---|---|---|
| **①** | 原始 CSV 逐行实算（本文第一节及 `verify_v211_gaps.py` / `probe_parent_external_id.py`） | ✅ 可 |
| **②** | 上游脚本产物（`run_manifest.json` / `stats.json` / `normalize.py`） | ❌ 仅作引用 |
| **③** | 上游文档结论（V0.2.2 / V2.1 文档，带行号） | ❌ 仅作引用，须与①对碰 |
| **④** | 基线文档定义（本文第一节） | ✅ 可（其本身由①构成） |

**判定纪律**：凡 ② ③ 与 ① 冲突，**以 ① 为准并在 §2.3 点名**。本节的每处处置都标注了层级；凡只标 ③ 而无 ① 支撑的，属于「定式已给、暂无数据可验」，已在 §2.6 单列。

---

### 2.1 差异行总表

**统计口径**：`失效` = V2.1 映射行在 V2.1.1 下语义错误、目标列消失或判据被推翻，必须删除或改写；`新增` = V2.1 映射表完全没有、V2.1.1 必须补的行；`连带` = 行本身保留但 notes/判据须改写。

| 组 | 目标表 | 失效 | 新增 | 连带 | 小计 |
|---|---|---:|---:|---:|---:|
| A | `data_dataset`（许可 9 列删除） | 11 | 0 | 0 | **11** |
| A′ | `source_record` 许可三列 notes | 0 | 0 | 3 | **3** |
| B | `source_record`（五段键 / 隔离 / 新增列） | 3 | 4 | 1 | **8** |
| C | `historical_place` | 1 | 1 | 1 | **3** |
| D | `historical_place_name` / `_location`（`rejected_by`） | 2 | 2 | 0 | **4** |
| E | `data_quality_issue`（指纹 / 批次 / 计数） | 1 | 3 | 0 | **4** |
| F | `source_record.record_scope`（4 值收敛） | 2 | 0 | 0 | **2** |
| — | **`candidate_match`** | **0** | **0** | **0** | **0**（已核，见 §2.5） |
| **合计** | | **20** | **10** | **5** | **35** |

> **合计 35 行 = 失效 20 + 新增 10 + 连带 5**。占 V2.1 全部 207 数据行的 **16.9%**。

---

### 2.2 逐行详述

#### 2.2.A `data_dataset`：许可 9 列删除（**11 行失效**）

**待删的 9 个目标列**（③ `CORE_DATA_MODEL_V2.1.md:144–152` 逐列核对，顺序与原文一致）：
`license_id`(144) / `license_url`(145) / `attribution_text`(146) / `attribution_required`(147) / `modification_note_required`(148) / `overlay_license_id`(149) / `redistributable`(150) / `license_evidence`(151) / `license_verified_at`(152) —— **恰 9 列**，与任务书口径一致。

**删除依据**（③ `V0.2.2 §3.3` 逐字）：「不设计授权、许可、再分发管理；不重新引入 `attribution_text`、`citation_text` **或任何替代字段**」。

| V2.1 映射行（`L<n>`） | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |
|---|---|---|---|
| `L5` `data_datasets.homepage` → `data_dataset.license_url` | 目标列 `license_url` 删除（③:145）；且 notes「许可页缺失时暂用 homepage」把主页当许可页兜底，属 §3.3 禁止的许可语义 | **删除映射行**，或改指 `data_source.homepage`（`L203` 已有该列）。**不得**改名落到 `notes`/`evidence` 变相保留 | **存在**（①）：`data_datasets.homepage` 7/7 非空、唯一 5 |
| `L6` `data_datasets.license_id` → `data_dataset.license_id` | 目标列删除（③:144） | **删除映射行**。暂存列随之失去入库通路 | **存在**（①）：7/7 非空、唯一 5（`no_spdx_academic_noncommercial` / `CC-BY-4.0` / `CC-BY-3.0` / `ODC-By-1.0` / `unconfirmed`） |
| `L7` `data_datasets.license_url` → `(dropped)` | 行本身已是 dropped，但 notes「保留在 `license_evidence` 文本里」指向**已删除**的列（③:151） | **保留 dropped，改写 notes**：去掉 `license_evidence` 引用，改为「与 `homepage` 同源重复，V2.1.1 目标模型不设许可列 ⇒ 整列 dropped」 | **存在**（①）：6/7 非空、**1 行空** |
| `L8` `data_datasets.redistributable` → `data_dataset.redistributable` | 目标列删除（③:150）；其「三态拆分」（`unconfirmed→true`+`license_id='unknown'`）随 `license_id` 一起消失 ⇒ transform 无落点 | **删除映射行** | **存在**（①）：7/7 非空、唯一 3（`no`/`yes_with_attribution`/`unconfirmed`） |
| `L9` `data_datasets.attribution_text` → `data_dataset.attribution_text` | 目标列删除（③:146）；§3.3 明令**不重新引入 `attribution_text` 或任何替代字段** | **删除映射行**。**禁止**改名为 `citation_text` / `credit` / `source_credit` 落到其它列 | **存在**（①）：6/7 非空、1 行空、最长 158 字符 |
| `L10` `data_datasets.acquisition_method` → `(derived)` `license_evidence` | 目标列 `license_evidence` 删除（③:151） | **删除映射行**。`acquisition_method` 若需保留须另找**非许可**目标列，否则整列 dropped（见 §2.6 Q2） | **存在**（①）：7/7 非空、唯一 6 |
| `L11` `data_datasets.evidence` → `data_dataset.license_evidence` | 目标列删除（③:151）；且 `evidence` 的主要内容就是 EULA/授权取证文本 | **删除映射行** | **存在**（①）：7/7 非空、唯一 7、最长 459 字符 |
| `L14` `(derived)` → `data_dataset.attribution_required` | 目标列删除（③:147）；其判据「`attribution_text` 非空 ⇒ true」随源列一起删 | **删除映射行** | `derived`（① 暂存无此列） |
| `L15` `(derived)` → `data_dataset.modification_note_required` | 目标列删除（③:148） | **删除映射行** | `derived`（① 暂存无此列） |
| `L16` `(derived)` → `data_dataset.overlay_license_id` | 目标列删除（③:149） | **删除映射行** | `derived`（① 暂存无此列） |
| `L17` `(derived)` → `data_dataset.license_verified_at` | 目标列删除（③:152） | **删除映射行**。连带：`L759` 系列「导入前置校验会拒」的许可门禁（③ `CORE_DATA_MODEL_V2.1.md:759`）**同时失效**，须从 V2.1.1 `IMPORT_RULES` 前置校验清单中摘除 | `derived`（① 暂存无此列） |

> **A 组判定要点（防「改名替代」）**：§3.3 写的是「不重新引入 `attribution_text`、`citation_text` **或任何替代字段**」。因此 V2.1.1 的 `FIELD_MAPPING` 若出现任何以 `citation_`/`credit_`/`attribution_` 开头的 `target_column`，即判 FAIL——不管它挂在哪个表下。判定式可直接实现：`target_column` 正则 `^(attribution|citation|license)_` 命中行数 == 0。

---

#### 2.2.A′ `source_record` 许可三列：`dropped` 保留，notes 须改写（**3 行连带**）

| V2.1 映射行 | 失效原因 | V2.1.1 应有处置 | 暂存是否真实存在 |
|---|---|---|---|
| `L39` `source_records.license_status` → `(dropped)` | 行本身保留，但 notes「许可只从 `data_dataset` 读」——`data_dataset` 的许可列已全删，该理由**不再成立** | 保留 dropped，**改写 notes** 为「暂存按行冗余的许可三列，V2.1 已判 dropped；V2.1.1 目标模型不设任何许可列」。判据并入 §3.3 禁用词扫描 | **存在**（①）：29,391/29,391 非空、唯一 6、0 空 |
| `L40` `source_records.redistributable` → `(dropped)` | 同上 | 同上 | **存在**（①）：29,391/29,391 非空、唯一 3（`no`/`yes_with_attribution`/`unconfirmed`）、0 空 |
| `L41` `source_records.attribution_text` → `(dropped)` | 同上 | 同上 | **存在**（①）：29,383/29,391 非空、**8 行空**、唯一 5 |

> **连带待裁定项**：`L204` `(none).(generated)` → `data_source.license_homepage`。`data_source` 表的这一列也是许可列，但 V0.2.2 §3.3 只约束 `DATA_PROVENANCE` 文档与 `data_dataset` 的 9 列，**未提及 `data_source`**。见 §2.6 Q1。

---

#### 2.2.B `source_record`：五段键、隔离优先、4 个新增列（**3 失效 + 4 新增 + 1 连带**）

**定式依据**（③ `V0.2.2 §2.5.0` C29、`§2.3.1` 第 0 行、`§2.5`）：

```
自然键 = (dataset_id, record_scope, parent_external_id, external_id, duplicate_ordinal)
C29  parent_external_id 为必需段：
     ① 任何情况下不得省略、不得以 NULL 兜底、不得用空串代替；
     ② 无父级概念的数据集（CHGIS place）写入哨兵值 '-'（不是 NULL）；
     ③ 派生失败 ⇒ 整批 failed（与 A12 同一处置），不是默认放行；
     ④ 哨兵必须是 parent_external_id 值域之外的保留字，且只能在 data_dataset
        或一张常量表里声明一次。
```

| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |
|---|---|---|---|
| `L46` `(derived)` → `source_record.parent_external_id`，`text`，**`required=N`**，`json_field`，notes「Pleiades→place_id；MCGD→LocID；**CHGIS/WHG→NULL**」 | **三重失效**：(a) `required` 由 `N` 变为**必需段**（③ C29①）；(b) notes 的「→NULL」被 C29① 明文禁止，CHGIS place 须写哨兵 `'-'`（③ C29②）；(c) V2.1 目标列定义是可空无约束（③ `CORE_DATA_MODEL_V2.1.md:265`），V2.1.1 须加 `NOT NULL` | **改写**：`required=Y`；`transform=json_field+sentinel`；notes 改为「Pleiades `name`/`location`/`edge` → `raw_payload.place_id`；MCGD → `raw_payload.LocID`；无父级概念者 → 哨兵 `'-'`（哨兵在常量表声明一次，③ C29④）；派生失败 ⇒ 整批 failed」。**必须补齐 Pleiades place 与 WHG 全组的规则**（见 §2.4） | **`derived`**（① 暂存 14 列中**无** `parent_external_id`）；派生来源 = `source_records.raw_payload_json` |
| `L50` `(derived)` → `source_record.is_active`，`rule`，notes「重复 ID 的第 2 行 ⇒ false（QUARANTINE）」 | notes 的判据被 V0.2.2 §2.3.1 **第 0 行**推翻：判定表在最前面新增「重复检测优先」行，先于 V2.1 的全部 10 行；且「第 2 行」的定序依据由 `raw_record_index` 改为 `content_hash` | **改写 notes**：`is_active=false` ⇔ 同**五段键的四段前缀**（含 `parent_external_id`）下存在另一行 `content_hash` 相同且 `duplicate_ordinal` 更小；隔离是**每批重算的派生结论**，不是一次置位；O7 解除保护**不得**复活它 | `derived`（① 暂存无此列） |
| `L45` `(derived)` → `source_record.occurrence_key`，`parent_ordinal\|''` | **语义冲突（连带）**：V2.1 §4.2 定义 `occurrence_key = <parent_external_id>#<按 raw_record_index 升序的名次>`；V0.2.2 的 `duplicate_ordinal` 按 **`content_hash`** 定序。**两者定序依据不同，不是同一列**，但 V2.1 的 `UNIQUE(dataset_id, record_scope, external_id, occurrence_key)` 与 V0.2.2 的五段键在段集上重叠 | **改写 notes**，写明 `occurrence_key`（`raw_record_index` 定序、V2 遗留）与 `duplicate_ordinal`（`content_hash` 定序、V2.1.1 新增）**并存且定序依据不同**；并明确 `UNIQUE` 由 4 段升级为 **5 段**（含 `parent_external_id`）⇒ CHECK `is_active OR occurrence_key <> ''`（③:279）需同步复核 | `derived`（① 暂存无此列） |

**B 组必须新增的 4 行（V2.1 映射表完全没有）**

| 新增行 | 定式（含层级） | 暂存是否真实存在 |
|---|---|---|
| `source_records.(derived)` → `source_record.duplicate_ordinal` | 组内按 `(content_hash ASC, raw_record_index ASC)` 定序后的名次（③ `V0.2.2 §2.5`）。实测权威值：`ordinal=0` = **29,377**，另 7 组 × 2 行 = 14 行、`ordinal` 1/2 各 7 行（③ `§0 N04`） | **`derived`**（① 暂存无此列）。由 `raw_payload_json` + 定序规则派生 |
| `source_records.(derived)` → `source_record.inactive_reason` | 3 值：`duplicate_quarantine` / `source_absent` / `batch_rolled_back`（③ `§2.3.1` 第 0 行、`§2.2.4`）。**V2.1 目标表根本没有这一列**（③ `CORE_DATA_MODEL_V2.1.md:258–273` 逐列核对：无）⇒ 这是 V2.1.1 的新表列，但 V0.2.2 §1「新列 +2」**未计入** | **`derived`**（① 暂存无此列） |
| `source_records.(derived)` → `source_record.inactive_at` | 与 `inactive_reason` 同生（③ `§2.3.2` 第 5 条「`inactive_reason` + `inactive_at` + `inactive_in_batch_id`（C21/C22）完整保留」；`§2.2.4` 视图按 `inactive_at DESC NULLS LAST` 取「最后失效原因」） | **`derived`**（① 暂存无此列） |
| `source_records.(derived)` → `source_record.inactive_in_batch_id` | 同上（③ `§2.3.2`、`§2.2.4`） | **`derived`**（① 暂存无此列） |

> **⚠ B 组内部结构冲突（必须点名，③ 与 ③ 冲突）**：V0.2.2 §1 合计栏逐字写「**新表 0，新列 +2（仅 `rejected_by` × 2 表）**」，§1 第 66 行与 CHANGELOG 第 17 行同样写 +2。但 §2.3.1 / §2.3.2 / §2.2.4 三处实际引用了 `source_record` 的 `inactive_reason` / `inactive_at` / `inactive_in_batch_id` 三列，而 V2.1 目标表（③ `CORE_DATA_MODEL_V2.1.md:258–273`）**一列都没有**。⇒ 真实新列数至少为 **+5（2 × `rejected_by` + 3 × 隔离台账列）**，不是 +2。这不是 QA 推断，是 V0.2.2 正文与 V2.1 表定义逐列对碰的结果（① 侧可佐证：暂存 14 列中 3 列全无）。**V2.1.1 编制时必须先裁定这 3 列加不加**，否则 `IMPORT_RULES` 第 0 行判定表无字段可写。

> **C29 与索引的连带**：V2.1 的 `UNIQUE` 是 **4 段** `(dataset_id, record_scope, external_id, occurrence_key)`（③ `CORE_DATA_MODEL_V2.1.md:276`），V0.2.2 C29 要求 **5 段含 `parent_external_id`**。这不是映射行，但直接决定 `L45` / `L46` 的语义；V2.1.1 `CORE` 与 ER 图必须同步，否则 UNIQUE 会退化成四段键 ⇒ 398 组误隔离（③ `§2.5.0`）。

---

#### 2.2.C `historical_place`（**1 失效 + 1 新增 + 1 连带**）

| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |
|---|---|---|---|
| `L59` `historical_places.record_status` → `historical_place.record_status`，`enum_rule = staging\|published\|merged\|rejected`（**4 值**） | V0.2.2 §2.1.1 定 `record_status` 为 **3 值** `staging` / `rejected` / `merged`（③）；而 V2.1 目标表的 CHECK 是 **4 值**（③ `CORE_DATA_MODEL_V2.1.md:338`，含 `published`）。⇒ `published` 的去留是本轮真实变更点，但 V0.2.2 只在 §5.5「视图派生列」一带隐含处理，**未在 §2.1.1 声明该 CHECK 变更** | **改写 `enum_rule` 为 3 值**，并在 V2.1.1 `CORE` 中同步修订 CHECK。若 `published` 需保留作发布态，须由架构师显式裁定（§2.6 Q3） | **存在**（①）：`historical_places.record_status` 19,039/19,039 非空、**唯一 1 值 = `staging`** |
| **新增**：`historical_places.(derived)` → `historical_place.dataset_id` | V0.2.2 §2.2.2 的 `v_place_evidence` 视图 SQL **逐字依赖**它：`FROM historical_place p JOIN source_record sr ON sr.dataset_id = p.dataset_id`（③ 第 203 行）。但 V2.1 §5.2.1 规则 1 明文「`historical_place` / `_name` / `_location` **不带 dataset 列**，归属通过 `source_record_id` 回溯」（③ `CORE_DATA_MODEL_V2.1.md:176`），且 V0.2.2 §1「新列 +2」**未计入它** | **必须新增该映射行**，`transform = join(created_from_source_record_id → source_record.dataset_id)`（`L69` 已定义 `created_from_source_record_id` 的派生规则，可直接复用）。**同时必须修订 V2.1 §5.2.1 规则 1 或改用 `JOIN source_record` 表达**——两条定式当前互斥 | **`derived`**（① `historical_places` 15 列中**无** `dataset_id`）；派生来源 = `created_from_source_record_id`（① 亦为 derived，`L69`） |
| `L58` `historical_places.primary_external_id` → `(dropped)`（连带） | 行本身保留 dropped，但 notes「MCGD 643 行填 LocID 而 source_record 用 NameID，join 不上」**与本轮冲突**：C29 把 `parent_external_id` 定为必需段后，MCGD 的 `LocID` 正是 `parent_external_id` 的来源（③ `§2.5.0`、`CORE_DATA_MODEL_V2.1.md:298`）⇒ 「join 不上」的说法需要重新表述 | 保留 dropped，**改写 notes**：补一句「MCGD 的 `LocID` 不用于 `external_id` 的 join，但它是 `parent_external_id` 的来源，二者用途不同、不可混淆」 | **存在**（①）：19,039/19,039 非空、唯一 18,997、最长 15 字符 |

> **⚠ 关于「`historical_place` 新增 `grain_key`」——任务书该项与 V0.2.2-r2 正文不符，予以驳回**：
> - ③ `V0.2.2 §2.7.2` 第 750 行逐字写：`OR (p.grain_key = sr.parent_external_id AND sr.record_scope <> 'place')` 是 **V0.2.1 的旧写法**，V0.2.2 已将「`<> 'place'` 过宽」改为**白名单 + 数据集显式声明**。
> - ③ `CHANGELOG` 第 271 行在「本轮新增字段」栏逐字写：**「字段：无（`data_dataset.place_grain` 已在 V0.2.1 的 `grain_key` 派生式中使用）」**。
> - ③ `CHANGELOG` 第 254 行的 `p.grain_key` 出现在「原设计」列（即被替换的旧式），不是「修改后」列。
> ⇒ **`grain_key` 不是 V2.1.1 新增列，而是已被 `data_dataset.place_grain` 取代的废弃概念。** V2.1.1 的 `FIELD_MAPPING` **不应**新增 `grain_key` 行；若新增即判 FAIL。
> 附带：`data_dataset.place_grain` 本身也**不是**新增列（③ `V0.2.2 §1` 第 68 行与 §2.7.2 第 711 行两处回退，它是 V2 既有列 `CORE_DATA_MODEL_V2.md:208`，V2.1 收敛为 2 值），其映射行 `L19` 只需把 `enum_rule` 从 3 值改为 `per_record\|per_parent_external_id` 2 值——**这已计入 `L19` 的常规修订，不属本轮新增**。

---

#### 2.2.D `historical_place_name` / `_location`：`rejected_by`（**2 失效 + 2 新增**）

**定式依据**（③ `V0.2.2 §2.2.1`，逐字）：

```sql
ALTER TABLE historical_place_name     ADD COLUMN rejected_by text NULL;
ALTER TABLE historical_place_location ADD COLUMN rejected_by text NULL;
-- C25：(record_status = 'rejected') = (rejected_by IS NOT NULL)   —— 同生同灭
-- C26：rejected_by IS NULL OR rejected_by IN ('auto','manual')     —— 值域 2
```

| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |
|---|---|---|---|
| `L110` `historical_place_locations.(derived)` → `record_status`，`gate`，`staging\|published\|rejected`，notes「`crs_confidence='unknown'` 或 `geom` NULL ⇒ `staging`」 | 由**单列 gate** 变为**双列联动**：C25 要求 `record_status='rejected'` ⟺ `rejected_by IS NOT NULL`，只写 `record_status` 的映射行无法满足该 CHECK | **改写**：保留 `gate` 逻辑，但 `transform` 改为 `gate + rejected_by 联动`；`enum_rule` 的 `published` 去留随 `L59` 一并裁定（§2.6 Q3） | **`derived`**（① `historical_place_locations` 22 列中**无** `record_status`、无 `rejected_by`） |
| `L132` `historical_place_names.(derived)` → `record_status`，`literal 'staging'`，`staging\|published\|rejected` | 同上；且 `literal 'staging'` 写法下 C25 自动满足（`staging≠rejected` ⇒ `rejected_by` 必为 NULL），但映射行**未表达**该联动 | **改写**：`transform = literal 'staging' + rejected_by=NULL`，notes 补「C25 由本行与 `rejected_by` 行共同满足」；`published` 去留同 Q3 | **`derived`**（① `historical_place_names` 13 列中**无** `record_status`、无 `rejected_by`） |

**D 组必须新增的 2 行**

| 新增行 | 定式（含层级） | 暂存是否真实存在 |
|---|---|---|
| `historical_place_names.(derived)` → `historical_place_name.rejected_by` | `text NULL`，初值 `literal NULL`（本批 0 条 rejected，③ `V0.2.2 §0 R24`：暂存 0 条 rejected / merged / locked）；值域 `auto\|manual`（C26）；与 `record_status` 同生同灭（C25） | **`derived`**（① 暂存 13 列中**无** `rejected_by`）。本批无源列可导，只能按规则置 NULL |
| `historical_place_locations.(derived)` → `historical_place_location.rejected_by` | 同上 | **`derived`**（① 暂存 22 列中**无** `rejected_by`） |

> **① 侧实测支撑（R24 印证）**：暂存 `historical_place_names` / `historical_place_locations` **均无 `record_status` 列、无 `rejected_by` 列**，两表 47,503 / 18,103 行里也**没有**任何 rejected / merged / locked 语义列。⇒ 本批两列的入库值**只能**是 `record_status='staging'` + `rejected_by=NULL`，C25/C26 **构造上自动满足**，无需运行期判定。这一点应当写进 V2.1.1 `IMPORT_RULES`，避免实现者去找一个不存在的暂存列。

---

#### 2.2.E `data_quality_issue`：指纹、批次、计数（**1 失效 + 3 新增**）

**定式依据**（③ `V0.2.2 §2.5.7`，r2 新增，team-lead 裁定 U19，逐字）：

```
content_hash       : sha256   -- 内容身份。导入器算。用于 ordinal 定序、跨版本稳定、重复隔离判定
issue_fingerprint  : md5      -- 台账去重键。PostgreSQL 内算
                              -- （GENERATED ALWAYS AS md5(jsonb_build_array(...)::text) STORED）
                              -- 用于识别"同一问题重复出现"，承载 first_batch_id / last_batch_id / occurrence_count
```

| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |
|---|---|---|---|
| `L176` `data_quality_issues.(derived)` → `data_quality_issue.batch_id`，`bigint`，`Y`，`batch` | V0.2.2 §2.5.7 把单列 `batch_id` 拆为 **`first_batch_id` + `last_batch_id`**，并由 `issue_fingerprint` 承载「同一问题重复出现」的 `occurrence_count`（③） | **拆为两行**：`first_batch_id`（`bigint`，`Y`，`batch`）与 `last_batch_id`（`bigint`，`N`，`batch`） | **`derived`**（① 暂存无 `batch_id` / `first_batch_id` / `last_batch_id`） |

**E 组必须新增的 3 行**

| 新增行 | 定式（含层级） | 暂存是否真实存在 |
|---|---|---|
| `data_quality_issues.(derived)` → `data_quality_issue.occurrence_count` | `integer`，`NOT NULL DEFAULT 1`；同一 `issue_fingerprint` 每批重复出现则 `+= 1`（③ `§2.5.7`、`CHANGELOG:190`） | **`derived`**（① 暂存 11 列中**无**） |
| `data_quality_issues.(derived)` → `data_quality_issue.issue_fingerprint` | **PostgreSQL 生成列**，非导入器写入：`GENERATED ALWAYS AS md5(jsonb_build_array(...)::text) STORED`（③ `§2.5.7`） | **`derived`**（① 暂存 11 列中**无** `issue_fingerprint`）；构成要素只能取自暂存的 11 列 |
| `data_quality_issues.(derived)` → `data_quality_issue.first_batch_id` | `bigint`，`Y`，= 本批 `batch_id`（与 `L176` 原值同源） | **`derived`**（① 暂存无） |

> **⚠ E 组算法更正（与任务书口径的差异，须点名）**：
> 任务书写「`issue_fingerprint` **改 JSON 数组编码**」——**编码**部分正确（`jsonb_build_array(...)::text`），但必须一并写明：**算法是 `md5`，且 V0.2.2-r2 已明确裁定不得改为 `sha256`**。
> ③ 依据：`V0.2.2 §2.5.7` 标题即「两种摘要算法并存是**有意设计**，不可互换、不可统一（r2 新增，team-lead 裁定 U19）」；§5.2 断言 `ALG-1`；`CHANGELOG` R2-03（第 835–842 行）与 r2 裁定表第 19 行：「**`issue_fingerprint` 保持 md5**……改算法会使 **197 条已算历史指纹全部对不上**」。
> ⇒ V2.1.1 的 `FIELD_MAPPING` / `CORE` / `SQL` 三处若把 `issue_fingerprint` 写成 `sha256`，**即判 FAIL**。同理，`content_hash` 必须是 **sha256**（`§2.5.6` 规范定义），两者**不得互换**。

> **⚠ E 组实测缺口：`L174` 的 fallback 无源列可实现（① 实测）**
> `L174` notes 写「有 `source_record_id` 则 join 取；**数据集级问题按 `raw_file` 归属**」。
> 但①实测：`data_quality_issues.csv` 只有 **11 列**（`issue_id`/`source_id`/`source_dataset`/`source_record_id`/`issue_type`/`severity`/`field_name`/`observed_value`/`expected_rule`/`action_taken`/`notes`），**没有 `raw_file` 列**，也没有 `dataset_id` 列。而 `source_record_id` 有 **6 行空值**（12,625/12,631 非空）。
> ⇒ 这 6 行**既无 `source_record_id` 可 join，也无 `raw_file` 可归属**，`L174` 的 `dataset_id`（`required=Y`）**无解**。V2.1.1 必须为这 6 行显式补一条规则（或判定为整批 failed / 落 `source_id` 级兜底），否则 `required=Y` 写不进去。见 §2.6 Q4。

**① 侧实测：`issue_fingerprint` 的可用构成要素**（暂存 11 列的实测基数，供架构师选段）：

| 暂存列 | 非空 / 总 | 唯一值 | 是否适合入指纹 |
|---|---:|---:|---|
| `issue_type` | 12,631 / 12,631 | **13** | ✅ 主段 |
| `severity` | 12,631 / 12,631 | 3（`info`/`blocking`/`warning`） | ✅ |
| `field_name` | 12,631 / 12,631 | **17**（含 `BEG_RULE\|END_RULE` 复合写法） | ✅ |
| `observed_value` | 12,304 / 12,631 | 3,406（**327 行空**） | ⚠️ 空值需约定 |
| `expected_rule` | 12,631 / 12,631 | 16 | ✅ |
| `action_taken` | 12,631 / 12,631 | 3（`preserved_and_flagged`/`needs_manual_review`/`discarded`） | ✅ |
| `source_record_id` | 12,625 / 12,631 | 12,504（**6 行空**） | ⚠️ 空值需约定 |
| `notes` | 12,631 / 12,631 | 50 | ❌ 自由文本，不建议 |

---

#### 2.2.F `record_scope` 值域收敛为 4 值，**不得出现 `connection`**（**2 失效**）

**定式依据**（③ `V0.2.2 §2.7.2` R21、§0 N10、`§2.7.3` A12）：
「`record_scope` 全域只有 **4 种**（R21，**无第五种**）」，「出现第五种 ⇒ 整批 `failed`（不默认放行）」。

| V2.1 映射行 | 失效原因（含层级） | V2.1.1 应有处置 | 暂存是否真实存在 |
|---|---|---|---|
| `L35` `source_records.external_id_type` → `(derived)` `record_scope`，notes「**16 种取值** → 4 个 scope，逐条查表，不猜」 | **notes 与实测不符**：① 实测 `external_id_type` **只有 11 种**，不是 16 种（详见 §2.3 D-3）。「16 种」若被 V2.1.1 沿用，会让实现者去找 5 个不存在的取值 | **改写 notes 为 11 种**，并按 §2.3 的 11→4 查表逐条列全 | **存在**（①）：29,391/29,391 非空、唯一 **11** |
| `L44` `source_records.(derived)` → `source_record.record_scope`，`Y`，`lookup(dataset_id, external_id_type)`，`place\|location\|name\|edge` | 行本身保留，但：① 查表基数由 16 改为 **11**（同上）；② 判据由 V2.1 的「`external_id_type` 查表」升级为 V0.2.2 §2.7.1 **白名单 + 数据集显式声明**（`data_dataset.place_grain`）；③ 值域**必须**是 4 值，任何 `connection` 字面量出现即 FAIL | **改写**：`enum_rule` 保持 4 值；`transform` 改为 `lookup(11→4 查表) + §2.7.1 白名单`；notes 补「`external_id_type` 中的 `pleiades_connection_id` 映射到 **`edge`**，**不是** `connection`；值域外取值 ⇒ A12 整批 failed」 | **`derived`**（① 暂存 14 列中**无** `record_scope`） |

**① 实测的 11 → 4 权威查表**（`source_records` 29,391 行逐行实算，与 ③ `V0.2.2 §2.7.2` N10 完全闭合）

| `external_id_type` | 行数 | → `record_scope` | 所属 `dataset_id` |
|---|---:|---|---|
| `chgis_sys_id` | 15,748 | `place` | `chgis_v6_prefecture_points` 5,226 + `chgis_v6_county_points` 10,522 |
| `pleiades_place_id` | 2,643 | `place` | `pleiades_gis_4_1_slice` |
| `whg_source_id` | 5 | `place` | `whg_geoname_s_gn_sample` 4 + `whg_getty_tgn_sample` 1 |
| `whg_place_id` | 2 | `place` | `whg_hgis_de_las_indias_sample` |
| **place 小计** | **18,398** | | = ③ N10 的 18,398 ✓ |
| `pleiades_name_id` | 4,579 | `name` | `pleiades_gis_4_1_slice` |
| `mcgd_nameid` | 960 | `name` | `mcgd_zenodo_22094815_head960` |
| `whg_place_name_index` | 223 | `name` | WHG 三个数据集（201 + 19 + 3） |
| **name 小计** | **5,762** | | = ③ N10 的 5,762 ✓ |
| `pleiades_location_id` | 2,460 | `location` | `pleiades_gis_4_1_slice` |
| `whg_geometry` | 5 | `location` | `whg_geoname_s_gn_sample` 4 + `whg_getty_tgn_sample` 1 |
| `whg_geom_index` | 3 | `location` | `whg_hgis_de_las_indias_sample` |
| **location 小计** | **2,468** | | = ③ N10 的 2,468 ✓ |
| `pleiades_connection_id` | 2,763 | **`edge`**（**非 `connection`**） | `pleiades_gis_4_1_slice` |
| **edge 小计** | **2,763** | | = ③ N10 的 2,763 ✓ |
| **总计** | **29,391** | | = ① 实测总行数 ✓ |

> **四条闭合校验全部通过**（① 侧逐项与 ③ N10 对碰，0 偏差）：place 18,398 / name 5,762 / location 2,468 / edge 2,763，合计 29,391。

> **`connection` 判定式（可直接实现）**：V2.1.1 的 `FIELD_MAPPING` / `CORE` / `IMPORT_RULES` / `SQL` 中，正则 `record_scope\s*(=|IN\s*\(|::)\s*'?connection` 的命中次数 **== 0**；且 `record_scope` 的枚举声明处必须恰好含 4 个值 `place`/`name`/`location`/`edge`。

> **命名陷阱（实现者易踩，① 实测）**：`whg_place_name_index` 名字里有 `place`，但它映射到 **`name`** scope（223 行）；`whg_place_id`（2 行）才映射到 `place`。这正好印证 `L35` 原 notes 的「**逐条查表，不猜**」——V2.1.1 必须把 11 条逐条写出来，不得按名字子串推断。

---

### 2.3 实测发现与文档不一致之处（点名清单）

> 全部为 ① 与 ③ 对碰的结果。凡冲突，**以 ① 为准**。

| # | 不一致项 | ① 实测值 | ③ 文档值 | 影响 | 建议处置 |
|---|---|---|---|---|---|
| **D-1** | `source_record` 新列数 | V2.1 目标表（③ `CORE_DATA_MODEL_V2.1.md:258–273`）**无** `inactive_reason`/`inactive_at`/`inactive_in_batch_id`/`duplicate_ordinal`；暂存（①）亦 4 列全无 ⇒ 至少需新增 4 列 | ③ `V0.2.2 §1` §0/§4第11项/CHANGELOG 三处逐字写「新列 **+2**（仅 `rejected_by` × 2 表）」，但 §2.3.1/§2.3.2/§2.2.4 已引用这 4 列 | **定式自相矛盾**：`IMPORT_RULES` 第 0 行判定表与 `v_place_liveness` 视图无字段可写 | 请架构师裁定并统一「新列数」口径（§2.6 Q5） |
| **D-2** | `historical_place.dataset_id` | ① 暂存 15 列中**无**；③ V2.1 §5.2.1 规则 1 明令「不带 dataset 列」 | ③ `V0.2.2 §2.2.2` 第 203 行视图 SQL 逐字写 `ON sr.dataset_id = p.dataset_id`，依赖该列存在 | **视图无法编译**；且与 V2.1 既有决策直接冲突 | 二选一：加列并修订 §5.2.1 规则 1，或改视图为 `JOIN source_record`（§2.6 Q6） |
| **D-3** | `external_id_type` 取值种类数 | ① **11 种** | ③ `V2.1 FIELD_MAPPING L35` notes 写「**16 种取值**」 | 实现者会去找 5 个不存在的取值；`A12` 的「第五种 ⇒ 整批 failed」判据基数错 | 改为 11 种，并按 §2.2.F 查表逐条列全 |
| **D-4** | `historical_place.record_status` 值域 | ③ V2.1 目标表 CHECK = **4 值**（`staging`/`published`/`merged`/`rejected`，`CORE_DATA_MODEL_V2.1.md:338`）；① 暂存唯一 1 值 = `staging` | ③ `V0.2.2 §2.1.1` 标题写「**3 值，不变**」 | 「不变」与 V2.1 的 4 值 CHECK 不符 ⇒ `published` 去留未声明 | 请架构师显式裁定（§2.6 Q3） |
| **D-5** | `parent_external_id` 派生覆盖率 | ① 29,391 行中仅 **10,765 行**（36.6%）能从 `raw_payload_json` 取到 `place_id` / `LocID`；**18,626 行取不到** | ③ `V0.2.2 §2.5.0` C29② 只写了「无父级概念的数据集（**CHGIS place**）写入哨兵 `'-'`」，覆盖 15,748 行 | **2,878 行无规则可依**（详见 §2.4） | 请架构师补齐其余 2,878 行的规则（§2.6 Q7） |
| **D-6** | `data_quality_issue.dataset_id` 的 fallback | ① `data_quality_issues` 11 列中**无 `raw_file`、无 `dataset_id`**；`source_record_id` **6 行空** | ③ `V2.1 L174` notes「数据集级问题按 **`raw_file`** 归属」 | 这 6 行 `dataset_id`（`required=Y`）**无解** | 补规则或判整批 failed（§2.6 Q4） |
| **D-7** | `issue_fingerprint` 算法 | —（生成列，暂存无此列，① 无法验） | ③ `V0.2.2 §2.5.7` + `CHANGELOG R2-03` + §6 r2 裁定 19：**保持 `md5`**，明令不得改 `sha256` | 若 V2.1.1 误写 `sha256` ⇒ 197 条已算历史指纹全失效 | 三处（CORE / SQL / 映射）逐字写 `md5`，并加 `ALG-1` 断言 |
| **D-8** | `candidate_matches` 行数 | ① **53,137 行 × 19 列** | ③ V0.2.2 §0 权威数字表**未列** `candidate_match` | 缺一张表的基线行数 | 建议补入 §0 或明确「不入权威表」 |

---

### 2.4 `parent_external_id` 派生覆盖率（**D-5 的展开，① 逐行实算**）

C29 把 `parent_external_id` 定为五段键的**必需段**且禁止 NULL，但暂存 CSV **没有这一列**，只能从 `raw_payload_json` 派生。下表按 `(dataset_id, external_id_type)` 交叉统计实测覆盖率：

| `dataset_id` | `external_id_type` | `record_scope` | 总行 | 可取到 | **取不到** | 命中键 |
|---|---|---|---:|---:|---:|---|
| `chgis_v6_county_points` | `chgis_sys_id` | place | 10,522 | 0 | **10,522** | — |
| `chgis_v6_prefecture_points` | `chgis_sys_id` | place | 5,226 | 0 | **5,226** | — |
| `mcgd_zenodo_22094815_head960` | `mcgd_nameid` | name | 960 | **960** | 0 | `LocID` |
| `pleiades_gis_4_1_slice` | `pleiades_name_id` | name | 4,579 | **4,579** | 0 | `place_id` |
| `pleiades_gis_4_1_slice` | `pleiades_connection_id` | edge | 2,763 | **2,763** | 0 | `place_id` |
| `pleiades_gis_4_1_slice` | `pleiades_place_id` | place | 2,643 | 0 | **2,643** | — |
| `pleiades_gis_4_1_slice` | `pleiades_location_id` | location | 2,460 | **2,460** | 0 | `place_id` |
| `whg_geoname_s_gn_sample` | `whg_place_name_index` | name | 201 | 0 | **201** | — |
| `whg_geoname_s_gn_sample` | `whg_source_id` | place | 4 | 0 | **4** | — |
| `whg_geoname_s_gn_sample` | `whg_geometry` | location | 4 | 0 | **4** | — |
| `whg_getty_tgn_sample` | `whg_place_name_index` | name | 19 | 0 | **19** | — |
| `whg_getty_tgn_sample` | `whg_source_id` | place | 1 | 0 | **1** | — |
| `whg_getty_tgn_sample` | `whg_geometry` | location | 1 | 0 | **1** | — |
| `whg_hgis_de_las_indias_sample` | `whg_place_name_index` | name | 3 | 0 | **3** | — |
| `whg_hgis_de_las_indias_sample` | `whg_geom_index` | location | 3 | **3** | 0 | `place_id` |
| `whg_hgis_de_las_indias_sample` | `whg_place_id` | place | 2 | 0 | **2** | — |
| **合计** | | | **29,391** | **10,765** | **18,626** | |

**按 `record_scope` 汇总**

| `record_scope` | 总行 | 可取到 | **取不到** | 覆盖率 | C29② 是否覆盖 |
|---|---:|---:|---:|---:|---|
| `place` | 18,398 | 0 | **18,398** | 0% | ⚠️ **仅覆盖 CHGIS 的 15,748 行** |
| `name` | 5,762 | 5,539 | **223** | 96.1% | ❌ **未覆盖**（WHG 223 行） |
| `location` | 2,468 | 2,463 | **5** | 99.8% | ❌ **未覆盖**（WHG 5 行） |
| `edge` | 2,763 | 2,763 | 0 | 100% | —（不适用，本身有 `place_id`） |

**结论（① 实测）**：

1. **C29② 只覆盖了 15,748 / 18,626 = 84.6% 的「取不到」行，仍有 2,878 行无规则可依。**
2. 未覆盖的 2,878 行构成：`pleiades_place_id` **2,643** + `whg_place_name_index` **223** + `whg_geometry` **5** + `whg_source_id` **5** + `whg_place_id` **2**。
3. **尤其要注意 `place` scope 的 0% 覆盖率**：18,398 行 `place` 记录**全部**取不到父级——这不是缺陷，而是 `place` 记录本身就是实体（不是某实体的子行）。但 C29① 禁止 NULL，所以**全部 18,398 行都必须落哨兵或其它规则**，而 C29② 只说了「CHGIS place」。Pleiades place（2,643）与 WHG place（7）**口径缺失**。
4. ① 侧可交叉印证 ③ 的正确部分：V2.1 `CORE_DATA_MODEL_V2.1.md:298` 写「Pleiades 9,802 行全有；MCGD 960 行全有」——① 实测 **Pleiades 命中 9,802 / MCGD 命中 960**，**逐项吻合**。⇒ ③ 的这条是对的，错的只是它没说清剩下 18,626 行怎么办。

---

### 2.5 已核、**无** V2.1.1 驱动变更的表

| 表 / 映射行段 | 核实结论 | ① 实测支撑 |
|---|---|---|
| `candidate_match`（`L139–L162`，24 行） | V0.2.2-r2 全篇**未对 `candidate_match` 提出任何结构变更**。⇒ 24 行**全部维持 V2.1 原样**，本轮 0 失效 / 0 新增 | `candidate_matches` **53,137 行 × 19 列**；`relation_type` 唯一 **6 值**（③ V2.1 `L140` 枚举报 7 值 ⇒ 6/7 出现，属正常，非 V2.1.1 变更）；`reviewer` / `reviewed_at` **53,137 行 100% 空、唯一值 0** ⇒ 印证 `L156`/`L157` 的 `derived` 判定；`status` 唯一 2 值（`candidate` / `needs_manual_review`） |
| `import_batch`（`L183–L200`，18 行） | V0.2.2 §2.4 只改**统计口径**（R1 减 `N_quar`、`failed_count`；R2 只统计回滚相关台账类型），**未改表结构** ⇒ 18 行维持原样，但 `L193 quarantined_count` / `L195 failed_count` 的 **notes 须按 R1 口径改写** | — |
| `data_source`（`L201–L208`，8 行） | 除 `L204 license_homepage` 待裁定（§2.6 Q1）外，其余 7 行维持原样 | — |
| `data_dataset` 非许可列（`L2/L3/L4/L12/L13/L18–L29`，15 行） | 维持原样。`L19 place_grain` 的 `enum_rule` 由 3 值收敛为 2 值属 **V2.1 已完成的收敛**（③ `CORE_DATA_MODEL_V2.1.md:136/154`），不计入本轮 | `data_datasets` **7 行 × 11 列** |

---

### 2.6 待架构师裁定项（QA 不下判定，只列事实与选项）

> **本清单不是「已发现问题」的终审结论**，而是 V2.1.1 编制前**必须先有答案**的 7 个问号。每一条都给出了 ① 实测事实与可选处置，由架构师定夺。

| # | 问题 | ① 实测事实 | 可选处置 |
|---|---|---|---|
| **Q1** | `data_source.license_homepage`（`L204`）是否随 9 列一并删除？ | ③ `V0.2.2 §3.3` 只约束 `DATA_PROVENANCE` 文档与 `data_dataset` 的 9 列，**未提及 `data_source`** | (a) 一并删除（彻底无许可语义）；(b) 保留但改名（改名即触 §3.3「任何替代字段」）；(c) 保留原名并写明「仅展示链接、不构成许可判定」 |
| **Q2** | `data_datasets.acquisition_method`（`L10`）失去 `license_evidence` 落点后怎么办？ | ① 7/7 非空、唯一 6，内容是取数方式（如 `full DBF + sidecars read from the shipped V6 zip`） | (a) 整列 dropped；(b) 落 `data_dataset.notes`（但会与 `L12 notes` 冲突，须定合并规则）；(c) 新增**非许可**目标列 |
| **Q3** | `historical_place` / `_name` / `_location` 的 `record_status` 是否保留 `published`？ | ① 暂存唯一 1 值 = `staging`；③ V2.1 CHECK 为 4 值含 `published`，③ V0.2.2 §2.1.1 称 3 值 | (a) 统一为 3 值（删 `published`，同步改 4 处 CHECK：`CORE:338` / `CORE:479` / `CORE:483` / `CORE:484`）；(b) 统一为 4 值并更正 V0.2.2 §2.1.1 标题 |
| **Q4** | `data_quality_issue.dataset_id` 对 6 行「无 `source_record_id`」如何取值？ | ① `data_quality_issues` 无 `raw_file` 列、无 `dataset_id` 列；`source_record_id` 6 行空 | (a) 按 `source_id`（4 值）落到 `data_source` 级并拒绝入库；(b) 整批 failed（同 A12）；(c) 落 `dataset_id = NULL` 并放宽 `required`（会破坏 `L174` 的 NOT NULL） |
| **Q5** | `source_record` 是否新增 `inactive_reason` / `inactive_at` / `inactive_in_batch_id` / `duplicate_ordinal` 四列？ | ① 暂存 14 列中 4 列全无；③ V2.1 目标表 4 列全无；③ V0.2.2 §1 写「新列 +2」但正文已引用这 4 列 | (a) 加 4 列，§1 合计更正为 **+6**；(b) 不加，`v_place_liveness` 与判定表第 0 行改用其它表达（须重写 §2.2.4 与 §2.3.1） |
| **Q6** | `historical_place.dataset_id` 加不加？ | ① 暂存无；③ `V0.2.2 §2.2.2:203` 视图依赖它；③ `V2.1 CORE:176` 规则 1 禁止它 | (a) 加列 + 修订 V2.1 §5.2.1 规则 1；(b) 不加列，视图改为 `JOIN source_record sr ON sr.source_record_id = p.created_from_source_record_id`（不改表结构，但 SQL 需重写且失去 `dataset_id` 直连能力） |
| **Q7** | 未覆盖的 2,878 行 `parent_external_id` 怎么填？ | ① `pleiades_place_id` 2,643 + `whg_place_name_index` 223 + `whg_geometry` 5 + `whg_source_id` 5 + `whg_place_id` 2 | (a) 全部落哨兵 `'-'`（与 CHGIS place 一致，最简单且与 C29④ 的「常量表声明一次」兼容）；(b) WHG 的 `whg_place_name_index` 另行从 `raw_payload` 取父键（① 实测其 payload 顶层键无 `place_id`/`LocID`，不可行 ⇒ 只能取 (a)） |

---

### 2.7 本节的可直接实现判定式（供 V2.1.1 交付物扫描）

| # | 判定式 | FAIL 条件 | 来源层级 |
|---|---|---|---|
| **M1** | `FIELD_MAPPING_V2.1.1.csv` 的 `target_column` 列，正则 `^(attribution\|citation\|license)_` 命中行数 | `> 0` 即 FAIL（§2.2.A） | ③ §3.3 + ① 列清单 |
| **M2** | `FIELD_MAPPING_V2.1.1.csv` 是否含 `target_column = grain_key` 的行 | `> 0` 即 FAIL（`grain_key` 已废弃） | ③ §2.7.2:750 + CHANGELOG:271 |
| **M3** | `record_scope` 枚举声明处的值个数 | `!= 4` 或含 `connection` 即 FAIL | ① 11→4 查表 + ③ N10 |
| **M4** | `issue_fingerprint` 定义处是否写 `md5` | 写成 `sha256` 或缺失即 FAIL | ③ §2.5.7 + CHANGELOG R2-03 |
| **M5** | `content_hash` 定义处是否写 `sha256` | 写成 `md5` 即 FAIL | ③ §2.5.6 |
| **M6** | `parent_external_id` 行的 `required` 列 | `!= Y` 或 notes 含「NULL 兜底」即 FAIL | ③ C29① + ① 覆盖率表 |
| **M7** | `source_record` 是否有 `inactive_reason` / `inactive_at` / `inactive_in_batch_id` / `duplicate_ordinal` 四行的定义 | 缺失任一即 FAIL（§2.2.4 / §2.3.1 依赖） | ③ §2.3.1、§2.3.2、§2.2.4 |
| **M8** | `historical_place_name` / `_location` 是否有 `rejected_by` 行，且值域为 `auto\|manual` | 缺失或值域不符即 FAIL | ③ §2.2.1 C25/C26 |
| **M9** | `external_id_type` 的 notes 是否写「11 种」并逐条列全 11 条 → 4 值 | 写「16 种」或条目数 `!= 11` 即 FAIL | ① 实测 |
| **M10** | `data_quality_issue` 是否有 `first_batch_id` / `last_batch_id` / `occurrence_count` / `issue_fingerprint` 四行 | 缺失任一即 FAIL | ③ §2.5.7 |

---

### 2.8 本节结论与边界声明

- **本节是「预判」，不是「验收」。** 预判对象是 V2.1 的 207 条映射行在 V2.1.1 定式下的存废，判据来自 V0.2.2-r2 定式正文（③）与七张暂存 CSV 的逐行实算（①）。
- **本节不对任何尚未产出的交付物下判定。** `FIELD_MAPPING_V2.1.1.csv` 尚未编制，§2.7 的 M1–M10 是**给未来扫描用的判据**，不是当前扫描结果。
- **本节不宣布通过。** §2.3 的 8 条不一致（D-1 ~ D-8）与 §2.6 的 7 个待裁定项（Q1 ~ Q7）**全部处于未决状态**，需架构师在编制 V2.1.1 时逐条回应。
- **行数口径**：V2.1 映射表 **208 行 = 1 表头 + 207 数据行**（① 实测，与任务书「208 行」口径一致）。本节差异行合计 **35 行**（失效 20 / 新增 10 / 连带 5）。
- **可复现性**：本节全部 ① 类数字可由本目录三个脚本原样重算——`staging_field_inventory.py`（逐列统计）、`verify_v211_gaps.py`（字段存在性与值域）、`probe_parent_external_id.py`（父键覆盖率交叉表）。

