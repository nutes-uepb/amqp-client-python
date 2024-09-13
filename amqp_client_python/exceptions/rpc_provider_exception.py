from .eventbus_exception import EventBusException


class RpcProviderException(EventBusException):
    message: str = ""
    description: str = ""

    def __init__(self, message: str, description="") -> None:
        self.message = message
        self.description = description
