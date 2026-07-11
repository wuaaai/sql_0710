"""RAG 槽位增强器。

从 RAG 检索到的知识库文档片段中提取财政领域实体，
回填到 Text2SQL 意图中缺失的槽位。

对应设计文档：结果融合层设计.md §5
"""

import re
from collections import Counter, defaultdict
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from src.domain.intent.unified_intent import Text2SqlIntent, UnifiedIntentDict
from src.domain.fusion.fusion_result import RagEnrichmentLog


class RagSlotEnricher:
    """RAG 槽位增强器。

    输入:
        intent_v1: UnifiedIntentDict       # 第一版意图
        snippets: List[KnowledgeSnippet]    # RAG 文档片段
        user_question: str                  # 原始问题

    输出:
        intent_v2: UnifiedIntentDict        # 增强后意图
        log: RagEnrichmentLog               # 增强日志
    """

    # 最低相关度阈值 — 低于此值的 snippet 不参与槽位提取
    MIN_RELEVANCE_SCORE = 0.3

    # 高置信投票阈值 — 至少出现次数
    HIGH_CONFIDENCE_THRESHOLD = 2

    def __init__(
        self,
        metric_aliases: Dict[str, List[str]],
        subject_keywords: Optional[List[str]] = None,
    ):
        """初始化增强器。

        Args:
            metric_aliases: 指标别名映射表，{规范名: [别名列表]}
            subject_keywords: 已知科目关键词列表（可选）
        """
        self._metric_aliases = metric_aliases
        self._subject_keywords = subject_keywords or []

    # ============================================================
    # 公开方法
    # ============================================================

    def enrich(
        self,
        intent_v1: UnifiedIntentDict,
        snippets: List,
        user_question: str,
    ) -> Tuple[UnifiedIntentDict, RagEnrichmentLog]:
        """RAG 反哺主入口。

        流程：[A]提取候选值 → [B]投票 → [C]补全

        Args:
            intent_v1: 第一版意图
            snippets: RAG 检索到的 KnowledgeSnippet 列表
            user_question: 原始问题文本

        Returns:
            (intent_v2, enrichment_log)
        """
        # [A] 提取候选值 + 追踪来源
        candidates, sources = self._extract_candidates(snippets, user_question)

        # [B] 投票筛选
        voted = self._vote(candidates)

        # [C] 补全返回
        return self._fill(intent_v1, voted, candidates, sources)

    # ============================================================
    # [A] 候选提取
    # ============================================================

    def _extract_candidates(
        self, snippets: List, user_question: str
    ) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
        """从所有 snippet 中提取槽位候选值。

        与原始问题交叉校验：RAG 提取的值如果与问题已有信息矛盾，不采纳。
        对应设计文档 §8 方案3（防污染）。

        Args:
            snippets: RAG 文档片段列表
            user_question: 原始问题文本

        Returns:
            (candidates, sources)：候选值字典和来源追踪字典
        """
        candidates: Dict[str, List[str]] = defaultdict(list)
        sources: Dict[str, List[str]] = defaultdict(list)

        # 从原始问题提取"锚点"信息
        question_years = set(re.findall(r"(\d{4})年", user_question))
        question_account_books = self._extract_account_books(user_question)

        for s in snippets:
            # 低相关度片段跳过（设计文档 §8 方案2）
            if getattr(s, "score", 1.0) < self.MIN_RELEVANCE_SCORE:
                continue

            text: str = getattr(s, "content", "")
            source: str = getattr(s, "source", "")
            if not text:
                continue

            # 时间 — 如果问题已有年份，只提取相差 ≤1 年的（方案3防污染）
            years_in_doc = re.findall(r"(\d{4})年", text)
            if question_years:
                q_year = int(list(question_years)[0])
                years_in_doc = [
                    y for y in years_in_doc if abs(int(y) - q_year) <= 1
                ]
            for y in years_in_doc:
                candidates["time"].append(f"{y}年")
                sources["time"].append(source)

            # 地区层级
            for kw in ["全省", "省本级", "各市", "各区县"]:
                if kw in text:
                    candidates["region_level"].append(kw)
                    sources["region_level"].append(source)

            # 指标 — 别名匹配
            for canonical, aliases in self._metric_aliases.items():
                if any(a in text for a in aliases):
                    candidates["metrics"].append(canonical)
                    sources["metrics"].append(source)

            # 四本账 — 与问题锚点交叉校验（方案3）
            for kw in ["一般公共预算", "政府性基金", "国有资本经营预算", "社会保险基金"]:
                if kw in text:
                    # 如果问题已有四本账且与文档不同，跳过
                    if question_account_books and kw not in question_account_books:
                        continue
                    candidates["account_book"].append(kw)
                    sources["account_book"].append(source)

            # 数据阶段
            for kw, label in [
                ("执行", "执行数"), ("预算数", "预算数"), ("年初预算", "预算数"),
                ("草案", "草案数"), ("完成情况", "完成情况"),
            ]:
                if kw in text:
                    candidates["data_stage"].append(label)
                    sources["data_stage"].append(source)

            # 业务模块
            for kw in ["预算执行", "决算", "预算调整", "预算草案"]:
                if kw in text:
                    candidates["business_module"].append(kw)
                    sources["business_module"].append(source)

            # 科目 — 词典匹配 + 正则（白名单过滤，只采纳已知科目词典内的值）
            for keyword in self._subject_keywords:
                if keyword in text and keyword not in user_question:
                    candidates["subjects"].append(keyword)
                    sources["subjects"].append(source)
            # 正则提取也加白名单过滤，只采纳包含已知科目关键词的匹配
            for m in re.finditer(r"([一-龥]{2,18})(收入|支出)", text):
                term = m.group(0)
                if term not in user_question and self._is_known_subject(term):
                    candidates["subjects"].append(term)
                    sources["subjects"].append(source)

        return dict(candidates), dict(sources)

    # ============================================================
    # [B] 投票
    # ============================================================

    def _vote(self, candidates: Dict[str, List[str]]) -> Dict[str, Tuple[Optional[str], float]]:
        """对每个槽位统计频次，只采纳频次≥2的高置信候选。

        平局时宁可少补，不可错补。
        对应设计文档 §8 方案7。

        Args:
            candidates: {slot_name: [value1, value1, value2, ...]}

        Returns:
            {slot_name: (value, confidence)}
            value 为 None 表示投票失败（平局或频次不足）
        """
        result: Dict[str, Tuple[Optional[str], float]] = {}
        for slot, values in candidates.items():
            if not values:
                continue
            counter = Counter(values)
            top = counter.most_common(2)

            if len(top) == 1:
                # 只有一个候选值
                result[slot] = (
                    top[0][0],
                    0.9 if top[0][1] >= self.HIGH_CONFIDENCE_THRESHOLD else 0.5,
                )
            elif top[0][1] > top[1][1]:
                # 有明显胜出者
                result[slot] = (
                    top[0][0],
                    0.9 if top[0][1] >= self.HIGH_CONFIDENCE_THRESHOLD else 0.5,
                )
            elif top[0][1] == 1 and top[1][1] == 1:
                # 不同候选值各出现一次 → 取第一个，低置信
                result[slot] = (top[0][0], 0.5)
            else:
                # 平局 → 不补全（方案7）
                result[slot] = (None, 0.0)

        return result

    # ============================================================
    # [C] 补全
    # ============================================================

    def _fill(
        self,
        intent_v1: UnifiedIntentDict,
        voted: Dict[str, Tuple[Optional[str], float]],
        candidates: Dict[str, List[str]],
        sources: Dict[str, List[str]],
    ) -> Tuple[UnifiedIntentDict, RagEnrichmentLog]:
        """用投票结果补全 intent_v1 中的空槽位。

        只补空字段，非空保持原值。
        对应设计文档 §3.2 补全原则。

        Args:
            intent_v1: 第一版意图
            voted: 投票结果 {slot: (value, confidence)}
            candidates: 原始候选值（用于日志）
            sources: 来源追踪（用于日志）

        Returns:
            (intent_v2, enrichment_log)
        """
        t2s = deepcopy(intent_v1.text2sql)
        filled_slots: List[str] = []
        log_sources: Dict[str, str] = {}

        # metrics — 只补空列表
        if not t2s.metrics and "metrics" in voted:
            val, conf = voted["metrics"]
            if val and conf >= 0.5:
                t2s.metrics = [val]
                filled_slots.append("metrics")
                log_sources["metrics"] = self._top_source(sources.get("metrics", []))

        # region_level — 只补空字符串
        if not t2s.region_level and "region_level" in voted:
            val, conf = voted["region_level"]
            if val and conf >= 0.5:
                t2s.region_level = val
                filled_slots.append("region_level")
                log_sources["region_level"] = self._top_source(sources.get("region_level", []))

        # time — 只补空，同时计算 start/end
        if not t2s.time_text and "time" in voted:
            val, conf = voted["time"]
            if val and conf >= 0.5:
                t2s.time_text = val
                t2s.time_start, t2s.time_end = self._calc_time_range(val)
                filled_slots.append("time")
                log_sources["time"] = self._top_source(sources.get("time", []))

        # account_book
        if not t2s.account_book and "account_book" in voted:
            val, conf = voted["account_book"]
            if val and conf >= 0.5:
                t2s.account_book = val
                filled_slots.append("account_book")
                log_sources["account_book"] = self._top_source(sources.get("account_book", []))

        # data_stage
        if not t2s.data_stage and "data_stage" in voted:
            val, conf = voted["data_stage"]
            if val and conf >= 0.5:
                t2s.data_stage = val
                filled_slots.append("data_stage")
                log_sources["data_stage"] = self._top_source(sources.get("data_stage", []))

        # business_module
        if not t2s.business_module and "business_module" in voted:
            val, conf = voted["business_module"]
            if val and conf >= 0.5:
                t2s.business_module = val
                filled_slots.append("business_module")
                log_sources["business_module"] = self._top_source(sources.get("business_module", []))

        # subjects — 合并补全（不去掉已有的）
        if "subjects" in voted:
            val, conf = voted["subjects"]
            if val and conf >= 0.5 and val not in t2s.subjects:
                t2s.subjects = t2s.subjects + [val]
                filled_slots.append("subjects")
                log_sources["subjects"] = self._top_source(sources.get("subjects", []))

        # 构造候选值日志（转为可序列化格式）
        log_candidates = {
            slot: [(str(v), cnt) for v, cnt in Counter(vals).most_common()]
            for slot, vals in candidates.items()
        }

        return (
            UnifiedIntentDict(text2sql=t2s, rag=intent_v1.rag),
            RagEnrichmentLog(
                filled_slots=filled_slots,
                candidates=log_candidates,
                sources=log_sources,
            ),
        )

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _calc_time_range(time_text: str) -> Tuple[str, str]:
        """从时间文本计算 start_yyyymm 和 end_yyyymm。

        Args:
            time_text: 例 "2025年" / "2025年3月"

        Returns:
            (start_yyyymm, end_yyyymm)
        """
        # "2025年3月至7月"
        m = re.search(r"(\d{4})年(\d{1,2})[月至到-]+(\d{1,2})月?", time_text)
        if m:
            return f"{m.group(1)}{int(m.group(2)):02d}", f"{m.group(1)}{int(m.group(3)):02d}"
        # "2025年3月"
        m = re.search(r"(\d{4})年(\d{1,2})月", time_text)
        if m:
            ym = f"{m.group(1)}{int(m.group(2)):02d}"
            return ym, ym
        # "2025年全年" / "2025年"
        m = re.search(r"(\d{4})年", time_text)
        if m:
            return f"{m.group(1)}01", f"{m.group(1)}12"
        return "", ""

    @staticmethod
    def _extract_account_books(question: str) -> List[str]:
        """从问题中提取四本账关键词作为锚点。"""
        result = []
        for kw in ["一般公共预算", "政府性基金", "国有资本经营预算", "社会保险基金"]:
            if kw in question:
                result.append(kw)
        return result

    @staticmethod
    def _top_source(source_list: List[str]) -> str:
        """从来源列表中取出现次数最多的。"""
        if not source_list:
            return ""
        return Counter(source_list).most_common(1)[0][0]

    def _is_known_subject(self, term: str) -> bool:
        """检查提取的科目是否在已知词典中（白名单过滤）。

        Args:
            term: 正则提取的候选科目，如"卫生健康支出"

        Returns:
            True 表示该科目在已知词典中
        """
        # 精确匹配
        if term in self._subject_keywords:
            return True
        # 子串匹配 — 已知科目包含提取的 term 或 term 包含已知科目
        for kw in self._subject_keywords:
            if term in kw or kw in term:
                return True
        return False
