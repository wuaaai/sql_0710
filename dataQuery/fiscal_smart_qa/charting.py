"""图表配置生成模块。

根据查询结果和意图信息，生成前端可直接消费的图表配置结构。
这里只负责决定“能不能画、画什么图、数据怎么组织”。
"""

from __future__ import annotations

from typing import Any, Dict, List

from intent import UserIntent


def build_chart_config(intent: UserIntent, rows: List[Dict[str, Any]], metric_label: str) -> Dict[str, Any]:
    """为当前查询结果生成图表配置。"""
    if not rows:
        return {"can_plot": False}

    dimension_keys, metric_keys = _split_dimension_and_metric_keys(rows[0])
    if not metric_keys:
        return {"can_plot": False}
    if len(rows) == 1 and _is_single_value_result(rows[0], dimension_keys, metric_keys):
        return {"can_plot": False}

    if _can_pivot_subjects_by_time(rows):
        return _build_subject_time_grouped_bar(rows, metric_keys[0], metric_label)

    chart_type = _choose_chart_type(intent)
    primary_dimension = _pick_primary_dimension(dimension_keys, metric_keys)

    if chart_type == "pie":
        metric_key = metric_keys[0]
        return {
            "can_plot": True,
            "type": "pie",
            "title": metric_label,
            "labels": [str(row[primary_dimension]) for row in rows],
            "values": [float(row[metric_key] or 0) for row in rows],
        }

    if chart_type == "line":
        return {
            "can_plot": True,
            "type": "line",
            "title": metric_label,
            "labels": [str(row[primary_dimension]) for row in rows],
            "series": _build_metric_series(rows, metric_keys),
        }

    if chart_type == "bar_line":
        return {
            "can_plot": True,
            "type": "bar_line",
            "title": metric_label,
            "labels": [str(row[primary_dimension]) for row in rows],
            "series": _build_metric_series(rows, metric_keys),
        }

    if chart_type == "bar_horizontal":
        return {
            "can_plot": True,
            "type": "bar_horizontal",
            "title": metric_label,
            "labels": [str(row[primary_dimension]) for row in rows],
            "series": _build_metric_series(rows, metric_keys),
        }

    return {
        "can_plot": True,
        "type": "bar",
        "title": metric_label,
        "labels": [str(row[primary_dimension]) for row in rows],
        "series": _build_metric_series(rows, metric_keys),
    }


def _build_subject_time_grouped_bar(rows: List[Dict[str, Any]], metric_key: str, metric_label: str) -> Dict[str, Any]:
    """把“时间 + 科目”结果转换成分组柱状图结构。"""
    time_labels = sorted({str(row.get("YEAR_MONTH", "")) for row in rows if row.get("YEAR_MONTH") is not None})
    subject_names = sorted({str(row.get("XM_NAME", "")) for row in rows if row.get("XM_NAME")})

    value_map: Dict[tuple[str, str], float] = {}
    for row in rows:
        year_month = str(row.get("YEAR_MONTH", ""))
        subject_name = str(row.get("XM_NAME", ""))
        value_map[(year_month, subject_name)] = float(row.get(metric_key) or 0)

    series = []
    for subject_name in subject_names:
        series.append(
            {
                "name": subject_name,
                "values": [value_map.get((label, subject_name), 0.0) for label in time_labels],
            }
        )

    return {
        "can_plot": True,
        "type": "bar",
        "title": metric_label,
        "labels": time_labels,
        "series": series,
    }


def _build_metric_series(rows: List[Dict[str, Any]], metric_keys: List[str]) -> List[Dict[str, Any]]:
    """把结果行整理成图表所需的 series 数组。"""
    output: List[Dict[str, Any]] = []
    for metric_key in metric_keys:
        output.append(
            {
                "name": metric_key,
                "values": [float(row.get(metric_key) or 0) for row in rows],
            }
        )
    return output


def _choose_chart_type(intent: UserIntent) -> str:
    """根据用户意图和问题特征选择图表类型。"""
    if intent.chart_hint and intent.chart_hint != "auto":
        return _normalize_chart_hint(intent.chart_hint)

    question = intent.raw_question or ""
    metric = " ".join(intent.metrics) if intent.metrics else (intent.metric or "")

    if intent.query_type == "proportion":
        return "pie"
    if intent.query_type == "mixed" or _looks_like_mixed_chart(question):
        return "bar_line"
    if _looks_like_ranking(question):
        return "bar_horizontal"
    if intent.query_type == "comparison":
        return "bar"
    if _looks_like_rate_metric(question, metric):
        return "line"
    if _looks_like_cumulative_metric(question, metric):
        return "line"
    if _looks_like_monthly_detail(question, metric):
        return "bar"
    if intent.query_type == "trend":
        if _looks_like_explicit_trend(question):
            return "line"
        return "bar"
    return "bar"


