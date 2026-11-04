import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const here = fileURLToPath(new URL('.', import.meta.url))

/**
 * 从仓库根目录的 .env 读取 VITE_MAPTILER_API_KEY。
 * 打包/运行时只把该变量注入浏览器；Service Token 绝不进入前端。
 * 密钥缺失时不报错，地图降级为无底图模式（由界面明确提示）。
 */
function loadRootEnv(): Record<string, string> {
  const out: Record<string, string> = {}
  try {
    const raw = readFileSync(here + '../.env', 'utf8')
    for (const line of raw.split(/\r?\n/)) {
      const m = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim())
      if (m) out[m[1]] = m[2].trim()
    }
  } catch {
    /* 没有 .env 时静默降级 */
  }
  // 允许用环境变量临时覆盖（例如把前端指向测试库做写入联调）
  for (const k of ['VITE_MAPTILER_API_KEY', 'VITE_API_BASE', 'API_HOST_PORT', 'WEB_HOST_PORT']) {
    if (process.env[k]) out[k] = process.env[k] as string
  }
  return out
}

const env = loadRootEnv()
const webPort = Number(env.WEB_HOST_PORT || process.env.WEB_HOST_PORT || 5180)

export default defineConfig({
  plugins: [vue()],
  define: {
    __MAPTILER_KEY__: JSON.stringify(env.VITE_MAPTILER_API_KEY || ''),
  },
  server: {
    // 只绑回环地址：本机工具，不对外暴露
    host: '127.0.0.1',
    port: webPort,
    // 端口被占用时直接报错，避免「以为在 5180、其实悄悄跑到 5182」
    strictPort: true,
    proxy: {
      // 浏览器只与前端同源通信，避免后端开 CORS
      '/api': {
        target: `http://127.0.0.1:${env.API_HOST_PORT || 8088}`,
        changeOrigin: true,
      },
    },
  },
  build: { outDir: 'dist', sourcemap: false },
})