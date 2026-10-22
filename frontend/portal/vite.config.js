import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
 const env = loadEnv(mode, '.', '')

 return {
  plugins: [react(), tailwindcss()],
  resolve: { dedupe: ['react', 'react-dom'] },
  server: {
   host: '127.0.0.1',
   port: 5175,
   strictPort: true,
   proxy: {
    '/api': {
     target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
     changeOrigin: false,
    },
    '/admin': { target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false },
    '/static': { target: env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: false },
   },
  },
  test: { environment: 'jsdom', restoreMocks: true, setupFiles: ['./src/test-setup.js'] },
 }
})
