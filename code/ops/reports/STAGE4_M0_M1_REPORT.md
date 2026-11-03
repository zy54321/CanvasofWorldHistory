# 阶段四 M0 + M1 交付报告

生成时间（UTC）：2026-11-03T10:35Z　｜　工作目录：`E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code`

> 本轮只做 M0 地图技术验证 + M1 只读查询，**未执行任何写库操作**，Migration / 九张业务表 / 原始 CSV 全部未变。

---

## 一、结论

| 编号 | 验收项 | 判定 | 证据 |
|---|---|---|---|
| M0-01 | 地图加载、默认全球视野 | **PASS** | center 20,20 / zoom 1.4，canvas 就绪，图层 5 个 |
| M0-02 | 四种样式可用 | **PASS** | 真实 MapTiler 底图：Outdoor / Streets / Satellite / Satellite Hybrid 四样式名互异，Satellite 与 Hybrid 含栅格影像层 |
| M0-03 | 切换样式保留视野 | **PASS** | 116.4,39.9 z6.2 → 四次切换后相机漂移 **0** |
| M0-04 | 中国/欧洲/北美/中东 | **PASS** | 四区域相机均正确落位；北美 0 点为未知坐标系被排除（见 §6.2） |
| M0-05 | 凭证不泄漏、不硬编码 | **PASS** | key 只从 `.env` 注入；页面 HTML 无 `key=`；全库扫描除 `.env` 外无明文；无 key 时界面明确提示不伪装 |
| M1-01 | 地点搜索（含别名/年代/分页） | **PASS** | 长安 8 条、桂林 10 条、别名「桂林縣」命中、洛阳年代筛选 5→1→0、分页 1/444→2/444 |
| M1-02 | 地点详情 | **PASS** | 名称/位置/来源/精度四段齐全，含原始坐标系与来源记录 |
| M1-03 | bbox 空间查询返回 GeoJSON | **PASS** | `FeatureCollection`，元数据含 bbox/totalInBbox/returned/limit/truncated |
| M1-04 | 搜索与地图标记互相定位 | **PASS** | 点结果 z1.4→z7 并高亮；点标记打开详情 |
| M1-05 | 数据保护 | **PASS** | 九表行数、Flyway 校验和、七张 CSV 指纹全部与导入后一致 |

**底图状态**：2026-11-03T19:10Z 已配置有效的 MapTiler API key（`code/.env`，20 位，未入库、未进任何交付文件）。
四种样式均返回真实瓦片：`outdoor-v2` / `streets-v2` / `satellite` / `hybrid` 的 style.json 全部 HTTP 200，
浏览器内 0 个真实失败请求。以下判定基于**真实底图**，非离线降级视图。

---

## 二、执行环境

| 项 | 值 |
|---|---|
| 前端 | Vue 3.5.13 + TypeScript 5.6.3 + Vite 6.0.7 + MapLibre GL JS 4.7.1 |
| 后端 | Spring Boot 3.5.16（Java 21 目标），模块化单体，`JdbcTemplate` 直读库 |
| 数据库 | PostgreSQL 17.11 + PostGIS 3.6.4，`127.0.0.1:55432/canvas_history`，用户 `canvas_app` |
| 后端端口 | 8088（`API_HOST_PORT`）；前端 5180（`WEB_HOST_PORT`） |
| 浏览器验证 | Chrome（headless new + swiftshader）经 puppeteer-core 23.11.1 驱动 |

---

## 三、新增与修改的源码

### 后端（新建，`backend/`）

| 文件 | 作用 |
|---|---|
| `pom.xml` | Spring Boot 3.5.16 + web + jdbc + postgresql 42.7.x，版本全部固定 |
| `src/main/resources/application.yml` | 数据源、Jackson、分页上限；凭证仅从环境变量读 |
| `CanvasHistoryApplication.java` | 启动类 |
| `config/WebConfig.java` | CORS 白名单（dev 端口） |
| `dto/Dtos.java` | 搜索项 / 详情 / 名称 / 位置 / 来源记录 / 质量台账 DTO |
| `service/PlaceQueryService.java` | 三条只读查询的 SQL 实现（搜索、详情、bbox） |
| `web/PlaceController.java` | `GET /api/v1/places`、`/places/{id}`、`/places/map` |
| `web/MetaController.java` | `GET /api/v1/meta/health`、`/meta/stats` |
| `run-dev.sh` | 从 `../.env` 注入凭证并启动 jar |

### 前端（新建，`frontend/`）

