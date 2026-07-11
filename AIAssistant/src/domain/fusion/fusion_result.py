"""融合层领域数据类。

定义 RAG 反哺 Text2SQL 模块的输出数据结构。
对应设计文档：结果融合层设计.md §3
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Citation:
    """引用来源 — 标注回答中每条信息的出处。

    对应设计文档 §3。
    """

    type: str = ""
    """来源类型。取值：sql / rag。"""

    label: str = ""
    """显示标签，例 "数据来源" / "政策依据"。"""

    detail: str = ""
    """详细信息。sql 类型为表名/字段名，rag 类型为文档名。"""


@dataclass
class RagEnrichmentLog:
    """RAG 反哺增强日志 — 记录本次增强了哪些槽位、候选值及来源。

    对应设计文档 §3.3 和 §5.2。
    """

    filled_slots: List[str] = field(default_factory=list)
    """本次补全了哪些槽位，例 ["metrics","region_level","time"]。"""

    candidates: Dict[str, List] = field(default_factory=dict)
    """每个槽位的候选值及出现次数。
    例 {"metrics": [("执行金额",5),("预算数",2)], "region_level": [("全省",5)]}。"""

    sources: Dict[str, str] = field(default_factory=dict)
    """每个被补全的值来自哪个文档。
    例 {"metrics": "2025年预算解读", "region_level": "2025年预算解读"}。"""

    degrade_reason: str = ""
    """降级原因。当 RAG 结果不可用时记录，例 "RAG最高相关度0.15<0.3"。"""


@dataclass
class FusionResult:
    """融合层最终输出 — 面向前端/Dify 的完整回答。

    对应设计文档 §3。
    """

    answer: str = ""
    """最终自然语言回答，markdown 格式。含表格、引用、数据一致性说明。"""

    answer_mode: str = "fallback"
    """回答类型。取值：sql / rag / both / clarify / fallback。
    对应设计文档 §3.1。"""

    sql_data: Optional[List[Dict[str, Any]]] = None
    """SQL 查询原始结果行，供前端图表渲染。
    仅 sql / both 模式有值。"""

    chart_config: Optional[Dict[str, Any]] = None
    """ECharts option，前端直接绑定图表组件。
    仅 sql / both 模式有值。"""

    citations: List[Citation] = field(default_factory=list)
    """引用来源列表。"""

    enrichment_log: Optional[RagEnrichmentLog] = None
    """RAG 反哺增强日志。纯 rag / fallback 模式下为 None。
    对应设计文档 §3.3。"""

    overall_confidence: float = 0.0
    """整体可信度 0-1。基于 SQL 数据质量 + RAG 相关度 + 口径/时间匹配度。"""

    slot_missing: List[str] = field(default_factory=list)
    """缺失的槽位列表。仅 clarify 模式有值。
    例 ["region_level", "time"]。对应设计文档 §8 方案9。"""

    clarify_prompt: str = ""
    """槽位补全引导文案。仅 clarify 模式有值。
    例 "请补充查询的年份和地区层级。例如：2025年全省..."。"""

    degrade_reason: str = ""
    """降级原因。当 RAG 或 text2sql 执行异常时记录，用于排查。
    例 "RAG检索超时" / "SQL执行失败: 表不存在"。"""

    generated_at: str = ""
    """生成时间戳，ISO 格式。"""
