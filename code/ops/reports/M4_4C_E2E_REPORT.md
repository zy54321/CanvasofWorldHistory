# M4-4c · Pleiades 4.1 前端 E2E 与全量回归 验收报告

日期：2026-11-04
状态：**M4-4c 完成，等待 Owner 验收。未进入 M4-5。**
被测库：`canvas_history_m4_4b`（M4-4b 验收库，**未重建、未重导入、未改动**）
应用实例：前端 `127.0.0.1:5180` → 代理 → `127.0.0.1:8089` → `canvas_history_m4_4b`（**只读，写白名单为空**）

---

## 一、结论

| 任务 | 结论 | 判据 |
|---|---|---|
| 一 · 地图 E2E | **PASS** | API 61 条 + 浏览器 21 条，全部通过 |
| 二 · 搜索与详情 E2E | **PASS** | 见 §四、§五 |
| 三 · 时间轴 E2E | **PASS**（10 个样本逐个验，已排除已知冲突地点） | 见 §六 |
| 四 · 人工保护回归 | **三档机制 PASS**；「管理界面编辑是否受保护」**FAIL（既有产品缺陷，已报）** | 见 §七 |
| 五 · M0–M3 完整回归 | **PASS** | M0/M1 15/15、M2 14/14、M3 56/56、M4 遗留 9/9 |
| 验收库数据指纹 | **PASS**：既有四源指纹与 M4-4b 交付时逐字节一致 | 见 §九 |

**统计**：API 61 / UI 21 / M0M1 15 / M2 14 / M3 56 / M4 9 = **176 条判据，176 条通过**，
另有 1 条**独立缺陷结论（FAIL）**：管理界面改地点后不写保护位（§七.3），不属"回归失败"，
而是本轮实测到的**既有产品行为**，按施工边界"必须停止并报告"，未擅自修改。

**本轮修了 2 处前端缺陷**（同一根因、两处代码）：无坐标地点会让搜索结果列表与地图定位抛
`pageerror`。这是 Pleiades 4.1 引入 7,200 个"有名字、无坐标"地点后**第一次被真实踩到**的问题。
详见 §八。

---

## 二、施工前检查

| 项 | 结果 |
|---|---|
| Git | 分支 `m4-3-pleiades-gis`，HEAD `ed9752a`，工作区仅 `汇报/` 未跟踪 |
| M4-4b 提交 | `4459b63`（代码）、`ed9752a`（报告）均在 |
| `canvas_history_m4_4b` | 存在，Flyway **V9**，157,220 源记录 |
| `canvas_history_m4_4b_protect` | 存在（M4-4b 留下 3 个受保护地点） |
| PostgreSQL / PostGIS | 17.11 / 3.6（GEOS 3.14.1），容器 healthy |
| 后端 | 8089 启动，`/api/v1/meta/health` → `"database":"canvas_history_m4_4b"` ✅ |
| 前端 | 5180（Vite 6.0.7），`/api` 代理指向 8089 ✅ |
| MapTiler | key 存在，M0-02 走真实底图（`Streets / Satellite / Satellite Hybrid / Outdoor`）✅ |
| 误连正式库风险 | 已排除：health 回报库名；且 8089 实例写白名单为空，`POST/PUT` 一律 **403**（实测） |

**清理动作（必须记录）**：环境里残留着上一轮遗留的 2 个 API（8088/8089，其中一个连的是
`canvas_history_m2check`）与 3 个 Vite 实例。若直接复用，E2E 会**测到错误的库**。
已 `Stop-Process` 全部清掉，重新按上表启动，并以 `health.database` 作为唯一判据确认连接。

测试前基线（`ops/m4-4c/24_snapshot_after_e2e.log`，口径同 M4-4b：扣掉 `updated_at` /
`last_batch_id` / `occurrence_count`，几何用 `ST_AsEWKB`）：

| 表 | 行数 | sha256（前 16） |
|---|---:|---|
| source_record | 157,220 | `fc06a8ffbb332516` |
| historical_place | 57,967 | `e69a22790b7a0672` |
| historical_place_name | 84,554 | `566a9604a13d45f1` |
| historical_place_location | 53,792 | `61717dcc7f0c84fb` |
| candidate_match | 66,311 | `549cf610a2e4f033` |
| data_quality_issue | 21,447 | `81b6f066b2f5da8e` |
| data_dataset | 9 | `b12bde5d5fb4b8b7` |

