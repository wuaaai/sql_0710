"""表能力矩阵模块。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class TableCapability:
    """描述一张表适合回答什么类型的问题。"""

    table_en: str
    table_zh: str
    business_module: str = ""
    account_book: str = ""
    flow_type: str = ""
    region_level: str = ""
    data_stage: str = ""
    time_grain: str = ""
    aliases: List[str] = field(default_factory=list)


def build_capability_from_metadata(table_en: str, table_zh: str, table_info: dict, schema: dict) -> TableCapability:
    """根据现有元数据自动推断一张表的能力标签。"""
    text = " ".join(
        str(item)
        for item in [
            table_zh,
            table_info.get("cate", ""),
            table_info.get("key_words", []),
        ]
    )

    business_module = _detect_business_module(text)
    account_book = _detect_account_book(text)
    flow_type = _detect_flow_type(text)
    region_level = _detect_region_level(text)
    data_stage = _detect_data_stage(text, business_module)
    time_grain = _detect_time_grain(schema)

    return TableCapability(
        table_en=table_en,
        table_zh=table_zh,
        business_module=business_module,
        account_book=account_book,
        flow_type=flow_type,
        region_level=region_level,
        data_stage=data_stage,
        time_grain=time_grain,
        aliases=[],
    )


def _detect_business_module(text: str) -> str:
    """从表描述中识别业务模块。"""
    if "预算执行" in text:
        return "预算执行"
    if "预算调整" in text:
        return "预算调整"
    if "决算" in text:
        return "决算"
    if "草案" in text or "预算草案" in text:
        return "预算草案"
    return ""


def _detect_account_book(text: str) -> str:
    """从表描述中识别属于四本账中的哪一本。"""
    if "一般公共预算" in text:
        return "一般公共预算"
    if "政府性基金" in text:
        return "政府性基金"
    if "国有资本经营预算" in text or "国有资本" in text:
        return "国有资本经营预算"
    if "社会保险基金" in text or "社保基金" in text:
        return "社会保险基金"
    return ""


def _detect_flow_type(text: str) -> str:
    """从表描述中识别是收入表、支出表还是收支混合表。"""
    has_income = "收入" in text
    has_expenditure = "支出" in text
    if has_income and has_expenditure:
        return "收支"
    if has_income:
        return "收入"
    if has_expenditure:
        return "支出"
    return ""


def _detect_region_level(text: str) -> str:
    """从表描述中识别数据覆盖的地区层级。"""
    if "全省" in text:
        return "全省"
    if "省本级" in text or "省级" in text:
        return "省本级"
    if "各市" in text or "地市" in text:
        return "地市"
    if "地区" in text or "区县" in text:
        return "区县"
    return ""


def _detect_data_stage(text: str, business_module: str) -> str:
    """从表描述中识别数据阶段，例如执行数、草案数或完成情况。"""
    if "完成情况" in text:
        return "完成情况"
    if "草案" in text:
        return "草案数"
    if "预算数" in text:
        return "预算数"
    if business_module == "预算执行":
        return "执行数"
    return ""


def _detect_time_grain(schema: dict) -> str:
    """根据字段结构判断表更偏月度还是年度数据。"""
    fields = schema.get("fields", {})
    for column_name in ["YEAR_MONTH", "BIZ_MONTH", "STAT_MONTH"]:
        if column_name in fields:
            return "month"
    return "year"
