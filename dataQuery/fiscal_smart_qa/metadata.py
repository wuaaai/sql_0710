"""元数据加载与表能力过滤模块。

这个模块负责两件事：
1. 读取 schema、表说明、表能力矩阵等基础配置。
2. 根据业务域路由结果，先做一轮候选表过滤。

这样做的目的是在后续向量召回之前，先把明显不相关的表排除掉，
让系统在表数量扩容后依然保持较好的准确率和性能。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import MetadataConfig
from domain_router import DomainRoute
from table_capability import TableCapability, build_capability_from_metadata


@dataclass(frozen=True)
class TableFilterResult:
    """保存表能力过滤后的结果。"""

    allowed_tables: List[str]
    capability_bonus: Dict[str, float]
    reasons: Dict[str, List[str]]


@dataclass(frozen=True)
class MetadataBundle:
    """统一封装问数流程所需的元数据。"""

    schema_meta: Dict[str, dict]
    table_info: Dict[str, dict]
    table_capabilities: Dict[str, TableCapability] = field(default_factory=dict)

    def get_table_schema(self, table_en: str) -> dict:
        """按英文表名获取 schema 描述。"""
        return self.schema_meta.get("tables", {}).get(table_en, {})

    def get_table_info_by_zh(self, table_zh: str) -> dict:
        """按中文表名获取表说明信息。"""
        return self.table_info.get(table_zh, {})

    def get_table_info_by_en(self, table_en: str) -> Tuple[Optional[str], dict]:
        """按英文表名获取中文表名和表说明。"""
        for table_zh, info in self.table_info.items():
            if info.get("table") == table_en:
                return table_zh, info
        schema = self.get_table_schema(table_en)
        return schema.get("comment"), {}

    def get_table_capability(self, table_en: str) -> Optional[TableCapability]:
        """获取单张表的能力描述。"""
        return self.table_capabilities.get(table_en)

    def filter_tables(self, route: DomainRoute) -> TableFilterResult:
        """根据业务域路由结果过滤候选表。

        第二层选表策略不是让所有表直接竞争，而是：
        1. 先看业务模块是否匹配。
        2. 再看四本账、收支方向是否匹配。
        3. 最后给地区层级、时间粒度等弱条件加分。
        """
        allowed_tables: List[str] = []
        capability_bonus: Dict[str, float] = {}
        reasons: Dict[str, List[str]] = {}

        for table_en, capability in self.table_capabilities.items():
            matched, bonus, reason_list = _match_capability(capability, route)
            if not matched:
                continue
            allowed_tables.append(table_en)
            capability_bonus[table_en] = bonus
            reasons[table_en] = reason_list

        if allowed_tables:
            return TableFilterResult(
                allowed_tables=allowed_tables,
                capability_bonus=capability_bonus,
                reasons=reasons,
            )

        # 如果过滤条件过严导致没有表命中，则退回全表兜底，避免系统完全不可用。
        all_tables = list(self.schema_meta.get("tables", {}).keys())
        return TableFilterResult(
            allowed_tables=all_tables,
            capability_bonus={},
            reasons={},
        )


def load_metadata(config: MetadataConfig) -> MetadataBundle:
    """从配置文件加载问数所需的全部元数据。"""
    with config.schema_meta_path.open("r", encoding="utf-8") as fh:
        schema_meta = json.load(fh)
    with config.table_info_path.open("r", encoding="utf-8") as fh:
        table_info = json.load(fh)

    table_capabilities = _load_capabilities(config.capability_matrix_path, schema_meta, table_info)
    return MetadataBundle(
        schema_meta=schema_meta,
        table_info=table_info,
        table_capabilities=table_capabilities,
    )


def _load_capabilities(
    capability_matrix_path: Optional[Path],
    schema_meta: Dict[str, dict],
    table_info: Dict[str, dict],
) -> Dict[str, TableCapability]:
    """优先加载显式配置的表能力矩阵，没有时再自动推断。"""
    if capability_matrix_path and capability_matrix_path.exists():
        with capability_matrix_path.open("r", encoding="utf-8") as fh:
            raw_data = json.load(fh)
        capabilities = {}
        for table_en, item in raw_data.items():
            capabilities[table_en] = TableCapability(
                table_en=table_en,
                table_zh=item.get("table_zh", table_en),
                business_module=item.get("business_module", ""),
                account_book=item.get("account_book", ""),
                flow_type=item.get("flow_type", ""),
                region_level=item.get("region_level", ""),
                data_stage=item.get("data_stage", ""),
                time_grain=item.get("time_grain", ""),
                aliases=item.get("aliases", []),
            )
        return capabilities

    capabilities: Dict[str, TableCapability] = {}
    tables = schema_meta.get("tables", {})
    for table_en, schema in tables.items():
        table_zh, info = _get_table_info_by_en(table_en, table_info, schema)
        capabilities[table_en] = build_capability_from_metadata(table_en, table_zh or table_en, info, schema)
    return capabilities


def _get_table_info_by_en(table_en: str, table_info: Dict[str, dict], schema: dict) -> Tuple[Optional[str], dict]:
    """内部辅助方法：按英文表名查找表说明。"""
    for table_zh, info in table_info.items():
        if info.get("table") == table_en:
            return table_zh, info
    return schema.get("comment"), {}


def _match_capability(capability: TableCapability, route: DomainRoute) -> Tuple[bool, float, List[str]]:
    """判断一张表是否符合当前业务域，并返回额外加分。"""
    reasons: List[str] = []
    bonus = 0.0

    if route.business_module and capability.business_module and route.business_module != capability.business_module:
        return False, 0.0, reasons
    if route.business_module and capability.business_module == route.business_module:
        bonus += 0.30
        reasons.append(f"业务模块匹配: {route.business_module}")

    if route.account_book and capability.account_book and route.account_book != capability.account_book:
        return False, 0.0, reasons
    if route.account_book and capability.account_book == route.account_book:
        bonus += 0.25
        reasons.append(f"四本账匹配: {route.account_book}")

    if route.flow_type and route.flow_type != "收支":
        if capability.flow_type and capability.flow_type not in {route.flow_type, "收支"}:
            return False, 0.0, reasons
        if capability.flow_type in {route.flow_type, "收支"}:
            bonus += 0.20
            reasons.append(f"收支方向匹配: {route.flow_type}")

    if route.region_level and capability.region_level and route.region_level == capability.region_level:
        bonus += 0.05
        reasons.append(f"地区层级匹配: {route.region_level}")

    if route.time_grain and capability.time_grain and route.time_grain == capability.time_grain:
        bonus += 0.05
        reasons.append(f"时间粒度匹配: {route.time_grain}")

    return True, round(bonus, 6), reasons
