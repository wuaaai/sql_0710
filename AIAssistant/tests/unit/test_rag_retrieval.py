"""RAG 检索链路单元测试。

覆盖 HybridRetriever（query 构造、检索流程）、
RagService（编排层）、ConcurrentTaskDispatcher（全链路调度）。
"""

import pytest

from src.domain.intent.unified_intent import RagIntent, Text2SqlIntent, UnifiedIntentDict
from src.pages.rag_knowledge_chain.retrieval import (
    HybridRetriever,
    KnowledgeSnippet,
)
from src.pages.request_lifecycle.dispatch_execution import (
    ConcurrentTaskDispatcher,
    dispatch,
)
from src.services.rag_service import RagResult, RagService


# ============================================================
# Mock 基础设施
# ============================================================

class MockVectorStore:
    """模拟向量库，根据 query 中关键词返回不同文档。"""

    def similarity_search(self, query, k=10, filter=None):
        results = []
        if "政策" in query or "规定" in query:
            results.append(
                _make_doc("关于加强预算管理的若干政策措施...", "政策文件.pdf", 0.92)
            )
        if "口径" in query or "定义" in query:
            results.append(
                _make_doc("一般公共预算收入口径是指...", "口径说明.pdf", 0.88)
            )
        if "构成" in query or "分类" in query:
            results.append(
                _make_doc("一般公共预算收入由税收收入、非税收入等构成...", "预算解读.pdf", 0.95)
            )
        if "金额" in query or "数据" in query:
            results.append(
                _make_doc("2019年全省一般公共预算收入总计5432亿元...", "预算执行报告.pdf", 0.85)
            )
        return results


def _make_doc(content, source, score):
    return type(
        "Doc",
        (),
        {"page_content": content, "metadata": {"source": source, "score": score}},
    )()


# ============================================================
# HybridRetriever._build_search_queries 测试
# ============================================================

class TestBuildSearchQueries:
    def setup_method(self):
        self.retriever = HybridRetriever()

    def test_no_flags_only_original_question(self):
        rag = RagIntent(original_question="你好")
        queries = self.retriever._build_search_queries(rag)
        assert len(queries) == 1
        assert queries[0] == "你好"

    def test_composition_flag_adds_composition_query(self):
        rag = RagIntent(
            need_composition=True,
            original_question="一般公共预算收入构成",
        )
        queries = self.retriever._build_search_queries(rag)
        assert len(queries) == 2
        assert "构成" in queries[1]

    def test_policy_flag_adds_policy_query(self):
        rag = RagIntent(
            need_policy_basis=True,
            original_question="预算执行依据",
        )
        queries = self.retriever._build_search_queries(rag)
        assert len(queries) == 2
        assert "政策" in queries[1]

    def test_caliber_flag_adds_caliber_query(self):
        rag = RagIntent(
            need_caliber_explanation=True,
            original_question="口径解释",
        )
        queries = self.retriever._build_search_queries(rag)
        assert len(queries) == 2
        assert "口径" in queries[1]

    def test_data_value_flag_adds_data_query(self):
        rag = RagIntent(
            need_data_value=True,
            original_question="收入多少",
        )
        queries = self.retriever._build_search_queries(rag)
        assert len(queries) == 2
        assert "金额" in queries[1]

    def test_all_flags_five_queries(self):
        rag = RagIntent(
            need_policy_basis=True,
            need_caliber_explanation=True,
            need_composition=True,
            need_data_value=True,
            original_question="预算收入情况",
        )
        queries = self.retriever._build_search_queries(rag)
        assert len(queries) == 5  # 原始 + 4 个 need_* 定向 query

    def test_data_value_not_in_routing_but_in_query(self):
        """need_data_value=True 时构造了检索 query，但不参与路由判定。"""
        rag = RagIntent(
            need_data_value=True,
            original_question="收入多少",
        )
        queries = self.retriever._build_search_queries(rag)
        assert len(queries) == 2
        # 验证 data_value query 包含数据关键词
        assert any("金额" in q or "数据" in q for q in queries)


# ============================================================
# HybridRetriever.retrieve 测试
# ============================================================

