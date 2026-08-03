import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/unit/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
    // src/lib/env.ts 對缺少 API base URL 是 fail-fast 的（那是真實部署
    // 該有的行為），測試環境給定值即可。LIFF 相關變數刻意不給，
    // 讓預設情況就是「未設定 LIFF」的 web 模式。
    env: {
      NEXT_PUBLIC_API_BASE_URL: 'http://localhost:8000/api/v1',
    },
  },
})
