from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


RouteName = Literal["text_qa", "fiscal_sql", "hybrid", "chitchat"]
TaskRouteName = Literal["text_qa", "fiscal_sql"]
SlotStatus = Literal["none", "ready", "clarify"]


@dataclass
class IntentTask:
    """子意图任务。

    一个用户问题可以拆成多个子问题，每个子问题只对应一种能力：
    - text_qa：查财政文档知识库
    - fiscal_sql：查财政数据
    """

    route: TaskRouteName
    question: str
    reason: str = ""
    slot_status: SlotStatus = "none"
    missing_slots: List[str] = field(default_factory=list)
    slot_values: Dict[str, str] = field(default_factory=dict)


@dataclass
class RoutingDecision:
    """统一路由结果。"""

    route: RouteName
    confidence: float
    reason: str
    source: str = "rules"
    text_question: str = ""
    data_question: str = ""
    main_intent: str = ""
    sub_tasks: List[IntentTask] = field(default_factory=list)
    slot_status: SlotStatus = "none"
    missing_slots: List[str] = field(default_factory=list)
    slot_values: Dict[str, str] = field(default_factory=dict)
    clarify_message: str = ""


@dataclass
class TextQaResult:
    """智能问答结果。"""

    answer: str
    raw_output: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FiscalQaResult:
    """智能问数结果。"""

    answer: str
    sql: str = ""
    rows: List[Dict[str, Any]] = field(default_factory=list)
    chart: Dict[str, Any] = field(default_factory=dict)
    facts: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str = ""
    slot_status: SlotStatus = "none"
    missing_slots: List[str] = field(default_factory=list)
    slot_values: Dict[str, str] = field(default_factory=dict)
    need_clarify: bool = False


@dataclass
class UnifiedAnswer:
    """统一返回结果。"""

    route: RouteName
    answer: str
    decision: RoutingDecision
    text_result: Optional[TextQaResult] = None
    fiscal_result: Optional[FiscalQaResult] = None
    extra: Dict[str, Any] = field(default_factory=dict)
