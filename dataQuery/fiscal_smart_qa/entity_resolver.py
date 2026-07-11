"""实体解析与新版选表模块。

这个模块负责把 QueryPlan 进一步解析成可执行查询所需的实体信息，
包括目标表、命中的科目、命中的指标，以及候选表排序结果。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from domain_router import BusinessDomainRouter, DomainRoute
from metadata import MetadataBundle, TableFilterResult
from normalizer import normalize_text
from query_plan import QueryPlan
from vector_retriever import SearchHit, VectorRetriever


@dataclass
class TableCandidate:
    """表示一张进入候选集的表。"""

    table_en: str
    table_zh: str
    score: float
    reason: Dict[str, float | str] = field(default_factory=dict)


@dataclass
class ResolvedEntities:
    """保存实体解析后的完整结果。"""

    plan: QueryPlan
    selected_table: TableCandidate
    table_candidates: List[TableCandidate]
    subject_hits: List[SearchHit]
    metric_hits: List[SearchHit]
    domain_route: DomainRoute
    allowed_tables: List[str]


class EntityResolver:
    """执行新版两层选表和实体命中流程。"""

    def __init__(self, retriever: VectorRetriever, metadata: MetadataBundle):
        """保存实体解析过程依赖的组件。"""
        self._retriever = retriever
        self._metadata = metadata
        self._domain_router = BusinessDomainRouter()

    def resolve(self, plan: QueryPlan) -> ResolvedEntities:
        """根据 QueryPlan 解析出表、科目和指标。"""
        domain_route = self._domain_router.route(plan)
        table_filter = self._metadata.filter_tables(domain_route)

        desc_hits = self._retriever.search_table_profiles(
            plan.raw_question,
            limit=20,
            allowed_tables=table_filter.allowed_tables,
        )
        metric_query_text = " ".join(plan.metrics) if plan.metrics else plan.raw_question
        metric_hits = self._retriever.search_metric_aliases(
            metric_query_text,
            limit=20,
            allowed_tables=table_filter.allowed_tables,
        )

        all_exact_subject_hits: List[SearchHit] = []
        all_vector_subject_hits: List[SearchHit] = []
        for subject_query in plan.subjects:
            normalized_subject = normalize_text(subject_query)
            all_exact_subject_hits.extend(
                self._retriever.find_exact_subjects(
                    normalized_subject,
                    limit=10,
                    allowed_tables=table_filter.allowed_tables,
                )
            )
            all_vector_subject_hits.extend(
                self._retriever.search_subject_bindings(
                    subject_query,
                    limit=10,
                    allowed_tables=table_filter.allowed_tables,
                )
            )

        if not plan.subjects:
            all_vector_subject_hits.extend(
                self._retriever.search_subject_bindings(
                    plan.raw_question,
                    limit=10,
                    allowed_tables=table_filter.allowed_tables,
                )
            )

        table_candidates = self._score_tables(
            plan=plan,
            desc_hits=desc_hits,
            metric_hits=metric_hits,
            exact_subject_hits=all_exact_subject_hits,
            vector_subject_hits=all_vector_subject_hits,
            table_filter=table_filter,
        )
        if not table_candidates:
            raise ValueError("未找到可用的候选表，请先确认向量库和表能力矩阵已正确构建。")

        selected_table = table_candidates[0]
        subject_hits = _pick_subject_hits(
            all_exact_subject_hits,
            all_vector_subject_hits,
            selected_table.table_en,
            plan.subjects,
        )
        selected_metric_hits = _pick_metric_hits(metric_hits, selected_table.table_en, plan.metrics)

        return ResolvedEntities(
            plan=plan,
            selected_table=selected_table,
            table_candidates=table_candidates[:5],
            subject_hits=subject_hits,
            metric_hits=selected_metric_hits,
            domain_route=domain_route,
            allowed_tables=table_filter.allowed_tables,
        )

    def _score_tables(
        self,
        plan: QueryPlan,
        desc_hits: List[SearchHit],
        metric_hits: List[SearchHit],
        exact_subject_hits: List[SearchHit],
        vector_subject_hits: List[SearchHit],
        table_filter: TableFilterResult,
    ) -> List[TableCandidate]:
        """综合描述、指标、科目和能力矩阵得分，对候选表排序。"""
        stats: Dict[str, Dict[str, float]] = {}
        for hit in desc_hits:
            stats.setdefault(hit.table_en, {"desc": 0.0, "subject": 0.0, "subject_exact": 0.0, "metric": 0.0})
            stats[hit.table_en]["desc"] = max(stats[hit.table_en]["desc"], hit.score)
        for hit in metric_hits:
            stats.setdefault(hit.table_en, {"desc": 0.0, "subject": 0.0, "subject_exact": 0.0, "metric": 0.0})
            stats[hit.table_en]["metric"] = max(stats[hit.table_en]["metric"], hit.score)
        for hit in vector_subject_hits:
            stats.setdefault(hit.table_en, {"desc": 0.0, "subject": 0.0, "subject_exact": 0.0, "metric": 0.0})
            stats[hit.table_en]["subject"] = max(stats[hit.table_en]["subject"], hit.score)
        for hit in exact_subject_hits:
            stats.setdefault(hit.table_en, {"desc": 0.0, "subject": 0.0, "subject_exact": 0.0, "metric": 0.0})
            stats[hit.table_en]["subject_exact"] = 1.0

        candidates: List[TableCandidate] = []
        for table_en, values in stats.items():
            table_zh, _ = self._metadata.get_table_info_by_en(table_en)
            budget_bonus = _budget_bonus(table_zh or "", plan.budget_scope)
            capability_bonus = table_filter.capability_bonus.get(table_en, 0.0)
            final_score = (
                0.35 * values["desc"] +
                0.20 * values["subject"] +
                0.15 * values["metric"] +
                0.10 * values["subject_exact"] +
                budget_bonus +
                capability_bonus
            )
            candidates.append(
                TableCandidate(
                    table_en=table_en,
                    table_zh=table_zh or table_en,
                    score=round(final_score, 6),
                    reason={
                        "desc_score": round(values["desc"], 6),
                        "subject_score": round(values["subject"], 6),
                        "metric_score": round(values["metric"], 6),
                        "subject_exact": round(values["subject_exact"], 6),
                        "budget_bonus": round(budget_bonus, 6),
                        "capability_bonus": round(capability_bonus, 6),
                        "capability_reason": " | ".join(table_filter.reasons.get(table_en, [])),
                    },
                )
            )

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates


def _pick_subject_hits(
    exact_hits: List[SearchHit],
    vector_hits: List[SearchHit],
    table_en: str,
    subjects: List[str],
) -> List[SearchHit]:
    """为当前选中的表挑出最合适的科目命中结果。"""
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
    """为当前选中的表挑出最合适的指标命中结果。"""
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
    """如果预算口径与表名明显一致，则给一点加分。"""
    if not budget_scope:
        return 0.0
    if budget_scope in table_zh:
        return 0.08
    return -0.02
