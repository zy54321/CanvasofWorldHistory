# P6-A 首次 Release 验收报告

> 项目：World History Spacetime Canvas
> 日期：2026-11-07
> 目标版本：`v1.0.0`
> 状态：**阶段一（只读核查）完成，等待 Owner 执行 BAT 01 / BAT 02**
> 本轮未执行任何 Git 写操作、未制作正式 Release、未部署 PROD

---

## 一、阶段完成情况

| 阶段 | 内容 | 状态 |
|---|---|---|
| 一 | 发布前只读核查（7 项） | **已完成** |
| 一·补 | 发布一致性缺陷修复 + 临时仓库验证 | **已完成**（1 处缺陷） |
| 二 | 正式 Git 提交与推送 | **等待 Owner 双击 `01_提交GitHub.bat`** |
| 三 | 正式制作 Release | **等待 Owner 双击 `02_制作Release.bat`** |
| 四 | Release 成品验证 | **阻塞于阶段三** |
| 五 | 生产部署前核查 | **已完成** |
| 六 | BAT 03 部署 | **未执行（按边界禁止）** |

---

## 二、第一阶段：只读核查结果

### 2.1 分支与提交关系

| 项 | 实际值 |
|---|---|
| 当前分支 | `m4-3-pleiades-gis` |
| HEAD | `9efea3ac52b6bb5ad96d5055bfe3cdeb160f0ba0` |
| `origin/main` | `9efea3ac52b6bb5ad96d5055bfe3cdeb160f0ba0` |
| **HEAD 与 origin/main** | **完全一致（同一提交）** |
| 是否落后远端 | 否（behind = 0） |
| 是否领先远端 | 否（ahead = 0） |
| 是否分叉 | 否 |
| 本地分支 | `m4-3-pleiades-gis`、`m3-time-map`、`m4-2-import-rules`、`master` |
| **本地是否存在 `main`** | **不存在**（只有 `origin/main` 远程跟踪分支） |

**关键结论**：当前分支内容与远端 `main` 完全相同，只是分支名不同，且本地从未建立 `main` 分支。

### 2.2 工作区变更

| 类型 | 数量 |
|---|---|
| 删除 | **428** |
| 修改 | **8** |
| 新增（未跟踪） | **25** |
| 合计 | 461 |

**428 项删除摘要**（此前已确认，本轮复核一致）：

| 维度 | 结果 |
|---|---|
| 目录分布 | `code/ops/reports` **425** 项 + `code/ops/__pycache__` **3** 项 |
| 类型分布 | `.png` 273、`.json` 77、`.md` 32、`.csv` 28、`.txt` 15、`.pyc` 3 |
| 是否含源码/构建/迁移文件 | **0 个** |
| 是否影响运行、构建、测试 | **否**（`ops/` 关键脚本全部存在，`data/` 完整，迁移 10 个完整） |

**8 项修改**：

```
code/.gitignore
code/README.md
code/backend/pom.xml
code/backend/run-dev.sh
code/frontend/index.html
code/frontend/src/map/basemaps.ts
code/frontend/vite.config.ts
code/start-dev.sh
```

**25 项新增**：

| 类别 | 文件 |
|---|---|
| 三个 BAT 入口 | `01_提交GitHub.bat`、`02_制作Release.bat` |
| 脚本 | `scripts/dev/git-publish.ps1`、`scripts/release/git-release.ps1` |
| 部署模板 | `scripts/release/templates/` 下 8 个（含 `03_发布Prod.bat`、`publish-prod.ps1`） |
| Maven Wrapper | `code/backend/mvnw`、`mvnw.cmd`、`.mvn/wrapper/maven-wrapper.properties` |
| DEV 环境 | `code/.env.dev`（**被忽略，不会提交**）、`code/docker-compose.dev.yml`、`code/backend/run-dev-api.sh` |
| 前端运行时配置 | `code/frontend/public/config.js` |
| 文档 | `docs/` 下 5 份、根目录 DEV 验收报告 1 份 |
| 占位 | `code/ops/reports/v1b/.gitkeep` |

### 2.3 远端同步状态

- `git fetch` 成功，无网络异常
- behind = 0，ahead = 0
- 无未推送提交
- 远端只有 `main` 一个分支

### 2.4 工具链完整性

| 项 | 状态 |
|---|---|
| `01_提交GitHub.bat` | 存在（项目根） |
| `02_制作Release.bat` | 存在（项目根） |
| `03_发布Prod.bat` | 存在（`scripts/release/templates/`，只进 Release 包，不进项目根） |
| `scripts/dev/git-publish.ps1` | 存在 |
| `scripts/release/git-release.ps1` | 存在 |
| 部署模板 | 8 个齐全（compose、启动脚本 ×2、flyway、env 模板、DEPLOY.md、publish-prod.ps1、BAT 03） |

### 2.5 敏感文件排除

| 路径 | 状态 |
|---|---|
| `code/.env` | 已忽略 |
| `code/.env.dev` | 已忽略 |
| `code/backend/target/` | 已忽略 |
| `code/frontend/dist/` | 已忽略 |
| `code/frontend/node_modules/` | 已忽略 |
| `code/data/backup/*.dump` | 已忽略 |
| **待提交列表中是否含敏感项** | **0 个** |