---

## 三、任务一 · 地图 E2E

### 3.1 罗马区域（API 层，E1/E2）

| 判据 | 结果 |
|---|---|
| `GET /api/v1/places/map?bbox=12.30,41.70,12.60,42.00&limit=2000` | **HTTP 200**，返回 603 条 |
| `meta.returned` 与 `features` 长度一致 | 603 = 603 ✅ |
| `meta.totalInBbox` 与库内 `ST_Intersects` 计数一致 | 603 ✅ |
| 面/线来源的 6 个样本全部出现在结果中 | 6/6 ✅ |
| 全部要素坐标在合法经纬度范围 | 0 越界 ✅ |
| 面/线地点的地图坐标 = 库内 `representative_lon/lat` | 逐点相等（1e-9）✅ |
| 库内 `geom_type` 与夹具一致（Polygon / MultiPolygon / LineString） | ✅ |

罗马 bbox 内的 v4.1 地点（库内实计）：**Polygon 45 个 / LineString 206 个 / Point 357 个**。

### 3.2 罗马区域（浏览器，U2）

`map.fitBounds(罗马 bbox)` 后读 `places` 图层：**400 个要素**，6 个样本中 **5 个**进入图层
（第 6 个 `150063 Sabini` 的代表点落在 bbox 外——它的多边形与 bbox 相交但面内点在框外，
属产品既定口径：地图按**几何相交**取地点、按**代表点**落标记）。

### 3.3 面与线（U3/U4、E3）

| 判据 | 结果 |
|---|---|
| 面地点 `150130 Velini (lake)` 详情可打开 | ✅ 4 条位置（Point×3 + Polygon×1） |
| 线地点 `153964 Delkon (river)` | ✅ 4 条位置（LineString + Polygon） |
| `geom_type ≠ Point` 是否引发异常 | 无 0 次 ✅ |
| 详情位置行渲染 geomType 相关字段 | API 返回 `geomType`；面板展示「定位精度 / 坐标系置信 / 有效期」，不单列 geomType（见 §十 UNVERIFIED 说明） |
| 位置条数 | 4 / 4 ✅ |

### 3.4 无坐标地点（U5、E4）

样本：`136043 Magnata`（v4.1、无任何位置行）。

| 判据 | 结果 |
|---|---|
| 名称搜索可命中 | ✅（`Magnata` → 136043） |
| 详情可打开 | ✅ 标题 `Magnata`，位置 0 条，显示「**无位置记录**」 |
| 地图上不出现该地点 | ✅ 点击后 `places` 图层里不含 136043（没有虚构坐标） |
| 不产生前端异常 | **修复前 FAIL → 修复后 PASS**（见 §八） |

---

## 四、任务二 · 搜索 E2E

| 判据 | 结果 |
|---|---|
| `Athens`（v4.1 主名）命中 `157338 Athenae` | ✅ |
| `Pompeii` 命中 `150913 Pompeii` | ✅ |
| 结果定位正确（id 与库一致、正名/纪年同屏） | ✅ `Athens｜正名 Athenae · settlement · 1700 – 2100` |
| 详情打开 | ✅ 两者均 HTTP 200 |
| 多条位置展示 | ✅ `150130` 4 条、`153964` 4 条 |
| **precise / rough 不整体降级** | ✅ 3 precise + 1 rough，UI 原文展示 `precise` / `rough`（不是 `unknown`） |
| 来源可追溯至 Pleiades 4.1 | ✅ 数据集 `Pleiades Datasets v4.1 — GIS CSV (complete package)`、版本 4.1、来源 `pleiades`、`sourceRecords` 7 条且 `rawFile ∈ {places.csv, names.csv, location_points.csv, location_linestrings.csv, location_polygons.csv, connections.csv}` |
| 地点基本信息 / 时间信息 | ✅ 正名、类型、精度、有效期、记录状态齐全 |

---

## 五、任务三 · 时间轴 E2E

**样本选择规则**（`ops/m4-4c/make_fixtures.py`，可复跑）：
v4.1 数据集内、**只有 1 条名称**（避免多条名称的时间窗互相覆盖导致年份过滤出现歧义）、
该名称有完整纪年、**不在 820 条 `derived_value_mismatch` 涉及的地点内**、
有可用几何；按 `md5(place_id)` 排序取 10 个。候选池 31,188 → 实际取 10。

