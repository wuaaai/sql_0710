"""RAG 检索领域服务。

完整复用自 dataQuery/text_smart_qa/src/unified/text_qa_service.py（Agent 调用模式），
同时保留直接检索模式（HybridRetriever）。

两种模式：
1. 直接检索：RagIntent → HybridRetriever.retrieve() → KnowledgeSnippets
2. Agent 模式：RagIntent → RagAgent.ainvoke() → LLM 多轮检索 + 生成回答
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from src.domain.intent.unified_intent import RagIntent
from src.pages.rag_knowledge_chain.rag_agent import RagAgent
from src.pages.rag_knowledge_chain.retrieval import (
    HybridRetriever,
    KnowledgeSnippet,
)


# ============================================================
# RagResult
# ============================================================

@dataclass
class RagResult:
    """RAG 检索结果。"""

    snippets: List[KnowledgeSnippet] = field(default_factory=list)
    answer: str = ""
    success: bool = True
    error: str = ""
    mode: str = "direct"
    extra: Dict = field(default_factory=dict)


# ============================================================
# RagService — 统一对外入口
# 直接检索模式：对应现有 HybridRetriever
# Agent 模式：复用 text_qa_service.py 的 Agent 调用
# ============================================================

@dataclass
class RagService:
    """RAG 检索领域服务。

    用法:
        # 直接检索
        service = RagService(retriever=retriever)
        result = service.search(rag_intent)

        # Agent 模式
        agent = RagAgent(agent=langchain_agent)
        service = RagService(agent=agent)
        result = await service.asearch(rag_intent, messages, thread_id, region_code)
    """

    retriever: Optional[HybridRetriever] = None
    agent: Optional[RagAgent] = None

    # ---- 直接检索 ----

    def search(
        self,
        rag_intent: RagIntent,
        region_code: Optional[str] = None,
        history_messages: Optional[List[dict]] = None,
    ) -> RagResult:
        """直接检索模式：RagIntent → 多路检索 → KnowledgeSnippets。"""
        if self.retriever is not None:
            try:
                snippets = self.retriever.retrieve(
                    rag_intent, region_code=region_code
                )
                return RagResult(
                    snippets=snippets,
                    success=True,
                    mode="direct",
                    extra={"rag_intent": rag_intent},
                )
            except Exception as e:
                return RagResult(
                    success=False, error=str(e), extra={"rag_intent": rag_intent}
                )
        return RagResult(success=False, error="未注入 Retriever 或 Agent")

    # ---- Agent 模式 ----
    # 复用自 dataQuery/.../text_qa_service.py:TextQaService.answer()

    async def asearch(
        self,
        rag_intent: RagIntent,
        messages: List,
        thread_id: str,
        region_code: Optional[str] = None,
        question_override: Optional[str] = None,
    ) -> RagResult:
        """Agent 模式：使用 RagAgent 进行 LLM 多轮检索。

        Args:
            rag_intent: RAG 检索意图。
            messages: LangChain 消息列表。
            thread_id: 会话 ID。
            region_code: 地区权限码。
            question_override: 可选的问题替换（由路由层改写后的优化问题）。

        Returns:
            RagResult，包含 Agent 生成的 answer。
        """
        if self.agent is None or not self.agent.is_available:
            return RagResult(
                success=False,
                error="Agent 未初始化",
                mode="agent",
            )

        try:
            # 可选：替换最后一条用户消息为优化后的问题
            final_messages = self._replace_last_user_question(
                messages, question_override
            )

            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "region_code": region_code,
                }
            }

            result = await self.agent.ainvoke(
                [{"role": msg.type, "content": msg.content} for msg in final_messages],
                config=config,
            )

            all_messages = result.get("messages", [])
            answer = (
                all_messages[-1].content if all_messages else "未生成回答。"
            )

            # 同时做一次直接检索获取知识片段用于溯源
            snippets = (
                self.retriever.retrieve(rag_intent, region_code=region_code)
                if self.retriever
                else []
            )

            return RagResult(
                snippets=snippets,
                answer=str(answer),
                success=True,
                mode="agent",
                extra={"rag_intent": rag_intent, "thread_id": thread_id},
            )
        except Exception as e:
            return RagResult(
                success=False,
                error=str(e),
                mode="agent",
                extra={"rag_intent": rag_intent},
            )

    # ---- 工具方法 ----
    # 复用自 text_qa_service.py:_replace_last_user_question

    @staticmethod
    def _replace_last_user_question(
        messages: List, question_override: Optional[str]
    ) -> List:
        """替换最后一条用户消息为优化后的问题。"""
        if not question_override:
            return list(messages)

        new_messages = list(messages)
        for index in range(len(new_messages) - 1, -1, -1):
            if isinstance(new_messages[index], HumanMessage):
                new_messages[index] = HumanMessage(content=question_override)
                break
        return new_messages
