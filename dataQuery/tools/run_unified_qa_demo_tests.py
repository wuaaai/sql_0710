from __future__ import annotations

import asyncio
import json
import sys
import types
from pathlib import Path
from typing import Any


WORKSPACE_DIR = Path(__file__).resolve().parents[1]
TEXT_QA_DIR = WORKSPACE_DIR / "text_smart_qa"
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))
if str(TEXT_QA_DIR) not in sys.path:
    sys.path.insert(0, str(TEXT_QA_DIR))


def _install_demo_stubs() -> None:
    """为本地演示脚本注入最小依赖，避免真实环境依赖不足。"""
    if "langchain_core.messages" not in sys.modules:
        langchain_core_module = types.ModuleType("langchain_core")
        messages_module = types.ModuleType("langchain_core.messages")

        class AIMessage:
            def __init__(self, content: str = ""):
                self.content = content

        class HumanMessage:
            def __init__(self, content: str = ""):
                self.content = content

        messages_module.AIMessage = AIMessage
        messages_module.HumanMessage = HumanMessage
        langchain_core_module.messages = messages_module
        sys.modules["langchain_core"] = langchain_core_module
        sys.modules["langchain_core.messages"] = messages_module

    if "text_smart_qa.src.agent.my_llm" not in sys.modules:
        my_llm_module = types.ModuleType("text_smart_qa.src.agent.my_llm")

        class DemoLlm:
            def invoke(self, messages: list[dict]) -> Any:
                return types.SimpleNamespace(
                    content=json.dumps(
                        {
                            "route": "text_qa",
                            "confidence": 0.6,
                            "reason": "demo llm fallback",
                            "text_question": "",
                            "data_question": "",
                        },
                        ensure_ascii=False,
                    )
                )

        my_llm_module.llm = DemoLlm()
        sys.modules["text_smart_qa.src.agent.my_llm"] = my_llm_module

    if "text_smart_qa.src.agent.utils.log_utils" not in sys.modules:
        log_utils_module = types.ModuleType("text_smart_qa.src.agent.utils.log_utils")

        class DemoLog:
            def info(self, *args, **kwargs):
                pass

            def warning(self, *args, **kwargs):
                pass

            def error(self, *args, **kwargs):
                pass

        log_utils_module.log = DemoLog()
        sys.modules["text_smart_qa.src.agent.utils.log_utils"] = log_utils_module

    if "text_smart_qa.src.unified.text_qa_service" not in sys.modules:
        text_qa_service_module = types.ModuleType("text_smart_qa.src.unified.text_qa_service")

        class TextQaService:
            async def answer(self, messages, thread_id, region_code=None, question_override=None):
                question = question_override or _pick_last_user_question(messages)
                from text_smart_qa.src.unified.models import TextQaResult

                return TextQaResult(
                    answer=(
                        f"【模拟智能问答】已根据财政文档知识库回答：{question}\n"
                        "这里返回的是演示数据，用于验证主意图、子意图和补槽位流程。"
                    ),
                    raw_output={"thread_id": thread_id, "region_code": region_code},
                )

        text_qa_service_module.TextQaService = TextQaService
        sys.modules["text_smart_qa.src.unified.text_qa_service"] = text_qa_service_module

    if "text_smart_qa.src.unified.fiscal_sql_service" not in sys.modules:
        fiscal_sql_service_module = types.ModuleType("text_smart_qa.src.unified.fiscal_sql_service")

        class FiscalSqlService:
            async def answer(self, question: str):
                from text_smart_qa.src.unified.models import FiscalQaResult

                answer = (
                    "【模拟智能问数】已完成财政数据查询。\n"
                    "业务域：预算执行\n"
                    "表名：RDYS_LD_YSZX_YBGGYS_SBJZCWCQK\n"
                    "科目：卫生健康支出\n"
                    "指标：执行金额\n"
                    "地区层级：省本级\n"
                    "收支方向：支出\n"
                    "时间范围：2025年全年"
                )
                return FiscalQaResult(
                    answer=answer,
                    sql='SELECT "YEAR_MONTH", "BYS_JE" FROM demo_table WHERE "YEAR_MONTH" BETWEEN \'202501\' AND \'202512\'',
                    rows=[
                        {"YEAR_MONTH": "202501", "BYS_JE": 8437.0},
                        {"YEAR_MONTH": "202502", "BYS_JE": 15802.0},
                        {"YEAR_MONTH": "202503", "BYS_JE": 23222.0},
                    ],
                    chart={
                        "can_plot": True,
                        "type": "line",
                        "title": "卫生健康支出执行金额",
                        "labels": ["202501", "202502", "202503"],
                        "series": [{"name": "执行金额", "values": [8437.0, 15802.0, 23222.0]}],
                    },
                    facts={"row_count": 3, "subjects": ["卫生健康支出"], "metrics": ["执行金额"]},
                    summary={"answer_text": answer},
                    success=True,
                    error="",
                    slot_status="ready",
                    slot_values={
                        "subject": "卫生健康支出",
                        "metric": "执行金额",
                        "flow_direction": "支出",
                        "region_level": "省本级",
                    },
                )

        fiscal_sql_service_module.FiscalSqlService = FiscalSqlService
        sys.modules["text_smart_qa.src.unified.fiscal_sql_service"] = fiscal_sql_service_module


