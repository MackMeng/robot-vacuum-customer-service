"""
项目介绍————面向消费者（toc）的智能客服系统，旨在为用户提供全周期的扫地机器人产品的相关服务
    1.智能问答服务：
        ·处理购买前的产品咨询（如功能、价格、对比等）
        ·解决购买后的使用问题（如操作指导、故障处理、维护建议等）
        ·基于RAG技术，从知识库检索准确信息并用自然语言回答客户，确保响应及时且可靠
    2.使用报告和优化建议生成：
        ·针对以购买的用户，自动分析产品的使用数据（如清洁频率、耗材状态、错误日志）
        ·生成个性化报告，总结使用情况并给出优化建议（如清洁计划调整、部件更换提醒）
        ·支持用户主动查询报告或系统定期推送，帮助用户最大化产品价值
"""

import streamlit  as st
from agent.react_agent import ReactAgent
import time

#标题
st.title("扫地机器人智能客服系统")
st.divider()

#长期保存状态
if "agent" not in st.session_state:
  st.session_state["agent"]=ReactAgent()

if "message" not in st.session_state:
  st.session_state["message"]=[]

for message in st.session_state["message"]:
  st.chat_message(message["role"]).write(message["content"])

#用户输入提示词query
prompt=st.chat_input("请输入您的问题：")
if prompt:
  st.chat_message("user").write(prompt)
  st.session_state["message"].append({"role": "user", "content": prompt})

  #调用智能客服系统
  response_messages=[]
  with st.spinner("智能客服思考中..."):
    res_stream=st.session_state["agent"].execute_stream(prompt)
    #迭代器——将流式输出的内容记录到缓存列表中
    def capture(generator,cache_list):
      for chunk in generator:
        cache_list.append(chunk)

        for char in chunk:
          time.sleep(0.01)
          yield char   #yield:返回当前迭代值，不阻塞后续代码执行，一个字符一个字符地返回
    st.chat_message("assistant").write_stream(capture(res_stream,response_messages))
    st.session_state["message"].append({"role":"assistant","content":response_messages[-1]})
    st.rerun()  #重新运行当前页面，更新缓存列表
