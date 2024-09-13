class EventBusException(Exception):
    message: str = ""
    description: str = ""

    def __init__(self, message: str, description="") -> None:
        self.message = message
        self.description = description
