# ========================天气 MCP 服务========================
"""
独立的天气 MCP Server（stdio 传输）：
    对外暴露 get_weather 工具，数据来自 Open-Meteo（免 API Key）。
    agent 侧通过 MCP 客户端（utils/mcp_client.py）调用它，实现「工具服务化、可跨客户端复用」。
    通常无需手动启动：由 MCP 客户端在调用时以子进程方式拉起。
    手动调试：python mcp_server/weather_server.py（stdio，需配 MCP 客户端连接）。
"""

import json
import urllib.parse
import urllib.request

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("robot-vacuum-weather")

# WMO 天气代码 -> 中文描述（常用部分）
_WEATHER_CODE = {
    0: "晴",
    1: "大部晴朗",
    2: "多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "毛毛雨(轻)",
    53: "毛毛雨(中)",
    55: "毛毛雨(重)",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    80: "阵雨(轻)",
    81: "阵雨(中)",
    82: "阵雨(强)",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}


def _get_json(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": "robot-vacuum-weather-mcp/1.0"}
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


@mcp.tool()
def get_weather(city: str) -> str:
    """获取指定城市的实时天气（数据来源 Open-Meteo，免 API Key）。"""
    geo_url = (
        "https://geocoding-api.open-meteo.com/v1/search?"
        + urllib.parse.urlencode(
            {"name": city, "count": 1, "language": "zh", "format": "json"}
        )
    )
    geo = _get_json(geo_url)
    results = geo.get("results") or []
    if not results:
        return f"未找到城市：{city}，请确认城市名称。"

    loc = results[0]
    lat, lon = loc["latitude"], loc["longitude"]
    name = loc.get("name") or city

    fc_url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
            "timezone": "auto",
        }
    )
    data = _get_json(fc_url)
    cur = data.get("current", {})
    code = cur.get("weather_code")
    desc = _WEATHER_CODE.get(code, f"天气代码{code}")
    return (
        f"{name} 实时天气：{desc}，气温 {cur.get('temperature_2m')}℃，"
        f"相对湿度 {cur.get('relative_humidity_2m')}%，"
        f"风速 {cur.get('wind_speed_10m')} km/h（数据来源 Open-Meteo）"
    )


if __name__ == "__main__":
    mcp.run()
