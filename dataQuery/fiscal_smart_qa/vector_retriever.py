"""向量检索模块。

这个模块负责访问 pgvector 中的三类向量索引：
1. 表画像向量
2. 指标别名向量
3. 科目绑定向量

上层流程只需要调用这里的方法，不需要关心具体的 SQL 查询细节。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pg8000.native

from config import PGVectorConfig
from embedding_client import EmbeddingClient


@dataclass
class SearchHit:
    """表示一次向量检索命中的结果。"""

    table_en: str
    table_zh: str
    score: float
    payload: Dict[str, Any]


class VectorRetriever:
    """封装 pgvector 检索能力。"""

    def __init__(self, config: PGVectorConfig, embeddings: EmbeddingClient):
        """初始化数据库连接和向量编码器。"""
        self._config = config
        self._embeddings = embeddings
        self._conn = pg8000.native.Connection(
            host=config.host,
            port=config.port,
            database=config.dbname,
            user=config.user,
            password=config.password,
            timeout=60,
            ssl_context=False,
        )

    def close(self) -> None:
        """关闭 pgvector 数据库连接。"""
        self._conn.close()

    def search_table_profiles(
        self,
        question: str,
        limit: int = 8,
        allowed_tables: Optional[List[str]] = None,
    ) -> List[SearchHit]:
        """根据问题检索最相关的表画像。"""
        query_vector = self._embeddings.embed_one(question)
        table_filter_sql = _build_table_filter_sql(allowed_tables)
        rows = self._conn.run(
            f"""
            SELECT table_en, table_zh, chunk_type, content, budget_type, is_provincial,
                   1 - (embedding <=> :vec::vector) AS score
            FROM vec_table_profile
            WHERE version = :version AND status = 'active' {table_filter_sql}
            ORDER BY embedding <=> :vec2::vector
            LIMIT :lim
            """,
            vec=_vector_to_str(query_vector),
            vec2=_vector_to_str(query_vector),
            version=self._config.version,
            lim=limit,
        )
        return [
            SearchHit(
                table_en=row[0],
                table_zh=row[1],
                score=float(row[6]),
                payload={
                    "chunk_type": row[2],
                    "content": row[3],
                    "budget_type": row[4],
                    "is_provincial": row[5],
                },
            )
            for row in rows
        ]

    def search_metric_aliases(
        self,
        question: str,
        limit: int = 6,
        table_en: Optional[str] = None,
        allowed_tables: Optional[List[str]] = None,
    ) -> List[SearchHit]:
        """检索与问题最接近的指标别名。"""
        query_vector = self._embeddings.embed_one(question)
        where_parts = [_build_table_filter_sql(allowed_tables)]
        if table_en:
            where_parts.append(f" AND table_en = '{_escape_sql_value(table_en)}'")
        rows = self._conn.run(
            f"""
            SELECT table_en, table_zh, metric_name, metric_name_norm, column_name, unit,
                   1 - (embedding <=> :vec::vector) AS score
            FROM vec_metric_alias
            WHERE version = :version AND status = 'active' {''.join(where_parts)}
            ORDER BY embedding <=> :vec2::vector
            LIMIT :lim
            """,
            vec=_vector_to_str(query_vector),
            vec2=_vector_to_str(query_vector),
            version=self._config.version,
            lim=limit,
        )
        return [
            SearchHit(
                table_en=row[0],
                table_zh=row[1],
                score=float(row[6]),
                payload={
                    "metric_name": row[2],
                    "metric_name_norm": row[3],
                    "column_name": row[4],
                    "unit": row[5],
                },
            )
            for row in rows
        ]

    def search_subject_bindings(
        self,
        question: str,
        limit: int = 8,
        table_en: Optional[str] = None,
        allowed_tables: Optional[List[str]] = None,
    ) -> List[SearchHit]:
        """检索与问题相关的科目绑定信息。"""
        query_vector = self._embeddings.embed_one(question)
        where_parts = [_build_table_filter_sql(allowed_tables)]
        if table_en:
            where_parts.append(f" AND table_en = '{_escape_sql_value(table_en)}'")
        rows = self._conn.run(
            f"""
            SELECT table_en, table_zh, subject_name, subject_name_norm, select_code, table_select_text,
                   1 - (embedding <=> :vec::vector) AS score
            FROM vec_subject_binding
            WHERE version = :version AND status = 'active' {''.join(where_parts)}
            ORDER BY embedding <=> :vec2::vector
            LIMIT :lim
            """,
            vec=_vector_to_str(query_vector),
            vec2=_vector_to_str(query_vector),
            version=self._config.version,
            lim=limit,
        )
        return [
            SearchHit(
                table_en=row[0],
                table_zh=row[1],
                score=float(row[6]),
                payload={
                    "subject_name": row[2],
                    "subject_name_norm": row[3],
                    "select_code": row[4],
                    "table_select_text": row[5],
                },
            )
            for row in rows
        ]

    def find_exact_subjects(
        self,
        normalized_subject: str,
        limit: int = 10,
        allowed_tables: Optional[List[str]] = None,
    ) -> List[SearchHit]:
        """做一次精确或近似精确的科目匹配。"""
        if not normalized_subject:
            return []
        table_filter_sql = _build_table_filter_sql(allowed_tables)
        rows = self._conn.run(
            f"""
            SELECT table_en, table_zh, subject_name, subject_name_norm, select_code, table_select_text
            FROM vec_subject_binding
            WHERE version = :version
              AND status = 'active'
              {table_filter_sql}
              AND (
                    subject_name_norm = :term
                 OR position(:term in subject_name_norm) > 0
                 OR position(subject_name_norm in :term) > 0
              )
            LIMIT :lim
            """,
            version=self._config.version,
            term=normalized_subject,
            lim=limit,
        )
        return [
            SearchHit(
                table_en=row[0],
                table_zh=row[1],
                score=1.0,
                payload={
                    "subject_name": row[2],
                    "subject_name_norm": row[3],
                    "select_code": row[4],
                    "table_select_text": row[5],
                },
            )
            for row in rows
        ]


def _build_table_filter_sql(allowed_tables: Optional[List[str]]) -> str:
    """把允许参与检索的表名拼成 SQL 条件。"""
    if not allowed_tables:
        return ""
    escaped = ", ".join(f"'{_escape_sql_value(name)}'" for name in allowed_tables)
    return f" AND table_en IN ({escaped})"


def _escape_sql_value(value: str) -> str:
    """对 SQL 字符串做最基本的单引号转义。"""
    return str(value).replace("'", "''")


def _vector_to_str(vec: List[float]) -> str:
    """把向量数组转成 pgvector 可识别的字符串格式。"""
    return f"[{','.join(str(v) for v in vec)}]"