### 2.6 目标 Release 目录与 Tag

| 项 | 状态 |
|---|---|
| `E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory` | **不存在** |
| 本地 Git Tag | **0** |
| 远端 Git Tag | **0** |

不存在覆盖风险，首次发布路径干净。

### 2.7 发布分支核查（只提供建议，未做任何操作）

由于本地没有 `main` 分支，BAT 01 当前的行为是：**把 `m4-3-pleiades-gis` 推送到远端同名分支**（会新建 `origin/m4-3-pleiades-gis`），而不是推到 `origin/main`。

两个可选路径：

| 方案 | 做法 | 结果 | 评价 |
|---|---|---|---|
| **A（推荐）** | 先建立本地 `main` 并切过去，再双击 BAT 01 | 提交落在 `main`，`origin/main` 前进，符合 R2「main 为发布分支」 | 需要一次手动分支操作（`git checkout -b main origin/main`），属 Owner 决定 |
| B | 直接双击 BAT 01 | 提交进入 `m4-3-pleiades-gis`，远端新建同名分支；`origin/main` 不动 | 简单，但发布分支策略被绕开，后续每次 Release 都要解释分支差异 |

**未执行任何 checkout / merge / rebase / 远端改动。**

---

## 三、第一阶段补：一致性缺陷修复

### 3.1 发现的问题

BAT 02 的「先 Tag、后归档」流程中，父目录创建（`New-Item`）写在 `try` 块**之外**。若该行抛异常（路径非法、无写权限），异常会直接冒到外层捕获，**归档回退逻辑不会执行，留下一个没有包的孤儿 Tag**。

这正是任务清单第 7 项关心的「状态不一致」类问题。

### 3.2 修复

把 `New-Item` 移入 `try` 块，使 `finally` 中的回退（删目录 + `git tag -d`）能覆盖到它。

### 3.3 验证（临时仓库，不触碰真实仓库）

用「父路径是一个文件」精确触发归档失败：

```
阻塞文件：%TEMP%\canvas-p6a-test\blocker（是普通文件）
ReleaseRoot 指向它 → targetDir = blocker\1.0.0 → 父目录创建必然失败
```

实测结果：

| 步骤 | 结果 |
|---|---|
| 选版本 v1.0.0 | 通过 |
| 创建 annotated tag | `[OK] Tag 已创建：v1.0.0` |
| 归档 | `[X] 归档失败` |
| Tag 回退 | `[!] 回退刚创建的 Tag` |
| 本地 Tag 最终 | **空** |
| 远端 Tag 最终 | **空** |
| 退出码 | 1 |
| 临时构建目录 | 已清理 |

**结论：归档失败时不再留下孤儿 Tag，三种失败路径（取消 Tag / Tag 失败 / 归档失败）都不会产生「有 Tag 无包」或「有包无 Tag」。**

### 3.4 关于「远端 Tag 已推送但本地归档失败」

在当前实现下**不可能发生**：代码顺序是 `创建 Tag → 归档 → 推送`，归档失败时推送尚未执行，远端本就没有该 Tag。

| 场景 | 本地包 | 本地 Tag | 远端 Tag | 一致性 |
|---|---|---|---|---|
| 取消创建 Tag | 无 | 无 | 无 | 一致 |
| Tag 创建失败 | 无 | 无 | 无 | 一致 |
| 归档失败 | 无（已清理） | 无（已回退） | 无 | 一致 |
| Tag 成功、推送取消 | 有 | 有 | 无 | 明确提示「未推送」，exit 0 |
| Tag 成功、推送失败 | 有 | 有 | 无 | 明确提示「未推送状态」，exit 1 |
| 全部成功 | 有 | 有 | 有 | 一致 |

---

## 四、第二阶段：正式 Git 提交（等待 Owner 执行）

### 4.1 计划提交内容

| 项 | 值 |
|---|---|
| 分支（当前） | `m4-3-pleiades-gis` |
| 提交范围 | 全部 461 项变更（428 删 + 8 改 + 25 增） |
| 删除摘要 | 425 个 `code/ops/reports` 阶段产物 + 3 个 `__pycache__` |
| 敏感文件 | 无（BAT 01 会自动扫描，应零命中） |
| 预期触发 | 因删除数 428 > 50，BAT 01 会要求「额外确认删除」后再确认提交 |

### 4.2 需要 Owner 决定的事项

**发布分支**（见 §2.7）。若选方案 A，需在执行 BAT 01 前先切换分支；若选方案 B，直接执行即可。

### 4.3 执行后需核验（由我完成）

- Commit SHA
- 实际推送分支名
- 远端对应 SHA 与本地是否一致
- 工作区是否干净
- 是否有遗漏或异常文件

---

## 五、第三阶段：正式 Release（等待 Owner 执行）

### 5.1 预期产物

