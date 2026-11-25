# 依赖安装（含 mcp / fastapi / uvicorn）
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUTF8=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000 8501
ENTRYPOINT ["./docker-entrypoint.sh"]
# 默认启动 API；UI 可通过 compose 用不同 command 启动 streamlit
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]