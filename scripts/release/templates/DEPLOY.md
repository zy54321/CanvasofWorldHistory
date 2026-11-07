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
│   ├── docker-compose.prod.yml   仅数据库服务，复用既有生产卷
│   ├── publish-prod.ps1          03 的实际逻辑
│   ├── prod-status.ps1           04 的实际逻辑（只读）
│   ├── start-api.bat / .sh       启动应用
│   └── flyway.sh                 迁移入口
├── config/.env.example    配置模板（真实 .env 需自行创建，不入包）
└── docs/DEPLOY.md         本文件
```

> `04_查看Prod状态.bat` 只读：显示当前部署版本、数据库 Flyway 版本、
> 端口监听与健康检查结果，不启停服务、不写任何文件。

## 首次部署

1. **准备配置**
   ```
   copy config\.env.example config\.env
   ```
   填写 `POSTGRES_PASSWORD`（必填）。`POSTGRES_DB` 必须是 `canvas_history`。

2. **启动数据库**（若尚未运行）
   ```
   docker compose -f deploy\docker-compose.prod.yml --env-file config\.env up -d
   ```
   使用了固定卷名 `canvas-history-pgdata`，会挂载既有数据，不会新建空库。

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

- 不要使用 `docker compose down -v`（会删除生产数据卷）。
- 不要修改 `db/migration` 里已发布的迁移文件。
- 不要把 `config/.env` 提交到 Git 或回传到开发仓库。
- 不要通过新建空数据库来"绕过"迁移问题。
