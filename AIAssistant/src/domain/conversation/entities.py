"""会话领域实体定义。"""


class UserRequest:
    """表示单次用户请求，负责承载原始输入和多模态信息。"""

    pass


class ConversationSession:
    """表示一次完整的用户对话会话，聚合多轮请求和回答。"""

    pass


class AssistantResponse:
    """表示系统对用户请求的回答，包含回答文本、引用来源和可信度。"""

    pass
