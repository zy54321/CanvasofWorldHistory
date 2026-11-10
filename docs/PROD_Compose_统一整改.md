# PROD Compose 统一整改（2026-11-10）

## 1. 问题

整改前，PROD 的 `app` 与 `db` 虽然共用 Compose 项目名 `canvas-history`
（同一项目、同一网络、同一数据卷），却分别由两份 YAML 定义：

| 容器 | 定义文件 | 项目名 |
|---|---|---|
| `canvas-history-prod-app` | `E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory\1.0.1\deploy\docker-compose.app.prod.yml` | `canvas-history` |
| `canvas-history-db` | `E:\01_Work\01_PersonalProjects\014-CanvasofWorldHistory\code\docker-compose.yml` | `canvas-history` |

后果：

- 任何一方单独执行 `up/down` 都会把对方视为 orphan（`--remove-orphans` 甚至可能误删对方容器）；
- 无法用一条命令看到/管理完整的生产拓扑；
- 生产编排分散在「发布目录」与「源码目录」两处，发布流程与开发仓库耦合；
- 源码目录里那份文件既是「生产库定义」又是「本地开发库定义」，语义重叠。

## 2. 目标状态

```
E:\01_Work\04_Prod\01_Personal\canvas-history\compose.yaml     ← 唯一运行入口
        ▲ 部署时安装
scripts\release\templates\compose.yaml                          ← 版本化来源（仓库内）
        ▲ 打包
Release 包 deploy\compose.yaml                                  ← 发布产物内的副本
```

- 项目名固定 `canvas-history`，同一文件定义 `app` + `db`。
- 容器名、端口、卷名、网络名、环境变量与整改前逐项一致。
- 数据卷 `canvas-history-pgdata` 声明 `external: true`：Compose 不创建、不删除；
  卷缺失时 `up` 直接失败，不会静默初始化空库。
- 应用侧 `SPRING_FLYWAY_ENABLED=false` 保持；迁移只经 `deploy/flyway.sh` 显式执行。
- DEV 完全不动：`code/docker-compose.dev.yml`、项目 `canvas-history-dev`、
  容器 `canvas-history-db-dev`、卷 `canvas-history-dev-pgdata`、网络 `canvas-history-dev-net`、端口 15433。

## 3. 旧入口的处理

| 旧入口 | 处理 |
|---|---|
| `1.0.1\deploy\docker-compose.app.prod.yml` | 删除，并入 `compose.yaml` |
| `1.0.1\deploy\docker-compose.prod.yml` | 删除，并入 `compose.yaml` |
| `code\docker-compose.yml` | 降级为本地沙箱 `canvas-history-local`（容器 `canvas-history-db-local`、卷 `canvas-history-local-pgdata`、网络 `canvas-history-local-net`、端口 55432），与生产零共享 |
| `publish-container.ps1` | 只读 `compose.yaml`，仅重建 `app`（`--no-deps`） |
| `prod-status.ps1` | 增加「唯一 Compose + 容器标签对齐检查」 |

## 4. 施工顺序与安全闸门

1. **备份**：`pg_dump -Fc` 全库 → `canvas-history\backups\<ts>\canvas_history.dump`，
   用 `pg_restore -l` 验证可解析（260 个 TOC 条目）。
2. **只读校验**：`docker compose config`、服务列表、`config --hash` 与容器标签比对、
   DEV/PROD 资源边界核对。全程不执行 `up/down/rm`。
3. **审批点**：若新配置会改变 `db` 服务定义（即需要重建数据库容器），
   必须先输出影响、备份状态、最小切换步骤，取得批准后才执行。
4. **切换**：只重建必要的容器；数据库卷不迁移、不重建。
5. **回归**：健康检查、页面 200、卷 SHA/大小不变、DEV 容器与卷未变。

## 5. 判定「是否会重建数据库容器」的方法

Compose 用 `com.docker.compose.config-hash` 判断服务是否需要重建。可离线比对：

```
# 容器当前生效的配置哈希
docker inspect --format '{{index .Config.Labels "com.docker.compose.config-hash"}}' canvas-history-db

# 某份 compose 文件中 db 服务将得到的哈希
docker compose -p canvas-history --env-file <PROD>\config\.env -f <file> config --hash db
```

两者相等 ⇒ `up` 不会重建该容器。该方法已用整改前的两份文件校准过：`db` 完全复现，
说明比对结果可信。

发布脚本内置同一检查：若 Release 包内的 `compose.yaml` 会改变 `db` 服务定义，
脚本直接拒绝，除非显式加 `-AllowDbRecreate`。

## 6. 日常维护

```bat
:: 状态（只读）
::   双击 04_查看Prod状态.bat
:: 手工查看编排
docker compose -f E:\01_Work\04_Prod\01_Personal\canvas-history\compose.yaml ^
               --env-file E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory\config\.env ps
```

- 禁止 `docker compose down -v`。
- 禁止用第二份 Compose 文件对 `canvas-history` 执行 `up/down`。
- 需要改生产编排时：改 `scripts\release\templates\compose.yaml`，走发版流程安装，
  不要直接改运行副本（下次发布会覆盖，且不做漂移容忍）。
- 数据库迁移：`bash deploy/flyway.sh canvas_history info|migrate`。

## 7. 切换执行记录（2026-11-10 11:10–11:13）

经用户批准后执行，全程只动容器定义，不动数据卷。

| 步骤 | 结果 |
|---|---|
| `stop app` | 停止 `canvas-history-prod-app` |
| `up -d --force-recreate db` | db 重建，4 秒转 healthy；卷 `canvas-history-pgdata`（created 2026-11-03T04:21:02Z）未变 |
| `up -d --force-recreate app` | 首次失败：`.env` 中 `CANVAS_CONFIG_JS_PATH` 的值被反斜杠转义截断（`E://01_Work//...`），bind source 不存在 |
| 修正 .env 为正斜杠后重试 | app 6 秒 healthy，页面 200，`depends_on` 等待 db healthy 生效 |

切换后核对：

- 两个容器 `com.docker.compose.project.config_files` 均指向同一份 `compose.yaml`；
  `docker compose ls` 只显示一条 `canvas-history`。
- 两个服务 `config --hash` 与容器标签**逐位相等**（db `d9799b21…`，app `df46d900…`），
  说明后续 `docker compose up -d` 对两者都是 no-op，不会再有隐式重建。
- 数据：places 57967 / names 84554 / locations 53792 / Flyway V10 / 608 MB，与切换前一致。
- DEV：容器 ID 与启动时间、卷创建时间、端口全部未变；仅新增 0 个新卷、新网络。
- 实测中断：约 1 分钟（含一次失败重试），生产库数据零丢失。

**踩坑记录（重要）**：`.env` 的值里不要用反斜杠写 Windows 路径。
compose 的 env-file 解析会把 `\0`、`\n` 之类当转义序列，把路径截断成
`E://01_Work//.../config.js/n`，导致 bind mount 失败、应用 502。
统一改用正斜杠，发布脚本回写 `.env` 时也强制 `\` → `/`。

## 8. 已知取舍

- PROD 数据库容器不再挂载 `code\data\staging`（`/staging`）。该挂载只服务于
  阶段三一次性 CSV 导入，仓库中无任何运行时消费者；生产编排不再依赖开发仓库路径。
  若将来需要重新导入，应显式加回只读挂载，并按「重建容器」流程审批。
- 运行副本 `compose.yaml` 由发布脚本安装，内容必须与包内副本逐字一致；
  手工修改会在下次发布时被覆盖并留下 `.bak-<ts>` 备份。
