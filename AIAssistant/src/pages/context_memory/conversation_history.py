"""历史会话管理能力。

完整复用自 dataQuery/text_smart_qa/src/agent/utils/memory_manager.py
提供：token 截断、轮次保留、user-assistant 配对、消息格式转换。
"""

import copy
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

# 默认配置（与老项目 env_utils 对齐）
MEMORY_TOKEN_LIMIT = 8000
MAX_USER_MESSAGES = 20
TOKENIZER_MODEL_NAME = "gpt-4"


# ============================================================
# Token 计算
# ============================================================

def get_tokenizer():
    try:
        import tiktoken

        return tiktoken.encoding_for_model(TOKENIZER_MODEL_NAME)
    except Exception:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(str(text)))


# ============================================================
# 消息截断
# ============================================================

def preserve_user_assistant_pairs(messages: list) -> tuple:
    """保留 user-assistant 配对，旧 assistant 截断为"已回答完毕"。"""
    if not messages:
        return [], ""

    user_positions = []
    assistant_groups = {}
    current_user_idx = None
    for i, msg in enumerate(messages):
        if msg.get("role") == "user":
            current_user_idx = i
            user_positions.append(i)
            assistant_groups[i] = []
        elif msg.get("role") == "assistant" and current_user_idx is not None:
            assistant_groups[current_user_idx].append(i)

    result = [messages[0]] if messages and messages[0].get("role") != "user" else []
    last_user_message = ""

    for n, w in enumerate(user_positions):
        if n + 1 == len(user_positions):
            result.extend(messages[w:])
            last_user_message = messages[w].get("content", "")
            break
        else:
            messages[w]["content"] = "历史提问：" + messages[w]["content"]
            result.append(messages[w])
            if w in assistant_groups and assistant_groups[w]:
                mm = messages[assistant_groups[w][-1]]
                mm["content"] = "已回答完毕"
                result.append(mm)
    return result, last_user_message


def get_last_n_rounds(messages: list, n: int) -> list:
    user_indices = [i for i, msg in enumerate(messages) if msg.get("role") == "user"]
    if len(user_indices) <= n:
        return messages[:]
    start_idx = user_indices[-n]
    if messages[0].get("role") != "user":
        return [messages[0]] + messages[start_idx:]
    return messages[start_idx:]


def handle_tool_messages(messages: list) -> list:
    """截断 tool 消息，只保留最后一个完整内容。"""
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
                except Exception:
                    new_msg["content"] = ""
                result_messages.append(new_msg)
        else:
            result_messages.append(msg)
    return result_messages


def filter_recent_user_messages(
    messages: list,
    token_limit: int = MEMORY_TOKEN_LIMIT,
    max_user_messages: int = MAX_USER_MESSAGES,
) -> tuple:
    """主过滤函数：结合 token 限制、轮次限制、tool 消息处理。"""
    user_messages = [msg.get("content", "") for msg in messages if msg.get("role") == "user"]
    user_message_count = len(user_messages)
    total_tokens = sum(count_tokens(msg.get("content", "")) for msg in messages)

    if user_message_count <= 1:
        if total_tokens <= token_limit:
            return total_tokens, messages, user_messages[-1] if user_messages else ""
        filtered = handle_tool_messages(messages)
        new_tokens = sum(count_tokens(msg.get("content", "")) for msg in filtered)
        return new_tokens, filtered, user_messages[-1] if user_messages else ""

    if user_message_count <= max_user_messages:
        preserved, last_msg = preserve_user_assistant_pairs(messages)
        preserved_tokens = sum(count_tokens(msg.get("content", "")) for msg in preserved)
        if preserved_tokens <= token_limit:
            return preserved_tokens, preserved, last_msg
        filtered = handle_tool_messages(preserved)
        final_tokens = sum(count_tokens(msg.get("content", "")) for msg in filtered)
        return final_tokens, filtered, last_msg

    last_n = get_last_n_rounds(messages, max_user_messages)
    preserved, last_msg = preserve_user_assistant_pairs(last_n)
    preserved_tokens = sum(count_tokens(msg.get("content", "")) for msg in preserved)
    if preserved_tokens <= token_limit:
        return preserved_tokens, preserved, last_msg
    filtered = handle_tool_messages(preserved)
    final_tokens = sum(count_tokens(msg.get("content", "")) for msg in filtered)
    return final_tokens, filtered, last_msg


# ============================================================
# AgentMemoryManager — 会话记忆管理
# ============================================================

class AgentMemoryManager:
    """管理多会话历史记忆，含 token 截断与 LangChain 格式转换。"""

    def __init__(self, token_limit: int = MEMORY_TOKEN_LIMIT):
        self.session_memory: Dict[str, List[Dict[str, Any]]] = {}
        self.token_limit = token_limit

    @staticmethod
    def dict_to_langchain(msg_dict: dict):
        role = msg_dict.get("role")
        content = msg_dict.get("content", "")
        if role == "user":
            return HumanMessage(content=content)
        elif role == "assistant":
            return AIMessage(
                content=content, tool_calls=msg_dict.get("tool_calls", [])
            )
        elif role == "tool":
            return ToolMessage(
                content=content,
                tool_call_id=msg_dict.get("tool_call_id", ""),
                name=msg_dict.get("name", ""),
            )
        else:
            return SystemMessage(content=content)

    @staticmethod
    def langchain_to_dict(msg) -> dict:
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        elif isinstance(msg, ToolMessage):
            role = "tool"
        else:
            role = "system"

        msg_dict = {"role": role, "content": str(msg.content) if msg.content else ""}
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            msg_dict["tool_calls"] = msg.tool_calls
        if isinstance(msg, ToolMessage):
            msg_dict["tool_call_id"] = msg.tool_call_id
            msg_dict["name"] = msg.name
        return msg_dict

    def add_user_query_and_get_inputs(self, thread_id: str, query: str) -> List[Any]:
        if thread_id not in self.session_memory:
            self.session_memory[thread_id] = []

        self.session_memory[thread_id].append({"role": "user", "content": query})
        history_copy = copy.deepcopy(self.session_memory[thread_id])
        _, filtered_history, _ = filter_recent_user_messages(
            history_copy, self.token_limit
        )
        return [self.dict_to_langchain(m) for m in filtered_history]

    def save_agent_response(
        self, thread_id: str, all_returned_messages: List[Any], input_length: int
    ):
        new_messages = all_returned_messages[input_length:]
        for msg in new_messages:
            self.session_memory[thread_id].append(self.langchain_to_dict(msg))


# 全局实例（与老项目一致）
memory_manager = AgentMemoryManager()
