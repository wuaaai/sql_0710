"""RAG 反哺 Text2SQL 真实数据集成测试。

使用真实 pgvector 连接，验证完整链路：意图提取 → RAG检索 → 槽位反哺。
"""

import sys, json
from pathlib import Path
from typing import Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.configs.datasource_settings import DataSourceSettings, RagVectorConfig
from src.pages.infrastructure.llm.llm_gateway import LlmConfig, LlmGateway
from src.pages.infrastructure.vectorstores.vector_store_client import PgVectorStore
from src.pages.rag_knowledge_chain.retrieval import CustomLocalEmbeddings, HybridRetriever
from src.pages.request_lifecycle.unified_intent_extractor import UnifiedIntentExtractor
from src.pages.request_lifecycle.rag_slot_enricher import RagSlotEnricher
from src.pages.request_lifecycle.dispatch_execution import ConcurrentTaskDispatcher
from src.domain.intent.unified_intent import Text2SqlIntent, UnifiedIntentDict, RagIntent
from src.services.rag_service import RagService, RagResult


# ============================================================
# 配置
# ============================================================

ds = DataSourceSettings()

LLM_CONFIG = LlmConfig(
    api_key="sk-fdc7d21b49ca45c08b5962fee5f4847f",
    base_url="https://api.deepseek.com/v1",
    model="deepseek-chat",
    timeout_seconds=90,
)

SUBJECT_KEYWORDS = [
    "税收收入", "非税收入", "卫生健康支出", "教育支出",
    "社会保障和就业支出", "农林水支出", "科学技术支出",
    "住房保障支出", "交通运输支出", "一般公共预算收入",
    "政府性基金收入", "国有资本经营预算收入", "社会保险基金收入",
]

METRIC_ALIASES = {
    "预算执行率": ["预算执行率", "执行率", "预算完成率"],
    "本月金额": ["本月金额", "当月金额", "本月数", "本月执行金额", "本月执行数"],
    "累计金额": ["累计金额", "累计收入", "累计支出", "累计执行金额", "累计数", "累计执行数"],
    "同比增幅": ["同比增额", "同比增长率", "同比增长", "同比"],
    "环比增幅": ["环比增额", "环比增长率", "环比增长", "环比"],
    "预算数": ["预算数", "年初预算", "调整预算"],
    "总计": ["总计", "合计", "总计多少", "合计多少"],
    "金额": ["金额"],
}


def setup_rag() -> RagService:
    """初始化 RAG 服务 — 连接真实 pgvector。"""
    rag_cfg = ds.rag_vector
    print(f"[RAG] 连接 pgvector: {rag_cfg.collection_name}")

    # Embedding 客户端
    emb = CustomLocalEmbeddings(
        api_url="http://10.32.10.160:8991/embed",
        api_key="",
        model_name="",
    )

    # pgvector 向量库
    vector_store = PgVectorStore(
        connection=rag_cfg.connection_string,
        collection_name=rag_cfg.collection_name,
        embedding=emb,
    )

    # 检索器
    retriever = HybridRetriever(
        vector_store=vector_store,
        rerank_url="http://10.32.10.160:8991/rerank",
        rerank_key="",
        rerank_model="",
        top_k=5,
        recall_k=10,
    )

    return RagService(retriever=retriever)


def test_enrichment_with_real_rag():
    """核心测试：真实 RAG 检索 → 槽位反哺。"""
    print("\n" + "=" * 60)
    print("测试：RAG 真实检索 → 槽位反哺")
    print("=" * 60)

    # 初始化
    llm = LlmGateway(LLM_CONFIG)
    extractor = UnifiedIntentExtractor(llm, SUBJECT_KEYWORDS, METRIC_ALIASES)
    enricher = RagSlotEnricher(METRIC_ALIASES, SUBJECT_KEYWORDS)
    rag_service = setup_rag()
    dispatcher = ConcurrentTaskDispatcher()

    # 测试用例 — 槽位不全的问题，期望 RAG 补全
    test_cases = [
        {
            "question": "卫生健康支出执行情况",
            "desc": "槽位不全→RAG补全",
        },
        {
            "question": "2019年全省一般公共预算收入总计多少，由哪几部分构成",
            "desc": "混合问题→both模式",
        },
        {
            "question": "河北省的减税降费政策有哪些",
            "desc": "纯RAG问题",
        },
    ]

    for case in test_cases:
        q = case["question"]
        print(f"\n{'─' * 50}")
        print(f"[{case['desc']}] 问题: {q}")

        # 1. 意图提取
        intent_v1 = extractor.extract(q)
        t2s = intent_v1.text2sql
        print(f"  intent_v1: subjects={t2s.subjects}, metrics={t2s.metrics}, "
              f"region={t2s.region_level}, time={t2s.time_text}, "
              f"account={t2s.account_book}, data_stage={t2s.data_stage}")

        # 2. RAG 检索
        rag_result = rag_service.search(intent_v1.rag)
        snippet_count = len(rag_result.snippets) if rag_result.snippets else 0
        print(f"  RAG: {snippet_count} snippets")
        if snippet_count > 0:
            print(f"    top1 source: {rag_result.snippets[0].source}")
            print(f"    top1 score: {rag_result.snippets[0].score:.3f}")
            print(f"    top1 content[:100]: {rag_result.snippets[0].content[:100]}...")

        # 3. 槽位反哺
        if t2s.subjects or t2s.metrics:
            intent_v2, log = enricher.enrich(intent_v1, rag_result.snippets, q)
            print(f"  反哺: filled_slots={log.filled_slots}")
            if log.filled_slots:
                print(f"    candidates: {json.dumps(log.candidates, ensure_ascii=False, indent=6)[:300]}")
            # 前后对比
            print(f"  intent_v2: subjects={intent_v2.text2sql.subjects}, "
                  f"metrics={intent_v2.text2sql.metrics}, "
                  f"region={intent_v2.text2sql.region_level}, "
                  f"time={intent_v2.text2sql.time_text}, "
                  f"account={intent_v2.text2sql.account_book}")
        else:
            print(f"  纯RAG问题，跳过反哺层")

        # 4. 调度
        plan = dispatcher.dispatch(intent_v1)
        print(f"  调度: text2sql={plan.text2sql}, rag={plan.rag}, "
              f"clarify={plan.clarify}, fallback={plan.fallback}")

    print(f"\n{'=' * 60}")
    print("真实数据集成测试完成")


if __name__ == "__main__":
    test_enrichment_with_real_rag()
