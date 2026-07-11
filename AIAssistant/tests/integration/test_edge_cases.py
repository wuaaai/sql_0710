"""RAG 反哺模块 — 刁钻边缘问题测试。

设计 15 个边界情况问题，测试系统的极限表现。
"""

import json, sys, time
from pathlib import Path
from typing import List

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.configs.datasource_settings import DataSourceSettings
from src.pages.infrastructure.llm.llm_gateway import LlmConfig, LlmGateway
from src.pages.infrastructure.vectorstores.vector_store_client import PgVectorStore
from src.pages.rag_knowledge_chain.retrieval import CustomLocalEmbeddings, HybridRetriever
from src.pages.request_lifecycle.unified_intent_extractor import UnifiedIntentExtractor
from src.pages.request_lifecycle.rag_slot_enricher import RagSlotEnricher
from src.pages.request_lifecycle.dispatch_execution import ConcurrentTaskDispatcher
from src.services.rag_service import RagService

ds = DataSourceSettings()

LLM_CONFIG = LlmConfig(
    api_key="sk-fdc7d21b49ca45c08b5962fee5f4847f",
    base_url="https://api.deepseek.com/v1", model="deepseek-chat", timeout_seconds=90,
)

SUBJECT_KEYWORDS = [
    "税收收入", "非税收入", "卫生健康支出", "教育支出", "社会保障和就业支出",
    "农林水支出", "科学技术支出", "住房保障支出", "交通运输支出",
    "一般公共预算收入", "政府性基金收入", "国有资本经营预算收入", "社会保险基金收入",
    "债务付息支出", "公共安全支出", "国防支出", "节能环保支出",
    "城乡社区支出", "资源勘探信息支出", "商业服务业支出", "金融支出",
    "粮油物资储备支出", "灾害防治及应急管理支出", "文化旅游体育与传媒支出",
]

METRIC_ALIASES = {
    "本月金额": ["执行金额", "本月数", "本月执行金额", "当月金额"],
    "预算数": ["预算数", "年初预算", "调整预算"],
    "累计金额": ["累计金额", "累计数", "累计执行金额", "累计收入", "累计支出"],
    "同比增幅": ["同比增额", "同比增长率", "同比增长", "同比"],
    "环比增幅": ["环比增额", "环比增长率", "环比增长", "环比"],
    "预算执行率": ["执行率", "预算完成率"],
    "总计": ["总计", "合计", "总计多少", "合计多少"],
    "金额": ["金额"],
}

# ============================================================
# 边缘问题设计（按类别）
# ============================================================
EDGE_CASES = [
    # --- 类别1: 极度模糊 ---
    {
        "id": "E1", "category": "极度模糊",
        "question": "支出情况",
        "expect": "缺少科目/时间/地区，应 clarify",
    },
    {
        "id": "E2", "category": "极度模糊",
        "question": "收入",
        "expect": "只有一个字，无法判断意图",
    },
    {
        "id": "E3", "category": "极度模糊",
        "question": "完成多少",
        "expect": "缺少科目/时间/地区，应 clarify",
    },

    # --- 类别2: 多轮对话碎片 ---
    {
        "id": "E4", "category": "多轮对话碎片",
        "question": "比上年高多少",
        "expect": "无上下文，无法补全科目/时间，应 clarify",
    },
    {
        "id": "E5", "category": "多轮对话碎片",
        "question": "那2024年呢",
        "expect": "仅有年份，缺少科目/地区，应 clarify",
    },
    {
        "id": "E6", "category": "多轮对话碎片",
        "question": "再说说支出的构成",
        "expect": "缺少科目/时间/地区，但 need_composition 应为 true",
    },

    # --- 类别3: 跨四本账 ---
    {
        "id": "E7", "category": "跨四本账",
        "question": "四本账的收入分别多少",
        "expect": "四本账都需要查，科目模糊",
    },
    {
        "id": "E8", "category": "跨四本账",
        "question": "对比一般公共预算和政府性基金在卫生健康上的投入",
        "expect": "跨账本比较，科目+四本账交叉",
    },

    # --- 类别4: 嵌套科目 ---
    {
        "id": "E9", "category": "嵌套科目",
        "question": "卫生健康支出里面基本公共卫生服务的执行金额是多少",
        "expect": "嵌套科目，需要识别子科目",
    },
    {
        "id": "E10", "category": "嵌套科目",
        "question": "税收收入中增值税和企业所得税哪个贡献大",
        "expect": "嵌套比较，需要识别子科目+比较",
    },

    # --- 类别5: 口语/非标准表达 ---
    {
        "id": "E11", "category": "口语表达",
        "question": "去年全省花了多少钱在医疗上",
        "expect": "\"医疗\"→卫生健康支出，\"花了多少钱\"→支出金额，\"去年\"→2025",
    },
    {
        "id": "E12", "category": "口语表达",
        "question": "养老金这块儿现在咋样",
        "expect": "\"养老金\"→社会保险基金/社会保障支出，极其模糊",
    },

    # --- 类别6: 歧义/冲突 ---
    {
        "id": "E13", "category": "歧义",
        "question": "石家庄的收入",
        "expect": "\"石家庄\"是地区不是科目，容易误判",
    },
    {
        "id": "E14", "category": "歧义",
        "question": "教育 卫生健康 社保 这三项哪项支出增长最快",
        "expect": "三个科目比较 + 趋势",
    },

    # --- 类别7: 含无关信息 ---
    {
        "id": "E15", "category": "含无关信息",
        "question": "我们处长说想看看2025年全省的卫生健康支出到底执行得怎么样了",
        "expect": "需要过滤\"我们处长说想看看\"的噪音",
    },
    {
        "id": "E16", "category": "含无关信息",
        "question": "帮我查一下呗，2025年省本级的那个教育支出，预算完成了多少，谢谢啦",
        "expect": "口语化+礼貌用语，需要提取核心查询",
    },

    # --- 类别8: 相对时间 ---
    {
        "id": "E17", "category": "相对时间",
        "question": "近三年卫生健康支出的趋势",
        "expect": "\"近三年\"→2024/2025/2026，query_type=trend",
    },
    {
        "id": "E18", "category": "相对时间",
        "question": "这个月和上个月相比，收入变化了多少",
        "expect": "多轮依赖，无上下文",
    },
]

