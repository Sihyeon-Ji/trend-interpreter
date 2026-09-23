"""API 서버. uv run scripts/serve_api.py  →  http://localhost:8080/docs"""
import uvicorn

from trend_agents.config import API_PORT

if __name__ == "__main__":
    uvicorn.run("trend_agents.api.app:app", host="0.0.0.0", port=API_PORT, reload=False)
