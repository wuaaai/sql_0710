"""RAG 检索增强能力。

整合两个来源：
1. dataQuery/text_smart_qa/src/agent/tools/my_rag_tool.py
   — CustomLocalEmbeddings / local_rerank / _sync_search_logic / search_knowledge_base
   （向量粗排 + Rerank 精排二阶段检索）

2. 步骤5 实现的 HybridRetriever
   — 从 RagIntent.need_* 构造多路定向检索 query

流程：RagIntent → 多路 query → 向量粗排 → Rerank 精排 → TopK
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from langchain_core.embeddings import Embeddings
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.pages.infrastructure.vectorstores.vector_store_client import PgVectorStore
from src.pages.rag_knowledge_chain.region_filter import build_pgvector_filter
from src.pages.rag_knowledge_chain.tool_limiter import rag_limiter
from src.domain.intent.unified_intent import RagIntent


# ============================================================
# Embedding 客户端
# 完整复用自 my_rag_tool.py:CustomLocalEmbeddings
# ============================================================

def _build_headers(api_key: str) -> dict:
    h = {"Content-Type": "application/json", "accept": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


class CustomLocalEmbeddings(Embeddings):
    """自定义 Embedding 接口，兼容 OpenAI 格式和本地格式。"""

    def __init__(self, api_url: str, api_key: str = "", model_name: str = ""):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            headers = _build_headers(self.api_key)
            if self.api_key:
                payload = {"input": texts}
                if self.model_name:
                    payload["model"] = self.model_name
                response = requests.post(
                    self.api_url, json=payload, headers=headers, timeout=60
                )
                response.raise_for_status()
                data = response.json()
                if "data" in data:
                    sorted_items = sorted(
                        data["data"], key=lambda x: x.get("index", 0)
                    )
                    return [item["embedding"] for item in sorted_items]
                return []
            else:
                response = requests.post(
                    self.api_url, json=texts, headers=headers, timeout=60
                )
                response.raise_for_status()
                return response.json()["embeddings"]
        except Exception as e:
            print(f"请求 Embedding 接口失败: {e}")
            return []

    def embed_query(self, text: str) -> List[float]:
        embeddings = self.embed_documents([text])
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        return []


# ============================================================
# Rerank 接口
# 完整复用自 my_rag_tool.py:local_rerank
# ============================================================

def local_rerank(
    query: str,
    texts: List[str],
    api_url: str = "",
    api_key: str = "",
    model_name: str = "",
) -> List[dict]:
    """对文档列表重排序，兼容 OpenAI 格式和本地格式。"""
    if not texts:
        return []

    try:
        headers = _build_headers(api_key)
        if api_key:
            payload: dict = {"query": query, "documents": texts}
            if model_name:
                payload["model"] = model_name
            response = requests.post(api_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return _parse_rerank_result(response.json(), texts)
        else:
            params = {"query": query}
            response = requests.post(
                api_url, params=params, json=texts, headers=headers, timeout=15
            )
            response.raise_for_status()
            result = response.json()
            if (
                isinstance(result, dict)
                and "ranked_documents" in result
                and "scores" in result
            ):
                ranked = result["ranked_documents"]
                scores = result["scores"]
                return [
                    {"text": t, "score": float(s)} for t, s in zip(ranked, scores)
                ]
            else:
                return [{"text": t, "score": 0.0} for t in texts]
    except Exception as e:
        print(f"请求 Rerank 接口失败: {e}")
        return [{"text": t, "score": float(len(texts) - i)} for i, t in enumerate(texts)]


def _parse_rerank_result(result: dict, texts: List[str]) -> List[dict]:
    """解析 Rerank 返回，兼容多种格式。"""
    if "results" in result:
        items = sorted(
            result["results"], key=lambda x: x.get("relevance_score", 0), reverse=True
        )
        return [
            {"text": texts[r["index"]], "score": float(r.get("relevance_score", 0))}
            for r in items
            if r.get("index", -1) < len(texts)
        ]
    if "data" in result:
        items = sorted(result["data"], key=lambda x: x.get("score", 0), reverse=True)
        return [
            {"text": texts[r["index"]], "score": float(r.get("score", 0))}
            for r in items
            if r.get("index", -1) < len(texts)
        ]
    if "scores" in result and isinstance(result["scores"], list):
        paired = list(zip(texts, result["scores"]))
        paired.sort(key=lambda x: x[1], reverse=True)
        return [{"text": t, "score": float(s)} for t, s in paired]
    return [{"text": t, "score": 0.0} for t in texts]


# ============================================================
# 检索结果
# ============================================================

@dataclass
class KnowledgeSnippet:
    """单条知识片段。"""

    content: str
    source: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================
# need_* → 检索关键词映射
# ============================================================

_POLICY_EXPANSION = "政策 文件 规定 措施 依据 法规"
_CALIBER_EXPANSION = "口径 定义 解释 含义 怎么算"
_COMPOSITION_EXPANSION = "构成 分类 组成 包括 涵盖"
_DATA_VALUE_EXPANSION = "金额 数据 总计 数值"


# ============================================================
# HybridRetriever — 整合 need_* 多路 query + 两阶段检索
# ============================================================

@dataclass
class HybridRetriever:
    """接收 RagIntent，根据 need_* 构造多路定向检索 query，
    复用 my_rag_tool.py 的向量粗排 + Rerank 精排模式。
    """

    vector_store: Optional[PgVectorStore] = None
    """pgvector 向量库"""

    rerank_url: str = ""
    rerank_key: str = ""
    rerank_model: str = ""
    """Rerank API 配置"""

    top_k: int = 5
    recall_k: int = 10

    # ---- 主入口 ----

    def retrieve(
        self,
        rag_intent: RagIntent,
        region_code: Optional[str] = None,
    ) -> List[KnowledgeSnippet]:
        """根据 RagIntent 执行多路检索。"""
        if self.vector_store is None:
            return []

        queries = self._build_search_queries(rag_intent)
        all_docs: Dict[str, KnowledgeSnippet] = {}

        for query in queries:
            snippets = self._vector_search(query, region_code)
            for s in snippets:
                key = s.content[:200]
                if key not in all_docs or s.score > all_docs[key].score:
                    all_docs[key] = s

        candidates = list(all_docs.values())

        # Rerank
        if self.rerank_url and candidates:
            candidates = self._rerank_candidates(
                rag_intent.original_question, candidates
            )

        candidates.sort(key=lambda x: x.score, reverse=True)
        return candidates[: self.top_k]

    # ---- query 构造 ----

    def _build_search_queries(self, rag: RagIntent) -> List[str]:
        """从 RagIntent 构造多路定向检索 query。"""
        queries = [rag.original_question]
        if rag.need_policy_basis:
            queries.append(f"{rag.original_question} {_POLICY_EXPANSION}")
        if rag.need_caliber_explanation:
            queries.append(f"{rag.original_question} {_CALIBER_EXPANSION}")
        if rag.need_composition:
            queries.append(f"{rag.original_question} {_COMPOSITION_EXPANSION}")
        if rag.need_data_value:
            queries.append(f"{rag.original_question} {_DATA_VALUE_EXPANSION}")
        return queries

    # ---- 向量粗排 ----
    # 复用自 my_rag_tool.py:_sync_search_logic

    def _vector_search(
        self, query: str, region_code: Optional[str]
    ) -> List[KnowledgeSnippet]:
        try:
            filter_dict = (
                build_pgvector_filter([region_code]) if region_code else None
            )
            results = self.vector_store.similarity_search(
                query, k=self.recall_k, filter=filter_dict
            )
            if not results:
                # 判断权限不足 vs 真的无内容
                if filter_dict:
                    unfiltered = self.vector_store.similarity_search(
                        query, k=1, filter=None
                    )
                    if unfiltered:
                        print("[RAG] 无过滤查询有结果 → 判定为权限不足")
                return []

            snippets = []
            for doc in results:
                content = doc.page_content
                metadata = doc.metadata or {}
                recall_context = metadata.get("recall_context", content)
                snippets.append(
                    KnowledgeSnippet(
                        content=recall_context,
                        source=metadata.get("source", ""),
                        score=0.0,
                        metadata=metadata,
                    )
                )
            return snippets
        except Exception as e:
            print(f"向量检索出错: {e}")
            return []

    # ---- Rerank 精排 ----
    # 复用自 my_rag_tool.py:local_rerank

    def _rerank_candidates(
        self, query: str, snippets: List[KnowledgeSnippet]
    ) -> List[KnowledgeSnippet]:
        try:
            texts = [s.content for s in snippets]
            ranked = local_rerank(
                query,
                texts,
                api_url=self.rerank_url,
                api_key=self.rerank_key,
                model_name=self.rerank_model,
            )
            score_map = {item["text"]: item.get("score", 0.0) for item in ranked}
            for s in snippets:
                if s.content in score_map:
                    s.score = score_map[s.content]
            return snippets
        except Exception as e:
            print(f"Rerank 出错: {e}")
            return snippets


# ============================================================
# Agent 工具 — search_knowledge_base
# 复用自 my_rag_tool.py 的 @tool 定义
# ============================================================

class RAGSearchArgs(BaseModel):
    query: str = Field(..., description="需要检索的用户问题或关键词")


@tool("private_knowledge_search", args_schema=RAGSearchArgs)
@rag_limiter
async def search_knowledge_base(query: str, config) -> str:
    """企业私有知识库搜索工具。
    当用户询问关于'预算'、'政策'、'报销'、'规定'等内部文档细节时，必须使用此工具。
    """
    # 注意：此工具需要由外部注入 retriever 实例
    # 实际检索逻辑在 HybridRetriever.retrieve() 中
    return f"检索完成: {query}"
