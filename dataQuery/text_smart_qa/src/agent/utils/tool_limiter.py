import asyncio
from functools import wraps
from src import env_utils

class TurnCallLimiter:
    """
    基于单轮对话（Per-Turn）的工具调用次数限制器
    """
    def __init__(self, max_calls: int = 4, fallback_msg: str = "已达到单轮最大调用次数限制。"):
        self.max_calls = max_calls
        self.fallback_msg = fallback_msg
        # 记录格式: {"thread_id_1": 当前轮次调用数, "thread_id_2": 当前轮次调用数}
        self.turn_counts = {}

    def __call__(self, func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 获取 LangChain 注入的 config
            config = kwargs.get("config", {})
            
            # 提取 thread_id（会话 ID），用于区分不同用户
            session_id = "default_session"
            if isinstance(config, dict) and "configurable" in config:
                session_id = config["configurable"].get("thread_id", "default_session")
            elif hasattr(config, "get"):
                configurable = config.get("configurable", {})
                session_id = configurable.get("thread_id", "default_session")

            # 初始化当前用户本轮的计数器
            if session_id not in self.turn_counts:
                self.turn_counts[session_id] = 0

            # 检查当前用户本轮是否超过限制
            if self.turn_counts[session_id] >= self.max_calls:
                print(f"⚠️ 工具拦截: 会话 [{session_id}] 本轮调用已达上限 ({self.max_calls}次)")
                return self.fallback_msg
            
            # 增加计数
            self.turn_counts[session_id] += 1
            print(f"🔍 工具调用: 会话 [{session_id}] 本轮第 {self.turn_counts[session_id]}/{self.max_calls} 次检索")
            
            return await func(*args, **kwargs)
            
        return async_wrapper
        
    def reset_turn(self, session_id: str):
        """
        核心逻辑：在每次接收到用户的新问题时，调用此方法清零该用户的计数器
        """
        self.turn_counts[session_id] = 0
        print(f"🔄 状态重置: 已清空会话 [{session_id}] 的调用计数，开启新一轮问答。")

    def force_exhaust(self, session_id: str):
        """
        立即将指定会话的本轮调用次数设为上限，阻止后续重试。
        用于权限不足等场景，避免无效的重复调用。
        """
        self.turn_counts[session_id] = self.max_calls
        print(f"🛑 强制耗尽: 会话 [{session_id}] 本轮调用次数已被设为上限 ({self.max_calls})，阻止进一步调用。")

# 实例化一个全局对象，供工具和主程序共同使用
rag_limiter = TurnCallLimiter(
    max_calls=env_utils.RAG_MAX_CALLS,
    fallback_msg=(
        f"【强制终止】本轮知识库检索已达{env_utils.RAG_MAX_CALLS}次上限，该工具已被锁定。"
        "你必须立即基于已检索到的信息生成回答，绝对禁止再次调用此工具。"
        "如果已有信息不足以回答，直接告知用户'未找到相关内容，请优化问题后重试'。"
    )
)