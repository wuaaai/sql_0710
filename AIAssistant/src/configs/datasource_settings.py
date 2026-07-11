"""数据源配置 — 统一管理 pgvector 向量库和达梦数据库连接。

从 .env 文件加载配置，与 dataQuery 和 sql_0623 的连接参数保持一致。
"""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

# 加载 .env 文件
_ENV_FILE = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
if os.path.exists(_ENV_FILE):
    load_dotenv(_ENV_FILE, override=False)
# 本地覆盖（优先级更高）
_LOCAL_ENV = os.path.join(os.path.dirname(__file__), "..", "..", ".env.local")
if os.path.exists(_LOCAL_ENV):
    load_dotenv(_LOCAL_ENV, override=True)


@dataclass
class PgvectorConfig:
    """pgvector text2sql 选表向量库配置 — 参考 dataQuery fiscal_smart_qa。"""

    host: str = field(default_factory=lambda: os.getenv("PGVECTOR_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("PGVECTOR_PORT", "5433")))
    dbname: str = field(default_factory=lambda: os.getenv("PGVECTOR_DB", "text2sql_dm_vector"))
    user: str = field(default_factory=lambda: os.getenv("PGVECTOR_USER", "hbch"))
    password: str = field(default_factory=lambda: os.getenv("PGVECTOR_PASSWORD", ""))
    version: str = field(default_factory=lambda: os.getenv("PGVECTOR_VERSION", "v1"))

    @property
    def connection_string(self) -> str:
        """构造 SQLAlchemy 连接字符串。"""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.dbname}"
        )


@dataclass
class RagVectorConfig:
    """pgvector RAG 知识库配置 — 参考 sql_0623。"""

    connection_string: str = field(
        default_factory=lambda: os.getenv(
            "RAG_DB_CONNECTION",
            "postgresql+psycopg2://postgres:ROOT@127.0.0.1:5432/postgres",
        )
    )
    collection_name: str = field(
        default_factory=lambda: os.getenv("RAG_COLLECTION", "parent_child_db_1024")
    )


@dataclass
class DamengConfig:
    """达梦数据库配置 — 参考 sql_0623。"""

    host: str = field(default_factory=lambda: os.getenv("DM_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("DM_PORT", "5236")))
    user: str = field(default_factory=lambda: os.getenv("DM_USER", "SYSDBA"))
    password: str = field(default_factory=lambda: os.getenv("DM_PASSWORD", ""))
    schema: str = field(default_factory=lambda: os.getenv("DM_SCHEMA", "RDYS_PUBLIC_TBS"))


@dataclass
class DataSourceSettings:
    """数据源总配置。"""

    pgvector: PgvectorConfig = field(default_factory=PgvectorConfig)
    rag_vector: RagVectorConfig = field(default_factory=RagVectorConfig)
    dameng: DamengConfig = field(default_factory=DamengConfig)
