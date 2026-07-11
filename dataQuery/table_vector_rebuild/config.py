from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
METADATA_DIR = BASE_DIR / "metadata"
DEFAULT_TABLE_INFO_PATH = METADATA_DIR / "table_info.json"
DEFAULT_SCHEMA_META_PATH = METADATA_DIR / "RDYS_PUBLIC_TBS.json"


@dataclass(frozen=True)
class EmbeddingConfig:
    url: str
    dimension: int = 1024
    timeout_seconds: int = 60


@dataclass(frozen=True)
class PGVectorConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str


@dataclass(frozen=True)
class DamengConfig:
    host: str
    port: int
    user: str
    password: str
    schema: str


@dataclass(frozen=True)
class MetadataConfig:
    table_info_path: Path
    schema_meta_path: Path


@dataclass(frozen=True)
class AppConfig:
    embedding: EmbeddingConfig
    pgvector: PGVectorConfig
    dameng: DamengConfig
    metadata: MetadataConfig


def load_config() -> AppConfig:
    return AppConfig(
        embedding=EmbeddingConfig(
            url=os.getenv("VECTOR_EMBEDDING_URL", "http://10.32.10.160:8991/embed"),
            dimension=int(os.getenv("VECTOR_DIM", "1024")),
            timeout_seconds=int(os.getenv("VECTOR_TIMEOUT", "60")),
        ),
        pgvector=PGVectorConfig(
            host=os.getenv("PGVECTOR_HOST", "10.32.10.160"),
            port=int(os.getenv("PGVECTOR_PORT", "5433")),
            dbname=os.getenv("PGVECTOR_DB", "text2sql_dm_vector"),
            user=os.getenv("PGVECTOR_USER", "hbch"),
            password=os.getenv("PGVECTOR_PASSWORD", "hbch2711"),
        ),
        dameng=DamengConfig(
            host=os.getenv("DM_HOST", "localhost"),
            port=int(os.getenv("DM_PORT", "5236")),
            user=os.getenv("DM_USER", "SYSDBA"),
            password=os.getenv("DM_PASSWORD", "SYSDBA001"),
            schema=os.getenv("DM_SCHEMA", "RDYS_PUBLIC_TBS_DM"),
        ),
        metadata=MetadataConfig(
            table_info_path=Path(os.getenv("DM_TABLE_INFO_PATH", str(DEFAULT_TABLE_INFO_PATH))),
            schema_meta_path=Path(os.getenv("DM_SCHEMA_META_PATH", str(DEFAULT_SCHEMA_META_PATH))),
        ),
    )
