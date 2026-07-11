"""单轮对话工具调用次数限制器。

完整复用自 dataQuery/text_smart_qa/src/agent/utils/tool_limiter.py

用于限制 RAG 知识库检索工具每轮对话的调用次数（默认4次）。
权限不足时立即耗尽配额，避免无效重试。
"""

from functools import wraps

# 每轮对话 RAG 工具最大调用次数（与老项目 env_utils.RAG_MAX_CALLS 对齐）
RAG_MAX_CALLS = 4


class TurnCallLimiter:
    """基于单轮对话（Per-Turn）的工具调用次数限制器。

    按 thread_id 区分会话，每个会话每轮最多调用 max_calls 次。
    """

    def __init__(self, max_calls: int = RAG_MAX_CALLS, fallback_msg: str = ""):
        self.max_calls = max_calls
        self.fallback_msg = fallback_msg or (
            f"【强制终止】本轮知识库检索已达{max_calls}次上限，该工具已被锁定。"
            "你必须立即基于已检索到的信息生成回答，绝对禁止再次调用此工具。"
            "如果已有信息不足以回答，直接告知用户'未找到相关内容，请优化问题后重试'。"
        )
        self.turn_counts = {}

    def __call__(self, func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            config = kwargs.get("config", {})

            session_id = "default_session"
            if isinstance(config, dict) and "configurable" in config:
                session_id = config["configurable"].get("thread_id", "default_session")
            elif hasattr(config, "get"):
                configurable = config.get("configurable", {})
                session_id = configurable.get("thread_id", "default_session")

            if session_id not in self.turn_counts:
                self.turn_counts[session_id] = 0

            if self.turn_counts[session_id] >= self.max_calls:
                print(f"工具拦截: 会话 [{session_id}] 本轮调用已达上限 ({self.max_calls}次)")
                return self.fallback_msg

            self.turn_counts[session_id] += 1
            print(
                f"工具调用: 会话 [{session_id}] 本轮第 "
                f"{self.turn_counts[session_id]}/{self.max_calls} 次检索"
            )

            return await func(*args, **kwargs)

        return async_wrapper

    def reset_turn(self, session_id: str):
        """收到用户新问题时调用，清零该会话的计数器。"""
        self.turn_counts[session_id] = 0
        print(f"状态重置: 已清空会话 [{session_id}] 的调用计数，开启新一轮问答。")

    def force_exhaust(self, session_id: str):
        """立即将本轮调用次数设为上限，阻止后续重试（权限不足等场景）。"""
        self.turn_counts[session_id] = self.max_calls
        print(
            f"强制耗尽: 会话 [{session_id}] 本轮调用次数已被设为上限 "
            f"({self.max_calls})，阻止进一步调用。"
        )


# 全局实例，供工具和主程序共同使用
rag_limiter = TurnCallLimiter(max_calls=RAG_MAX_CALLS)
