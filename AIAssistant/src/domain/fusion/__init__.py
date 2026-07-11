"""融合层领域模块。

导出 RAG 反哺 Text2SQL 模块的输出数据结构。
"""

from .fusion_result import Citation, FusionResult, RagEnrichmentLog

__all__ = [
    "Citation",
    "FusionResult",
    "RagEnrichmentLog",
]
