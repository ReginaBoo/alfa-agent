import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

export default defineConfig({
  plugins: [react()],
  root: resolve(__dirname, 'src/renderer'),
  build: {
    outDir: resolve(__dirname, 'out/web'),
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, 'src/renderer/index.html'),
    },
  },
  // ЖЕСТКО ЗАДАЕМ ЗНАЧЕНИЯ (без process.env)
  define: {
    'import.meta.env.VITE_BACKEND_URL': JSON.stringify('https://89.169.165.170.nip.io'),
    'import.meta.env.VITE_FRONTEND_URL': JSON.stringify('http://frontend-aa.website.yandexcloud.net'),
    'import.meta.env.VITE_USE_MOCKS': JSON.stringify('false'),
  },
  server: {
    proxy: {
      '/api': {
        target: 'https://89.169.165.170.nip.io',
        changeOrigin: true,
        secure: true,
      },
      '/auth': {
        target: 'https://89.169.165.170.nip.io',
        changeOrigin: true,
        secure: true,
      }
    }
  }
});
