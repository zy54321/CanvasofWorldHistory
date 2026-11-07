# World History Spacetime Canvas
# DEV → RELEASE → PROD 三 BAT 发布体系设计方案

> 版本：R2
> 日期：2026-11-06
> 状态：设计修订稿，待 Owner 最终验收
> R1：由本版本取代
> 本阶段：仅设计，不创建数据库、不修改配置、不创建 BAT、不执行 Migration。

---

## 一、Owner 已确认的基础决策

| 项目 | 正式决策 |
|---|---|
| 部署机器 | 当前 Windows 电脑 |
| DEV 位置 | 现有个人项目目录 |
| RELEASE 位置 | `E:\01_Work\03_Release\01_Personal` |
| PROD 位置 | `E:\01_Work\04_Prod\01_Personal` |
| PROD 数据库 | 现有 `canvas_history` |
| DEV 数据库 | 新建独立数据库 |
| 生产数据 | 必须保留，不重新导入、不覆盖 |
| 用户交互 | 所有执行决策使用 Y/N |
| 版本识别 | 主动读取上一个版本并显示给用户 |
| Release 归档 | 按项目名、版本号建立独立目录 |
| Prod 部署 | 按项目名、版本号建立独立目录 |

### 1.1 三个环境的绝对边界

DEV、RELEASE、PROD 是三种不同职责的环境。

- DEV：开发、修改、测试。
- RELEASE：经过构建和验收的不可变交付物。
- PROD：正式运行环境和正式业务数据。

任何环境都不得擅自改变其他环境的状态。

---

## 二、目录结构（正式冻结候选）

### 2.1 DEV

项目根目录：

`E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory`

```text
014-CanvasofWorldHistory/
├── .git/
├── 01_提交GitHub.bat
├── 02_制作Release.bat
├── code/
│   ├── backend/
│   ├── frontend/
│   ├── data/
│   ├── tests/
│   └── ops/
├── docs/
│   ├── RELEASE_PIPELINE_DESIGN.md
│   ├── DEPLOY.md
│   └── RESTORE.md
└── 设计资料/
```

BAT 01、BAT 02 均放在项目根目录。

不在项目内建立 Release 或 Prod 运行目录。

### 2.2 RELEASE

根目录：

`E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory`

```text
CanvasofWorldHistory/
├── 1.0.0/
│   ├── 03_发布Prod.bat
│   ├── manifest.json
│   ├── SHA256SUMS.txt
│   ├── api/
│   ├── db/
│   │   └── migration/
│   ├── deploy/
│   ├── config/
│   │   └── .env.example
│   └── docs/
├── 1.0.1/
└── ...
```

每个版本是独立、完整的正式发布包。

要求：

1. 不依赖 DEV 源码目录。
2. 不依赖 DEV 的 node_modules、Maven 缓存。
3. 不包含真实数据库凭证。
4. 不包含原始数据暂存包。
5. 不包含运行日志。
6. 不允许覆盖已经存在的版本。
7. 必须包含自己的部署入口 BAT 03。

### 2.3 PROD

根目录：

`E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory`

```text
CanvasofWorldHistory/
├── current.json
├── config/
│   └── .env
├── backups/
├── logs/
├── deployments/
├── legacy-unversioned/
├── 1.0.0/
│   ├── api/
│   ├── manifest.json
│   └── SHA256SUMS.txt
├── 1.0.1/
└── ...
```

其中：

- `current.json`：唯一的当前生产部署状态记录。
- `config/`：生产专用配置及凭证。
- `backups/`：数据库备份。
- `logs/`：生产运行日志。
- `deployments/`：每次部署的审计记录。
- `legacy-unversioned/`：第一次正式发布前，现有未版本化运行环境的保护副本。
- `1.0.0/` 等：正式部署版本。

生产配置与版本产物分离。

版本升级不删除旧版本，不覆盖旧版本。

---

## 三、数据库架构与隔离

### 3.1 PROD：现有数据库

正式数据库：

`canvas_history`

根据此前盘点，原有基础设施为：

| 项目 | 已记录基线 |
|---|---|
| 数据库 | canvas_history |
| PostgreSQL | 17 + PostGIS 3.6 |
| 容器 | canvas-history-db |
| 数据卷 | canvas-history-pgdata |
| 主机端口 | 15432 |
| Flyway | V10 |
| 历史地点 | 57,967 |
| 名称 | 84,554 |
| 位置 | 53,792 |
| 源记录 | 157,220 |
| 候选匹配 | 66,311 |
| 质量台账 | 20,824 |
| 事件/人物/政权 | 0 / 0 / 0 |