| # | place_id | 名称 | 有效年（天文） | 命中 | 不命中 | 纪年一致 |
|---:|---|---|---|---|---|---|
| 1 | 153006 | Diabolis | -29 ~ 640 | -29 ✅ | 641 ✅ | ✅ |
| 2 | 160033 | Φάσηλις | -549 ~ 640 | -549 ✅ | 641 ✅ | ✅ |
| 3 | 158808 | Etsyena | -29 ~ 300 | -29 ✅ | 301 ✅ | ✅ |
| 4 | 172861 | باش تبة | 1700 ~ 2100 | 1700 ✅ | 2101 ✅ | ✅ |
| 5 | 174534 | Necropoli di San Placido | 1700 ~ 2100 | 1700 ✅ | 2101 ✅ | ✅ |
| 6 | 160064 | Sanaos L. | -329 ~ 640 | -329 ✅ | 641 ✅ | ✅ |
| 7 | 153743 | Stageira | -549 ~ -329 | -549 ✅ | -328 ✅ | ✅ |
| 8 | 158363 | Kybersos | -329 ~ -29 | -329 ✅ | -28 ✅ | ✅ |
| 9 | 154176 | Blachernai | -29 ~ 640 | -29 ✅ | 641 ✅ | ✅ |
| 10 | 171181 | Arcadian Gate | 1700 ~ 2100 | 1700 ✅ | 2101 ✅ | ✅ |

- BCE 7 条 / CE 3 条，两侧都覆盖。
- **BCE/CE 转换**：天文年 `-549` 在界面上显示为「前 550」（`1 - astro`），不出现公元 0 年；
  浏览器实测 `settlement · 前 30 – 640` ✅。
- **地图与时间轴同步**：10 个样本中前 5 个，用各自代表坐标构造 0.1° bbox 查询，全部能在
  地图接口里查得 ✅（E9）。
- **口径限制（如实记录）**：产品的时间过滤作用在**名称**的有效期上（`/places?year=`），
  地图接口本身不带年份参数；因此"时间轴过滤"在 API/搜索层验证，"地图同步"验证的是
  "被过滤命中的地点能在其坐标处被地图查到"，不是"地图按时段重绘"。这一点在 M1 阶段
  就是既定设计，本轮未改产品。

**已知遗留未触碰**：820 条 `derived_value_mismatch` / 629 个地点的地点级时间包络口径问题，
本轮**按指令不改**；时间样本已主动排除这些地点，避免用已知有争议的数据当判据。

---

## 六、任务四 · 人工保护回归

测试域：**`canvas_history_m4_4b_protect`（独立副本）**，验收库未被写入（§九已证）。

### 6.1 三档保护机制 —— PASS

| place_id | 保护位 | 测试前 | 系统更新后 | 结论 |
|---|---|---|---|---|
| 135875 | `locked=true` | 人工改名-A | 人工改名-A | 不被覆盖 ✅ |
| 135876 | `created_by='manual'` | 人工改名-B | 人工改名-B | 不被覆盖 ✅ |
| 135877 | `manual_edited_fields={canonical_name}` | 人工改名-C | 人工改名-C | 不被覆盖 ✅ |

- 导入器概览：`新增 0 / 内容变更 1 / 无变化 57,963 / **人工保护跳过 3**（其中名称冲突登记台账 3）`
- `data_quality_issue` 中 `manual_edit_conflict` 3 条，`resolution_note` 逐条写明
  「保护原因 = locked / created_by=manual / manual_edited_fields=canonical_name；库中现值=…；导入值=…」
- 三处 `updated_at` 保持 `2026-11-04 12:00:00+08` 未变 ✅
- 日志：`ops/reports/m4-4c/17_protect.log`

### 6.2 系统更新是怎么做的

在**副本**上重放导入器（`--db canvas_history_m4_4b_protect --staging-dir data/staging_m4_3`）。
没有在验收库上重放，也没有重新导入任何数据到 `canvas_history_m4_4b`。

### 6.3 发现：管理界面编辑**不写**保护位 —— FAIL（既有产品缺陷，未修）

