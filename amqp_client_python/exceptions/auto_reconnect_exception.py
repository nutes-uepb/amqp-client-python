from .eventbus_exception import EventBusException


class AutoReconnectException(EventBusException):
    message: str = ""
    description: str = ""

    def __init__(self, message, description="") -> None:
        self.message = message
        self.description = description
