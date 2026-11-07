# P0 只读盘点报告

> 依据：R2 设计稿 第九节 P0 / 第十节重点风险清单
> 日期：2026-11-06 10:36
> 性质：**只读**。未创建容器、未创建数据库、未修改配置、未执行 Migration、未创建 BAT、未 Commit
> 唯一写操作：为验证备份可用性，向系统临时目录生成一份 dump 并立即删除（详见 §7）

---

## 结论摘要

| # | 检查项 | 结论 |
|---|---|---|
| 1 | 容器与 Volume 对应关系 | ✅ 清晰，compose project `canvas-history`，卷 `canvas-history-pgdata` |
| 2 | 数据库是否仍为 V10 | ✅ V10，10 条迁移全部 success，0 失败 |
| 3 | API / 前端真实启动命令 | ✅ 已抓到完整命令行（§3） |
| 4 | 运行 Jar 路径与 SHA256 | ✅ 已取得（§3） |
| 5 | Vite 实例用途 | ✅ 纯开发预览，proxy 到 8088，非生产服务 |
| 6 | `.env` 被谁读取 | ✅ 3 处 shell + 全部 Python + compose + vite，共 6 条链 |
| 7 | 正式库连接配置来源 | ✅ 唯一来源 `code/.env`，`POSTGRES_DB=canvas_history` |
| 8 | **DEV 误连正式库路径** | ⚠️ **存在 8 条，其中 2 条会写库。当前隔离度为零** |
| 9 | 现有备份是否可用 | ⚠️ **无任何备份文件**；备份能力本身可用（33 MB / 2.35 s） |
| 10 | DEV 建库是否触碰现有卷 | ✅ 用独立容器 + 独立卷不会；**但不可复用现有容器** |

**一句话**：基础设施本身健康，数据完好；**风险全部集中在「DEV 与 PROD 共用同一份 `.env`、同一套默认值」上**，与 R2 的判断一致。

---

## 1. 容器、数据卷与网络

| 项 | 实测 |
|---|---|
| 容器 | `canvas-history-db`，镜像 `postgis/postgis:17-3.6`，状态 `Up 2 hours (healthy)` |
| 端口映射 | `127.0.0.1:15432 -> 5432/tcp` |
| Compose 项目 | `canvas-history`（label `com.docker.compose.project`） |
| Compose 工作目录 | `E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code` |
| Compose 文件 | `code\docker-compose.yml` |
| 数据卷 | `canvas-history-pgdata` → `/var/lib/docker/volumes/canvas-history-pgdata/_data` |
| 卷标签 | `com.docker.compose.project=canvas-history`，`com.docker.compose.volume=pgdata` |
| 网络 | `canvas-history-net`（bridge），当前仅挂载 `canvas-history-db` |
| 只读挂载 | `code\data\staging` → 容器 `/staging:ro` |
| Docker 数据根 | `/var/lib/docker`（WSL2，overlayfs）；镜像 20.52 GB、卷 7.96 GB、构建缓存 40.14 GB |

**判定**：容器与卷一一对应，无孤立卷、无重名容器。这是 P1 建 DEV 时的安全基础。

---

## 2. 数据库身份与版本

### 2.1 生产库基线（与 R2 §3.1 逐项核对）

| 项 | R2 记录值 | 实测值 | 一致 |
|---|---|---|---|
| 数据库 | canvas_history | canvas_history | ✅ |
| PostgreSQL | 17 + PostGIS 3.6 | 17.11 | ✅ |
| Flyway | V10 | V10（10 条，success=10，failed=0） | ✅ |
| 历史地点 | 57,967 | 57,967 | ✅ |
| 名称 | 84,554 | 84,554 | ✅ |
| 位置 | 53,792 | 53,792 | ✅ |
| 源记录 | 157,220 | 157,220 | ✅ |
| 候选匹配 | 66,311 | 66,311 | ✅ |
| 质量台账 | 20,824 | 20,824 | ✅ |
| 事件/人物/政权 | 0 / 0 / 0 | 0 / 0 / 0 | ✅ |

库体积 608 MB；schema = `public` / `infra` / `tiger` / `topology`。

### 2.2 新发现：同一实例内有 17 个库

