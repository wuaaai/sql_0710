"""PostgreSQL pgvector 向量存储实现。

完整复用自 dataQuery/text_smart_qa/src/agent/db/pgvector_store.py
提供：
1. 向量表构建（动态维度、ivfflat 索引）
2. 文档切片批量写入
3. 向量相似度检索（cosine/l2/inner_product）
4. metadata 过滤（精确匹配、$like 前缀、$or 组合、$in/$ne、数值比较）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, Text, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, declarative_base

Base = declarative_base()


# ============================================================
# metadata 过滤条件构造
# ============================================================

def _build_filter_clause(filter_dict: Optional[dict]) -> Tuple[str, Dict[str, Any]]:
    """把过滤字典转换成 SQL WHERE 条件。

    支持的操作符：
    - 精确匹配: {"key": "value"}
    - $like 前缀匹配: {"key": {"$like": "130000%"}}
    - $or 多条件: {"$or": [{"a": "1"}, {"b": "2"}]}
    - $in: {"key": {"$in": ["a", "b"]}}
    - $ne: {"key": {"$ne": "x"}}
    - 数值比较: {"key": {"$gte": 0.5, "$lte": 1.0}}
    """
    if not filter_dict:
        return "", {}

    params: Dict[str, Any] = {}
    counter = [0]

    def _next_param() -> str:
        counter[0] += 1
        return f"fp{counter[0]}"

    def _build_in_clause(key: str, values: List[Any]) -> str:
        placeholders: List[str] = []
        for item in values:
            param_name = _next_param()
            params[param_name] = item
            placeholders.append(f":{param_name}")
        if not placeholders:
            return "1=0"
        return f"(c_metadata->>'{key}') IN ({', '.join(placeholders)})"

    def _walk(node: Optional[dict]) -> str:
        if not node:
            return "1=1"

        if "$or" in node:
            or_parts = [_walk(item) for item in node["$or"] if item]
            if not or_parts:
                return "1=1"
            return "(" + " OR ".join(or_parts) + ")"

        clauses: List[str] = []
        for key, value in node.items():
            if key.startswith("$"):
                continue

            if isinstance(value, dict):
                for op, op_value in value.items():
                    if op == "$like":
                        param_name = _next_param()
                        params[param_name] = str(op_value)
                        clauses.append(f"(c_metadata->>'{key}') LIKE :{param_name}")
                    elif op == "$in":
                        clauses.append(_build_in_clause(key, list(op_value or [])))
                    elif op == "$ne":
                        param_name = _next_param()
                        params[param_name] = str(op_value)
                        clauses.append(f"(c_metadata->>'{key}') != :{param_name}")
                    elif op in {"$gte", "$lte", "$gt", "$lt"}:
                        param_name = _next_param()
                        params[param_name] = float(op_value)
                        sql_op = {"$gte": ">=", "$lte": "<=", "$gt": ">", "$lt": "<"}[op]
                        clauses.append(
                            f"CAST(c_metadata->>'{key}' AS DOUBLE PRECISION) {sql_op} :{param_name}"
                        )
            else:
                param_name = _next_param()
                params[param_name] = str(value)
                clauses.append(f"(c_metadata->>'{key}') = :{param_name}")

        return " AND ".join(clauses) if clauses else "1=1"

    return _walk(filter_dict), params


# ============================================================
# PgVectorStore — pgvector 向量存储
# ============================================================

class PgVectorStore(VectorStore):
    """基于 PostgreSQL pgvector 的向量存储。

    用法:
        store = PgVectorStore(
            connection="postgresql://user:pass@host:5432/db",
            collection_name="rag_knowledge",
            embedding=embeddings,
        )
        store.create_collection()
        store.add_documents(docs)
        results = store.similarity_search("查询文本", k=10, filter={"region_code": {"$like": "130000%"}})
    """

    def __init__(
        self,
        connection: str,
        collection_name: str,
        embedding: Embeddings,
        distance_strategy: str = "cosine",
        index_lists: int = 100,
    ):
        self.connection_string = connection
        self.collection_name = collection_name
        self.embedding = embedding
        self.distance_strategy = distance_strategy
        self.index_lists = index_lists
        self._engine = create_engine(connection, pool_pre_ping=True)
        self._table_cls = None

        if distance_strategy not in {"cosine", "l2", "inner_product"}:
            raise ValueError(f"不支持 distance_strategy: {distance_strategy}")

    @property
    def embeddings(self) -> Embeddings:
        return self.embedding

    # ---- 扩展与建表 ----

    def _ensure_extension(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

    def _get_table_cls(self, dim: Optional[int] = None):
        if self._table_cls is not None:
            return self._table_cls

        if dim is None:
            dim = self._get_dimension()
            if dim is None:
                raise ValueError("无法确定向量维度，请先写入数据后再执行检索。")

        table_name = self.collection_name

        class DynamicTable(Base):
            __tablename__ = table_name
            __table_args__ = {"extend_existing": True}

            id = Column(Integer, primary_key=True, autoincrement=True)
            c_document = Column(Text, nullable=False)
            c_embedding = Column(Vector(dim), nullable=False)
            c_metadata = Column(JSONB, nullable=False, default=dict)

        DynamicTable.__name__ = f"PgVectorTable_{table_name}"
        self._table_cls = DynamicTable
        return DynamicTable

    def _get_dimension(self) -> Optional[int]:
        with self._engine.connect() as conn:
            exists = conn.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_name = :name)"
                ),
                {"name": self.collection_name},
            ).scalar()
            if not exists:
                return None

            try:
                row = conn.execute(
                    text(f'SELECT vector_dims(c_embedding) FROM "{self.collection_name}" LIMIT 1')
                ).fetchone()
                if row and row[0]:
                    return int(row[0])
            except Exception:
                return None
        return None

    def _ensure_vector_index(self) -> None:
        operator_class = {
            "cosine": "vector_cosine_ops",
            "l2": "vector_l2_ops",
            "inner_product": "vector_ip_ops",
        }[self.distance_strategy]
        index_name = f"idx_{self.collection_name}_embedding_ivfflat"

        sql = (
            f'CREATE INDEX IF NOT EXISTS "{index_name}" '
            f'ON "{self.collection_name}" USING ivfflat '
            f'(c_embedding {operator_class}) WITH (lists = {int(self.index_lists)})'
        )

        with self._engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()

    # ---- 集合生命周期 ----

    def create_collection(self) -> None:
        self._ensure_extension()
        print(f"[pgvector] 集合 '{self.collection_name}' 将在首次写入时自动建表")

    def delete_collection(self) -> None:
        with self._engine.connect() as conn:
            conn.execute(text(f'DROP TABLE IF EXISTS "{self.collection_name}"'))
            conn.commit()
        print(f"[pgvector] 已删除集合 '{self.collection_name}'")

    # ---- 文档写入 ----

    def add_documents(
        self,
        documents: List[Document],
        batch_size: int = 32,
        **kwargs,
    ) -> List[str]:
        if not documents:
            return []

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata or {} for doc in documents]

        print(f"[pgvector] 正在为 {len(texts)} 个文档生成向量...")
        embeddings = self.embedding.embed_documents(texts)
        if not embeddings:
            return []

        dim = len(embeddings[0])
        self._ensure_extension()
        TableCls = self._get_table_cls(dim)
        Base.metadata.create_all(self._engine, tables=[TableCls.__table__])
        self._ensure_vector_index()

        ids: List[str] = []
        with Session(self._engine) as session:
            for start in range(0, len(documents), batch_size):
                end = min(start + batch_size, len(documents))
                for text_val, emb_val, meta_val in zip(
                    texts[start:end],
                    embeddings[start:end],
                    metadatas[start:end],
                ):
                    row = TableCls(
                        c_document=text_val,
                        c_embedding=emb_val,
                        c_metadata=meta_val,
                    )
                    session.add(row)
                    session.flush()
                    ids.append(str(row.id))
                session.commit()
                print(f"[pgvector] 已写入 {end}/{len(documents)}")

        print(f"[pgvector] 写入完成，共 {len(ids)} 条")
        return ids

    # ---- 相似度检索 ----

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter: Optional[dict] = None,
        **kwargs,
    ) -> List[Document]:
        query_embedding = self.embedding.embed_query(query)
        if not query_embedding:
            return []

        TableCls = self._get_table_cls()
        filter_clause, filter_params = _build_filter_clause(filter)

        with Session(self._engine) as session:
            if self.distance_strategy == "l2":
                distance_expr = TableCls.c_embedding.l2_distance(query_embedding)
            elif self.distance_strategy == "inner_product":
                distance_expr = TableCls.c_embedding.max_inner_product(query_embedding)
            else:
                distance_expr = TableCls.c_embedding.cosine_distance(query_embedding)

            query_builder = session.query(TableCls, distance_expr.label("_distance"))
            if filter_clause:
                query_builder = query_builder.filter(text(filter_clause)).params(**filter_params)

            rows = query_builder.order_by(text("_distance")).limit(k).all()

        documents: List[Document] = []
        for row, _distance in rows:
            metadata = row.c_metadata or {}
            documents.append(
                Document(
                    page_content=row.c_document,
                    metadata=metadata,
                )
            )
        return documents

    # ---- 兼容接口 ----

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
        **kwargs,
    ) -> List[str]:
        if metadatas is None:
            metadatas = [{} for _ in texts]
        documents = [
            Document(page_content=text_item, metadata=meta)
            for text_item, meta in zip(texts, metadatas)
        ]
        return self.add_documents(documents, **kwargs)

    @classmethod
    def from_texts(cls, texts, embedding, metadatas=None, **kwargs):
        raise NotImplementedError("请先显式创建 PgVectorStore，再调用 add_texts。")

    @classmethod
    def from_documents(cls, documents, embedding, **kwargs):
        raise NotImplementedError("请先显式创建 PgVectorStore，再调用 add_documents。")


# ============================================================
# VectorStoreClient — 兼容新项目命名的别名
# ============================================================

VectorStoreClient = PgVectorStore
