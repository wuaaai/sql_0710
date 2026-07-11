"""双链路调度执行。

在 AIAssistant 框架的请求生命周期中，本模块是步骤 3，
位于统一意图识别（unified_intent_extractor）之后，结果汇总（result_aggregation）之前。

读取 UnifiedIntentDict，各链路按自身字段独立决定是否执行，
不交叉判定。五种调度结果：纯 Text2SQL / 纯 RAG / 混合 / 追问补槽位 / 闲聊兜底。

对应设计文档：统一意图识别模块设计.md §3.1、§7
"""

from dataclasses import dataclass, field
from typing import List, Optional

from src.domain.intent.unified_intent import Text2SqlIntent, UnifiedIntentDict


# ============================================================
# 调度指令
# ============================================================

@dataclass
class DispatchPlan:
    """双链路调度决策结果。

    由 ConcurrentTaskDispatcher 从 UnifiedIntentDict 推导得出，
    告知下游具体执行哪些链路。
    """

    text2sql: bool = False
    """是否执行 Text2SQL 链路。"""

    rag: bool = False
    """是否执行 RAG 链路。"""

    clarify: bool = False
    """是否需要追问用户补槽位。为 True 时 text2sql 和 rag 均不执行。"""

    clarify_message: str = ""
    """补槽位提示文案，供前端展示。"""

    missing_slots: List[str] = field(default_factory=list)
    """缺失的关键槽位列表，例如 ["time", "region_level", "metric"]。"""

    fallback: bool = False
    """是否闲聊兜底——text2sql 和 rag 均不执行，交由通用对话处理。"""

    text2sql_intent: Optional[Text2SqlIntent] = None
    """传入 Text2SQL 链路的意图子集。仅当 text2sql=True 时有值。"""


# ============================================================
# 槽位标签映射 — 复用 router_service.py 的 slot_label_map
# ============================================================

_SLOT_LABEL_MAP = {
    "subject": "科目",
    "metric": "指标",
    "flow_direction": "收支方向",
    "region_level": "地区层级",
    "time": "时间",
}


class ConcurrentTaskDispatcher:
    """双链路调度器。

    职责：
    - 读取 UnifiedIntentDict
    - text2sql 链路：subjects 或 metrics 非空 且 槽位齐全 → 执行
    - RAG 链路：need_composition / need_policy_basis / need_caliber_explanation 任一为 true → 执行
    - 槽位缺失时生成补槽位追问文案
    - 均不需要时走闲聊兜底
    - 返回 DispatchPlan
    """

    def dispatch(self, intent_dict: UnifiedIntentDict) -> DispatchPlan:
        """主入口：从统一意图字典推导调度策略。

        各链路依据自身字段独立决定是否执行，一个字段不决定另一个链路的死活。

        Args:
            intent_dict: 统一意图识别模块输出的 UnifiedIntentDict

        Returns:
            DispatchPlan，告知下游哪些链路需要执行
        """
        t2s = intent_dict.text2sql
        rag = intent_dict.rag

        # 各链路独立判定是否执行
        run_text2sql = self._should_run_text2sql(t2s)
        run_rag = self._should_run_rag(rag)

        # 有查数意图但槽位不完整 → 追问补槽位，不执行 SQL
        if run_text2sql and not self._slots_ready(t2s):
            missing = self._find_missing_slots(t2s)
            return DispatchPlan(
                clarify=True,
                clarify_message=self._build_clarify_message(t2s, missing),
                missing_slots=missing,
                text2sql_intent=None,
            )

        # 均无意图 → 闲聊兜底
        if not run_text2sql and not run_rag:
            return DispatchPlan(fallback=True)

        return DispatchPlan(
            text2sql=run_text2sql,
            rag=run_rag,
            text2sql_intent=t2s if run_text2sql else None,
        )

    # ============================================================
    # 链路执行判定
    # ============================================================

    @staticmethod
    def _should_run_text2sql(t2s: Text2SqlIntent) -> bool:
        """Text2SQL 链路执行判定。

        subjects 或 metrics 非空 → 有查数意图，需要跑 text2sql。
        但最终是否执行还要看 _slots_ready。

        对应设计文档 §3.1 路由推导表。
        """
        return bool(t2s.subjects or t2s.metrics)

    @staticmethod
    def _should_run_rag(rag) -> bool:
        """RAG 链路执行判定。

        need_composition / need_policy_basis / need_caliber_explanation
        任一为 true → 需要跑 RAG。

        need_data_value 不参与此判定，它是 RAG 内部检索策略字段。

        对应设计文档 §3.1 路由推导表。
        """
        return rag.need_composition or rag.need_policy_basis or rag.need_caliber_explanation

    # ============================================================
    # 槽位校验 — 复用 router_service.py 的四槽位硬校验逻辑
    # ============================================================

    @staticmethod
    def _slots_ready(t2s: Text2SqlIntent) -> bool:
        """判断 Text2SQL 的四槽位是否齐全。

        四个必要条件：科目 / 指标 / 收支方向 / 地区层级。
        复用 router_service.py:_is_fiscal_query_ready() 的逻辑。
        """
        has_subject = bool(t2s.subjects)
        has_metric = bool(t2s.metrics)
        has_flow = t2s.flow_type in ("收入", "支出")
        has_region = bool(t2s.region_level)
        return has_subject and has_metric and has_flow and has_region

    @staticmethod
    def _find_missing_slots(t2s: Text2SqlIntent) -> List[str]:
        """找出当前意图中缺失的关键槽位。

        复用 router_service.py:_find_missing_fiscal_slots() 的逻辑。
        """
        missing: List[str] = []
        if not t2s.subjects:
            missing.append("subject")
        if not t2s.metrics:
            missing.append("metric")
        if t2s.flow_type not in ("收入", "支出"):
            missing.append("flow_direction")
        if not t2s.region_level:
            missing.append("region_level")
        if not t2s.time_text:
            missing.append("time")
        return missing

    @staticmethod
    def _build_clarify_message(t2s: Text2SqlIntent, missing_slots: List[str]) -> str:
        """生成缺槽位时的补充提问文案。

        复用 router_service.py:_build_clarify_message() 的逻辑。
        """
        missing_labels = [
            _SLOT_LABEL_MAP[slot] for slot in missing_slots if slot in _SLOT_LABEL_MAP
        ]

        current_lines = []
        if t2s.subjects:
            current_lines.append(f"- 已识别科目：{'、'.join(t2s.subjects)}")
        if t2s.metrics:
            current_lines.append(f"- 已识别指标：{'、'.join(t2s.metrics)}")
        if t2s.flow_type:
            current_lines.append(f"- 已识别收支方向：{t2s.flow_type}")
        if t2s.region_level:
            current_lines.append(f"- 已识别地区层级：{t2s.region_level}")
        if t2s.time_text:
            current_lines.append(f"- 已识别时间：{t2s.time_text}")

        lines = [
            "这个问题更像是财政数据查询，但当前还不具备直接执行 SQL 的条件。",
            f"还缺少的关键条件：{'、'.join(missing_labels) if missing_labels else '关键槽位'}。",
        ]
        if current_lines:
            lines.append("当前已经识别到的信息如下：")
            lines.extend(current_lines)
        lines.append("请补充缺少的条件后，我就可以继续帮你查询。")
        lines.append('例如你可以这样问：2025年省本级卫生健康支出的执行金额是多少')

        return "\n".join(lines)