| 步骤 | 结果 |
|---|---|
| 1. 选一个未保护的地点 `135880 Anatis/Asana (river)` | `locked=false, created_by=import, manual_edited_fields={}` |
| 2. 通过管理 API 改名 | `PUT /api/v1/places/135880` → **HTTP 200**，名称变为「M4-4c 人工改名-135880」 |
| 3. 检查保护位 | **仍然** `locked=false, created_by=import, manual_edited_fields={}` |
| 4. 重放导入器 | 「**内容变更 1**」→ 名称被改回 `Anatis/Asana (river)` |

**结论**：三档保护机制本身工作正常，但 `PlaceAdminService.update()` 从不写
`locked` / `manual_edited_fields`（全仓只有 importer 读它们，没有任何代码写它们）。
所以**在管理界面手工修改一个"导入来的"地点，下次导入会被静默覆盖**。

- 代码位置：`PlaceAdminService.update()`（UPDATE 只写 canonical_name/lang/type/basis/desc/notes/updated_at）
- 影响面：只影响"导入数据集的地点"，对 `manual_entry` 地点无影响（导入器不碰它们）
- 是否 Pleiades 引起：**不是**。这条路径在 M2 就存在；只是本轮"人工保护回归"第一次把它测出来
- 为什么没修：给管理界面加"自动写保护位"= 改变产品行为（一个地点编辑后是否永久免疫导入），
  属施工指令 §八「涉及业务语义的修改必须停止并报告」。**已停在此处，等 Owner 决策。**

### 6.4 建议（供决策，未执行）

| 方案 | 含义 | 代价 |
|---|---|---|
| A | `PUT /places/{id}` 时把被改字段并入 `manual_edited_fields` | 改 1 个 service 方法；导入器已支持该语义，无需改库 |
| B | 管理界面加显式「锁定」开关（写 `locked=true`） | 需前端 + 接口，属功能扩展 |
| C | 保持现状，把"导入数据集地点不可在管理界面编辑"做成显式限制 | 需产品确认，否则是静默数据丢失 |

---

## 七、任务五 · M0–M3 完整回归

既有测试集**一个不删、判据一个不改、断言标准一个不降**。

| 套件 | 被测对象 | 结果 | 日志 |
|---|---|---|---|
| `tests/e2e/accept-m0m1.cjs`（M0-01~05、M1-01~04） | 5180 → **m4_4b**（只读） | **15/15 PASS** | `20_m0m1.log` |
| `tests/e2e-manage/m2-ui.cjs`（管理界面 14 项） | 5184 → `canvas_history_m4_4c_m2`（m4_4b 的克隆，可写） | **14/14 PASS** | `22_m2.log` |
| `tests/e2e-m3/m3-ui.cjs`（矩阵/联动 56 项） | 5182 → **m2check**（只读） | **56/56 PASS** | `21_m3.log` |
| `tests/e2e-m4/m4-place-no-source.cjs`（M3 遗留） | 5184 → m4_4c_m2（可写） | **9/9 PASS** | `30_m4_legacy.log` |

### 7.1 为什么 M2 / M3 不在 m4_4b 上跑

| 套餐 | 需要什么 | m4_4b 有没有 | 处理 |
|---|---|---|---|
| M0 / M1 | 地点数据（只读） | 有（57,967） | **直接在 m4_4b 上跑** ✅ |
| M2 | 写权限 + 至少 1 个事件可关联 | 只读；**0 个事件** | 克隆 `canvas_history_m4_4c_m2`（可写），预置 1 条事件（等价于 m2check 上既有的 32 条之一） |
| M3 | 8 个政权 / 12 条事件-政权关联 | **0 条**（m4check 起源库没有 M2/M3 样本数据） | 在 **m2check** 上跑（只读，V8 未变） |
| M4 遗留 | 写权限 | 只读 | 同 M2 的克隆 |

这是本轮最需要说明的一点：**M3 的回归不是在 Pleiades 数据上跑的**，因为验收库没有 M2/M3
的样本数据。M0/M1（地点主链路）确实跑在 Pleiades 全量数据上；M2 跑在"Pleiades 全量 + 可写"
的克隆上；M3 跑在其原生基线 m2check 上。三者合起来覆盖 M0–M3，但**"Pleiades 数据 + 政权矩阵"
这个组合本身没有被 E2E 覆盖**（矩阵只按政权行渲染，不读地点表，逻辑上不受影响）。

### 7.2 关键回归证据（摘）

- M0-02 四种样式：`Streets 1959ms / Satellite 1076ms / Hybrid 938ms / Outdoor 1593ms` 全部就绪，
  每步 `places` 图层均 400 点（与 M3 冻结时同口径）。
