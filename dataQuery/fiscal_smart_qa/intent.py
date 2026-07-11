"""意图识别模块。

这个模块负责把用户自然语言问题转换成结构化的 `QueryPlan` / `UserIntent`。
处理过程分为两层：
1. 优先调用大模型抽取结构化字段。
2. 如果大模型失败，则使用规则方法兜底。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from llm_client import DeepSeekClient
from query_plan import QueryPlan


@dataclass
class UserIntent:
    """兼容旧流程使用的意图对象。"""

    raw_question: str
    query_type: str
    time_text: str = ""
    start_yyyymm: str = ""
    end_yyyymm: str = ""
    budget_scope: str = ""
    subject: str = ""
    subjects: List[str] = field(default_factory=list)
    metric: str = ""
    metrics: List[str] = field(default_factory=list)
    region: str = ""
    regions: List[str] = field(default_factory=list)
    compare_dimension: str = ""
    compare_operator: str = "none"
    chart_hint: str = "auto"
    top_n: int = 0
    business_module: str = ""
    account_book: str = ""
    flow_type: str = ""
    region_level: str = ""
    data_stage: str = ""
    time_grain: str = ""
    extra: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_plan(cls, plan: QueryPlan) -> "UserIntent":
        """把 QueryPlan 转成旧版 UserIntent 对象。"""
        return cls(
            raw_question=plan.raw_question,
            query_type=plan.query_type,
            time_text=plan.time_text,
            start_yyyymm=plan.start_yyyymm,
            end_yyyymm=plan.end_yyyymm,
            budget_scope=plan.budget_scope,
            subject=plan.subject,
            subjects=plan.subjects,
            metric=plan.metric,
            metrics=plan.metrics,
            region=plan.region,
            regions=plan.regions,
            compare_dimension=plan.compare_dimension,
            compare_operator=plan.compare_operator,
            chart_hint=plan.chart_hint,
            top_n=plan.top_n,
            business_module=plan.business_module,
            account_book=plan.account_book,
            flow_type=plan.flow_type,
            region_level=plan.region_level,
            data_stage=plan.data_stage,
            time_grain=plan.time_grain,
            extra=plan.extra,
        )


# detail 明细 / trend 趋势/ proportion 占比/ comparison 对比比较/ mixed 混合/ summary 汇总摘要

INTENT_PROMPT = """
你是财政智能问数系统的 QueryPlan 提取器。
请从用户问题中提取关键信息，并严格输出 JSON。

字段要求：
- query_type: 只能是 detail / trend / proportion / comparison / mixed / summary
- time_text: 原始时间表达
- start_yyyymm: 例如 202510
- end_yyyymm: 例如 202512
- budget_scope: 例如 一般公共预算收入 / 一般公共预算支出 / 政府性基金收入 / 政府性基金支出
- subjects: 科目列表
- metrics: 指标列表
- regions: 地区列表
- compare_dimension: time / region / subject / none
- compare_operator: none / larger / smaller / diff / rank / proportion
- chart_hint: auto / line / pie / bar / bar_horizontal / bar_line
- top_n: 整数，没有就填 0
- business_module: 预算草案 / 预算执行 / 预算调整 / 决算 / unknown
- account_book: 一般公共预算 / 政府性基金 / 国有资本经营预算 / 社会保险基金 / unknown
- flow_type: 收入 / 支出 / 收支 / unknown
- region_level: 全省 / 省本级 / 地市 / 区县 / unknown
- data_stage: 预算数 / 执行数 / 草案数 / 完成情况 / unknown
- time_grain: month / year 

