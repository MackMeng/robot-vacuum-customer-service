#========================智能客服系统========================
"""
1个ReactAgent类：
    1个方法：execute_stream 执行流式输出
"""


from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompt
from agent.tools.agent_tools import rag_summarize,get_weather,get_city_name,get_user_id,get_current_month,fetch_external_data,fill_context_for_report
from agent.tools.middleware import monitor_tool,log_before_model,report_prompt_switch

class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompt(),
            tools=[rag_summarize,get_weather,get_city_name,get_user_id,
                   get_current_month,fetch_external_data,fill_context_for_report],
            middleware=[monitor_tool,log_before_model,report_prompt_switch],
        )

    # 执行流式输出
    def execute_stream(self,query: str):
        input_dict={
            "messages":[
                {"role":"user","content":query}
            ]
        }
        #第三个参数context，用于传递上下文Runtime中的信息，用来传递是否需要根据场景切换提示词的信息
        #stream_mode="values"，返回模型的输出值，而不是中间状态
        chunks = self.agent.stream(input_dict,stream_mode="values",context={"report":False})
        for chunk in chunks:
            latest_message=chunk["messages"][-1]
            if latest_message.content:
                yield latest_message.content.strip()+"\n"


if __name__ == "__main__":
    agent=ReactAgent()
    for chunk in agent.execute_stream("扫地机器人在我所在的地区的气温下该如何保养"):
        print(chunk,end="",flush=True)      #flush=True，确保每个字符都立即打印