```
canvas_history_m4_4b_protect   729 MB
canvas_history_m4_5_verify     632 MB
canvas_history_m4_4c_m2        630 MB
canvas_history_m4_4b           630 MB
canvas_history                 608 MB   ← 生产
canvas_history_m2check         480 MB
canvas_history_p0_rehearsal    397 MB
canvas_history_stage3          301 MB
canvas_history_stage3_r1       283 MB
canvas_history_stage3_r11      283 MB
canvas_history_stage3_r12      283 MB
canvas_history_m4check         170 MB
canvas_history_p0_backup_restore 121 MB
canvas_history_stage3_r11_fault 43 MB
canvas_history_stage3_r1_fault  43 MB
canvas_history_stage3_r12_fault 43 MB
canvas_history_migrationcheck   16 MB
```

历史测试库合计约 **5.1 GB**，卷总占用 6.7 GB 基本被它们占满。

**影响**：
1. R2 要求「DEV 使用独立容器」是**正确且必要**的。若只在现有容器里新建 `canvas_history_dev`，它会与 16 个历史库共享同一 PostgreSQL 实例与卷，达不到 R2 §1.1 要求的「DEV 任何操作不影响 PROD」——虽然逻辑隔离成立，但 `DROP DATABASE` 误操作、磁盘打满、实例级重启都会波及生产。
2. 这些库是历史遗留，**本轮不动**。清理需单独授权（§9 建议）。

### 2.3 角色与权限（安全弱点）

```
rolname      superuser  createdb
canvas_app   t          t
```

生产应用使用 **superuser 账号**连接。任何通过应用层 SQL 注入或配置误用，都可能触及实例级操作。

R2 §3.2 已规划 DEV 用 `canvas_app_dev`，建议同时明确：**该账号不得为 superuser**，只需 `CONNECT` + 目标库所有权。生产账号降权属于独立整改项，不在本轮。

### 2.4 DEV 库现状

`canvas_history_dev` **不存在**（`pg_database` 计数 0）。首次创建是干净起点。

---

## 3. 运行进程、Jar 与前端实例

### 3.1 进程实况

| PID | 程序 | 完整命令行 | 启动时间 |
|---|---|---|---|
| 19932 | java.exe | `"C:\Program Files\Microsoft\jdk-25.0.3.9-hotspot\bin\java.exe" -jar target/canvas-history-api.jar --server.port=8088` | 11-06 09:50:04 |
| 27716 | node.exe | `npx-cli.js vite --host 127.0.0.1 --port 5180` | 11-06 09:50:07 |
| 36036 | node.exe | `vite.js --host 127.0.0.1 --port 5180`（实际监听） | 11-06 09:50:16 |

API 的工作目录是 `code\backend`（命令行用相对路径 `target/...`）。

### 3.2 Jar 身份

| 项 | 值 |
|---|---|
| 路径 | `code\backend\target\canvas-history-api.jar` |
| 大小 | 23,699,728 字节 |
| SHA256 | `c23d767fb220e830b16a70809ccd1e07a1a2c9e646c502c24832b1d7ef5f0aae` |
| 构建时间 | 2026-11-05 08:58–08:59 |
| MANIFEST | `Implementation-Version: 0.1.0`，无 `git.properties`，无 `build-info` |

**这是 P7 首次登记时必须记录的身份依据**。注意：该 SHA256 无法从源码复现（构建未记录 Git SHA、未固定时间戳），所以「重新构建得到同一个 jar」不可行——只能以这份文件本身为准。

### 3.3 前端

| 项 | 值 |
|---|---|
| `frontend/dist` | **不存在**（从未构建） |
| 当前服务方式 | Vite dev server（PID 36036），`/api` proxy → `127.0.0.1:8088` |
| 用途 | **仅供开发预览与代理，不是生产服务器** |

R2 §7 的单 Jar 方案要求 dist 进入 jar——这一步从未验证过，属于 P2 的硬性验证项。

### 3.4 运行实例身份

```
health:       {"status":"ok","database":"canvas_history","user":"canvas_app","postgres":"17.11"}
write-policy: {"database":"canvas_history","allowedDatabases":["canvas_history"],
               "writeAllowed":true,"configProblems":[]}
```