以上是 R1 盘点基线，正式施工前重新核验。

绝对要求：

1. 保留现有数据库。
2. 保留现有 Docker 数据卷。
3. 不重新创建正式数据库。
4. 不重新导入 Pleiades。
5. 不执行 DROP、TRUNCATE、Flyway clean。
6. 不以空数据库替换现有数据库。
7. 不允许 DEV 连接正式数据库。

### 3.2 DEV：独立新数据库

建议数据库名：

`canvas_history_dev`

建议独立基础设施：

| 项目 | DEV |
|---|---|
| 数据库 | canvas_history_dev |
| 容器 | canvas-history-db-dev |
| 数据卷 | canvas-history-dev-pgdata |
| 主机端口 | 15433 |
| 数据库账号 | canvas_app_dev |
| 网络 | canvas-history-dev-net |

DEV 使用独立 PostgreSQL 容器、独立数据卷、独立账号和连接配置。

采用与 PROD 相同的 PostgreSQL/PostGIS 镜像版本。

**初始数据建立方式：**

- 使用现有 V1–V10 Migration 创建数据库结构。
- 使用项目已有、经过验收的正式数据暂存与导入流程建立开发数据。
- 测试数据独立创建。
- 不直接修改或覆盖 PROD 数据。
- 不默认将 PROD 数据库备份恢复为 DEV 数据库。

如果以后需要复制生产数据，必须单独授权。

### 3.3 数据库版本统一规则

本项目只有一套正式数据库模型和一条 Flyway Migration 链。

唯一源码位置：

`backend/src/main/resources/db/migration/`

执行规则：

1. Migration 只能从这一目录产生。
2. DEV 和 PROD 使用相同的 Migration 文件。
3. 不允许存在 DEV 专属 Migration 链。
4. 不允许存在 PROD 专属 Migration 链。
5. 已发布 Migration 永远不可修改。
6. Migration 版本号单调递增。
7. 禁止 outOfOrder。
8. 禁止 baselineOnMigrate。
9. 禁止手工修改数据库结构而不生成 Migration。
10. 正式发布前必须在 DEV 验证 Migration。

DEV 可以先于 PROD 应用尚未发布的新 Migration，但这只是同一条迁移链的进度差异，不是两套数据库设计。

正式发布后，PROD 必须达到该 Release 对应的数据库版本。

**任何时候都不允许通过重新导入数据、重新初始化数据库来解决结构升级问题。**

### 3.4 配置隔离

这是本次需要重点整改的地方。

此前盘点发现项目 `.env` 默认连接 `canvas_history`。

必须解决：

- 项目根下的 `.env` 仅允许 DEV 使用。
- DEV `.env` 必须连接 `canvas_history_dev`。
- PROD `.env` 只能放在 PROD 根目录的 `config/`。
- PROD 凭证不能进入 Git、Release 包或 DEV 配置。
- DEV 启动脚本必须检查数据库名，不是 `canvas_history_dev` 就拒绝启动。
- PROD 启动脚本必须检查数据库名，不是 `canvas_history` 就拒绝启动。

不能只依靠用户记住自己应该连接哪个数据库，必须由程序强制校验。

---

## 四、版本管理规则

### 4.1 三层版本对应

| 层级 | 版本格式 | 权威 |
|---|---|---|
| Git Tag | v1.0.0 | Git |
| RELEASE 目录 | 1.0.0 | 本地 Release 归档 |
| PROD 目录 | 1.0.0 | 实际部署版本 |

Manifest 中使用不带 v 的版本号。

Git Tag 使用 v 前缀。

三者必须可以相互验证。

GitHub Release 页面不是本地交付物的替代品，也不是生产部署状态的权威。

### 4.2 BAT 02 版本识别

启动时主动读取：

1. GitHub 远端 Tag。
2. 本地已存在的 Release 版本目录。
3. PROD `current.json` 当前部署版本。

展示：

```text
最近一次正式 Release：v1.0.0
本地 Release：1.0.0
当前 Prod：1.0.0

建议下一版本：v1.0.1
```

若 Release Tag 与本地 Release 目录不一致，停止，不猜测、不自动修复。

Prod 落后于最新 Release 是正常情况，不视为版本冲突。

### 4.3 Y/N 版本选择

