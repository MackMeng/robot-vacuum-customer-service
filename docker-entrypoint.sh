 #!/bin/sh
set -e

# 首次启动若无向量库则构建一次（需 DASHSCOPE_API_KEY 与网络）；失败不阻断启动
if [ ! -f "chroma_db/chroma.sqlite3" ]; then
  echo "[entrypoint] 未检测到向量库，开始构建..."
  python -m rag.vector_store || echo "[entrypoint] 向量库构建失败，可稍后手动执行：python -m rag.vector_store"
fi

exec "$@"