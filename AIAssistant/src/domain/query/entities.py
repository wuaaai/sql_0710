"""查询领域实体定义。"""


class QueryIntent:
    """表示用户查询意图，负责承载槽位、指标、维度、过滤条件和查询目标。"""

    pass


class SchemaCandidate:
    """表示候选表结构或候选字段集合，用于承载选表和映射阶段的中间结果。"""

    pass


class SqlQueryPlan:
    """表示一份待执行的 SQL 方案，负责承载 SQL 文本、执行参数和风险提示。"""

    pass


class SqlExecutionResult:
    """表示 SQL 执行结果，负责承载返回数据、执行耗时、异常信息和数据来源。"""

    pass
