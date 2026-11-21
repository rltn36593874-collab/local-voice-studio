import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 기본은 mock 모드. `npm run dev:real`(.env.real의 VITE_API=real)일 때만 백엔드(:8000)로 프록시한다.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1', // 사내 1인 도구: 이 PC 밖에서 접속 못 하게
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
