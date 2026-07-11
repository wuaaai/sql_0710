"""问数主流程编排模块。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from charting import build_chart_config
from dameng_executor import DamengExecutor
from entity_resolver import EntityResolver, ResolvedEntities
from intent import UserIntent, build_query_plan
from query_compiler import CompiledQuery, QueryCompiler
from query_plan import QueryPlan, SlotValidationResult, validate_query_plan
from result_analyzer import AnalysisResult, ResultAnalyzer


@dataclass
class PipelineResult:
    """保存一次问数流程的完整中间结果和最终结果。"""

    plan: QueryPlan
    intent: UserIntent
    resolved: ResolvedEntities
    compiled: CompiledQuery
    rows: List[Dict[str, Any]]
    analysis: AnalysisResult
    chart: Dict[str, Any]


class ClarifyRequiredError(Exception):
    """表示这是问数问题，但当前还缺少必要槽位。"""

    def __init__(self, validation: SlotValidationResult):
        super().__init__(validation.message)
        self.validation = validation


class FiscalQaPipeline:
    """把意图识别、选表、编译 SQL、执行查询和结果分析串起来。"""

    def __init__(
        self,
        llm_client,
        entity_resolver: EntityResolver,
        compiler: QueryCompiler,
        executor: DamengExecutor,
        analyzer: ResultAnalyzer,
    ):
        """保存整条问数流水线所依赖的组件。"""
        self._llm_client = llm_client
        self._entity_resolver = entity_resolver
        self._compiler = compiler
        self._executor = executor
        self._analyzer = analyzer

    def run(self, question: str) -> PipelineResult:
        """执行一次完整的智能问数流程。"""
        plan = build_query_plan(self._llm_client, question)
        validation = validate_query_plan(plan)
        if not validation.ready_for_sql:
            raise ClarifyRequiredError(validation)

        intent = UserIntent.from_plan(plan)
        resolved = self._entity_resolver.resolve(plan)
        compiled = self._compiler.compile(resolved)
        rows = self._executor.query(compiled.sql)
        analysis = self._analyzer.analyze(
            question=question,
            table_zh=resolved.selected_table.table_zh,
            plan=plan,
            sql=compiled.sql,
            rows=rows,
        )
        chart = build_chart_config(intent, rows, "、".join(compiled.metric_labels))
        return PipelineResult(
            plan=plan,
            intent=intent,
            resolved=resolved,
            compiled=compiled,
            rows=rows,
            analysis=analysis,
            chart=chart,
        )
