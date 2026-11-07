// 运行时配置占位文件。
//
// 构建产物通过 <script src="./config.js"> 读取 window.__ENV__，
// 这样正式 Release 包里不需要、也不允许包含任何真实密钥。
//
// 仓库内始终保持为空（只有空对象），部署时由发布流程覆盖此文件：
//   window.__ENV__ = { MAPTILER_KEY: '你的受限 API key' };
//
// 不提供该文件或字段为空时，地图自动降级为无底图模式，界面会明确提示。
window.__ENV__ = window.__ENV__ || {};
