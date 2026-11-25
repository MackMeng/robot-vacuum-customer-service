# ========================智能客服系统========================
"""
1个ReactAgent类：
    1个方法：execute_stream 执行流式输出（支持传入历史，实现多轮对话）
    报告生成由 generate_usage_report 工具内部调用显式 StateGraph 子图完成。
"""

from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompt
from agent.tools.agent_tools import (
    rag_summarize,
    get_weather,
    get_city_name,
    generate_usage_report,
)
from agent.tools.middleware import monitor_tool, log_before_model


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompt(),
            tools=[
                rag_summarize,
                get_weather,
                get_city_name,
                generate_usage_report,
            ],
            middleware=[monitor_tool, log_before_model],
        )

    # 执行流式输出（history 为既往对话，用于多轮上下文）
    def execute_stream(self, query: str, history: list | None = None):
        # 滑动窗口：只保留最近若干条历史，避免上下文无限增长导致变慢、变贵甚至超窗口
        history = (history or [])[-8:]  # 取最近8条历史记录
        input_dict = {"messages": history + [{"role": "user", "content": query}]}
        # stream_mode="values"，返回模型的输出值，而不是中间状态
        chunks = self.agent.stream(input_dict, stream_mode="values")
        for chunk in chunks:
            latest_message = chunk["messages"][-1]
            # 仅输出模型的最终文本回答：跳过工具结果(ToolMessage)与带工具调用的中间消息，
            # 避免把工具的原始返回值泄露给用户，或让报告等内容重复输出
            if (
                latest_message.type == "ai"
                and not getattr(latest_message, "tool_calls", None)
                and latest_message.content
            ):
                yield latest_message.content.strip() + "\n"


if __name__ == "__main__":
    agent = ReactAgent()
    for chunk in agent.execute_stream("扫地机器人在我所在的地区的气温下该如何保养"):
        print(chunk, end="", flush=True)  # flush=True，确保每个字符都立即打印
