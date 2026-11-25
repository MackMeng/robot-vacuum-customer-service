# ========================报告生成子图模块========================
"""
报告生成场景的显式 LangGraph 编排（StateGraph）：
    用「状态 + 节点 + 条件边」把报告流程固定下来，替代原先依赖模型自主决定
    工具调用顺序的做法，流程确定、可讲清状态流转：
        START
          → resolve_user   获取用户ID
          → resolve_month  获取月份
          → fetch_records  检索使用记录
          → 条件边(是否有记录?)
              ├─ 有：generate_report 生成个性化报告 → END
              └─ 无：no_record       返回无记录提示     → END

    对外只暴露 run_report()，供 generate_usage_report 工具调用，
    与主 ReAct 智能体解耦。
"""

import json
from typing import TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent.tools.agent_tools import (
    fetch_external_data,
    get_current_month,
    get_user_id,
)
from model.factory import chat_model
from utils.logger_handler import logger
from utils.prompt_loader import load_report_prompt


class ReportState(TypedDict):
    """报告子图在节点间流转的状态。"""

    user_id: str  # 用户ID
    month: str  # 报告月份（YYYY-MM）
    records: dict  # 该用户该月的使用记录
    report: str  # 最终生成的报告文本


# 节点：获取用户ID
def resolve_user(state: ReportState) -> dict:
    return {"user_id": get_user_id.invoke({})}


# 节点：获取月份
def resolve_month(state: ReportState) -> dict:
    return {"month": get_current_month.invoke({})}


# 节点：检索使用记录
def fetch_records(state: ReportState) -> dict:
    records = fetch_external_data.invoke(
        {"user_id": state["user_id"], "month": state["month"]}
    )
    return {"records": records}


# 条件函数：根据是否检索到记录决定后续分支
def has_records(state: ReportState) -> str:
    return "generate" if state.get("records") else "empty"


# 节点：生成报告（把使用记录喂给模型，由模型撰写）
def generate_report(state: ReportState) -> dict:
    system_prompt = load_report_prompt()
    human_prompt = (
        f"用户ID：{state['user_id']}\n"
        f"报告月份：{state['month']}\n"
        f"使用记录（JSON）：\n"
        f"{json.dumps(state['records'], ensure_ascii=False, indent=2)}\n\n"
        f"请根据以上使用记录，生成该用户本月的扫地机器人使用情况报告与保养建议。"
    )
    response = chat_model.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ]
    )
    return {"report": response.content}


# 节点：无记录时的兜底提示
def no_record(state: ReportState) -> dict:
    msg = (
        f"未查询到用户 {state['user_id']} 在 {state['month']} 的使用记录，"
        f"暂时无法生成报告。请确认用户ID或月份是否正确。"
    )
    logger.warning(f"[report_graph] {msg}")
    return {"report": msg}


def _build_graph():
    builder = StateGraph(ReportState)
    builder.add_node("resolve_user", resolve_user)
    builder.add_node("resolve_month", resolve_month)
    builder.add_node("fetch_records", fetch_records)
    builder.add_node("generate_report", generate_report)
    builder.add_node("no_record", no_record)

    builder.add_edge(START, "resolve_user")
    builder.add_edge("resolve_user", "resolve_month")
    builder.add_edge("resolve_month", "fetch_records")
    builder.add_conditional_edges(
        "fetch_records",
        has_records,
        {"generate": "generate_report", "empty": "no_record"},
    )
    builder.add_edge("generate_report", END)
    builder.add_edge("no_record", END)

    return builder.compile()


# 编译一次，重复复用
report_graph = _build_graph()


def run_report() -> str:
    """执行报告子图，返回最终报告文本。"""
    initial_state: ReportState = {
        "user_id": "",
        "month": "",
        "records": {},
        "report": "",
    }
    result = report_graph.invoke(initial_state)
    return result.get("report", "")


if __name__ == "__main__":
    print(run_report())
