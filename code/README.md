# 世界历史时空画布 · 代码工程（V1.0）

阶段一：工程基础设施已就绪——PostgreSQL 17 + PostGIS 3.6 容器化运行，宿主机可连，数据卷持久化。
阶段二：V2.1.1 数据层已落库——九张表、170 列、24 条 SQL 约束（C01–C26 去重）、三个派生视图，
      全部经 Flyway 版本化迁移（V1–V3）执行，空库可从零初始化。
阶段三：九表首次正式导入完成（29,391 / 19,039 / 47,499 / 18,101 / 53,131 / 12,831 / 7 / 7 / 4）。
阶段四 M0+M1：Spring Boot 只读 API（8088）+ Vue 3 + MapLibre 前端（5180）已可本地运行，
              支持历史地名搜索、地点详情、bbox 空间查询与地图联动。

## 1. 目录

```text
code/
  docker-compose.yml        # 数据库服务（api/web 预留段见文件末尾）
  .env.example              # 环境变量模板（提交）
  .env                      # 真实凭证（已 gitignore，不提交）
  .gitignore
  backend/                  # Spring Boot 只读查询 API
    src/main/java/.../web/             # PlaceController / MetaController
    src/main/java/.../service/         # PlaceQueryService（三条只读 SQL）
    src/main/resources/db/migration/   # Flyway 版本化 DDL，唯一迁移入口
      V1__enable_extensions.sql        # PostGIS 扩展（已执行）
      V2__core_data_model.sql          # 九张表 + 约束 + 索引（已执行）
      V3__derived_views.sql            # 三个派生视图（已执行）
    run-dev.sh                         # 从 ../.env 注入凭证启动 jar
  frontend/                 # Vue 3 + TS + MapLibre 前端
  tests/e2e/                # M0/M1 浏览器端到端验收脚本
  start-dev.sh              # 一键拉起后端 + 前端
  data/staging/             # 七张暂存 CSV（只读挂载，已 gitignore）
  ops/                      # 运维自检脚本与各阶段验收证据
```

## 2. 首次启动

```bash
cp .env.example .env
# 生成随机密码填入 POSTGRES_PASSWORD
openssl rand -base64 24 | tr -d '/+=' | cut -c1-24

docker compose up -d
docker compose ps            # 等到 STATUS 出现 (healthy)
```

## 2.5 应用启动（阶段四 M0/M1）

```bash
cd backend  && mvn -DskipTests package && bash run-dev.sh   # API  http://127.0.0.1:8088
cd frontend && npm install && npx vite --host 127.0.0.1      # WEB  http://127.0.0.1:5180
# 或一键： bash start-dev.sh
```

- 接口：`GET /api/v1/places`、`/api/v1/places/{id}`、`/api/v1/places/map?bbox=w,s,e,n`、`/api/v1/meta/health|stats`
- 地图底图需要 `code/.env` 的 `VITE_MAPTILER_API_KEY`（MapTiler **API key**，非 Service Token）。
  该值为空时界面会明确提示「底图未接入 MapTiler」，地点数据与检索仍正常，不会伪装成加载成功。
- 验收脚本与截图说明见 `tests/e2e/README.md`、`ops/reports/STAGE4_M0_M1_REPORT.md`。

## 2.6 M2 人物 / 事件接口（M2-2A）

```text
/api/v1/persons               GET 列表/搜索      POST 创建
/api/v1/persons/{id}          GET 详情           PUT 整体替换   DELETE 删除
/api/v1/persons/{id}/names    GET/POST，/{nameId} PUT/DELETE
/api/v1/persons/{id}/events   GET/POST，/{linkId} PUT/DELETE
/api/v1/persons/{id}/places   GET/POST，/{linkId} PUT/DELETE

/api/v1/events                GET 列表/搜索      POST 创建
/api/v1/events/{id}           GET 详情           PUT 整体替换   DELETE 删除
/api/v1/events/{id}/persons   GET/POST，/{linkId} PUT/DELETE
/api/v1/events/{id}/places    GET/POST，/{linkId} PUT/DELETE
```

