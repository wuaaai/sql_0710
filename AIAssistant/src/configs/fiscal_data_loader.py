"""财政元数据加载器。

从 dataQuery 元数据文件中加载真实指标名、科目词典和业务分类，
替代手写的关键词列表。

数据来源：
- table_info.json → 达梦表结构元数据（真实字段名/单位/业务分类）
- RDYS_PUBLIC_TBS.json → 全库 Schema 元数据（字段注释/表注释）
- projectname.json → 科目名称列表（需从达梦抽取，可能为空）
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple

# ============================================================
# 元数据文件路径
# ============================================================
_METADATA_DIR = Path(r"E:\Develop_docu\sql_0710\dataQuery\table_vector_rebuild\metadata")
_TABLE_INFO_PATH = _METADATA_DIR / "table_info.json"
_PROJECTNAME_PATH = Path(r"E:\Develop_docu\sql_0710\dataQuery\fiscal_smart_qa\projectname.json")


# ============================================================
# 加载函数
# ============================================================

def load_metric_aliases() -> Dict[str, List[str]]:
    """从 table_info.json 加载真实指标别名映射。

    将达梦中同一字段的多种名称映射到规范名。
    例："本月数—金额" / "本月数-金额" / "本月执行金额" → "本月金额"

    Returns:
        {规范名: [别名列表]}
    """
    metric_set: Dict[str, set] = {}

    def _add(canonical: str, alias: str):
        if canonical not in metric_set:
            metric_set[canonical] = set()
        metric_set[canonical].add(alias)

    if _TABLE_INFO_PATH.exists():
        with open(_TABLE_INFO_PATH, "r", encoding="utf-8") as f:
            table_info = json.load(f)

        for table_name, info in table_info.items():
            for unit_type, fields in info.get("unit", {}).items():
                for col, alias in fields.items():
                    # 根据字段含义归类到规范名
                    if "预算数" in alias or "调整预算" in alias:
                        _add("预算数", alias)
                    if "同比" in alias or "增减" in alias:
                        _add("同比增幅", alias)
                    if "环比" in alias:
                        _add("环比增幅", alias)
                    if "执行率" in alias or "完成率" in alias or "为预算数%" in alias:
                        _add("预算执行率", alias)
                    if "累计" in alias:
                        _add("累计金额", alias)
                    if "本月" in alias and "同比" not in alias:
                        _add("本月金额", alias)
                    if "总计" in alias or "合计" in alias or "总额" in alias:
                        _add("总计", alias)
                    _add("金额", alias)

    # 补充口语化别名
    supplements = {
        "本月金额": ["执行金额", "完成金额", "本月执行数", "本月完成数"],
        "累计金额": ["累计收入", "累计支出", "累计执行数"],
        "同比增幅": ["同比增长", "同比增减", "同比变化", "比上年同期"],
        "总计": ["合计多少", "总计多少", "一共多少"],
        "预算数": ["年初预算", "预算安排", "安排数"],
        "预算执行率": ["执行率", "完成率", "完成百分比"],
        "金额": ["多少", "金额多少"],
    }
    for canonical, aliases in supplements.items():
        if canonical not in metric_set:
            metric_set[canonical] = set()
        metric_set[canonical].update(aliases)

    return {k: list(v) for k, v in metric_set.items()}


def load_subject_keywords() -> List[str]:
    """加载科目关键词列表。

    优先从 projectname.json 加载（达梦抽取的真实科目名），
    为空时从 table_info.json 的表名关键词中提取兜底。

    Returns:
        科目关键词列表
    """
    subjects = []

    # 来源1: projectname.json — 达梦抽取的真实科目名
    if _PROJECTNAME_PATH.exists():
        with open(_PROJECTNAME_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            subjects.extend(data.get("project_names", []))

    # 来源2: 从 table_info.json 表中文名中提取科目关键词
    if not subjects and _TABLE_INFO_PATH.exists():
        with open(_TABLE_INFO_PATH, "r", encoding="utf-8") as f:
            table_info = json.load(f)
        for table_name, info in table_info.items():
            # 表中文名中提取"XX收入""XX支出"模式
            import re
            for m in re.finditer(r"([一-龥]+)(收入|支出)", table_name):
                subjects.append(m.group(0))

    # 来源3: 硬编码兜底（财政常用科目）
    if not subjects:
        subjects = [
            "税收收入", "非税收入", "卫生健康支出", "教育支出",
            "社会保障和就业支出", "农林水支出", "科学技术支出",
            "住房保障支出", "交通运输支出", "公共安全支出",
            "国防支出", "节能环保支出", "城乡社区支出",
            "一般公共预算收入", "政府性基金收入",
            "国有资本经营预算收入", "社会保险基金收入",
            "债务付息支出", "资源勘探信息支出", "商业服务业支出",
            "金融支出", "粮油物资储备支出", "灾害防治及应急管理支出",
            "文化旅游体育与传媒支出",
        ]

    return list(set(subjects))


def load_data_stage_keywords() -> Dict[str, List[str]]:
    """加载数据阶段关键词（从真实字段名推断）。"""
    return {
        "执行数": ["执行", "完成", "本月数", "累计数"],
        "预算数": ["预算数", "预算安排", "调整预算", "年初预算"],
        "草案数": ["草案", "预算草案"],
        "完成情况": ["完成情况", "执行率", "完成率"],
    }


def load_business_modules() -> List[str]:
    """加载业务模块列表。"""
    modules = []
    if _TABLE_INFO_PATH.exists():
        with open(_TABLE_INFO_PATH, "r", encoding="utf-8") as f:
            table_info = json.load(f)
        for info in table_info.values():
            cate = info.get("cate", "")
            if cate and cate not in modules:
                modules.append(cate)
    return modules or ["预算执行", "决算", "预算调整", "预算草案", "预算审查"]