当前 8088 实例**可写生产库**（`run-prod.sh` 白名单设计）。这就是 R2 所说的「DEV 联调误连生产即写入」的现实基础。

---

## 4. 端口占用

| 端口 | 状态 | 占用者 | R2 规划 |
|---:|---|---|---|
| 15432 | 占用 | docker (canvas-history-db) | PROD PG |
| **15433** | **空闲** | — | DEV PG ✅ 可行 |
| 8088 | 占用 | java PID 19932 | 未在 R2 端口表中（见 §8 差异） |
| **8089** | **空闲** | — | DEV API ✅ 可行 |
| 5180 | 占用 | node PID 36036（vite） | PROD API（单 Jar） ⚠️ 需先停 vite |
| **5181** | **空闲** | — | DEV 前端 ✅ 可行 |

**补充证据**：历史 E2E 脚本 `tests/e2e-m4c/places-e2e.cjs` 的注释写明「5180 → 代理到 8089 → 库 canvas_history_m4_4b」。说明 **8089 + 测试库** 是项目既有的 DEV 惯例，R2 的端口规划与之吻合，不是新发明的约定。

---

## 5. `.env` 读取链（完整）

### 5.1 唯一配置源

全项目只有 **1 份** `.env`：`code\.env`（另有 `.env.example` 模板）。

```
COMPOSE_PROJECT_NAME=canvas-history
POSTGRES_DB=canvas_history        ← 指向生产
POSTGRES_USER=canvas_app
POSTGRES_PASSWORD=***（已隐藏）
DB_HOST_PORT=15432
TZ=Asia/Shanghai
VITE_MAPTILER_API_KEY=***（已隐藏）
API_HOST_PORT=8088
WEB_HOST_PORT=5180
DB_WRITE_ALLOWED_DATABASES=       ← 空 = 默认只读
```

### 5.2 六条读取链

| # | 读取者 | 方式 | 用途 |
|---|---|---|---|
| 1 | `backend/run-dev.sh:23` | `set -a; . ../.env` | 全量注入，拼 `DB_URL` |
| 2 | `backend/run-prod.sh:54` | `grep API_HOST_PORT` | 仅取端口（凭证仍由 run-dev.sh 加载） |
| 3 | `ops/flyway.sh:26` | `set -a; . ./.env` | 迁移凭证 |
| 4 | 全部 Python 脚本 | `import_staging.load_env()` 硬读 `CODE_ROOT/.env` | 数据库连接 |
| 5 | `docker-compose.yml` | compose 自动加载同目录 `.env` | 建库、端口、卷 |
| 6 | `frontend/vite.config.ts` | `readFileSync(here + '../.env')` | MapTiler Key + 端口 + proxy |

`load_env()` 实现（`ops/import_staging.py:204`）**只读一个固定路径**，没有环境变量覆盖、没有 profile 概念。

### 5.3 安全事实

`.env` **从未进入 Git 历史**（`git log --all -- code/.env` 为空，`--diff-filter=A` 亦无记录）。凭证未泄漏。

---

## 6. DEV 误连正式库的路径（R2 最高优先级项）

### 6.1 完整清单

| # | 路径 | 默认落点 | 是否写库 | 严重度 |
|---|---|---|---|---|
| 1 | `bash backend/run-dev.sh`（不带参数） | `DB_NAME="${DB_NAME:-${POSTGRES_DB:-canvas_history}}"` → **canvas_history** | 否（白名单空 → 只读） | **高** |
| 2 | `bash start-dev.sh`（间接调用 #1） | 同上 | 否 | **高** |
| 3 | `bash backend/run-prod.sh` | 强制 canvas_history | **是（可写）** | **高**（设计如此，但无场景隔离） |
| 4 | `python ops/verify_db.py:48` | `env["POSTGRES_DB"]` → canvas_history | 否 | 中 |
| 5 | `python ops/v1b/test_cm.py:45` | **硬编码** `dbname="canvas_history"` | 否（只读校验），但读生产 | **高** |
| 6 | `python ops/v1b/bench_views.py:108` | `--db` 默认 `canvas_history` | 否 | 中 |
| 7 | `python ops/p0/supplemental/audit_*.py` | `--baseline` 默认 `canvas_history` | 否 | 中 |
| 8 | `bash ops/flyway.sh canvas_history migrate` | 库名由参数决定，**无白名单校验** | **是** | **高** |

