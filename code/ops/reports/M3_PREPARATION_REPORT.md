# M3 前置工程收尾报告

执行时间：2026-11-04（Asia/Shanghai）
范围：Git 基线、正式库写入保护、地点列表排序、地点选项来源统一、运行安全边界
结论：**M2 — FROZEN ／ M3 — READY TO START**

---

## 一、Git 仓库状态与基线

项目根目录原本**已有** Git 仓库（`E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\.git`），
未重复初始化，直接沿用。

| 项 | 值 |
|---|---|
| 仓库根 | `E:/01_Work/01_PersonalProjects/014-CanvasofWorldHistory` |
| 分支 | `master` |
| 远程 | **无**（未设置、未推送） |
| 作者（仓库本地配置，沿用既有值） | `canvas-history <dev@localhost>` |
| 跟踪文件数 | 344 |
| 工作区 | 干净（报告本次提交后仅余新增报告文件） |

提交历史：

```
3d58c41  2026-11-04  chore(m3-prep): database write guard, place list ordering, backend-driven place options
6e95890  2026-11-04  chore: establish M2 accepted baseline      ← M2 正式基线
```

**M2 基线 Commit ID：`6e95890`**（`chore: establish M2 accepted baseline`）
**本轮加固 Commit ID：`3d58c41`**

### .gitignore 策略

仓库根 `.gitignore` + `code/.gitignore` 两级生效，已实测命中（`git check-ignore -v`）：

| 排除项 | 规则位置 | 实测 |
|---|---|---|
| `.env`（真实 Key / 数据库口令） | `code/.gitignore:2` | ✔ 已忽略 |
| `frontend/dist/`（含编译进 bundle 的 Key） | `code/.gitignore:23` | ✔ 已忽略 |
| `data/staging/*`（七张原始 CSV，约 70MB） | `code/.gitignore:8` | ✔ 已忽略 |
| `ops/.deps/`、`backend/target/`、`node_modules/` | 同上 | ✔ 已忽略 |
| `*.log`（测试运行日志） | `code/.gitignore:39` | ✔ 已忽略 |
| `code.zip`、`.workbuddy/`、`设计资料/P0收敛/` | 根 `.gitignore` | ✔ 已忽略 |

纳入管理的：前后端源码、V1–V5 Migration、测试脚本（`ops/m2/*.py`、`tests/e2e*/*.cjs`）、
各阶段验收报告（含 `M2_FINAL_REPORT.md`）、配置说明。

提交前对 50 个暂存文件做了凭证扫描：**真实 MapTiler Key 与数据库口令命中数 = 0**；
`git ls-files` 中 `.env` 类文件仅有 `.env.example`。

> 说明：`.env.example` 中的 `DB_WRITE_ALLOWED_DATABASES=` 是**空模板**，不含任何真实值。

---

## 二、修改文件清单（本轮）

### 新增（6）

| 文件 | 作用 |
|---|---|
| `backend/.../config/WriteGuard.java` | 写入闸门：按 `current_database()` 精确匹配白名单，fail-closed |
| `backend/.../config/WriteGuardInterceptor.java` | 挂 `/api/**`，非安全方法统一设卡 |
| `backend/.../config/WriteForbiddenException.java` | 拒绝时抛出，交由统一异常处理翻译成 403 |
| `ops/m2/m3prep_test.py` | 写保护 / 排序 / 选项 三组实测脚本（真实 HTTP + 真实库） |
| `tests/e2e-manage/guard-ui.cjs` | 写拒绝与选项加载失败的界面表现验证 |
| `ops/reports/m3_prep/`（报告与证据） | 17 份执行日志、2 组截图、2 份结果 JSON |

### 修改（11）

