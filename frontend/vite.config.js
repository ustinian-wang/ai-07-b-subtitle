import { defineConfig, loadEnv } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const target = (env.VITE_PROXY_API || 'http://127.0.0.1:8907').replace(/\/+$/, '');
  const proxy = { '/api': { target, changeOrigin: true } };
  return {
    plugins: [vue()],
    server: { host: '127.0.0.1', port: 9177, proxy },
    preview: { host: '127.0.0.1', port: 9177, proxy },
  };
});
