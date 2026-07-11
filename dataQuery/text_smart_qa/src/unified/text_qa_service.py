from __future__ import annotations

from typing import List, Optional

from langchain_core.messages import HumanMessage

from text_smart_qa.src.agent.my_agent1 import agent
from text_smart_qa.src.unified.models import TextQaResult


class TextQaService:
    """复用原有智能问答 Agent。"""

    async def answer(
        self,
        messages: List,
        thread_id: str,
        region_code: Optional[str] = None,
        question_override: Optional[str] = None,
    ) -> TextQaResult:
        final_messages = self._replace_last_user_question(messages, question_override)
        inputs = {"messages": final_messages}
        config = {"configurable": {"thread_id": thread_id, "region_code": region_code}}
        result = await agent.ainvoke(inputs, config=config)
        all_messages = result.get("messages", [])
        answer = all_messages[-1].content if all_messages else "未生成回答。"
        return TextQaResult(answer=str(answer), raw_output=result)

    @staticmethod
    def _replace_last_user_question(messages: List, question_override: Optional[str]) -> List:
        if not question_override:
            return list(messages)

        new_messages = list(messages)
        for index in range(len(new_messages) - 1, -1, -1):
            if isinstance(new_messages[index], HumanMessage):
                new_messages[index] = HumanMessage(content=question_override)
                break
        return new_messages