- M0-04 四区域：中国/欧洲/中东视野各 400 点，相机落位与 M3 一致。
- M1-01 搜索「长安」8 条、同名不合并（6 个不同 id）；别名「桂林縣」命中；年代筛选 5→1→0。
- M1-02 详情页：`万县` 名称 3 / 位置 1 / 来源 1 / 质量 0，精度 `unknown`（CHGIS 行），与 M1 一致。
- M1-03 `bbox` 接口：`totalInBbox=4905`（比 M3 时的 4,900 量级略增，因为加了 Pleiades 点），
  `limit=99999` 被钳制为 2000 且 `truncated=true`。
- M3-56 项含 BCE 边界（前 2 年）、矩阵地区手风琴、表头零错位、控制台 0 错误。

---

## 八、本轮修复的 2 处前端缺陷（同一根因）

### 8.1 现象

| 位置 | 触发 | 后果 |
|---|---|---|
| `SearchPanel.vue` 搜索结果行 | 命中一个**无坐标**的地点 | 渲染时 `item.lon.toFixed(3)` 抛 `TypeError`，**整个结果列表渲染失败** |
| `App.vue` `onPick()` | 点击一个**无坐标**的地点 | `flyToPlace(undefined, undefined)` → MapLibre 抛 `Invalid LngLat object: (NaN, NaN)` |

### 8.2 根因

接口用 `spring.jackson.default-property-inclusion: non_null` 序列化，无坐标地点的
`representativeLon/Lat` **字段直接不出现**，前端取到的是 `undefined`，不是 `null`。
两处守卫写的是 `!== null`，`undefined !== null` 为真 → 走进"有坐标"分支 → 崩。

### 8.3 为什么现在才出现

Pleiades 4.1 带来 **7,200 个"有名字、无坐标"的地点**（占新地点的 18.5%）。CHGIS/MCGD/WHC
时代没有这种数据，所以这条路径从未被真实踩到。**不是 Pleiades 写坏了代码，是新数据暴露了
一个一直存在的健壮性缺口。**

### 8.4 修复（最小、只碰这两处守卫）

| 文件 | 改动 |
|---|---|
| `frontend/src/components/SearchPanel.vue` | `v-if="item.lon !== null && item.lat !== null"` → `!= null`（并加注释） |
| `frontend/src/App.vue` | `if (item.lon !== null && item.lat !== null)` → `!= null`（并加注释） |

- 不改接口、不改数据、不改产品行为：`v-else` 的「无代表坐标」分支**本来就有**，
  只是永远走不到。修复后它按设计生效。
- 修复前后对照：`pageerror` 从 3 条（每次渲染崩溃）→ **0 条**；U5/U6 从 FAIL → PASS。

---

## 九、数据指纹与边界

### 9.1 验收库未被改动

| 证据 | 结果 |
|---|---|
| 既有四源指纹（`cutoff=14`，同 M4-4b 口径）与 M4-4b 交付逐字节比对 | **完全一致**（7 张表 7 个 sha256）✅ |
| 全库行数 | 157,220 / 57,967 / 84,554 / 53,792 / 66,311 / 21,447 / 9，与 M4-4b 一致 ✅ |
| 8089 实例写白名单 | 为空 ⇒ `POST /places` **403**、`PUT /places/150913` **403**（实测）✅ |
| 人工测试数据 | 只写在 `_protect` 与 `_m2` 两个副本上，验收库 0 条 ✅ |

### 9.2 本轮未做（边界确认）

| 禁止项 | 是否发生 |
|---|---|
| 连接正式库执行写操作 | 否（仅只读 SELECT） |
| 执行新的 Migration | 否 |
| 重新导入 Pleiades 数据到验收库 | 否（只在副本上重放导入器做保护测试） |
| 修改已验收的 staging | 否（`data/staging_m4_3` 未动） |
| 下载新数据 | 否 |
| 新增表/字段/约束 | 否 |
| 扩展产品功能 | 否（只修 2 处空值守卫） |
| 与 E2E 无关的重构 | 否 |
| 修复 M4-5 才处理的数据语义问题 | 否（820 条 mismatch 原样保留） |
| 启动 M4-5 | 否 |

### 9.3 环境里新增的测试副本（不进验收链，可随时删）