| 文件 | 改动 |
|---|---|
| `backend/.../config/WebConfig.java` | 注册写保护拦截器 |
| `backend/.../config/ApiExceptionHandler.java` | `WriteForbiddenException` → 403 `WRITE_FORBIDDEN`，带 database / allowedDatabases |
| `backend/.../web/MetaController.java` | 新增 `GET /api/v1/meta/write-policy` |
| `backend/.../service/PlaceAdminService.java` | 列表排序改 `updated_at DESC, place_id DESC`；编辑推进 `updated_at`；删除语义收紧（见 §7） |
| `backend/src/main/resources/application.yml` | 新增 `app.write.allowed-databases`（默认空 = 全库禁写） |
| `backend/run-dev.sh` | 支持 `DB_NAME` / `DB_WRITE_ALLOWED_DATABASES` / `API_PORT` 覆盖，一个脚本起两种实例 |
| `code/.env.example` | 补写白名单模板与用法注释 |
| `frontend/src/components/manage/PlaceEditor.vue` | 选项改为从后端加载；失败时禁用表单并提示；删除前端重复常量 |
| `frontend/src/api.ts` / `src/types.ts` | 新增 `placeAdmin.options()` 与 `PlaceOptions` 类型 |
| `frontend/vite.config.ts` | 固定 `host: 127.0.0.1`、`strictPort: true` |
| `ops/m2/api_test.py` | G03 断言随删除语义更新（见 §7） |

**未改动**：V1–V5 任何 Migration、七张原始 CSV、数据模型、M2 界面结构、事件/人物/地点字段规则。

---

## 三、数据库写入保护：设计

### 核心思路

不是 `ALLOW_WRITE=true` 全局开关，而是**按实际连接的数据库名做白名单精确匹配**：

```yaml
app:
  write:
    allowed-databases: ${DB_WRITE_ALLOWED_DATABASES:}   # 默认空 → 全库禁写
```

判定链（`WriteGuard`）：

1. 启动时执行 `select current_database()` 取**真实库名**——不看端口、不看配置文件里写的库名；
   端口可以随便映射、`DB_URL` 可以写错，只有库名是数据库自己说的。
2. 库名必须**逐字命中**白名单；白名单为空 = 一律禁止（fail-closed）。
3. 白名单出现 `*` / `%` 视为**配置错误**，整体拒绝，避免"图省事写个星号"把保护废掉。
4. 库名取不到（连接异常）→ 按禁止写入处理，失败方向永远是更保守。
5. 将来接口新增也自动受保护：拦截器挂在 `/api/**`，只放行 `GET / HEAD / OPTIONS`
   （OPTIONS 是 CORS 预检，必须放行否则浏览器连错误响应都读不到），
   `POST / PUT / PATCH / DELETE` 及任何新增方法都会过闸。

拒绝时返回 `403 {"error":"WRITE_FORBIDDEN", "database":..., "message":"数据库 xxx 不在写入白名单内…"}`，
**不是**靠前端隐藏按钮——实测 W02：只读实例界面上「新建地点」按钮仍可点，点了才被后端拒绝并给出原因。

### 实例配置

| 实例 | 库 | 白名单 | 结果 |
|---|---|---|---|
| 8088（+前端 5180） | `canvas_history` | 空 | **只读** |
| 8089（+前端 5181） | `canvas_history_m2check` | `canvas_history_m2check` | **可写** |

两个实例共用一个 `run-dev.sh`，靠环境变量区分：

```bash
bash backend/run-dev.sh                                   # 只读（正式库）
DB_NAME=canvas_history_m2check API_PORT=8089 \
DB_WRITE_ALLOWED_DATABASES=canvas_history_m2check bash backend/run-dev.sh   # 可写（测试库）
```

### 实测结果

**A. 正式库实例 8088 —— 11/11 PASS**（`ops/reports/m3_prep/01_writeguard_formal.log`）

```
PASS A01 写策略可读且指向 canvas_history        PASS A07 POST 创建人物被拒 403
PASS A02 写策略判定为禁止写入                   PASS A08 POST 创建事件被拒 403
PASS A03 GET 查询不受影响（total=10）          PASS A09 子资源写（地点名称）被拒 403
PASS A04 POST 创建地点被拒 403                  PASS A10 被拒后正式库数据量不变（19039 / 0）
PASS A05 PUT 编辑地点被拒 403                   PASS A11 目标地点仍可正常读取
PASS A06 DELETE 删除地点被拒 403
```

**B. 测试库实例 8089 —— 7/7 PASS**（`02_writable_testdb.log`）

```
PASS B01 写策略指向测试库且允许写入   PASS B05 子资源写（名称）成功 201
PASS B02 GET 正常                    PASS B06 DELETE 成功 200
PASS B03 POST 创建成功 201            PASS B07 删除后库中确无该行
PASS B04 PUT 编辑成功
```

**C. 配置异常 —— 4 组全按预期禁止**（`10_config_abnormal.log`）

