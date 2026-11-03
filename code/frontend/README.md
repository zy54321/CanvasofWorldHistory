# frontend —— Vue 3 + TypeScript + MapLibre GL JS

阶段四 M0（地图技术验证）+ M1（历史地理数据只读查询）已在此建立最小可运行工程。

## 启动

```bash
cd frontend
npm install          # 首次
npx vite --host 127.0.0.1
# → http://127.0.0.1:5180/
```

或用仓库根 `../start-dev.sh` 同时拉起后端与前端。

前端开发服务器通过 Vite proxy 把 `/api` 转发到 `http://127.0.0.1:8088`（读 `.env` 的 `API_HOST_PORT`），
浏览器只与前端同源通信，后端不需要开 CORS。

## 目录

```text
src/
  api.ts                 # /api/v1 封装（搜索、详情、bbox、统计）
  types.ts               # 与后端 DTO 一一对应的类型
  map/basemaps.ts        # 四种样式定义、样式 URL、区域预设、离线降级底图
  components/
    MapView.vue          # MapLibre 实例、样式切换、视野查询、点选
    SearchPanel.vue      # 关键词 / 年代 / 分页
    DetailPanel.vue      # 名称、位置、来源、质量提示四个页签
  App.vue                # 布局与三面板联动
```

## 地图凭证

- 只读 `code/.env` 的 `VITE_MAPTILER_API_KEY`，由 `vite.config.ts` 在构建期注入，
  源码里没有硬编码；该变量是 **API key**（需在 MapTiler 控制台限制 Allowed HTTP origins），
  **Service Token 绝不进前端**。
- 当前已配置有效 key，四种样式（Outdoor / Streets / Satellite / Hybrid）加载真实瓦片。
- **改 `.env` 后必须重启 vite**（key 在启动时注入，HMR 不会重读）。
- 无 key 时**不会伪装成功**：界面显示「底图未接入 MapTiler」，地图降级为纯色 + 经纬网，
  四种样式仅切换离线预览底色；地点图层、搜索、空间查询、详情仍全部可用（数据来自真实数据库）。
- 该 key 是浏览器端 **API key**，请在 MapTiler 控制台限制 Allowed HTTP origins；
  不要使用 Service Token。
