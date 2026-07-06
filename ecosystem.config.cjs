/** pm2 本地开发：backend uvicorn --reload + frontend Vite HMR */
const BACKEND_PORT = process.env.BACKEND_PORT || 8907;
const VITE_PORT = process.env.VITE_PORT || 9177;
const DEV_HOST = process.env.DEV_HOST || '0.0.0.0';

module.exports = {
  apps: [
    {
      name: 'ai-07-b-subtitle-backend',
      cwd: './backend',
      script: '.venv/bin/uvicorn',
      args: `app.main:app --host ${DEV_HOST} --port ${BACKEND_PORT} --reload --reload-dir app`,
      interpreter: 'none',
      watch: false,
    },
    {
      name: 'ai-07-b-subtitle-frontend',
      cwd: './frontend',
      script: 'node_modules/.bin/vite',
      args: `--host ${DEV_HOST} --port ${VITE_PORT}`,
      interpreter: 'none',
      watch: false,
    },
  ],
};
