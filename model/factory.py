# ========================模型工厂模块========================
"""
模型工厂模块：
    1.chat_model:聊天模型工厂类，用于创建聊天模型实例
    2.embedding_model:嵌入模型工厂类，用于创建嵌入模型实例
"""

import os
from abc import ABC, abstractmethod
from typing import Optional
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.embeddings.dashscope import BATCH_SIZE
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from utils.cofig_handler import rag_conf


# 基础模型工厂类
class BaseModelFactory(ABC):
    @abstractmethod  # 抽象方法，必须在子类中实现,子类必须有generator方法,返回值为Embeddings或BaseChatModel
    # 生成模型实例
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


# 聊天模型工厂类
class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[BaseChatModel]:
        # 新旗舰模型(如qwen3.8-max)仅支持OpenAI兼容端点,ChatTongyi原生接口已不可用
        return ChatOpenAI(
            model=rag_conf["chat_model_name"],
            api_key=os.getenv("DASHSCOPE_API_KEY"),
            base_url=rag_conf["chat_base_url"],
        )


# 嵌入模型工厂类
class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings]:
        # 封装层BATCH_SIZE表未收录新模型时默认每批25条,超出qwen3.7系列上限20条,需显式注册
        BATCH_SIZE.setdefault(rag_conf["embedding_model_name"], 20)
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])


# 快速创建模型实例
chat_model = ChatModelFactory().generator()
embedding_model = EmbeddingModelFactory().generator()