class TestHybridRetrieverRetrieve:
    def setup_method(self):
        self.retriever = HybridRetriever(
            vector_store=MockVectorStore(),
            top_k=3,
        )

    def test_retrieve_composition_question(self):
        rag = RagIntent(
            need_composition=True,
            original_question="一般公共预算收入由哪几部分构成",
        )
        snippets = self.retriever.retrieve(rag)
        assert len(snippets) > 0
        # 应该有构成相关的结果
        contents = " ".join(s.content for s in snippets)
        assert "构成" in contents or "收入" in contents

    def test_retrieve_caliber_question(self):
        rag = RagIntent(
            need_caliber_explanation=True,
            original_question="一般公共预算收入的口径是什么",
        )
        snippets = self.retriever.retrieve(rag)
        assert len(snippets) > 0

    def test_retrieve_deduplicates(self):
        """验证多路 query 结果去重。"""
        rag = RagIntent(
            need_composition=True,
            need_data_value=True,
            original_question="收入构成和总计",
        )
        snippets = self.retriever.retrieve(rag)
        # 不应有重复内容
        contents = [s.content for s in snippets]
        assert len(contents) == len(set(contents))

    def test_retrieve_without_vector_store_returns_empty(self):
        retriever = HybridRetriever(vector_store=None)
        rag = RagIntent(need_composition=True, original_question="test")
        snippets = retriever.retrieve(rag)
        assert snippets == []


# ============================================================
# RagService 测试
# ============================================================

class TestRagService:
    def setup_method(self):
        retriever = HybridRetriever(vector_store=MockVectorStore(), top_k=3)
        self.service = RagService(retriever=retriever)

    def test_search_returns_rag_result(self):
        rag = RagIntent(
            need_composition=True,
            original_question="一般公共预算收入由哪几部分构成",
        )
        result = self.service.search(rag)
        assert isinstance(result, RagResult)
        assert result.success is True
        assert len(result.snippets) > 0

    def test_search_with_region_code(self):
        rag = RagIntent(
            need_composition=True,
            original_question="收入构成",
        )
        result = self.service.search(rag, region_code="130000000")
        assert result.success is True

    def test_search_preserves_rag_intent_in_extra(self):
        rag = RagIntent(
            need_caliber_explanation=True,
            original_question="口径是什么",
        )
        result = self.service.search(rag)
        assert "rag_intent" in result.extra


# ============================================================
# ConcurrentTaskDispatcher 全链路测试
# ============================================================

class TestDispatcherWithRag:
    def setup_method(self):
        retriever = HybridRetriever(vector_store=MockVectorStore(), top_k=3)
        rag_service = RagService(retriever=retriever)
        self.dispatcher = ConcurrentTaskDispatcher(rag_service=rag_service)

    def test_full_pipeline_hybrid_question(self):
        """全链路：提取 → 路由 → RAG 检索。"""
        from src.pages.request_lifecycle.unified_intent_extractor import (
            UnifiedIntentExtractor,
        )

        extractor = UnifiedIntentExtractor(llm_client=None)
        intent_dict = extractor.extract(
            "2019年全省一般公共预算收入总计多少，由哪几部分构成"
        )
        plan, rag_result = self.dispatcher.run(intent_dict)

        assert plan.rag is True
        assert rag_result is not None
        assert rag_result.success is True
        assert len(rag_result.snippets) > 0

    def test_pure_rag_question(self):
        """纯文档问题：仅执行 RAG。"""
        from src.pages.request_lifecycle.unified_intent_extractor import (
            UnifiedIntentExtractor,
        )

        extractor = UnifiedIntentExtractor(llm_client=None)
        intent_dict = extractor.extract("一般公共预算收入的口径是什么")
        plan, rag_result = self.dispatcher.run(intent_dict)

        assert plan.rag is True
        assert plan.text2sql is False
        assert rag_result.success is True

    def test_pure_data_no_rag(self):
        """纯查数问题：不执行 RAG。"""
        d = UnifiedIntentDict(
            text2sql=Text2SqlIntent(
                time_text="2025年",
                time_start="202501",
                region_level="省本级",
                flow_type="支出",
                metrics=["本月金额"],
                subjects=["卫生健康支出"],
            ),
            rag=RagIntent(),
        )
        plan, rag_result = self.dispatcher.run(d)
        assert plan.rag is False
        # 无 RAG 需求时 rag_result 为 None
