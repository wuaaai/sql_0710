import os
import asyncio
import sys

import requests
from typing import List, Dict
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from text_smart_qa.src.agent.db.pgvector_store import PgVectorStore
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import RunnableConfig
from ..utils.tool_limiter import rag_limiter
from ..utils.region_tree import build_pgvector_filter


from text_smart_qa.src import env_utils

# ================= 配置部分 =================
DB_CONNECTION = env_utils.PGVECTOR_CONNECTION
COLLECTION_NAME = env_utils.PGVECTOR_COLLECTION_NAME
LOCAL_API_URL = env_utils.EMBEDDING_API_URL
LOCAL_API_KEY = env_utils.EMBEDDING_API_KEY
LOCAL_EMBED_MODEL = env_utils.EMBEDDING_MODEL_NAME
LOCAL_RERANK_URL = env_utils.RERANK_API_URL
LOCAL_RERANK_KEY = env_utils.RERANK_API_KEY
LOCAL_RERANK_MODEL = env_utils.RERANK_MODEL_NAME
# ============================================


def _build_headers(api_key: str) -> dict:
    """有 API key 时加鉴权头，没有则仅设置 Content-Type"""
    h = {"Content-Type": "application/json", "accept": "application/json"}
    if api_key:
        h["Authorization"] = f"Bearer {api_key}"
    return h


# --- 1. 自定义 Embeddings 接口类（同时兼容内网 OpenAI 格式和本地格式）---
class CustomLocalEmbeddings(Embeddings):
    def __init__(self, api_url: str, api_key: str = "", model_name: str = ""):
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        try:
            headers = _build_headers(self.api_key)
            if self.api_key:
                # 内网 OpenAI 兼容格式
                payload = {"input": texts}
                if self.model_name:
                    payload["model"] = self.model_name
                response = requests.post(self.api_url, json=payload, headers=headers, timeout=60)
                response.raise_for_status()
                data = response.json()
                # OpenAI 格式: {"data": [{"embedding": [...], "index": 0}, ...]}
                if "data" in data:
                    sorted_items = sorted(data["data"], key=lambda x: x.get("index", 0))
                    return [item["embedding"] for item in sorted_items]
                return []
            else:
                # 本地格式: body = ["text1", ...] → {"embeddings": [[...], ...]}
                response = requests.post(self.api_url, json=texts, headers=headers, timeout=60)
                response.raise_for_status()
                return response.json()["embeddings"]
        except Exception as e:
            print(f"❌ 请求 Embedding 接口失败: {e}")
            return []

    def embed_query(self, text: str) -> List[float]:
        embeddings = self.embed_documents([text])
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        return []


