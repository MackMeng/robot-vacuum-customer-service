#========================文件处理工具模块========================
"""
四个方法：
    1.get_file_md5_hex:把文档内容变为md5的十六进制字符串
    2.listdir_with_allowed_type:获取文件夹下的所有文件路径（支持指定文件类型）
    3.pdf_loader:加载pdf文档内容
    4.txt_loader:加载txt文档内容
"""

import hashlib
import os
from utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, TextLoader

#把文档内容变为md5的十六进制字符串
def get_file_md5_hex(file_path:str):
    if not os.path.exists(file_path):
        logger.error(f"[md5计算]文件 {file_path}不存在")
        return None
    if not os.path.isfile(file_path):
        logger.error(f"[md5计算]路径 {file_path}不是文件")
        return None

    md5_obj= hashlib.md5()  #hashlib.md5()返回一个md5对象
    chunk_szie=4096
    try:
        with open(file_path, "rb") as f:        #rb:二进制读取
            while chunk := f.read(chunk_szie):  #将右边赋值给chunk在while判断
                md5_obj.update(chunk)           #更新md5对象直到读取到文件末尾
        md5_hex=md5_obj.hexdigest()             #hexdigest()返回md5对象的十六进制字符串
        return md5_hex
    except Exception as e:
        logger.error(f"[md5计算]文件 {file_path} 计算md5失败: {str(e)}")
        return None

#获取文件夹下的所有文件路径（支持指定文件类型）
def listdir_with_allowed_type(path:str,allowed_types:tuple[str]):
    files=[]
    if not os.path.isdir(path):     #判断是否是文件夹
        logger.error(f"[listdir_with_allowed_type]路径 {path}不是文件夹")
        return ()                   #返回空元组
    for f in os.listdir(path):
        if f.endswith(allowed_types):
            files.append(os.path.join(path,f))
    return tuple(files)

#加载pdf文档内容——转为Document对象列表
def pdf_loader(file_path:str)->list[Document]:
    loader=PyPDFLoader(file_path)
    return loader.load()
#加载txt文档内容——转为Document对象列表
def txt_loader(file_path:str,encoding:str="utf-8")->list[Document]:
    loader=TextLoader(file_path,encoding=encoding)
    return loader.load()
