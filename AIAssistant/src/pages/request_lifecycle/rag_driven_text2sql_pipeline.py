"""RAG 反哺 Text2SQL 管线。

模块总入口，接收用户问题，内部完成意图提取、RAG 检索、
槽位反哺补全、text2sql 二次查询，输出最终结构化回答。

对应设计文档：结果融合层设计.md §4
"""

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.domain.intent.unified_intent import Text2SqlIntent, UnifiedIntentDict
from src.domain.fusion.fusion_result import Citation, FusionResult, RagEnrichmentLog


class RagDrivenText2SqlPipeline:
    """RAG 反哺 Text2SQL 管线 — 模块总入口。

    输入:
        question: str                 # 用户问题
        history_messages: List[dict]   # 历史消息（可选）
        region_code: str              # 地区权限码（可选）

    输出:
        FusionResult                  # 最终回答 + 元信息
    """

    # ============================================================
    # 超时配置（对应设计文档 §8 方案8）
    # ============================================================
    EXTRACT_TIMEOUT = 15
    RAG_TIMEOUT = 10
    TEXT2SQL_TIMEOUT = 30
    CACHE_TTL = 300  # 缓存 5 分钟

    def __init__(
        self,
        extractor,
        rag_service,
        enricher,
        text2sql_pipeline,
    ):
        """初始化管线。

        Args:
            extractor: UnifiedIntentExtractor 实例
            rag_service: RagService 实例
            enricher: RagSlotEnricher 实例
            text2sql_pipeline: text2sql 执行管线（需支持 run(intent) → SqlExecutionResult）
        """
        self._extractor = extractor
        self._rag_service = rag_service
        self._enricher = enricher
        self._text2sql = text2sql_pipeline
        self._cache: Dict[str, FusionResult] = {}

    # ============================================================
    # 公开方法 — 主入口
    # ============================================================

    def run(
        self,
        question: str,
        history_messages: Optional[List[dict]] = None,
        region_code: Optional[str] = None,
    ) -> FusionResult:
        """执行完整管线。

        流程：
        1. 意图提取 → intent_v1
        2. 守卫检查
        3. 槽位齐全 → text2sql + RAG 并行
        4. 槽位不全 → RAG 检索 → 反哺增强 → 重查

        Args:
            question: 用户问题原文
            history_messages: 历史消息（可选）
            region_code: 地区权限码（可选）

        Returns:
            FusionResult
        """
        # 缓存检查（设计文档 §8 方案8）
        cache_key = self._cache_key(question, region_code)
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 步骤1: 意图提取
        try:
            intent_v1 = self._extractor.extract(question, history_messages, region_code)
        except Exception as e:
            return self._fallback(f"意图提取失败: {e}")

        # 守卫: 无业务意图 → 兜底
        if not self._has_business_intent(intent_v1):
            result = self._fallback()
            self._cache_set(cache_key, result)
            return result

        t2s = intent_v1.text2sql
        rag_intent = intent_v1.rag

        # 纯 RAG 问题（无 subjects 也无 metrics）
        if not t2s.subjects and not t2s.metrics:
            result = self._rag_only_path(rag_intent, question)
            self._cache_set(cache_key, result)
            return result

        # 槽位齐全 → 并行执行（设计文档 §8 方案1）
        if self._slots_ready(t2s):
            result = self._parallel_path(intent_v1, question, region_code)
            self._cache_set(cache_key, result)
            return result

        # 槽位不全 → RAG 反哺路径
        result = self._enrichment_path(intent_v1, question, region_code)
        self._cache_set(cache_key, result)
        return result

    # ============================================================
    # 路径1: 槽位齐全 — 并行执行
    # ============================================================

    def _parallel_path(
        self, intent_v1: UnifiedIntentDict, question: str, region_code: Optional[str]
    ) -> FusionResult:
        """text2sql 和 RAG 并行执行。"""
        sql_result = None
        rag_result = None

        with ThreadPoolExecutor(max_workers=2) as pool:
            sql_future = pool.submit(
                self._text2sql_run_safe, intent_v1.text2sql
            )
            rag_future = pool.submit(
                self._rag_search_safe, intent_v1.rag
            )
            try:
                sql_result = sql_future.result(timeout=self.TEXT2SQL_TIMEOUT)
            except FutureTimeout:
                sql_result = None
            try:
                rag_result = rag_future.result(timeout=self.RAG_TIMEOUT)
            except FutureTimeout:
                rag_result = None

        return self._build_final_answer(
            sql_result, rag_result, intent_v1, question
        )

    # ============================================================
    # 路径2: 槽位不全 — RAG 反哺
    # ============================================================

    def _enrichment_path(
        self, intent_v1: UnifiedIntentDict, question: str, region_code: Optional[str]
    ) -> FusionResult:
        """先跑 RAG，用结果反哺 text2sql 槽位，再重查。"""
        # RAG 检索
        rag_result = self._rag_search_safe(intent_v1.rag)

        # RAG 质量检查（设计文档 §8 方案2）
        can_enrich, degrade_reason = self._can_enrich(rag_result)
        if not can_enrich:
            # 降级：直接用 v1 查（可能槽位不全 → clarify）
            sql_result = self._text2sql_run_safe(intent_v1.text2sql)
            return self._build_final_answer(
                sql_result, rag_result, intent_v1, question,
                degrade_reason=degrade_reason,
            )

        # 反哺增强
        intent_v2, enrich_log = self._enricher.enrich(
            intent_v1, rag_result.snippets, question
        )

        # 增强后槽位齐全 → 重查 text2sql
        if self._slots_ready(intent_v2.text2sql):
            sql_result = self._text2sql_run_safe(intent_v2.text2sql)
        else:
            sql_result = None

        return self._build_final_answer(
            sql_result, rag_result, intent_v2, question,
            enrich_log=enrich_log,
        )

    # ============================================================
    # 路径3: 纯 RAG
    # ============================================================

    def _rag_only_path(self, rag_intent, question: str) -> FusionResult:
        """纯 RAG 问题 — 直接返回 RAG 回答。"""
        rag_result = self._rag_search_safe(rag_intent)
        if rag_result and rag_result.snippets:
            answer = rag_result.answer or self._format_snippets(rag_result.snippets)
            citations = [
                Citation(type="rag", label="政策依据", detail=s.source)
                for s in rag_result.snippets[:3]
            ]
            return FusionResult(
                answer=answer,
                answer_mode="rag",
                citations=citations,
                overall_confidence=self._calc_rag_confidence(rag_result),
                generated_at=self._now_iso(),
            )
        return self._clarify(None, "RAG 未检索到相关信息")

    # ============================================================
    # 最终回答组装（对应设计文档 §4 步骤4）
    # ============================================================

    def _build_final_answer(
        self,
        sql_result,
        rag_result,
        intent: UnifiedIntentDict,
        question: str,
        enrich_log: Optional[RagEnrichmentLog] = None,
        degrade_reason: str = "",
    ) -> FusionResult:
        """根据两路结果组装最终回答。"""
        has_sql = sql_result is not None and getattr(sql_result, "success", False) and getattr(sql_result, "rows", [])
        has_rag = rag_result is not None and getattr(rag_result, "success", False) and getattr(rag_result, "snippets", [])

        # both 模式：两边都有结果（设计文档 §8 方案4）
        if has_sql and has_rag:
            return self._answer_both(sql_result, rag_result, enrich_log, degrade_reason)

        # sql 模式
        if has_sql:
            return self._answer_sql(sql_result, enrich_log, degrade_reason)

        # rag 模式
        if has_rag:
            return self._answer_rag(rag_result, degrade_reason)

        # clarify 模式：两边都没结果
        t2s = intent.text2sql
        missing = self._find_missing_slots(t2s)
        return self._clarify(missing, degrade_reason)

    # ============================================================
    # answer 组装方法
    # ============================================================

    def _answer_both(self, sql_result, rag_result, enrich_log, degrade_reason) -> FusionResult:
        """both 模式：数据表格 + RAG 解读 + 增强日志。"""
        parts = []
        citations = []

        # 数据表格
        table = self._format_table(sql_result.rows, sql_result.source_table)
        parts.append(table)
        citations.append(Citation(type="sql", label="数据来源", detail=getattr(sql_result, "source_table", "")))

        # 增强日志标注
        if enrich_log and enrich_log.filled_slots:
            parts.append(f"\n> 本次查询通过知识库文档补全了以下条件：{'、'.join(enrich_log.filled_slots)}")

        # RAG 解读
        rag_text = rag_result.answer or self._format_snippets(rag_result.snippets)
        parts.append(f"\n## 政策解读\n{rag_text}")
        for s in rag_result.snippets[:3]:
            citations.append(Citation(type="rag", label="政策依据", detail=s.source))

        return FusionResult(
            answer="\n".join(parts),
            answer_mode="both",
            sql_data=sql_result.rows,
            citations=citations,
            enrichment_log=enrich_log,
            overall_confidence=0.92,
            degrade_reason=degrade_reason,
            generated_at=self._now_iso(),
        )

    def _answer_sql(self, sql_result, enrich_log, degrade_reason) -> FusionResult:
        """sql 模式：纯数据回答。"""
        table = self._format_table(sql_result.rows, getattr(sql_result, "source_table", ""))
        return FusionResult(
            answer=table,
            answer_mode="sql",
            sql_data=sql_result.rows,
            citations=[Citation(type="sql", label="数据来源", detail=getattr(sql_result, "source_table", ""))],
            enrichment_log=enrich_log,
            overall_confidence=0.95,
            degrade_reason=degrade_reason,
            generated_at=self._now_iso(),
        )

    def _answer_rag(self, rag_result, degrade_reason) -> FusionResult:
        """rag 模式：纯文档回答。"""
        answer = rag_result.answer or self._format_snippets(rag_result.snippets)
        citations = [Citation(type="rag", label="政策依据", detail=s.source) for s in rag_result.snippets[:3]]
        return FusionResult(
            answer=answer,
            answer_mode="rag",
            citations=citations,
            overall_confidence=self._calc_rag_confidence(rag_result),
            degrade_reason=degrade_reason,
            generated_at=self._now_iso(),
        )

    def _clarify(self, missing_slots=None, degrade_reason="") -> FusionResult:
        """clarify 模式：补全引导。"""
        missing = missing_slots or []
        labels = {"subject": "科目", "metric": "指标", "flow_direction": "收支方向",
                   "region_level": "地区层级", "time": "年份"}
        missing_labels = [labels.get(s, s) for s in missing]
        prompt = f"请补充：{'、'.join(missing_labels)}。例如：2025年全省卫生健康支出的执行金额是多少" if missing else "请提供更多查询条件"
        return FusionResult(
            answer=f"当前信息不足以查询，请补充以下条件：{'、'.join(missing_labels)}。",
            answer_mode="clarify",
            slot_missing=missing,
            clarify_prompt=prompt,
            overall_confidence=0.0,
            degrade_reason=degrade_reason,
            generated_at=self._now_iso(),
        )

    def _fallback(self, reason: str = "") -> FusionResult:
        """兜底模式。"""
        return FusionResult(
            answer="您好！我是河北省财政智能助手，可以帮您查询财政数据、解读预算政策。您可以问我：\n- 2025年全省一般公共预算收入是多少\n- 卫生健康支出的构成有哪些\n- 减税降费政策有哪些变化",
            answer_mode="fallback",
            overall_confidence=0.0,
            degrade_reason=reason,
            generated_at=self._now_iso(),
        )

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _has_business_intent(intent: UnifiedIntentDict) -> bool:
        """判断是否有业务意图（守卫层）。"""
        t2s = intent.text2sql
        rag = intent.rag
        return bool(
            t2s.subjects or t2s.metrics
            or rag.need_composition or rag.need_policy_basis or rag.need_caliber_explanation
        )

    @staticmethod
    def _slots_ready(t2s: Text2SqlIntent) -> bool:
        """检查四槽位是否齐全。"""
        return bool(
            t2s.subjects and t2s.metrics
            and t2s.flow_type in ("收入", "支出")
            and t2s.region_level
        )

    @staticmethod
    def _find_missing_slots(t2s: Text2SqlIntent) -> List[str]:
        """找出缺失槽位。"""
        missing = []
        if not t2s.subjects:
            missing.append("subject")
        if not t2s.metrics:
            missing.append("metric")
        if t2s.flow_type not in ("收入", "支出"):
            missing.append("flow_direction")
        if not t2s.region_level:
            missing.append("region_level")
        if not t2s.time_text:
            missing.append("time")
        return missing

    def _can_enrich(self, rag_result) -> Tuple[bool, str]:
        """RAG 质量检查。"""
        if rag_result is None or not getattr(rag_result, "success", False):
            return False, "RAG 检索失败"
        snippets = getattr(rag_result, "snippets", [])
        if not snippets:
            return False, "RAG 无结果"
        max_score = max(getattr(s, "score", 0.0) for s in snippets)
        if max_score < self._enricher.MIN_RELEVANCE_SCORE:
            return False, f"RAG最高相关度{max_score:.2f}<{self._enricher.MIN_RELEVANCE_SCORE}"
        return True, ""

    def _cache_key(self, question: str, region_code: Optional[str]) -> str:
        raw = f"{question}|{region_code or ''}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _cache_set(self, key: str, result: FusionResult):
        self._cache[key] = result
        # 简单 TTL 清理：超过 100 条清空（避免内存膨胀，实际可用 LRU）
        if len(self._cache) > 100:
            self._cache.clear()

    def _text2sql_run_safe(self, t2s_intent):
        """安全的 text2sql 调用。"""
        try:
            if self._text2sql is None:
                return None
            return self._text2sql.run(t2s_intent)
        except Exception:
            return None

    def _rag_search_safe(self, rag_intent):
        """安全的 RAG 调用。"""
        try:
            if self._rag_service is None:
                return None
            return self._rag_service.search(rag_intent)
        except Exception:
            return None

    @staticmethod
    def _format_table(rows: List[dict], source: str = "") -> str:
        """将 SQL 结果行格式化为 markdown 表格。"""
        if not rows:
            return "查询无结果。"
        headers = list(rows[0].keys())
        lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["------"] * len(headers)) + "|"]
        for row in rows[:20]:  # 最多20行
            vals = [str(row.get(h, "")) for h in headers]
            lines.append("| " + " | ".join(vals) + " |")
        if len(rows) > 20:
            lines.append(f"| ... | （共 {len(rows)} 行） |")
        if source:
            lines.append(f"\n*数据来源：{source}*")
        return "\n".join(lines)

    @staticmethod
    def _format_snippets(snippets: List) -> str:
        """将 RAG 片段格式化为文本。"""
        parts = []
        for s in snippets[:3]:
            source = getattr(s, "source", "")
            content = getattr(s, "content", "")
            parts.append(f"**{source}**\n{content}\n")
        return "\n".join(parts)

    @staticmethod
    def _calc_rag_confidence(rag_result) -> float:
        snippets = getattr(rag_result, "snippets", [])
        if not snippets:
            return 0.0
        return sum(getattr(s, "score", 0.0) for s in snippets[:3]) / min(3, len(snippets))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
