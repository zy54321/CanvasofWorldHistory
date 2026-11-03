# M2-2A 后端业务接口交付报告

执行时间（UTC）：2026-11-03T12:16Z 起 ｜ 工作目录：`E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code`
测试库：`canvas_history_m2check`（写入测试） ｜ 正式库：`canvas_history`（未写入）

---

## 一、结论

| 验收项 | 判定 | 证据 |
|---|---|---|
| 1. 人物 CRUD 完整通过 | **PASS** | A01–A05 |
| 2. 人物名称 CRUD 完整通过 | **PASS** | B01–B08 |
| 3. 事件 CRUD 完整通过 | **PASS** | C01–C06 |
| 4. 三类关联增删改查通过 | **PASS** | D01–D11 |
| 5. BCE/CE 时间读写正确 | **PASS** | E01–E04（-99、0、50、100 原样回读） |
| 6. 必填/精度/唯一约束错误正确处理 | **PASS** | B02/B03/B05、C04–C06、E04、F01–F05（全部 400/409/404，无 500） |
| 7. 删除人物/事件级联正确 | **PASS** | G01、G02 |
| 8. 删除被引用地点仍被拒绝 | **PASS** | `fk_event_place_place` RESTRICT 实测拦截 |
| 9. 不产生外键孤儿 | **PASS** | 7 条外键孤儿扫描 = 0 |
| 10. M0/M1 API 回归通过 | **PASS** | 6 项 API + 15 项浏览器 E2E 全 PASS |
| 11. 前后端启动正常、数据库健康 | **PASS** | 8088/5180 均 200；容器 healthy |

**测试脚本实测：43 项断言全部 PASS**（`ops/m2/api_test.py`，真实 HTTP 请求，非静态检查）。

---

## 二、API 清单

### 人物 `/api/v1/persons`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/persons?keyword=&page=&size=` | 列表 / 关键词搜索（规范名 + 全部别名）；keyword 空则返回全部 |
| GET | `/persons/{id}` | 详情：主表 + `names[]` + `events[]` + `places[]` |
| POST | `/persons` | 创建 → 201 返回完整详情 |
| PUT | `/persons/{id}` | 整体替换（可选字段传 null 即清空；recordStatus 传 null 表示不变） |
| DELETE | `/persons/{id}` | 删除 → 子表级联清除 |
| GET | `/persons/{id}/names` | 名称列表（primary/courtesy/alternate 优先排序） |
| POST | `/persons/{id}/names` | 新增名称 → 201 |
| PUT | `/persons/{id}/names/{nameId}` | 编辑名称 |
| DELETE | `/persons/{id}/names/{nameId}` | 删除名称 |
| GET | `/persons/{id}/events` | 关联事件（含该人角色、关系有效期） |
| POST | `/persons/{id}/events` | 关联事件 → 201 |
| PUT | `/persons/{id}/events/{linkId}` | 修改角色 / 关系有效期 / 备注 |
| DELETE | `/persons/{id}/events/{linkId}` | 解除关联 |
| GET | `/persons/{id}/places` | 活动地点（含 relationType、时间范围、sequenceOrder、代表坐标） |
| POST | `/persons/{id}/places` | 关联地点 → 201 |
| PUT | `/persons/{id}/places/{linkId}` | 修改关系类型 / 时间范围 / 顺序 |
| DELETE | `/persons/{id}/places/{linkId}` | 解除关联 |