默认 PATCH + 1。

用户选择 N 后，依次询问 MINOR + 1、MAJOR + 1。

全部选择 N，则退出。

不要求输入版本字符串。

首次发布时：

- 无 Tag。
- 无 Release 目录。
- PROD 尚未登记正式版本。

建议首次版本为 `v1.0.0`，通过 Y/N 确认。

### 4.4 首次 PROD 版本登记

不能把现有未版本化系统直接冒充为 v1.0.0。

首次部署前，先识别当前运行环境：

- 当前 Jar 的真实路径和 SHA256。
- 当前前端运行方式及资源。
- 当前 API 进程。
- 当前数据库身份及 Flyway 版本。
- 当前运行配置。
- 当前服务端口。

将现有环境保存到 `legacy-unversioned/`，并记录其真实身份。

`current.json` 中允许：

```json
{
  "status": "legacy_unversioned",
  "releaseVersion": null,
  "database": {
    "name": "canvas_history",
    "flywayVersion": 10
  }
}
```

只有在现有运行环境可识别、可保护、具备恢复条件后，才允许进行第一次正式部署。

不能伪造历史版本号。

---

## 五、三个 BAT 的职责

### BAT 01：01_提交GitHub.bat

位置：项目根目录。

职责：

- 检查 Git 工作区。
- 显示新增、修改、删除数量。
- 大批量删除单独警告。
- 敏感文件扫描。
- 检查当前分支及远端同步状态。
- 构建基础检查。
- 提交。
- 推送 GitHub。
- 验证推送结果。

建议统一使用 `main` 作为正式发布分支。

非 main 分支不能直接作为 Release 来源。

如果当前分支与 main 完全一致且工作区干净，可以安全切换；如果存在分叉或独有提交，停止并要求处理。

Commit 和 Push 分别确认。

Commit Message 自动生成，不要求用户输入长文本。

禁止：

- Force Push。
- 自动重置工作区。
- 自动覆盖远端提交。
- 未经确认提交敏感文件。

### BAT 02：02_制作Release.bat

位置：项目根目录。

职责：

1. 检查工作区干净。
2. 检查 main 与 GitHub 同步。
3. 读取最近版本。
4. 展示上一个 Release 和当前 Prod 版本。
5. Y/N 选择新版本。
6. 检查工具链。
7. 构建后端。
8. 构建前端。
9. 执行强制测试。
10. 生成临时 Release。
11. 生成 Manifest。
12. 生成 SHA256。
13. 完整性校验。
14. 创建并推送正式 Git Tag。
15. 将验证通过的包正式放入 E 盘 Release 目录。

正式目标：

`E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory\<版本号>`

正式 Release 必须具备 Git Tag、完整构建产物和完整性清单。

取消 Tag 或推送失败，不得把临时构建标记为正式 Release。

已有版本目录不允许覆盖。

### BAT 03：03_发布Prod.bat

位置：每个 Release 包的根目录。

例如：

`E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory\1.0.0\03_发布Prod.bat`

职责：

1. 识别当前 PROD 版本。
2. 识别目标 Release 版本。
3. 验证 Release 包完整性。
4. 验证当前运行环境。
5. 验证数据库身份。
6. 显示版本差异和 Migration 增量。
7. Y/N 确认升级。
8. 数据库备份。
9. 备份校验。
10. Y/N 确认继续。
11. 执行 Migration。
12. 部署应用。
13. 健康检查。
14. 冒烟测试。
15. 更新 `current.json`。
16. 生成部署日志。

正式目标：

`E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory\<版本号>`

BAT 03 不依赖 DEV 源码，不重新编译，不重新导入原始数据。

---

## 六、数据库备份和恢复

备份必须在 Migration 之前执行。

采用：

`pg_dump -Fc`

保存至：

