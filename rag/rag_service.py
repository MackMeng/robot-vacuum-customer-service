#========================RAG服务模块========================
"""
总结服务类：用户提问，搜索参考资料，将搜索到的参考资料提交给模型，模型总结回复
1个类：RagSummarizeService
2个方法：1.retriever_docs    搜索参考资料
        2.rag_summarize    将用户提问，和搜索到的参考资料，提交给模型，模型总结回复
"""
from langchain_core.documents import Document
from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompt
from langchain_core.prompts import PromptTemplate
from model import factory
from langchain_core.output_parsers import StrOutputParser

def print_prompt(prompt):
    print("="*50)
    print(prompt.to_string())
    print("="*50)
    return prompt

class RagSummarizeService:
    def __init__(self):
        self.vector_store=VectorStoreService()
        self.retriever=self.vector_store.get_retriever()
        self.prompt_text = load_rag_prompt()
        self.prompt_template=PromptTemplate.from_template(self.prompt_text)
        self.model=factory.chat_model
        self.chain=self.__init__chain()

    def __init__chain(self):
        chain = self.prompt_template | self.model|StrOutputParser()
        return chain

    # 搜索参考资料————根据用户提问，搜索相关的文档并返回
    def retriever_docs(self,query:str)->list[Document]:
        return self.retriever.invoke(query)

    # 总结服务————根据用户提问，搜索相关的文档，将搜索到的文档提交给模型，模型总结回复
    def rag_summarize(self,query:str)->str:
        contex_docs=self.retriever_docs(query)      #相关的资料有多个
        context=""
        counter=0
        for doc in contex_docs:                     #需要遍历所有的文档
            counter+=1
            context+=f"【参考资料{counter}】：参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"
        return self.chain.invoke(
            {"input":query,"context":context}
        )

if __name__ == "__main__":
    rag= RagSummarizeService()
    print(rag.rag_summarize("小户型适合那些扫地机器人"))
