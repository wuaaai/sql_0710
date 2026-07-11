import tiktoken
import copy
from typing import List, Dict, Any, Tuple
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from src import env_utils

def get_tokenizer():
    try:
        return tiktoken.encoding_for_model(env_utils.TOKENIZER_MODEL)
    except:
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(str(text)))

def preserve_user_assistant_pairs(messages: list) -> tuple:
    if not messages:
        return [], ""
    user_positions = []
    assistant_groups = {}
    last_user_message = ""
    current_user_idx = None
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            current_user_idx = i
            user_positions.append(i)
            assistant_groups[i] = []
        elif msg.get("role") == "assistant" and current_user_idx is not None:
            assistant_groups[current_user_idx].append(i)

    result = [messages[0]] if messages and messages[0].get("role") != "user" else []
    
    for n, w in enumerate(user_positions):
        if n + 1 == len(user_positions):
            result.extend(messages[w:])
            last_user_message = messages[w].get('content', '')
            break
        else:
            messages[w]['content'] = "历史提问：" + messages[w]['content']
            result.append(messages[w])
            if w in assistant_groups and assistant_groups[w]:
                mm = messages[assistant_groups[w][-1]]
                mm['content'] = '已回答完毕'
                result.append(mm)
    return result, last_user_message

def get_last_n_rounds(messages: list, n: int) -> list:
    user_indices = [i for i, msg in enumerate(messages) if msg.get("role") == "user"]
    if len(user_indices) <= n:
        return messages[:]
    start_idx = user_indices[-n]
    return [messages[0]] + messages[start_idx:] if messages[0].get("role") != "user" else messages[start_idx:]

def handle_tool_messages(messages: list) -> list:
    last_tool_indices = [i for i, msg in enumerate(messages) if msg.get("role") == "tool"]
    last_tool_idx = last_tool_indices[-1] if last_tool_indices else -1
    result_messages = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "tool":
            if i == last_tool_idx:
                result_messages.append(msg)
            else:
                content = msg.get("content", "")
                new_msg = msg.copy()
                try:
                    truncated_content = content.split("文档名：")[1]
                    new_msg["content"] = "文档名：" + truncated_content
                except:
                    new_msg["content"] = ""
                result_messages.append(new_msg)
        else:
            result_messages.append(msg)
    return result_messages

def filter_recent_user_messages(messages: list, token_limit: int, max_user_messages: int = None) -> tuple:
    if max_user_messages is None:
        max_user_messages = env_utils.MAX_USER_MESSAGES
    total_tokens = sum(count_tokens(msg.get('content', '')) for msg in messages)
    user_messages = [msg.get("content", "") for msg in messages if msg.get("role") == "user"]
    user_message_count = len(user_messages)

    if user_message_count <= 1:
        if total_tokens <= token_limit:
            return total_tokens, messages, user_messages[-1] if user_messages else ""
        else:
            filtered_messages = handle_tool_messages(messages)
            new_total_tokens = sum(count_tokens(msg.get('content', '')) for msg in filtered_messages)
            return new_total_tokens, filtered_messages, user_messages[-1] if user_messages else ""
    else:
        if user_message_count <= max_user_messages:
            preserved_messages, last_user_message = preserve_user_assistant_pairs(messages)
            preserved_tokens = sum(count_tokens(msg.get('content', '')) for msg in preserved_messages)
            if preserved_tokens <= token_limit:
                return preserved_tokens, preserved_messages, last_user_message
            else:
                filtered_preserved = handle_tool_messages(preserved_messages)
                final_tokens = sum(count_tokens(msg.get('content', '')) for msg in filtered_preserved)
                return final_tokens, filtered_preserved, last_user_message
        else:
            last_n_rounds_messages = get_last_n_rounds(messages, max_user_messages)
            preserved_messages, last_user_message = preserve_user_assistant_pairs(last_n_rounds_messages)
            preserved_tokens = sum(count_tokens(msg.get('content', '')) for msg in preserved_messages)
            if preserved_tokens <= token_limit:
                return preserved_tokens, preserved_messages, last_user_message
            else:
                filtered_final = handle_tool_messages(preserved_messages)
                final_tokens = sum(count_tokens(msg.get('content', '')) for msg in filtered_final)
                return final_tokens, filtered_final, last_user_message

#  消息格式转换与状态管理 
class AgentMemoryManager:
    def __init__(self, token_limit=None):
        if token_limit is None:
            token_limit = env_utils.MEMORY_TOKEN_LIMIT
        # 存储所有会话的历史记忆
        self.session_memory: Dict[str, List[Dict[str, Any]]] = {}
        self.token_limit = token_limit

    def dict_to_langchain(self, msg_dict: dict):
        """将字典转为 LangChain 消息体"""
        role = msg_dict.get("role")
        content = msg_dict.get("content", "")
        if role == "user": return HumanMessage(content=content)
        elif role == "assistant": return AIMessage(content=content, tool_calls=msg_dict.get("tool_calls", []))
        elif role == "tool": return ToolMessage(content=content, tool_call_id=msg_dict.get("tool_call_id", ""), name=msg_dict.get("name", ""))
        else: return SystemMessage(content=content)

    def langchain_to_dict(self, msg) -> dict:
        """将 LangChain 消息体转回字典"""
        if isinstance(msg, HumanMessage): role = "user"
        elif isinstance(msg, AIMessage): role = "assistant"
        elif isinstance(msg, ToolMessage): role = "tool"
        else: role = "system"
        
        msg_dict = {"role": role, "content": str(msg.content) if msg.content else ""}
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            msg_dict["tool_calls"] = msg.tool_calls
        if isinstance(msg, ToolMessage):
            msg_dict["tool_call_id"] = msg.tool_call_id
            msg_dict["name"] = msg.name
        return msg_dict

    def add_user_query_and_get_inputs(self, thread_id: str, query: str) -> List[Any]:
        """将新问题加入记忆，截断计算后返回给 LangChain 的输入格式"""
        if thread_id not in self.session_memory:
            self.session_memory[thread_id] = []
            
        # 记录用户的最新问题
        self.session_memory[thread_id].append({"role": "user", "content": query})
        
        # 深拷贝历史记录
        history_copy = copy.deepcopy(self.session_memory[thread_id])
        
        # 执行截断逻辑
        _, filtered_history, _ = filter_recent_user_messages(history_copy, self.token_limit)
        
        # 转为 LangChain 格式并返回
        return [self.dict_to_langchain(m) for m in filtered_history]

    def save_agent_response(self, thread_id: str, all_returned_messages: List[Any], input_length: int):
        new_messages = all_returned_messages[input_length:]
        for msg in new_messages:
            self.session_memory[thread_id].append(self.langchain_to_dict(msg))

memory_manager = AgentMemoryManager()