import { resolve } from 'path'
import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  main: {
    define: {
      'process.env.VITE_BACKEND_URL': JSON.stringify(process.env.VITE_BACKEND_URL || 'https://89.169.165.170.nip.io')
    }
  },

  preload: {},

  renderer: {
    resolve: {
      alias: {
        '@renderer': resolve('src/renderer/src'),
      },
    },

    plugins: [react()],

    server: {
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  },
})
