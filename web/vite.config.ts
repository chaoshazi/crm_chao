import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// 开发时把 /api 与 /health 代理到本机 CRM API（9100），前端不需要处理跨域；
// 生产构建产物由 FastAPI 直接托管（CRM_SERVE_WEB=true）。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      '/api': { target: 'http://127.0.0.1:9100', changeOrigin: true },
      '/health': { target: 'http://127.0.0.1:9100', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
});