### 事件 `/api/v1/events`

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/events?keyword=&page=&size=` | 列表 / 搜索（标题 + 摘要） |
| GET | `/events/{id}` | 详情：主表 + `persons[]` + `places[]` |
| POST | `/events` | 创建 → 201 |
| PUT | `/events/{id}` | 整体替换 |
| DELETE | `/events/{id}` | 删除 → 子表级联清除 |
| GET | `/events/{id}/persons` | 关联人物（含角色） |
| POST | `/events/{id}/persons` | 关联人物 → 201 |
| PUT | `/events/{id}/persons/{linkId}` | 修改角色 / 有效期 / 备注 |
| DELETE | `/events/{id}/persons/{linkId}` | 解除关联 |
| GET | `/events/{id}/places` | 关联地点（含地点角色） |
| POST | `/events/{id}/places` | 关联地点 → 201 |
| PUT | `/events/{id}/places/{linkId}` | 修改地点角色 / 有效期 |
| DELETE | `/events/{id}/places/{linkId}` | 解除关联 |

**时间口径**：所有 `*YearAstro` 均为天文学纪年整数（公元前 1 年 = 0）。接口只透传整数，不做 BCE/CE 标签换算，也不解析「公元前 384 年」这类文本——换算由前端统一处理，避免两套换算漂移。

**错误响应**（统一 JSON）：

```json
{ "status": 409, "error": "Conflict", "message": "违反唯一约束（uq_pn_name）：…", "constraint": "uq_pn_name" }
```

SQLSTATE → HTTP：`23505`→409、`23503` 仍被引用→409 / 引用不存在→400、`23514`→400、`23502`→400、`22P02`→400。**不再有 500 泄漏**。

---

## 三、实测结果

### 3.1 API 断言 43/43 PASS

`ops/reports/m2_2/05_api_test.log`。摘录关键项：

```
PASS A01 创建人物 → 201 且回读字段一致             | birth=-550 death=-478
PASS A03 编辑人物（整体替换）                     | name=孔丘（仲尼）
PASS B02 同类型同文本同语言重复 → 409              | uq_pn_name
PASS B05 非 transliteration 类型带转写方案 → 400   | 明确拒绝
PASS B07 按别名搜索命中（走 person_name）          | total=1
PASS C03 编辑为开放区间（只知起点）                | end=null precision=range
PASS C05 公元前区间倒挂 → 400                     | -221 晚于 -770 被拒
PASS D05 同事件同地点同角色重复 → 409              | uq_event_place
PASS D10 一个事件可关联多个地点                    | places=2
PASS E01 跨公元前后人物：-99 与 50 原样存取
PASS E03 公元前 1 年 = 内部 0 可原样存取
PASS G01 删除事件：关联清除，人物与地点不受影响
```

### 3.2 数据库级校验

- **孤儿扫描**（7 条外键 LEFT JOIN 全表）= **0**
- **RESTRICT 实测**：先删被 `historical_place_location` 引用的地点 → 被拦；再造一个**无子位置行**的地点并挂 `event_place`，删除时被 `fk_event_place_place` 拦下，地点仍在（证明是 M2 外键自身在起作用，不是被既有外键挡住）
- 正式库六表仍 **0 行**（无任何测试数据写入）

### 3.3 数据保护（`03_data_protection.log`）

九表行数 29,391 / 19,039 / 47,499 / 18,101 / 53,131 / 12,831 / 7 / 7 / 4 与 M2-1 结束时完全一致；V1–V4 校验和 `882334605 / 966227528 / -2058740630 / 1291861836` 未变；`max(place_id)=38084`、`max(name_id)=94998` 未变；七张 CSV 指纹全中。

### 3.4 M0/M1 回归

搜索桂林 10 条、洛阳 year=1200→1 / -500→0、详情 27421、bbox `FeatureCollection` 272 命中、limit=99999 钳制 2000、三视图 84,958 / 19,039 / 19,039；浏览器 E2E **15/15 PASS**。

---

## 四、修改的文件

**新增（8 个 Java 文件）**

| 文件 | 职责 |
|---|---|
| `dto/PersonDtos.java` | 人物列表/详情/名称/事件/地点 行对象 |
| `dto/EventDtos.java` | 事件列表/详情/人物/地点 行对象 |
| `dto/Requests.java` | 6 类写入请求体 + 删除响应 |
| `service/PersonService.java` | 人物 CRUD、名称 CRUD、人物↔事件、人物↔地点 |
| `service/EventService.java` | 事件 CRUD、事件↔人物、事件↔地点 |
| `web/PersonController.java` | 17 个端点 |
| `web/EventController.java` | 13 个端点 |
| `config/ApiExceptionHandler.java` | SQLSTATE → HTTP 语义映射 |

**修改（1 个文件）**

- `backend/src/main/resources/application.yml`：`hikari.read-only` 由 `true` 改为 `false`（M1 时期连接级只读，M2 需要写入）。池名 `canvas-ro` → `canvas-rw`，并加注释说明「`/places/**` 在代码层仍只发 SELECT」。

**未修改**：V1–V4 Migration、七张 CSV、`import_staging.py`、`verify_import.py`、`PlaceQueryService`/`PlaceController`/`MetaController`、前端全部代码。

**新增测试脚本**：`ops/m2/api_test.py`（43 项断言）。

---

## 五、未完成事项与真实问题

1. **`application.yml` 的只读开关**：为了让 M2 能写，连接级只读被关闭。这意味着**如果误把写接口指向正式库，就会真的写进去**。我没有做「按库名拒绝写入」的硬闸，因为那会让 M2-2B 的前端联调无法进行。建议 Owner 决定是否需要「非 `m2check` 库禁止写」的环境开关；需要的话我下一轮加。
2. **写接口目前无鉴权**：`@PostMapping` 等直接开放。设计要求本轮不建权限中心，故未加。正式对外前必须补。
3. **`event_type` / `location_role` / `role` / `relation_type` 仍是自由文本**（按本轮口径第 3 条）。接口不做枚举校验，只在为空时补 `unknown`。M2-1 报告里提的「值域待定」仍未裁决，会影响 M2-2B 表单下拉项。
4. **`PUT` 语义是整体替换**：`recordStatus` 传 `null` 保留原值，其余可选字段传 `null` 即清空。前端需按此实现，否则容易误清数据。已写进 DTO 注释。
5. **搜索是 `ILIKE '%kw%'`**，无 trigram 索引。当前 `person`/`event` 表数据量为 0，量级上不去前不需要索引；一旦真实录入超过万级人物需补索引（不需改 V4，加 V5 即可）。
6. **详情子集合上限 500 行**，超出置 `truncated=true`。当前无数据触及。
7. **`canvas_history_m2check` 中的测试数据仍在**（person 3 / event 2 等），是刻意的可复跑痕迹；该库可随时 `TRUNCATE` 或删除，不影响正式库。

已停在此处，未进入 M2-2B，未改前端。
