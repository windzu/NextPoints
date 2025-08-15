from .models.enums import ErrorCode


class SDKException(Exception):
    def __init__(self, code: ErrorCode, message: str, detail=None):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(f"{code}: {message}")


class TimeoutException(SDKException):
    pass
