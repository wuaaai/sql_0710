"""统一意图识别提取器。

在 AIAssistant 框架的请求生命周期中，本模块位于 request_preprocessing 和 dispatch_execution 之间，
负责将用户自然语言问题一次性提取为结构化意图字典（UnifiedIntentDict）。

提取策略：LLM 优先，规则兜底。一次提取，两路消费。
对应设计文档：统一意图识别模块设计.md §2、§6、§7
"""

import re
from typing import Dict, List, Optional

from src.domain.intent.unified_intent import RagIntent, Text2SqlIntent, UnifiedIntentDict

# ============================================================
# LLM Prompt — 复用 dataQuery intent.py 的 INTENT_PROMPT 模板
# 扩充了 rag 侧 4 个 need_* 字段的判断逻辑
# ============================================================

INTENT_PROMPT = """
你是财政智能助手的统一意图提取器。
请从用户问题中提取关键信息，并严格输出 JSON。

字段要求：
- query_type: 只能是 detail / trend / proportion / comparison / mixed / summary
- time_text: 原始时间表达
- start_yyyymm: 例如 202510
- end_yyyymm: 例如 202512
- budget_scope: 例如 一般公共预算收入 / 一般公共预算支出 / 政府性基金收入 / 政府性基金支出
- subjects: 问题中提及的财政科目/项目/支出类别列表，例 ["税收收入","卫生健康支出"]。
  重要：具体科目如"一般公共预算收入""税收收入"等即使与 budget_scope 重叠也必须填入 subjects。
  如果问题没有提及具体科目，填空列表 []。
- metrics: 指标列表，例 ["总计","执行金额","同比增幅"]。问"多少""总计"时填 ["总计"]，问"执行金额"时填 ["执行金额"]。
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

RAG 侧需要额外判断的布尔字段：
- need_policy_basis: 问题是否要求查询政策/文件/规定/措施依据（true/false）
- need_caliber_explanation: 问题是否要求解释口径/定义/怎么算/什么意思（true/false）
- need_composition: 问题是否要求说明构成/分类/包括哪些/由哪几部分（true/false）
- need_data_value: 问题是否问数值数据，如多少/金额/总量/总计/执行率（true/false）

规则：
1. 问趋势、变化、走势时，query_type 优先 trend
2. 问占比、构成、比重时，query_type 优先 proportion
3. 问对比、排名、哪个大、相差多少时，query_type 优先 comparison
4. 问题中如果出现"预算草案、预算执行、预算调整、决算"，要尽量提取 business_module
5. 问题中如果出现"一般公共预算、政府性基金、国有资本经营预算、社会保险基金"，要尽量提取 account_book
6. 问题中如果出现"收入、支出"，要尽量提取 flow_type
7. 问题中如出现"政策/文件/规定/措施"，need_policy_basis 填 true
8. 问题中如出现"口径/怎么算/什么意思/定义"，need_caliber_explanation 填 true
9. 问题中如出现"构成/包括哪些/由哪几部分/分类"，need_composition 填 true
10. 问题中如出现"多少/金额/总量/总计/执行率/同比/环比/增幅"，need_data_value 填 true
11. **科目提取规则：问题里提到的具体收支项目（如"卫生健康支出""税收收入""一般公共预算收入"）都必须填入 subjects，不能因为已填入 budget_scope 就省略**
12. **指标提取规则：问"多少""总计多少""合计"时，metrics 填 ["总计"]；问"执行金额""完成金额"时，填对应的指标名**
13. **纯定义/口径问题：如果问题是"XX是什么""XX的口径""XX的含义""怎么理解XX"，不要将 XX 填入 subjects，因为用户是在问定义而非查数据**
14. 只输出 JSON，不要输出解释
"""


