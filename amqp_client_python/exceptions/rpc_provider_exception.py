from .eventbus_exception import EventBusException


class RpcProviderException(EventBusException):
    message: str = None
    description: str = None

    def __init__(self, message, description="") -> None:
        self.message = message
        self.description = description
