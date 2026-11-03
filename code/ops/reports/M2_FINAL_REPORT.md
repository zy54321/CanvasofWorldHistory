# M2 最终交付报告

完成时间（UTC）：2026-11-03T13:40Z ｜ 工作目录：`E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code`
正式库：`canvas_history`（只读使用，本轮未写入任何数据） ｜ 写入测试库：`canvas_history_m2check`

---

## 〇、验收结论

**M2 — COMPLETED / ACCEPTED**

所有必测项均以真实执行结果为准，无未通过项。§11 列出 3 项"已知限制"，均不阻断 M2 结项，也不影响进入 M3。

---

## 一、M2 最终功能完成清单

| 领域 | 功能 | 状态 |
|---|---|---|
| 地点 | 列表 / 关键词搜索（名称+别名）、分页 | ✅ 新增管理列表接口 + 界面 |
| 地点 | 详情（名称、位置、来源、台账） | ✅ 复用 M1 详情 |
| 地点 | 新建 / 编辑 / 删除（含二次确认） | ✅ 新增写接口 + 界面 |
| 地点 | 多个历史名称（含类型、语言、有效期、转写方案） | ✅ 增删改查 |
| 地点 | 经纬度、定位精度、不确定度、坐标系置信 | ✅ 增删改查，允许整体留空=未定位 |
| 地点 | 地图定位复用 | ✅ 位置行「看地图」联动 M0 地图 |
| 人物 | 列表 / 搜索（规范名+全部别名）、分页 | ✅ |
| 人物 | 详情 / 新建 / 编辑 / 删除 | ✅ |
| 人物 | 规范姓名、别名/异体名/外文名（八类 name_type） | ✅ |
| 人物 | 生卒年份 + 各自精度 + 原始表述 | ✅ BCE/CE 界面输入 |
| 人物 | 关联事件（角色 + 关系有效期） | ✅ 对象选择器 |
| 人物 | 活动地点（关系类型 + 时间范围 + 顺序） | ✅ 对象选择器 |
| 事件 | 列表 / 搜索（标题+摘要）、分页 | ✅ |
| 事件 | 详情 / 新建 / 编辑 / 删除 | ✅ |
| 事件 | 标题、摘要、详细描述 | ✅ |
| 事件 | 时间区间 + 精度 + 原始表述 + 备注（允许完全未知/开放区间） | ✅ |
| 事件 | 事件类型（自由文本，不造枚举） | ✅ |
| 事件 | 关联多人物（角色）/ 多地点（地点角色） | ✅ 对象选择器 |
| 关联 | 三类关联的增 / 改 / 解除 / 重复拦截 | ✅ |
| 时间 | 天文学纪年统一换算、不显示公元 0 年 | ✅ `frontend/src/time.ts` 单一实现 |

---

## 二、前端新增页面与组件

| 文件 | 作用 |
|---|---|
| `src/components/manage/ManagePanel.vue` | 管理面板外壳：三页签 + 左列表（搜索/分页）+ 右编辑器 |
| `src/components/manage/PlaceEditor.vue` | 地点主表 + 历史名称 + 位置（三种子表单共用一处） |
| `src/components/manage/PersonEditor.vue` | 人物主表 + 名称 + 关联事件 + 活动地点 |
| `src/components/manage/EventEditor.vue` | 事件主表 + 关联人物 + 关联地点 |
| `src/components/manage/ObjectPicker.vue` | 通用对象选择器（地点/人物/事件），带搜索与「已关联」置灰 |
| `src/components/manage/AstroYear.vue` | 年份输入：公元前/公元 + 正整数 → 内部整数，实时回显内部值 |
| `src/time.ts` | 天文纪年换算与显示的唯一实现（toAstro/fromAstro/formatYear/formatRange） |

修改：`App.vue`（左下「内容管理」入口、面板挂载、看地图联动）、`api.ts`（三组写接口 + `ApiError`）、`types.ts`（M2 类型）、`styles.css`（共用表单样式）、`vite.config.ts`（允许 `API_HOST_PORT` 覆盖，便于把前端指向测试库联调）。

