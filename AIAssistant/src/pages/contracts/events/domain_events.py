"""领域事件定义。"""


class UserQuestionReceivedEvent:
    """用户问题已接收事件。"""

    pass


class KnowledgeSourceIngestedEvent:
    """知识源已入库事件。"""

    pass


class SqlQueryExecutedEvent:
    """SQL 查询已执行事件。"""

    pass


class SystemConfigUpdatedEvent:
    """系统配置已更新事件。"""

    pass
