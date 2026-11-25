# ========================MCP 客户端工具========================
"""
以同步方式调用本地 MCP Server 的工具：
    在独立线程中启动事件循环执行异步 MCP 调用，避免与调用方已在运行的事件循环冲突，
    使同步的 ReAct / Streamlit 流程也能复用 MCP 工具服务。
"""

import asyncio
import os
import sys
import threading


async def _call_tool(server_script: str, tool_name: str, arguments: dict) -> str:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,  # 使用当前解释器（含已安装的 mcp）拉起 server
        args=[server_script],
        env=dict(os.environ),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            texts = [c.text for c in result.content if getattr(c, "text", None)]
            return "\n".join(texts) if texts else str(result)


def run_mcp_tool(
    server_script: str, tool_name: str, arguments: dict, timeout: float = 30
) -> str:
    """同步调用 MCP Server 工具；内部在独立线程跑 asyncio.run，规避事件循环冲突。"""
    box: dict = {}
    error: dict = {}

    def _runner():
        try:
            box["value"] = asyncio.run(_call_tool(server_script, tool_name, arguments))
        except Exception as e:  # 记录后在主线程抛出
            error["e"] = e

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError(f"MCP 工具调用超时：{tool_name}")
    if "e" in error:
        raise error["e"]
    return box.get("value", "")
