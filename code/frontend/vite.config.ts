import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const here = fileURLToPath(new URL('.', import.meta.url))

/**
 * 读取环境文件。只把 VITE_MAPTILER_API_KEY 注入浏览器；Service Token 绝不进入前端。
 * 密钥缺失时不报错，地图降级为无底图模式（由界面明确提示）。
 *
 * DEV 与 PROD 的来源必须**显式**分开，绝不靠"文件是否存在"猜测：
 *   - 默认（含 `vite` / `vite build` / `vite preview`）一律读 `.env`；
 *   - 只有显式设置 `VITE_ENV_FILE` 时才改读别的文件，且构建模式下忽略该变量，
 *     防止本地开发配置被误打进正式产物。
 *
 * 这样「在同一台机器上同时跑生产预览 5180→8088 和 DEV 5181→8089」是安全的：
 * 谁也不会因为另一份 .env 文件存在而悄悄改掉自己的连接目标。
 */
function loadEnvFile(path: string): Record<string, string> {
  const out: Record<string, string> = {}
  try {
    const raw = readFileSync(path, 'utf8')
    for (const line of raw.split(/\r?\n/)) {
      const m = /^([A-Z0-9_]+)=(.*)$/.exec(line.trim())
      if (m) out[m[1]] = m[2].trim()
    }
  } catch {
    /* 文件不存在时静默降级 */
  }
  return out
}

export default defineConfig(({ mode }) => {
  const isBuild = mode === 'production'
  const requestedEnvFile = process.env.VITE_ENV_FILE
  // 构建模式忽略 VITE_ENV_FILE；开发时也要显式指定才切换环境文件
  const envPath =
    !isBuild && requestedEnvFile
      ? resolve(here, requestedEnvFile)
      : resolve(here, '../.env')

  const env = loadEnvFile(envPath)

  // 允许用环境变量临时覆盖（例如把前端指向测试库做写入联调）
  for (const k of ['VITE_MAPTILER_API_KEY', 'VITE_API_BASE', 'API_HOST_PORT', 'WEB_HOST_PORT']) {
    if (process.env[k]) env[k] = process.env[k] as string
  }

  // 正式发布包构建时必须剥离密钥：产物里不留任何真实 key，
  // 改由部署时的 config.js 在运行时注入（见 public/config.js 与 basemaps.ts）。
  if (process.env.CANVAS_STRIP_MAPTILER_KEY === '1') {
    env.VITE_MAPTILER_API_KEY = ''
  }

  const webPort = Number(env.WEB_HOST_PORT || process.env.WEB_HOST_PORT || 5180)
  const apiPort = Number(env.API_HOST_PORT || process.env.API_HOST_PORT || 8088)

  if (!isBuild) {
    console.log(`[vite] 环境文件：${envPath}`)
    console.log(`[vite] 前端 http://127.0.0.1:${webPort}  →  API http://127.0.0.1:${apiPort}`)
  }

  return {
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
          target: `http://127.0.0.1:${apiPort}`,
          changeOrigin: true,
        },
      },
    },
    build: { outDir: 'dist', sourcemap: false },
  }
})
