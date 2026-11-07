# DEV 环境隔离与数据库复制验收报告

> 项目：World History Spacetime Canvas
> 日期：2026-11-06
> 范围：仅 DEV 环境（未制作 BAT、未做 Release、未部署 Prod、未 Commit / Push）
> 结论：**通过**。DEV 与 PROD 双实例并行运行，数据完整复制，配置与端口完全隔离

---

## 一、原有环境盘点

### 1.1 PROD 现状（施工前）

| 项 | 值 |
|---|---|
| 容器 | `canvas-history-db`（ID `c982fb80…`，healthy） |
| Compose 项目 | `canvas-history` |
| 镜像 | `postgis/postgis:17-3.6` |
| 端口 | `127.0.0.1:15432 -> 5432` |
| 数据卷 | `canvas-history-pgdata`（6.697 GB） |
| 网络 | `canvas-history-net` |
| 数据库 | `canvas_history` / 账号 `canvas_app` |
| 库体积 | 608 MB |
| Flyway | V10（10 条迁移，全部 success） |
| 扩展 | `fuzzystrmatch 1.2`、`plpgsql 1.0`、`postgis 3.6.4` |
| API 进程 | java PID 19932，`-jar target/canvas-history-api.jar --server.port=8088` |
| 前端进程 | vite PID 36036，`--host 127.0.0.1 --port 5180`，proxy → 8088 |

### 1.2 施工前已确认的隔离缺口

| 缺口 | 状态 |
|---|---|
| 全项目只有一份 `.env`，指向 `canvas_history` | 已确认 |
| `run-dev.sh` 默认库名回退到 `canvas_history` | 已确认（本次未改动，见遗留问题 §9.3） |
| 无 DEV 容器、无 DEV 卷、无 DEV 网络、无 `.env.dev` | 已确认（干净起点） |
| 端口 15433 / 8089 / 5181 均空闲 | 已确认 |

---

## 二、DEV 新建资源清单

### 2.1 容器与基础设施

| 项 | DEV 值 | 与 PROD 的关系 |
|---|---|---|
| 容器 | `canvas-history-db-dev`（ID `89283f93…`） | 不同容器，独立进程 |
| Compose 项目 | `canvas-history-dev` | 不同项目名，`down -v` 不会波及 PROD |
| 镜像 | `postgis/postgis:17-3.6` | 同一镜像，版本完全一致 |
| 端口 | `127.0.0.1:15433 -> 5432` | 与 15432 分离 |
| 数据卷 | `canvas-history-dev-pgdata`（698.1 MB） | 独立卷，路径不同 |
| 网络 | `canvas-history-dev-net`，仅挂 `canvas-history-db-dev` | 独立网络 |
| 数据库 | `canvas_history_dev` | 独立库 |
| 账号 | `canvas_app_dev` | 独立账号 |
| 库体积 | 321 MB | 来自 PROD 复制，无历史膨胀 |

### 2.2 服务进程

| 服务 | DEV | PROD |
|---|---|---|
| 数据库 | `canvas-history-db-dev` : 15433 | `canvas-history-db` : 15432 |
| API | java PID 3580 : **8089** | java PID 19932 : **8088** |
| 前端 | vite PID 10880 : **5181** | vite PID 32772 : **5180** |

四个进程同时运行，互不干扰。

---

## 三、数据库复制过程

### 3.1 方法

采用 `pg_dump -Fc` + `pg_restore`，**未复制运行中的数据目录**（符合任务书禁止项）。

```
1. docker exec canvas-history-db pg_dump -U canvas_app -Fc -d canvas_history > seed.dump
      → 33 MB，耗时 2.96 秒（只读，不写生产）
2. 通过 stdin 管道送入 DEV 容器（避免 docker cp 的 Windows 路径转换问题）
3. docker exec canvas-history-db-dev pg_restore -U canvas_app_dev \
      -d canvas_history_dev --no-owner --no-acl --single-transaction seed.dump
      → 耗时 3.03 秒，零错误
4. 校验完成后删除宿主机与容器内的临时 dump
```

`--no-owner --no-acl` 的原因：dump 内对象属主是 `canvas_app`，DEV 账号是 `canvas_app_dev`，忽略属主避免权限错乱。

### 3.2 遇到并解决的问题

**问题 1：`CREATE SCHEMA "tiger" already exists`**

`--single-transaction` 使整次恢复原子回滚，DEV 库未被污染。根因是 DEV 镜像初始化时自带 `postgis_tiger_geocoder` / `postgis_topology` 两个扩展及其 schema，而 PROD 只有 3 个扩展。

处理：在 DEV 空库上 `DROP EXTENSION postgis_tiger_geocoder/postgis_topology CASCADE` + `DROP SCHEMA tiger/topology CASCADE`，使 DEV 扩展集合与 PROD 完全一致后重新恢复。**该操作只作用于新建的 DEV 空库，未触及 PROD。**

