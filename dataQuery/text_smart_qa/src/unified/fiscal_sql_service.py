from __future__ import annotations

import asyncio
import sys
import traceback
from pathlib import Path

from text_smart_qa.src.agent.utils.log_utils import log
from text_smart_qa.src.unified.chart_cache import save_chart_record_safe
from text_smart_qa.src.unified.models import FiscalQaResult


class FiscalSqlService:
    """封装 fiscal_smart_qa 的自然语言转 SQL 流程。"""

    def __init__(self):
        self._pipeline = None

    async def answer(self, question: str) -> FiscalQaResult:
        return await asyncio.to_thread(self._answer_sync, question)

    def _answer_sync(self, question: str) -> FiscalQaResult:
        try:
            pipeline = self._get_pipeline()
            result = pipeline.run(question)
            summary = self._build_summary(result, question)
            return FiscalQaResult(
                answer=summary["answer_text"],
                sql=result.compiled.sql,
                rows=result.rows,
                chart=result.chart,
                facts=result.analysis.facts,
                summary=summary,
                success=True,
                error="",
                slot_status="ready",
            )
        except Exception as exc:
            if exc.__class__.__name__ == "ClarifyRequiredError":
                validation = getattr(exc, "validation", None)
                missing_slots = list(getattr(validation, "missing_slots", []) or [])
                slot_values = dict(getattr(validation, "slot_values", {}) or {})
                clarify_message = getattr(validation, "message", "") or str(exc)
                return FiscalQaResult(
                    answer=clarify_message,
                    summary={
                        "answer_text": clarify_message,
                        "missing_slots": missing_slots,
                        "slot_values": slot_values,
                    },
                    success=False,
                    error="need_clarify",
                    slot_status="clarify",
                    missing_slots=missing_slots,
                    slot_values=slot_values,
                    need_clarify=True,
                )
            if isinstance(exc, ModuleNotFoundError):
                message = self._build_dependency_error_message(exc)
                log.error(f"[FiscalSqlService] 智能问数依赖缺失: {message}")
                log.error(traceback.format_exc())
                return FiscalQaResult(
                    answer=message,
                    summary={"answer_text": message},
                    success=False,
                    error=message,
                )
            if isinstance(exc, ImportError):
                message = self._build_import_error_message(exc)
                log.error(f"[FiscalSqlService] 智能问数导入失败: {message}")
                log.error(traceback.format_exc())
                return FiscalQaResult(
                    answer=message,
                    summary={"answer_text": message},
                    success=False,
                    error=message,
                )

            message = f"智能问数执行失败：{exc}"
            log.error(f"[FiscalSqlService] {message}")
            log.error(traceback.format_exc())
            return FiscalQaResult(
                answer=message,
                summary={"answer_text": message},
                success=False,
                error=message,
            )

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline

        fiscal_dir = self._get_fiscal_project_dir()
        if str(fiscal_dir) not in sys.path:
            sys.path.insert(0, str(fiscal_dir))

        from fiscal_smart_qa.config import load_config
        from fiscal_smart_qa.dameng_executor import DamengExecutor
        from fiscal_smart_qa.embedding_client import EmbeddingClient
        from fiscal_smart_qa.entity_resolver import EntityResolver
        from fiscal_smart_qa.llm_client import DeepSeekClient
        from fiscal_smart_qa.metadata import load_metadata
        from fiscal_smart_qa.qa_pipeline import FiscalQaPipeline
        from fiscal_smart_qa.query_compiler import QueryCompiler
        from fiscal_smart_qa.result_analyzer import ResultAnalyzer
        from fiscal_smart_qa.vector_retriever import VectorRetriever

        config = load_config()
        metadata = load_metadata(config.metadata)
        llm_client = DeepSeekClient(config.llm)
        embeddings = EmbeddingClient(config.embedding)
        retriever = VectorRetriever(config.pgvector, embeddings)
        resolver = EntityResolver(retriever, metadata)
        compiler = QueryCompiler(metadata, schema_name=config.dameng.schema)
        executor = DamengExecutor(config.dameng)
        analyzer = ResultAnalyzer(llm_client)

        self._pipeline = FiscalQaPipeline(
            llm_client=llm_client,
            entity_resolver=resolver,
            compiler=compiler,
            executor=executor,
            analyzer=analyzer,
        )
        return self._pipeline

    @staticmethod
    def _get_fiscal_project_dir() -> Path:
        workspace_dir = Path(__file__).resolve().parents[3]
        return workspace_dir / "fiscal_smart_qa"

    @staticmethod
    def _build_dependency_error_message(exc: ModuleNotFoundError) -> str:
        """把缺少依赖的异常转换成更容易理解的提示。"""
        module_name = getattr(exc, "name", "") or str(exc)
        if module_name == "pg8000":
            return (
                "智能问数模块暂时无法使用：当前运行环境缺少 `pg8000` 依赖。"
                "请在 text_smart_qa 项目环境中安装 `pg8000`，用于连接 PostgreSQL pgvector。"
            )
        if module_name == "dmPython":
            return (
                "智能问数模块暂时无法使用：当前运行环境缺少 `dmPython` 驱动。"
                "请在 text_smart_qa 项目环境中安装达梦数据库驱动 `dmPython`。"
            )
        return f"智能问数模块暂时无法使用：缺少依赖 `{module_name}`。"

    @staticmethod
    def _build_import_error_message(exc: ImportError) -> str:
        """把通用导入异常转换成统一的提示。"""
        text = str(exc)
        if "dmPython is required for Dameng access" in text:
            return (
                "智能问数模块暂时无法使用：当前运行环境未安装 `dmPython`，"
                "因此无法连接达梦数据库执行 SQL。"
            )
        return f"智能问数模块初始化失败：{text}"

    @staticmethod
    def _build_summary(result, question: str) -> dict:
        """把智能问数原始结果整理成更适合前端展示的摘要结构。"""
        plan = result.plan
        resolved = result.resolved
        row_count = len(result.rows)
        chart_key = (question or "").strip()

        business_module = plan.business_module or "未明确业务域"
        account_book = plan.account_book or "未明确四本账口径"
        flow_type = plan.flow_type or "未明确收支方向"
        region_level = plan.region_level or "未明确地区层级"
        region_name = plan.region or region_level
        subject_text = "、".join(plan.subjects) if plan.subjects else "未明确科目"
        metric_text = "、".join(plan.metrics) if plan.metrics else "未明确指标"
        time_text = plan.time_text or "未明确时间范围"
        table_name = resolved.selected_table.table_zh or resolved.selected_table.table_en
        lines = [
            "已完成数据库查询。",
            f"本次查询使用的业务域是“{business_module}”，数据表是“{table_name}”。",
            f"查询范围是“{time_text}”“{region_name}”，科目是“{subject_text}”，指标是“{metric_text}”。",
            f"口径识别结果：四本账是“{account_book}”，收支方向是“{flow_type}”，地区层级是“{region_level}”。",
        ]

        if row_count > 0:
            lines.append(f"本次共查询到 {row_count} 条记录。")

        analysis_summary = (result.analysis.summary or "").strip()
        if analysis_summary:
            lines.append(f"结果概览：{analysis_summary}")

        detail_table_markdown = _build_markdown_table(result.rows)
        if detail_table_markdown:
            lines.append("数据查询明细如下：")
            lines.append(detail_table_markdown)

        if result.chart.get("can_plot"):
            saved, error_message = save_chart_record_safe(chart_key, result.chart)
            if not saved:
                lines.append("说明：本次图表缓存未写入成功，但不影响文字结果查看。")
                log.warning(f"[FiscalSqlService] 图表缓存写入失败，question={chart_key}, error={error_message}")

        answer_text = "\n".join(lines)
        return {
            "id": chart_key,
            "question_key": chart_key,
            "answer_text": answer_text,
            "table_name": table_name,
            "table_code": resolved.selected_table.table_en,
            "business_module": business_module,
            "account_book": account_book,
            "flow_type": flow_type,
            "region_level": region_level,
            "region_name": region_name,
            "time_text": time_text,
            "subjects": plan.subjects,
            "metrics": plan.metrics,
            "row_count": row_count,
            "analysis_summary": analysis_summary,
            "detail_rows": result.rows,
            "detail_table_markdown": detail_table_markdown,
            "chart_ready": bool(result.chart.get("can_plot")),
            "chart_type": result.chart.get("type", ""),
        }


def _build_markdown_table(rows: list[dict]) -> str:
    """把查询结果转成 Markdown 表格。"""
    if not rows:
        return ""

    headers = list(rows[0].keys())
    if not headers:
        return ""

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = []
        for header in headers:
            values.append(str(row.get(header, "")))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)