界面沿用既有视觉：浅色面板、棕色强调色、同一套圆角/字号/间距；未引入任何 UI 框架或新依赖。

---

## 三、后端新增/修改文件与原因

| 文件 | 类型 | 原因 |
|---|---|---|
| `dto/PlaceAdminDtos.java` | 新增 | 地点管理列表行、删除响应、选项集合 |
| `service/PlaceAdminService.java` | 新增 | 地点 CRUD + 名称 CRUD + 位置 CRUD（M1 只交付了只读查询） |
| `web/PlaceAdminController.java` | 新增 | `/places/admin` 列表、`/places` POST、`/places/{id}` PUT/DELETE、`/names`、`/locations` |
| `dto/Requests.java` | 修改 | 追加 `PlaceUpsert` / `PlaceNameUpsert` / `PlaceLocationUpsert` |
| `config/WebConfig.java` | 修改 | **修缺陷**：CORS 原本只允许 `GET` 且端口写死 5180/5173，导致浏览器带 Origin 的 POST/PUT/DELETE 被 403 拒绝（表现为"保存失败且无提示"）；改为放行本机任意端口的 GET/POST/PUT/DELETE/OPTIONS |

M2-A 已交付的人物/事件接口（17 + 13 端点）**未做任何改动**，本轮只做回归。

---

## 四、数据库变更

**新增 `V5__manual_entry_dataset.sql`**（唯一结构变更，V1–V4 一个字节未动）：

1. `data_source.source_id` 的 CHECK 增加 `'manual'`，并插入 `manual / 人工录入` 一行；
2. 新增数据集 `manual_entry`（归属 `manual`），作为人工录入地点的落点；
3. 新增部分唯一索引 `uq_hpn_manual_name`：仅对 `source_record_id IS NULL` 的人工名称行去重（既有 47,499 行全部在索引之外，不受影响）。

**为什么必须有这一步**：`historical_place.dataset_id` 是 NOT NULL 外键，而 `data_dataset` 只有 7 个导入数据集、`data_source` 的 CHECK 又把 source_id 限死为 4 个第三方来源。M2 要求"新增地点"，但**没有诚实的归属可以放**——硬塞进 chgis 会把人工录入伪装成第三方数据。这是模型补全，不是为前端方便而放宽约束：四个原有 source_id 的语义完全不变。

**数据库对象现状**：17 张表（9 业务 + 6 人物事件 + flyway 记录 + spatial_ref_sys）、5 个视图（3 业务视图 + PostGIS 2 个元数据视图）。

---

## 五、API 对接情况

### 本轮新增（地点写入，13 个端点）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/places/admin?keyword=&page=&size=` | 管理列表（keyword 可空） |
| GET | `/api/v1/places/admin/options` | 可选值字典（与数据库 CHECK 一致） |
| POST | `/api/v1/places` | 新建 → 201 |
| PUT | `/api/v1/places/{id}` | 编辑 |
| DELETE | `/api/v1/places/{id}` | 删除，被引用时 409 |
| POST | `/api/v1/places/{id}/names` | 新增名称 |
| PUT | `/api/v1/places/{id}/names/{nameId}` | 编辑名称 |
| DELETE | `/api/v1/places/{id}/names/{nameId}` | 删除名称 |
| POST | `/api/v1/places/{id}/locations` | 新增位置 |
| PUT | `/api/v1/places/{id}/locations/{locationId}` | 编辑位置 |
| DELETE | `/api/v1/places/{id}/locations/{locationId}` | 删除位置 |

### 前端对接的既有接口（M2-A，未改）

人物 17 端点、事件 13 端点，全部按原契约调用；详情返回的 `names/events/places/persons/places` 子集合直接用于右侧编辑区。

**时间契约**：前端所有输入经 `time.ts` 换算成天文纪年整数再提交；后端只透传整数。已实测 `endYearAstro: null` 在 JSON 中保留（M2-A 修的 Jackson `non_null` 问题仍然有效），前端不会把"未知结束年"当 0。

---