class DemoHumanMessage:
    """最小化的人类消息对象。"""

    def __init__(self, content: str):
        self.content = content


def _pick_last_user_question(messages: list) -> str:
    for item in reversed(messages):
        if hasattr(item, "content"):
            return str(item.content)
    return ""


_install_demo_stubs()

from text_smart_qa.src.unified.unified_qa_service import UnifiedQaService  # noqa: E402


async def _run_one_case(service: UnifiedQaService, case_name: str, question: str) -> dict[str, Any]:
    raw_history = [{"role": "user", "content": question}]
    lc_messages = [DemoHumanMessage(content=question)]
    result = await service.answer(
        raw_history_dicts=raw_history,
        langchain_messages=lc_messages,
        thread_id=f"demo-{case_name}",
        region_code="130000",
    )

    fiscal_payload = None
    if result.fiscal_result is not None:
        fiscal_payload = {
            "success": result.fiscal_result.success,
            "need_clarify": result.fiscal_result.need_clarify,
            "slot_status": result.fiscal_result.slot_status,
            "missing_slots": result.fiscal_result.missing_slots,
            "slot_values": result.fiscal_result.slot_values,
            "sql": result.fiscal_result.sql,
        }

    return {
        "case_name": case_name,
        "question": question,
        "route": result.route,
        "reason": result.decision.reason,
        "slot_status": result.decision.slot_status,
        "missing_slots": result.decision.missing_slots,
        "slot_values": result.decision.slot_values,
        "answer": result.answer,
        "fiscal_result": fiscal_payload,
        "sub_tasks": result.extra.get("sub_tasks", []),
    }


async def main() -> None:
    service = UnifiedQaService()
    test_cases = [
        (
            "normal_fiscal",
            "预算执行业务域中，查询2025年全年省本级卫生健康支出的每月执行金额各是多少",
        ),
        (
            "missing_subject",
            "预算执行业务域中，查询2025年全年省本级支出的每月执行金额各是多少",
        ),
        (
            "missing_metric",
            "预算执行业务域中，查询2025年全年省本级卫生健康支出情况",
        ),
        (
            "hybrid",
            "2019年全省一般公共预算收入总计多少，由哪几部分构成",
        ),
        (
            "pure_text_qa",
            "一般公共预算收入总计由哪几部分构成",
        ),
    ]

    results = []
    for case_name, question in test_cases:
        results.append(await _run_one_case(service, case_name, question))

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
