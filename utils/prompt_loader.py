#========================提示词加载工具模块========================
"""
3个方法：
    1.load_system_prompt:加载系统提示词
    2.load_rag_prompt:加载rag提示词
    3.load_report_prompt:加载报告提示词
"""
from utils.cofig_handler import prompts_conf
from utils.path_tool import get_abspath
from utils.logger_handler import logger

#加载系统提示词
def load_system_prompt():
    try:
        system_prompt_path=get_abspath(prompts_conf['main_prompt_path'])
    except KeyError as e:
        logger.error("[load_system_prompt]在yaml配置项中没有main_prompt_path配置项")
        raise e #抛出异常

    try:
        return open(system_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_system_prompt]解析系统提示词出错,  {str(e)}")
        raise e

#加载rag提示词
def load_rag_prompt():
    try:
        rag_prompt_path=get_abspath(prompts_conf['rag_summarize_prompt_path'])
    except KeyError as e:
        logger.error("[load_rag_prompt]在yaml配置项中没有rag_summarize_prompt_path配置项")
        raise e #抛出异常

    try:
        return open(rag_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_rag_prompt]解析rag总结提示词出错,  {str(e)}")
        raise e

#加载报告提示词
def load_report_prompt():
    try:
        report_prompt_path=get_abspath(prompts_conf['report_prompt_path'])
    except KeyError as e:
        logger.error("[load_report_prompt]在yaml配置项中没有report_prompt_path配置项")
        raise e #抛出异常

    try:
        return open(report_prompt_path,"r",encoding="utf-8").read()
    except Exception as e:
        logger.error(f"[load_report_prompt]解析报告提示词出错,  {str(e)}")
        raise e


if __name__ == "__main__":
    print(load_system_prompt())
    print("=" * 50)
    print(load_rag_prompt())
    print("=" * 50)
    print(load_report_prompt())
