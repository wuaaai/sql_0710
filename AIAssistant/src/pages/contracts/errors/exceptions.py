"""统一异常定义。"""


class BusinessException(Exception):
    """统一业务异常对象，包含错误码和错误消息。"""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)
