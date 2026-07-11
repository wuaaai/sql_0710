"""统一意图识别领域模块。

导出统一意图识别层的数据结构，供 request_lifecycle 和下游链路使用。
"""

from .unified_intent import RagIntent, Text2SqlIntent, UnifiedIntentDict

__all__ = [
    "Text2SqlIntent",
    "RagIntent",
    "UnifiedIntentDict",
]