def _split_dimension_and_metric_keys(first_row: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """把结果字段拆成维度列和指标列。"""
    dimension_candidates = {"YEAR_MONTH", "REGION_NAME", "DIM_NAME", "XM_NAME", "KM_NAME", "RG_NAME"}
    dimension_keys: List[str] = []
    metric_keys: List[str] = []
    for key in first_row.keys():
        if key in dimension_candidates:
            dimension_keys.append(key)
        else:
            metric_keys.append(key)

    if not dimension_keys and len(first_row.keys()) > 1:
        keys = list(first_row.keys())
        dimension_keys.append(keys[0])
        metric_keys = keys[1:]

    if not metric_keys and dimension_keys:
        metric_keys = [dimension_keys[-1]]

    return dimension_keys, metric_keys


def _pick_primary_dimension(dimension_keys: List[str], metric_keys: List[str]) -> str:
    """选择最适合作为横轴或标签的主维度。"""
    if "YEAR_MONTH" in dimension_keys:
        return "YEAR_MONTH"
    if dimension_keys:
        return dimension_keys[0]
    return metric_keys[0]


def _normalize_chart_hint(chart_hint: str) -> str:
    """把外部图表提示值归一成内部支持的类型。"""
    if chart_hint == "line":
        return "line"
    if chart_hint == "pie":
        return "pie"
    if chart_hint == "bar_line":
        return "bar_line"
    if chart_hint in {"bar_horizontal", "horizontal_bar"}:
        return "bar_horizontal"
    return "bar"


def _is_single_value_result(first_row: Dict[str, Any], dimension_keys: List[str], metric_keys: List[str]) -> bool:
    """判断结果是否只是一个单值，不适合绘图。"""
    if len(metric_keys) != 1:
        return False
    if not dimension_keys:
        return True
    if len(first_row.keys()) <= 2:
        return True
    return False


def _can_pivot_subjects_by_time(rows: List[Dict[str, Any]]) -> bool:
    """判断是否适合转换为按时间分组、按科目拆 series 的图表。"""
    if not rows:
        return False
    first_row = rows[0]
    return "YEAR_MONTH" in first_row and "XM_NAME" in first_row


def _looks_like_explicit_trend(question: str) -> bool:
    """判断问题是否明确在问趋势。"""
    trend_keywords = ["趋势", "变化", "走势", "波动", "变动"]
    return any(keyword in (question or "") for keyword in trend_keywords)


def _looks_like_monthly_detail(question: str, metric: str) -> bool:
    """判断是否更适合画月度明细柱状图。"""
    time_keywords = ["每月", "各月", "分月", "逐月", "月份"]
    detail_metric_keywords = ["本月", "当月", "执行金额", "支出", "收入", "金额"]
    text = f"{question} {metric}"
    return any(keyword in text for keyword in time_keywords) and any(
        keyword in text for keyword in detail_metric_keywords
    )


def _looks_like_cumulative_metric(question: str, metric: str) -> bool:
    """判断指标是否属于累计类。"""
    cumulative_keywords = ["累计", "累计完成", "截至", "累计金额", "累计执行"]
    text = f"{question} {metric}"
    return any(keyword in text for keyword in cumulative_keywords)


def _looks_like_rate_metric(question: str, metric: str) -> bool:
    """判断指标是否属于比例、增幅、执行率类。"""
    rate_keywords = ["同比", "环比", "增速", "增长率", "完成率", "执行率", "百分比", "比重"]
    text = f"{question} {metric}"
    return any(keyword in text for keyword in rate_keywords)


def _looks_like_ranking(question: str) -> bool:
    """判断问题是否带有明显的排名意图。"""
    ranking_keywords = ["排名", "前", "top", "TOP", "最多", "最高", "最低"]
    return any(keyword in (question or "") for keyword in ranking_keywords)


def _looks_like_mixed_chart(question: str) -> bool:
    """判断问题是否适合组合图。"""
    mixed_keywords = ["趋势和明细", "趋势及明细", "变化和明细", "走势和明细"]
    return any(keyword in (question or "") for keyword in mixed_keywords)
