# 部署说明

本包是 **单 Jar 同源部署**：`api/canvas-history-api.jar` 同时提供前端页面与 `/api` 接口，
不需要 Nginx，不需要 Node，也不需要 Vite。

## 包内结构

```
<版本>/
├── 03_发布Prod.bat        部署入口（双击）
├── 04_查看Prod状态.bat    状态查看入口（只读，双击）
├── manifest.json          版本、Git SHA、构建时间、Flyway 版本
├── SHA256SUMS.txt         全部文件的校验和
├── api/canvas-history-api.jar
├── db/migration/V*.sql    Flyway 迁移脚本（与开发源码同一套）
├── deploy/
│   ├── compose.yaml              PROD 唯一编排（app + db，项目名 canvas-history）
│   ├── publish-prod.ps1          03 的实际逻辑
│   ├── prod-status.ps1           04 的实际逻辑（只读）
│   ├── start-api.bat / .sh       启动应用
│   └── flyway.sh                 迁移入口（显式执行）
├── config/.env.example    配置模板（真实 .env 需自行创建，不入包）
└── docs/DEPLOY.md         本文件
```

> `04_查看Prod状态.bat` 只读：显示当前部署版本、数据库 Flyway 版本、
> PROD 编排对齐情况、端口监听与健康检查结果，不启停服务、不写任何文件。

## PROD 编排：只有一份 Compose

PROD 的 `app` 与 `db` 由**同一个**文件管理，项目名固定 `canvas-history`：

```
E:\01_Work\04_Prod\01_Personal\canvas-history\compose.yaml
```

- 包内 `deploy/compose.yaml` 是版本化来源；`03_发布Prod.bat` 在部署时把它安装到
  上述正式路径，安装前会把旧文件备份为 `compose.yaml.bak-<时间戳>`。
- 除该文件外，任何 Compose 文件都不得对 `canvas-history` 项目执行 `up/down`。
- `code/docker-compose.yml` 已降级为 `canvas-history-local` 本地沙箱（端口 55432），
  与生产无任何共享资源。
- 生产数据卷 `canvas-history-pgdata` 在文件中声明为 `external: true`：
  Compose 不会创建、也不会删除它；卷不存在时 `up` 直接报错，不会静默建空库。

手工查看/启停生产编排（**必须**带 `--env-file`，凭据只在该文件中）：

```
docker compose -f E:\01_Work\04_Prod\01_Personal\canvas-history\compose.yaml ^
               --env-file E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory\config\.env ps
```

## 首次部署

1. **准备配置**
   ```
   copy config\.env.example config\.env
   ```
   填写 `POSTGRES_PASSWORD`（必填）。`POSTGRES_DB` 必须是 `canvas_history`。

2. **准备数据库**（若尚未运行）

   `03_发布Prod.bat` 会先安装统一 Compose，再校验库身份与 Flyway 版本；
   数据库容器已存在时不会被重建。只有在需要从零起库时才手工执行：
   ```
   docker compose -f E:\01_Work\04_Prod\01_Personal\canvas-history\compose.yaml ^
                  --env-file config\.env up -d db
   ```
   卷 `canvas-history-pgdata` 为 `external: true`，必须先存在；不存在时 `up` 会直接报错，
   不会新建空库（从零恢复请按备份流程人工建卷）。

3. **执行迁移**（仅在数据库版本低于本包要求时）
   ```
   bash deploy/flyway.sh canvas_history info      # 先看状态
   bash deploy/flyway.sh canvas_history migrate   # 再执行
   ```

4. **启动应用**
   ```
   deploy\start-api.bat
   ```
   默认端口 5180，页面与 API 同源：http://127.0.0.1:5180/

5. **配置地图底图（可选）**

   前端在浏览器端从 `/config.js` 读取 key，构建产物里不含任何密钥。注入方式：

   ```
   mkdir web
   echo window.__ENV__ = { MAPTILER_KEY: '你的受限 API key' }; > web\config.js
   ```

   启动脚本已把 `web\` 作为优先静态目录（`--spring.web.resources.static-locations=file:./web/,classpath:/static/`），
   放在这里的文件会覆盖 jar 内置资源，**无需重新打包**。

   不提供 `web\config.js` 时，地图自动降级为经纬网底图，界面有明确提示，其余功能不受影响。

## 校验包完整性

```
powershell -NoProfile -Command "Get-Content SHA256SUMS.txt | ForEach-Object { $h,$f = $_ -split '  ',2; $a=(Get-FileHash $f -Algorithm SHA256).Hash; if ($a -ne $h) { Write-Host \"MISMATCH $f\" } }"
```

## 禁止事项

- 不要使用 `docker compose down -v`（生产卷虽是 external 不会被删，但仍禁止；本地沙箱卷会被删）。
- 不要用第二个 Compose 文件对项目 `canvas-history` 执行 `up/down`——包括仓库里的
  `code/docker-compose.yml`（它已是 `canvas-history-local` 沙箱）。
- 不要在未确认备份可恢复的情况下重建数据库容器；发布脚本默认拒绝
  （`-AllowDbRecreate` 必须由人工显式给出）。
- 不要修改 `db/migration` 里已发布的迁移文件。
- 不要让应用启动时自动跑迁移（`SPRING_FLYWAY_ENABLED` 恒为 `false`，迁移只走 `flyway.sh`）。
- 不要把 `config/.env` 提交到 Git 或回传到开发仓库。
- 不要通过新建空数据库来"绕过"迁移问题。
