import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => ({
  base: mode === 'mock' ? './' : '/',
  // Pages가 JSON을 10분 캐시해서, 배포마다 주소가 바뀌게 빌드 시각을 붙인다.
  define: { __BUILD_ID__: JSON.stringify(String(Date.now())) },
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
}))
