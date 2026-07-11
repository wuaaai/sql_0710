"""文本规范化工具模块。"""

from __future__ import annotations

import re


SPACE_RE = re.compile(r"\s+")
LEADING_INDEX_RE = re.compile(r"^[0-9一二三四五六七八九十]+[、.)）]")


def normalize_text(text: str) -> str:
    """清理空格、换行和序号，得到更适合匹配的标准文本。"""
    if text is None:
        return ""
    value = str(text).strip().replace("\u3000", " ")
    value = value.replace("（", "(").replace("）", ")")
    value = value.replace("：", ":").replace("，", ",")
    value = value.replace("\n", "").replace("\r", "")
    value = SPACE_RE.sub("", value)
    value = LEADING_INDEX_RE.sub("", value)
    return value
