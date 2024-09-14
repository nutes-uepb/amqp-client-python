from .timeout_exception import TimeoutException


class ResponseTimeoutException(TimeoutException):
    message: str = ""
    description: str = ""

    def __init__(self, message, description="") -> None:
        self.message = message
        self.description = description