| 库 | 用途 |
|---|---|
| `canvas_history_m4_4b_protect` | 人工保护（M4-4b 留下，本轮复跑） |
| `canvas_history_m4_4c_m2` | M2 管理界面回归（可写，含 1 条预置事件 + M2 用例产生的数据） |

验收库 `canvas_history_m4_4b` 保持 M4-4b 交付状态，M4-5 可直接用。

---

## 十、UNVERIFIED（明确未验证，不计入 PASS）

| 项 | 为什么没验 | 影响 |
|---|---|---|
| 详情面板把 `geomType` 单独展示成一行 | 产品没有这个字段位；API 已返回且与库一致 | 无（展示选择，不是缺陷）。"详情能正确识别位置类型"按 API 契约判 PASS |
| 地图渲染 Polygon/LineString 的**真实形状** | 产品只画代表点（`geometry.type = Point`），M1 起就是这样 | 无。面/线地形的可视化是产品演进项，不是本轮回归目标 |
| "Pleiades 数据 + 政权矩阵"组合 | 验收库无政权/事件数据（m4check 起源） | 低：矩阵只按政权行渲染，不读地点表 |
| 搜索结果的**分页**在 38,928 个新地点上的深层翻页 | 只验到第 1/2 页（M1-01e） | 低 |
| MapTiler key 的配额/限流下的长时间稳定性 | 短时 E2E 不覆盖 | 低 |

---

## 十一、已知遗留（沿用 M4-4b，本轮未触碰）

| # | 事项 | 数量 | 处置 |
|---|---|---|---|
| 1 | 地点级时间包络口径不一致（归一化含 connection，导入器排除 edge） | 820 条台账 / 629 地点 | M4-5 前统一口径需重建暂存，本轮按指令不改 |
| 2 | 暂存 `action_taken` 用库外动词 | 732 行 | 导入器映射并保留原值，等下一轮改归一化 |
| 3 | `place_type` 只有 settlement/unknown | 26,383 个 NEW 地点 | 需 `place_type_link` 时再做 |
| 4 | `is_preferred` 全 false | — | 现状可用 |
| 5 | 42 行 `name_lang` → `und` | — | 需保真时加列 |
| 6 | **管理界面编辑不写保护位** | 所有导入地点 | **本轮新增登记**，见 §六.3，需 Owner 决策 |

---

## 十二、交付与 Git

### 12.1 交付目录

`汇报/2026-11-04/<HHMMSS>/`

| 文件 | 内容 |
|---|---|
| `M4-4c_E2E验收报告.md` | 本报告 |
| `M4-4c_源码包.zip` | 本轮改动的 2 个前端文件 + 3 个测试/夹具脚本 + 2 个 SQL + 本报告 |
| `SHA256SUMS.txt` | 报告、源码包、全部日志、JSON、截图的 sha256 |
| `交付说明.md` | 目录导读与复核命令 |
| `logs/` | 10 份测试日志 |
| `evidence/` | 21 张截图（地图/详情/时间轴/矩阵/管理界面）+ 3 份 JSON（fixtures / api_e2e / ui_result） |

### 12.2 代码变更

| 文件 | 类型 |
|---|---|
| `frontend/src/components/SearchPanel.vue` | 修复（1 行 + 注释） |
| `frontend/src/App.vue` | 修复（1 行 + 注释） |
| `ops/m4-4c/make_fixtures.py` | 新增（夹具） |
| `ops/m4-4c/api_e2e.py` | 新增（API E2E 61 条） |
| `tests/e2e-m4c/places-e2e.cjs` | 新增（浏览器 E2E 21 条） |
| `ops/m4-4c/snapshot.sql` | 新增（全库快照） |

未改：后端 Java 代码、`import_staging.py`、`normalize.py`、V1–V9、staging、任何原始数据。

### 12.3 Git

| 项 | 值 |
|---|---|
| 分支 | `m4-3-pleiades-gis`（未开新分支、未推送） |
| 代码提交 | `f5182ec` fix(m4-4c): guard missing coordinates in search and map fly-to, add E2E suite |
| 报告提交 | 本文件所在提交（`docs(m4-4c): …`），见 `git log` |
| 未入库 | `code/ops/reports/m4-4c/*.log`（被 `.gitignore` 的 `*.log` 忽略，日志在交付包内） |

---

**M4-4c STOP / WAITING FOR OWNER ACCEPTANCE（未启动 M4-5）**
