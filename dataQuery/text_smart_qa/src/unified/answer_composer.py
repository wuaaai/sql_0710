from __future__ import annotations

from text_smart_qa.src.unified.models import FiscalQaResult, TextQaResult


class AnswerComposer:
    """把不同能力的结果整理成统一口径。"""

    @staticmethod
    def compose_text_answer(result: TextQaResult) -> str:
        return result.answer

    @staticmethod
    def compose_fiscal_answer(result: FiscalQaResult) -> str:
        answer = result.answer.strip() if result.answer else ""
        if result.need_clarify:
            return answer or "这个财政数据查询还缺少关键条件。"
        if not result.success:
            return answer or "智能问数暂时不可用。"
        return answer or "已完成财政数据查询。"

    @staticmethod
    def compose_hybrid_answer(text_result: TextQaResult | None, fiscal_result: FiscalQaResult | None) -> str:
        parts = []

        if fiscal_result and fiscal_result.answer:
            parts.append("先给出财政数据相关结果：\n" + fiscal_result.answer.strip())

        if text_result and text_result.answer:
            parts.append("再补充相关财政文档解释：\n" + text_result.answer.strip())

        if fiscal_result and fiscal_result.need_clarify and text_result:
            parts.append("说明：数据查询部分还缺少关键条件，我先给出了文档解释和补槽位提示。")
        elif fiscal_result and fiscal_result.need_clarify:
            parts.append("说明：这个问题更像财政数据查询，但当前还需要补充关键条件。")
        elif fiscal_result and fiscal_result.success and text_result:
            parts.append("说明：数据结果来自财政数据库，解释内容来自财政文档知识库。")
        elif fiscal_result and fiscal_result.success:
            parts.append("说明：本次已完成财政数据查询，未补充文档解释内容。")
        elif text_result:
            parts.append("说明：本次已完成财政文档解释，但智能问数模块当前不可用。")

        return "\n\n".join(part for part in parts if part)
