import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API runs on :8000. The dev server proxies /api to it, so the app never
// hard-codes a backend URL. Set VITE_API_BASE for a deployed backend instead.
// 127.0.0.1, not localhost: uvicorn listens on IPv4 only, and localhost can resolve to ::1.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.API_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
