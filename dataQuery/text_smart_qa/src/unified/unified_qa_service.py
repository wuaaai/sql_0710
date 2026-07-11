from __future__ import annotations

import asyncio
from typing import List, Optional

from text_smart_qa.src.agent.utils.log_utils import log
from text_smart_qa.src.unified.answer_composer import AnswerComposer
from text_smart_qa.src.unified.chitchat_service import ChitchatService
from text_smart_qa.src.unified.fiscal_sql_service import FiscalSqlService
from text_smart_qa.src.unified.models import FiscalQaResult, IntentTask, TextQaResult, UnifiedAnswer
from text_smart_qa.src.unified.router_service import RouterService
from text_smart_qa.src.unified.text_qa_service import TextQaService


class UnifiedQaService:
    """统一调度智能问答、智能问数、混合回答和闲聊。"""

    def __init__(self):
        self._router = RouterService()
        self._text_service = TextQaService()
        self._fiscal_service = FiscalSqlService()
        self._chitchat_service = ChitchatService()

    async def answer(
        self,
        raw_history_dicts: List[dict],
        langchain_messages: List,
        thread_id: str,
        region_code: Optional[str] = None,
    ) -> UnifiedAnswer:
        current_question = self._get_current_question(raw_history_dicts)

        decision = self._router.route_by_rules(current_question)
        if decision is None:
            log.info("[UnifiedQaService] 简单规则未命中，改走大模型路由")
            decision = await self._router.route_question(current_question, raw_history_dicts)
        else:
            log.info(
                f"[UnifiedQaService] 简单规则已命中，route={decision.route}, "
                f"reason={decision.reason}"
            )

        if decision.route == "chitchat":
            return UnifiedAnswer(
                route="chitchat",
                answer=self._chitchat_service.answer(current_question),
                decision=decision,
                extra={"sub_tasks": self._serialize_sub_tasks(decision.sub_tasks)},
            )

        text_tasks = [task for task in decision.sub_tasks if task.route == "text_qa"]
        fiscal_tasks = [task for task in decision.sub_tasks if task.route == "fiscal_sql"]
        need_clarify = decision.slot_status == "clarify"

        if decision.route == "text_qa":
            text_question = self._pick_primary_question(text_tasks, decision.text_question or current_question)
            text_result = await self._text_service.answer(
                messages=langchain_messages,
                thread_id=thread_id,
                region_code=region_code,
                question_override=text_question,
            )
            return UnifiedAnswer(
                route="text_qa",
                answer=AnswerComposer.compose_text_answer(text_result),
                decision=decision,
                text_result=text_result,
                extra={"sub_tasks": self._serialize_sub_tasks(decision.sub_tasks)},
            )

        if decision.route == "fiscal_sql":
            if need_clarify:
                fiscal_result = self._build_clarify_fiscal_result(decision, current_question)
                return UnifiedAnswer(
                    route="fiscal_sql",
                    answer=AnswerComposer.compose_fiscal_answer(fiscal_result),
                    decision=decision,
                    fiscal_result=fiscal_result,
                    extra={
                        "missing_slots": list(decision.missing_slots),
                        "slot_values": dict(decision.slot_values),
                        "sub_tasks": self._serialize_sub_tasks(decision.sub_tasks),
                    },
                )

            fiscal_question = self._pick_primary_question(fiscal_tasks, decision.data_question or current_question)
            fiscal_result = await self._fiscal_service.answer(fiscal_question)
            return UnifiedAnswer(
                route="fiscal_sql",
                answer=AnswerComposer.compose_fiscal_answer(fiscal_result),
                decision=decision,
                fiscal_result=fiscal_result,
                extra={
                    "sql": fiscal_result.sql,
                    "chart": fiscal_result.chart,
                    "missing_slots": fiscal_result.missing_slots,
                    "slot_values": fiscal_result.slot_values,
                    "sub_tasks": self._serialize_sub_tasks(decision.sub_tasks),
                },
            )

        text_question = self._pick_primary_question(text_tasks, decision.text_question or current_question)
        if need_clarify:
            text_result = None
            if text_tasks:
                text_result = await self._text_service.answer(
                    messages=langchain_messages,
                    thread_id=thread_id,
                    region_code=region_code,
                    question_override=text_question,
                )
            fiscal_result = self._build_clarify_fiscal_result(decision, current_question)
        else:
            fiscal_question = self._pick_primary_question(fiscal_tasks, decision.data_question or current_question)
            text_result, fiscal_result = await self._run_hybrid(
                text_question=text_question,
                fiscal_question=fiscal_question,
                langchain_messages=langchain_messages,
                thread_id=thread_id,
                region_code=region_code,
            )

        return UnifiedAnswer(
            route="hybrid",
            answer=AnswerComposer.compose_hybrid_answer(text_result, fiscal_result),
            decision=decision,
            text_result=text_result,
            fiscal_result=fiscal_result,
            extra={
                "sql": fiscal_result.sql if fiscal_result else "",
                "chart": fiscal_result.chart if fiscal_result else {},
                "missing_slots": fiscal_result.missing_slots if fiscal_result else [],
                "slot_values": fiscal_result.slot_values if fiscal_result else {},
                "sub_tasks": self._serialize_sub_tasks(decision.sub_tasks),
            },
        )

    async def _run_hybrid(
        self,
        text_question: str,
        fiscal_question: str,
        langchain_messages: List,
        thread_id: str,
        region_code: Optional[str],
    ) -> tuple[TextQaResult | None, FiscalQaResult | None]:
        text_task = self._text_service.answer(
            messages=langchain_messages,
            thread_id=thread_id,
            region_code=region_code,
            question_override=text_question,
        )
        fiscal_task = self._fiscal_service.answer(fiscal_question)

        text_result, fiscal_result = await asyncio.gather(text_task, fiscal_task, return_exceptions=True)

        safe_text_result = None if isinstance(text_result, Exception) else text_result
        safe_fiscal_result = None if isinstance(fiscal_result, Exception) else fiscal_result

        if safe_text_result is None and safe_fiscal_result is None:
            raise RuntimeError("智能问答和智能问数都执行失败，无法生成混合回答。")

        return safe_text_result, safe_fiscal_result

    @staticmethod
    def _pick_primary_question(tasks: List[IntentTask], fallback_question: str) -> str:
        """从同类子任务里选一个主问题，当前先取第一个。"""
        if tasks:
            return tasks[0].question
        return fallback_question

    @staticmethod
    def _serialize_sub_tasks(tasks: List[IntentTask]) -> List[dict]:
        """把子任务对象转换成可序列化结构。"""
        return [
            {
                "route": task.route,
                "question": task.question,
                "reason": task.reason,
                "slot_status": task.slot_status,
                "missing_slots": list(task.missing_slots),
                "slot_values": dict(task.slot_values),
            }
            for task in tasks
        ]

    @staticmethod
    def _get_current_question(history_messages: List[dict]) -> str:
        for item in reversed(history_messages):
            if item.get("role") == "user":
                return str(item.get("content", "")).strip()
        return ""

    @staticmethod
    def _build_clarify_fiscal_result(decision, fallback_question: str) -> FiscalQaResult:
        """当问数槽位不完整时，构造一个结构化的补槽位结果。"""
        clarify_message = decision.clarify_message or "这个财政数据查询还缺少关键条件，请先补充后再查询。"
        return FiscalQaResult(
            answer=clarify_message,
            success=False,
            error="need_clarify",
            slot_status="clarify",
            missing_slots=list(decision.missing_slots),
            slot_values=dict(decision.slot_values),
            need_clarify=True,
            summary={
                "question": fallback_question,
                "answer_text": clarify_message,
                "missing_slots": list(decision.missing_slots),
                "slot_values": dict(decision.slot_values),
            },
        )


unified_qa_service = UnifiedQaService()
