"""查询结果分析模块。

该模块先用 Python 对查询结果做一层结构化分析，
再把分析结论交给大模型润色成更自然的回答。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from llm_client import DeepSeekClient
from query_plan import QueryPlan


@dataclass
class AnalysisResult:
    """保存结果分析后的自然语言结论和结构化事实。"""

    summary: str
    facts: Dict[str, Any]


ANALYSIS_PROMPT = """
你是财政数据分析助手。请根据用户问题、QueryPlan、Python 计算结论、SQL 和查询结果，输出一段简洁、专业、易懂的回答。
要求：
1. 先直接回答核心结论
2. 提到关键指标名、科目名、表名
3. 如果结果为空，要明确说明未查询到数据
4. 不要编造数据
5. 优先参考已经给出的 Python 计算结论
"""


class ResultAnalyzer:
    """对 SQL 结果做摘要分析。"""

    def __init__(self, client: DeepSeekClient):
        """保存大模型客户端。"""
        self._client = client

    def analyze(
        self,
        question: str,
        table_zh: str,
        plan: QueryPlan,
        sql: str,
        rows: List[Dict[str, Any]],
    ) -> AnalysisResult:
        """生成结构化 facts 和最终回答摘要。"""
        facts = self._build_facts(plan, rows)
        summary = self._build_python_summary(plan, rows, facts)
        summary = self._llm_rewrite(question, table_zh, plan, sql, rows, summary)
        return AnalysisResult(summary=summary, facts=facts)

    def _llm_rewrite(
        self,
        question: str,
        table_zh: str,
        plan: QueryPlan,
        sql: str,
        rows: List[Dict[str, Any]],
        python_summary: str,
    ) -> str:
        """用大模型把 Python 结论改写成更自然的说明。"""
        if not rows:
            return python_summary

        try:
            prompt = (
                f"用户问题：{question}\n"
                f"表名：{table_zh}\n"
                f"QueryPlan：{json.dumps(plan.to_dict(), ensure_ascii=False)}\n"
                f"Python结论：{python_summary}\n"
                f"SQL：{sql}\n"
                f"结果：{json.dumps(rows, ensure_ascii=False)}"
            )
            return self._client.chat(ANALYSIS_PROMPT, prompt, temperature=0.3).strip()
        except Exception:
            return python_summary

    def _build_facts(self, plan: QueryPlan, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """从查询结果中提取结构化事实，供后续总结使用。"""
        facts: Dict[str, Any] = {
            "row_count": len(rows),
            "subjects": plan.subjects,
            "metrics": plan.metrics,
            "compare_operator": plan.compare_operator,
        }
        if not rows:
            return facts

        if plan.compare_dimension == "subject":
            subject_key = _pick_subject_key(rows[0])
            metric_keys = _pick_metric_keys(rows[0])
            comparisons = []
            for row in rows:
                subject_name = str(row.get(subject_key, "")) if subject_key else ""
                metric_values = {key: _to_float(row.get(key)) for key in metric_keys}
                comparisons.append({"subject": subject_name, "metrics": metric_values})
            facts["subject_comparisons"] = comparisons

            if metric_keys and len(comparisons) >= 2:
                metric_key = metric_keys[0]
                sorted_rows = sorted(comparisons, key=lambda item: item["metrics"].get(metric_key, 0), reverse=True)
                facts["largest_subject"] = sorted_rows[0]["subject"]
                facts["largest_value"] = sorted_rows[0]["metrics"].get(metric_key, 0)
                facts["smallest_subject"] = sorted_rows[-1]["subject"]
                facts["smallest_value"] = sorted_rows[-1]["metrics"].get(metric_key, 0)
                if len(sorted_rows) >= 2:
                    facts["value_diff"] = sorted_rows[0]["metrics"].get(metric_key, 0) - sorted_rows[1]["metrics"].get(metric_key, 0)

        return facts

    def _build_python_summary(self, plan: QueryPlan, rows: List[Dict[str, Any]], facts: Dict[str, Any]) -> str:
        """在不依赖大模型的情况下生成一版稳定的兜底摘要。"""
        if not rows:
            return "未查询到数据。"

        if plan.compare_dimension == "subject" and facts.get("subject_comparisons"):
            return _build_subject_summary(plan, facts)

        if len(rows) == 1:
            row_text = "，".join(f"{key}={value}" for key, value in rows[0].items())
            metric_text = "、".join(plan.metrics) if plan.metrics else "指标"
            subject_text = "、".join(plan.subjects) if plan.subjects else "当前科目"
            return f"{subject_text}的{metric_text}查询结果为：{row_text}。"

        metric_text = "、".join(plan.metrics) if plan.metrics else "指标"
        return f"本次查询返回 {len(rows)} 条记录，关键指标为：{metric_text}。"


def _build_subject_summary(plan: QueryPlan, facts: Dict[str, Any]) -> str:
    """生成科目对比类问题的摘要说明。"""
    comparisons = facts.get("subject_comparisons", [])
    if not comparisons:
        return "未查询到可比较的数据。"

    metric_name = plan.metrics[0] if plan.metrics else "指标"
    if plan.compare_operator == "larger":
        return (
            f"按{metric_name}比较，{facts.get('largest_subject', '')}更大，"
            f"数值为 {facts.get('largest_value', 0):g}；"
            f"与下一项相差 {facts.get('value_diff', 0):g}。"
        )
    if plan.compare_operator == "smaller":
        return (
            f"按{metric_name}比较，{facts.get('smallest_subject', '')}更小，"
            f"数值为 {facts.get('smallest_value', 0):g}。"
        )
    if plan.compare_operator == "diff":
        return (
            f"按{metric_name}比较，{facts.get('largest_subject', '')}与{facts.get('smallest_subject', '')}"
            f"相差 {abs(float(facts.get('largest_value', 0)) - float(facts.get('smallest_value', 0))):g}。"
        )

    details = []
    for item in comparisons:
        subject_name = item.get("subject", "")
        metric_values = item.get("metrics", {})
        values_text = "，".join(f"{key}={value:g}" for key, value in metric_values.items())
        details.append(f"{subject_name}：{values_text}")
    return "；".join(details) + "。"


def _pick_subject_key(first_row: Dict[str, Any]) -> str:
    """从结果字段中找出科目名称列。"""
    for key in ["XM_NAME", "KM_NAME", "SUBJECT_NAME", "DIM_NAME"]:
        if key in first_row:
            return key
    return ""


def _pick_metric_keys(first_row: Dict[str, Any]) -> List[str]:
    """从结果字段中找出指标列。"""
    ignored_keys = {"YEAR_MONTH", "RG_NAME", "XM_NAME", "KM_NAME", "SUBJECT_NAME", "DIM_NAME"}
    return [key for key in first_row.keys() if key not in ignored_keys]


def _to_float(value: Any) -> float:
    """把结果值安全转换为浮点数。"""
    try:
        return float(value or 0)
    except Exception:
        return 0.0