| 项 | 预期值 |
|---|---|
| 版本 | `v1.0.0` |
| Release 目录 | `E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory\1.0.0` |
| Git Tag | `v1.0.0`（annotated） |
| 包内文件数 | 约 21 个（20 个受校验 + SHA256SUMS） |
| 包体积 | 约 23 MB |
| 部署形态 | 单 Jar 同源 |

### 5.2 执行后需验证（由我完成）

1. Release 目录存在且版本号正确
2. Git Tag 与 Manifest `gitTag` 一致
3. Manifest `gitCommit` 与实际提交 SHA 一致
4. `sha256sum -c` 全部 OK
5. jar 内含 `BOOT-INF/classes/static/index.html`
6. 包根存在 `03_发布Prod.bat`
7. `deploy/publish-prod.ps1` 及依赖齐全
8. 无真实密钥、无数据库 dump
9. 包内无指向 DEV 源码的运行时路径

---

## 六、第五阶段：生产部署前核查（只读）

| 项 | 结果 |
|---|---|
| PROD 容器 `canvas-history-db` | **healthy**，`127.0.0.1:15432` |
| DEV 容器 `canvas-history-db-dev` | healthy，`127.0.0.1:15433`（两者互不影响） |
| 正式数据库 | `canvas_history` |
| Flyway 版本 | **V10** |
| 数据量 | `historical_place = 57,967` |
| 目标端口 5180 | **空闲** |
| 旧端口 8088 | **空闲**（当前无运行中的旧 API） |
| 旧 jar | 存在：`code\backend\target\canvas-history-api.jar`，22.9 MB，2026-11-07 10:30 |
| 是否有运行中的旧应用 | **无**（8088/5180 均无监听进程） |

### 6.1 关于「旧应用可恢复文件」

当前**没有正在运行的旧应用**，因此首次部署不存在「回滚到旧应用」的问题。`target/` 里的 jar 是构建产物，不是部署实例。

若首次部署失败，生产会处于「无服务」状态（与部署前一致），人工处置即可。

### 6.2 `MAPTILER_API_KEY` 应如何提供

首次运行 BAT 03 时，`PROD/config/.env` 不存在，工具会**从现有容器读取数据库凭据自动生成**该文件，其中 `MAPTILER_API_KEY=` 留空。

两种补法：

| 方式 | 做法 | 效果 |
|---|---|---|
| 推荐 | 首次部署前手工编辑 `PROD\config\.env`，填入 `MAPTILER_API_KEY=你的受限 key` | 部署时自动写入 `web/config.js`，页面直接有底图 |
| 备选 | 部署后把 `web\config.js` 放到 `PROD\<版本>\web\` 并重启实例 | 免重打包，但需重启 |

不填则地图降级为经纬网底图，界面有明确提示，其余功能正常。

### 6.3 关于「Start-Process 启动的 Java 在 BAT 结束后是否存活」（未验证）

P5 报告中已注明：测试工具沙箱会在命令结束时清理进程树，因此该点未能端到端验证。

本轮尝试补做时，临时目录已被清理、Docker 也曾中途停止，**未获得可靠的独立验证结论**。判断依据只能是 Windows 的标准行为：`Start-Process` 创建的是独立进程，父进程退出不影响。

**建议**：首次正式部署后，立即用另一次独立操作（例如重新打开命令行或浏览器）确认 `http://127.0.0.1:5180/` 可访问，再关闭 BAT 窗口。若发现服务随窗口退出，改用任务计划或 winsw 托管（属后续项）。

---

## 七、SHA / Tag / Release 对应关系

| 项 | 值 |
|---|---|
| 提交 SHA | **待 Owner 执行 BAT 01 后填写** |
| 推送分支 | **待定**（见 §2.7 方案 A / B） |
| 远端 SHA | **待 Owner 执行后核对** |
| Release 版本 | `1.0.0`（计划） |
| Git Tag | `v1.0.0`（计划） |
| Release 目录 | `E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory\1.0.0`（计划） |
| 数据库版本 | V10（不变，无新迁移） |

---

## 八、未完成 / 阻塞项

| # | 项 | 原因 |
|---|---|---|
| 1 | Git 提交与推送 | 按规则由 Owner 双击 BAT 01 执行 |
| 2 | 正式 Release 制作 | 依赖 #1 |
| 3 | Release 成品 9 项验证 | 依赖 #2 |
| 4 | BAT 03 部署 | **按边界禁止**，需 P7 单独授权 |
| 5 | Java 进程独立性端到端验证 | 测试环境限制，见 §6.3 |

---

## 九、阶段性结论

只读核查与一致性修复已完成，未发现阻塞首次发布的确定性缺陷（唯一发现的一处已在临时仓库验证修复）。

发布前状态：
- 仓库无未推送提交、无分叉
- 工作区变更构成清晰，428 项删除均为历史产物
- 无敏感文件进入提交范围
- 无既有 Release 目录或 Tag，不存在覆盖风险
- 生产数据库健康且未被触碰

**下一步等待 Owner：先确定发布分支方案，再双击 `01_提交GitHub.bat`。**

BAT 03 不会在本次授权范围内执行。