- 时间字段一律**天文学纪年整数**（公元前 1 年 = 0），接口不做 BCE/CE 标签换算。
- 错误统一为 `{status, error, message, constraint?}`；SQLSTATE 23505→409、23514/23502/22P02→400、23503 按「仍被引用/不存在」分 409/400。
- 写入测试只在 `canvas_history_m2check` 上做；正式库写入需显式指定 `DB_URL`。
- 地点管理写入（M2 收尾补齐）：`/api/v1/places/admin` 列表、`POST /api/v1/places`、`PUT|DELETE /places/{id}`、
  `/places/{id}/names`、`/places/{id}/locations`。
- 前端管理入口：地图页左下「内容管理」，三页签（地点 / 人物 / 事件），左侧列表 + 右侧编辑，
  关联一律用对象选择器（不手填 ID）。时间输入用「公元前/公元 + 正整数」，换算集中在 `frontend/src/time.ts`。
- **改 `.env` 后必须重启 vite**；联调时可用 `API_HOST_PORT=8089 npx vite --port 5181` 把前端指向测试库。
- 接口清单与实测日志见 `ops/reports/M2_FINAL_REPORT.md`、`ops/reports/m2_final/`。

## 3. 日常命令

```bash
docker compose ps                                  # 状态
docker compose logs -f db                          # 日志
docker compose exec db psql -U canvas_app -d canvas_history   # 进入 psql
docker compose restart db                          # 重启（数据保留）
docker compose down                                # 停止并删容器（数据卷保留）
docker compose down -v                             # 危险：连数据卷一起删除，禁止随手使用
```

宿主机直连（需要本机 psql 或任意 PG 客户端）：

```text
host=127.0.0.1  port=55432  db=canvas_history  user=canvas_app  password=见 .env
```

## 4. 自检

```bash
python -m pip install --target ./ops/.deps psycopg2-binary   # 一次性
PYTHONPATH=./ops/.deps python ops/verify_db.py check          # 连接 + PostGIS
PYTHONPATH=./ops/.deps python ops/verify_db.py write          # 写持久化标记
docker compose down && docker compose up -d                   # 重建容器
PYTHONPATH=./ops/.deps python ops/verify_db.py read           # 标记仍在 = 卷持久化通过
```

## 5. 数据库迁移（Flyway）

```bash
bash ops/flyway.sh canvas_history info        # 迁移状态
bash ops/flyway.sh canvas_history migrate     # 执行未应用的迁移（幂等，重复执行无副作用）
```

- 脚本目录：`backend/src/main/resources/db/migration`，Spring Boot 阶段四直接复用。
- 已执行过的迁移文件**不得修改**（checksum 已记录），变更一律新增 V4、V5…
- 空库初始化验证用独立库，不碰正式库：

```bash
docker compose exec db psql -U canvas_app -d postgres -c "CREATE DATABASE canvas_history_migrationcheck;"
bash ops/flyway.sh canvas_history_migrationcheck migrate
PYTHONPATH=./ops/.deps python ops/verify_schema.py canvas_history_migrationcheck
```

## 6. 版本与端口

| 项 | 值 |
|---|---|
| 镜像 | `postgis/postgis:17-3.6`（PostgreSQL 17.11 / PostGIS 3.6.4，固定版本，不使用 latest） |
| 容器名 | `canvas-history-db` |
| 卷 | `canvas-history-pgdata` |
| 网络 | `canvas-history-net` |
| 宿主端口 | `127.0.0.1:55432 -> 5432`（仅本机，不对局域网暴露） |
| 预留端口 | api 8088 / web 5180（5432、5433、5173 已被本机其他项目占用） |

## 7. 铁律

- 真实凭证只写在 `.env`，不进源码、不进 Git、不进日志。
- 数据库 schema 只通过 Flyway 迁移变更，不手工改表。
- `data/staging/` 是七张原始暂存 CSV 的只读副本，导入程序只读不写。
- 不使用 `latest` 镜像标签。
