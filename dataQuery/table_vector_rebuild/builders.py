from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from dameng_source import DamengSource
from embedding_client import EmbeddingClient
from metadata_loader import LoadedMetadata
from normalizers import clean_text_block, normalize_text, stable_id, unique_list
from pgvector_store import MetricAliasRow, SubjectBindingRow, TableProfileRow


class VectorRebuildService:
    def __init__(
        self,
        metadata: LoadedMetadata,
        source: DamengSource,
        embeddings: EmbeddingClient,
    ):
        self._metadata = metadata
        self._source = source
        self._embeddings = embeddings
        self._schema_tables = metadata.schema_meta["tables"]

    def build_table_profiles(self, version: str) -> List[TableProfileRow]:
        rows: List[TableProfileRow] = []
        for table_en, table_meta in self._schema_tables.items():
            table_zh = table_meta.get("comment", table_en)
            table_info = self._metadata.table_info.get(table_zh, {})
            chunks = self._split_auto_profile_chunks(table_en, table_zh, table_info)
            vectors = self._embeddings.embed_many([chunk["content"] for chunk in chunks])
            for chunk, vector in zip(chunks, vectors):
                rows.append(
                    TableProfileRow(
                        id=stable_id("table_profile", version, table_en, chunk["chunk_type"], chunk["content_norm"]),
                        version=version,
                        table_en=table_en,
                        table_zh=table_zh,
                        chunk_type=chunk["chunk_type"],
                        content=chunk["content"],
                        content_norm=chunk["content_norm"],
                        budget_type=table_info.get("cate", ""),
                        is_provincial=bool(table_info.get("is_sheng", 0)),
                        status="active",
                        embedding=vector,
                    )
                )
        return rows

    def build_subject_bindings(self, version: str) -> List[SubjectBindingRow]:
        rows: List[SubjectBindingRow] = []
        for table_zh, table_info in self._metadata.table_info.items():
            table_en = table_info.get("table")
            if not table_en or table_en not in self._schema_tables:
                continue

            subject_name_column = self._resolve_subject_name_column(table_en, table_info)
            if not subject_name_column:
                continue
            subject_code_column = self._resolve_subject_code_column(table_en, table_info)

            source_rows = self._source.fetch_distinct_subject_rows(
                table_name=table_en,
                subject_name_column=subject_name_column,
                subject_code_column=subject_code_column,
            )
            payload_texts: List[str] = []
            payload_rows: List[Tuple[str, str, str]] = []
            for subject_name, select_code in source_rows:
                normalized = normalize_text(subject_name)
                if not normalized or normalized == "合计":
                    continue
                display_name = clean_text_block(str(subject_name))
                payload_texts.append(f"{table_zh} 可查询科目: {display_name}")
                payload_rows.append((display_name, normalized, select_code or ""))

            vectors = self._embeddings.embed_many(payload_texts) if payload_texts else []
            for (subject_name, normalized, select_code), vector in zip(payload_rows, vectors):
                rows.append(
                    SubjectBindingRow(
                        id=stable_id("subject_binding", version, table_en, normalized, select_code),
                        version=version,
                        table_en=table_en,
                        table_zh=table_zh,
                        subject_name=subject_name,
                        subject_name_norm=normalized,
                        select_code=select_code,
                        table_select_text=subject_name,
                        subject_type=self._infer_subject_type(subject_name_column),
                        is_provincial=bool(table_info.get("is_sheng", 0)),
                        status="active",
                        embedding=vector,
                    )
                )
        return rows

    def build_metric_aliases(self, version: str) -> List[MetricAliasRow]:
        rows: List[MetricAliasRow] = []
        payload_texts: List[str] = []
        row_specs: List[Tuple[str, str, str, str, str, str]] = []

        for table_zh, table_info in self._metadata.table_info.items():
            table_en = table_info.get("table")
            schema_table = self._schema_tables.get(table_en or "")
            if not table_en or not schema_table:
                continue

            unit_map = table_info.get("unit", {})
            for unit, fields in unit_map.items():
                for column_name, metric_desc in fields.items():
                    metric_name = clean_text_block(metric_desc)
                    metric_norm = normalize_text(metric_name)
                    if not metric_norm:
                        continue
                    payload_texts.append(f"{table_zh} 指标: {metric_name}")
                    row_specs.append((table_en, table_zh, metric_name, metric_norm, column_name, unit))

        vectors = self._embeddings.embed_many(payload_texts) if payload_texts else []
        for spec, vector in zip(row_specs, vectors):
            table_en, table_zh, metric_name, metric_norm, column_name, unit = spec
            rows.append(
                MetricAliasRow(
                    id=stable_id("metric_alias", version, table_en, column_name, metric_norm),
                    version=version,
                    table_en=table_en,
                    table_zh=table_zh,
                    metric_name=metric_name,
                    metric_name_norm=metric_norm,
                    column_name=column_name,
                    unit=unit,
                    status="active",
                    embedding=vector,
                )
            )
        return rows

    def _split_auto_profile_chunks(self, table_en: str, table_zh: str, table_info: dict) -> List[Dict[str, str]]:
        chunks: List[Dict[str, str]] = []

        scenario_text = self._build_scenario_text(table_zh, table_info)
        if scenario_text:
            chunks.append(
                {
                    "chunk_type": "scenario",
                    "content": scenario_text,
                    "content_norm": normalize_text(scenario_text),
                }
            )

        subject_summary = self._build_subject_summary(table_zh, table_info)
        if subject_summary:
            chunks.append(
                {
                    "chunk_type": "supported_subjects_summary",
                    "content": subject_summary,
                    "content_norm": normalize_text(subject_summary),
                }
            )

        schema_summary = self._make_schema_summary(table_en, table_zh)
        if schema_summary:
            chunks.append(
                {
                    "chunk_type": "schema_summary",
                    "content": schema_summary,
                    "content_norm": normalize_text(schema_summary),
                }
            )

        if not chunks:
            overview = f"{table_zh} 用于业务查询，英文表名为 {table_en}"
            chunks.append(
                {
                    "chunk_type": "table_overview",
                    "content": overview,
                    "content_norm": normalize_text(overview),
                }
            )
        return chunks

    def _build_scenario_text(self, table_zh: str, table_info: dict) -> str:
        category = table_info.get("cate", "业务数据")
        level_text = "省级" if table_info.get("is_sheng", 0) else "全省或地市级"
        return f"{table_zh} 适用场景: 用于{category}相关查询，数据层级为{level_text}"

    def _build_subject_summary(self, table_zh: str, table_info: dict) -> str:
        names = table_info.get("project_name", [])
        keys = table_info.get("project_key", [])
        metric_count = sum(len(fields) for fields in table_info.get("unit", {}).values())
        subject_fields = "、".join(names[:3]) if names else "未识别"
        code_fields = "、".join(keys[:3]) if keys else "未识别"
        return (
            f"{table_zh} 支持主题摘要: 名称字段 {subject_fields}; "
            f"编码字段 {code_fields}; 已识别指标字段 {metric_count} 个"
        )

    def _make_schema_summary(self, table_en: str, table_zh: str) -> str:
        schema_table = self._schema_tables.get(table_en, {})
        field_comments = []
        for column_name, field in schema_table.get("fields", {}).items():
            comment = field.get("comment")
            if not comment:
                continue
            field_comments.append(f"{column_name}:{comment}")
        field_comments = unique_list(field_comments[:12])
        if not field_comments:
            return ""
        return f"{table_zh} 关键字段: " + "；".join(field_comments)

    def _resolve_subject_name_column(self, table_en: str, table_info: dict) -> Optional[str]:
        schema_fields = self._schema_tables[table_en]["fields"]
        comment_to_column = {field["comment"]: name for name, field in schema_fields.items()}
        for comment in table_info.get("project_name", []):
            if comment in comment_to_column:
                return comment_to_column[comment]
        for fallback in ("XM_NAME", "KM_NAME"):
            if fallback in schema_fields:
                return fallback
        return None

    def _resolve_subject_code_column(self, table_en: str, table_info: dict) -> Optional[str]:
        schema_fields = self._schema_tables[table_en]["fields"]
        comment_to_column = {field["comment"]: name for name, field in schema_fields.items()}
        for comment in table_info.get("project_key", []):
            if comment in comment_to_column:
                return comment_to_column[comment]
        for fallback in ("XM_CODE", "KM_CODE"):
            if fallback in schema_fields:
                return fallback
        return None

    def _infer_subject_type(self, subject_name_column: str) -> str:
        if subject_name_column.startswith("KM_"):
            return "subject"
        if subject_name_column.startswith("XM_"):
            return "project"
        return "generic"
