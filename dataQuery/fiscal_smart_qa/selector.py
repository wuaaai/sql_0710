"""旧版选表模块。

该模块保留原有“全表向量竞争”的方式，便于兼容旧代码。
新版扩展方案建议优先使用 `entity_resolver.py` 中的两层选表流程。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from intent import UserIntent
from metadata import MetadataBundle
from normalizer import normalize_text
from vector_retriever import SearchHit, VectorRetriever


@dataclass
class SelectedTable:
    """表示旧版流程中选中的候选表。"""

    table_en: str
    table_zh: str
    score: float
    reason: Dict[str, float] = field(default_factory=dict)


@dataclass
class SelectionResult:
    """保存旧版选表和实体命中结果。"""

    selected_table: SelectedTable
    subject_hit: Optional[SearchHit]
    subject_hits: List[SearchHit]
    metric_hit: Optional[SearchHit]
    metric_hits: List[SearchHit]
    table_candidates: List[SelectedTable]


class TableSelector:
    """使用旧版方式在全表范围内做向量召回和排序。"""

    def __init__(self, retriever: VectorRetriever, metadata: MetadataBundle):
        """保存向量检索器和元数据。"""
        self._retriever = retriever
        self._metadata = metadata

    def select(self, intent: UserIntent) -> SelectionResult:
        """根据用户意图选择最合适的表、科目和指标。"""
        desc_hits = self._retriever.search_table_profiles(intent.raw_question, limit=8)
        metric_query_text = " ".join(intent.metrics) if intent.metrics else (intent.metric or intent.raw_question)
        metric_hits = self._retriever.search_metric_aliases(metric_query_text, limit=12)

        all_exact_subject_hits: List[SearchHit] = []
        all_vector_subject_hits: List[SearchHit] = []
        subject_queries = intent.subjects or ([intent.subject] if intent.subject else [])
        for subject_query in subject_queries:
            normalized_subject = normalize_text(subject_query)
            all_exact_subject_hits.extend(self._retriever.find_exact_subjects(normalized_subject, limit=10))
            all_vector_subject_hits.extend(self._retriever.search_subject_bindings(subject_query, limit=8))

        if not subject_queries:
            all_vector_subject_hits.extend(self._retriever.search_subject_bindings(intent.raw_question, limit=8))

        stats: Dict[str, Dict[str, float]] = {}
        for hit in desc_hits:
            stats.setdefault(hit.table_en, {"desc": 0.0, "subject": 0.0, "subject_exact": 0.0, "metric": 0.0})
            stats[hit.table_en]["desc"] = max(stats[hit.table_en]["desc"], hit.score)
        for hit in metric_hits:
            stats.setdefault(hit.table_en, {"desc": 0.0, "subject": 0.0, "subject_exact": 0.0, "metric": 0.0})
            stats[hit.table_en]["metric"] = max(stats[hit.table_en]["metric"], hit.score)
        for hit in all_vector_subject_hits:
            stats.setdefault(hit.table_en, {"desc": 0.0, "subject": 0.0, "subject_exact": 0.0, "metric": 0.0})
            stats[hit.table_en]["subject"] = max(stats[hit.table_en]["subject"], hit.score)
        for hit in all_exact_subject_hits:
            stats.setdefault(hit.table_en, {"desc": 0.0, "subject": 0.0, "subject_exact": 0.0, "metric": 0.0})
            stats[hit.table_en]["subject_exact"] = 1.0

        candidates: List[SelectedTable] = []
        for table_en, values in stats.items():
            table_zh, _ = self._metadata.get_table_info_by_en(table_en)
            bonus = _budget_bonus(table_zh or "", intent.budget_scope)
            final_score = (
                0.45 * values["desc"] +
                0.25 * values["subject"] +
                0.20 * values["metric"] +
                0.15 * values["subject_exact"] +
                bonus
            )
            candidates.append(
                SelectedTable(
                    table_en=table_en,
                    table_zh=table_zh or table_en,
                    score=round(final_score, 6),
                    reason={
                        "desc_score": round(values["desc"], 6),
                        "subject_score": round(values["subject"], 6),
                        "metric_score": round(values["metric"], 6),
                        "subject_exact": round(values["subject_exact"], 6),
                        "budget_bonus": round(bonus, 6),
                    },
                )
            )

        if not candidates:
            raise ValueError("未找到可用的候选表，请先确认向量库已经完成构建。")

        candidates.sort(key=lambda item: item.score, reverse=True)
        selected = candidates[0]

        subject_hits = _pick_subject_hits(all_exact_subject_hits, all_vector_subject_hits, selected.table_en, subject_queries)
        subject_hit = subject_hits[0] if subject_hits else None

        selected_metric_hits = _pick_metric_hits(metric_hits, selected.table_en, intent.metrics)
        metric_hit = selected_metric_hits[0] if selected_metric_hits else _pick_best_hit(metric_hits, selected.table_en)

        return SelectionResult(
            selected_table=selected,
            subject_hit=subject_hit,
            subject_hits=subject_hits,
            metric_hit=metric_hit,
            metric_hits=selected_metric_hits,
            table_candidates=candidates[:5],
        )


def _pick_best_hit(hits: List[SearchHit], table_en: str) -> Optional[SearchHit]:
    """在指定表中挑出得分最高的一条命中。"""
    matched = [hit for hit in hits if hit.table_en == table_en]
    if not matched:
        return None
    matched.sort(key=lambda item: item.score, reverse=True)
    return matched[0]


def _pick_subject_hits(
    exact_hits: List[SearchHit],
    vector_hits: List[SearchHit],
    table_en: str,
    subjects: List[str],
) -> List[SearchHit]:
    """为旧版流程挑选科目命中结果。"""
    output: List[SearchHit] = []
    used_codes = set()
    used_names = set()

    for subject in subjects:
        normalized_subject = normalize_text(subject)
        matched = [
            hit for hit in exact_hits
            if hit.table_en == table_en and (
                hit.payload.get("subject_name_norm") == normalized_subject
                or normalized_subject in str(hit.payload.get("subject_name_norm", ""))
                or str(hit.payload.get("subject_name_norm", "")) in normalized_subject
            )
        ]
        if not matched:
            matched = [
                hit for hit in vector_hits
                if hit.table_en == table_en and (
                    subject in str(hit.payload.get("subject_name", ""))
                    or normalized_subject in str(hit.payload.get("subject_name_norm", ""))
                )
            ]

        if not matched:
            continue

        matched.sort(key=lambda item: item.score, reverse=True)
        for hit in matched:
            code = hit.payload.get("select_code")
            name = hit.payload.get("subject_name")
            if code and code in used_codes:
                continue
            if name and name in used_names:
                continue
            output.append(hit)
            if code:
                used_codes.add(code)
            if name:
                used_names.add(name)
            break

    if output:
        return output

    fallback_hits = [hit for hit in exact_hits + vector_hits if hit.table_en == table_en]
    fallback_hits.sort(key=lambda item: item.score, reverse=True)
    return fallback_hits[:1]


def _pick_metric_hits(hits: List[SearchHit], table_en: str, metrics: List[str]) -> List[SearchHit]:
    """为旧版流程挑选指标命中结果。"""
    matched = [hit for hit in hits if hit.table_en == table_en]
    if not matched:
        return []

    if not metrics:
        matched.sort(key=lambda item: item.score, reverse=True)
        return matched[:1]

    output: List[SearchHit] = []
    used_columns = set()
    lower_metrics = [item.lower() for item in metrics]
    for metric_name in lower_metrics:
        best_hit = None
        best_score = -1.0
        for hit in matched:
            payload_metric_name = str(hit.payload.get("metric_name", "")).lower()
            payload_metric_norm = str(hit.payload.get("metric_name_norm", "")).lower()
            if metric_name not in payload_metric_name and metric_name not in payload_metric_norm:
                continue
            column_name = hit.payload.get("column_name")
            if column_name in used_columns:
                continue
            if hit.score > best_score:
                best_hit = hit
                best_score = hit.score
        if best_hit:
            output.append(best_hit)
            used_columns.add(best_hit.payload.get("column_name"))

    if output:
        return output

    matched.sort(key=lambda item: item.score, reverse=True)
    deduped: List[SearchHit] = []
    for hit in matched:
        column_name = hit.payload.get("column_name")
        if column_name in used_columns:
            continue
        deduped.append(hit)
        used_columns.add(column_name)
        if len(deduped) >= max(1, len(metrics)):
            break
    return deduped


def _budget_bonus(table_zh: str, budget_scope: str) -> float:
    """预算口径和表名接近时给一点加分。"""
    if not budget_scope:
        return 0.0
    if budget_scope in table_zh:
        return 0.08
    return -0.02
