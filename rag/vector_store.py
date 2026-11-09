#========================向量数据库存储模块========================
"""
rag模块中向量数据库存储模块——————初始化向量库，获取检索器，加载文档到向量库
1个类：VectorStoreService
2个类方法：
    1.get_retriever:获取检索器-返回检索器对象
    2.load_documents:加载文档-从数据文件内读取数据文件，转为向量存入向量库
"""
import os
from langchain_chroma import Chroma
from langchain_core.documents import Document
from utils.cofig_handler import chroma_conf
from model.factory import embedding_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from utils.path_tool import get_abspath
from utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from utils.logger_handler import logger

#向量库存储服务————加载文档，分片，存储到向量库
class VectorStoreService:
    def __init__(self):
        #使用 chroma 向量数据库，初始化向量数据库对象
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],     # 集合名称
            embedding_function=embedding_model,
            persist_directory=get_abspath(chroma_conf["persist_directory"]),
        )
        #初始化文本分块器
        self.splitter=RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunksize"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )


    # 获取检索器-返回检索器对象
    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k": chroma_conf["k"]})

    # 加载文档
    def load_documents(self):
        """
        从数据文件内读取数据文件，转为向量存入向量库
        先通过md5检查文件是否已处理过，若已处理过则跳过，否则处理
        :return:None
        """
        def check_md5_hex(md5_for_check:str):       #md5_for_check:要检查的文档的md5值
            if not os.path.exists(get_abspath(chroma_conf["md5_hex_store"])):
                # 创建文件
                open(get_abspath(chroma_conf["md5_hex_store"]), "w", encoding="utf-8").close()
                return False    # 文件不存在,md5没处理过

            with open(get_abspath(chroma_conf["md5_hex_store"]), "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line=line.strip()    # 去掉前后空格
                    if line==md5_for_check:
                        return True    # md5已处理过
            return False    # md5未处理过

        def save_md5_hex(md5_for_save:str):
            with open(get_abspath(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
                f.write(md5_for_save+"\n")

        # 获取文件文档
        def get_file_documents(read_path:str)->list[Document]:
            if read_path.endswith(".txt"):
                return txt_loader(read_path)
            if read_path.endswith(".pdf"):
                return pdf_loader(read_path)
            return []    # 其他文件类型,返回空列表

        # 遍历数据文件夹下的所有允许类型的文件的绝对路径-----得到的元组，每个元素是一个文件的绝对路径
        allowed_files_path=listdir_with_allowed_type(
            get_abspath(chroma_conf["data_path"]),
            tuple(chroma_conf["allowed_knowledge_file_types"])
        )
        for path in allowed_files_path:
            #获取文件的md5
            md5_hex=get_file_md5_hex(path)
            if md5_hex is None:
                logger.warning(f"[加载知识库] {path} MD5计算失败,跳过")
                continue
            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库] {path}内容已经存在知识库,跳过")    # md5已处理过,跳过
                continue
            try:
                documents:list[Document]=get_file_documents(path)
                if not documents:
                    logger.warning(f"[加载知识库] {path}内没有有效内容,跳过")    # 文档为空,跳过
                    continue
                split_document:list[Document]=self.splitter.split_documents(documents)
                if not split_document:
                    logger.warning(f"[加载知识库] {path}分片后没有有效内容,跳过")    # 文档为空,跳过
                    continue
                self.vector_store.add_documents(split_document)  # 加载文档到向量库
                save_md5_hex(md5_hex)                            #记录已处理的md5
                logger.info(f"[加载知识库] {path}内容已加载到知识库")    # 加载成功
            except Exception as e:
                #exc_info=True  # 打印详细错误信息,包括栈跟踪
                logger.error(f"[加载知识库] {path}内容加载失败: {str(e)}",exc_info=True)    # 加载失败
                continue

if __name__ == "__main__":
    vs=VectorStoreService()
    vs.load_documents()
    retriever=vs.get_retriever()
    res=retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("="*50)
