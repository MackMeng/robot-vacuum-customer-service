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
    3.多轮会话管理：
        ·基于SQLite持久化会话，支持新建、加载历史对话、删除（带二次确认）
        ·将既往对话作为上下文传入Agent，实现真正的多轮记忆
"""

import time
import streamlit as st
from agent.react_agent import ReactAgent
from utils import session_store

# 初始化会话存储表（幂等，仅首次真正建表）
session_store.init_db()

# 标题
st.title("扫地机器人智能客服系统")
st.divider()

# 长期保存状态：agent 单例，切换会话时复用，避免重复加载模型
if "agent" not in st.session_state:
    st.session_state["agent"] = ReactAgent()

if "message" not in st.session_state:
    st.session_state["message"] = []

# 当前会话 ID（None 表示尚未落库的新会话）
if "session_id" not in st.session_state:
    st.session_state["session_id"] = None

# 待确认删除的会话 ID（None 表示无删除请求）
if "confirm_delete" not in st.session_state:
    st.session_state["confirm_delete"] = None

# ====================侧边栏：会话管理====================
with st.sidebar:
    st.header("会话记录")

    # 新建会话：仅清空当前状态，不写库（避免产生空会话），首条消息时才真正创建
    if st.button("新建会话"):
        st.session_state["session_id"] = None
        st.session_state["message"] = []
        st.session_state["confirm_delete"] = None
        st.rerun()

    st.divider()

    sessions = session_store.list_sessions()
    if not sessions:
        st.caption("暂无历史会话")

    for s in sessions:
        is_active = s["id"] == st.session_state["session_id"]   # 是否为当前会话
        label = s["title"] or f"会话 {s['id']}"
        col_load, col_del = st.columns([5, 1])  # 5:1 列宽比，加载按钮占5/6，删除按钮占1/6
        with col_load:  #with语句块，将代码块中的元素都添加到col_load列中
            # 加载历史会话：从库中读出整段对话覆盖当前状态，当前会话高亮
            if st.button(
                label,
                key=f"load_{s['id']}",
                type="primary" if is_active else "secondary",
            ):
                st.session_state["session_id"] = s["id"]
                st.session_state["message"] = session_store.load_messages(s["id"])
                st.session_state["confirm_delete"] = None
                st.rerun()
        with col_del:
            if st.button("删除", key=f"del_{s['id']}"):
                st.session_state["confirm_delete"] = s["id"]
                st.rerun()

    # 删除二次确认：Streamlit 无原生 confirm，用两步交互防误删
    if st.session_state["confirm_delete"] is not None:
        cid = st.session_state["confirm_delete"]    #cid为待删除会话的ID
        target = next((s for s in sessions if s["id"] == cid), None)    #next()函数返回迭代器的下一个元素，若迭代器为空则返回None，否则返回迭代器的下一个元素
        title = target["title"] if target else f"会话 {cid}"
        st.warning(f"确认删除会话「{title}」？删除后不可恢复。")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("确认删除"):
                session_store.delete_session(cid)
                # 若删的是当前会话，回到空白新会话
                if st.session_state["session_id"] == cid:
                    st.session_state["session_id"] = None
                    st.session_state["message"] = []
                st.session_state["confirm_delete"] = None
                st.rerun()
        with col_no:
            if st.button("取消"):
                st.session_state["confirm_delete"] = None
                st.rerun()

# ====================主区：渲染历史对话====================
for message in st.session_state["message"]:
    st.chat_message(message["role"]).write(message["content"])

# 用户输入提示词query
prompt = st.chat_input("请输入您的问题：")
if prompt:
    st.chat_message("user").write(prompt)
    st.session_state["message"].append({"role": "user", "content": prompt})

    # 首条消息时懒创建会话，标题取首条用户消息前 20 字
    if st.session_state["session_id"] is None:
        st.session_state["session_id"] = session_store.create_session(prompt[:20])

    # 调用智能客服系统，传入既往对话作为多轮上下文（不含刚追加的当前 prompt）
    history = st.session_state["message"][:-1]
    response_messages = []
    with st.spinner("智能客服思考中..."):
        res_stream = st.session_state["agent"].execute_stream(prompt, history)

        # 迭代器——将流式输出的内容记录到缓存列表中
        def capture(generator, cache_list):
            for chunk in generator:
                cache_list.append(chunk)

                for char in chunk:
                    time.sleep(0.01)
                    yield char  # yield:返回当前迭代值，不阻塞后续代码执行，一个字符一个字符地返回

        st.chat_message("assistant").write_stream(
            capture(res_stream, response_messages)
        )
        st.session_state["message"].append(
            {"role": "assistant", "content": response_messages[-1]}
        )

    # 整段回答结束后一次性落库（一轮一个事务），并刷新会话活跃时间
    session_store.save_messages(
        st.session_state["session_id"], st.session_state["message"]
    )
    st.rerun()  # 重新运行当前页面，更新缓存列表
