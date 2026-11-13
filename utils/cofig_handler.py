# ========================配置文件处理模块========================
"""
yaml配置文件处理
k:v
四个快速获取配置文件内容的方法：        打开文件，然后返回全加载内容
    1.rag_conf:加载rag相关的配置文件
    2.chroma_conf:加载chroma向量数据库的配置文件
    3.prompts_conf:加载prompts配置文件
    4.agent_conf:加载agent配置文件
"""

import yaml
from utils.path_tool import get_abspath


# 加载rag相关的配置文件
def load_rag_cofig(
    config_path: str = get_abspath("config/rag.yaml"), encoding: str = "utf-8"
):
    """
    加载rag相关的配置文件
    :param config_path: 配置文件路径
    :return: 配置文件内容
    """
    with open(config_path, "r", encoding=encoding) as f:  # 打开配置文件
        return yaml.load(
            f, Loader=yaml.FullLoader
        )  # 加载yaml文件,Loader=yaml.FullLoader:加载所有yaml语法


# 加载chroma向量数据库的配置文件
def load_chroma_cofig(
    config_path: str = get_abspath("config/chroma.yaml"), encoding: str = "utf-8"
):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


# 加载prompts配置文件
def load_prompts_cofig(
    config_path: str = get_abspath("config/prompts.yaml"), encoding: str = "utf-8"
):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


# 加载agent配置文件
def load_agent_cofig(
    config_path: str = get_abspath("config/agent.yaml"), encoding: str = "utf-8"
):
    with open(config_path, "r", encoding=encoding) as f:
        return yaml.load(f, Loader=yaml.FullLoader)


# 快速获取配置文件内容
rag_conf = load_rag_cofig()
chroma_conf = load_chroma_cofig()
prompts_conf = load_prompts_cofig()
agent_conf = load_agent_cofig()


if __name__ == "__main__":
    print(rag_conf["chat_model_name"])
