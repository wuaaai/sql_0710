"""项目名称加载工具。

这个模块负责从 fiscal_smart_qa 目录下的 projectname.json 中加载项目名称，
供统一路由层做“明确科目”识别。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List


PROJECT_NAME_FILE = Path(__file__).resolve().parent / "projectname.json"


def load_project_names() -> List[str]:
    """从 projectname.json 读取项目名称列表。

    返回规则：
    1. 文件不存在时返回空列表。
    2. 文件内容是字符串数组时，直接清洗后返回。
    3. 文件内容是对象时，优先读取 project_names 字段。
    """
    if not PROJECT_NAME_FILE.exists():
        return []

    try:
        payload = json.loads(PROJECT_NAME_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    if isinstance(payload, list):
        return _clean_names(payload)

    if isinstance(payload, dict):
        raw_names = payload.get("project_names", [])
        return _clean_names(raw_names)

    return []


def _clean_names(raw_names) -> List[str]:
    """清洗项目名称，去空、去重，并按长度降序排序。"""
    names: List[str] = []
    seen = set()
    for item in raw_names or []:
        text = str(item or "").strip()
        if not text:
            continue
        if text in seen:
            continue
        seen.add(text)
        names.append(text)
    return sorted(names, key=len, reverse=True)
