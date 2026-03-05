import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig(({ command, mode }) => {
  const isProduction = mode === 'production'

  return {
    plugins: [react()],
    base: isProduction ? './' : '/',  // relative paths in production
    server: {
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000', // dev backend
          changeOrigin: true,
          secure: false,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: !isProduction,
    },
  }
})