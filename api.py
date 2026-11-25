# ========================FastAPI 接口层========================
"""
面向工程的 HTTP 接口（与 Streamlit demo 并存）：
    GET    /health            健康检查
    GET    /sessions          会话列表
    DELETE /sessions/{id}     删除会话
    POST   /chat              SSE 流式对话（支持 session_id 多轮）
启动：uvicorn api:app --host 0.0.0.0 --port 8000
"""

import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from utils import session_store

app = FastAPI(title="扫地机器人智能客服 API", version="1.0.0")

session_store.init_db()

_agent = None


def get_agent():
    """延迟初始化 ReactAgent：避免导入期就要求 API Key，加快健康检查。"""
    global _agent
    if _agent is None:
        from agent.react_agent import ReactAgent

        _agent = ReactAgent()
    return _agent


class ChatRequest(BaseModel):
    message: str
    session_id: int | None = None


def _sse(event: str | None, data) -> str:
    """把一条数据封装成 SSE 帧；dict 自动转 JSON。"""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    head = f"event: {event}\n" if event else ""
    return f"{head}data: {payload}\n\n"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/sessions")
def list_sessions():
    return session_store.list_sessions()


@app.delete("/sessions/{session_id}")
def delete_session(session_id: int):
    session_store.delete_session(session_id)
    return {"deleted": session_id}


@app.post("/chat")
def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message 不能为空")

    session_id = req.session_id
    created = False
    if session_id is None:
        session_id = session_store.create_session(req.message.strip()[:20])
        created = True

    history = session_store.load_messages(session_id)

    def event_stream():
        yield _sse("session", {"session_id": session_id, "created": created})
        collected = []
        try:
            for chunk in get_agent().execute_stream(req.message, history):
                collected.append(chunk)
                yield _sse(None, chunk)
        except Exception as e:  # 流中途异常：先发 error 事件再结束
            yield _sse("error", str(e))
            return

        messages = list(history)
        messages.append({"role": "user", "content": req.message})
        messages.append({"role": "assistant", "content": "".join(collected).strip()})
        session_store.save_messages(session_id, messages)
        yield _sse("done", "[DONE]")

    return StreamingResponse(event_stream(), media_type="text/event-stream")
