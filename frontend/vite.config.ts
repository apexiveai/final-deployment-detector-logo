import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv, type ProxyOptions } from 'vite'

export default defineConfig(({ mode }) => {
  const frontendEnv = loadEnv(mode, process.cwd(), '')
  const backendEnv = loadEnv(
    mode,
    fileURLToPath(new URL('../backend/', import.meta.url)),
    '',
  )
  let backendUrl: URL

  try {
    backendUrl = new URL(
      frontendEnv.VITE_API_URL || 'http://127.0.0.1:8081',
    )
  } catch {
    throw new Error('VITE_API_URL must be a single valid backend URL.')
  }

  if (!['http:', 'https:'].includes(backendUrl.protocol)) {
    throw new Error('VITE_API_URL must use HTTP or HTTPS.')
  }

  const apiProxy: ProxyOptions = {
    target: backendUrl.origin,
    changeOrigin: true,
    configure(proxy) {
      proxy.on('proxyReq', (proxyRequest) => {
        if (backendEnv.API_KEY) {
          proxyRequest.setHeader('X-API-Key', backendEnv.API_KEY)
        }
      })
    },
  }

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api': apiProxy,
      },
    },
    preview: {
      proxy: {
        '/api': apiProxy,
      },
    },
  }
})