`PROD_ROOT\backups\`

必须验证：

- pg_dump 成功。
- 备份文件存在。
- SHA256 生成并复核。
- pg_restore --list 成功。
- 定期在独立演练数据库完成真实恢复验证。

取消原设计中「新备份必须大于前次备份 50%」的规则，该规则不具备可靠的数据库完整性判断能力。

不自动删除历史备份。

数据库恢复必须经过人工决策，不允许 BAT 自动 DROP 正式数据库或执行破坏性恢复。

### 回滚边界

应用回滚：自动执行，恢复旧版本应用。

数据库回滚：不自动执行，必须有备份和人工恢复方案。

迁移失败：停止新应用启动，保留现场，输出具体错误和恢复指引。

迁移成功但应用启动失败：优先恢复旧应用，前提是 Migration 满足向后兼容要求。

---

## 七、部署形态

首选候选方案仍为单 Jar 同源部署：

- 前端 dist 打入 Jar。
- Spring Boot 同时提供前端页面与 API。
- 不依赖 Vite 开发服务器。
- 不需要额外 Nginx。
- 生产环境只需要现有数据库容器和应用进程。

但必须先完成真实构建和浏览器验证，未验证前不视为最终冻结。

MapTiler Key 采用运行时配置注入，不在构建阶段硬编码进 Release。

生产配置位于：

`PROD_ROOT\config\.env`

浏览器可见的 Key 仍应设置域名限制。

---

## 八、运行端口建议

初步建议，最终以 P0 现场检查为准：

| 服务 | PROD | DEV |
|---|---:|---:|
| PostgreSQL | 15432 | 15433 |
| API | 5180（单 Jar 方案） | 8089 |
| 前端 | 与 API 同源 | 5181 |

端口必须独立。

启动前检查占用情况，禁止静默更换端口。

若单 Jar 验证失败，再冻结前后端分离方案。

---

## 九、施工阶段

| 阶段 | 任务 | 生产库是否写入 |
|---|---|---|
| P0 | 只读盘点当前运行环境、容器、数据卷、端口、配置 | 否 |
| P1 | 建立 DEV 独立数据库及配置隔离 | 否 |
| P2 | 补齐构建、版本识别、运行时配置注入 | 否 |
| P3 | 实现 BAT 01 | 否 |
| P4 | 实现 BAT 02 | 否 |
| P5 | 实现 BAT 03、备份与恢复演练 | 正式演练前不写 |
| P6 | DEV → RELEASE → PROD 全链路隔离演练 | 否 |
| P7 | 首次正式部署 | 经单独授权后执行 |

每个阶段单独验收，不能跳过。

P7 必须单独获得 Owner 授权。

---

## 十、P0 必须重点查明的风险

此前项目 `.env` 默认指向正式数据库，这是本轮最高优先级的安全问题。

P0 必须只读确认：

1. 现有 `canvas_history` 容器和 Volume 的真实对应关系。
2. 现有数据库是否仍为 V10。
3. 当前 API 和前端进程的真实启动命令。
4. 当前运行的 Jar 路径和 SHA256。
5. 当前 Vite 实例的用途。
6. `.env` 被哪些脚本和服务读取。
7. 正式数据库连接配置实际来自哪里。
8. DEV 启动是否存在误连正式库的路径。
9. 现有数据库备份是否可用。
10. DEV 新数据库的创建是否会触碰现有 Docker Volume。

P0 只读，不启动新容器、不创建数据库、不改配置。

---

## 十一、尚待最终冻结的工程选择

以下不是 Owner 已确认的事实，而是待验证或待最终确认的设计建议：

1. 首次正式 Release：建议 v1.0.0。
2. 部署形态：优先单 Jar，必须先通过实际验证。
3. MapTiler Key：运行时注入。
4. E2E：修复依赖后作为正式 Release 硬闸门。
5. Git Tag：正式 Release 必须推送远端。
6. 发布分支：main。
7. DEV 数据：优先使用经过验收的源数据导入流程，不直接复制 PROD。

这些项目不得在施工时被默认为已经获得 Owner 批准。

---

## 十二、最终验收标准

整个体系完成后，必须能够做到：

- 用户只需要双击 BAT 01、02、03。
- 所有决策均通过 Y/N 完成。
- 用户不需要手动输入复杂命令。
- 自动读取上一次 Release 版本。
- 自动读取当前 Prod 版本。
- Release 和 Prod 分别保存历史版本。
- 不覆盖历史 Release。
- DEV 和 PROD 数据库完全隔离。
- 数据库使用唯一、连续的 Migration 链。
- 不重新导入生产数据。
- 发布前自动备份。
- 部署失败能够恢复旧应用。
- 每次部署都有版本、SHA256、数据库版本和日志记录。
- 可以从任意一个正式 Release 识别对应代码和数据库结构。
- DEV 的任何测试、清理、重置都不能影响 PROD。

**最终目标：建立一套可靠、可重复、可审计、可恢复的个人工程项目发布体系，而不是仅仅制作三个能够运行的 BAT 文件。**