| 文件 | 作用 |
|---|---|
| `package.json` / `vite.config.ts` / `tsconfig.json` / `index.html` | 工程骨架；Vite proxy `/api` → 8088；构建期注入 key |
| `src/main.ts` / `src/styles.css` | 入口与全局样式 |
| `src/api.ts` / `src/types.ts` | API 封装与类型 |
| `src/map/basemaps.ts` | 四种样式、样式 URL、区域预设、离线降级底图 |
| `src/components/MapView.vue` | 地图实例、样式切换（保视野）、视野内 bbox 拉取、点选、定位 |
| `src/components/SearchPanel.vue` | 关键词 / 年代 / 分页 / 同名不合并展示 |
| `src/components/DetailPanel.vue` | 名称、位置、来源记录、质量提示四页签 |
| `src/App.vue` | 三面板联动与数据状态条 |

### 未触碰

`src/main/resources/db/migration/V1–V3`、九张业务表结构、七张 CSV、`设计资料/V2.1.1_正式交付` 全部未改。

---

## 四、启动方法

```bash
cd E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory/code

# 后端（首次需构建）
cd backend && mvn -DskipTests package && bash run-dev.sh
# → http://127.0.0.1:8088/api/v1/meta/health

# 前端（另一个终端）
cd frontend && npm install && npx vite --host 127.0.0.1
# → http://127.0.0.1:5180/
```

或 `bash start-dev.sh` 一次拉起两者。

---

## 五、实测结果

### 5.1 浏览器端到端（15 项全 PASS，真实底图模式）

脚本 `C:\Users\the_z\.workbuddy\tools\e2e\accept-m0m1.cjs`，输出 `m0_m1_shots/e2e_result.json`：

```
检测到 MapTiler key：是（真实底图模式）
PASS M0-01 地图加载 / 默认全球视野 — canvas=true loaded=true center=20,20 zoom=1.4 layers=117
PASS M0-05 凭证不泄漏 / 不硬编码 — HTML 中无 key 参数=true；已检测到 API key
PASS M0-02 四种样式可用 — 样式名互异 4 种：Streets / Satellite / Satellite Hybrid / Outdoor；
                          Satellite 与 Hybrid 含栅格影像层（raster 0/1/1/0）；每步点层 400 点
PASS M0-03 视野保持 — 切换前 116.4,39.9 z6.2；四次切换后相机完全一致，漂移 0
PASS M0-04 四区域测试 — 中国@108,32 z3.8 400点 / 欧洲@14,49 z3.9 400点 / 北美@-98,42 z3.2 0点 / 中东@45,29 z4.2 400点
PASS M1-01 地点搜索命中真实记录 — 共 8 条；长安县×6 …
PASS M1-01b 同名不同地点不合并 — 首屏 6 条 id 各不同 #29931 #29933 #29934 #29935 #29936 #33473
PASS M1-01c 别名搜索 — 搜「桂林縣」→ 正名 桂林县 · 县级治所 · 590–665
PASS M1-01d 年代筛选 — 洛阳：不限 5 条 / year=1200 1 条 / year=-500 0 条
PASS M1-01e 分页 — 1 / 444 → 2 / 444
PASS M1-04 搜索结果 → 地图定位 — z1.4@20,20 → z7@110.4075,18.8006；高亮环 1 个
PASS M1-02 地点详情 — 万县：坐标 110.40747,18.80063 / 精度 unknown / CHGIS V6 / CHGIS
PASS M1-03 bbox 空间查询 — HTTP 200，FeatureCollection，首点 [119.990395,26.883463]，truncated=true
PASS M1-03b 返回数量上限 — limit=99999 被钳制为 2000，实际返回 2000，truncated=true
PASS CLEAN 浏览器控制台 — 无 JS 错误、无真实失败请求（另有 80 个因样式切换被浏览器取消的瓦片请求，属正常）
=== 合计 15 项，PASS 15，FAIL 0 ===
```

截图见 `ops/reports/m0_m1_shots/`（M0-01 / M0-02 四张 / M0-04 四区域 / M1-01 搜索·年代·分页 / M1-02 四页签 / M1-04 定位 / M0-05 假 key 管线）。

### 5.2 API 层（`ops/reports/m0_m1_api_test.log`）

| 检查 | 结果 |
|---|---|
| `GET /places?keyword=桂林` | 10 条，含 `matchedNameType`（primary/alternate/transliteration） |
| `GET /places?keyword=洛阳&year=1200` | 1 条（1087–1130 段）；`year=-500` → 0 条 |
| `GET /places/map?bbox=110,23,111,24&limit=1` | `FeatureCollection`，`meta.totalInBbox=87 / returned=1 / truncated=true` |
| `limit=99999` 全球 bbox | 服务端钳制 2000，`truncated=true`，`totalInBbox=17,326` |
| `GET /places/19051` | 名称 3 / 位置 1 / 来源 1 / 台账 1（`unknown_time_bound_type`，`preserved_and_flagged`） |
| 详情是否泄漏 raw_payload | **否**（无该字段） |
| 不存在的 id | 404；非法 bbox → 400 |