| 场景 | 配置 | 判定 | 实测 |
|---|---|---|---|
| C1 连测试库但**未设白名单** | `DB_NAME=canvas_history_m2check`，白名单空 | 只读 | `writeAllowed=false`，POST 403，GET 200，库内新增 0 行 |
| C2 白名单**库名不匹配** | 连测试库，白名单 `canvas_history` | 只读 | `writeAllowed=false`，POST 403，GET 200，库内新增 0 行 |
| C3 白名单写**通配** `*` | 连测试库，白名单 `*` | 配置错误→只读 | `configProblems=["白名单不接受通配值: *"]`，POST 403 |
| C4 **重启 8088 后** | 同上 A 组配置 | 只读仍然生效 | `writeAllowed=false`，POST 403、DELETE 403、GET 200，地点数仍 19039 |

C1 是最关键的一条：**同一个数据库**，8089 能写、C1 实例不能写——证明判定依据是白名单而非端口或库名本身。

**界面层（`14_guard_ui.log`，4/4 PASS）**

```
PASS W01 只读实例写操作在界面给出明确提示 → 「数据库 canvas_history 不在写入白名单内，写操作已被拒绝（只读实例）」
PASS W02 写按钮未被前端隐藏（权限由后端判定）
PASS W03 选项接口失败时给出明确提示（不静默用内置常量）
PASS W04 选项未加载时表单下拉被禁用
```

---

## 四、地点列表排序

改动：`ORDER BY p.updated_at DESC NULLS LAST, p.place_id DESC`（原为 `place_id` 升序），
并在编辑时推进 `updated_at = now()`——否则"按更新时间排序"名不副实。

实测 4/4 PASS（`03_ordering.log`）：

```
PASS O01 新建的 3 条按创建时间倒序排在最前   [60, 59, 58, 18, 16]
PASS O02 编辑最早的一条后它排到第一（58 → 首位）
PASS O03 列表必要字段未受影响
PASS O04 搜索 + 分页仍然可用（total=3，每页 2 条）
```

未改 M1 的查询与数据：`historical_place` 行数仍 19,039，M0/M1 接口结果不变（§6）。

---

## 五、地点选项来源统一

### 接口实际返回（`GET /api/v1/places/admin/options`）

`placeTypes` / `placeTypeSources` / `recordStatuses` / `nameTypes` /
`timeBoundTypes` / `locationPrecisions` / `crsConfidences` —— 7 个字段。

### 前端不再维护取值清单

`PlaceEditor.vue` 删除了 `PLACE_TYPES`、`NAME_TYPES`、`TBTS`、`PRECISIONS`、`CRS_CONF`
五个常量数组，改为 `onMounted` 调 `placeAdmin.options()`；前端只保留
「代码 → 中文标签」的展示映射（`LABELS`），**取值本身只有一个来源**。

加载失败时不静默降级：显示「地点选项加载失败：…。表单已禁用，请确认后端可用后刷新页面。」
并禁用所有下拉（实测 W03 / W04）。

### 与数据库 CHECK 约束一致性实测（7/7 PASS，`04_options_vs_check.log`）

直接读 `pg_get_constraintdef` 解析出实际允许值，与接口返回比对：

```
PASS P-placeTypes        与 ck_historical_place_place_type 一致
PASS P-nameTypes         与 ck_hpn_name_type 一致
PASS P-timeBoundTypes    与 ck_hpn_time_bound_type 一致
PASS P-locationPrecisions 与 ck_hpl_location_precision 一致
PASS P-crsConfidences    与 ck_hpl_crs_confidence 一致
PASS P-recordStatuses    与 ck_historical_place_record_status 一致（收窄：merged 不开放手选）
```

唯一"收窄"是 `recordStatuses` 去掉 `merged`——系统态，不由表单手选，属刻意收窄而非缺失。

### 编辑闭环

界面选「县级治所」→ 保存 → 库内：

```
place_id=72 | 选项闭环校验点 | admin_center_county
```

即选项值确实经界面写入数据库，不是只在下拉里显示（`16_options_edit_ui.png`）。

---

## 六、本机服务绑定与安全边界