def setup():
    llm = LlmGateway(LLM_CONFIG)
    extractor = UnifiedIntentExtractor(llm, SUBJECT_KEYWORDS, METRIC_ALIASES)
    enricher = RagSlotEnricher(METRIC_ALIASES, SUBJECT_KEYWORDS)
    dispatcher = ConcurrentTaskDispatcher()

    rag_cfg = ds.rag_vector
    emb = CustomLocalEmbeddings(api_url="http://10.32.10.160:8991/embed")
    vs = PgVectorStore(connection=rag_cfg.connection_string, collection_name=rag_cfg.collection_name, embedding=emb)
    retriever = HybridRetriever(vector_store=vs, rerank_url="http://10.32.10.160:8991/rerank", top_k=5, recall_k=10)
    rag_service = RagService(retriever=retriever)

    return extractor, enricher, dispatcher, rag_service


def run():
    extractor, enricher, dispatcher, rag_service = setup()

    print("\n" + "=" * 80)
    print("RAG 反哺模块 — 边缘问题测试")
    print("=" * 80)

    for case in EDGE_CASES:
        q = case["question"]
        print(f"\n{'─' * 60}")
        print(f"[{case['id']}] {case['category']}: {q}")
        print(f"  预期: {case['expect']}")

        # 提取
        intent_v1 = extractor.extract(q)
        t1 = intent_v1.text2sql
        r1 = intent_v1.rag
        print(f"  v1: subjects={t1.subjects}, metrics={t1.metrics}, "
              f"flow={t1.flow_type}, region={t1.region_level}, "
              f"time={t1.time_text}, account={t1.account_book}")
        print(f"  rag_need: policy={r1.need_policy_basis}, caliber={r1.need_caliber_explanation}, "
              f"compos={r1.need_composition}, data={r1.need_data_value}")

        # RAG
        rag_result = rag_service.search(intent_v1.rag)
        n_snippets = len(rag_result.snippets) if rag_result.snippets else 0
        top = max((s.score for s in rag_result.snippets), default=0) if rag_result.snippets else 0

        # 反哺
        if t1.subjects or t1.metrics:
            intent_v2, log = enricher.enrich(intent_v1, rag_result.snippets, q)
            t2 = intent_v2.text2sql
            print(f"  反哺: filled={log.filled_slots}")
            if log.filled_slots:
                print(f"    candidates: {json.dumps({k: v[:2] for k,v in log.candidates.items()}, ensure_ascii=False)}")
            print(f"  v2: subjects={t2.subjects}, metrics={t2.metrics}, "
                  f"flow={t2.flow_type}, region={t2.region_level}, "
                  f"time={t2.time_text}, account={t2.account_book}")
            plan = dispatcher.dispatch(intent_v2)
        else:
            print(f"  纯RAG问题，跳过反哺")
            plan = dispatcher.dispatch(intent_v1)

        route = "fallback" if plan.fallback else ("clarify" if plan.clarify else ("both" if plan.text2sql and plan.rag else ("sql" if plan.text2sql else "rag")))
        print(f"  调度: {route} | RAG_snippets={n_snippets}, top_score={top:.3f}")

    print(f"\n{'=' * 80}")
    print("边缘问题测试完成")

if __name__ == "__main__":
    run()