### 6.2 根因

三个条件叠加：

1. **只有一份 `.env`**，且 `POSTGRES_DB=canvas_history`；
2. **默认值链** `DB_NAME → POSTGRES_DB → canvas_history` 三级回退，任何一级为空都落到生产；
3. **没有任何库名断言**。`run-dev.sh` 是纯粹的「连上去再说」，`run-prod.sh` 有校验但只保护自己。

R2 §3.4 要求的「DEV 启动脚本必须检查数据库名，不是 `canvas_history_dev` 就拒绝启动」——**当前完全不存在**。

### 6.3 现有防护（不足以依赖）

- `run-prod.sh` 有 `TARGET_DB` + 白名单双重校验 ✅（但它本来就是生产启动器）
- `application.yml` 的 `app.write.allowed-databases` 默认空 → 只读 ✅（但 `run-prod.sh` 会覆盖为可写）
- `ephemeral_db.py` 有「只删自己建的库」范式 ✅（可作为 DEV 建库实现参考）

---

## 7. 备份与恢复现状

### 7.1 现有备份：零

在项目目录与 `E:\01_Work\04_Prod` 全量搜索 `*.dump` / `*.backup` / `*.sql.gz`，Canvas 项目**没有任何备份文件**（命中的都是 myledger / family-growth-bank 的备份）。

生产库 608 MB，**当前处于零备份状态**。这是 P0 发现的最紧迫事实。

### 7.2 备份能力：可用（已实测）

在系统临时目录做了一次真实 dump 并立即删除：

| 项 | 实测值 |
|---|---|
| 命令 | `docker exec canvas-history-db pg_dump -U canvas_app -Fc -d canvas_history` |
| 耗时 | **2.35 秒** |
| 体积 | **33 MB**（608 MB 库，gzip 压缩） |
| `pg_restore --list` | ✅ 成功，TOC Entries 260，对象条目 255 |
| Dump Version | 1.16-0 |

### 7.3 重要发现：SHA256 不能跨次比对

两次连续 dump 的 SHA256 不同（`c09027…` vs `034562…`），因为 custom format 内嵌创建时间戳。

**结论**：备份校验只能用「`pg_restore --list` 成功 + 对象数 + 体积区间」，**不能**用「与前次 SHA256 相同」或「体积必须大于前次 50%」来判断。R2 §6 取消 50% 规则的判断是**正确**的，本报告实测数据支持该决定。

### 7.4 恢复能力

- 未做实际恢复演练（P0 不做写操作）。`verify_backup_restore.py` 存在，可在 P5 复用。
- **恢复目标库必须是临时库**，不能是 `canvas_history`——需在 P5 演练中验证。

---

## 8. DEV 建库的影响评估

### 8.1 隔离可行性

| 项 | 结论 |
|---|---|
| 独立容器 `canvas-history-db-dev` | ✅ 名字未被占用 |
| 独立卷 `canvas-history-dev-pgdata` | ✅ 不存在，可新建 |
| 独立端口 15433 | ✅ 空闲 |
| 独立网络 `canvas-history-dev-net` | ✅ 不存在 |
| 镜像 | ✅ `postgis/postgis:17-3.6` 已在本地，**无需拉取** |
| 对现有卷的影响 | ✅ 新卷独立，`docker volume rm` 不会波及 `canvas-history-pgdata` |
| 磁盘 | E: 769.6 GB 空闲 / C: 108 GB / D: 62.1 GB，充足 |
| 预计占用 | 镜像复用 0 + 初始卷 <1 GB，导入后约 600–700 MB |

### 8.2 三条硬性约束（P1 必须遵守）

1. **compose project 名必须是 `canvas-history-dev`**。若沿用 `canvas-history`，`docker compose down -v` 会直接删除生产卷。
2. **不可在现有 `canvas-history-db` 容器内建 DEV 库**。虽然技术上可行，但会与 16 个历史库共享实例与卷，违反 R2 §1.1。
3. **DEV 服务的 `DB_NAME` 必须断言为 `canvas_history_dev`**，断言失败即拒绝启动（R2 §3.4）。

