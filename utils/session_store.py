# ========================会话存储模块========================
"""
基于 SQLite 的会话持久化存储，为 Web 端提供多轮对话的「新建 / 加载 / 删除」能力。
    存储粒度：一个会话一行，整段对话以 JSON 字符串存于 messages 字段。
    主要方法：
        1. init_db：建表（幂等）
        2. create_session：新建会话，返回会话 ID
        3. list_sessions：按最近活跃倒序列出会话
        4. load_messages：加载某会话的完整对话
        5. save_messages：覆盖保存某会话的对话并刷新活跃时间
        6. delete_session：删除某会话
"""

import json
import os
import sqlite3
from contextlib import contextmanager

from utils.cofig_handler import agent_conf
from utils.logger_handler import logger
from utils.path_tool import get_abspath

# 数据库文件路径，默认 data/sessions.db，可在 config/agent.yaml 中配置
DB_PATH = get_abspath(agent_conf.get("session_db_path", "data/sessions.db"))


@contextmanager     # 上下文管理器，确保连接在使用后自动关闭
def _get_conn():
    """随用随开一个连接，退出时提交并关闭。
    Streamlit 每次交互可能落在不同线程，复用全局连接会触发 sqlite3 的
    check_same_thread 限制，故每次操作独立开关连接。"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn  # yield之前执行的代码会在with语句块中执行，之后的代码会在退出with语句块时执行
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """建表（幂等），应用启动时调用一次。"""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT,
                messages   TEXT NOT NULL DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)


def create_session(title: str = "新会话") -> int:
    """新建一个空会话并返回自增 ID。标题由调用方传入（通常取首条用户消息）。"""
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (title, messages) VALUES (?, ?)",
            (title, "[]"),
        )
        return cur.lastrowid    #返回最新的自增主键的id，若插入失败则返回None


def list_sessions() -> list[dict]:
    """按最近活跃（updated_at）倒序返回会话列表，仅含侧边栏需要的字段。"""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, updated_at FROM sessions ORDER BY updated_at DESC, id DESC"
        ).fetchall()    #由新到旧排序
    return [dict(row) for row in rows]


def load_messages(session_id: int) -> list[dict]:
    """加载某会话的完整对话（role/content 列表）；会话不存在时返回空列表。"""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT messages FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()     #返回单条记录，若不存在则返回[]
    if row is None:
        logger.warning(f"[session_store] 会话 {session_id} 不存在，返回空对话")
        return []
    return json.loads(row["messages"])


def save_messages(session_id: int, messages: list[dict]) -> None:
    """覆盖保存整段对话并刷新活跃时间。ensure_ascii=False 保证中文不被转义。"""
    payload = json.dumps(messages, ensure_ascii=False)
    with _get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET messages = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (payload, session_id),
        )


def delete_session(session_id: int) -> None:
    """删除某会话。"""
    with _get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


if __name__ == "__main__":
    init_db()   # 建表
    sid = create_session("扫地机器人如何保养")   # 创建会话
    save_messages(
        sid,
        [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好，有什么可以帮你？"},
        ],
    )
    print(list_sessions())
    print(load_messages(sid))
    delete_session(sid)
    print(list_sessions())
