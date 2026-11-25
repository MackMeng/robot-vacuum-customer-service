# ========================智能客服工具模块========================
"""
agent工具调用模块：
    对外（主智能体可调用）4个工具：
        1. rag_summarize：从向量库检索并总结资料
        2. get_weather：获取指定城市的天气
        3. get_city_name：获取用户所在城市的名称
        4. generate_usage_report：生成/查询个人使用报告（内部走报告子图）
    报告子图内部复用（不直接暴露给模型）3个数据工具：
        get_user_id：获取用户id
        get_current_month：获取当前月份
        fetch_external_data：从外部系统获取指定用户指定月份的使用记录
"""

import os.path
import random
from rag.rag_service import RagSummarizeService
from langchain_core.tools import tool
from utils.cofig_handler import agent_conf
from utils.logger_handler import logger
from utils.mcp_client import run_mcp_tool
from utils.path_tool import get_abspath

user_ids = [
    "1001",
    "1002",
    "1003",
    "1004",
    "1005",
    "1006",
    "1007",
    "1008",
    "1009",
    "1010",
]
month_arr = [
    "2025-01",
    "2025-02",
    "2025-03",
    "2025-04",
    "2025-05",
    "2025-06",
    "2025-07",
    "2025-08",
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
]
external_data = {}
current_city = None


@tool(description="从向量存储中检索参考资料")
def rag_summarize(query: str) -> str:
    return RagSummarizeService().rag_summarize(query)


# get_city_name/get_user_id/get_current_month 为演示用模拟数据（随机返回），非真实查询
@tool(
    description="获取指定城市的实时天气（通过 MCP 天气服务，数据来源 Open-Meteo），以字符串返回"
)
def get_weather(city: str) -> str:
    # 通过独立 MCP 天气服务获取真实天气；服务不可用时降级为提示，避免打断对话
    server_script = get_abspath("mcp_server/weather_server.py")
    try:
        return run_mcp_tool(server_script, "get_weather", {"city": city})
    except Exception as e:
        logger.error(f"[get_weather] MCP 天气服务调用失败：{e}")
        return f"{city}的天气信息暂时获取失败（天气服务不可用）。"


@tool(description="获取用户所在城市的名称，以字符串的形式返回")
def get_city_name() -> str:
    return random.choice(["深圳", "合肥", "杭州"])


@tool(description="获取用户id，以字符串的形式返回")
def get_user_id() -> str:
    return random.choice(user_ids)


@tool(description="获取当前月份，以字符串的形式返回")
def get_current_month() -> str:
    return random.choice(month_arr)


def generate_external_data() -> dict:
    """
    {
        "user_id":{
            "month":{"特征":xxx,"效率":xxx,...},
            "month2":{"特征":xxx,"效率":xxx,...},
    }
    :return:
    """
    if not external_data:
        external_data_path = get_abspath(agent_conf["external_data_path"])
        if not os.path.exists(external_data_path):
            raise FileNotFoundError(f"外部数据文件{external_data_path}不存在")

        with open(external_data_path, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:  # 跳过第一行
                arr: list[str] = line.strip().split(
                    ","
                )  # strip（）去掉首尾空格，split（）根据逗号分隔
                user_id: str = arr[0].replace('"', "")  # replace（）去掉双引号
                feature: str = arr[1].replace('"', "")
                efficiency: str = arr[2].replace('"', "")
                consumables: str = arr[3].replace('"', "")
                time: str = arr[4].replace('"', "")
                comparison: str = arr[5].replace('"', "")

                if user_id not in external_data:
                    external_data[user_id] = {}
                external_data[user_id][time] = {
                    "特征": feature,
                    "效率": efficiency,
                    "消耗品": consumables,
                    "比较": comparison,
                }
    return external_data


@tool(description="从外部系统中，获取指定用户在指定月份的使用记录，以字符串的形式返回")
def fetch_external_data(user_id: str, month: str) -> dict:
    generate_external_data()

    try:
        return external_data[user_id][month]
    except KeyError:
        logger.warning(
            f"[fetch_external_data] 未能检索到用户：{user_id}在{month}的使用记录"
        )
        return {}


@tool(
    description=(
        "生成或查询用户本月的扫地机器人使用报告与保养建议。"
        "内部会自动完成：获取用户ID→获取当前月份→检索使用记录→生成报告。"
        "当用户明确要求「生成/查询我的使用报告、使用记录」时调用；"
        "调用后请将返回的报告内容原样作为最终回答输出，不要改写、概括或补充。"
    )
)
def generate_usage_report() -> str:
    # 延迟导入报告子图，避免与 report_graph 形成循环依赖
    from agent.report_graph import run_report

    return run_report()


if __name__ == "__main__":
    print(fetch_external_data.invoke({"user_id": "1001", "month": "2025-02"}))
