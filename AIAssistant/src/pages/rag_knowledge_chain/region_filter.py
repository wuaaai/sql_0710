"""地区权限树 — 基于9位行政区划编码自动推导层级关系。

完整复用自 dataQuery/text_smart_qa/src/agent/utils/region_tree.py

9位编码结构: XXX YYY ZZZ
  XXX = 省级 (130=河北)
  YYY = 市级 (000=省本级, 100=石家庄, 102=长安区...)
  ZZZ = 预留 (当前均为000)

判断规则: 取前6位核心码
  - 核心码以 "00" 结尾 → 组节点（省/市本级）→ 前缀展开，能看到下级
  - 核心码不以 "00" 结尾 → 叶子节点（区县）→ 精确匹配
"""

from typing import List, Optional


def strip_trailing_zeros(code: str) -> str:
    """去掉尾部连续的 '0'，保留核心层级前缀。"""
    return code.rstrip("0")


def is_group_node(code: str) -> bool:
    """判断9位码是否为组节点（有下级）。

    取前6位核心码，以 "00" 结尾则为组节点。
    """
    core = code[:6]
    return core.endswith("00")


def is_ancestor_or_self(ancestor_code: str, target_code: str) -> bool:
    """判断 ancestor_code 是否是 target_code 的祖先（或自身）。"""
    if ancestor_code == target_code:
        return True
    if not is_group_node(ancestor_code):
        return False
    ancestor_prefix = strip_trailing_zeros(ancestor_code)
    target_prefix = strip_trailing_zeros(target_code)
    return target_prefix.startswith(ancestor_prefix)


def build_pgvector_filter(region_codes: List[str]) -> Optional[dict]:
    """将用户权限的地区码列表转为 PGVector metadata 过滤条件。

    组节点（核心码以00结尾）展开为前缀匹配，叶子节点精确匹配。
    返回 None 表示无过滤条件。
    """
    if not region_codes:
        return None

    conditions = []
    for code in region_codes:
        if is_group_node(code):
            prefix = strip_trailing_zeros(code)
            cond = {"region_code": {"$like": f"{prefix}%"}}
        else:
            cond = {"region_code": code}
        conditions.append(cond)

    if len(conditions) == 1:
        return conditions[0]
    return {"$or": conditions}
