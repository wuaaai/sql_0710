"""QueryPlan 到 SQL 的编译模块。

这个版本使用新版 `ResolvedEntities` 结构，把已经解析好的表、科目、指标
编译成可直接执行的 SQL。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from entity_resolver import ResolvedEntities
from metadata import MetadataBundle


@dataclass
class CompiledQuery:
    """保存编译后的 SQL 及展示信息。"""

    sql: str
    metric_labels: List[str]
    chart_dimension: str


class QueryCompiler:
    """根据实体解析结果拼装查询 SQL。"""

    def __init__(self, metadata: MetadataBundle, schema_name: str = ""):
        """保存元数据和可选的 schema 名。"""
        self._metadata = metadata
        self._schema_name = (schema_name or "").strip()

    def compile(self, resolved: ResolvedEntities) -> CompiledQuery:
        """把解析结果编译为最终 SQL。"""
        plan = resolved.plan
        schema = self._metadata.get_table_schema(resolved.selected_table.table_en)
        fields = schema.get("fields", {})
        _, table_info = self._metadata.get_table_info_by_en(resolved.selected_table.table_en)

        time_col = _resolve_time_column(fields)
        region_name_col = _resolve_region_name_column(fields)
        subject_name_col = _resolve_subject_name_column(fields, table_info)
        subject_code_col = _resolve_subject_code_column(fields, table_info)

        metric_columns: List[str] = []
        metric_labels: List[str] = []
        for hit in resolved.metric_hits:
            column_name = hit.payload["column_name"]
            if column_name in metric_columns:
                continue
            metric_columns.append(column_name)
            metric_labels.append(hit.payload.get("metric_name") or column_name)

        if not metric_columns:
            fallback_column = _fallback_metric_column(table_info)
            metric_columns.append(fallback_column)
            metric_labels.append(fallback_column)

        where_parts: List[str] = []
        if time_col and plan.start_yyyymm and plan.end_yyyymm:
            where_parts.append(f"{_q(time_col)} BETWEEN '{plan.start_yyyymm}' AND '{plan.end_yyyymm}'")

        subject_code_expr = _subject_code_expr(fields, subject_code_col)
        subject_name_expr = _subject_name_expr(fields, subject_name_col)

        has_code_filter = False
        subject_codes = [hit.payload.get("select_code") for hit in resolved.subject_hits if hit.payload.get("select_code")]
        subject_names = [hit.payload.get("subject_name") for hit in resolved.subject_hits if hit.payload.get("subject_name")]
        if subject_code_expr and subject_codes:
            has_code_filter = True
            if len(subject_codes) == 1:
                where_parts.append(f"{subject_code_expr} = '{subject_codes[0]}'")
            else:
                code_list = ", ".join(f"'{code}'" for code in subject_codes)
                where_parts.append(f"{subject_code_expr} IN ({code_list})")
        elif subject_name_expr and subject_names:
            if len(subject_names) == 1:
                where_parts.append(f"{subject_name_expr} = '{subject_names[0]}'")
            else:
                name_list = ", ".join(f"'{name}'" for name in subject_names)
                where_parts.append(f"{subject_name_expr} IN ({name_list})")

        if not has_code_filter and plan.region and plan.region not in {"全省", "河北省", "省本级"} and region_name_col:
            where_parts.append(f"{_q(region_name_col)} = '{plan.region}'")

        include_subject_dimension = plan.compare_dimension == "subject" or len(resolved.subject_hits) >= 2
        include_time_dimension = _should_include_time_dimension(plan, time_col)
        include_region_dimension = plan.compare_dimension == "region"

        select_columns: List[str] = []
        if include_time_dimension and time_col:
            select_columns.append(_q(time_col))
        if include_region_dimension and region_name_col:
            select_columns.append(_q(region_name_col))
        if include_subject_dimension and subject_name_expr:
            select_columns.append(f"{subject_name_expr} XM_NAME")
        select_columns.extend(_q(metric_col) for metric_col in metric_columns)

        sql_parts = [
            f"SELECT {', '.join(select_columns)}",
            f"FROM {_table_expr(self._schema_name, resolved.selected_table.table_en)}",
        ]
        if where_parts:
            sql_parts.append(f"WHERE {' AND '.join(where_parts)}")

        order_sql = _build_order_sql(plan.raw_question, metric_columns)
        if order_sql:
            sql_parts.append(order_sql)

        chart_dimension = "time" if include_time_dimension else plan.compare_dimension
        return CompiledQuery(
            sql=" ".join(sql_parts),
            metric_labels=metric_labels,
            chart_dimension=chart_dimension,
        )


def _should_include_time_dimension(plan, time_col: Optional[str]) -> bool:
    """判断结果中是否需要把时间列作为展示维度。"""
    if not time_col:
        return False
    if plan.compare_dimension == "time" or plan.query_type in {"trend", "detail", "mixed"}:
        return True
    if plan.start_yyyymm and plan.end_yyyymm and plan.start_yyyymm != plan.end_yyyymm:
        return True
    return False


def _build_order_sql(question: str, metric_columns: List[str]) -> str:
    """按问题类型决定是否追加排序。"""
    # 默认尽量不加 ORDER BY，只有明确排名类问题才排序。
    if _looks_like_ranking(question) and metric_columns:
        return f"ORDER BY {_q(metric_columns[0])} DESC"
    return ""


def _looks_like_ranking(question: str) -> bool:
    """判断用户问题是否属于排名类问题。"""
    keywords = ["排名", "前", "top", "TOP", "最多", "最高", "最低"]
    return any(keyword in (question or "") for keyword in keywords)


def _resolve_time_column(fields: dict) -> Optional[str]:
    """推断表中的时间字段。"""
    for column_name in ["YEAR_MONTH", "BIZ_MONTH", "STAT_MONTH", "SJRQ", "RQ", "DATE_YEAR", "NF"]:
        if column_name in fields:
            return column_name
    return _find_column_by_comment(fields, ["业务年月", "年月", "月份", "年份", "日期", "业务年度"])


def _resolve_region_name_column(fields: dict) -> Optional[str]:
    """推断表中的地区名称字段。"""
    for column_name in ["RG_NAME", "REGION_NAME", "AREA_NAME", "CITY_NAME", "COUNTY_NAME"]:
        if column_name in fields:
            return column_name
    return _find_column_by_comment(fields, ["区划名称", "地区名称", "区域名称", "地市名称", "县区名称"])


def _resolve_subject_name_column(fields: dict, table_info: dict) -> Optional[str]:
    """推断表中的科目名称字段。"""
    for fallback in ("AI_XM_NAME", "AI_KM_NAME", "KM_NAME", "XM_NAME"):
        if fallback in fields:
            return fallback

    mapping = {str(field.get("comment", "") or ""): column_name for column_name, field in fields.items()}
    for comment in table_info.get("project_name", []):
        if comment in mapping:
            return mapping[comment]
    return None


def _resolve_subject_code_column(fields: dict, table_info: dict) -> Optional[str]:
    """推断表中的科目编码字段。"""
    for fallback in ("AI_XM_CODE", "AI_KM_CODE", "KM_CODE", "XM_CODE"):
        if fallback in fields:
            return fallback

    mapping = {str(field.get("comment", "") or ""): column_name for column_name, field in fields.items()}
    for comment in table_info.get("project_key", []):
        if comment in mapping:
            return mapping[comment]
    return None


def _subject_code_expr(fields: dict, subject_code_col: Optional[str]) -> str:
    """生成科目编码查询表达式，优先使用 AI 修正后的字段。"""
    if "AI_XM_CODE" in fields and "XM_CODE" in fields:
        return f"NVL({_q('AI_XM_CODE')}, {_q('XM_CODE')})"
    if "AI_KM_CODE" in fields and "KM_CODE" in fields:
        return f"NVL({_q('AI_KM_CODE')}, {_q('KM_CODE')})"
    if subject_code_col:
        return _q(subject_code_col)
    return ""


def _subject_name_expr(fields: dict, subject_name_col: Optional[str]) -> str:
    """生成科目名称查询表达式，优先使用 AI 修正后的字段。"""
    if "AI_XM_NAME" in fields and "XM_NAME" in fields:
        return f"NVL({_q('AI_XM_NAME')}, {_q('XM_NAME')})"
    if "AI_KM_NAME" in fields and "KM_NAME" in fields:
        return f"NVL({_q('AI_KM_NAME')}, {_q('KM_NAME')})"
    if subject_name_col:
        return _q(subject_name_col)
    return ""


def _find_column_by_comment(fields: dict, keywords: List[str]) -> Optional[str]:
    """通过字段注释中的关键词反推字段名。"""
    for column_name, field in fields.items():
        comment = str(field.get("comment", "") or "")
        if any(keyword in comment for keyword in keywords):
            return column_name
    return None


def _fallback_metric_column(table_info: dict) -> str:
    """在未命中指标时，从表说明里挑一个可用指标字段兜底。"""
    for fields in table_info.get("unit", {}).values():
        for column_name in fields.keys():
            return column_name
    raise ValueError("Unable to find an available metric column from table_info.")


def _q(name: str) -> str:
    """给字段名或表名加上双引号，避免关键字冲突。"""
    escaped = str(name).replace('"', '""')
    return f'"{escaped}"'


def _table_expr(schema_name: str, table_name: str) -> str:
    """生成带 schema 的表表达式。"""
    table_expr = _q(table_name)
    if not schema_name:
        return table_expr
    return f"{_q(schema_name)}.{table_expr}"
