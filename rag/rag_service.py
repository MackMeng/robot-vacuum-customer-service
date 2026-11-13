# ========================RAG服务模块========================
"""
总结服务类：用户提问，搜索参考资料，将搜索到的参考资料提交给模型，模型总结回复
1个类：RagSummarizeService
2个方法：1.retriever_docs    搜索参考资料(向量粗召回 + rerank精排)
        2.rag_summarize    将用户提问，和搜索到的参考资料，提交给模型，模型总结回复
"""

from langchain_core.documents import Document
from langchain_community.document_compressors import DashScopeRerank
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompt
from utils.cofig_handler import chroma_conf
from langchain_core.prompts import PromptTemplate
from model import factory
from langchain_core.output_parsers import StrOutputParser


class RagSummarizeService:
    def __init__(self):
        self.vector_store = VectorStoreService()
        self.retriever = self.vector_store.get_retriever()
        self.reranker = DashScopeRerank(top_n=chroma_conf["rerank_top_n"])
        # DashScopeRerank内部会强制默认gte-rerank(已下线),构造后显式覆盖为配置的精排模型
        self.reranker.model = chroma_conf["rerank_model_name"]
        self.prompt_text = load_rag_prompt()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = factory.chat_model
        self.chain = self.__init__chain()

    def __init__chain(self):
        chain = self.prompt_template | self.model | StrOutputParser()
        return chain

    # 搜索参考资料————先向量粗召回k条,再rerank精排留top_n条;精排后metadata会附带relevance_score
    def retriever_docs(self, query: str) -> list[Document]:
        docs = self.retriever.invoke(query)
        if not docs:  # 空结果直接返回,避免无意义的rerank API调用
            return []
        return list(self.reranker.compress_documents(docs, query))

    # 总结服务————根据用户提问，搜索相关的文档，将搜索到的文档提交给模型，模型总结回复
    def rag_summarize(self, query: str) -> str:
        context_docs = self.retriever_docs(query)
        # 逐条编号拼接参考资料(含元数据),供提示词模板的{context}占位符使用
        context = ""
        for counter, doc in enumerate(context_docs, start=1):
            context += f"【参考资料{counter}】：参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"
        return self.chain.invoke({"input": query, "context": context})


if __name__ == "__main__":
    rag = RagSummarizeService()
    print(rag.rag_summarize("小户型适合那些扫地机器人"))