**问题 2：`docker cp` 的 Git Bash 路径转换**

`docker cp` 把 `/c/Users/...` 解析成 `e:\c\Users\...`，两次失败。改用 `docker exec -i ... sh -c 'cat > /tmp/seed.dump' < file` 的管道方式，并配合 `MSYS_NO_PATHCONV=1`，一次成功。

### 3.3 复制结果核对

| 校验项 | PROD | DEV | 结果 |
|---|---|---|---|
| 基表数（public） | 19 | 19 | ✅ |
| 视图数 | 5 | 5 | ✅ |
| `historical_place` | 57,967 | 57,967 | ✅ |
| `historical_place_name` | 84,554 | 84,554 | ✅ |
| `historical_place_location` | 53,792 | 53,792 | ✅ |
| `source_record` | 157,220 | 157,220 | ✅ |
| `candidate_match` | 66,311 | 66,311 | ✅ |
| `data_quality_issue` | 20,824 | 20,824 | ✅ |
| `data_dataset` / `data_source` | 9 / 5 | 9 / 5 | ✅ |
| `import_batch` | 15 | 15 | ✅ |
| `spatial_ref_sys` | 8,500 | 8,500 | ✅ |
| event / person / polity | 0 / 0 / 0 | 0 / 0 / 0 | ✅ |
| **19 张基表逐表行数** | — | — | ✅ **完全一致（diff 无差异）** |
| Flyway 记录（rank/version/checksum/success） | 10 条 | 10 条 | ✅ **逐字段一致** |
| 扩展集合 | 3 个 | 3 个 | ✅ **完全一致** |
| 已解决质量问题 | 197 | 197 | ✅ |
| 有几何的位置 | 53,782 | 53,782 | ✅ |
| SRID 种类 | 1 | 1 | ✅ |
| 几何类型分布 | — | POINT 44,775 / LINESTRING 4,893 / POLYGON 4,112 / MULTIPOLYGON 2 | ✅ |

---

## 四、修改文件清单

### 4.1 新增（3 个）

| 文件 | 行数 | 作用 |
|---|---|---|
| `code/docker-compose.dev.yml` | 50 | DEV 独立 compose：项目名 `canvas-history-dev`、容器/卷/网络/端口全部带 dev 标识；凭证只从 `.env.dev` 读 |
| `code/.env.dev` | 22 | DEV 环境变量。**已被根 `.gitignore` 的 `.env.*` 规则忽略**，不会入库 |
| `code/backend/run-dev-api.sh` | 86 | DEV 专用后端启动器，三道断言（见 §7.2） |

### 4.2 修改（2 个）

| 文件 | 改动 |
|---|---|
| `code/start-dev.sh` | 从「调用 `run-dev.sh`（连生产）」改为「调用 `run-dev-api.sh`（连 DEV）」；前端启动加 `VITE_ENV_FILE=../.env.dev`；启动后自动校验 `health.database == canvas_history_dev`，不符则杀掉进程 |
| `code/frontend/vite.config.ts` | 环境文件选择从「隐式（有 `.env.dev` 就用）」改为「显式（只有设置 `VITE_ENV_FILE` 才切换）」，且构建模式忽略该变量 |

### 4.3 关于 vite.config.ts 的这次反复（重要）

第一版实现是「开发模式下若 `.env.dev` 存在则优先读它」。实测立刻暴露问题：**5180 的旧 vite 实例热重载配置后也读到了 `.env.dev`，导致本应指向生产 8088 的前端代理指向了 DEV 8089。**

这说明「按文件是否存在猜测环境」是危险的隐式规则。已改为显式：

- `npx vite`（不带变量）→ 读 `.env` → 5180 → 8088 → `canvas_history`
- `VITE_ENV_FILE=../.env.dev npx vite` → 读 `.env.dev` → 5181 → 8089 → `canvas_history_dev`
- `vite build` → 强制读 `.env`，忽略 `VITE_ENV_FILE`

改完后实测两条链路各自正确（见 §8.2）。

---

## 五、DEV 启动方式

### 5.1 首次或重启后（先起数据库）

```bash
cd E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code
docker compose -f docker-compose.dev.yml --env-file .env.dev up -d
```

### 5.2 启动前后端

```bash
cd E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code
bash start-dev.sh
```

脚本会：加载 `.env.dev` → 校验库名与白名单 → 校验 DEV 容器健康 → 启动 8089 后端与 5181 前端 → 自动请求 health 并断言 `database == canvas_history_dev`。

### 5.3 只起后端 / 只起前端

```bash
bash backend/run-dev-api.sh                        # 仅 8089
cd frontend && VITE_ENV_FILE=../.env.dev npx vite --host 127.0.0.1 --port 5181   # 仅 5181
```