### 8.3 目标目录现状

| 路径 | 状态 |
|---|---|
| `E:\01_Work\03_Release\01_Personal` | ✅ 存在（已有 family-growth-bank、myledger） |
| `E:\01_Work\04_Prod\01_Personal` | ✅ 存在（已有 family-growth-bank、myledger 等 6 个目录） |
| `…\CanvasofWorldHistory` | ❌ 不存在，P4/P5 首次创建 |

两个父目录已被其他项目使用，说明这是你的通用布局。本次只是新增一个项目子目录，**不参考、不复制其他项目的配置**。

---

## 9. 与 R2 设计稿的差异与修正建议

| # | R2 原文 | P0 实测 | 建议 |
|---|---|---|---|
| 1 | §4.2「读取 GitHub 远端 Tag」 | `gh` 未安装，API 匿名限流 | 改用 **`git ls-remote --tags origin`**，无需认证、无需 API，可直接取远端 Tag。这一条把 R1 的「无法读远端」问题解决了 |
| 2 | §8 端口表 PROD API = 5180 | 5180 当前被 vite 占用 | 单 Jar 上线前必须先停 dev vite；建议 PROD 5180 与 DEV 5181 明确分工，且在 BAT 03 启动前做端口占用检查 |
| 3 | §8 端口表未列 8088 | 8088 是当前生产 API | 单 Jar 方案下 8088 退出；过渡期需明确「8088 旧实例」与「5180 新实例」的切换窗口 |
| 4 | §3.2「DEV 账号 canvas_app_dev」 | 该角色不存在；现有 `canvas_app` 是 **superuser** | 新建 `canvas_app_dev` 时**不给 superuser**；同时建议把「生产账号降权」列为独立整改项 |
| 5 | §3.1 隐含「只有一个库」 | 实例内还有 16 个历史测试库（5.1 GB） | 不影响 R2 结论，但需在 DEPLOY.md 写明「实例内存在历史库，勿在共享实例上做破坏性操作」；历史库清理另议 |
| 6 | §6「备份校验」 | dump 的 SHA256 每次不同 | 校验标准明确为：`pg_restore --list` 成功 + 对象数 ≥ 250 + 体积在 20–80 MB 区间；不比对跨次 SHA |
| 7 | §7「单 Jar 同源部署」 | dist 从未构建，未验证 | 保持「待验证」状态正确；P2 必须先跑通 `npm run build` 与静态资源托管，再冻结 |

---

## 10. P1 启动前的硬性前置条件

按 R2 顺序，P1 开工前必须完成或明确：

| # | 条件 | 当前状态 |
|---|---|---|
| 1 | Owner 确认 R2 设计稿（含 §11 未冻结项） | 待确认 |
| 2 | 明确 DEV 是否采用**独立容器**（本报告强烈建议是） | 待确认 |
| 3 | 明确 DEV 初始数据来源：走导入流程（耗时长、需 staging 数据）还是从生产备份恢复 | 待确认（R2 §3.2 倾向导入） |
| 4 | 生产库**第一份基线备份** | ❌ 尚未建立，建议 P1 之前先做（33 MB / 2.4 秒，成本极低） |
| 5 | 确认 DEV 不触碰现有 16 个历史库 | 待确认（建议保持原样，不清理） |

**第 4 项建议优先执行**：在动任何结构之前，先给生产库留一份基线备份。这一步只写文件、不动数据库，风险为零。是否现在做，请你决定。

---

## 11. 本轮未做（边界声明）

- 未创建任何容器、卷、网络
- 未创建 `canvas_history_dev`
- 未修改 `.env`、`.env.example`、`application.yml`、`docker-compose.yml`
- 未执行任何 Migration
- 未创建 BAT
- 未 Commit / Push
- 未对 `canvas_history` 做任何写操作（唯一写操作是临时 dump 文件，已删除并二次确认无残留）
- 未清理 16 个历史测试库（需单独授权）

---

**等待 Owner 对 P0 报告的审查，以及是否立即建立生产库基线备份的指示。**
