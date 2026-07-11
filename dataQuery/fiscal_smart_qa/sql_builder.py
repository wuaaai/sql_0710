"""旧版 SQL 构建模块。

这个模块服务于旧的 `SelectionResult` 流程，保留它可以兼容历史调用链。
新版流程优先使用 `query_compiler.py`。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from intent import UserIntent
from metadata import MetadataBundle
from selector import SelectionResult


@dataclass
class BuiltSQL:
    """保存 SQL 和前端展示所需信息。"""

    sql: str
    metric_label: str
    metric_labels: List[str]
    chart_dimension: str


class SqlBuilder:
    """根据旧版选择结果拼装 SQL。"""

    def __init__(self, metadata: MetadataBundle, schema_name: str = ""):
        """保存元数据和 schema 名。"""
        self._metadata = metadata
        self._schema_name = (schema_name or "").strip()

    def build(self, intent: UserIntent, selection: SelectionResult) -> BuiltSQL:
        """把旧版意图和选表结果转换成 SQL。"""
        table = selection.selected_table
        schema = self._metadata.get_table_schema(table.table_en)
        fields = schema.get("fields", {})
        _, table_info = self._metadata.get_table_info_by_en(table.table_en)

        time_col = _resolve_time_column(fields)
        region_name_col = _resolve_region_name_column(fields)
        subject_name_col = _resolve_subject_name_column(fields, table_info)
        subject_code_col = _resolve_subject_code_column(fields, table_info)

        metric_hits = selection.metric_hits or ([selection.metric_hit] if selection.metric_hit else [])
        metric_columns: List[str] = []
        metric_labels: List[str] = []
        for hit in metric_hits:
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
        if time_col and intent.start_yyyymm and intent.end_yyyymm:
            where_parts.append(f"{_q(time_col)} BETWEEN '{intent.start_yyyymm}' AND '{intent.end_yyyymm}'")

        has_code_filter = False
        subject_hits = selection.subject_hits or ([selection.subject_hit] if selection.subject_hit else [])
        if subject_hits:
            subject_codes = [hit.payload.get("select_code") for hit in subject_hits if hit.payload.get("select_code")]
            subject_names = [hit.payload.get("subject_name") for hit in subject_hits if hit.payload.get("subject_name")]

            if subject_code_col and subject_codes:
                has_code_filter = True
                if len(subject_codes) == 1:
                    where_parts.append(f"{_q(subject_code_col)} = '{subject_codes[0]}'")
                else:
                    code_list = ", ".join(f"'{code}'" for code in subject_codes)
                    where_parts.append(f"{_q(subject_code_col)} IN ({code_list})")
            elif subject_name_col and subject_names:
                if len(subject_names) == 1:
                    where_parts.append(f"{_q(subject_name_col)} = '{subject_names[0]}'")
                else:
                    name_list = ", ".join(f"'{name}'" for name in subject_names)
                    where_parts.append(f"{_q(subject_name_col)} IN ({name_list})")

        if not has_code_filter and intent.region and intent.region not in {"全省", "省本级", "河北省"} and region_name_col:
            where_parts.append(f"{_q(region_name_col)} = '{intent.region}'")

        sql = self._build_by_type(
            table_name=table.table_en,
            intent=intent,
            time_col=time_col,
            region_name_col=region_name_col,
            subject_name_col=subject_name_col,
            metric_columns=metric_columns,
            where_parts=where_parts,
            include_subject_dimension=len(subject_hits) >= 2 or intent.compare_dimension == "subject",
        )

        chart_dimension = "time" if intent.query_type in {"trend", "mixed", "detail"} else intent.compare_dimension
        metric_label = "、".join(metric_labels)
        return BuiltSQL(
            sql=sql,
            metric_label=metric_label,
            metric_labels=metric_labels,
            chart_dimension=chart_dimension,
        )

    def _build_by_type(
        self,
        table_name: str,
        intent: UserIntent,
        time_col: Optional[str],
        region_name_col: Optional[str],
        subject_name_col: Optional[str],
        metric_columns: List[str],
        where_parts: List[str],
        include_subject_dimension: bool,
    ) -> str:
        """根据查询类型拼装 SELECT 和 ORDER BY。"""
        table_expr = _table_expr(self._schema_name, table_name)
        select_columns = _build_select_columns(
            time_col=time_col if intent.compare_dimension == "time" or intent.query_type in {"trend", "detail", "mixed"} else None,
            region_name_col=region_name_col if intent.compare_dimension == "region" else None,
            subject_name_col=subject_name_col if include_subject_dimension else None,
            metric_columns=metric_columns,
        )

        sql_parts = [f"SELECT {', '.join(select_columns)}", f"FROM {table_expr}"]
        if where_parts:
            sql_parts.append(f"WHERE {' AND '.join(where_parts)}")

        order_sql = _build_order_sql(intent, time_col, region_name_col, subject_name_col, metric_columns)
        if order_sql:
            sql_parts.append(order_sql)

        return " ".join(sql_parts)


def _build_select_columns(
    time_col: Optional[str],
    region_name_col: Optional[str],
    subject_name_col: Optional[str],
    metric_columns: List[str],
) -> List[str]:
    """构建 SELECT 子句中的字段列表。"""
    columns: List[str] = []
    if time_col:
        columns.append(_q(time_col))
    if region_name_col:
        columns.append(_q(region_name_col))
    if subject_name_col:
        columns.append(_q(subject_name_col))
    for metric_col in metric_columns:
        columns.append(_q(metric_col))
    return columns


def _build_order_sql(
    intent: UserIntent,
    time_col: Optional[str],
    region_name_col: Optional[str],
    subject_name_col: Optional[str],
    metric_columns: List[str],
) -> str:
    """按查询意图生成 ORDER BY 子句。"""
    if (intent.query_type in {"trend", "detail", "mixed"} or intent.compare_dimension == "time") and time_col:
        return f"ORDER BY {_q(time_col)}"

    if intent.compare_dimension == "subject" and subject_name_col:
        return f"ORDER BY {_q(subject_name_col)}"

    if _looks_like_ranking(intent.raw_question) and metric_columns:
        return f"ORDER BY {_q(metric_columns[0])} DESC"

    if intent.compare_dimension == "region" and region_name_col:
        return f"ORDER BY {_q(region_name_col)}"

    return ""


def _looks_like_ranking(question: str) -> bool:
    """判断是否属于排名类问题。"""
    ranking_keywords = ["排名", "前", "top", "TOP", "最多", "最高", "最低"]
    return any(keyword in (question or "") for keyword in ranking_keywords)


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


def _find_column_by_comment(fields: dict, keywords: List[str]) -> Optional[str]:
    """通过字段注释中的关键词反查字段名。"""
    for column_name, field in fields.items():
        comment = str(field.get("comment", "") or "")
        if any(keyword in comment for keyword in keywords):
            return column_name
    return None


def _resolve_subject_name_column(fields: dict, table_info: dict) -> Optional[str]:
    """推断表中的科目名称字段。"""
    mapping = {str(field.get("comment", "") or ""): column_name for column_name, field in fields.items()}
    for comment in table_info.get("project_name", []):
        if comment in mapping:
            return mapping[comment]
    for fallback in ("KM_NAME", "XM_NAME"):
        if fallback in fields:
            return fallback
    return None


def _resolve_subject_code_column(fields: dict, table_info: dict) -> Optional[str]:
    """推断表中的科目编码字段。"""
    mapping = {str(field.get("comment", "") or ""): column_name for column_name, field in fields.items()}
    for comment in table_info.get("project_key", []):
        if comment in mapping:
            return mapping[comment]
    for fallback in ("KM_CODE", "XM_CODE"):
        if fallback in fields:
            return fallback
    return None


def _fallback_metric_column(table_info: dict) -> str:
    """未命中指标时，从表说明中找一个默认指标字段。"""
    for fields in table_info.get("unit", {}).values():
        for column_name in fields.keys():
            return column_name
    raise ValueError("Unable to find an available metric column from table_info.")


def _q(name: str) -> str:
    """给字段名或表名加双引号。"""
    escaped = str(name).replace('"', '""')
    return f'"{escaped}"'


def _table_expr(schema_name: str, table_name: str) -> str:
    """生成带 schema 的表表达式。"""
    table_expr = _q(table_name)
    if not schema_name:
        return table_expr
    return f"{_q(schema_name)}.{table_expr}"