### 5.4 停止

```bash
# 停服务：Ctrl+C（start-dev.sh 有 trap 会带走子进程）
# 停数据库（保留数据）：
docker compose -f docker-compose.dev.yml --env-file .env.dev down
```

**切勿**在生产目录执行 `docker compose down -v`；DEV 的 `-v` 只会删 `canvas-history-dev-pgdata`。

---

## 六、DEV 访问地址

| 用途 | 地址 |
|---|---|
| DEV 前端 | http://127.0.0.1:5181/ |
| DEV API 健康 | http://127.0.0.1:8089/api/v1/meta/health |
| DEV API 统计 | http://127.0.0.1:8089/api/v1/meta/stats |
| DEV 数据库 | `127.0.0.1:15433`，库 `canvas_history_dev`，账号 `canvas_app_dev` |

对照 PROD：前端 5180 / API 8088 / 数据库 15432。

---

## 七、数据库连接配置说明

### 7.1 配置来源分离

| 环境 | 配置文件 | 库名 | 端口 | 写白名单 |
|---|---|---|---|---|
| PROD | `code/.env` | `canvas_history` | 15432 | 由 `run-prod.sh` 注入 `canvas_history` |
| DEV | `code/.env.dev` | `canvas_history_dev` | 15433 | `canvas_history_dev` |

`run-dev-api.sh` **只读 `.env.dev`**；文件不存在时直接退出，**不回退到 `.env`**。

### 7.2 三道强制断言（不满足即拒绝启动）

| # | 断言 | 拒绝时的退出码 |
|---|---|---|
| 1 | 目标库名必须是 `canvas_history_dev` | 2 |
| 2 | 写白名单必须且只能等于 `canvas_history_dev` | 2 |
| 3 | 容器 `canvas-history-db-dev` 的健康状态必须精确等于 `healthy` | 2 |

三者的实测结果见 §8.3。

### 7.3 写保护

DEV 实例的 `writeAllowed=true`，但白名单只有 `canvas_history_dev`；PROD 的白名单只有 `canvas_history`。二者按**实际连接的库名**精确匹配（`current_database()`），不看端口，不支持通配。

---

## 八、验收测试结果

### 8.1 数据库独立性

| 测试 | 结果 |
|---|---|
| PROD 与 DEV 为两个独立 PostgreSQL 实例 | ✅ 容器 ID 不同、卷路径不同、网络不同、端口不同 |
| DEV 数据来自当前生产库 | ✅ 19 张基表逐表行数 diff 无差异 |
| 关键表数据完整 | ✅ 六张核心表全部吻合 |
| Flyway 状态正确 | ✅ 10 条记录 rank/version/checksum/success 逐字段一致 |
| PostGIS 扩展正常 | ✅ `postgis 3.6.4`，扩展集合与 PROD 完全相同 |

### 8.2 环境可用性

| 测试 | 结果 |
|---|---|
| DEV 后端启动 | ✅ 8089，health `status=ok` |
| DEV 前端访问 | ✅ 5181 返回 HTTP 200 |
| DEV API 正常 | ✅ `/meta/health`、`/meta/stats`、`/places`、`/places/map`、`/places/{id}` 全部 200 |
| DEV 统计与 PROD 一致 | ✅ `places 57967 / names 84554 / locations 53792 / geom 53782 / ledger 20824` |
| DEV 地图接口 | ✅ HTTP 200，162 KB，0.36 秒 |
| 前端代理指向正确 | ✅ 5181 → 8089 → `canvas_history_dev`；5180 → 8088 → `canvas_history` |
| PROD 与 DEV 同时运行 | ✅ 2 个数据库容器 + 2 个 API + 2 个前端，四进程并存 |

### 8.3 隔离测试（读写）

**DEV 写入测试**

```
POST http://127.0.0.1:8089/api/v1/places  {"canonicalName":"DEV-SMOKE-TEST",...}
→ HTTP 201  {"created":true,"placeId":115944}
```

| 检查 | DEV | PROD |
|---|---|---|
| 读取 placeId 115944 | ✅ 200，返回完整详情 | ✅ **404（不存在）** |
| `historical_place` 行数 | 57,968 | **57,967（未变）** |

清理：`DELETE /places/115944` → 200，DEV 回到 57,967，`canonical_name='DEV-SMOKE-TEST'` 残留 0 条。

**结论：DEV 写入对 PROD 零影响，反向同理。**

### 8.4 六维度隔离核对