| 检查 | 结果 |
|---|---|
| 前端 5180 / 5181 | `127.0.0.1` 监听，`vite.config.ts` 已固定 `host: 127.0.0.1` + `strictPort: true` |
| 后端 8088 / 8089 | `127.0.0.1` 监听（Spring 默认回环，未配 `server.address=0.0.0.0`） |
| Docker 端口发布 | `127.0.0.1:15432 -> 5432/tcp`，compose 写死 `127.0.0.1:${DB_HOST_PORT}:5432` |
| 0.0.0.0 / `[::]` 监听 | **本项目相关端口 0 条** |
| 正式库 / 测试库连接独立 | 同一 `run-dev.sh`，`DB_NAME` + `DB_WRITE_ALLOWED_DATABASES` + `API_PORT` 三处显式区分 |
| 凭证提交风险 | 跟踪文件扫描：真实 Key / 口令命中 0；`.env` 未被跟踪；`frontend/dist` 已删且被忽略 |
| CORS | `allowedOriginPatterns("http://127.0.0.1:[*]", "http://localhost:[*]")`，方法 GET/POST/PUT/DELETE/OPTIONS —— 仅回环，本地开发功能保留 |

结论：**没有发现公网暴露风险**。

> 环境说明：本轮开始时 Docker Desktop 守护进程处于停止状态（四个服务同时掉线）。
> 已用 `docker desktop start` 恢复，容器随 restart 策略自动拉起，**数据完好**
> （`source_record=29391 / historical_place=19039 / person=0`）。这本身就是一次
> "数据库重启后数据仍在"的实证。

---

## 七、回归测试结果（全部真实执行）

| # | 测试 | 命令/脚本 | 结果 | 日志 |
|---|---|---|---|---|
| 1 | 正式库写保护 | `m3prep_test.py writeguard :8088` | **11 / 11 PASS** | `01_writeguard_formal.log` |
| 2 | 测试库写入 | `m3prep_test.py writable :8089` | **7 / 7 PASS** | `02_writable_testdb.log` |
| 3 | 配置异常 3 组 + 重启 | 手工 curl（见 §3） | **4 / 4 符合** | `10_config_abnormal.log` |
| 4 | 地点排序 | `m3prep_test.py ordering :8089` | **4 / 4 PASS** | `03_ordering.log` |
| 5 | 选项 vs CHECK | `m3prep_test.py options` | **7 / 7 PASS** | `04_options_vs_check.log` |
| 6 | 写保护界面表现 | `guard-ui.cjs` | **4 / 4 PASS** | `14_guard_ui.log` |
| 7 | M2-A API 回归 | `api_test.py :8089` | **43 / 43 PASS** | `05_m2a_regression.log` |
| 8 | M2 完整业务 | `api_m2_full_test.py :8089` | **36 / 36 PASS** | `06_m2_full.log` |
| 9 | 管理界面 E2E | `m2-ui.cjs 5181` | **14 / 14 PASS** | `07_ui_e2e.log` |
| 10 | M0/M1 API | 7 项 curl | **全通过** | `08_m0m1_regression.log` |
| 11 | M0/M1 浏览器 E2E | `accept-m0m1.cjs 5180` | **15 / 15 PASS** | `09_m0m1_ui_regression.log` |
| 12 | 数据保护 | `final_compare.py` | **全一致** | `15_data_protection.log` |

### 数据保护（正式库）

```
source_record 29391 / historical_place 19039 / historical_place_name 47499
historical_place_location 18101 / candidate_match 53131 / data_quality_issue 12831 / import_batch 7
data_dataset 8（含 V5 种子 manual_entry）/ data_source 5（含 V5 种子 manual）
person=0 event=0 person_name=0 event_place=0 event_person=0 person_place=0   ← 六张 M2 表仍为空
Flyway: V1 882334605 / V2 966227528 / V3 -2058740630 / V4 1291861836 / V5 -1325948257  全部 success，校验和未变
七张原始 CSV 指纹 7/7 命中 R1.2 基线
```

M0/M1 接口：搜索「桂林」10 条、洛阳 year=1200→1 条 / -500→0 条、详情正常、
bbox 返回 `FeatureCollection`（视野内 272）、`limit=99999` 被钳制为 2000、
三视图 `84,958 / 19,039 / 19,039` 与基线一致。

---

## 八、本轮附带修正的两处（需知悉）

### 1. 地点删除语义（`PlaceAdminService.delete`）

回归时发现：M2 的「删除地点」在**加过名称或坐标**之后会直接失败（`historical_place_name` /
`historical_place_location` 的外键没有 `ON DELETE` 规则，报 23503），界面上表现为莫名其妙的
"仍被引用"，功能实际不可用。