# --- 2. Rerank 接口调用（同时兼容内网格式和本地格式）---
def local_rerank(query: str, texts: List[str]) -> List[dict]:
    if not texts:
        return []

    try:
        headers = _build_headers(LOCAL_RERANK_KEY)
        if LOCAL_RERANK_KEY:
            # 内网格式: {"query": "...", "model": "...", "documents": [...]}
            payload: dict = {"query": query, "documents": texts}
            if LOCAL_RERANK_MODEL:
                payload["model"] = LOCAL_RERANK_MODEL
            response = requests.post(LOCAL_RERANK_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
            return _parse_rerank_result(result, texts)
        else:
            # 本地格式: ?query=xxx + body ["text1", ...]
            params = {"query": query}
            response = requests.post(LOCAL_RERANK_URL, params=params, json=texts, headers=headers, timeout=15)
            response.raise_for_status()
            result = response.json()
            if isinstance(result, dict) and "ranked_documents" in result and "scores" in result:
                ranked_texts = result["ranked_documents"]
                scores = result["scores"]
                return [{"text": t, "score": float(s)} for t, s in zip(ranked_texts, scores)]
            else:
                print(f"⚠️ Rerank 返回格式不匹配预期: {result}")
                return [{"text": t, "score": 0.0} for t in texts]

    except Exception as e:
        print(f"❌ 请求 Rerank 接口失败: {e}")
        return [{"text": t, "score": float(len(texts) - i)} for i, t in enumerate(texts)]


def _parse_rerank_result(result: dict, texts: List[str]) -> List[dict]:
    """解析内网 Rerank 返回结果，兼容多种格式"""
    # 格式1: {"results": [{"index": 0, "relevance_score": 0.9}, ...]}
    if "results" in result:
        items = sorted(result["results"], key=lambda x: x.get("relevance_score", 0), reverse=True)
        return [{"text": texts[r["index"]], "score": float(r.get("relevance_score", 0))} for r in items if r.get("index", -1) < len(texts)]
    # 格式2: {"data": [{"index": 0, "score": 0.9}, ...]}
    if "data" in result:
        items = sorted(result["data"], key=lambda x: x.get("score", 0), reverse=True)
        return [{"text": texts[r["index"]], "score": float(r.get("score", 0))} for r in items if r.get("index", -1) < len(texts)]
    # 格式3: 直接返回 scores 列表
    if "scores" in result and isinstance(result["scores"], list):
        paired = list(zip(texts, result["scores"]))
        paired.sort(key=lambda x: x[1], reverse=True)
        return [{"text": t, "score": float(s)} for t, s in paired]
    # fallback
    print(f"⚠️ Rerank 返回格式不匹配预期: {result}")
    return [{"text": t, "score": 0.0} for t in texts]


# --- 全局初始化资源 ---
print("⏳ 正在初始化 RAG 工具资源...")
embeddings = CustomLocalEmbeddings(api_url=LOCAL_API_URL, api_key=LOCAL_API_KEY, model_name=LOCAL_EMBED_MODEL)
vector_store = PgVectorStore(
    embedding=embeddings,
    collection_name=COLLECTION_NAME,
    connection=DB_CONNECTION,
)
print("✅ RAG 工具准备就绪！")


# --- 定义参数结构 ---
class RAGSearchArgs(BaseModel):
    query: str = Field(..., description="需要检索的用户问题或关键词")


# --- 3. 核心检索逻辑 (粗排召回 + Rerank精排) ---
def _sync_search_logic(query: str, region_code: str = None) -> str:
    try:
        print(f"\n{'='*60}")
        print(f"[RAG] 用户问题: {query}")
        print(f"[RAG] Dify传入 region_code: {region_code!r}")

        # 构建区划过滤条件（权限树：上级自动包含所有下级）
        filter_dict = build_pgvector_filter([region_code]) if region_code else None

        # 第一步：向量粗排 (召回) — 数据库先按 filter 过滤行，再计算向量距离排序
        print(f"[RAG] 执行向量检索 (k=10, filter={filter_dict})")
        results = vector_store.similarity_search(query, k=10, filter=filter_dict)
        print(f"[RAG] 检索结果数: {len(results)}")
        
        if not results:
            # 判断是权限不足还是真的没有内容
            if filter_dict:
                unfiltered = vector_store.similarity_search(query, k=1, filter=None)
                if unfiltered:
                    print("[RAG] 无过滤查询有结果 -> 判定为权限不足")
                    return "【权限不足】当前账号无权访问该地区数据，请联系管理员申请相应地区的访问权限。"
            return "知识库中未找到相关信息。"

        # 注入权限范围提示，让 LLM 知道当前只搜了哪个范围
        scope_notice = ""
        if region_code:
            from ..utils.region_tree import is_group_node, strip_trailing_zeros
            prefix = strip_trailing_zeros(region_code)
            scope_notice = (
                f"[系统提示] 当前检索范围受限于地区权限（权限码: {region_code}），"
                f"仅返回该地区及其下级的数据。如果用户问题涉及的地域范围超出此权限，"
                f"请在回答中明确告知用户其权限范围的限制。\n\n"
            )

        # 第二步：用子块内容做 Rerank（子块短而精准，是向量检索命中的那段）
        child_chunks = [doc.page_content for doc in results]  # 子块，短而聚焦
        child_to_parent = {doc.page_content: doc.metadata.get("recall_context", doc.page_content) for doc in results}
        child_to_source = {doc.page_content: doc.metadata.get("source", "未知来源") for doc in results}

        # 第三步：Rerank 精排打分
        print(f"[RAG] 送入 Rerank: {len(child_chunks)} 个子块")
        reranked_items = local_rerank(query, child_chunks)
        if reranked_items:
            top_scores = [f"{it['score']:.4f}" for it in reranked_items[:3]]
            print(f"[RAG] Rerank 完成，Top3 得分: {top_scores}")
        else:
            print(f"[RAG] Rerank 返回空，使用原始排序")

        # 第四步：组装最终结果 (取 Rerank 打分最高的前 3 个，映射回完整父文档)
        final_content = []
        top_k = 3
        seen_parents = set()
        for item in reranked_items:
            child_text = item["text"]
            full_text = child_to_parent.get(child_text, child_text)
            if full_text in seen_parents:
                continue
            seen_parents.add(full_text)
            score = item["score"]
            source = child_to_source.get(child_text, "未知来源")

            text_block = (
                f"--- 引用来源 {len(final_content)+1}: {source} (相关度得分: {score:.4f}) ---\n"
                f"{full_text}\n"
            )
            final_content.append(text_block)
            if len(final_content) >= top_k:
                break

        result = scope_notice + "\n".join(final_content)
        print(f"[RAG] 返回结果长度: {len(result)} 字符")
        print(f"[RAG] --- 送入LLM的 {len(final_content)} 个文档开始 ---")
        for i, block in enumerate(final_content):
            print(block)
            print("---")
        print(f"[RAG] --- 送入LLM的文档结束 ---")
        return result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"检索过程出错: {str(e)}"


@tool("private_knowledge_search", args_schema=RAGSearchArgs)
@rag_limiter
async def search_knowledge_base(query: str, config: RunnableConfig) -> str:
    """
    企业私有知识库搜索工具。
    当用户询问关于'预算'、'政策'、'报销'、'规定'等内部文档细节时，必须使用此工具。
    该工具会返回文档的详细上下文。
    """
    region_code = None
    thread_id = "default_session"
    if config and "configurable" in config:
        region_code = config["configurable"].get("region_code")
        thread_id = config["configurable"].get("thread_id", "default_session")
    print(f"[RAG] 从 config 提取 region_code: {region_code!r}")
    result = await asyncio.to_thread(_sync_search_logic, query, region_code)
    # 权限不足时立即耗尽本轮配额，避免无效重试
    if "权限不足" in result:
        rag_limiter.force_exhaust(thread_id)
    return result


# ================= 测试代码 =================
if __name__ == "__main__":
    async def main():
        test_question = "2026年邯郸的数据有哪些？"

        # # 测试1: 不传区划 — 搜索全部
        # print(f"\n{'='*60}")
        # print(f"测试1: 不限区划")
        # print(f"❓ 提问: {test_question}")
        # print("-" * 50)
        # response = await search_knowledge_base.ainvoke({"query": test_question})
        # print(f"🤖 结果:\n{response[:500]}...")

        # 测试2: 传邯郸市区划 (config 模拟 Dify 传入)
        print(f"\n{'='*60}")
        print(f"测试2: 限定区划 130000 ")
        print(f"❓ 提问: {test_question}")
        print("-" * 50)
        response = await search_knowledge_base.ainvoke(
            {"query": test_question},
            config={"configurable": {"region_code": "130000"}}
        )
        print(f"🤖 结果:\n{response[:500]}...")

    asyncio.run(main())