class UnifiedIntentExtractor:
    """统一意图提取器。

    职责：
    - 接收用户问题 + 历史消息 + 地区权限码
    - 第一阶段：LLM 结构化提取（复用 dataQuery intent.py 的 INTENT_PROMPT + build_query_plan 模式）
    - 第二阶段：LLM 失败时规则兜底（复用 dataQuery intent.py 的全部 _extract_* 函数）
    - 拆分投影：从原始提取结果构造 text2sql 子集和 rag 子集
    - 返回 UnifiedIntentDict

    输入：
        question: str          — 当前轮用户问题原文
        history_messages: list — 最近 N 轮历史消息，用于指代消解和上下文补全（可选）
        region_code: str       — 用户地区权限码，9位行政区划编码（可选）

    输出：
        UnifiedIntentDict      — 包含 text2sql 子集和 rag 子集
    """

    # ============================================================
    # RAG need_* 字段的关键词集合 — 复用 router_service.py 关键词列表
    # ============================================================

    _DATA_KEYWORDS = [
        "多少", "金额", "收入", "支出", "执行率", "同比", "环比",
        "趋势", "变化", "排名", "各市", "各区县", "各地", "每月",
        "分月", "占比", "比重", "预算执行", "完成多少", "总计多少",
        "增收", "增支",
    ]

    _POLICY_KEYWORDS = [
        "政策", "文件", "规定", "措施", "依据",
    ]

    _CALIBER_KEYWORDS = [
        "口径", "怎么算", "什么意思", "定义", "含义", "如何理解", "怎么理解",
    ]

    _COMPOSITION_KEYWORDS = [
        "构成", "组成", "由哪几部分", "包括哪些", "分类", "分别指", "范围",
    ]

    def __init__(self, llm_client, subject_keywords: List[str], metric_aliases: Dict[str, List[str]]):
        """初始化提取器。

        Args:
            llm_client: LLM 调用客户端，需支持 chat_json(prompt, question) → dict 接口
            subject_keywords: 科目关键词列表，从 projectname.json 动态加载
            metric_aliases: 指标别名映射表，{规范名: [别名列表]}
        """
        self._llm = llm_client
        self._subject_keywords = subject_keywords
        self._metric_aliases = metric_aliases

    # ============================================================
    # 公开方法
    # ============================================================

    def extract(
        self,
        question: str,
        history_messages: Optional[List[dict]] = None,
        region_code: Optional[str] = None,
    ) -> UnifiedIntentDict:
        """主入口：从用户问题中提取统一意图字典。

        流程（对应设计文档 §6）：
        1. 尝试 LLM 结构化提取 → 逐字段规则补全
        2. LLM 失败则全量规则兜底
        3. 拆分投影为 text2sql 子集和 rag 子集

        Args:
            question: 用户问题原文
            history_messages: 历史消息列表，每项 {"role": "...", "content": "..."}
            region_code: 9位行政区划编码（当前版本暂未使用，预留）

        Returns:
            UnifiedIntentDict，包含 text2sql 和 rag 两套子集
        """
        history = history_messages or []

        # 第一阶段：LLM 提取 + 规则补全
        try:
            raw = self._llm_extract(question, history)
            text2sql = self._build_text2sql_from_llm(question, raw)
        except Exception:
            # 第二阶段：全量规则兜底
            raw = self._rule_fallback(question)
            text2sql = self._build_text2sql_from_rules(question, raw)

        # 拆分投影：构造 RAG 子集（只解析 need_* 布尔值 + 透传原问题，不做检索词拼接）
        rag = self._build_rag_fields(question, raw)

        return UnifiedIntentDict(text2sql=text2sql, rag=rag)

    # ============================================================
    # 第一阶段：LLM 提取
    # ============================================================

    def _llm_extract(self, question: str, history: List[dict]) -> dict:
        """第一阶段：LLM 结构化提取。

        复用 dataQuery intent.py 的 INTENT_PROMPT 模板，调用 LLM 输出 JSON。
        扩充了 rag 侧 4 个 need_* 布尔字段。

        Args:
            question: 用户问题原文
            history: 历史消息列表，拼接到 prompt 中辅助指代消解

        Returns:
            LLM 输出的原始 JSON dict

        Raises:
            Exception: LLM 调用失败或输出解析失败时抛出，由外层 catch 后走 _rule_fallback
        """
        history_text = self._build_history_text(history)
        full_prompt = f"历史对话摘要：\n{history_text}\n\n当前问题：\n{question}"
        result = self._llm.chat_json(INTENT_PROMPT, full_prompt)
        if result is None:
            raise ValueError("LLM 返回空结果")
        return result

    def _build_text2sql_from_llm(self, question: str, raw: dict) -> Text2SqlIntent:
        """从 LLM 原始输出构造 Text2SqlIntent，逐字段规则补全。

        复用 dataQuery intent.py:build_query_plan() 的二阶段补全模式：
        LLM 输出优先，LLM 返回 unknown 或空值时用规则函数修正。

        Args:
            question: 用户问题原文
            raw: LLM 输出的原始 dict

        Returns:
            经过规则补全的 Text2SqlIntent
        """
        rule_result = self._rule_fallback(question)

        return Text2SqlIntent(
            time_text=self._nvl(raw.get("time_text"), rule_result.get("time_text", "")),
            time_start=self._nvl(raw.get("start_yyyymm"), rule_result.get("start_yyyymm", "")),
            time_end=self._nvl(raw.get("end_yyyymm"), rule_result.get("end_yyyymm", "")),
            time_grain=self._normalize_unknown(raw.get("time_grain"), rule_result.get("time_grain", "")),
            business_module=self._normalize_unknown(
                raw.get("business_module"), rule_result.get("business_module", "")
            ),
            account_book=self._normalize_unknown(
                raw.get("account_book"), rule_result.get("account_book", "")
            ),
            flow_type=self._normalize_unknown(
                raw.get("flow_type"), rule_result.get("flow_type", "")
            ),
            region_level=self._normalize_unknown(
                raw.get("region_level"), rule_result.get("region_level", "")
            ),
            data_stage=self._normalize_unknown(
                raw.get("data_stage"), rule_result.get("data_stage", "")
            ),
            query_type=str(raw.get("query_type") or rule_result.get("query_type", "summary")),
            subjects=self._normalize_list(
                raw.get("subjects"), rule_result.get("subjects", [])
            ),
            metrics=self._normalize_list(
                raw.get("metrics"), rule_result.get("metrics", [])
            ),
            regions=self._normalize_list(
                raw.get("regions"), rule_result.get("regions", [])
            ),
            compare_dimension=str(raw.get("compare_dimension") or rule_result.get("compare_dimension", "none")),
            compare_operator=str(raw.get("compare_operator") or rule_result.get("compare_operator", "none")),
            chart_hint=str(raw.get("chart_hint") or rule_result.get("chart_hint", "auto")),
            top_n=int(raw.get("top_n", 0) or rule_result.get("top_n", 0)),
        )

    # ============================================================
    # 第二阶段：规则兜底
    # ============================================================

    def _rule_fallback(self, question: str) -> dict:
        """第二阶段：全量规则兜底。

        LLM 提取失败时调用。依次调用全部 _extract_* 规则函数，
        同时用 router_service.py 的关键词集合判断 rag 侧 need_* 布尔字段。

        返回 dict 字段结构与 LLM 输出一致。

        Args:
            question: 用户问题原文

        Returns:
            规则提取的原始 dict
        """
        start_yyyymm, end_yyyymm, time_text = self._extract_time_range(question)
        budget_scope = self._extract_budget_scope(question)
        business_module = self._extract_business_module(question)
        account_book = self._extract_account_book(question, budget_scope)
        flow_type = self._extract_flow_type(question, budget_scope)
        data_stage = self._extract_data_stage(question, business_module)
        regions = self._extract_regions(question)
        region_level = self._extract_region_level(question, regions)
        metrics = self._extract_metrics(question)
        subjects = self._extract_subjects(question, metrics)
        query_type, chart_hint, compare_dimension = self._infer_query_type_and_chart(question, subjects)

        return {
            "query_type": query_type,
            "chart_hint": chart_hint,
            "compare_dimension": compare_dimension,
            "time_text": time_text,
            "start_yyyymm": start_yyyymm,
            "end_yyyymm": end_yyyymm,
            "budget_scope": budget_scope,
            "business_module": business_module,
            "account_book": account_book,
            "flow_type": flow_type,
            "region_level": region_level,
            "data_stage": data_stage,
            "time_grain": self._extract_time_grain(question),
            "subjects": subjects,
            "metrics": metrics,
            "regions": regions,
            "compare_operator": self._guess_compare_operator(question),
            "top_n": self._extract_top_n(question),
            "need_policy_basis": self._has_any_keyword(question, self._POLICY_KEYWORDS),
            "need_caliber_explanation": self._has_any_keyword(question, self._CALIBER_KEYWORDS),
            "need_composition": self._has_any_keyword(question, self._COMPOSITION_KEYWORDS),
            "need_data_value": self._has_any_keyword(question, self._DATA_KEYWORDS),
        }

    def _build_text2sql_from_rules(self, question: str, raw: dict) -> Text2SqlIntent:
        """从规则兜底结果构造 Text2SqlIntent。

        Args:
            question: 用户问题原文（当前未使用，预留）
            raw: _rule_fallback 返回的 dict

        Returns:
            Text2SqlIntent
        """
        return Text2SqlIntent(
            time_text=str(raw.get("time_text", "")),
            time_start=str(raw.get("start_yyyymm", "")),
            time_end=str(raw.get("end_yyyymm", "")),
            time_grain=str(raw.get("time_grain", "")),
            business_module=str(raw.get("business_module", "")),
            account_book=str(raw.get("account_book", "")),
            flow_type=str(raw.get("flow_type", "")),
            region_level=str(raw.get("region_level", "")),
            data_stage=str(raw.get("data_stage", "")),
            query_type=str(raw.get("query_type", "summary")),
            subjects=list(raw.get("subjects", [])),
            metrics=list(raw.get("metrics", [])),
            regions=list(raw.get("regions", [])),
            compare_dimension=str(raw.get("compare_dimension", "none")),
            compare_operator=str(raw.get("compare_operator", "none")),
            chart_hint=str(raw.get("chart_hint", "auto")),
            top_n=int(raw.get("top_n", 0)),
        )

    # ============================================================
    # 规则提取函数 — 全部从 dataQuery intent.py 迁移
    # ============================================================

    def _extract_time_range(self, question: str) -> tuple:
        """从问题中提取时间范围。

        迁移自 intent.py:_extract_time_range()。
        支持：2019年10-12月 / 2019年3月 / 2019年全年 / 2019年。

        Returns:
            (start_yyyymm, end_yyyymm, time_text)
        """
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

    def _extract_budget_scope(self, question: str) -> str:
        """提取预算口径，例如一般公共预算、政府性基金等。

        迁移自 intent.py:_extract_budget_scope()。
        """
        scope_keywords = [
            "一般公共预算收入", "一般公共预算支出",
            "政府性基金收入", "政府性基金支出",
            "国有资本经营预算收入", "国有资本经营预算支出",
            "社会保险基金收入", "社会保险基金支出",
            "一般公共预算", "政府性基金",
            "国有资本经营预算", "社会保险基金",
        ]
        for scope in scope_keywords:
            if scope in question:
                return scope
        return ""

    def _extract_regions(self, question: str) -> List[str]:
        """从问题中识别地区名称。

        迁移自 intent.py:_extract_regions()。
        """
        known_regions = [
            "全省", "河北省", "省本级",
            "石家庄市", "唐山市", "保定市", "邯郸市",
        ]
        return [name for name in known_regions if name in question]

    def _extract_metrics(self, question: str) -> List[str]:
        """从问题中识别指标名称。

        迁移自 intent.py:_extract_metrics()。
        """
        if self._metric_aliases:
            alias_groups = [
                (canonical, aliases)
                for canonical, aliases in self._metric_aliases.items()
            ]
        else:
            alias_groups = [
                ("预算执行率", ["预算执行率", "执行率", "预算完成率"]),
                ("本月金额", ["本月金额", "当月金额", "本月数", "本月执行金额", "本月执行数"]),
                ("累计金额", ["累计金额", "累计收入", "累计支出", "累计执行金额", "累计数", "累计执行数"]),
                ("同比增幅", ["同比增额", "同比增长率", "同比增长", "同比"]),
                ("环比增幅", ["环比增额", "环比增长率", "环比增长", "环比"]),
                ("预算数", ["预算数", "年初预算", "调整预算"]),
                ("总计", ["总计", "合计", "总计多少", "合计多少"]),
                ("金额", ["金额"]),
            ]

        found: List[str] = []
        for canonical_name, aliases in alias_groups:
            if any(alias in question for alias in aliases):
                if canonical_name == "金额" and any(
                    item in found for item in ["本月金额", "累计金额"]
                ):
                    continue
                found.append(canonical_name)
        return self._dedupe_keep_order(found)

    def _extract_subjects(self, question: str, metrics: List[str]) -> List[str]:
        """从问题中提取科目或项目名称。

        迁移自 intent.py:_extract_subjects()。
        """
        text = question
        removable_words = [
            self._extract_budget_scope(question),
            *self._extract_regions(question),
            self._extract_time_range(question)[2],
            "哪个大", "谁大", "相差多少", "分别是多少", "各是多少",
            "是多少", "对比", "比较", "其中", "的",
        ]
        for word in removable_words:
            if word:
                text = text.replace(word, " ")

        for phrase in [
            "一般公共预算收入中", "一般公共预算支出中",
            "一般公共预算中", "政府性基金中",
        ]:
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
            if candidate and not self._is_non_subject(candidate):
                subjects.append(candidate)
        return self._dedupe_keep_order(subjects)

    _NON_SUBJECT_PATTERNS = [
        "是什么", "什么意思", "怎么理解", "如何理解",
        "怎么说", "怎么算", "如何计算",
        "由哪几部分", "包括哪些", "有哪些",
        "多少", "多少钱", "总计多少", "合计多少",
        "你好", "您好", "谢谢", "再见",
        "你是谁", "你能做什么",
        "天气", "讲个笑话",
        "早上好", "晚上好",
    ]

    @classmethod
    def _is_non_subject(cls, candidate: str) -> bool:
        """判断候选文本是否为非科目模式（疑问词/问候语等）。"""
        for pattern in cls._NON_SUBJECT_PATTERNS:
            if pattern in candidate:
                return True
        if len(candidate) < 2:
            return True
        return False

    def _extract_business_module(self, question: str) -> str:
        """提取业务模块。

        迁移自 intent.py:_extract_business_module()。
        """
        if "预算执行" in question:
            return "预算执行"
        if "决算" in question:
            return "决算"
        if "预算调整" in question:
            return "预算调整"
        if "预算草案" in question or "草案" in question:
            return "预算草案"
        return ""

    def _extract_account_book(self, question: str, budget_scope: str) -> str:
        """提取四本账类型。

        迁移自 intent.py:_extract_account_book()。
        """
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

    def _extract_flow_type(self, question: str, budget_scope: str) -> str:
        """提取收支方向。

        迁移自 intent.py:_extract_flow_type()。
        """
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

    def _extract_region_level(self, question: str, regions: List[str]) -> str:
        """提取地区层级。

        迁移自 intent.py:_extract_region_level()。
        """
        if "全省" in question or "河北省" in question:
            return "全省"
        if "省本级" in question or "省级" in question:
            return "省本级"
        if "各市" in question or any(region.endswith("市") for region in regions):
            return "地市"
        if "各区县" in question or "区县" in question:
            return "区县"
        return ""

    def _extract_data_stage(self, question: str, business_module: str) -> str:
        """提取数据阶段。

        迁移自 intent.py:_extract_data_stage()。
        """
        if "执行率" in question or "完成情况" in question:
            return "完成情况"
        if "预算数" in question or "年初预算" in question or "调整预算" in question:
            return "预算数"
        if "草案" in question:
            return "草案数"
        if business_module == "预算执行":
            return "执行数"
        return ""

    def _extract_time_grain(self, question: str) -> str:
        """推断问题关注的是月度还是年度。

        迁移自 intent.py:_extract_time_grain()。
        """
        if any(word in question for word in ["每月", "各月", "分月", "逐月"]):
            return "month"
        if re.search(r"\d{4}年\d{1,2}月", question):
            return "month"
        if "全年" in question or re.search(r"\d{4}年", question):
            return "year"
        return ""

    def _extract_top_n(self, question: str) -> int:
        """从问题中提取前 N 名里的 N。

        迁移自 intent.py:_extract_top_n()。
        """
        match = re.search(r"前(\d+)", question)
        if match:
            return int(match.group(1))
        return 0

    def _guess_compare_operator(self, question: str) -> str:
        """根据问题措辞推断比较操作类型。

        迁移自 intent.py:_guess_compare_operator()。
        """
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

    def _infer_query_type_and_chart(self, question: str, subjects: List[str]) -> tuple:
        """基于问题关键词推断查询类型、图表类型和比较维度。

        迁移自 intent.py:fallback_query_plan() 的逻辑。
        """
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

        if len(subjects) >= 2 and compare_dimension == "none":
            compare_dimension = "subject"
            query_type = "comparison"

        return query_type, chart_hint, compare_dimension

    @staticmethod
    def _has_any_keyword(question: str, keywords: List[str]) -> bool:
        """判断问题是否包含关键词集合中的任意一个。"""
        return any(word in question for word in keywords)

    # ============================================================
    # 拆分投影：构造 RAG 子集
    # ============================================================

    def _build_rag_fields(self, question: str, raw: dict) -> RagIntent:
        """第二阶段：从 LLM 原始输出解析 RAG 子集。

        只做 need_* 布尔值解析 + 透传原问题，不做检索词拼接。
        search_query 和 subject_keywords 的构造由 RAG Agent 内部自行处理。

        对应设计文档 §3.3。
        """
        return RagIntent(
            need_policy_basis=self._resolve_need_field(
                raw.get("need_policy_basis"),
                self._has_any_keyword(question, self._POLICY_KEYWORDS),
            ),
            need_caliber_explanation=self._resolve_need_field(
                raw.get("need_caliber_explanation"),
                self._has_any_keyword(question, self._CALIBER_KEYWORDS),
            ),
            need_composition=self._resolve_need_field(
                raw.get("need_composition"),
                self._has_any_keyword(question, self._COMPOSITION_KEYWORDS),
            ),
            need_data_value=self._resolve_need_field(
                raw.get("need_data_value"),
                self._has_any_keyword(question, self._DATA_KEYWORDS),
            ),
            original_question=question,
        )

    @staticmethod
    def _resolve_need_field(llm_value, rule_default: bool) -> bool:
        """解析 need_* 布尔字段：LLM 优先，规则兜底。"""
        if llm_value is None:
            return rule_default
        if isinstance(llm_value, bool):
            return llm_value
        if isinstance(llm_value, str):
            lowered = llm_value.strip().lower()
            if lowered in ("true", "yes", "1"):
                return True
            if lowered in ("false", "no", "0"):
                return False
        return rule_default

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _build_history_text(history: List[dict]) -> str:
        """将历史消息列表拼接为文本，限制最近 6 轮。"""
        parts: List[str] = []
        for item in history[-6:]:
            role = item.get("role", "")
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            parts.append(f"{role}: {content}")
        return "\n".join(parts) or "无"

    @staticmethod
    def _normalize_unknown(value, fallback: str) -> str:
        """把 LLM 输出的 unknown 或空值替换为规则推断结果。

        复用 dataQuery intent.py:_normalize_unknown()。
        """
        text = str(value or "").strip()
        if not text or text.lower() == "unknown":
            return fallback
        return text

    @staticmethod
    def _normalize_list(raw_value, fallback: List[str]) -> List[str]:
        """把 LLM 输出的列表与规则提取列表合并去重。

        复用 dataQuery intent.py:_normalize_list() 的逻辑：
        - LLM 有值就用 LLM 的结果
        - LLM 返回空列表或 None 时才用规则兜底
        """
        values: List[str] = []
        if isinstance(raw_value, list):
            values.extend(str(item).strip() for item in raw_value if str(item).strip())
        elif isinstance(raw_value, str) and raw_value.strip():
            values.append(raw_value.strip())
        values = UnifiedIntentExtractor._dedupe_keep_order(values)
        return values if values else list(fallback)

    @staticmethod
    def _dedupe_keep_order(items: List[str]) -> List[str]:
        """列表去重，同时保持原始顺序。

        复用 dataQuery intent.py:_dedupe_keep_order()。
        """
        output: List[str] = []
        seen = set()
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            output.append(item)
        return output

    @staticmethod
    def _nvl(value, fallback):
        """如果 value 为空则取 fallback。用于字符串字段的 LLM 优先 + 规则补全。"""
        if value is None:
            return fallback
        text = str(value).strip()
        return text if text else fallback
