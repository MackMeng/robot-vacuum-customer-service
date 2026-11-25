# ================中间件模块================
"""
进行工具执行与模型调用的监控：
    2个中间件函数：
        1. monitor_tool: 工具执行过程监控
        2. log_before_model: 模型执行前输出日志

"""

from typing import Callable
from langchain.agents import AgentState
from langchain.agents.middleware import (
    wrap_tool_call,
    before_model,
)
from langchain.tools.tool_node import ToolCallRequest
from langgraph.runtime import Runtime
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from utils.logger_handler import logger


# 工具执行的监控
@wrap_tool_call
def monitor_tool(
    request: ToolCallRequest,
    handler: Callable[[ToolCallRequest], ToolMessage | Command],
) -> ToolMessage | Command:
    """
    工具执行过程监控，记录工具的执行信息
    :param request: 请求的封装数据
    :param handler: 执行的函数本身
    :return: 传进来的数据原封不动的返回
    """
    logger.info(f"[tool monitor]执行工具：{request.tool_call['name']}")
    logger.info(f"[tool monitor]传入参数：{request.tool_call['args']}")
    try:
        result = handler(request)
        logger.info(f"[monitor tool]工具{request.tool_call['name']}调用成功")
        return result
    except Exception as e:
        logger.error(
            f"[monitor tool]工具{request.tool_call['name']}调用失败，原因:{str(e)}"
        )
        raise e


@before_model
# 模型执行前输出日志
def log_before_model(state: AgentState, runtime: Runtime):
    """
    :param state:   整个Agent智能体的状态记录
    :param runtime: 记录整个执行过程中的上下文信息
    :return:
    """
    logger.info(f"[log before model]即将调用模型，带有{len(state['messages'])}条消息")
    logger.debug(
        f"[log before model]{type(state['messages'][-1]).__name__}|{state['messages'][-1].content.strip()}"
    )
    return None
