"""第一层业务域路由模块。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from query_plan import QueryPlan


@dataclass
class DomainRoute:
    """保存业务模块、四本账和收支方向等路由结果。"""

    business_module: str = ""
    account_book: str = ""
    flow_type: str = ""
    region_level: str = ""
    data_stage: str = ""
    time_grain: str = ""
    hard_filters: Dict[str, str] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)


class BusinessDomainRouter:
    """先把用户问题缩小到更小的业务范围。"""

    def route(self, plan: QueryPlan) -> DomainRoute:
        """根据 QueryPlan 里的结构化字段生成业务域路由结果。"""
        route = DomainRoute(
            business_module=plan.business_module,
            account_book=plan.account_book,
            flow_type=plan.flow_type,
            region_level=plan.region_level,
            data_stage=plan.data_stage,
            time_grain=plan.time_grain,
        )

        if route.business_module:
            route.hard_filters["business_module"] = route.business_module
            route.reasons.append(f"命中业务模块: {route.business_module}")

        if route.account_book:
            route.hard_filters["account_book"] = route.account_book
            route.reasons.append(f"命中四本账: {route.account_book}")

        if route.flow_type and route.flow_type != "收支":
            route.hard_filters["flow_type"] = route.flow_type
            route.reasons.append(f"命中收支方向: {route.flow_type}")

        if route.region_level:
            route.reasons.append(f"识别地区层级: {route.region_level}")

        if route.time_grain:
            route.reasons.append(f"识别时间粒度: {route.time_grain}")

        return route
