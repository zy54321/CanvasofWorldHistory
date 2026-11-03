# 阶段四 M0 + M1 的浏览器端到端验收脚本

`accept-m0m1.cjs` 会用本机 Chrome（headless + swiftshader，保证 WebGL 可用）打开
`http://127.0.0.1:5180/`，逐项验证 M0-01 ~ M0-05、M1-01 ~ M1-04，并输出截图与
`e2e_result.json`。全部 PASS 时进程退出码 0，否则 1。

## 前置

1. 数据库容器在跑，且已完成正式导入：
   `docker exec canvas-history-db psql -U canvas_app -d canvas_history -tAc "select count(*) from historical_place"` → 19039
2. 后端已启动：`bash ../backend/run-dev.sh`（8088）
3. 前端已启动：`cd ../frontend && npx vite --host 127.0.0.1`（5180）
4. 安装 puppeteer-core（不进仓库依赖，仅本机验收用）：
   ```bash
   npm i puppeteer-core@23.11.1
   ```

## 运行

```bash
node accept-m0m1.cjs ../ops/reports/m0_m1_shots
```

第二个参数是截图与 `e2e_result.json` 的输出目录。

## 覆盖的判据

| 编号 | 检查方式 |
|---|---|
| M0-01 | 读 MapLibre 实例：`loaded()`、style 图层数、初始 center/zoom |
| M0-02 | 依次点四个样式按钮，比对背景色互异 + 每次切换后 `places` source 要素数 |
| M0-03 | 切换前后读相机（center/zoom），要求漂移为 0 |
| M0-04 | 依次点四个区域按钮，读各区域相机落位与视野内点数 |
| M0-05 | 检查页面 HTML 是否出现 `key=`；确认无 key 时界面有明确提示 |
| M1-01 | 关键词搜索、别名搜索、年代筛选、分页、同名不同 id |
| M1-02 | 详情标题 + 4 个概览字段 + 四个页签内容 |
| M1-03 | 直接 fetch `/api/v1/places/map`，校验 FeatureCollection / Point / meta；并验证 limit 钳制 |
| M1-04 | 点搜索结果后相机是否移动、`selected-place` 高亮要素是否为 1 |
| CLEAN | 收集 `pageerror` / console error / requestfailed |

## 说明

- 当前 `.env` 的 `VITE_MAPTILER_API_KEY` 为空，所以 M0-02 验证的是**离线降级底色**的切换，
  不是 MapTiler 真实瓦片；这一点在报告里如实标注，未写成"底图加载成功"。
- `key-pipeline.cjs` 用于验证「有 key 时请求确实打到 api.maptiler.com」这条管线：
  用假 key 启动第二个前端实例（5181）后运行，可看到 403 被如实显示在界面上。
