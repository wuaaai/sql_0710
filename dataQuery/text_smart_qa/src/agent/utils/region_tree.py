"""
地区权限树 — 基于9位行政区划编码自动推导层级关系。

9位编码结构: XXX YYY ZZZ
  XXX = 省级 (130=河北)
  YYY = 市级 (000=省本级, 100=石家庄, 102=长安区...)
  ZZZ = 预留 (当前均为000)

判断规则: 取前6位核心码
  - 核心码以 "00" 结尾 → 组节点（省/市本级）→ 前缀展开，能看到下级
  - 核心码不以 "00" 结尾 → 叶子节点（区县）→ 精确匹配

示例:
  130000000 → 核心 130000 → 末尾00 → 组节点 → strip→"13" → $like "13%"
  130100000 → 核心 130100 → 末尾00 → 组节点 → strip→"1301" → $like "1301%"
  130102000 → 核心 130102 → 末尾02 → 叶子   → 精确匹配 "130102000"
"""

from typing import List, Optional


def strip_trailing_zeros(code: str) -> str:
    """去掉尾部连续的 '0'，保留核心层级前缀。"""
    return code.rstrip("0")


def is_group_node(code: str) -> bool:
    """
    判断9位码是否为组节点（有下级）。
    取前6位核心码，以 "00" 结尾则为组节点。
    """
    core = code[:6]
    return core.endswith("00")


def is_ancestor_or_self(ancestor_code: str, target_code: str) -> bool:
    """判断 ancestor_code 是否是 target_code 的祖先（或自身）。"""
    if ancestor_code == target_code:
        return True
    # 叶子节点不能是任何其他节点的祖先
    if not is_group_node(ancestor_code):
        return False
    ancestor_prefix = strip_trailing_zeros(ancestor_code)
    target_prefix = strip_trailing_zeros(target_code)
    return target_prefix.startswith(ancestor_prefix)


def build_pgvector_filter(region_codes: List[str]) -> Optional[dict]:
    """
    将用户权限的地区码列表转为 PGVector metadata 过滤条件。
    组节点（核心码以00结尾）展开为前缀匹配，叶子节点精确匹配。
    返回 None 表示无过滤条件。
    """
    if not region_codes:
        print("[RegionTree] 未传入 region_code，不进行地区过滤")
        return None

    print(f"[RegionTree] 输入权限码: {region_codes}")

    conditions = []
    for code in region_codes:
        core = code[:6]
        if is_group_node(code):
            prefix = strip_trailing_zeros(code)
            cond = {"region_code": {"$like": f"{prefix}%"}}
            print(f"[RegionTree] 核心码 '{core}' 末尾00 → 组节点, strip='{prefix}' -> $like '{prefix}%'")
        else:
            cond = {"region_code": code}
            print(f"[RegionTree] 核心码 '{core}' 末尾非00 → 叶子节点, 精确匹配 '{code}'")
        conditions.append(cond)

    if len(conditions) == 1:
        return conditions[0]
    filter_dict = {"$or": conditions}
    print(f"[RegionTree] 多权限合并 -> $or: {filter_dict}")
    return filter_dict


# ================= 测试 =================
if __name__ == "__main__":
    # --- strip ---
    assert strip_trailing_zeros("130000000") == "13"
    assert strip_trailing_zeros("130100000") == "1301"
    assert strip_trailing_zeros("130102000") == "130102"

    # --- is_group_node ---
    assert is_group_node("130000000")       # 核心 130000 末尾00 → 组
    assert is_group_node("130100000")       # 核心 130100 末尾00 → 组
    assert not is_group_node("130102000")   # 核心 130102 末尾02 → 叶子
    assert not is_group_node("130104000")   # 核心 130104 末尾04 → 叶子
    assert not is_group_node("130105000")   # 核心 130105 末尾05 → 叶子
    assert not is_group_node("130107000")   # 核心 130107 末尾07 → 叶子

    # --- is_ancestor_or_self ---
    assert is_ancestor_or_self("130000000", "130102000")     # 河北省本级 → 长安区 ✓
    assert is_ancestor_or_self("130100000", "130102000")     # 石家庄市本级 → 长安区 ✓
    assert is_ancestor_or_self("130000000", "130000000")     # 自身 ✓
    assert not is_ancestor_or_self("130102000", "130104000") # 长安区 → 桥西区 ✗
    assert not is_ancestor_or_self("130100000", "130000000") # 反向 ✗

    # --- build_pgvector_filter ---
    f = build_pgvector_filter(["130000000"])
    assert f == {"region_code": {"$like": "13%"}}, f"Unexpected: {f}"

    f = build_pgvector_filter(["130100000"])
    assert f == {"region_code": {"$like": "1301%"}}, f"Unexpected: {f}"

    f = build_pgvector_filter(["130102000"])
    assert f == {"region_code": "130102000"}, f"Unexpected: {f}"

    f = build_pgvector_filter(["130102000", "130104000"])
    assert f == {"$or": [
        {"region_code": "130102000"},
        {"region_code": "130104000"},
    ]}, f"Unexpected: {f}"

    assert build_pgvector_filter([]) is None
    assert build_pgvector_filter(None) is None

    print("All tests passed.")
