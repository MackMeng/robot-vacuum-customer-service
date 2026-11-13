# ====================日志工具模块========================
"""
为整个项目提供统一的日志记录器
1个方法：get_logger：获取日志记录器
"""

import logging
import os
from datetime import datetime
from utils.path_tool import get_abspath

# 日志保存的根目录(文件夹)
LOG_ROOT = get_abspath("logs")
# 确保日志目录存在，若不存在则创建目录
os.makedirs(LOG_ROOT, exist_ok=True)
# 默认日志格式配置   时间（年-月-日 时:分:秒） —— 日志记录器名称 —— 日志级别 —— 模块名：行号 —— 日志消息
DEAFULT_LOG_FORMAT = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)


# 获取日志记录器
def get_logger(
    name: str = "agent",
    console_level: int = logging.INFO,  # 控制台日志级别
    file_level: int = logging.DEBUG,  # 文件日志级别
    log_file=None,
) -> logging.Logger:
    # 创建日志记录器---logging.getLogger:获取日志记录器
    logger = logging.getLogger(name)
    # setLevel:设置日志级别
    logger.setLevel(console_level)

    # 避免重复添加handler
    if logger.handlers:
        return logger

    # 控制台handler:打印日志到控制台
    console_handler = logging.StreamHandler()  # 创建控制台handler
    console_handler.setFormatter(DEAFULT_LOG_FORMAT)  # 设置日志格式
    console_handler.setLevel(console_level)  # 设置日志级别
    logger.addHandler(console_handler)  # 添加控制台handler

    # 文件handler:打印日志到文件
    if not log_file:  # 日志文件不存在时，创建当天的日志文件
        log_file = os.path.join(
            LOG_ROOT, f'{name}_{datetime.now().strftime("%Y-%m-%d")}.log'
        )
    file_handler = logging.FileHandler(log_file, encoding="utf-8")  # 创建文件handler
    file_handler.setLevel(file_level)  # 设置日志级别
    file_handler.setFormatter(DEAFULT_LOG_FORMAT)  # 设置日志格式
    logger.addHandler(file_handler)  # 添加文件handler

    return logger


# 快捷获取日志记录器
logger = get_logger()

if __name__ == "__main__":
    logger.info("这是一条info日志")
    logger.debug("这是一条debug日志")
    logger.error("这是一条error日志")
    logger.warning("这是一条warning日志")
    logger.critical("这是一条critical日志")
