"""启动前快速检查脚本。"""

from __future__ import annotations

from config import load_config
from dameng_executor import DamengExecutor
from embedding_client import EmbeddingClient
from metadata import load_metadata
from vector_retriever import VectorRetriever


def main() -> None:
    """按顺序检查元数据、向量库、达梦和 embedding 服务是否可用。"""
    config = load_config()
    print("[1] Loading metadata...")
    metadata = load_metadata(config.metadata)
    print(f"    schema tables: {len(metadata.schema_meta.get('tables', {}))}")
    print(f"    table_info rows: {len(metadata.table_info)}")

    print("[2] Checking pgvector...")
    embeddings = EmbeddingClient(config.embedding)
    retriever = VectorRetriever(config.pgvector, embeddings)
    try:
        table_hits = retriever.search_table_profiles("2025年10月一般公共预算收入中税收收入合计是多少？", limit=3)
        print(f"    table hits: {len(table_hits)}")
    finally:
        retriever.close()

    print("[3] Checking Dameng...")
    dm = DamengExecutor(config.dameng)
    rows = dm.query("SELECT 1 AS OK FROM DUAL")
    print(f"    dameng ok: {rows}")

    print("[4] Checking DeepSeek config...")
    if config.llm.api_key:
        print("    api key: configured")
    else:
        print("    api key: missing")

    print("[5] Checking embedding service...")
    vector = embeddings.embed_one("测试向量服务")
    print(f"    embedding dimension: {len(vector)}")

    print("Quick check finished.")


if __name__ == "__main__":
    main()
