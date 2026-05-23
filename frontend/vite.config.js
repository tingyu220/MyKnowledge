import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,  // 监听所有网络接口
    port: 3000,
    https: {
      key: path.resolve(__dirname, '../backend/key.pem'),
      cert: path.resolve(__dirname, '../backend/cert.pem')
    },
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true
      }
    }
  }
})

