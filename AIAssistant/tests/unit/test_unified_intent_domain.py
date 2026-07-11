"""统一意图识别 domain 层单元测试。

覆盖 Text2SqlIntent、RagIntent、UnifiedIntentDict、DispatchPlan
及辅助函数 slots_ready / missing_slots。
"""

import pytest

from src.domain.intent.unified_intent import (
    DispatchPlan,
    RagIntent,
    Text2SqlIntent,
    UnifiedIntentDict,
    missing_slots,
    slots_ready,
)


class TestText2SqlIntent:
    """Text2SqlIntent 数据类测试。"""

    def test_default_values(self):
        t2s = Text2SqlIntent()
        assert t2s.business_module == ""
        assert t2s.subjects == []
        assert t2s.metrics == []
        assert t2s.query_type == "summary"
        assert t2s.compare_dimension == "none"
        assert t2s.compare_operator == "none"
        assert t2s.chart_hint == "auto"
        assert t2s.top_n == 0

    def test_custom_values(self):
        t2s = Text2SqlIntent(
            business_module="预算执行",
            account_book="一般公共预算",
            flow_type="收入",
            subjects=["税收收入", "非税收入"],
            metrics=["本月金额"],
        )
        assert t2s.business_module == "预算执行"
        assert t2s.subjects == ["税收收入", "非税收入"]
        assert len(t2s.subjects) == 2


class TestRagIntent:
    """RagIntent 数据类测试。"""

    def test_default_all_false(self):
        rag = RagIntent()
        assert rag.need_policy_basis is False
        assert rag.need_caliber_explanation is False
        assert rag.need_composition is False
        assert rag.need_data_value is False
        assert rag.original_question == ""

    def test_original_question_preserved(self):
        rag = RagIntent(original_question="什么是预算执行率")
        assert rag.original_question == "什么是预算执行率"


class TestUnifiedIntentDict:
    """UnifiedIntentDict 组合测试。"""

    def test_default_construction(self):
        d = UnifiedIntentDict()
        assert isinstance(d.text2sql, Text2SqlIntent)
        assert isinstance(d.rag, RagIntent)

    def test_design_doc_example1_hybrid(self):
        """设计文档示例1：混合问题。"""
        d = UnifiedIntentDict(
            text2sql=Text2SqlIntent(
                business_module="预算执行",
                account_book="一般公共预算",
                flow_type="收入",
                region_level="全省",
                time_text="2019年",
                time_start="201901",
                time_end="201912",
                time_grain="year",
                subjects=["一般公共预算收入"],
                metrics=["本月金额"],
                regions=["全省"],
                data_stage="执行数",
                chart_hint="pie",
            ),
            rag=RagIntent(
                need_composition=True,
                need_data_value=True,
                original_question="2019年全省一般公共预算收入总计多少，由哪几部分构成",
            ),
        )
        assert slots_ready(d.text2sql) is True
        assert d.rag.need_composition is True
        assert d.rag.original_question != ""

    def test_design_doc_example3_pure_rag(self):
        """设计文档示例3：纯文档问答。"""
        d = UnifiedIntentDict(
            text2sql=Text2SqlIntent(
                account_book="一般公共预算",
                flow_type="收入",
            ),
            rag=RagIntent(
                need_caliber_explanation=True,
                original_question="一般公共预算收入的口径是什么",
            ),
        )
        # subjects 和 metrics 为空 → text2sql 不执行
        assert bool(d.text2sql.subjects or d.text2sql.metrics) is False
        # need_caliber_explanation 为 True → rag 执行
        assert d.rag.need_caliber_explanation is True


class TestSlotsReady:
    """槽位校验函数测试。"""

    def test_all_slots_ready(self):
        t2s = Text2SqlIntent(
            time_text="2019年",
            time_start="201901",
            region_level="全省",
            flow_type="收入",
            metrics=["本月金额"],
            subjects=["一般公共预算收入"],
        )
        assert slots_ready(t2s) is True
        assert missing_slots(t2s) == []

    def test_missing_time(self):
        t2s = Text2SqlIntent(
            region_level="全省",
            flow_type="收入",
            metrics=["本月金额"],
        )
        assert slots_ready(t2s) is False
        assert "time" in missing_slots(t2s)

    def test_missing_region_level(self):
        t2s = Text2SqlIntent(
            time_text="2019年",
            time_start="201901",
            flow_type="收入",
            metrics=["本月金额"],
        )
        assert "region_level" in missing_slots(t2s)

    def test_missing_metrics(self):
        t2s = Text2SqlIntent(
            time_text="2019年",
            time_start="201901",
            region_level="全省",
            flow_type="收入",
        )
        assert "metrics" in missing_slots(t2s)

    def test_missing_flow_type(self):
        t2s = Text2SqlIntent(
            time_text="2019年",
            time_start="201901",
            region_level="全省",
            metrics=["本月金额"],
        )
        assert "flow_type" in missing_slots(t2s)

    def test_missing_multiple_slots(self):
        """示例4场景：缺少时间、地区层级、指标。"""
        t2s = Text2SqlIntent(
            business_module="预算执行",
            flow_type="支出",
            subjects=["卫生健康支出"],
            data_stage="执行数",
        )
        missing = missing_slots(t2s)
        assert "time" in missing
        assert "region_level" in missing
        assert "metrics" in missing

    def test_generic_metrics_only(self):
        t2s = Text2SqlIntent(
            time_text="2019年",
            time_start="201901",
            region_level="全省",
            flow_type="收入",
            metrics=["情况", "规模"],
        )
        assert "metrics" in missing_slots(t2s)


class TestDispatchPlan:
    """DispatchPlan 测试。"""

    def test_default(self):
        plan = DispatchPlan()
        assert plan.text2sql is False
        assert plan.rag is False
        assert plan.clarify is False
        assert plan.missing == []

    def test_hybrid_plan(self):
        plan = DispatchPlan(text2sql=True, rag=True)
        assert plan.text2sql is True
        assert plan.rag is True
        assert plan.clarify is False

    def test_clarify_plan(self):
        plan = DispatchPlan(
            clarify=True,
            missing=["time", "region_level", "metrics"],
        )
        assert plan.clarify is True
        assert len(plan.missing) == 3