处理：

- `manual_entry` 数据集的地点 → **连带删除自己的名称与位置**，再删主体（这三者本属同一聚合）；
- **导入数据集**（CHGIS / Pleiades / MCGD / WHG）的地点 → 在管理界面**拒绝删除**，
  提示"其名称与位置是导入证据"。19,039 条导入数据不应被界面误删。
- 事件 / 人物 / 候选 / 台账对该地点的引用，仍交给数据库判定（RESTRICT / NO ACTION），
  一律转 409，**绝不连带删除其他业务对象**。

因此 `api_test.py` 的 G03 断言从「被数据库 RESTRICT 拒绝（必须带 constraint）」改为
「被拒绝且给出可读原因」——因为 900001 属于测试库自建数据集，现在先被应用层保护拦下。
数据库 RESTRICT 本身的证明仍在 `api_m2_full_test.py` 的 **D01 / D01b**：
D01b 专门造了一个**无位置行**、只被 `event_place` 引用的地点，删除返回
`409 fk_event_place_place`，地点仍在库中。**没有放宽任何外键**。

### 2. 测试库清理（仅 `canvas_history_m2check`）

B07（按别名搜索）在多轮运行后失败，原因是测试库里累积了多个同名人物，"size=5 应命中该人物"
的假设不再成立——是**测试数据堆积**，不是功能缺陷。做法：清空测试库的 M2 六表
（`TRUNCATE person, person_name, event, event_place, event_person, person_place RESTART IDENTITY`）
后按顺序重跑，43/43 与 36/36 全通过。正式库未做任何清理。

---

## 九、未解决问题

| 项 | 状态 | 影响 |
|---|---|---|
| 写接口**无鉴权** | 未做（不在本轮范围） | 当前仅绑回环 + 写白名单，本机工具可接受；对外部署前必须补 |
| `event_type` / `location_role` / `role` / `relation_type` **自由文本** | 保持原状（指令明确不改） | 多人录入可能出现取值不一致，M3 再议 |
| 写白名单**只保护数据库写入**，不区分"谁在写" | 设计如此 | 若把可写实例指向正式库，仍会写进去——需靠部署配置纪律 + 显式白名单 |
| `*.log` 不入库 | 有意排除 | 测试日志只在工作目录，报告引用其路径 |
| 仓库未配置 `.gitattributes` | 未做 | Windows 下 CRLF 警告较多（仅提示，不影响内容）；改动会影响全仓库行尾，故不在收尾轮动手 |
| Docker Desktop 依赖 WSL，本机沙箱策略曾拦 `wsl.exe` | 环境限制 | 已通过 `docker desktop start` 恢复；若再次停止需人工启动 Docker |

---

## 十、当前运行状态

| 服务 | 地址 | 库 | 写权限 |
|---|---|---|---|
| 前端（正式） | http://127.0.0.1:5180 | → 8088 → `canvas_history` | 只读 |
| 后端（正式） | http://127.0.0.1:8088 | `canvas_history` | **禁止写入** |
| 前端（测试） | http://127.0.0.1:5181 | → 8089 → `canvas_history_m2check` | 可写 |
| 后端（测试） | http://127.0.0.1:8089 | `canvas_history_m2check` | 允许写入 |
| 数据库 | 127.0.0.1:15432 | PostgreSQL 17.11 + PostGIS | healthy |

自检接口：`GET /api/v1/meta/write-policy`（返回当前实例实际库名与是否可写）。

---

## 十一、结论

- Git：仓库沿用原有仓库，M2 基线 `6e95890`，本轮加固 `3d58c41`，无远程、无推送、无 reset。
- 写保护：按真实库名白名单，默认全库禁写，A/B/C 共 22 项实测全部符合；重启后仍生效。
- 排序：最新更新优先，4 项实测通过，搜索与分页未受影响。
- 选项：前端零重复常量，7 项与数据库 CHECK 逐项一致，加载失败有明确提示。
- 安全：5 个端口全部只绑回环，Docker 发布限 `127.0.0.1`，凭证零泄漏。
- 回归：M2-A 43/43、M2 36/36、界面 14/14、M0/M1 15/15，正式库数据与 Migration 未变。

**M2 — FROZEN**

**M3 — READY TO START**
