"""项目配置加载模块。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_METADATA_DIR = Path(r"D:\pythonPro\dataQuery\table_vector_rebuild\metadata")


def _load_env_files() -> None:
    """加载项目配置文件，后加载的本地配置会覆盖前面的默认配置。"""
    load_dotenv(BASE_DIR / ".env", override=False)
    load_dotenv(BASE_DIR / ".env.local", override=True)


_load_env_files()


@dataclass(frozen=True)
class LLMConfig:
    """大模型服务配置。"""

    api_key: str
    base_url: str
    model: str
    timeout_seconds: int = 90


@dataclass(frozen=True)
class EmbeddingConfig:
    """向量化服务配置。"""

    url: str
    dimension: int
    timeout_seconds: int = 60


@dataclass(frozen=True)
class PGVectorConfig:
    """pgvector 检索库配置。"""

    host: str
    port: int
    dbname: str
    user: str
    password: str
    version: str


@dataclass(frozen=True)
class DamengConfig:
    """达梦数据库配置。"""

    host: str
    port: int
    user: str
    password: str
    schema: str


@dataclass(frozen=True)
class MetadataConfig:
    """元数据和表能力矩阵配置。"""

    schema_meta_path: Path
    table_info_path: Path
    capability_matrix_path: Path | None = None


@dataclass(frozen=True)
class AppConfig:
    """项目总配置对象。"""

    llm: LLMConfig
    embedding: EmbeddingConfig
    pgvector: PGVectorConfig
    dameng: DamengConfig
    metadata: MetadataConfig


def load_config() -> AppConfig:
    """把环境变量整理成项目内部统一使用的配置对象。"""
    return AppConfig(
        llm=LLMConfig(
            api_key=os.getenv("DEEPSEEK_API_KEY", "YOUR_DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            timeout_seconds=int(os.getenv("DEEPSEEK_TIMEOUT", "90")),
        ),
        embedding=EmbeddingConfig(
            url=os.getenv("VECTOR_EMBEDDING_URL", "http://10.32.10.160:8991/embed"),
            dimension=int(os.getenv("VECTOR_DIM", "1024")),
            timeout_seconds=int(os.getenv("VECTOR_TIMEOUT", "60")),
        ),
        pgvector=PGVectorConfig(
            host=os.getenv("PGVECTOR_HOST", "localhost"),
            port=int(os.getenv("PGVECTOR_PORT", "5435")),
            dbname=os.getenv("PGVECTOR_DB", "text2sql_vector"),
            user=os.getenv("PGVECTOR_USER", "hbch"),
            password=os.getenv("PGVECTOR_PASSWORD", "hbch2711"),
            version=os.getenv("PGVECTOR_VERSION", "v1"),
        ),
        dameng=DamengConfig(
            host=os.getenv("DM_HOST", "localhost"),
            port=int(os.getenv("DM_PORT", "5236")),
            user=os.getenv("DM_USER", "SYSDBA"),
            password=os.getenv("DM_PASSWORD", "SYSDBA001"),
            schema=os.getenv("DM_SCHEMA", "RDYS_PUBLIC_TBS_DM"),
        ),
        metadata=MetadataConfig(
            schema_meta_path=Path(
                os.getenv("QA_SCHEMA_META_PATH", str(DEFAULT_METADATA_DIR / "RDYS_PUBLIC_TBS.json"))
            ),
            table_info_path=Path(
                os.getenv("QA_TABLE_INFO_PATH", str(DEFAULT_METADATA_DIR / "table_info.json"))
            ),
            capability_matrix_path=Path(os.getenv("QA_TABLE_CAPABILITY_PATH"))
            if os.getenv("QA_TABLE_CAPABILITY_PATH")
            else None,
        ),
    )
