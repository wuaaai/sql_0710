from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from ...agent.my_llm import trimmer

class EnforceStopMiddleware(AgentMiddleware):
    def __init__(self, max_iterations: int):
        self.max_iterations = max_iterations
        self.fallback_msg = "未找到与该问题完全匹配的内容，请重新优化问题后进行提问"

    async def awrap_model_call(self, request: ModelRequest, handler):
        # --- 1. 执行异步 Token 裁剪 (解决 BlockingError) ---
        # 使用 ainvoke 替代 invoke，并加上 await
        trimmed_messages = await trimmer.ainvoke(request.messages)
        
        # --- 2. 计算“当前这一轮提问”的迭代次数 ---
        all_history = request.state.get("messages", [])
        
        # 找到最后一条人类消息的索引，以此重置计数
        last_human_index = -1
        for i in range(len(all_history) - 1, -1, -1):
            if isinstance(all_history[i], HumanMessage):
                last_human_index = i
                break
        
        # 只统计最后一条 HumanMessage 之后的 AI 消息（即当前问题的工具调用次数）
        current_run_ai_msgs = [
            m for m in all_history[last_human_index:] 
            if isinstance(m, AIMessage) and m.tool_calls # 只有带工具调用的才算迭代
        ]
        current_iteration = len(current_run_ai_msgs)

        # --- 3. 判断是否达到迭代上限 ---
        if current_iteration >= self.max_iterations:
            print(f"DEBUG: 当前轮次已迭代 {current_iteration} 次，强制停止。")
            
            force_answer_instruction = SystemMessage(
                content=(
                    "【系统警告】已达到最大检索迭代次数限制，**禁止再次调用任何工具**！\n"
                    "请立即根据上述对话历史中**已检索到的信息**，回答用户的问题。\n"
                    f"如果信息不足或无关，请严格输出：'{self.fallback_msg}'"
                )
            )
            
            # 使用裁剪后的消息列表 + 强制回复指令
            new_messages = list(trimmed_messages) + [force_answer_instruction]
            
            new_request = request.override(
                tools=[], 
                messages=new_messages,
                tool_choice="none" 
            )
            return await handler(new_request)

        # --- 4. 正常执行 (使用裁剪后的消息) ---
        new_request = request.override(messages=trimmed_messages)
        return await handler(new_request)

    # 如果有同步方法 wrap_model_call，建议也统一逻辑（虽然 LangGraph 主要走异步）
    def wrap_model_call(self, request: ModelRequest, handler):
        # 同步环境下只能用 invoke，但 LangGraph 运行时通常会报错，建议优先走异步
        trimmed_messages = trimmer.invoke(request.messages)
        new_request = request.override(messages=trimmed_messages)
        return handler(new_request)