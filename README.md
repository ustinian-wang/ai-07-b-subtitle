# ai-07-b-subtitle

由 `scripts/add-ai-project.sh` 生成的 **FastAPI + Vite（Vue 3）** 最小沙箱，与 `projects/ai-01-chat` 等家族项目结构对齐。

## 开发

```bash
cd projects/ai-07-b-subtitle/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 填写 OPENAI_API_KEY 等
uvicorn app.main:app --host 127.0.0.1 --port 8907

cd ../frontend
npm install && npm run dev
# 浏览器打开 Vite 地址（默认 http://127.0.0.1:9177 ）
```

- 健康检查: `GET http://127.0.0.1:8907/api/health`
- 代理: 前端 `/api` → `http://127.0.0.1:8907`；改端口时同步 `backend/.env` 与 `frontend/.env.development`

## Git

本目录为**独立仓库**：在 `projects/ai-07-b-subtitle` 内执行 `git remote add` / `git push`。

共性说明见仓库根目录 `docs/ai-projects-family.md`。
