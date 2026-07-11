"""FastAPI 服务入口。

这个文件负责把问数能力包装成一个 HTTP 服务，
方便前端、Dify 或其他系统通过接口调用。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

from config import load_config
from dameng_executor import DamengExecutor
from embedding_client import EmbeddingClient
from entity_resolver import EntityResolver
from llm_client import DeepSeekClient
from metadata import load_metadata
from qa_pipeline import FiscalQaPipeline
from query_compiler import QueryCompiler
from result_analyzer import ResultAnalyzer
from vector_retriever import VectorRetriever


class QueryRequest(BaseModel):
    """接口入参：用户输入的自然语言问题。"""

    question: str


def create_app() -> FastAPI:
    """创建并初始化 FastAPI 应用。"""
    config = load_config()
    metadata = load_metadata(config.metadata)
    llm_client = DeepSeekClient(config.llm)
    embeddings = EmbeddingClient(config.embedding)
    retriever = VectorRetriever(config.pgvector, embeddings)
    resolver = EntityResolver(retriever, metadata)
    compiler = QueryCompiler(metadata, schema_name=config.dameng.schema)
    executor = DamengExecutor(config.dameng)
    analyzer = ResultAnalyzer(llm_client)
    pipeline = FiscalQaPipeline(
        llm_client=llm_client,
        entity_resolver=resolver,
        compiler=compiler,
        executor=executor,
        analyzer=analyzer,
    )

    app = FastAPI(title="Fiscal Smart QA")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def index():
        """返回一个简单的本地调试页面。"""
        return FileResponse(Path(__file__).resolve().parent / "templates" / "index.html")

    @app.get("/health")
    def health():
        """健康检查接口，用于确认服务是否已启动。"""
        return {"status": "ok"}

    @app.post("/api/query")
    def query_data(payload: QueryRequest):
        """执行完整问数流程，并返回调试信息和最终结果。"""
        result = pipeline.run(payload.question)
        return {
            "plan": result.plan.to_dict(),
            "intent": result.intent.__dict__,
            "domain_route": {
                "business_module": result.resolved.domain_route.business_module,
                "account_book": result.resolved.domain_route.account_book,
                "flow_type": result.resolved.domain_route.flow_type,
                "region_level": result.resolved.domain_route.region_level,
                "data_stage": result.resolved.domain_route.data_stage,
                "time_grain": result.resolved.domain_route.time_grain,
                "reasons": result.resolved.domain_route.reasons,
            },
            "allowed_table_count": len(result.resolved.allowed_tables),
            "selected_table": {
                "table_en": result.resolved.selected_table.table_en,
                "table_zh": result.resolved.selected_table.table_zh,
                "score": result.resolved.selected_table.score,
                "reason": result.resolved.selected_table.reason,
            },
            "subject_match": result.resolved.subject_hits[0].payload if result.resolved.subject_hits else None,
            "subject_matches": [hit.payload for hit in result.resolved.subject_hits],
            "metric_match": result.resolved.metric_hits[0].payload if result.resolved.metric_hits else None,
            "metric_matches": [hit.payload for hit in result.resolved.metric_hits],
            "sql": result.compiled.sql,
            "rows": result.rows,
            "analysis": result.analysis.summary,
            "analysis_facts": result.analysis.facts,
            "chart": result.chart,
            "candidates": [
                {
                    "table_en": item.table_en,
                    "table_zh": item.table_zh,
                    "score": item.score,
                    "reason": item.reason,
                }
                for item in result.resolved.table_candidates
            ],
        }

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
