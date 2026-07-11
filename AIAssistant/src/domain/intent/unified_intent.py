"""统一意图识别领域数据类。

本模块定义统一意图识别层的输出数据结构，是整个 text2sql 链路和 RAG 链路的契约基础。
两套子集各自独立，下游链路按需消费，不设公共中间层。

设计文档：统一意图识别模块设计.md §3
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Text2SqlIntent:
    """Text2SQL 链路专用子集 — 财政问数的结构化查询意图。

    字段设计对应 dataQuery 中 QueryPlan 的全部核心字段，
    可直接参与 SQL 参数绑定、业务域路由和选表。

    设计文档参考：统一意图识别模块设计.md §3.2
    """

    # === 财政领域语义 ===

    business_module: str = ""
    """业务域。取值：预算执行 / 决算 / 预算调整 / 预算草案 / 预算审查。
    用于 text2sql 链路第一层业务域路由，决定候选表范围。
    来源：intent.py:_extract_business_module() — 关键词匹配。"""

    account_book: str = ""
    """四本账口径。取值：一般公共预算 / 政府性基金 / 国有资本经营预算 / 社会保险基金。
    用于表能力矩阵过滤，排除不相关账本的表。
    来源：intent.py:_extract_account_book() — 关键词匹配。"""

    flow_type: str = ""
    """收支方向。取值：收入 / 支出 / 收支。
    用于确定查询的是收入表还是支出表。
    来源：intent.py:_extract_flow_type() — 关键词判定。"""

    region_level: str = ""
    """地区层级。取值：全省 / 省本级 / 地市 / 区县。
    用于表能力矩阵过滤和 SQL 地区条件构建。
    来源：intent.py:_extract_region_level() — 关键词匹配。"""

    # === 时间 ===

    time_text: str = ""
    """用户问题中的原始时间表达文本，例如 "2019年"、"2025年10-12月"。
    来源：intent.py:_extract_time_range() — 正则提取。"""

    time_start: str = ""
    """查询起始时间，格式 yyyymm。全年时 = 01 月，单月时 = 该月。
    例如 "201901"。"""

    time_end: str = ""
    """查询结束时间，格式 yyyymm。全年时 = 12 月，单月时 = 该月。
    例如 "201912"。"""

    time_grain: str = ""
    """时间粒度。取值：month / year。
    用于决定 SQL 中 GROUP BY 和图表横轴的粒度。
    来源：intent.py:_extract_time_grain() — 每月/各月/分月 → month，全年/年度 → year。"""

    # === 查询要素 ===

    query_type: str = "summary"
    """查询类型。取值：detail / trend / proportion / comparison / mixed / summary。
    决定 SQL 的聚合方式和结果分析策略。
    来源：intent.py:INTENT_PROMPT + fallback_query_plan() — LLM 提取 + 规则兜底。"""

    subjects: List[str] = field(default_factory=list)
    """科目/项目名称列表，例如 ["税收收入", "非税收入"]。
    这是 text2sql 链路最关键的字段——决定 WHERE 条件中的科目过滤。
    来源：intent.py:_extract_subjects() + LLM + projectname.json 动态词典。"""

    metrics: List[str] = field(default_factory=list)
    """指标名称列表，例如 ["本月金额", "预算执行率"]。
    决定 SQL SELECT 中的指标列和别名匹配。
    来源：intent.py:_extract_metrics() — 别名映射表（执行率→预算执行率，同比→同比增幅）。"""

    regions: List[str] = field(default_factory=list)
    """地区名称列表，例如 ["全省", "石家庄市"]。
    决定 WHERE 条件中的地区过滤。
    来源：intent.py:_extract_regions() — 已知地区名列表匹配。"""

    data_stage: str = ""
    """数据阶段。取值：预算数 / 执行数 / 草案数 / 完成情况。
    影响选表——不同阶段的财政数据存放在不同表中。
    来源：intent.py:_extract_data_stage() — 关键词 + 业务模块推断。"""

    # === 比较与分析 ===

    compare_dimension: str = "none"
    """比较维度。取值：time / region / subject / none。
    用于决定多维度查询的对比方向。
    来源：intent.py:INTENT_PROMPT — LLM 提取。"""

    compare_operator: str = "none"
    """比较操作类型。取值：larger / smaller / diff / rank / proportion / none。
    影响 SQL 的 ORDER BY、HAVING、窗口函数生成。
    来源：intent.py:_guess_compare_operator() — 措辞推断。"""

    chart_hint: str = "auto"
    """图表类型建议。取值：line / pie / bar / bar_horizontal / bar_line / auto。
    传给前端渲染对应图表类型。
    来源：intent.py:INTENT_PROMPT + fallback_query_plan() — LLM + 规则。"""

    top_n: int = 0
    """查询前 N 条，0 表示不限制。
    例如"前10"→ top_n=10，SQL 中生成 LIMIT 10。
    来源：intent.py:_extract_top_n() — 正则。"""


@dataclass
class RagIntent:
    """RAG 链路专用子集 — 面向文档检索的语义信息。

    统一意图提取层只提供原始材料，不做检索优化。
    search_query 拼接、subject_keywords 扩展等检索策略由 RAG Agent 内部自行处理。

    设计文档参考：统一意图识别模块设计.md §3.3

    注意：本类的详细实现由 RAG 同事负责，此处仅定义接口契约。
    """

    need_policy_basis: bool = False
    """问题是否要求检索政策/文件/规定/措施依据。"""

    need_caliber_explanation: bool = False
    """问题是否要求检索口径解释/定义/怎么算。"""

    need_composition: bool = False
    """问题是否要求检索构成/分类/包括哪些/由哪几部分。"""

    need_data_value: bool = False
    """检索时是否附加数据类关键词（收入金额/总计/数值）。
    仅影响 RAG 内部检索策略，不参与 dispatch_execution 的路由决策。"""

    original_question: str = ""
    """用户原始问题原文，供 RAG Agent 自行改写和检索。"""


@dataclass
class UnifiedIntentDict:
    """统一意图识别层的完整输出。

    聚合 text2sql 子集和 rag 子集，是统一意图识别模块与下游链路之间的唯一契约。
    下游各取所需——text2sql 链路取 text2sql，RAG 链路取 rag，
    不直接消费对方字段。

    设计文档参考：统一意图识别模块设计.md §3.1
    """

    text2sql: Text2SqlIntent = field(default_factory=Text2SqlIntent)
    """Text2SQL 链路专用子集，我的职责范围。"""

    rag: RagIntent = field(default_factory=RagIntent)
    """RAG 链路专用子集，RAG 同事的职责范围。"""