## 六、自动化测试结果

| 套件 | 项数 | 结果 | 日志 |
|---|---:|---|---|
| M2-A 原有 API 回归（`ops/m2/api_test.py`） | 43 | **43 PASS** | `m2_final/01_api_m2a_regression.log` |
| M2 完整业务测试（`ops/m2/api_m2_full_test.py`） | 36 | **36 PASS** | `m2_final/02_api_m2_full.log` |
| 管理界面 E2E（`tests/e2e-manage/m2-ui.cjs`） | 14 | **14 PASS** | `m2_final/ui_shots/ui_result.json` |

M2 完整业务测试覆盖验收场景一~六，摘录：

```
PASS P01 新建地点（不含坐标）→ 未定位记录，locations 为空
PASS P03 一个地点挂多个历史名称（其一有效期 -500~-400）
PASS P05 添加坐标与定位精度（112.5 / approximate / ±5000m / hasGeom）
PASS P06/P07 经度越界、单侧坐标 → 400
PASS H03 仅姓名即可创建人物（生卒/简介全缺失）
PASS E02/E03 事件时间未知可保存；开放区间 endYearAstro 为显式 null
PASS L01/L04 一个事件关联多人物、多地点
PASS L02/L05 重复关联 → 409（uq_event_person / uq_event_place）
PASS T01 公元前 1 年=0、公元 1 年=1，相邻不重叠
PASS D01b 删除仅被 event_place 引用的地点 → 409 fk_event_place_place，地点仍在
PASS D03 删除事件 → event_person/event_place 级联清空
PASS D06 七条外键全库孤儿扫描 = 0
```

界面 E2E 14 项（浏览器真实点击）：

```
PASS U01 界面新建地点 → 进入该地点编辑态（地点 #14）
PASS U02 界面添加带有效期名称 → 显示「前500 ~ 前400」
PASS U03 界面添加坐标与定位精度
PASS U04 界面输入公元前 551 年 → 内部整数 -550（换算正确）
PASS U05 关联地点弹出对象选择器（不是手填 ID）
PASS U06/U07 建立活动地点关联、事件关联
PASS U08–U10 事件（时间未知）关联人物与地点
PASS U11 列表关键词搜索命中新建记录
PASS U12 删除事件（二次确认）后回到空态
PASS U13 浏览器控制台 0 个 JS 错误
```

> 说明：本轮修掉了 CORS 只允许 GET 的缺陷后，界面写操作才真正可用——此前 U01 会看到 "403 Forbidden" 而无任何提示。该缺陷只有浏览器真跑才会暴露，静态检查与 curl 都发现不了（curl 不带 Origin 头）。

---

## 七、M0 / M1 回归结果

- **API**（`03_m0m1_regression.log`）：桂林搜索 10 条、洛阳 year=1200→1 / -500→0、详情 27421、bbox `FeatureCollection` 272 命中、limit=99999 钳制 2000、三视图 84,958 / 19,039 / 19,039 —— 全部与 M2 施工前一致。
- **浏览器**（`04_m0m1_ui_regression.log`）：M0-01~05 + M1-01~04 + 控制台洁净，**15/15 PASS**（真实 MapTiler 底图，四样式切换零漂移）。

---

## 八、Git 变更文件清单

当前目录**不是 Git 仓库**（`fatal: not a git repository`），因此无 commit 可列。实际文件变更见 `m2_final/07_inventory.log`：

- 后端新增 3：`PlaceAdminDtos.java`、`PlaceAdminService.java`、`PlaceAdminController.java`
- 后端修改 2：`WebConfig.java`、`Requests.java`
- Migration 新增 1：`V5__manual_entry_dataset.sql`
- 前端新增 7：`manage/{ManagePanel,PlaceEditor,PersonEditor,EventEditor,ObjectPicker,AstroYear}.vue`、`time.ts`
- 前端修改 5：`App.vue`、`api.ts`、`types.ts`、`styles.css`、`vite.config.ts`
- 测试脚本新增 2：`ops/m2/api_m2_full_test.py`、`tests/e2e-manage/m2-ui.cjs`

