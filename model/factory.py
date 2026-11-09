#========================模型工厂模块========================
"""
模型工厂模块：
    1.chat_model:聊天模型工厂类，用于创建聊天模型实例
    2.embedding_model:嵌入模型工厂类，用于创建嵌入模型实例
"""
from abc import ABC, abstractmethod
from typing import Optional
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_community.chat_models import ChatTongyi
from utils.cofig_handler import rag_conf

# 基础模型工厂类
class BaseModelFactory(ABC):
    @abstractmethod  # 抽象方法，必须在子类中实现,子类必须有generator方法,返回值为Embeddings或BaseChatModel
    # 生成模型实例
    def generator(self) -> Optional[Embeddings|BaseChatModel]:
        pass

# 聊天模型工厂类
class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[BaseChatModel]:
        return ChatTongyi(model=rag_conf["chat_model_name"])

# 嵌入模型工厂类
class EmbeddingModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings]:
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])

#快速创建模型实例
chat_model=ChatModelFactory().generator()
embedding_model=EmbeddingModelFactory().generator()