| 维度 | PROD | DEV | 隔离 |
|---|---|---|---|
| 容器名称 | `canvas-history-db` | `canvas-history-db-dev` | ✅ |
| 数据库名称 | `canvas_history` | `canvas_history_dev` | ✅ |
| 连接地址 | `127.0.0.1:15432` | `127.0.0.1:15433` | ✅ |
| Volume | `canvas-history-pgdata` | `canvas-history-dev-pgdata` | ✅ |
| 网络 | `canvas-history-net`（仅 db） | `canvas-history-dev-net`（仅 db-dev） | ✅ |
| 端口 | 15432 / 8088 / 5180 | 15433 / 8089 / 5181 | ✅ |

### 8.5 断言测试（故意配错）

| 场景 | 期望 | 实测 |
|---|---|---|
| `DB_NAME=canvas_history bash run-dev-api.sh` | 拒绝 | ✅ `拒绝启动：…只允许连接 canvas_history_dev，收到 'canvas_history'`，exit 2 |
| `DB_WRITE_ALLOWED_DATABASES=canvas_history bash run-dev-api.sh` | 拒绝 | ✅ `拒绝启动：DEV 写白名单必须是 'canvas_history_dev'`，exit 2 |
| DEV 容器停止时启动 | 拒绝 | ✅ `状态为 'unhealthy'，未就绪`，exit 2 |

**过程中修复的两个自身缺陷**：

1. 最初未保存外部传入的 `DB_WRITE_ALLOWED_DATABASES`，被 `.env.dev` 覆盖 → 断言 2 形同虚设，已修。
2. 最初用 `grep -q healthy` 判断容器状态，而 `unhealthy` 含 `healthy` 子串 → 误判通过，已改为精确字符串比较。

### 8.6 PROD 未受影响的最终确认

施工前后对比：

```
施工前：57967|84554|53792|157220|66311|20824|9|5|10
施工后：57967|84554|53792|157220|66311|20824|9|5|10
```

PROD 卷占用仍为 6.697 GB，Flyway 仍为 V10，未执行任何迁移，未停止或重建生产容器，未修改生产配置。

---

## 九、遗留问题

### 9.1 `canvas_app_dev` 是超级用户（中）

Compose 的 `POSTGRES_USER` 必然是 superuser。DEV 目前用它，功能无碍，但权限过大。

建议：后续创建 `canvas_app_dev` 之外的普通角色用于应用连接，superuser 仅用于初始化。**PROD 的 `canvas_app` 同样是 superuser，属于独立整改项。**

### 9.2 `mvn` 不在 PATH（中，P2 阻断项）

构建后端仍需手工指定 `C:\Users\the_z\.m2\wrapper\dists\apache-maven-3.9.9-bin\33b4b2b4\apache-maven-3.9.9\bin\mvn.cmd`。`start-dev.sh` 中「jar 不存在则构建」的分支直接调用 `mvn` 会失败。需要补 Maven Wrapper（P2）。

### 9.3 旧 `run-dev.sh` 仍可误连生产（高，本次按边界未改）

`run-dev.sh` 的 `DB_NAME="${DB_NAME:-${POSTGRES_DB:-canvas_history}}"` 仍在，且 `run-prod.sh` 依赖它启动生产。本次**没有动它**，因为改动会破坏生产启动器。

当前状态下，`bash backend/run-dev.sh` 仍会连生产库（只读，因白名单为空）。这是已知风险，需在 P3 实现 BAT 01 时一并处理（把通用启动器与生产启动器彻底拆开）。

### 9.4 DEV 后端 jar 仍是 11-05 构建的产物

本次只改前端配置与启动脚本，未重新打包后端。jar 内不含 `run-dev-api.sh`（它是外部脚本），所以功能无影响。但若后续修改 Java 代码，需在 PATH 修好后重新构建。

### 9.5 生产实例内仍有 16 个历史测试库（低）

合计约 5.1 GB，位于 `canvas-history-db` 内。本次未清理。建议保持原样并在 DEPLOY.md 中记录，清理需单独授权。

### 9.6 前端 dev server 不是生产形态（信息）

5180/5181 都是 vite 开发服务器。单 Jar 同源部署（R2 §7）尚未验证，属 P2 范围。

### 9.7 `.env.dev` 与生产共用同一把 MapTiler Key（低）

DEV 从生产 `.env` 复制了同一把受限 key。若后续要做 key 分环境管理，需在 P2 的运行时注入方案中一并设计。

---

## 十、本次未做（边界声明）

- 未制作任何 BAT（01/02/03）
- 未创建 Release 包、未创建 Prod 部署目录
- 未 Commit / Push，未打 Tag
- 未修改生产数据库、未对生产执行 Migration
- 未停止或重建生产容器，未删除或覆盖生产卷
- 未执行 Docker 全局清理（`system prune` 等）
- 未建设正式备份体系（复制用的临时 dump 已删除）
- 未清理 16 个历史测试库

---

**DEV 环境已可用，等待 Owner 验收后安排下一步（BAT 01 / P2 能力补齐）。**