规则：
1. 问趋势、变化、走势时，query_type 优先 trend
2. 问占比、构成、比重时，query_type 优先 proportion
3. 问对比、排名、哪个大、相差多少时，query_type 优先 comparison
4. 问题中如果出现“预算草案、预算执行、预算调整、决算”，要尽量提取 business_module
5. 问题中如果出现“一般公共预算、政府性基金、国有资本经营预算、社会保险基金”，要尽量提取 account_book
6. 问题中如果出现“收入、支出”，要尽量提取 flow_type
7. 只输出 JSON，不要输出解释
"""


def extract_intent(client: DeepSeekClient, question: str) -> UserIntent:
    """对外暴露的旧接口，返回 UserIntent。"""
    plan = build_query_plan(client, question)
    return UserIntent.from_plan(plan)


def build_query_plan(client: DeepSeekClient, question: str) -> QueryPlan:
    """优先使用大模型抽取结构化查询计划。"""
    try:
        payload = client.chat_json(INTENT_PROMPT, question)
        metrics = _normalize_list(payload.get("metrics"), "", _extract_metrics(question))
        subjects = _normalize_list(payload.get("subjects"), "", _extract_subjects(question, metrics))
        regions = _normalize_list(payload.get("regions"), "", _extract_regions(question))
        budget_scope = str(payload.get("budget_scope") or _extract_budget_scope(question))
        business_module = _normalize_unknown(payload.get("business_module"), _extract_business_module(question))
        account_book = _normalize_unknown(payload.get("account_book"), _extract_account_book(question, budget_scope))
        flow_type = _normalize_unknown(payload.get("flow_type"), _extract_flow_type(question, budget_scope))
        region_level = _normalize_unknown(payload.get("region_level"), _extract_region_level(question, regions))
        data_stage = _normalize_unknown(payload.get("data_stage"), _extract_data_stage(question, business_module))
        time_grain = _normalize_unknown(payload.get("time_grain"), _extract_time_grain(question))

        return QueryPlan(
            raw_question=question,
            query_type=str(payload.get("query_type") or "summary"),
            time_text=str(payload.get("time_text") or ""),
            start_yyyymm=str(payload.get("start_yyyymm") or ""),
            end_yyyymm=str(payload.get("end_yyyymm") or ""),
            budget_scope=budget_scope,
            subjects=subjects,
            metrics=metrics,
            regions=regions,
            compare_dimension=str(payload.get("compare_dimension") or "none"),
            compare_operator=str(payload.get("compare_operator") or _guess_compare_operator(question)),
            chart_hint=str(payload.get("chart_hint") or "auto"),
            top_n=int(payload.get("top_n", 0) or 0),
            business_module=business_module,
            account_book=account_book,
            flow_type=flow_type,
            region_level=region_level,
            data_stage=data_stage,
            time_grain=time_grain,
            extra={},
        )
    except Exception:
        return fallback_query_plan(question)


def fallback_extract_intent(question: str) -> UserIntent:
    """旧版兜底接口，直接走规则抽取。"""
    return UserIntent.from_plan(fallback_query_plan(question))


def fallback_query_plan(question: str) -> QueryPlan:
    """当大模型失败时，使用规则方法生成查询计划。"""
    start_yyyymm, end_yyyymm, time_text = _extract_time_range(question)
    query_type = "summary"
    chart_hint = "auto"
    compare_dimension = "none"

    if any(word in question for word in ["趋势", "变化", "走势", "波动"]):
        query_type = "trend"
        chart_hint = "line"
        compare_dimension = "time"
    elif any(word in question for word in ["占比", "构成", "比重", "比例"]):
        query_type = "proportion"
        chart_hint = "pie"
    elif any(word in question for word in ["对比", "排名", "哪个大", "谁大", "相差多少", "高于", "低于"]):
        query_type = "comparison"
        chart_hint = "bar"
        compare_dimension = "subject"
    elif any(word in question for word in ["各市", "各地", "各区县"]):
        query_type = "comparison"
        chart_hint = "bar"
        compare_dimension = "region"
    elif any(word in question for word in ["每月", "各月", "分月", "逐月"]):
        query_type = "detail"
        chart_hint = "bar"
        compare_dimension = "time"

    budget_scope = _extract_budget_scope(question)
    regions = _extract_regions(question)
    metrics = _extract_metrics(question)
    subjects = _extract_subjects(question, metrics)

    if len(subjects) >= 2 and compare_dimension == "none":
        compare_dimension = "subject"
        query_type = "comparison"

    business_module = _extract_business_module(question)
    account_book = _extract_account_book(question, budget_scope)
    flow_type = _extract_flow_type(question, budget_scope)
    region_level = _extract_region_level(question, regions)
    data_stage = _extract_data_stage(question, business_module)
    time_grain = _extract_time_grain(question)

    return QueryPlan(
        raw_question=question,
        query_type=query_type,
        time_text=time_text,
        start_yyyymm=start_yyyymm,
        end_yyyymm=end_yyyymm,
        budget_scope=budget_scope,
        subjects=subjects,
        metrics=metrics,
        regions=regions,
        compare_dimension=compare_dimension,
        compare_operator=_guess_compare_operator(question),
        chart_hint=chart_hint,
        top_n=_extract_top_n(question),
        business_module=business_module,
        account_book=account_book,
        flow_type=flow_type,
        region_level=region_level,
        data_stage=data_stage,
        time_grain=time_grain,
        extra={},
    )


def _normalize_unknown(value, fallback: str) -> str:
    """把 unknown 或空值替换成规则推断结果。"""
    text = str(value or "").strip()
    if not text or text.lower() == "unknown":
        return fallback
    return text


def _extract_time_range(question: str) -> tuple[str, str, str]:
    """从问题中提取时间范围。"""
    match = re.search(r"(\d{4})年(\d{1,2})[-至到](\d{1,2})月", question)
    if match:
        year = match.group(1)
        start_month = int(match.group(2))
        end_month = int(match.group(3))
        return f"{year}{start_month:02d}", f"{year}{end_month:02d}", match.group(0)

    match = re.search(r"(\d{4})年(\d{1,2})月", question)
    if match:
        year = match.group(1)
        month = int(match.group(2))
        yyyymm = f"{year}{month:02d}"
        return yyyymm, yyyymm, match.group(0)

    match = re.search(r"(\d{4})年全年", question)
    if match:
        year = match.group(1)
        return f"{year}01", f"{year}12", match.group(0)

    match = re.search(r"(\d{4})年", question)
    if match:
        year = match.group(1)
        return f"{year}01", f"{year}12", match.group(0)

    return "", "", ""


def _extract_budget_scope(question: str) -> str:
    """提取预算口径，例如一般公共预算、政府性基金等。"""
    scope_keywords = [
        "一般公共预算收入",
        "一般公共预算支出",
        "政府性基金收入",
        "政府性基金支出",
        "国有资本经营预算收入",
        "国有资本经营预算支出",
        "社会保险基金收入",
        "社会保险基金支出",
        "一般公共预算",
        "政府性基金",
        "国有资本经营预算",
        "社会保险基金",
    ]
    for scope in scope_keywords:
        if scope in question:
            return scope
    return ""


def _extract_regions(question: str) -> List[str]:
    """从问题中识别地区名称。"""
    known_regions = ["全省", "河北省", "省本级", "石家庄市", "唐山市", "保定市", "邯郸市"]
    return [name for name in known_regions if name in question]


def _normalize_list(list_value, single_value: str, fallback: List[str]) -> List[str]:
    """把模型输出统一整理成去重后的列表。"""
    values: List[str] = []
    if isinstance(list_value, list):
        values.extend(str(item).strip() for item in list_value if str(item).strip())
    elif isinstance(list_value, str) and list_value.strip():
        values.append(list_value.strip())

    if single_value and single_value.strip():
        values.insert(0, single_value.strip())

    values = _dedupe_keep_order(values)
    return values or fallback


def _extract_metrics(question: str) -> List[str]:
    """从问题中识别指标名称。"""
    metric_aliases = [
        ("预算执行率", ["预算执行率", "执行率", "预算完成率"]),
        ("本月金额", ["本月金额", "当月金额", "本月数", "本月执行金额", "本月执行数"]),
        ("累计金额", ["累计金额", "累计收入", "累计支出", "累计执行金额", "累计数", "累计执行数"]),
        ("同比增幅", ["同比增额", "同比增长率", "同比增长", "同比"]),
        ("环比增幅", ["环比增额", "环比增长率", "环比增长", "环比"]),
        ("预算数", ["预算数", "年初预算", "调整预算"]),
        ("金额", ["金额"]),
    ]

    found: List[str] = []
    for canonical_name, aliases in metric_aliases:
        if any(alias in question for alias in aliases):
            if canonical_name == "金额" and any(item in found for item in ["本月金额", "累计金额"]):
                continue
            found.append(canonical_name)
    return _dedupe_keep_order(found)


def _extract_subjects(question: str, metrics: List[str]) -> List[str]:
    """从问题中提取科目或项目名称。"""
    text = question
    removable_words = [
        _extract_budget_scope(question),
        *_extract_regions(question),
        _extract_time_range(question)[2],
        "哪个大",
        "谁大",
        "相差多少",
        "分别是多少",
        "各是多少",
        "是多少",
        "对比",
        "比较",
        "其中",
        "的",
    ]
    for word in removable_words:
        if word:
            text = text.replace(word, " ")

    for phrase in ["一般公共预算收入中", "一般公共预算支出中", "一般公共预算中", "政府性基金中"]:
        text = text.replace(phrase, " ")

    for metric in metrics:
        text = text.replace(metric, " ")

    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    raw_parts = re.split(r"[与和及、,，]", text)
    subjects: List[str] = []
    for part in raw_parts:
        candidate = part.strip(" ，。？? ")
        candidate = candidate.replace("累计", "").replace("本月", "").replace("金额", "").strip()
        if candidate:
            subjects.append(candidate)
    return _dedupe_keep_order(subjects)


def _extract_business_module(question: str) -> str:
    """提取业务模块，例如预算执行、草案、预算审查。"""
    if "预算执行" in question:
        return "预算执行"
    if "决算" in question:
        return "决算"
    if "预算调整" in question:
        return "预算调整"
    if "预算草案" in question or "草案" in question:
        return "预算草案"
    return ""


def _extract_account_book(question: str, budget_scope: str) -> str:
    """提取四本账类型。"""
    text = f"{question} {budget_scope}"
    if "一般公共预算" in text:
        return "一般公共预算"
    if "政府性基金" in text:
        return "政府性基金"
    if "国有资本经营预算" in text or "国有资本" in text:
        return "国有资本经营预算"
    if "社会保险基金" in text or "社保基金" in text:
        return "社会保险基金"
    return ""


def _extract_flow_type(question: str, budget_scope: str) -> str:
    """提取收支方向。"""
    text = f"{question} {budget_scope}"
    has_income = "收入" in text
    has_expenditure = "支出" in text
    if has_income and has_expenditure:
        return "收支"
    if has_income:
        return "收入"
    if has_expenditure:
        return "支出"
    return ""


def _extract_region_level(question: str, regions: List[str]) -> str:
    """提取地区层级。"""
    if "全省" in question or "河北省" in question:
        return "全省"
    if "省本级" in question or "省级" in question:
        return "省本级"
    if "各市" in question or any(region.endswith("市") for region in regions):
        return "地市"
    if "各区县" in question or "区县" in question:
        return "区县"
    return ""


def _extract_data_stage(question: str, business_module: str) -> str:
    """提取数据阶段，例如预算数、执行数、完成情况。"""
    if "执行率" in question or "完成情况" in question:
        return "完成情况"
    if "预算数" in question or "年初预算" in question or "调整预算" in question:
        return "预算数"
    if "草案" in question:
        return "草案数"
    if business_module == "预算执行":
        return "执行数"
    return ""


def _extract_time_grain(question: str) -> str:
    """推断问题关注的是月度还是年度。"""
    if any(word in question for word in ["每月", "各月", "分月", "逐月"]) or re.search(r"\d{4}年\d{1,2}月", question):
        return "month"
    if "全年" in question or re.search(r"\d{4}年", question):
        return "year"
    return ""


def _guess_compare_operator(question: str) -> str:
    """根据问题措辞推断比较操作类型。"""
    if "哪个大" in question or "谁大" in question:
        return "larger"
    if "哪个小" in question or "谁小" in question:
        return "smaller"
    if "相差多少" in question:
        return "diff"
    if "排名" in question:
        return "rank"
    if "占比" in question or "比重" in question:
        return "proportion"
    return "none"


def _extract_top_n(question: str) -> int:
    """从问题中提取前 N 名里的 N。"""
    match = re.search(r"前(\d+)", question)
    if match:
        return int(match.group(1))
    return 0


def _dedupe_keep_order(items: List[str]) -> List[str]:
    """列表去重，同时保持原始顺序。"""
    output: List[str] = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        output.append(item)
    return output
