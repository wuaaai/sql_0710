"""旧版结果分析模块。

该模块仍被部分旧流程使用，作用是对查询结果生成一段自然语言说明。
与 `result_analyzer.py` 相比，这里保持了更轻量的接口形式。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from llm_client import DeepSeekClient


ANALYSIS_PROMPT = """
你是财政数据分析助手。请根据用户问题、选中的表、Python 计算结论、SQL 和查询结果，输出一段简洁、专业、易懂的回答。
要求：
1. 先直接回答核心结论
2. 提到关键指标名、科目名、表名
3. 如果结果为空，要明确说明未查询到数据
4. 不要编造数据
5. 优先参考已经给出的 Python 计算结论
"""


def build_analysis(
    client: DeepSeekClient,
    question: str,
    table_zh: str,
    subject_names: List[str],
    metric_names: List[str],
    sql: str,
    rows: List[Dict[str, Any]],
) -> str:
    """基于查询结果生成最终回答。"""
    if not rows:
        return f"未在表《{table_zh}》中查询到与“{question}”相关的数据。"

    metric_text = "、".join(metric_names) if metric_names else "指标"
    subject_text = "、".join(subject_names) if subject_names else "未限定科目"
    python_summary = build_python_summary(question, rows, subject_names, metric_names)

    try:
        prompt = (
            f"用户问题：{question}\n"
            f"表名：{table_zh}\n"
            f"科目：{subject_text}\n"
            f"指标：{metric_text}\n"
            f"Python结论：{python_summary}\n"
            f"SQL：{sql}\n"
            f"结果：{json.dumps(rows, ensure_ascii=False)}"
        )
        return client.chat(ANALYSIS_PROMPT, prompt, temperature=0.3).strip()
    except Exception:
        return python_summary


def build_python_summary(
    question: str,
    rows: List[Dict[str, Any]],
    subject_names: List[str],
    metric_names: List[str],
) -> str:
    """生成不依赖大模型的兜底摘要。"""
    if not rows:
        return "未查询到数据。"

    if _is_subject_comparison(question, rows):
        compare_text = _build_subject_comparison_text(rows, metric_names)
        if compare_text:
            return compare_text

    first_row = rows[0]
    row_text = "，".join(f"{key}={value}" for key, value in first_row.items())
    metric_text = "、".join(metric_names) if metric_names else "指标"
    subject_text = "、".join(subject_names) if subject_names else "当前科目"
    return f"{subject_text}的{metric_text}查询结果为：{row_text}。"


def _is_subject_comparison(question: str, rows: List[Dict[str, Any]]) -> bool:
    """判断当前结果是否像是科目对比问题。"""
    if len(rows) < 2:
        return False
    if "XM_NAME" in rows[0]:
        return True
    compare_keywords = ["哪个大", "谁大", "相差多少", "对比", "比较"]
    return any(keyword in question for keyword in compare_keywords)


def _build_subject_comparison_text(rows: List[Dict[str, Any]], metric_names: List[str]) -> str:
    """为科目对比类查询生成摘要。"""
    if not rows:
        return ""

    subject_key = _pick_subject_key(rows[0])
    metric_keys = _pick_metric_keys(rows[0])
    if not subject_key or not metric_keys:
        return ""

    metric_key = metric_keys[0]
    comparable_rows = []
    for row in rows:
        subject_name = str(row.get(subject_key, ""))
        metric_value = _to_float(row.get(metric_key))
        if not subject_name:
            continue
        comparable_rows.append((subject_name, metric_value))

    if len(comparable_rows) < 2:
        return ""

    comparable_rows.sort(key=lambda item: item[1], reverse=True)
    largest_name, largest_value = comparable_rows[0]
    second_name, second_value = comparable_rows[1]
    diff_value = largest_value - second_value
    metric_text = metric_names[0] if metric_names else metric_key

    details_text = "；".join(f"{name}={value:g}" for name, value in comparable_rows)
    return (
        f"按{metric_text}比较，{largest_name}更大，数值为 {largest_value:g}；"
        f"{second_name}为 {second_value:g}；两者相差 {diff_value:g}。明细如下：{details_text}。"
    )


def _pick_subject_key(first_row: Dict[str, Any]) -> str:
    """从结果字段中识别科目名称列。"""
    for key in ["XM_NAME", "KM_NAME", "SUBJECT_NAME", "DIM_NAME"]:
        if key in first_row:
            return key
    return ""


def _pick_metric_keys(first_row: Dict[str, Any]) -> List[str]:
    """从结果字段中识别指标列。"""
    ignored_keys = {"YEAR_MONTH", "RG_NAME", "XM_NAME", "KM_NAME", "SUBJECT_NAME", "DIM_NAME"}
    return [key for key in first_row.keys() if key not in ignored_keys]


def _to_float(value: Any) -> float:
    """把任意结果值安全转换成数字。"""
    try:
        return float(value or 0)
    except Exception:
        return 0.0
