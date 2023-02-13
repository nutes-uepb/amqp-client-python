class EventBusException(Exception):
    message: str = None
    description: str = None

    def __init__(self, message, description="") -> None:
        self.message = message
        self.description = description