**未改动**：V1–V4 Migration、七张原始 CSV、`import_staging.py`、`verify_import.py`、`PlaceQueryService`/`PlaceController`/`MetaController`（M1 只读链路完整保留）。

---

## 九、运行与部署验证

| 项 | 结果 |
|---|---|
| 数据库容器 | `canvas-history-db` Up (healthy)，重启后 5s 恢复 |
| 后端 8088（正式库） | 200；M0/M1 全绿；M2 接口在该库列表为空（未写入） |
| 后端 8089（测试库） | 200；承载全部写入测试 |
| 前端 5180（→ 正式库） | 200，地图与检索正常 |
| 前端 5181（→ 测试库） | 200，用于管理界面联调与 E2E |
| 重启后持久化 | 测试库 person=22 / name=4 / event=14 / 关联 11 / place=16 全部仍在；Flyway 5 条记录完好；正式库九表 180,010 行未变 |

---

## 十、数据保护

- 正式库 `canvas_history`：九张业务表行数 29,391 / 19,039 / 47,499 / 18,101 / 53,131 / 12,831 / 7 / 7 / 4 **逐表未变**；六张 M2 新表**仍为 0 行**（全部写入测试都在 `canvas_history_m2check`）。
- Flyway：V1–V4 校验和 `882334605 / 966227528 / -2058740630 / 1291861836` **未变**，新增 V5 `-1325948257`。
- `data_dataset` 7→8、`data_source` 4→5 是 V5 种子行（`manual_entry` / `manual`），非数据异常，已在对比脚本中单独核对。
- 真实数据主键区间未变：`max(place_id)=38084`、`max(name_id)=94998`。
- 未执行 DROP / TRUNCATE / 重建库 / 重置序列；未修改七张原始 CSV。

---

## 十一、尚未解决的问题与影响

| # | 问题 | 影响 | 建议 |
|---|---|---|---|
| 1 | **写接口无鉴权**：任何人能调用 POST/PUT/DELETE | 仅本机 `127.0.0.1` 绑定 + 未对外暴露，当前风险可控；一旦部署到服务器即不可接受 | 在对外开放前补最小鉴权（M3 或上线前专项） |
| 2 | **无"非测试库禁止写"的硬闸**：若把 8088（正式库）当开发环境用，写操作会真的落库 | 误操作风险靠流程规避（本轮所有写入测试显式用 8088/8089 双实例隔离） | 可加 `ALLOW_WRITE_DB` 白名单开关，需 Owner 授权 |
| 3 | **`event_type` / `location_role` / `role` / `relation_type` 仍为自由文本** | 表单是自由输入而不是下拉，不同录入者可能写出不一致取值 | 值域规范确定后加一条 V6 字典/CHECK，界面再换下拉 |
| 4 | 地点管理列表默认按 `place_id` 升序 | 新建的地点排在最后，需要翻页 | 后续可加"按更新时间"排序参数 |
| 5 | `PLACE_TYPES` 等选项在前端与后端各有一份常量 | 两处若改动不一致会出现前端可选、后端拒绝 | 已提供 `/places/admin/options` 接口，后续可改为前端拉取 |
| 6 | M0 英文地图标签问题 | 按指令不在本次范围 | 保持记录 |

以上均不阻断 M2 结项，也不影响进入 M3。

---

## 十二、交付物位置

- 报告：`ops/reports/M2_FINAL_REPORT.md`
- 日志：`ops/reports/m2_final/01_api_m2a_regression.log`、`02_api_m2_full.log`、`03_m0m1_regression.log`、`04_m0m1_ui_regression.log`、`05_data_protection.log`、`06_persistence.log`、`07_inventory.log`
- 界面截图：`ops/reports/m2_final/ui_shots/`（14 张，含管理面板、地点/人物/事件编辑、对象选择器、关联结果、删除后空态）
- M0/M1 回归截图：`ops/reports/m2_final/shots/`
- 测试脚本：`ops/m2/api_m2_full_test.py`、`tests/e2e-manage/m2-ui.cjs`
