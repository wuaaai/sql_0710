"""兼容层。

历史代码曾通过 `VastbaseVectorStore` 访问 Vastbase G100 的 floatvector。
现在项目已经统一切换到 PostgreSQL pgvector，因此这里保留同名导出，
避免旧代码导入时报错。
"""

from text_smart_qa.src.agent.db.pgvector_store import PgVectorStore

VastbaseVectorStore = PgVectorStore
