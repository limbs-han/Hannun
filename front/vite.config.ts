import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // VITE_DEV_PROXY 에 서버 주소를 넣으면 /api 요청을 그쪽으로 넘깁니다.
  // 배포 API 는 localhost 오리진을 허용하지 않으므로, 개발 중에는 이 프록시로 동일 출처를 만듭니다.
  const proxyTarget = loadEnv(mode, process.cwd(), '').VITE_DEV_PROXY

  return {
    plugins: [vue()],
    server: proxyTarget
      ? { proxy: { '/api': { target: proxyTarget, changeOrigin: true, secure: true } } }
      : undefined,
  }
})
