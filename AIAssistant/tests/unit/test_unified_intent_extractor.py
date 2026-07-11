"""统一意图识别模块 — 联调测试。

对应设计文档 §4，用四个示例验证五种调度结果。
测试 extract() → dispatch() 的完整链路，使用真实 LLM（DeepSeek）。
LLM 配置复用 dataQuery 项目 .env 中的 API key。
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.pages.infrastructure.llm.llm_gateway import LlmConfig, LlmGateway
from src.pages.request_lifecycle.dispatch_execution import ConcurrentTaskDispatcher
from src.pages.request_lifecycle.unified_intent_extractor import UnifiedIntentExtractor


LLM_CONFIG = LlmConfig(
    api_key="sk-d507bd835e174d99b57757f3010dfd02",
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat",
    timeout_seconds=90,
)


@dataclass
class TestCase:
    """单个测试用例。"""
    name: str
    question: str
    expected_text2sql: bool
    expected_rag: bool
    expected_clarify: bool
    expected_fallback: bool


TEST_CASES = [
    TestCase(
        name="示例1：混合问题（查数 + 解释构成）",
        question="2019年全省一般公共预算收入总计多少，由哪几部分构成",
        expected_text2sql=True, expected_rag=True,
        expected_clarify=False, expected_fallback=False,
    ),
    TestCase(
        name="示例2：纯查数",
        question="2025年省本级卫生健康支出的执行金额是多少",
        expected_text2sql=True, expected_rag=False,
        expected_clarify=False, expected_fallback=False,
    ),
    TestCase(
        name="示例3：纯文档问答",
        question="一般公共预算收入的口径是什么",
        expected_text2sql=False, expected_rag=True,
        expected_clarify=False, expected_fallback=False,
    ),
    TestCase(
        name="示例4：槽位缺失（追问补槽位）",
        question="卫生健康支出执行情况",
        expected_text2sql=False, expected_rag=False,
        expected_clarify=True, expected_fallback=False,
    ),
    TestCase(
        name="示例5：闲聊兜底",
        question="你好，今天天气怎么样",
        expected_text2sql=False, expected_rag=False,
        expected_clarify=False, expected_fallback=True,
    ),
]


def run_tests():
    """执行全部测试用例。"""
    llm_client = LlmGateway(LLM_CONFIG)
    subject_keywords = [
        "税收收入", "非税收入", "卫生健康支出", "教育支出",
        "社会保障和就业支出", "一般公共预算收入",
    ]
    metric_aliases = {
        "预算执行率": ["预算执行率", "执行率", "预算完成率"],
        "本月金额": ["本月金额", "当月金额", "本月执行金额"],
        "累计金额": ["累计金额", "累计收入", "累计支出"],
        "同比增幅": ["同比增额", "同比增长率", "同比增长", "同比"],
        "环比增幅": ["环比增额", "环比增长率", "环比增长", "环比"],
        "预算数": ["预算数", "年初预算", "调整预算"],
        "金额": ["金额"],
    }

    extractor = UnifiedIntentExtractor(
        llm_client=llm_client,
        subject_keywords=subject_keywords,
        metric_aliases=metric_aliases,
    )
    dispatcher = ConcurrentTaskDispatcher()

    passed = 0
    failed = 0

    for case in TEST_CASES:
        print(f"\n{'=' * 60}")
        print(f"测试: {case.name}")
        print(f"问题: {case.question}")

        intent_dict = extractor.extract(case.question)
        plan = dispatcher.dispatch(intent_dict)

        errors = []
        if plan.text2sql != case.expected_text2sql:
            errors.append(f"  text2sql: 期望={case.expected_text2sql}, 实际={plan.text2sql}")
        if plan.rag != case.expected_rag:
            errors.append(f"  rag: 期望={case.expected_rag}, 实际={plan.rag}")
        if plan.clarify != case.expected_clarify:
            errors.append(f"  clarify: 期望={case.expected_clarify}, 实际={plan.clarify}")
        if plan.fallback != case.expected_fallback:
            errors.append(f"  fallback: 期望={case.expected_fallback}, 实际={plan.fallback}")

        if errors:
            print("[FAIL]")
            for err in errors:
                print(err)
            print(f"  实际 DispatchPlan: text2sql={plan.text2sql}, rag={plan.rag}, "
                  f"clarify={plan.clarify}, fallback={plan.fallback}")
            if plan.clarify:
                print(f"  补槽位文案: {plan.clarify_message[:100]}...")
            failed += 1
        else:
            print("[PASS]")
            result_desc = _describe_result(plan)
            print(f"  调度结果: {result_desc}")
            passed += 1

    print(f"\n{'=' * 60}")
    print(f"测试完成: {passed} 通过, {failed} 失败, 共 {len(TEST_CASES)} 个用例")
    return failed == 0


def _describe_result(plan) -> str:
    if plan.fallback:
        return "闲聊兜底"
    if plan.clarify:
        return f"追问补槽位（缺: {', '.join(plan.missing_slots)}）"
    if plan.text2sql and plan.rag:
        return "混合（Text2SQL + RAG 并行）"
    if plan.text2sql:
        return "纯 Text2SQL"
    if plan.rag:
        return "纯 RAG"
    return "未知"


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
