import { defineConfig } from 'vite';

export default defineConfig({
  base: '/guardian-results/',
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: process.env.GUARDIAN_API_TARGET || 'http://127.0.0.1:8000', changeOrigin: false } },
  },
  test: { environment: 'jsdom', restoreMocks: true },
});
