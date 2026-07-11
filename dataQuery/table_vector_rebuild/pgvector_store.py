from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence

import pg8000.native

from config import PGVectorConfig


@dataclass(frozen=True)
class TableProfileRow:
    id: str
    version: str
    table_en: str
    table_zh: str
    chunk_type: str
    content: str
    content_norm: str
    budget_type: str
    is_provincial: bool
    status: str
    embedding: List[float]


@dataclass(frozen=True)
class SubjectBindingRow:
    id: str
    version: str
    table_en: str
    table_zh: str
    subject_name: str
    subject_name_norm: str
    select_code: str
    table_select_text: str
    subject_type: str
    is_provincial: bool
    status: str
    embedding: List[float]


@dataclass(frozen=True)
class MetricAliasRow:
    id: str
    version: str
    table_en: str
    table_zh: str
    metric_name: str
    metric_name_norm: str
    column_name: str
    unit: str
    status: str
    embedding: List[float]


class PGVectorStore:
    def __init__(self, config: PGVectorConfig):
        self._config = config
        self._conn = pg8000.native.Connection(
            host=config.host,
            port=config.port,
            database=config.dbname,
            user=config.user,
            password=config.password,
            timeout=60,
            ssl_context=False  # 禁用 SSL
        )

    def close(self) -> None:
        self._conn.close()

    def init_schema(self, dimension: int) -> None:
        self._conn.run("CREATE EXTENSION IF NOT EXISTS vector")

        self._conn.run(
            f"""
            CREATE TABLE IF NOT EXISTS vec_table_profile (
                id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                table_en TEXT NOT NULL,
                table_zh TEXT NOT NULL,
                chunk_type TEXT NOT NULL,
                content TEXT NOT NULL,
                content_norm TEXT NOT NULL,
                budget_type TEXT NOT NULL DEFAULT '',
                is_provincial BOOLEAN NOT NULL DEFAULT FALSE,
                status TEXT NOT NULL DEFAULT 'active',
                embedding vector({dimension})
            )
            """
        )
        self._conn.run(
            f"""
            CREATE TABLE IF NOT EXISTS vec_subject_binding (
                id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                table_en TEXT NOT NULL,
                table_zh TEXT NOT NULL,
                subject_name TEXT NOT NULL,
                subject_name_norm TEXT NOT NULL,
                select_code TEXT NOT NULL DEFAULT '',
                table_select_text TEXT NOT NULL DEFAULT '',
                subject_type TEXT NOT NULL DEFAULT '',
                is_provincial BOOLEAN NOT NULL DEFAULT FALSE,
                status TEXT NOT NULL DEFAULT 'active',
                embedding vector({dimension})
            )
            """
        )
        self._conn.run(
            f"""
            CREATE TABLE IF NOT EXISTS vec_metric_alias (
                id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                table_en TEXT NOT NULL,
                table_zh TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_name_norm TEXT NOT NULL,
                column_name TEXT NOT NULL,
                unit TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'active',
                embedding vector({dimension})
            )
            """
        )

        self._create_indexes()

    def replace_version(
        self,
        version: str,
        table_profiles: Sequence[TableProfileRow],
        subject_bindings: Sequence[SubjectBindingRow],
        metric_aliases: Sequence[MetricAliasRow],
    ) -> None:
        self._conn.run("BEGIN")
        try:
            self._conn.run("DELETE FROM vec_table_profile WHERE version = :version", version=version)
            self._conn.run("DELETE FROM vec_subject_binding WHERE version = :version", version=version)
            self._conn.run("DELETE FROM vec_metric_alias WHERE version = :version", version=version)

            for row in table_profiles:
                self._upsert_table_profile(row)
            for row in subject_bindings:
                self._upsert_subject_binding(row)
            for row in metric_aliases:
                self._upsert_metric_alias(row)

            self._conn.run("COMMIT")
        except Exception:
            self._conn.run("ROLLBACK")
            raise

    def _create_indexes(self) -> None:
        statements = [
            "CREATE INDEX IF NOT EXISTS vec_table_profile_version_idx ON vec_table_profile (version)",
            "CREATE INDEX IF NOT EXISTS vec_table_profile_table_en_idx ON vec_table_profile (table_en)",
            "CREATE INDEX IF NOT EXISTS vec_table_profile_chunk_type_idx ON vec_table_profile (chunk_type)",
            (
                "CREATE INDEX IF NOT EXISTS vec_table_profile_embedding_idx "
                "ON vec_table_profile USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            ),
            "CREATE INDEX IF NOT EXISTS vec_subject_binding_version_idx ON vec_subject_binding (version)",
            "CREATE INDEX IF NOT EXISTS vec_subject_binding_table_en_idx ON vec_subject_binding (table_en)",
            "CREATE INDEX IF NOT EXISTS vec_subject_binding_subject_norm_idx ON vec_subject_binding (subject_name_norm)",
            (
                "CREATE INDEX IF NOT EXISTS vec_subject_binding_embedding_idx "
                "ON vec_subject_binding USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            ),
            "CREATE INDEX IF NOT EXISTS vec_metric_alias_version_idx ON vec_metric_alias (version)",
            "CREATE INDEX IF NOT EXISTS vec_metric_alias_table_en_idx ON vec_metric_alias (table_en)",
            "CREATE INDEX IF NOT EXISTS vec_metric_alias_metric_norm_idx ON vec_metric_alias (metric_name_norm)",
            (
                "CREATE INDEX IF NOT EXISTS vec_metric_alias_embedding_idx "
                "ON vec_metric_alias USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            ),
        ]
        for sql in statements:
            try:
                self._conn.run(sql)
            except Exception:
                pass

    def _upsert_table_profile(self, row: TableProfileRow) -> None:
        self._conn.run(
            """
            INSERT INTO vec_table_profile
                (id, version, table_en, table_zh, chunk_type, content, content_norm,
                 budget_type, is_provincial, status, embedding)
            VALUES
                (:id, :version, :table_en, :table_zh, :chunk_type, :content, :content_norm,
                 :budget_type, :is_provincial, :status, :embedding::vector)
            ON CONFLICT (id) DO UPDATE SET
                version = EXCLUDED.version,
                table_en = EXCLUDED.table_en,
                table_zh = EXCLUDED.table_zh,
                chunk_type = EXCLUDED.chunk_type,
                content = EXCLUDED.content,
                content_norm = EXCLUDED.content_norm,
                budget_type = EXCLUDED.budget_type,
                is_provincial = EXCLUDED.is_provincial,
                status = EXCLUDED.status,
                embedding = EXCLUDED.embedding
            """,
            id=row.id,
            version=row.version,
            table_en=row.table_en,
            table_zh=row.table_zh,
            chunk_type=row.chunk_type,
            content=row.content,
            content_norm=row.content_norm,
            budget_type=row.budget_type,
            is_provincial=row.is_provincial,
            status=row.status,
            embedding=_vector_to_str(row.embedding),
        )

    def _upsert_subject_binding(self, row: SubjectBindingRow) -> None:
        self._conn.run(
            """
            INSERT INTO vec_subject_binding
                (id, version, table_en, table_zh, subject_name, subject_name_norm,
                 select_code, table_select_text, subject_type, is_provincial, status, embedding)
            VALUES
                (:id, :version, :table_en, :table_zh, :subject_name, :subject_name_norm,
                 :select_code, :table_select_text, :subject_type, :is_provincial, :status, :embedding::vector)
            ON CONFLICT (id) DO UPDATE SET
                version = EXCLUDED.version,
                table_en = EXCLUDED.table_en,
                table_zh = EXCLUDED.table_zh,
                subject_name = EXCLUDED.subject_name,
                subject_name_norm = EXCLUDED.subject_name_norm,
                select_code = EXCLUDED.select_code,
                table_select_text = EXCLUDED.table_select_text,
                subject_type = EXCLUDED.subject_type,
                is_provincial = EXCLUDED.is_provincial,
                status = EXCLUDED.status,
                embedding = EXCLUDED.embedding
            """,
            id=row.id,
            version=row.version,
            table_en=row.table_en,
            table_zh=row.table_zh,
            subject_name=row.subject_name,
            subject_name_norm=row.subject_name_norm,
            select_code=row.select_code,
            table_select_text=row.table_select_text,
            subject_type=row.subject_type,
            is_provincial=row.is_provincial,
            status=row.status,
            embedding=_vector_to_str(row.embedding),
        )

    def _upsert_metric_alias(self, row: MetricAliasRow) -> None:
        self._conn.run(
            """
            INSERT INTO vec_metric_alias
                (id, version, table_en, table_zh, metric_name, metric_name_norm,
                 column_name, unit, status, embedding)
            VALUES
                (:id, :version, :table_en, :table_zh, :metric_name, :metric_name_norm,
                 :column_name, :unit, :status, :embedding::vector)
            ON CONFLICT (id) DO UPDATE SET
                version = EXCLUDED.version,
                table_en = EXCLUDED.table_en,
                table_zh = EXCLUDED.table_zh,
                metric_name = EXCLUDED.metric_name,
                metric_name_norm = EXCLUDED.metric_name_norm,
                column_name = EXCLUDED.column_name,
                unit = EXCLUDED.unit,
                status = EXCLUDED.status,
                embedding = EXCLUDED.embedding
            """,
            id=row.id,
            version=row.version,
            table_en=row.table_en,
            table_zh=row.table_zh,
            metric_name=row.metric_name,
            metric_name_norm=row.metric_name_norm,
            column_name=row.column_name,
            unit=row.unit,
            status=row.status,
            embedding=_vector_to_str(row.embedding),
        )


def _vector_to_str(vec: List[float]) -> str:
    return f"[{','.join(str(v) for v in vec)}]"
