from __future__ import annotations


class ChitchatService:
    """处理闲聊和无关问题。"""

    @staticmethod
    def answer(question: str) -> str:
        if any(word in question for word in ["你好", "您好", "早上好", "晚上好"]):
            return "您好，我是财政智能助手。我可以帮您查询财政文档内容，也可以查询财政数据。"
        if "谢谢" in question:
            return "不客气。如果您要查财政政策解读、预算文件或财政数据，我可以继续帮您处理。"
        return "我主要支持两类问题：财政文档问答，以及财政数据查询。您可以直接告诉我想查的政策内容、预算解读，或者某个财政指标的数据。"