响应时间（3 次均值）：搜索 123 ms、详情 33 ms、全球 bbox（400 点）51 ms、近景 bbox 7 ms。

### 5.3 地图约束落实

- 只取 `geom IS NOT NULL`、`crs_confidence <> 'unknown'`、`record_status <> 'rejected'`、`source_record.is_active`、
  `merged_into_place_id IS NULL` 的位置；实测返回的 2000 个要素全部 `crsConfidence=confirmed`，无 geometry 缺失。
- 每地点用 `DISTINCT ON (place_id) ORDER BY location_id` 取一条代表位置，不另写一套地点选择规则。
- 上限 `MAX_MAP_FEATURES = 2000` 服务端硬钳制，前端请求 400，浏览器不会拿到全量。

---

## 六、未验证事项与真实阻塞

1. **底图凭证已就位（原阻塞已解除）**
   早期无 key 时界面如实提示「底图未接入 MapTiler」，并用假 key 验证过管线会 403 且不伪装成功
   （`M0-05_fakekey_pipeline.png` 留存）。现已配置真实 key，四种样式均加载真实瓦片。
   注意：该 key 是浏览器端 **API key**，须在 MapTiler 控制台限制 Allowed HTTP origins；
   若改为对外部署，需把 origin 白名单加上实际域名。

2. **北美视野 0 点是坐标约束生效，不是缺陷或数据缺失**
   北美视野 bbox `-159.2,10,-36.8,63.4` 内共 6 条位置（MCGD 的 Alma/Akron/Albany、WHG 的 Santa Fe 等），
   **全部 `crs_confidence = 'unknown'`**；按「未知坐标系不得作为可信位置显示」的约束被排除，故地图为空。
   欧洲视野同理可查：1,150 个点中 917 来自 Pleiades（希腊-罗马世界），2 来自 WHG geonames，1 来自 Getty TGN，
   说明多来源数据确实在正常工作，排除逻辑没有误伤。
   证据：`m0_m1_shots/crs_exclusion_check.log`。
   （附带事实：本批 643 条 MCGD 位置全部为 `unknown`，因此在任何视野都不会上图。）

3. **`location_precision` 全为 `unknown`**：源数据未提供精度分级，详情页如实显示 `unknown`，
   未按经验值编造 `uncertainty_m`。

4. **未做**：聚合（cluster）、时间轴联动（M2+）、地点/人物/事件 CRUD、AI 功能、微服务与额外中间件。

---

## 七、数据保护对照

`ops/reports/m0_m1_shots/db_unchanged.log`：

| 表 | 导入后 | 本轮结束 |
|---|---:|---:|
| source_record | 29,391 | 29,391 |
| historical_place | 19,039 | 19,039 |
| historical_place_name | 47,499 | 47,499 |
| historical_place_location | 18,101 | 18,101 |
| candidate_match | 53,131 | 53,131 |
| data_quality_issue | 12,831 | 12,831 |
| import_batch | 7 | 7 |
| data_dataset | 7 | 7 |
| data_source | 4 | 4 |

Flyway：`1:882334605:true | 2:966227528:true | 3:-2058740630:true`，与导入后完全一致。
七张 CSV 的 SHA256 与 R1.2 基线逐字节一致。未执行 DROP / TRUNCATE / 重建库 / 重置序列 / 重新导入。

---

## 七点五、配置 key 后的两处修正

1. **地图截断采样改为空间分散**：原先 `ORDER BY place_id LIMIT N` 在全球视野下会取到同一数据集
   连续 id 的点，全部挤在中国西部一小块，视觉上像“只有那里有数据”。
   改为 `ORDER BY md5(place_id::text)` 后，400 点经度跨度从局部扩到 **129.7°**（-2.9~126.8），
   覆盖中国全境 + 地中海 + 中东；同一 bbox 下结果稳定可复现（确定性哈希，非随机）。
2. **attribution 去重**：MapTiler 样式自带 `© MapTiler © OpenStreetMap contributors`，
   自定义层原样重复了一遍导致显示两遍；现只补数据来源 `CHGIS / Pleiades / MCGD / WHG`。

## 八、已知小问题（不阻断）

- 前端 bundle 单文件 896 KB（MapLibre 占主体），未做代码分割；本地开发够用。
- 详情子集合上限：`sourceRecords` 与 `issues` 各 `LIMIT 50`，台账超出时置 `issueListTruncated=true` 并在界面提示；
  `names` / `locations` 不设上限（实测单地点最多 89 个名称、7 条位置；按 API 口径单地点台账最多 2 条，50 条上限远未触及）。
- 搜索为 `ILIKE '%kw%'` 全表匹配，`historical_place_name.name_text` 上暂无 trigram 索引；
  当前 47,499 行下 123 ms，数据量再上一个量级需补索引（属 M2 性能项）。
