"""查询计划模型模块。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class QueryPlan:
    """系统内部统一使用的问题结构。"""

    raw_question: str
    query_type: str
    time_text: str = ""
    start_yyyymm: str = ""
    end_yyyymm: str = ""
    budget_scope: str = ""
    regions: List[str] = field(default_factory=list)
    subjects: List[str] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)
    compare_dimension: str = "none"
    compare_operator: str = "none"
    chart_hint: str = "auto"
    top_n: int = 0

    business_module: str = ""
    account_book: str = ""
    flow_type: str = ""
    region_level: str = ""
    data_stage: str = ""
    time_grain: str = ""

    extra: Dict[str, str] = field(default_factory=dict)

    @property
    def region(self) -> str:
        """返回第一个地区，便于旧代码兼容。"""
        return self.regions[0] if self.regions else ""

    @property
    def subject(self) -> str:
        """返回第一个科目，便于旧代码兼容。"""
        return self.subjects[0] if self.subjects else ""

    @property
    def metric(self) -> str:
        """返回第一个指标，便于旧代码兼容。"""
        return self.metrics[0] if self.metrics else ""

    def to_dict(self) -> Dict[str, object]:
        """把 QueryPlan 转成字典，方便接口输出和调试。"""
        payload = asdict(self)
        payload["region"] = self.region
        payload["subject"] = self.subject
        payload["metric"] = self.metric
        return payload


@dataclass
class SlotValidationResult:
    """保存智能问数执行前的槽位校验结果。"""

    ready_for_sql: bool
    missing_slots: List[str] = field(default_factory=list)
    slot_values: Dict[str, str] = field(default_factory=dict)
    message: str = ""


def validate_query_plan(plan: QueryPlan) -> SlotValidationResult:
    """执行智能问数前，先校验关键槽位是不是足够明确。"""
    slot_values = {
        "subject": plan.subject,
        "metric": plan.metric,
        "flow_direction": plan.flow_type,
        "region_level": plan.region_level,
    }
    missing_slots: List[str] = []

    if _is_empty_or_generic_subject(plan.subject):
        missing_slots.append("subject")
    if _is_empty_or_generic_metric(plan.metric):
        missing_slots.append("metric")
    if plan.flow_type not in {"收入", "支出"}:
        missing_slots.append("flow_direction")
    if not plan.region_level:
        missing_slots.append("region_level")

    return SlotValidationResult(
        ready_for_sql=not missing_slots,
        missing_slots=missing_slots,
        slot_values=slot_values,
        message=_build_validation_message(missing_slots, slot_values),
    )


def _is_empty_or_generic_subject(subject: str) -> bool:
    """判断科目是否为空，或仅是过于宽泛的大类。"""
    if not subject:
        return True
    generic_subjects = {
        "财政收入",
        "财政支出",
        "收入",
        "支出",
        "重点支出",
        "一般公共预算",
        "政府性基金",
        "国有资本经营预算",
        "社会保险基金",
    }
    return subject in generic_subjects


def _is_empty_or_generic_metric(metric: str) -> bool:
    """判断指标是否为空，或只是模糊表达。"""
    if not metric:
        return True
    generic_metrics = {
        "情况",
        "规模",
        "水平",
    }
    return metric in generic_metrics


def _build_validation_message(missing_slots: List[str], slot_values: Dict[str, str]) -> str:
    """把槽位校验结果整理成用户容易理解的话术。"""
    if not missing_slots:
        return "槽位校验通过，可以直接执行财政数据查询。"

    slot_label_map = {
        "subject": "科目",
        "metric": "指标",
        "flow_direction": "收支方向",
        "region_level": "地区层级",
    }
    missing_labels = [slot_label_map[item] for item in missing_slots if item in slot_label_map]

    current_lines = []
    if slot_values.get("subject"):
        current_lines.append(f"- 已识别科目：{slot_values['subject']}")
    if slot_values.get("metric"):
        current_lines.append(f"- 已识别指标：{slot_values['metric']}")
    if slot_values.get("flow_direction"):
        current_lines.append(f"- 已识别收支方向：{slot_values['flow_direction']}")
    if slot_values.get("region_level"):
        current_lines.append(f"- 已识别地区层级：{slot_values['region_level']}")

    lines = [
        "这个问题具有智能问数意图，但关键槽位还不完整，暂时不执行 SQL 查询。",
        f"还缺少的条件：{'、'.join(missing_labels)}。",
    ]
    if current_lines:
        lines.append("当前已经识别到的信息如下：")
        lines.extend(current_lines)
    lines.append("请补充缺少条件后再查询。")
    return "\n".join(lines)
